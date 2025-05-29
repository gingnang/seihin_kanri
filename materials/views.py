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

logger = logging.getLogger(__name__)


def material_list(request):
    """原料一覧ページ（修正版）"""

    # データベースの状況を確認
    total_in_db = Material.objects.count()
    active_in_db = Material.objects.filter(is_active=True).count()

    # 検索クエリ
    search_query = request.GET.get('search', '').strip()

    # ソート設定
    sort_key = request.GET.get('sort', 'material_id')
    sort_order = request.GET.get('order', 'asc')

    # 有効なソートキーかチェック
    valid_sort_keys = ['material_id', 'material_name', 'unit_price', 'manufacturer']
    if sort_key not in valid_sort_keys:
        sort_key = 'material_id'

    # ソート順序を適用
    if sort_order == 'desc':
        sort_key = f'-{sort_key}'

    # クエリセット構築
    materials = Material.objects.filter(is_active=True)

    # 検索フィルタ適用
    if search_query:
        materials = materials.filter(
            Q(material_id__icontains=search_query) |
            Q(material_name__icontains=search_query) |
            Q(manufacturer__icontains=search_query) |
            Q(supplier__icontains=search_query)
        )

    # ソート適用
    materials = materials.order_by(sort_key)

    # ページネーション設定
    per_page_choices = [25, 50, 100, 200]
    per_page = int(request.GET.get('per_page', 50))
    if per_page not in per_page_choices:
        per_page = 50

    paginator = Paginator(materials, per_page)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    # シリアル番号計算
    start_index = (page_obj.number - 1) * per_page + 1

    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'sort_key': sort_key.lstrip('-'),  # ソートキーから'-'を除去
        'sort_order': sort_order,
        'per_page': per_page,
        'per_page_choices': per_page_choices,
        'total_in_db': total_in_db,
        'active_in_db': active_in_db,
        'total_count': materials.count(),
        'serial_numbers': [start_index],  # シリアル番号の開始値
    }

    return render(request, 'materials/material_list.html', context)


def material_detail(request, pk):
    """原料詳細ページ"""
    material = get_object_or_404(Material, pk=pk)

    # フィールド情報を整理
    field_data = []
    for field in material._meta.fields:
        if field.name not in ['id']:  # idフィールドを除外
            field_data.append({
                'name': field.name,
                'verbose_name': field.verbose_name,
                'value': getattr(material, field.name)
            })

    context = {
        'material': material,
        'field_data': field_data
    }

    return render(request, 'materials/material_detail.html', context)


def dashboard(request):
    """ダッシュボードページ"""
    total_materials = Material.objects.count()
    active_materials = Material.objects.filter(is_active=True).count()

    # サンプルの生産実績データ（実際のデータに置き換え可能）
    production_records = [
        {'date': '2025-05-29', 'product_name': 'サンプル製品A', 'amount': '100kg', 'staff': '田中'},
        {'date': '2025-05-28', 'product_name': 'サンプル製品B', 'amount': '150kg', 'staff': '佐藤'},
        {'date': '2025-05-27', 'product_name': 'サンプル製品C', 'amount': '200kg', 'staff': '山田'},
    ]

    context = {
        'total_materials': total_materials,
        'active_materials': active_materials,
        'material_count': total_materials,
        'production_count': 42,  # サンプル値
        'inventory_count': 87,  # サンプル値
        'shipment_count': 23,  # サンプル値
        'production_records': production_records,
    }

    return render(request, 'materials/dashboard.html', context)


def analyze_csv_structure(request):
    """CSVファイル構造の分析"""
    try:
        csv_loader = MaterialCSVLoader()
        result = csv_loader.analyze_csv_structure()
        return JsonResponse(result)
    except Exception as e:
        return JsonResponse({'error': str(e)})


def load_csv_data(request):
    """CSVデータの読み込み"""
    if request.method == 'POST':
        try:
            csv_loader = MaterialCSVLoader()
            result = csv_loader.load_materials()

            if result.get('success'):
                # 読み込み後、全データを有効化
                Material.objects.all().update(is_active=True)

                success_msg = f"""
CSV読み込み完了！
• 新規作成: {result.get('created', 0)}件
• 更新: {result.get('updated', 0)}件
• 総処理行数: {result.get('total_rows', 0)}行
• 使用エンコーディング: {result.get('encoding_used', '不明')}
                """.strip()
                messages.success(request, success_msg)
            else:
                messages.error(request, f"読み込みエラー: {result.get('error', '不明なエラー')}")

        except Exception as e:
            logger.error(f"CSV読み込みでシステムエラー: {str(e)}")
            messages.error(request, f"システムエラー: {str(e)}")

    return redirect('materials:material_list')


def load_csv_data(request):
    """CSVデータの読み込み（上書き機能付き）"""
    if request.method == 'POST':
        try:
            # 上書きモードを取得（デフォルトは'update'）
            overwrite_mode = request.POST.get('overwrite_mode', 'update')

            csv_loader = MaterialCSVLoader()
            result = csv_loader.load_materials_with_overwrite(overwrite_mode)

            if result.get('success'):
                # 読み込み後、全データを確実に有効化
                Material.objects.all().update(is_active=True)

                success_msg = f"""
CSV読み込み完了！
• 上書きモード: {result.get('overwrite_mode', 'update')}
• 新規作成: {result.get('created', 0)}件
• 更新: {result.get('updated', 0)}件
• スキップ: {result.get('skipped', 0)}件
• 全データを有効化しました
                """
                messages.success(request, success_msg)

            else:
                messages.error(request, f"読み込みエラー: {result.get('error', '不明')}")

        except Exception as e:
            messages.error(request, f"システムエラー: {str(e)}")

    return redirect('materials:material_list')


def load_csv_with_options(request):
    """CSVデータ読み込みオプション画面"""
    if request.method == 'POST':
        overwrite_mode = request.POST.get('overwrite_mode', 'update')

        try:
            csv_loader = MaterialCSVLoader()
            result = csv_loader.load_materials_with_overwrite(overwrite_mode)

            if result.get('success'):
                Material.objects.all().update(is_active=True)

                success_msg = f"""
CSV読み込み完了！
• 上書きモード: {result.get('overwrite_mode')}
• 新規作成: {result.get('created', 0)}件
• 更新: {result.get('updated', 0)}件
• スキップ: {result.get('skipped', 0)}件
• 処理行数: {result.get('total_rows', 0)}行
• エンコーディング: {result.get('encoding_used', '不明')}
                """
                messages.success(request, success_msg)

                if result.get('errors'):
                    error_msg = f"エラー {len(result['errors'])}件発生: {', '.join(result['errors'][:3])}"
                    messages.warning(request, error_msg)

            else:
                messages.error(request, f"読み込みエラー: {result.get('error')}")

        except Exception as e:
            messages.error(request, f"システムエラー: {str(e)}")

        return redirect('materials:material_list')

    # GET リクエストの場合、オプション画面を表示
    try:
        csv_loader = MaterialCSVLoader()
        csv_analysis = csv_loader.analyze_csv_structure()

        # 現在のデータベース状況
        db_status = {
            'total_count': Material.objects.count(),
            'active_count': Material.objects.filter(is_active=True).count(),
        }

        context = {
            'csv_analysis': csv_analysis,
            'db_status': db_status,
        }

        return render(request, 'materials/csv_load_options.html', context)

    except Exception as e:
        messages.error(request, f"CSV分析エラー: {str(e)}")
        return redirect('materials:material_list')