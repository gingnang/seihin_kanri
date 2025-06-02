# materials/csv_loader.py - 画像パス正規化対応版
import pandas as pd
import os
from django.conf import settings
from .models import Material
from decimal import Decimal
import logging
import chardet
import re
from django.db import transaction

logger = logging.getLogger(__name__)


class MaterialCSVLoader:
    def __init__(self):
        self.data_dir = os.path.join(settings.BASE_DIR, 'data')
        self.csv_file = '原料マスタ詳細.csv'

    def normalize_image_path(self, image_path):
        """
        画像パスを正規化する関数

        入力例: "images\1.jpg" または "images\\1.jpg"
        出力例: "images/1.jpg"
        """
        if not image_path or pd.isna(image_path) or image_path == '':
            return ''

        # 文字列に変換
        path = str(image_path).strip()

        # 空文字チェック
        if not path:
            return ''

        # バックスラッシュをフォワードスラッシュに変換
        path = path.replace('\\', '/')

        # 複数のスラッシュを単一のスラッシュに変換
        path = re.sub(r'/+', '/', path)

        # 先頭のスラッシュを除去
        path = path.lstrip('/')

        print(f"画像パス正規化: '{image_path}' → '{path}'")
        return path

    def detect_encoding_comprehensive(self, file_path):
        encodings_to_try = ['cp932', 'shift_jis', 'utf-8', 'utf-8-sig']
        try:
            with open(file_path, 'rb') as f:
                raw_data = f.read(50000)
                detected = chardet.detect(raw_data)
                if detected['encoding'] and detected['confidence'] > 0.3:
                    detected_encoding = detected['encoding']
                    if detected_encoding not in encodings_to_try:
                        encodings_to_try.insert(0, detected_encoding)
        except Exception as e:
            print(f"chardet error: {e}")
        return encodings_to_try

    def find_csv_files(self):
        if not os.path.exists(self.data_dir):
            return []
        return [os.path.join(self.data_dir, f) for f in os.listdir(self.data_dir) if f.endswith('.csv')]

    def create_column_mapping(self, columns):
        mapping = {}
        for col in columns:
            if col == '原料ID':
                mapping['material_id'] = col
            if col == '原料名':
                mapping['material_name'] = col
            if col == '製造所':
                mapping['manufacturer'] = col
            if col == '販売者':
                mapping['supplier'] = col
            if col == '分類':
                mapping['category'] = col
            if col == '単価':
                mapping['unit_price'] = col
            if col == '正袋重量':
                mapping['main_bag_weight'] = col
            if col == 'ラベル用備考':
                mapping['label_note'] = col
            if col == '原料区分':
                mapping['material_category'] = col
            if col == '荷姿':
                mapping['packaging'] = col
            if col == '品質管理備考':
                mapping['qc_note'] = col
            if col == '使用剤形':
                mapping['usage_form'] = col
            if col == '規格':
                mapping['standard'] = col
            if col == '商品名':  # 商品名の追加
                mapping['product_name'] = col
            if col == '画像パス':  # 画像パスの追加
                mapping['image_path'] = col
        return mapping

    def clean_and_convert_value(self, value, field_name=''):
        """値のクリーニングと変換"""
        if pd.isna(value) or value == '':
            return ''

        value_str = str(value).strip()

        # 画像パスの特別処理
        if field_name == 'image_path':
            return self.normalize_image_path(value_str)

        # 数値フィールドの処理
        if field_name in ['unit_price', 'main_bag_weight']:
            cleaned = re.sub(r'[,¥\s]', '', value_str)
            return cleaned if cleaned else '0'

        return value_str

    def load_materials(self):
        """従来のload_materials（互換性維持）"""
        return self.load_materials_with_overwrite('update')

    def load_materials_with_overwrite(self, overwrite_mode='update'):
        """
        上書きモード対応のCSV読み込み

        Args:
            overwrite_mode (str):
                'update' - 既存データを更新（推奨）
                'replace' - 既存データを削除して新規作成
                'skip' - 既存データをスキップ
        """
        try:
            csv_files = self.find_csv_files()
            if not csv_files:
                return {'success': False, 'error': 'CSVファイルが見つかりません'}

            file_path = csv_files[0]
            encodings = self.detect_encoding_comprehensive(file_path)
            df = None
            used_encoding = None

            for encoding in encodings:
                try:
                    df = pd.read_csv(file_path, encoding=encoding, dtype=str)
                    used_encoding = encoding
                    print(f"CSVファイルを {encoding} で読み込み成功")
                    break
                except Exception as e:
                    print(f"エンコーディング {encoding} で読み込み失敗: {e}")
                    continue

            if df is None:
                return {'success': False, 'error': 'CSVファイルを読み込めません'}

            df = df.fillna('')
            mapping = self.create_column_mapping(df.columns)

            if 'material_id' not in mapping:
                return {'success': False, 'error': '原料ID列が見つかりません'}

            created = 0
            updated = 0
            skipped = 0
            errors = []
            image_path_processed = 0

            print(f"データ処理開始: {len(df)}行")

            with transaction.atomic():
                for idx, row in df.iterrows():
                    try:
                        material_id = self.clean_and_convert_value(row[mapping['material_id']], 'material_id')

                        if not material_id:
                            skipped += 1
                            continue

                        values = {}
                        for field, col in mapping.items():
                            if field != 'material_id':
                                cleaned_value = self.clean_and_convert_value(row[col], field)
                                values[field] = cleaned_value

                                # 画像パス処理のログ
                                if field == 'image_path' and cleaned_value:
                                    image_path_processed += 1
                                    print(f"画像パス処理 {image_path_processed}: {row[col]} → {cleaned_value}")

                        # 上書きモード処理
                        if overwrite_mode == 'update':
                            # 既存データを更新、なければ新規作成
                            material, was_created = Material.objects.update_or_create(
                                material_id=material_id,
                                defaults=values
                            )
                            if was_created:
                                created += 1
                            else:
                                updated += 1

                        elif overwrite_mode == 'replace':
                            # 既存データを削除してから新規作成
                            Material.objects.filter(material_id=material_id).delete()
                            values['material_id'] = material_id
                            Material.objects.create(**values)
                            created += 1

                        elif overwrite_mode == 'skip':
                            # 既存データがあればスキップ
                            if Material.objects.filter(material_id=material_id).exists():
                                skipped += 1
                            else:
                                values['material_id'] = material_id
                                Material.objects.create(**values)
                                created += 1

                    except Exception as e:
                        error_msg = f"行{idx + 1}: {str(e)}"
                        errors.append(error_msg)
                        print(f"エラー: {error_msg}")
                        skipped += 1
                        continue

            # 全データを有効化
            Material.objects.all().update(is_active=True)

            result = {
                'success': True,
                'created': created,
                'updated': updated,
                'skipped': skipped,
                'total_rows': len(df),
                'encoding_used': used_encoding,
                'columns': list(df.columns),
                'overwrite_mode': overwrite_mode,
                'errors': errors[:5] if errors else [],
                'image_paths_processed': image_path_processed
            }

            print(f"処理完了: 作成{created}, 更新{updated}, スキップ{skipped}, 画像パス処理{image_path_processed}")
            return result

        except Exception as e:
            error_msg = f"CSV読み込みエラー: {str(e)}"
            print(error_msg)
            return {'success': False, 'error': error_msg}

    def analyze_csv_structure(self):
        """CSV構造分析（既存メソッド）"""
        try:
            csv_files = self.find_csv_files()
            if not csv_files:
                return {'success': False, 'error': 'CSVファイルが見つかりません'}

            file_path = csv_files[0]
            encodings = self.detect_encoding_comprehensive(file_path)

            for encoding in encodings:
                try:
                    df = pd.read_csv(file_path, encoding=encoding, nrows=5)

                    # 重複チェック
                    duplicates = 0
                    unique_ids = 0
                    if '原料ID' in df.columns:
                        duplicates = df['原料ID'].duplicated().sum()
                        unique_ids = df['原料ID'].nunique()

                    return {
                        'success': True,
                        'encoding': encoding,
                        'total_rows': len(df),
                        'columns': list(df.columns),
                        'duplicates_in_sample': duplicates,
                        'unique_ids_in_sample': unique_ids,
                        'recommended_mapping': self.create_column_mapping(df.columns)
                    }
                except Exception:
                    continue

            return {'success': False, 'error': '読み込み可能なエンコーディングが見つかりません'}

        except Exception as e:
            return {'success': False, 'error': str(e)}