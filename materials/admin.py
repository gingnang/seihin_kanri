from django.contrib import admin
from django.shortcuts import render, redirect
from django.urls import path
from django.contrib import messages
from django.http import HttpResponse
from .models import Material, Product, Recipe
from .csv_loader import MaterialCSVLoader
import io
import csv


@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = ('material_id', 'material_name', 'manufacturer', 'supplier', 'unit_price', 'is_active')
    list_filter = ('is_active', 'material_category', 'manufacturer')
    search_fields = ('material_id', 'material_name', 'manufacturer', 'supplier')
    list_editable = ('is_active',)
    ordering = ('material_id',)

    actions = ['export_csv', 'activate_materials', 'deactivate_materials']

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('import-csv/', self.import_csv, name='materials_material_import_csv'),
            path('analyze-csv/', self.analyze_csv, name='materials_material_analyze_csv'),
        ]
        return custom_urls + urls

    def import_csv(self, request):
        """CSVインポート機能"""
        if request.method == 'POST':
            try:
                csv_loader = MaterialCSVLoader()
                result = csv_loader.load_materials()

                if result['success']:
                    message = f"""
CSV読み込み完了！
• 新規作成: {result['created']}件
• 更新: {result['updated']}件
• スキップ: {result.get('skipped', 0)}件
• 総行数: {result['total_rows']}行
• エンコーディング: {result.get('encoding_used', '不明')}
                    """
                    self.message_user(request, message, level=messages.SUCCESS)
                else:
                    self.message_user(request, f"読み込みエラー: {result['error']}", level=messages.ERROR)

                return redirect('..')

            except Exception as e:
                self.message_user(request, f"システムエラー: {str(e)}", level=messages.ERROR)
                return redirect('..')

        # CSV分析情報を取得
        csv_loader = MaterialCSVLoader()
        analysis = csv_loader.analyze_csv_structure()

        context = {
            'title': 'CSV データ読み込み',
            'analysis': analysis,
            'opts': self.model._meta,
            'has_permission': True,
        }

        return render(request, 'admin/materials/material/import_csv.html', context)

    def analyze_csv(self, request):
        """CSV分析機能"""
        csv_loader = MaterialCSVLoader()
        analysis = csv_loader.analyze_csv_structure()

        if analysis.get('success'):
            response_content = f"""CSV分析結果:

ファイル情報:
- エンコーディング: {analysis['encoding']}
- 総行数: {analysis['total_rows']}
- 列数: {len(analysis['columns'])}

列名一覧:
{chr(10).join(f"- {col}" for col in analysis['columns'])}

推奨マッピング:
{chr(10).join(f"- {k}: {v}" for k, v in analysis.get('recommended_mapping', {}).items())}
"""
        else:
            response_content = f"分析エラー: {analysis.get('error', '不明なエラー')}"

        response = HttpResponse(response_content, content_type='text/plain; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename="csv_analysis.txt"'
        return response

    def export_csv(self, request, queryset):
        """選択された原料をCSVエクスポート"""
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename="materials_export.csv"'
        response.write('\ufeff')  # BOM for Excel

        writer = csv.writer(response)
        writer.writerow([
            '原料ID', '原料名', 'メーカー', '発注先', '適用', '単価', '発注量',
            '備考', '原料区分', '有効', '作成日時', '更新日時'
        ])

        for material in queryset:
            writer.writerow([
                material.material_id,
                material.material_name,
                material.manufacturer,
                material.supplier,
                material.application,
                material.unit_price,
                material.order_quantity,
                material.remarks,
                material.material_category,
                '有効' if material.is_active else '無効',
                material.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                material.updated_at.strftime('%Y-%m-%d %H:%M:%S'),
            ])

        return response

    export_csv.short_description = '選択された原料をCSV出力'

    def activate_materials(self, request, queryset):
        """選択された原料を有効化"""
        count = queryset.update(is_active=True)
        self.message_user(request, f'{count}件の原料を有効化しました。')

    activate_materials.short_description = '選択された原料を有効化'

    def deactivate_materials(self, request, queryset):
        """選択された原料を無効化"""
        count = queryset.update(is_active=False)
        self.message_user(request, f'{count}件の原料を無効化しました。')

    deactivate_materials.short_description = '選択された原料を無効化'


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('product_id', 'product_name', 'factory', 'sales_destination', 'filling_price', 'is_active')
    list_filter = ('is_active', 'factory')
    search_fields = ('product_id', 'product_name', 'factory', 'sales_destination')
    ordering = ('product_id',)


@admin.register(Recipe)
class RecipeAdmin(admin.ModelAdmin):
    list_display = ('product', 'material', 'pattern', 'blend_amount_kg', 'correction_category')
    list_filter = ('pattern', 'correction_category')
    search_fields = ('product__product_name', 'material__material_name')
    ordering = ('product', 'pattern', 'material')