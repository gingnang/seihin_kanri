# -*- coding: utf-8 -*-
from django.shortcuts import render, get_object_or_404, redirect
from django.core.paginator import Paginator
from django.db.models import Q, Min, Max
from django.contrib import messages
from .models import Material
from .csv_loader import MaterialCSVLoader
from decimal import Decimal


def material_list(request):
    """原料一覧ページ（検索・フィルタ機能付き）"""

    # 検索・フィルタパラメータ取得
    search_query = request.GET.get('search', '').strip()
    category_filter = request.GET.get('category', '')
    price_min = request.GET.get('price_min', '')
    price_max = request.GET.get('price_max', '')
    sort_by = request.GET.get('sort', 'material_id')
    sort_order = request.GET.get('order', 'asc')
    per_page = int(request.GET.get('per_page', 50))

    # 基本クエリ
    materials = Material.objects.filter(is_active=True)


    # 検索フィルタ適用
    if search_query:
        # 複数キーワード対応
        keywords = search_query.split()
        query = Q()

        for keyword in keywords:
            keyword_query = (
                    Q(material_id__icontains=keyword) |
                    Q(material_name__icontains=keyword) |
                    Q(supplier__icontains=keyword)
            )
            query &= keyword_query

        materials = materials.filter(query)

    # カテゴリフィルタ適用
    if category_filter:
        materials = materials.filter(material_category=category_filter)

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
    valid_sort_fields = ['material_id', 'material_name', 'unit_price', 'material_category', 'updated_at']
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
    all_categories = Material.objects.filter(is_active=True).values_list('material_category', flat=True).distinct()
    for category in all_categories:
        if category:
            count = Material.objects.filter(is_active=True, material_category=category).count()
            categories_with_count.append({
                'name': category,
                'count': count,
                'selected': category == category_filter
            })

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
        'price_min': price_min,
        'price_max': price_max,
        'sort_by': sort_by,
        'sort_order': sort_order,
        'per_page': per_page,
        'categories_with_count': categories_with_count,
        'total_count': total_count,
        'csv_summary': csv_summary,
        'materials_in_db': Material.objects.count(),
        'has_filters': bool(search_query or category_filter or price_min or price_max),
    }

    return render(request, 'materials/material_list.html', context)


def load_csv_data(request):
    if request.method == 'POST':
        try:
            csv_loader = MaterialCSVLoader()
            result = csv_loader.load_materials()

            if result['success']:
                messages.success(
                    request,
                    f"Data loaded: {result['created']} created, {result['updated']} updated"
                )
            else:
                messages.error(request, f"Load error: {result['error']}")

        except Exception as e:
            messages.error(request, f"System error: {str(e)}")

    return redirect('materials:material_list')


def dashboard(request):
    total_materials = Material.objects.count()
    active_materials = Material.objects.filter(is_active=True).count()

    csv_loader = MaterialCSVLoader()
    csv_summary = csv_loader.get_csv_summary()

    context = {
        'total_materials': total_materials,
        'active_materials': active_materials,
        'csv_summary': csv_summary,
    }

    return render(request, 'materials/dashboard.html', context)