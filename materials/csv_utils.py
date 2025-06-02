# -*- coding: utf-8 -*-
import pandas as pd
import os
from django.conf import settings
from .models import Material, Prod
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


class CSVDataLoader:
    """CSV Data Loader Class"""F

    def __init__(self):
        self.data_dir = os.path.join(settings.BASE_DIR, 'data')

    def load_material_master(self):
        """Load Material Master CSV"""
        try:
            file_path = None
            # Check file name variations
            possible_names = [
                'genryou_master.csv',
                'material_master.csv'
            ]

            # Also check actual files in directory
            if os.path.exists(self.data_dir):
                actual_files = os.listdir(self.data_dir)
                for file in actual_files:
                    if 'master' in file.lower() or 'genryou' in file:
                        possible_names.append(file)

            for name in possible_names:
                test_path = os.path.join(self.data_dir, name)
                if os.path.exists(test_path):
                    file_path = test_path
                    break

            if not file_path:
                raise FileNotFoundError("Material master file not found")

            # Try different encodings
            encodings = ['cp932', 'shift_jis', 'utf-8', 'utf-8-sig']
            df = None

            for encoding in encodings:
                try:
                    df = pd.read_csv(file_path, encoding=encoding, dtype=str)
                    logger.info(f"Successfully loaded with encoding: {encoding}")
                    break
                except UnicodeDecodeError:
                    continue

            if df is None:
                raise ValueError("Cannot read CSV file with any encoding")

            # Data cleaning
            df = df.fillna('')
            available_columns = df.columns.tolist()
            logger.info(f"Available columns: {available_columns}")

            materials_created = 0
            materials_updated = 0

            for _, row in df.iterrows():
                # Get material ID
                material_id = None
                for col in available_columns:
                    if any(keyword in col for keyword in ['ID', 'id', 'CD', 'cd']):
                        if pd.notna(row[col]) and str(row[col]).strip():
                            material_id = str(row[col]).strip()
                            break

                if not material_id:
                    continue

                # Get material name
                material_name = ''
                for col in available_columns:
                    if any(keyword in col for keyword in ['name', 'Name']):
                        if pd.notna(row[col]):
                            material_name = str(row[col]).strip()
                            break

                # Get unit price
                unit_price = Decimal('0')
                for col in available_columns:
                    if any(keyword in col for keyword in ['price', 'Price']):
                        if pd.notna(row[col]):
                            try:
                                price_str = str(row[col]).replace(',', '').replace('¥', '')
                                unit_price = Decimal(price_str) if price_str else Decimal('0')
                                break
                            except:
                                pass

                # Save to database
                material, created = Material.objects.get_or_create(
                    material_id=material_id,
                    defaults={
                        'material_name': material_name,
                        'unit_price': unit_price,
                        'material_category': 'Standard',
                    }
                )

                if created:
                    materials_created += 1
                else:
                    material.material_name = material_name
                    material.unit_price = unit_price
                    material.save()
                    materials_updated += 1

            return {
                'success': True,
                'created': materials_created,
                'updated': materials_updated,
                'total_rows': len(df),
                'columns': available_columns
            }

        except Exception as e:
            logger.error(f"Material master loading error: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def get_csv_info(self):
        """Get CSV file information"""
        csv_info = {}

        if not os.path.exists(self.data_dir):
            return {'error': 'Data directory not found'}

        files = os.listdir(self.data_dir)
        csv_files = [f for f in files if f.endswith('.csv')]

        for filename in csv_files:
            file_path = os.path.join(self.data_dir, filename)
            try:
                stat = os.stat(file_path)
                csv_info[filename] = {
                    'exists': True,
                    'size': stat.st_size,
                    'modified': stat.st_mtime,
                    'filename': filename
                }
            except:
                csv_info[filename] = {
                    'exists': False,
                    'error': 'File info error'
                }

        return csv_info