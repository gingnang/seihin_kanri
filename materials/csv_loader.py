# -*- coding: utf-8 -*-
import pandas as pd
import os
from django.conf import settings
from .models import Material
from decimal import Decimal
import logging
from django.db import transaction
import chardet
import re

logger = logging.getLogger(__name__)


class MaterialCSVLoader:
    def __init__(self):
        self.data_dir = os.path.join(settings.BASE_DIR, 'data')
        self.csv_file = '原料マスタ詳細.csv'

    def detect_encoding_comprehensive(self, file_path):
        """包括的なエンコーディング検出"""
        encodings_to_try = [
            'cp932',  # Shift_JIS (Windows) - 日本語で最も一般的
            'shift_jis',  # Shift_JIS
            'utf-8',  # UTF-8
            'utf-8-sig',  # UTF-8 with BOM
            'iso-2022-jp',  # JIS
            'euc-jp',  # EUC-JP
            'latin1',  # ISO-8859-1
        ]

        # chardetによる自動検出も試行
        try:
            with open(file_path, 'rb') as f:
                raw_data = f.read(50000)
                detected = chardet.detect(raw_data)
                if detected['encoding'] and detected['confidence'] > 0.5:
                    detected_encoding = detected['encoding']
                    if detected_encoding not in encodings_to_try:
                        encodings_to_try.insert(0, detected_encoding)
                    print(f"🔍 chardet検出: {detected_encoding} (信頼度: {detected['confidence']:.2f})")
        except:
            pass

        return encodings_to_try

    def load_materials(self):
        """原料CSVデータの完全読み込み"""
        try:
            file_path = os.path.join(self.data_dir, self.csv_file)
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"CSVファイルが見つかりません: {file_path}")

            encodings = self.detect_encoding_comprehensive(file_path)
            df = None
            used_encoding = None

            for encoding in encodings:
                try:
                    print(f"📖 エンコーディング '{encoding}' で読み込み中...")
                    df = pd.read_csv(file_path, encoding=encoding, dtype=str)
                    used_encoding = encoding
                    print(f"✅ 読み込み成功: {encoding}")
                    break
                except Exception as e:
                    print(f"❌ 読み込み失敗: {encoding}")
                    continue

            if df is None:
                raise ValueError("全てのエンコーディングで読み込み失敗")

            # データクリーニング
            df = df.fillna('')

            print(f"\n📊 CSV情報:")
            print(f"- エンコーディング: {used_encoding}")
            print(f"- 行数: {len(df)}")
            print(f"- 列数: {len(df.columns)}")
            print(f"- 列名: {list(df.columns)}")

            results = {
                'success': True,
                'created': 0,
                'updated': 0,
                'skipped': 0,
                'total_rows': len(df),
                'columns': list(df.columns),
                'encoding_used': used_encoding,
                'debug_info': []
            }

            # 列マッピング辞書（実際のCSVの列名に合わせて調整）
            column_mapping = {
                '原料ID': 'material_id',
                '原料名': 'material_name',
                '製造所': 'manufacturer',
                '販売者': 'supplier',
                '荷姿': 'application',
                '単価': 'unit_price',
                '正袋重量': 'order_quantity',
                '品質管理備考': 'remarks',
                '原料区分': 'material_category'
            }

            with transaction.atomic():
                for idx, row in df.iterrows():
                    try:
                        # 原料IDの取得（必須フィールド）
                        material_id = self.safe_get_value(row, '原料ID', '').strip()
                        if not material_id:
                            results['skipped'] += 1
                            continue

                        # 各フィールドの値を取得
                        material_name = self.safe_get_value(row, '原料名', f"原料_{material_id}")
                        manufacturer = self.safe_get_value(row, '製造所', '')
                        supplier = self.safe_get_value(row, '販売者', '')
                        application = self.safe_get_value(row, '荷姿', '')

                        # 備考の結合
                        remarks_parts = []
                        for col in ['品質管理備考', '生産本部備考', 'ラベル用備考']:
                            remark = self.safe_get_value(row, col, '').strip()
                            if remark:
                                remarks_parts.append(f"{col}: {remark}")
                        remarks = '; '.join(remarks_parts)

                        # 数値フィールドの処理
                        unit_price = self.safe_get_decimal(row, '単価')

                        # 正袋重量から発注量を取得
                        order_quantity_str = self.safe_get_value(row, '正袋重量', '0')
                        order_quantity = self.extract_numeric_from_string(order_quantity_str)

                        # 原料区分の取得
                        material_category = self.safe_get_value(row, '原料区分', 'Standard')

                        # デバッグ情報（最初の5行）
                        if idx < 5:
                            debug_info = {
                                'row': idx + 1,
                                'material_id': material_id,
                                'material_name': material_name[:30],
                                'manufacturer': manufacturer[:20],
                                'supplier': supplier[:20],
                                'unit_price': str(unit_price),
                                'order_quantity': str(order_quantity),
                                'category': material_category
                            }
                            results['debug_info'].append(debug_info)

                        # データベース保存
                        material, created = Material.objects.get_or_create(
                            material_id=material_id,
                            defaults={
                                'material_name': material_name,
                                'manufacturer': manufacturer,
                                'supplier': supplier,
                                'application': application,
                                'unit_price': unit_price,
                                'order_quantity': order_quantity,
                                'remarks': remarks,
                                'material_category': material_category,
                                'is_active': True
                            }
                        )

                        if created:
                            results['created'] += 1
                        else:
                            # 既存データの更新
                            material.material_name = material_name
                            material.manufacturer = manufacturer
                            material.supplier = supplier
                            material.application = application
                            material.unit_price = unit_price
                            material.order_quantity = order_quantity
                            material.remarks = remarks
                            material.material_category = material_category
                            material.is_active = True
                            material.save()
                            results['updated'] += 1

                    except Exception as e:
                        print(f"❌ 行{idx + 1}処理エラー: {e}")
                        results['skipped'] += 1
                        continue

            print(f"\n✅ 処理完了: 新規{results['created']}件, 更新{results['updated']}件, スキップ{results['skipped']}件")
            return results

        except Exception as e:
            logger.error(f"CSV読み込みエラー: {e}")
            return {'success': False, 'error': str(e)}

    def safe_get_value(self, row, column_name, default=''):
        """安全に値を取得"""
        if column_name not in row.index:
            return default
        try:
            value = str(row[column_name]).strip()
            return value if value not in ['nan', '', 'None', 'null', 'NaN'] else default
        except:
            return default

    def safe_get_decimal(self, row, column_name):
        """安全に数値を取得"""
        if column_name not in row.index:
            return Decimal('0')
        try:
            value_str = str(row[column_name]).strip()
            if value_str in ['nan', '', 'None', 'null', 'NaN']:
                return Decimal('0')

            # カンマや通貨記号を除去
            cleaned = re.sub(r'[^\d.-]', '', value_str)

            # 複数の小数点を処理
            if cleaned.count('.') > 1:
                parts = cleaned.split('.')
                cleaned = parts[0] + '.' + ''.join(parts[1:])

            return Decimal(cleaned) if cleaned and cleaned != '-' else Decimal('0')
        except:
            return Decimal('0')

    def extract_numeric_from_string(self, text):
        """文字列から数値を抽出（例: "25kg" → 25.0）"""
        try:
            # 数字と小数点のみ抽出
            numbers = re.findall(r'\d+\.?\d*', str(text))
            if numbers:
                return Decimal(numbers[0])
            return Decimal('0')
        except:
            return Decimal('0')

    def analyze_csv_structure(self):
        """CSV構造の分析"""
        try:
            file_path = os.path.join(self.data_dir, self.csv_file)
            if not os.path.exists(file_path):
                return {'error': f'CSVファイルが見つかりません: {file_path}'}

            encodings = self.detect_encoding_comprehensive(file_path)
            df = None
            used_encoding = None

            for encoding in encodings:
                try:
                    df = pd.read_csv(file_path, encoding=encoding, dtype=str)
                    used_encoding = encoding
                    break
                except Exception:
                    continue

            if df is None:
                return {'error': f'全てのエンコーディングで読み込み失敗: {encodings}'}

            # 欠損値を空文字に置換
            df = df.fillna('')

            # 列名の詳細分析
            columns_analysis = {}
            for col in df.columns:
                non_null = df[col].astype(str).str.strip().ne('').sum()
                unique = df[col].nunique()
                samples = df[col].dropna().astype(str).str.strip().head(5).tolist()

                columns_analysis[col] = {
                    'non_null_count': non_null,
                    'unique_count': unique,
                    'sample_values': samples
                }

            return {
                'success': True,
                'encoding': used_encoding,
                'total_rows': len(df),
                'columns': list(df.columns),
                'column_analysis': columns_analysis,
                'sample_data': df.head(3).to_dict('records')
            }

        except Exception as e:
            return {'error': f'分析エラー: {str(e)}'}

    def get_csv_summary(self):
        """CSV概要情報の取得"""
        file_path = os.path.join(self.data_dir, self.csv_file)
        if not os.path.exists(file_path):
            return {'exists': False, 'error': 'CSVファイルが見つかりません'}
        try:
            stat = os.stat(file_path)
            return {
                'exists': True,
                'file_size': stat.st_size,
                'modified_time': stat.st_mtime
            }
        except Exception as e:
            return {'exists': True, 'error': str(e)}