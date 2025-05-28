# -*- coding: utf-8 -*-
import pandas as pd
import os
from django.conf import settings
from .models import Material
from decimal import Decimal
import logging
from django.db import transaction

logger = logging.getLogger(__name__)


class MaterialCSVLoader:
    def __init__(self):
        self.data_dir = os.path.join(settings.BASE_DIR, 'data')
        self.csv_file = '原料マスタ詳細.csv'

    def load_materials(self):
        try:
            file_path = os.path.join(self.data_dir, self.csv_file)

            if not os.path.exists(file_path):
                raise FileNotFoundError(f"File not found: {file_path}")

            # Try different encodings
            encodings = ['cp932', 'shift_jis', 'utf-8', 'utf-8-sig']
            df = None

            for encoding in encodings:
                try:
                    df = pd.read_csv(file_path, encoding=encoding, dtype=str)
                    break
                except UnicodeDecodeError:
                    continue

            if df is None:
                raise ValueError("Cannot read CSV file")

            df = df.fillna('')
            results = {
                'success': True,
                'created': 0,
                'updated': 0,
                'total_rows': len(df),
                'columns': list(df.columns)
            }

            # Find material ID column
            material_id_col = None
            for col in df.columns:
                if any(keyword in col for keyword in ['ID', 'id', 'CD', 'cd']):
                    material_id_col = col
                    break

            # Find material name column
            material_name_col = None
            for col in df.columns:
                if any(keyword in col for keyword in ['名', 'name', 'Name']):
                    material_name_col = col
                    break

            # Find price column
            price_col = None
            for col in df.columns:
                if any(keyword in col for keyword in ['価格', '単価', 'price', 'Price']):
                    price_col = col
                    break

            if not material_id_col:
                raise ValueError("Material ID column not found")

            with transaction.atomic():
                for _, row in df.iterrows():
                    material_id = str(row[material_id_col]).strip()
                    if not material_id or material_id == 'nan':
                        continue

                    material_name = str(
                        row[material_name_col]).strip() if material_name_col else f"Material_{material_id}"
                    if material_name == 'nan':
                        material_name = f"Material_{material_id}"

                    unit_price = Decimal('0')
                    if price_col and str(row[price_col]).strip() and str(row[price_col]) != 'nan':
                        try:
                            price_str = str(row[price_col]).replace(',', '').replace('¥', '')
                            unit_price = Decimal(price_str)
                        except:
                            pass

                    material, created = Material.objects.get_or_create(
                        material_id=material_id,
                        defaults={
                            'material_name': material_name,
                            'unit_price': unit_price,
                            'material_category': 'Standard',
                        }
                    )

                    if created:
                        results['created'] += 1
                    else:
                        material.material_name = material_name
                        material.unit_price = unit_price
                        material.save()
                        results['updated'] += 1

            return results

        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    def get_csv_summary(self):
        file_path = os.path.join(self.data_dir, self.csv_file)

        if not os.path.exists(file_path):
            return {'exists': False, 'error': 'File not found'}

        try:
            stat = os.stat(file_path)
            return {
                'exists': True,
                'file_size': stat.st_size,
                'modified_time': stat.st_mtime
            }
        except Exception as e:
            return {'exists': True, 'error': str(e)}