# -*- coding: utf-8 -*-
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
        # ラベル用備考だけ手動でマッピング
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
        return mapping

    def load_materials(self):
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
                    break
                except Exception:
                    continue
            if df is None:
                return {'success': False, 'error': 'CSVファイルを読み込めません'}

            df = df.fillna('')
            mapping = self.create_column_mapping(df.columns)

            created = 0
            updated = 0
            skipped = 0

            with transaction.atomic():
                for idx, row in df.iterrows():
                    try:
                        material_id = row[mapping['material_id']]
                        values = {}
                        for field, col in mapping.items():
                            values[field] = row[col]
                        material, was_created = Material.objects.get_or_create(
                            material_id=material_id,
                            defaults=values
                        )
                        if was_created:
                            created += 1
                        else:
                            for k, v in values.items():
                                setattr(material, k, v)
                            material.save()
                            updated += 1
                    except Exception as e:
                        print(f"行{idx+1}エラー: {e}")
                        skipped += 1
                        continue

            return {
                'success': True,
                'created': created,
                'updated': updated,
                'skipped': skipped,
                'total_rows': len(df),
                'encoding_used': used_encoding,
                'columns': list(df.columns)
            }

        except Exception as e:
            return {'success': False, 'error': str(e)}
