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
                if detected['encoding'] and detected['confidence'] > 0.3:
                    detected_encoding = detected['encoding']
                    if detected_encoding not in encodings_to_try:
                        encodings_to_try.insert(0, detected_encoding)
                    print(f"🔍 chardet検出: {detected_encoding} (信頼度: {detected['confidence']:.2f})")
        except Exception as e:
            print(f"⚠️ chardet検出エラー: {e}")

        return encodings_to_try

    def find_csv_files(self):
        """利用可能なCSVファイルを検索"""
        if not os.path.exists(self.data_dir):
            return []

        # 優先順位付きでCSVファイルを検索
        priority_files = [
            '原料マスタ詳細.csv',
            'materials.csv',
            'material_master.csv',
            'genryou_master.csv'
        ]

        all_csv_files = [f for f in os.listdir(self.data_dir) if f.endswith('.csv')]

        # 優先ファイルから順に確認
        for priority_file in priority_files:
            if priority_file in all_csv_files:
                return [os.path.join(self.data_dir, priority_file)]

        # 優先ファイルがない場合は全CSVファイルを返す
        return [os.path.join(self.data_dir, f) for f in all_csv_files]

    def create_flexible_column_mapping(self, columns):
        """実際の列名に基づいて柔軟な列マッピングを作成"""
        print(f"🔗 検出された列名: {columns}")

        # 列名パターンマッチング辞書（より包括的）
        patterns = {
            'material_id': [
                '原料ID', '原料ＩＤ', '原料id', '原料Id', 'ID', 'id', 'Id', 'iD',
                '原料CD', '原料ＣＤ', '原料cd', '原料Cd', 'CD', 'cd', 'Cd', 'cD',
                '原料コード', '原料番号', '原料No', '品番', '商品コード', '商品番号',
                'material_id', 'MATERIAL_ID', 'Material_ID', 'code', 'CODE'
            ],
            'material_name': [
                '原料名', '原料名称', '原料名前', '名前', '名称', '商品名', '品名',
                '製品名', '材料名', '素材名', 'name', 'Name', 'NAME',
                'material_name', 'MATERIAL_NAME', 'Material_Name',
                'product_name', 'item_name'
            ],
            'manufacturer': [
                '製造所', 'メーカー', 'メーカ', 'メーカー名', '製造者', '製造元',
                '製造会社', '製造業者', '製作者', '製作会社', '会社名',
                'maker', 'Maker', 'MAKER', 'manufacturer', 'Manufacturer',
                'MANUFACTURER', 'company', 'Company', 'COMPANY'
            ],
            'supplier': [
                '販売者', '発注先', '注文先', '供給元', '供給先', '仕入先',
                '取引先', '納入業者', '業者', '卸業者', '商社',
                'supplier', 'Supplier', 'SUPPLIER', 'vendor', 'Vendor'
            ],
            'application': [
                '荷姿', '適用', '用途', '使用用途', '目的', '使用目的',
                '分類', '区分', '種別', 'カテゴリ',
                'application', 'Application', 'APPLICATION',
                'usage', 'Usage', 'purpose', 'Purpose'
            ],
            'unit_price': [
                '単価', '価格', '値段', '金額', '料金', '単位価格',
                '売価', '定価', '標準価格', '仕入価格', '原価', '費用',
                'price', 'Price', 'PRICE', 'unit_price', 'cost', 'Cost'
            ],
            'order_quantity': [
                '正袋重量', '発注量', '注文量', '購入量', '数量', '発注数',
                '仕入量', '入荷量', '量', '個数', '重量', '容量',
                'quantity', 'Quantity', 'QUANTITY', 'qty', 'QTY',
                'order_quantity', 'weight', 'amount'
            ],
            'remarks': [
                '備考', '品質管理備考', '生産本部備考', 'ラベル用備考',
                '注記', 'メモ', '説明', '補足', '詳細', 'コメント',
                'remarks', 'Remarks', 'REMARKS', 'memo', 'Memo',
                'note', 'Note', 'comment', 'description'
            ],
            'material_category': [
                '原料区分', '区分', '分類', 'カテゴリ', '種類', '種別',
                'category', 'Category', 'CATEGORY', 'type', 'Type',
                'material_category', 'class', 'classification'
            ]
        }

        mapping = {}
        used_columns = set()

        # 完全一致を最優先
        for field, pattern_list in patterns.items():
            for col in columns:
                if col not in used_columns:
                    for pattern in pattern_list:
                        if str(col).strip() == pattern:
                            mapping[field] = col
                            used_columns.add(col)
                            print(f"✅ 完全一致: {field} ← '{col}'")
                            break
                    if field in mapping:
                        break

        # 部分一致
        for field, pattern_list in patterns.items():
            if field not in mapping:
                for col in columns:
                    if col not in used_columns:
                        col_clean = str(col).strip().lower()
                        for pattern in pattern_list:
                            pattern_lower = pattern.lower()
                            if pattern_lower in col_clean or col_clean in pattern_lower:
                                mapping[field] = col
                                used_columns.add(col)
                                print(f"✅ 部分一致: {field} ← '{col}'")
                                break
                        if field in mapping:
                            break

        # マッピングできなかったフィールド
        for field in patterns.keys():
            if field not in mapping:
                print(f"⚠️ マッピング失敗: {field}")

        return mapping

    def load_materials(self):
        """超強化版CSV読み込み"""
        try:
            # CSVファイル検索
            csv_files = self.find_csv_files()

            if not csv_files:
                # dataディレクトリ作成提案
                if not os.path.exists(self.data_dir):
                    try:
                        os.makedirs(self.data_dir, exist_ok=True)
                        return {
                            'success': False,
                            'error': f'dataディレクトリを作成しました: {self.data_dir}\nCSVファイルを配置してから再実行してください。'
                        }
                    except Exception as e:
                        return {
                            'success': False,
                            'error': f'dataディレクトリの作成に失敗: {str(e)}'
                        }
                else:
                    return {
                        'success': False,
                        'error': f'CSVファイルが見つかりません。{self.data_dir} にCSVファイルを配置してください。'
                    }

            # 最初のCSVファイルを使用
            file_path = csv_files[0]
            print(f"📖 読み込み対象: {file_path}")

            # エンコーディング検出と読み込み
            encodings = self.detect_encoding_comprehensive(file_path)
            df = None
            used_encoding = None

            for encoding in encodings:
                try:
                    print(f"📖 エンコーディング '{encoding}' で読み込み試行...")

                    # 複数の区切り文字を試行
                    separators = [',', ';', '\t', '|']
                    for sep in separators:
                        try:
                            df = pd.read_csv(file_path, encoding=encoding, dtype=str, sep=sep)
                            if len(df.columns) > 1:  # 複数列がある場合のみ成功とみなす
                                used_encoding = encoding
                                print(f"✅ 読み込み成功: {encoding} (区切り文字: '{sep}')")
                                break
                        except:
                            continue

                    if df is not None and len(df.columns) > 1:
                        break

                except Exception as e:
                    print(f"❌ 読み込み失敗: {encoding} - {str(e)[:100]}")
                    continue

            if df is None or len(df.columns) <= 1:
                return {
                    'success': False,
                    'error': f'CSVファイルを読み込めませんでした。エンコーディング: {encodings}'
                }

            # データクリーニング
            df = df.fillna('')

            # 空の行を削除
            df = df.dropna(how='all')

            # 空白のみの行を削除
            df = df[df.astype(str).apply(lambda x: x.str.strip().str.len().sum(), axis=1) > 0]

            print(f"\n📊 CSV情報:")
            print(f"- エンコーディング: {used_encoding}")
            print(f"- 行数: {len(df)}")
            print(f"- 列数: {len(df.columns)}")
            print(f"- 列名: {list(df.columns)}")

            if len(df) == 0:
                return {
                    'success': False,
                    'error': 'CSVファイルにデータが含まれていません。'
                }

            # 柔軟な列マッピング
            column_mapping = self.create_flexible_column_mapping(df.columns)

            # 必須フィールド（原料ID）の確認
            if 'material_id' not in column_mapping:
                # 最初の列を原料IDとして使用
                column_mapping['material_id'] = df.columns[0]
                print(f"⚠️ 原料ID列が見つからないため、最初の列を使用: {df.columns[0]}")

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

                        # 原料IDが空またはインデックス的な値の場合はスキップ
                        if not material_id or material_id.lower() in ['nan', 'null', 'none',
                                                                      ''] or material_id.isdigit() and int(
                                material_id) == idx:
                            results['skipped'] += 1
                            continue

                        # 各フィールドの値を安全に取得
                        values = {}

                        # 原料名
                        material_name_col = column_mapping.get('material_name')
                        values['material_name'] = self.safe_get_value(row, material_name_col, f"原料_{material_id}")

                        # メーカー
                        manufacturer_col = column_mapping.get('manufacturer')
                        values['manufacturer'] = self.safe_get_value(row, manufacturer_col, '')

                        # 発注先
                        supplier_col = column_mapping.get('supplier')
                        values['supplier'] = self.safe_get_value(row, supplier_col, '')

                        # 適用
                        application_col = column_mapping.get('application')
                        values['application'] = self.safe_get_value(row, application_col, '')

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

                        values['remarks'] = '; '.join(remarks_parts)

                        # 数値フィールドの処理
                        unit_price_col = column_mapping.get('unit_price')
                        values['unit_price'] = self.safe_get_decimal(row, unit_price_col)

                        order_quantity_col = column_mapping.get('order_quantity')
                        if order_quantity_col:
                            order_quantity_str = self.safe_get_value(row, order_quantity_col, '0')
                            values['order_quantity'] = self.extract_numeric_from_string(order_quantity_str)
                        else:
                            values['order_quantity'] = Decimal('0')

                        # 原料区分
                        category_col = column_mapping.get('material_category')
                        values['material_category'] = self.safe_get_value(row, category_col, 'Standard')

                        # デバッグ情報（最初の5行）
                        if idx < 5:
                            debug_info = {
                                'row': idx + 1,
                                'material_id': material_id,
                                'material_name': values['material_name'][:30],
                                'manufacturer': values['manufacturer'][:20],
                                'supplier': values['supplier'][:20],
                                'unit_price': str(values['unit_price']),
                                'order_quantity': str(values['order_quantity']),
                                'category': values['material_category']
                            }
                            results['debug_info'].append(debug_info)

                        # データベース保存
                        material, created = Material.objects.get_or_create(
                            material_id=material_id,
                            defaults={
                                **values,
                                'is_active': True
                            }
                        )

                        if created:
                            results['created'] += 1
                        else:
                            # 既存データの更新
                            for field, value in values.items():
                                setattr(material, field, value)
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
            csv_files = self.find_csv_files()

            if not csv_files:
                return {'error': 'CSVファイルが見つかりません'}

            file_path = csv_files[0]
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
        csv_files = self.find_csv_files()

        if not csv_files:
            return {'exists': False, 'error': 'CSVファイルが見つかりません'}

        file_path = csv_files[0]
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