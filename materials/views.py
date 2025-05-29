# -*- coding: utf-8 -*-
from django.shortcuts import render, get_object_or_404, redirect
from django.core.paginator import Paginator
from django.db.models import Q
from django.contrib import messages
from django.http import JsonResponse
from .models import Material
from .csv_loader import MaterialCSVLoader
from decimal import Decimal
import logging
import traceback
import os
from django.conf import settings

logger = logging.getLogger(__name__)


def material_list(request):
    """原料一覧ページ（検索・フィルタ機能付き）"""

    # 検索・フィルタパラメータ取得
    search_query = request.GET.get('search', '').strip()
    category_filter = request.GET.get('category', '')
    manufacturer_filter = request.GET.get('manufacturer', '')
    supplier_filter = request.GET.get('supplier', '')
    price_min = request.GET.get('price_min', '')
    price_max = request.GET.get('price_max', '')
    sort_by = request.GET.get('sort', 'material_id')
    sort_order = request.GET.get('order', 'asc')
    per_page = int(request.GET.get('per_page', 100))

    # 基本クエリ（全データを表示）
    materials = Material.objects.all()

    # 検索フィルタ適用
    if search_query:
        keywords = search_query.split()
        query = Q()

        for keyword in keywords:
            keyword_query = (
                    Q(material_id__icontains=keyword) |
                    Q(material_name__icontains=keyword) |
                    Q(manufacturer__icontains=keyword) |
                    Q(supplier__icontains=keyword) |
                    Q(application__icontains=keyword) |
                    Q(remarks__icontains=keyword)
            )
            query &= keyword_query

        materials = materials.filter(query)

    # フィルタ適用
    if category_filter:
        materials = materials.filter(material_category=category_filter)
    if manufacturer_filter:
        materials = materials.filter(manufacturer__icontains=manufacturer_filter)
    if supplier_filter:
        materials = materials.filter(supplier__icontains=supplier_filter)

    # 価格フィルタ適用
    if price_min:
        try:
            min_price = Decimal(price_min)
            materials = materials.filter(unit_price__gte=min_price)
        except:
            pass
    if price_max:
        try:
            max_price = Decimal(price_max)
            materials = materials.filter(unit_price__lte=max_price)
        except:
            pass

    # ソート適用
    valid_sort_fields = ['material_id', 'material_name', 'manufacturer', 'supplier',
                         'unit_price', 'order_quantity', 'material_category', 'updated_at']
    if sort_by in valid_sort_fields:
        if sort_order == 'desc':
            sort_field = f'-{sort_by}'
        else:
            sort_field = sort_by
        materials = materials.order_by(sort_field)
    else:
        materials = materials.order_by('material_id')

    # 統計情報取得
    total_count = materials.count()

    # カテゴリ統計
    categories_with_count = []
    all_categories = Material.objects.values_list('material_category', flat=True).distinct()
    for category in all_categories:
        if category:
            count = Material.objects.filter(material_category=category).count()
            categories_with_count.append({
                'name': category,
                'count': count,
                'selected': category == category_filter
            })

    # メーカー・発注先統計
    manufacturers = Material.objects.filter(manufacturer__isnull=False) \
        .exclude(manufacturer='') \
        .values_list('manufacturer', flat=True).distinct()
    suppliers = Material.objects.filter(supplier__isnull=False) \
        .exclude(supplier='') \
        .values_list('supplier', flat=True).distinct()

    # ページネーション
    paginator = Paginator(materials, per_page)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # CSV情報取得
    csv_loader = MaterialCSVLoader()
    csv_summary = csv_loader.get_csv_summary()

    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'category_filter': category_filter,
        'manufacturer_filter': manufacturer_filter,
        'supplier_filter': supplier_filter,
        'price_min': price_min,
        'price_max': price_max,
        'sort_by': sort_by,
        'sort_order': sort_order,
        'per_page': per_page,
        'categories_with_count': categories_with_count,
        'manufacturers': sorted(manufacturers),
        'suppliers': sorted(suppliers),
        'total_count': total_count,
        'csv_summary': csv_summary,
        'materials_in_db': Material.objects.count(),
        'has_filters': bool(search_query or category_filter or manufacturer_filter
                            or supplier_filter or price_min or price_max),
    }

    return render(request, 'materials/material_list.html', context)


def material_detail(request, pk):
    """原料詳細ページ"""
    material = get_object_or_404(Material, pk=pk)
    return render(request, 'materials/material_detail.html', {'material': material})


def dashboard(request):
    """ダッシュボードページ"""
    total_materials = Material.objects.count()
    active_materials = Material.objects.filter(is_active=True).count()

    # 統計情報の追加
    materials_with_manufacturer = Material.objects.filter(
        manufacturer__isnull=False
    ).exclude(manufacturer='').count()

    materials_with_supplier = Material.objects.filter(
        supplier__isnull=False
    ).exclude(supplier='').count()

    # 価格統計
    try:
        from django.db.models import Avg, Min, Max
        price_stats = Material.objects.filter(unit_price__gt=0).aggregate(
            avg_price=Avg('unit_price'),
            min_price=Min('unit_price'),
            max_price=Max('unit_price')
        )
    except:
        price_stats = {'avg_price': 0, 'min_price': 0, 'max_price': 0}

    csv_loader = MaterialCSVLoader()
    csv_summary = csv_loader.get_csv_summary()

    context = {
        'total_materials': total_materials,
        'active_materials': active_materials,
        'materials_with_manufacturer': materials_with_manufacturer,
        'materials_with_supplier': materials_with_supplier,
        'price_stats': price_stats,
        'csv_summary': csv_summary,
    }

    return render(request, 'materials/dashboard.html', context)


def analyze_csv_structure(request):
    """CSVファイル構造の分析（AJAX用）"""
    try:
        csv_loader = MaterialCSVLoader()
        result = csv_loader.analyze_csv_structure()
        return JsonResponse(result)
    except Exception as e:
        logger.error(f"CSV分析エラー: {e}")
        return JsonResponse({
            'success': False,
            'error': f'CSV分析中にエラーが発生しました: {str(e)}'
        })


def load_csv_data(request):
    """CSVデータの読み込み（強化版）"""
    if request.method == 'POST':
        try:
            # 事前診断
            data_dir = os.path.join(settings.BASE_DIR, 'data')

            print(f"🔍 CSV読み込み開始")
            print(f"📁 データディレクトリ: {data_dir}")
            print(f"📁 ディレクトリ存在: {os.path.exists(data_dir)}")

            # データディレクトリ確認
            if not os.path.exists(data_dir):
                error_msg = f"""
❌ データディレクトリが見つかりません

📍 問題: {data_dir} が存在しません

🔧 解決方法:
1. プロジェクトのルートディレクトリで以下を実行:
   mkdir data

2. CSVファイルを data ディレクトリに配置:
   - 原料マスタ詳細.csv
   - または任意の原料データCSV

3. ファイル配置例:
   your_project/
   ├── data/
   │   └── 原料マスタ詳細.csv
   ├── materials/
   └── manage.py
                """
                messages.error(request, error_msg)
                return redirect('materials:material_list')

            # CSVファイル確認
            csv_files = [f for f in os.listdir(data_dir) if f.endswith('.csv')]
            print(f"📄 見つかったCSVファイル: {csv_files}")

            if not csv_files:
                error_msg = f"""
❌ CSVファイルが見つかりません

📍 問題: data ディレクトリにCSVファイルがありません

🔧 解決方法:
1. CSVファイルを data ディレクトリに配置:
   - 推奨ファイル名: 原料マスタ詳細.csv
   - または任意の原料データCSV

2. CSVファイルの形式:
   - 1行目: 列名（原料ID, 原料名, メーカー, 発注先など）
   - 2行目以降: データ
   - エンコーディング: UTF-8 または Shift_JIS

3. サンプルCSV内容:
   原料ID,原料名,メーカー,発注先,単価
   001,小麦粉,日本製粉,商事会社,120
   002,砂糖,三井製糖,甘味料商事,180
                """
                messages.error(request, error_msg)
                return redirect('materials:material_list')

            # CSV読み込み実行
            csv_loader = MaterialCSVLoader()
            result = csv_loader.load_materials()

            if result['success']:
                # 読み込み成功 - 全データを有効化
                Material.objects.all().update(is_active=True)

                success_message = f"""
🎉 CSV読み込み完了！

📊 処理結果:
• 新規作成: {result['created']}件
• 更新: {result['updated']}件
• スキップ: {result.get('skipped', 0)}件  
• 総行数: {result['total_rows']}行
• エンコーディング: {result.get('encoding_used', '不明')}

📋 処理された列: {len(result['columns'])}列
• {', '.join(result['columns'])}

🔧 フィールドマッピング:
• {result.get('column_mapping', {})}

✅ 全ての原料データを有効化しました
                """

                # デバッグ情報を追加
                if result.get('debug_info'):
                    success_message += f"\n\n📄 処理例（最初の{len(result['debug_info'])}行）:"
                    for debug in result['debug_info']:
                        success_message += f"\n• 行{debug['row']}: {debug['material_id']} - {debug.get('material_name', '')[:30]}"

                messages.success(request, success_message)

                # 読み込み後の確認
                total_after = Material.objects.count()
                active_after = Material.objects.filter(is_active=True).count()
                print(f"✅ 読み込み完了: 総数={total_after}, 有効={active_after}")

            else:
                error_message = f"""
❌ CSV読み込みエラー

📍 エラー内容: {result['error']}

🔧 一般的な解決方法:
1. CSVファイルの形式確認:
   - 文字コード: UTF-8 または Shift_JIS
   - 区切り文字: カンマ(,)
   - 1行目に列名が必要

2. ファイル権限確認:
   - ファイルが読み取り可能か確認

3. CSVファイル内容確認:
   - 空ファイルでないか
   - 文字化けしていないか
   - 必要な列（原料ID、原料名など）があるか

4. 手動確認方法:
   python manage.py shell
   から診断スクリプトを実行
                """
                messages.error(request, error_message)
                logger.error(f"CSV読み込み失敗: {result['error']}")

        except Exception as e:
            error_message = f"""
❌ システムエラーが発生しました

📍 エラー詳細: {str(e)}

🔧 解決方法:
1. サーバーを再起動:
   python manage.py runserver

2. Python環境確認:
   - 必要なライブラリがインストールされているか
   - pip install pandas chardet

3. 診断実行:
   python manage.py shell で診断スクリプトを実行

4. エラー詳細:
   {traceback.format_exc()}
            """
            messages.error(request, error_message)
            logger.error(f"CSV読み込みシステムエラー: {e}")
            logger.error(traceback.format_exc())

    else:
        # GET リクエストの場合は一覧ページにリダイレクト
        messages.info(request, "CSV読み込みはPOSTリクエストで実行してください。")

    return redirect('materials:material_list')