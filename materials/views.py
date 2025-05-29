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
    """原料一覧ページ（問題解決重視版）"""

    # ⭐ まず、データベースの状況を確認
    total_in_db = Material.objects.count()
    active_in_db = Material.objects.filter(is_active=True).count()
    inactive_in_db = Material.objects.filter(is_active=False).count()

    print(f"🔍 データベース状況確認:")
    print(f"   総件数: {total_in_db}")
    print(f"   有効: {active_in_db}")
    print(f"   無効: {inactive_in_db}")

    # ⭐ 問題特定: is_active=True で絞ると0件になるか？
    if active_in_db == 0 and total_in_db > 0:
        print("🚨 問題発見: 全データがis_active=Falseになっている！")
        # 緊急対応: 全データを有効化
        Material.objects.all().update(is_active=True)
        print("✅ 全データを有効化しました")
        active_in_db = total_in_db

    # ⭐ シンプルなクエリから開始
    show_all = request.GET.get('show_all', '0') == '1'
    if show_all:
        materials = Material.objects.all()
        print("📄 全データを表示")
    else:
        materials = Material.objects.filter(is_active=True)
        print(f"📄 有効データのみ表示: {materials.count()}件")

    # ⭐ 検索は最低限のみ
    search_query = request.GET.get('search', '').strip()
    if search_query:
        materials = materials.filter(
            Q(material_id__icontains=search_query) |
            Q(material_name__icontains=search_query)
        )
        print(f"🔍 検索後: {materials.count()}件")

    # ⭐ ソートも最低限
    materials = materials.order_by('material_id')

    # ⭐ ページネーションも最低限
    per_page = int(request.GET.get('per_page', 50))
    paginator = Paginator(materials, per_page)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    print(f"📄 ページ情報:")
    print(f"   現在ページ: {page_obj.number}")
    print(f"   ページあたり: {per_page}")
    print(f"   現在ページの件数: {len(page_obj.object_list)}")

    # ⭐ データサンプルを表示（デバッグ用）
    if page_obj.object_list:
        first_item = page_obj.object_list[0]
        print(f"📋 1件目のデータ例:")
        print(f"   ID: {first_item.material_id}")
        print(f"   名前: {first_item.material_name}")
        print(f"   有効: {first_item.is_active}")
    else:
        print("❌ ページにデータがありません")

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
    """ダッシュボードページ（シンプル版）"""
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
    """CSVデータの読み込み（シンプル版）"""
    if request.method == 'POST':
        try:
            csv_loader = MaterialCSVLoader()
            result = csv_loader.load_materials()

            if result.get('success'):
                # ⭐ 読み込み後、全データを確実に有効化
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

# debug_data関数は削除（不要）