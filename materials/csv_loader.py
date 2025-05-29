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

        # chardetによる自動検出
        try:
            with open(file_path, 'rb') as f:
                raw_data = f.read(50000)
                detected = chardet.detect(raw_data)
                if detected['encoding'] and detected['confidence'] > 0.5:
                    detected_encoding = detected['encoding']
                    if detected_encoding not in encodings_to_try:
                        encodings_to_try.insert(0, detected_encoding)
                    print(f"🔍 chardet検出: {detected_encoding} (信頼度: {detected['confidence']:.2f})")
        except Exception as e:
            print(f"⚠️ chardet検出エラー: {e}")

        return encodings_to_try

    def create_flexible_column_mapping(self, columns):
        """実際の列名に基づいて柔軟な列マッピングを作成"""
        print(f"🔗 実際の列名: {columns}")

        # 列名パターンマッチング辞書
        patterns = {
            'material_id': ['原料ID', 'ＩＤ', 'ID', 'id', 'CD', 'cd', '品番', 'コード'],
            'material_name': ['原料名', '名前', '商品名', '品名', 'name', '製品名', '名称'],
            'manufacturer': ['製造所', 'メーカー', 'メーカ', '製造者', '製造元', 'maker', 'manufacturer'],
            'supplier': ['販売者', '発注先', '供給元', '供給先', '仕入先', 'supplier', '業者'],
            'application': ['荷姿', '適用', '用途', '使用用途', '目的', 'application'],
            'unit_price': ['単価', '価格', '値段', 'price', '金額', '単位価格'],
            'order_quantity': ['正袋重量', '発注量', '注文量', '購入量', 'quantity', '数量', '重量'],
            'remarks': ['備考', '品質管理備考', '注記', 'メモ', '説明', 'remarks', 'memo'],
            'material_category': ['原料区分', '区分', '分類', 'カテゴリ', 'category', '種類']
        }

        mapping = {}
        used_columns = set()

        for field, pattern_list in patterns.items():
            for col in columns:
                if col not in used_columns:
                    col_clean = str(col).strip()
                    for pattern in pattern_list:
                        if pattern in col_clean or col_clean in pattern:
                            mapping[field] = col
                            used_columns.add(col)
                            print(f"✅ マッピング: {field} ← '{col}'")
                            break
                    if field in mapping:
                        break

            if field not in mapping:
                print(f"⚠️ マッピング失敗: {field}")

        return mapping

    def load_materials(self):
        """原料CSVデータの読み込み（柔軟性を向上）"""
        try:
            file_path = os.path.join(self.data_dir, self.csv_file)

            # ファイル存在確認
            if not os.path.exists(file_path):
                # 他の可能なファイル名も試行
                possible_files = [
                    '原料マスタ詳細.csv',
                    'material_master.csv',
                    'genryou_master.csv',
                    'materials.csv'
                ]

                found_file = None
                for filename in possible_files:
                    test_path = os.path.join(self.data_dir, filename)
                    if os.path.exists(test_path):
                        found_file = test_path
                        print(f"📄 代替ファイルを発見: {filename}")
                        break

                if found_file:
                    file_path = found_file
                else:
                    # ディレクトリ内の全CSVファイルを表示
                    if os.path.exists(self.data_dir):
                        csv_files = [f for f in os.listdir(self.data_dir) if f.endswith('.csv')]
                        if csv_files:
                            print(f"📋 利用可能なCSVファイル: {csv_files}")
                            # 最初のCSVファイルを使用
                            file_path = os.path.join(self.data_dir, csv_files[0])
                            print(f"📄 自動選択: {csv_files[0]}")
                        else:
                            raise FileNotFoundError(f"dataディレクトリにCSVファイルが見つかりません: {self.data_dir}")
                    else:
                        raise FileNotFoundError(f"dataディレクトリが見つかりません: {self.data_dir}")

            print(f"📖 読み込み対象: {file_path}")

            # エンコーディング検出と読み込み
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
                    print(f"❌ 読み込み失敗: {encoding} - {str(e)[:50]}")
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

            # 柔軟な列マッピング
            column_mapping = self.create_flexible_column_mapping(df.columns)

            # 必須フィールドのチェック
            if 'material_id' not in column_mapping:
                # 最初の列を原料IDとして使用
                if len(df.columns) > 0:
                    column_mapping['material_id'] = df.columns[0]
                    print(f"⚠️ 原料ID列が見つからないため、最初の列を使用: {df.columns[0]}")
                else:
                    raise ValueError("原料ID列が特定できません")

            results = {
                'success': True,
                'created': 0,
                'updated': 0,
                'skipped': 0,
                'total_rows': len(df),
                'columns': list(df.columns),
                'encoding_used': used_encoding,
                'column_mapping': column_mapping,
                'debug_info': []
            }

            # データ処理
            with transaction.atomic():
                for idx, row in df.iterrows():
                    try:
                        # 原料IDの取得（必須）
                        material_id_col = column_mapping.get('material_id')
                        material_id = self.safe_get_value(row, material_id_col, '').strip()
                        if not material_id:
                            results['skipped'] += 1
                            continue

                        # 各フィールドの値を安全に取得
                        material_name_col = column_mapping.get('material_name')
                        material_name = self.safe_get_value(row, material_name_col, f"原料_{material_id}")

                        manufacturer_col = column_mapping.get('manufacturer')
                        manufacturer = self.safe_get_value(row, manufacturer_col, '')

                        supplier_col = column_mapping.get('supplier')
                        supplier = self.safe_get_value(row, supplier_col, '')

                        application_col = column_mapping.get('application')
                        application = self.safe_get_value(row, application_col, '')

                        # 備考の処理（複数列から結合の可能性）
                        remarks_parts = []
                        remarks_col = column_mapping.get('remarks')
                        if remarks_col:
                            remark = self.safe_get_value(row, remarks_col, '').strip()
                            if remark:
                                remarks_parts.append(remark)

                        # 他の備考関連列も探す
                        for col in df.columns:
                            if '備考' in str(col) and col != remarks_col:
                                remark = self.safe_get_value(row, col, '').strip()
                                if remark:
                                    remarks_parts.append(f"{col}: {remark}")

                        remarks = '; '.join(remarks_parts)

                        # 数値フィールドの処理
                        unit_price_col = column_mapping.get('unit_price')
                        unit_price = self.safe_get_decimal(row, unit_price_col)

                        order_quantity_col = column_mapping.get('order_quantity')
                        if order_quantity_col:
                            order_quantity_str = self.safe_get_value(row, order_quantity_col, '0')
                            order_quantity = self.extract_numeric_from_string(order_quantity_str)
                        else:
                            order_quantity = Decimal('0')

                        # 原料区分
                        category_col = column_mapping.get('material_category')
                        material_category = self.safe_get_value(row, category_col, 'Standard')

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

            print(f"\n✅ 処理完了:")
            print(f"   新規作成: {results['created']}件")
            print(f"   更新: {results['updated']}件")
            print(f"   スキップ: {results['skipped']}件")

            return results

        except Exception as e:
            error_msg = f"CSV読み込みエラー: {str(e)}"
            print(f"❌ {error_msg}")
            logger.error(error_msg)
            return {'success': False, 'error': error_msg}

    def safe_get_value(self, row, column_name, default=''):
        """安全に値を取得"""
        if not column_name or column_name not in row.index:
            return default
        try:
            value = str(row[column_name]).strip()
            return value if value not in ['nan', '', 'None', 'null', 'NaN'] else default
        except:
            return default

    def safe_get_decimal(self, row, column_name):
        """安全に数値を取得"""
        if not column_name or column_name not in row.index:
            return Decimal('0')
        try:
            value_str = str(row[column_name]).strip()
            if value_str in ['nan', '', 'None', 'null', 'NaN']:
                return Decimal('0')

            # カンマや通貨記号を除去
            cleaned = re.sub(r'[^\d.-]', '', value_str)

            if cleaned.count('.') > 1:
                parts = cleaned.split('.')
                cleaned = parts[0] + '.' + ''.join(parts[1:])

            return Decimal(cleaned) if cleaned and cleaned != '-' else Decimal('0')
        except:
            return Decimal('0')

    def extract_numeric_from_string(self, text):
        """文字列から数値を抽出"""
        try:
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

            # ファイル存在確認（他のファイルも確認）
            if not os.path.exists(file_path) and os.path.exists(self.data_dir):
                csv_files = [f for f in os.listdir(self.data_dir) if f.endswith('.csv')]
                if csv_files:
                    file_path = os.path.join(self.data_dir, csv_files[0])
                else:
                    return {'error': f'CSVファイルが見つかりません: {self.data_dir}'}
            elif not os.path.exists(file_path):
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
                return {'error': '全てのエンコーディングで読み込み失敗'}

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

            # 推奨列マッピング
            column_mapping = self.create_flexible_column_mapping(df.columns)

            return {
                'success': True,
                'encoding': used_encoding,
                'total_rows': len(df),
                'columns': list(df.columns),
                'column_analysis': columns_analysis,
                'recommended_mapping': column_mapping,
                'sample_data': df.head(3).to_dict('records')
            }

        except Exception as e:
            return {'error': f'分析エラー: {str(e)}'}

    def get_csv_summary(self):
        """CSV概要情報の取得"""
        file_path = os.path.join(self.data_dir, self.csv_file)

        # 他のCSVファイルも確認
        if not os.path.exists(file_path) and os.path.exists(self.data_dir):
            csv_files = [f for f in os.listdir(self.data_dir) if f.endswith('.csv')]
            if csv_files:
                file_path = os.path.join(self.data_dir, csv_files[0])
            else:
                return {'exists': False, 'error': 'CSVファイルが見つかりません'}
        elif not os.path.exists(file_path):
            return {'exists': False, 'error': 'CSVファイルが見つかりません'}

        try:
            stat = os.stat(file_path)
            return {
                'exists': True,
                'file_size': stat.st_size,
                'modified_time': stat.st_mtime,
                'file_name': os.path.basename(file_path)
            }
        except Exception as e:
            return {'exists': True, 'error': str(e)}