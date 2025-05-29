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
    """原料一覧ページ"""
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
            Q(material_name__icontains=search_query)
        )

    materials = materials.order_by('material_id')

    per_page = int(request.GET.get('per_page', 50))
    paginator = Paginator(materials, per_page)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'show_all': show_all,
        'per_page': per_page,
        'total_in_db': total_in_db,
        'active_in_db': active_in_db,
        'inactive_in_db': inactive_in_db,
        'total_count': materials.count(),
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

    context = {
        'total_materials': total_materials,
        'active_materials': active_materials,
    }
    return render(request, 'materials/dashboard.html', context)


def analyze_csv_structure(request):
    """CSVファイル構造の分析（AJAX用）"""
    try:
        csv_loader = MaterialCSVLoader()
        result = csv_loader.analyze_csv_structure()
        return JsonResponse(result)
    except Exception as e:
        return JsonResponse({'error': str(e)})


def load_csv_data(request):
    """CSVデータの読み込み（POST時のみ）"""
    if request.method == 'POST':
        try:
            csv_loader = MaterialCSVLoader()
            result = csv_loader.load_materials()

            if result.get('success'):
                Material.objects.all().update(is_active=True)
                success_msg = f"""
CSV読み込み完了！
• 新規作成: {result.get('created', 0)}件
• 更新: {result.get('updated', 0)}件
• 全データを有効化しました
                """
                messages.success(request, success_msg)
            else:
                messages.error(request, f"読み込みエラー: {result.get('error', '不明')}")
        except Exception as e:
            messages.error(request, f"システムエラー: {str(e)}")
    return redirect('materials:material_list')

