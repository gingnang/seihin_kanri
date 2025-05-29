# -*- coding: utf-8 -*-
from django.shortcuts import render, get_object_or_404, redirect
from django.core.paginator import Paginator
from django.db.models import Q, Avg  # 🔧 修正: Avgを追加
from django.contrib import messages
from django.http import JsonResponse
from .models import Material
from .csv_loader import MaterialCSVLoader
from decimal import Decimal
import logging
from django.conf import settings

logger = logging.getLogger(__name__)


def top(request):
    return render(request, 'top.html')


def material_list(request):
    """原料一覧ページ（単価表示修正版）"""

    # 🔧 デバッグ情報の収集
    total_in_db = Material.objects.count()
    active_in_db = Material.objects.filter(is_active=True).count()
    inactive_in_db = Material.objects.filter(is_active=False).count()
    with_price = Material.objects.filter(unit_price__gt=0).count()

    logger.info(f"📊 データベース状況:")
    logger.info(f"   総件数: {total_in_db}")
    logger.info(f"   有効: {active_in_db}")
    logger.info(f"   無効: {inactive_in_db}")
    logger.info(f"   単価あり: {with_price}")

    # データが全て無効になっている問題の対応
    if active_in_db == 0 and total_in_db > 0:
        logger.warning("🚨 全データがis_active=Falseになっている！")
        Material.objects.all().update(is_active=True)
        active_in_db = total_in_db
        logger.info("✅ 全データを有効化しました")

    # 表示データの取得
    show_all = request.GET.get('show_all', '0') == '1'
    if show_all:
        materials = Material.objects.all()
        logger.info("📄 全データを表示")
    else:
        materials = Material.objects.filter(is_active=True)
        logger.info(f"📄 有効データのみ表示: {materials.count()}件")

    # 検索処理
    search_query = request.GET.get('search', '').strip()
    if search_query:
        materials = materials.filter(
            Q(material_id__icontains=search_query) |
            Q(material_name__icontains=search_query) |
            Q(manufacturer__icontains=search_query) |
            Q(supplier__icontains=search_query)
        )
        logger.info(f"🔍 検索後: {materials.count()}件")

    # ソート処理
    sort_key = request.GET.get('sort', 'material_id')
    sort_order = request.GET.get('order', 'asc')

    valid_sort_keys = ['material_id', 'material_name', 'unit_price', 'manufacturer', 'supplier']
    if sort_key not in valid_sort_keys:
        sort_key = 'material_id'

    order_prefix = '' if sort_order == 'asc' else '-'
    materials = materials.order_by(f'{order_prefix}{sort_key}')

    # ページネーション
    per_page = int(request.GET.get('per_page', 50))
    if per_page not in [25, 50, 100, 200]:
        per_page = 50

    paginator = Paginator(materials, per_page)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    # 🔧 デバッグ: データサンプルの確認
    if page_obj.object_list:
        first_item = page_obj.object_list[0]
        logger.info(f"📋 1件目のデータ例:")
        logger.info(f"   ID: {first_item.material_id}")
        logger.info(f"   名前: {first_item.material_name}")
        logger.info(f"   有効: {first_item.is_active}")
        logger.info(f"   単価: {first_item.unit_price} (型: {type(first_item.unit_price)})")

        # 🔧 修正: 現在のページの統計を正しく計算
        current_page_materials = list(page_obj.object_list)
        price_stats = {
            'null_count': sum(1 for m in current_page_materials if m.unit_price is None),
            'zero_count': sum(1 for m in current_page_materials if m.unit_price == 0),
            'positive_count': sum(1 for m in current_page_materials if m.unit_price and m.unit_price > 0),
        }
        logger.info(f"   現在ページの単価統計: {price_stats}")

    # 連番計算
    start_index = (page_obj.number - 1) * per_page + 1
    serial_numbers = (start_index, start_index + len(page_obj.object_list) - 1)

    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'show_all': show_all,
        'per_page': per_page,
        'per_page_choices': [25, 50, 100, 200],
        'sort_key': sort_key,
        'sort_order': sort_order,
        'total_in_db': total_in_db,
        'active_in_db': active_in_db,
        'inactive_in_db': inactive_in_db,
        'with_price': with_price,
        'total_count': materials.count(),
        'serial_numbers': serial_numbers,
        'debug': settings.DEBUG,  # デバッグモードの場合のみ詳細情報を表示
    }

    return render(request, 'materials/material_list.html', context)


def material_detail(request, pk):
    """原料詳細ページ（修正版）"""
    material = get_object_or_404(Material, pk=pk)

    # 🔧 フィールド情報を動的に取得
    field_data = []
    for field in material._meta.fields:
        if field.name not in ['id']:  # IDフィールドはスキップ
            value = getattr(material, field.name)
            field_data.append({
                'name': field.name,
                'verbose_name': field.verbose_name,
                'value': value
            })

    context = {
        'material': material,
        'field_data': field_data
    }
    return render(request, 'materials/material_detail.html', context)


def dashboard(request):
    """ダッシュボードページ（修正版）"""
    total_materials = Material.objects.count()
    active_materials = Material.objects.filter(is_active=True).count()
    materials_with_price = Material.objects.filter(unit_price__gt=0).count()

    # 🔧 修正: 平均価格の計算
    avg_price_result = Material.objects.filter(unit_price__gt=0).aggregate(
        avg_price=Avg('unit_price')
    )
    avg_price = avg_price_result['avg_price'] or 0

    context = {
        'total_materials': total_materials,
        'active_materials': active_materials,
        'materials_with_price': materials_with_price,
        'avg_price': avg_price,
        'material_count': total_materials,  # テンプレート互換性のため
        # 🔧 追加: ダッシュボード用の追加統計
        'inactive_materials': total_materials - active_materials,
        'materials_without_price': active_materials - materials_with_price,
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
        return JsonResponse({'success': False, 'error': str(e)})


def load_csv_data(request):
    """CSVデータの読み込み（修正版）"""
    if request.method == 'POST':
        try:
            csv_loader = MaterialCSVLoader()
            result = csv_loader.load_materials()

            if result.get('success'):
                # 🔧 読み込み後の状況確認
                Material.objects.all().update(is_active=True)

                success_msg = f"""
CSV読み込み完了！
• 新規作成: {result.get('created', 0)}件
• 更新: {result.get('updated', 0)}件
• スキップ: {result.get('skipped', 0)}件
• 単価ありデータ: {result.get('with_price', 0)}件
• 使用エンコーディング: {result.get('encoding_used', '不明')}
                """
                messages.success(request, success_msg)

                # 🔧 デバッグログ
                logger.info(f"CSV読み込み完了: {result}")

            else:
                error_msg = f"読み込みエラー: {result.get('error', '不明')}"
                messages.error(request, error_msg)
                logger.error(f"CSV読み込みエラー: {result}")

        except Exception as e:
            error_msg = f"システムエラー: {str(e)}"
            messages.error(request, error_msg)
            logger.error(f"CSV読み込みシステムエラー: {e}")

    return redirect('materials:material_list')


# 🔧 追加: デバッグ用のヘルパー関数
def debug_material_data(request):
    """デバッグ用: 原料データの詳細確認"""
    if not settings.DEBUG:
        return JsonResponse({'error': 'デバッグモードでのみ利用可能'})

    try:
        # データベースの詳細統計
        stats = {
            'total_count': Material.objects.count(),
            'active_count': Material.objects.filter(is_active=True).count(),
            'with_price_count': Material.objects.filter(unit_price__gt=0).count(),
            'zero_price_count': Material.objects.filter(unit_price=0).count(),
            'null_price_count': Material.objects.filter(unit_price__isnull=True).count(),
        }

        # サンプルデータ
        sample_materials = Material.objects.all()[:5]
        sample_data = []
        for material in sample_materials:
            sample_data.append({
                'id': material.material_id,
                'name': material.material_name,
                'price': str(material.unit_price),
                'price_type': str(type(material.unit_price)),
                'is_active': material.is_active,
            })

        result = {
            'success': True,
            'stats': stats,
            'sample_data': sample_data,
        }

        return JsonResponse(result)

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


# 🔧 追加: 単価データの一括修正用関数
def fix_price_data(request):
    """単価データの一括修正（管理者用）"""
    if not request.user.is_superuser:
        messages.error(request, "管理者権限が必要です")
        return redirect('materials:material_list')

    if request.method == 'POST':
        try:
            fixed_count = 0
            materials = Material.objects.all()

            for material in materials:
                # unit_priceが文字列の場合、Decimalに変換
                if isinstance(material.unit_price, str):
                    try:
                        if material.unit_price.strip():
                            # カンマと円マークを除去してDecimalに変換
                            cleaned_price = material.unit_price.replace(',', '').replace('¥', '').strip()
                            if cleaned_price:
                                material.unit_price = Decimal(cleaned_price)
                                material.save()
                                fixed_count += 1
                        else:
                            material.unit_price = None
                            material.save()
                            fixed_count += 1
                    except (ValueError, TypeError):
                        # 変換できない場合はNullにする
                        material.unit_price = None
                        material.save()
                        fixed_count += 1

            messages.success(request, f"{fixed_count}件の単価データを修正しました")
            logger.info(f"単価データ一括修正完了: {fixed_count}件")

        except Exception as e:
            messages.error(request, f"修正中にエラー: {str(e)}")
            logger.error(f"単価データ修正エラー: {e}")

    return redirect('materials:material_list')