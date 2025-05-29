# -*- coding: utf-8 -*-
from django.shortcuts import render, get_object_or_404, redirect
from django.core.paginator import Paginator
from django.db.models import Q
from django.contrib import messages
from django.http import JsonResponse
from .models import Material
from .csv_loader import MaterialCSVLoader
import logging


logger = logging.getLogger(__name__)

def material_list(request):
    """原料一覧ページ + ソート＆検索付き + 連番出力"""

    # ソートの指定
    sort_key = request.GET.get('sort', 'material_id')
    sort_order = request.GET.get('order', 'asc')
    if sort_order == 'desc':
        sort_key = '-' + sort_key

    total_in_db = Material.objects.count()
    active_in_db = Material.objects.filter(is_active=True).count()
    inactive_in_db = Material.objects.filter(is_active=False).count()

    show_all = request.GET.get('show_all', '0') == '1'
    if show_all:
        materials = Material.objects.all()
    else:
        materials = Material.objects.filter(is_active=True)

    search_query = request.GET.get('search', '').strip()
    if search_query:
        materials = materials.filter(
            Q(material_id__icontains=search_query) |
            Q(material_name__icontains=search_query) |
            Q(usage_form__icontains=search_query) |
            Q(material_category__icontains=search_query) |
            Q(manufacturer__icontains=search_query) |
            Q(supplier__icontains=search_query) |
            Q(unit_price__icontains=search_query) |
            Q(label_note__icontains=search_query)
        )

    materials = materials.order_by(sort_key, 'material_id')

    per_page = int(request.GET.get('per_page', 50))
    paginator = Paginator(materials, per_page)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    # 連番を算出（ページまたぎでも通し番号で表示）
    first_no = (page_obj.number - 1) * per_page + 1
    serial_numbers = list(range(first_no, first_no + len(page_obj.object_list)))

    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'show_all': show_all,
        'per_page': per_page,
        'total_in_db': total_in_db,
        'active_in_db': active_in_db,
        'inactive_in_db': inactive_in_db,
        'total_count': materials.count(),
        'sort_key': request.GET.get('sort', 'material_id'),
        'sort_order': sort_order,
        'serial_numbers': serial_numbers,
    }
    return render(request, 'materials/material_list.html', context)

def material_detail(request, pk):
    material = get_object_or_404(Material, pk=pk)
    # フィールド名・日本語名・値のセットをリストで作成
    field_data = []
    for field in Material._meta.fields:
        field_data.append({
            "name": field.name,
            "verbose_name": field.verbose_name,
            "value": getattr(material, field.name)
        })
    return render(request, 'materials/material_detail.html', {
        'material': material,
        'field_data': field_data
    })

def dashboard(request):
    """ダッシュボードページ"""
    total_materials = Material.objects.count()
    active_materials = Material.objects.filter(is_active=True).count()
    context = {
        'total_materials': total_materials,
        'active_materials': active_materials,
    }
    return render(request, 'materials/dashboard.html', context)

def analyze_csv_structure(request):
    try:
        csv_loader = MaterialCSVLoader()
        result = csv_loader.analyze_csv_structure()
        return JsonResponse(result)
    except Exception as e:
        return JsonResponse({'error': str(e)})

def load_csv_data(request):
    if request.method == 'POST':
        try:
            csv_loader = MaterialCSVLoader()
            result = csv_loader.load_materials()
            if result.get('success'):
                Material.objects.all().update(is_active=True)
                messages.success(request, f"CSV読み込み完了！新規作成: {result.get('created', 0)}件、更新: {result.get('updated', 0)}件")
            else:
                messages.error(request, f"読み込みエラー: {result.get('error', '不明')}")
        except Exception as e:
            messages.error(request, f"システムエラー: {str(e)}")
    return redirect('materials:material_list')


