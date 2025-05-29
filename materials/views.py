# -*- coding: utf-8 -*-
from django.shortcuts import render, get_object_or_404, redirect
from django.core.paginator import Paginator
from django.db.models import Q, Count, Avg, Min, Max
from django.contrib import messages
from django.http import JsonResponse
from django.core.cache import cache
from django.db import connection
from .models import Material
from .csv_loader import MaterialCSVLoader
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


class MaterialViewHelper:
    """原料ビュー用のヘルパークラス"""

    @staticmethod
    def get_safe_field_value(obj, field_name, default=''):
        """安全にフィールド値を取得"""
        try:
            return getattr(obj, field_name, default) or default
        except:
            return default

    @staticmethod
    def build_search_query(search_query):
        """検索クエリを安全に構築"""
        if not search_query:
            return Q()

        keywords = search_query.split()
        query = Q()

        # 検索対象フィールドのマッピング
        search_fields = [
            'material_id__icontains',
            'material_name__icontains',
            'manufacturer__icontains',
            'supplier__icontains',
            'application__icontains',
            'remarks__icontains'
        ]

        for keyword in keywords:
            keyword_query = Q()
            for field in search_fields:
                try:
                    keyword_query |= Q(**{field: keyword})
                except Exception as e:
                    logger.warning(f"検索フィールド {field} でエラー: {e}")
                    continue
            query &= keyword_query

        return query

    @staticmethod
    def get_database_stats():
        """データベース統計情報を取得"""
        try:
            stats = {
                'total_materials': Material.objects.count(),
                'active_materials': Material.objects.filter(is_active=True).count(),
                'inactive_materials': Material.objects.filter(is_active=False).count(),
                'with_manufacturer': Material.objects.exclude(
                    Q(manufacturer__isnull=True) | Q(manufacturer='')
                ).count(),
                'with_supplier': Material.objects.exclude(
                    Q(supplier__isnull=True) | Q(supplier='')
                ).count(),
                'with_price': Material.objects.filter(unit_price__gt=0).count(),
            }

            # 価格統計
            price_stats = Material.objects.filter(unit_price__gt=0).aggregate(
                avg_price=Avg('unit_price'),
                min_price=Min('unit_price'),
                max_price=Max('unit_price')
            )
            stats.update(price_stats)

            return stats
        except Exception as e:
            logger.error(f"統計情報取得エラー: {e}")
            return {
                'total_materials': 0,
                'active_materials': 0,
                'inactive_materials': 0,
                'with_manufacturer': 0,
                'with_supplier': 0,
                'with_price': 0,
                'avg_price': 0,
                'min_price': 0,
                'max_price': 0,
            }


def material_list(request):
    """原料一覧ページ（改良版）"""

    # デバッグモードの判定
    debug_mode = request.GET.get('debug', '0') == '1'

    # 統計情報取得
    stats = MaterialViewHelper.get_database_stats()

    if debug_mode:
        print(f"🔍 DATABASE STATS:")
        for key, value in stats.items():
            print(f"   {key}: {value}")

    # パラメータ取得
    search_query = request.GET.get('search', '').strip()
    category_filter = request.GET.get('category', '')
    manufacturer_filter = request.GET.get('manufacturer', '')
    supplier_filter = request.GET.get('supplier', '')
    price_min = request.GET.get('price_min', '')
    price_max = request.GET.get('price_max', '')
    sort_by = request.GET.get('sort', 'material_id')
    sort_order = request.GET.get('order', 'asc')
    per_page = int(request.GET.get('per_page', 50))
    show_inactive = request.GET.get('show_inactive', '0') == '1'

    # ベースクエリ
    if show_inactive:
        materials = Material.objects.all()
    else:
        materials = Material.objects.filter(is_active=True)

    # 検索フィルタ適用
    if search_query:
        search_q = MaterialViewHelper.build_search_query(search_query)
        materials = materials.filter(search_q)
        if debug_mode:
            print(f"🔍 検索後の件数: {materials.count()}")

    # カテゴリフィルタ
    if category_filter:
        materials = materials.filter(material_category=category_filter)

    # メーカーフィルタ
    if manufacturer_filter:
        materials = materials.filter(manufacturer__icontains=manufacturer_filter)

    # 発注先フィルタ
    if supplier_filter:
        materials = materials.filter(supplier__icontains=supplier_filter)

    # 価格フィルタ
    if price_min:
        try:
            materials = materials.filter(unit_price__gte=Decimal(price_min))
        except (ValueError, TypeError):
            pass

    if price_max:
        try:
            materials = materials.filter(unit_price__lte=Decimal(price_max))
        except (ValueError, TypeError):
            pass

    # ソート
    valid_sort_fields = {
        'material_id': 'material_id',
        'material_name': 'material_name',
        'manufacturer': 'manufacturer',
        'supplier': 'supplier',
        'unit_price': 'unit_price',
        'order_quantity': 'order_quantity',
        'category': 'material_category',
        'updated': 'updated_at'
    }

    if sort_by in valid_sort_fields:
        sort_field = valid_sort_fields[sort_by]
        if sort_order == 'desc':
            sort_field = f'-{sort_field}'
        materials = materials.order_by(sort_field)
    else:
        materials = materials.order_by('material_id')

    # 総件数
    total_count = materials.count()

    if debug_mode:
        print(f"🔍 フィルタ適用後: {total_count}件")

    # ページネーション
    paginator = Paginator(materials, per_page)
    page_number = request.GET.get('page', 1)

    try:
        page_obj = paginator.get_page(page_number)
    except Exception as e:
        logger.error(f"ページネーションエラー: {e}")
        page_obj = paginator.get_page(1)

    # フィルタ用選択肢の取得
    filter_options = get_filter_options()

    # CSV情報
    csv_info = get_csv_info()

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
        'show_inactive': show_inactive,
        'total_count': total_count,
        'stats': stats,
        'filter_options': filter_options,
        'csv_info': csv_info,
        'has_filters': bool(search_query or category_filter or manufacturer_filter
                            or supplier_filter or price_min or price_max),
        'debug_mode': debug_mode,
    }

    if debug_mode:
        context['sql_queries'] = len(connection.queries)
        print(f"🔍 SQL クエリ数: {len(connection.queries)}")

    return render(request, 'materials/material_list.html', context)


def get_filter_options():
    """フィルタ用の選択肢を取得"""
    cache_key = 'material_filter_options'
    options = cache.get(cache_key)

    if options is None:
        try:
            options = {
                'categories': list(
                    Material.objects.exclude(
                        Q(material_category__isnull=True) | Q(material_category='')
                    ).values_list('material_category', flat=True).distinct()
                ),
                'manufacturers': list(
                    Material.objects.exclude(
                        Q(manufacturer__isnull=True) | Q(manufacturer='')
                    ).values_list('manufacturer', flat=True).distinct()
                ),
                'suppliers': list(
                    Material.objects.exclude(
                        Q(supplier__isnull=True) | Q(supplier='')
                    ).values_list('supplier', flat=True).distinct()
                )
            }
            cache.set(cache_key, options, 300)  # 5分キャッシュ
        except Exception as e:
            logger.error(f"フィルタ選択肢取得エラー: {e}")
            options = {'categories': [], 'manufacturers': [], 'suppliers': []}

    return options


def get_csv_info():
    """CSV情報を取得"""
    try:
        csv_loader = MaterialCSVLoader()
        return csv_loader.get_csv_summary()
    except Exception as e:
        logger.error(f"CSV情報取得エラー: {e}")
        return {'exists': False, 'error': str(e)}


def material_detail(request, pk):
    """原料詳細ページ"""
    material = get_object_or_404(Material, pk=pk)

    # 関連統計
    try:
        related_stats = {
            'same_manufacturer_count': Material.objects.filter(
                manufacturer=material.manufacturer
            ).exclude(pk=material.pk).count() if material.manufacturer else 0,
            'same_supplier_count': Material.objects.filter(
                supplier=material.supplier
            ).exclude(pk=material.pk).count() if material.supplier else 0,
            'same_category_count': Material.objects.filter(
                material_category=material.material_category
            ).exclude(pk=material.pk).count() if material.material_category else 0,
        }
    except Exception as e:
        logger.error(f"関連統計取得エラー: {e}")
        related_stats = {
            'same_manufacturer_count': 0,
            'same_supplier_count': 0,
            'same_category_count': 0,
        }

    context = {
        'material': material,
        'related_stats': related_stats,
    }

    return render(request, 'materials/material_detail.html', context)


def dashboard(request):
    """ダッシュボードページ"""
    # 統計情報
    stats = MaterialViewHelper.get_database_stats()

    # CSV情報
    csv_info = get_csv_info()

    # 最近の更新
    try:
        recent_updates = Material.objects.order_by('-updated_at')[:5]
    except Exception as e:
        logger.error(f"最近の更新取得エラー: {e}")
        recent_updates = []

    context = {
        'stats': stats,
        'csv_info': csv_info,
        'recent_updates': recent_updates,
        # 下位互換性のため旧形式も保持
        'total_materials': stats['total_materials'],
        'active_materials': stats['active_materials'],
        'materials_with_manufacturer': stats['with_manufacturer'],
        'materials_with_supplier': stats['with_supplier'],
        'price_stats': {
            'avg_price': stats['avg_price'],
            'min_price': stats['min_price'],
            'max_price': stats['max_price'],
        },
        'csv_summary': csv_info,
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
    """CSVデータの読み込み"""
    if request.method == 'POST':
        try:
            csv_loader = MaterialCSVLoader()
            result = csv_loader.load_materials()

            if result.get('success'):
                # キャッシュクリア
                cache.delete('material_filter_options')

                success_msg = f"""
🎉 CSV読み込み完了！

📊 処理結果:
• 新規作成: {result.get('created', 0)}件
• 更新: {result.get('updated', 0)}件  
• スキップ: {result.get('skipped', 0)}件
• 総行数: {result.get('total_rows', 0)}行
• エンコーディング: {result.get('encoding_used', '不明')}

✅ データベースが正常に更新されました
                """

                messages.success(request, success_msg)
                logger.info(f"CSV読み込み成功: {result}")

            else:
                error_msg = f"❌ CSV読み込みエラー: {result.get('error', '不明なエラー')}"
                messages.error(request, error_msg)
                logger.error(f"CSV読み込み失敗: {result}")

        except Exception as e:
            error_msg = f"❌ システムエラー: {str(e)}"
            messages.error(request, error_msg)
            logger.error(f"CSV読み込み例外: {e}", exc_info=True)

    return redirect('materials:material_list')


def bulk_update_materials(request):
    """一括更新機能（管理者用）"""
    if request.method == 'POST':
        action = request.POST.get('action')
        material_ids = request.POST.getlist('material_ids')

        if not material_ids:
            messages.warning(request, "更新対象の原料を選択してください")
            return redirect('materials:material_list')

        try:
            materials = Material.objects.filter(id__in=material_ids)

            if action == 'activate':
                materials.update(is_active=True)
                messages.success(request, f"{len(material_ids)}件の原料を有効化しました")

            elif action == 'deactivate':
                materials.update(is_active=False)
                messages.success(request, f"{len(material_ids)}件の原料を無効化しました")

            elif action == 'delete':
                count = materials.count()
                materials.delete()
                messages.success(request, f"{count}件の原料を削除しました")

            # キャッシュクリア
            cache.delete('material_filter_options')

        except Exception as e:
            messages.error(request, f"一括更新エラー: {str(e)}")
            logger.error(f"一括更新エラー: {e}", exc_info=True)

    return redirect('materials:material_list')