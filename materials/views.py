# -*- coding: utf-8 -*-
from django.shortcuts import render, get_object_or_404, redirect
from django.core.paginator import Paginator
from django.db.models import Q, Avg
from django.contrib import messages
from django.http import JsonResponse
from .models import Material
from .csv_loader import MaterialCSVLoader
from decimal import Decimal, InvalidOperation
import logging
from django.conf import settings

logger = logging.getLogger(__name__)
# 以下のコードは変更なし...

def safe_price_comparison(price_value, comparison_value=0):
    """
    🔧 安全な価格比較関数
    文字列、Decimal、数値を適切に処理して比較
    """
    if price_value is None or price_value == '':
        return False

    try:
        # 文字列の場合はDecimalに変換
        if isinstance(price_value, str):
            cleaned_price = price_value.replace(',', '').replace('¥', '').strip()
            if not cleaned_price:
                return False
            price_decimal = Decimal(cleaned_price)
        elif isinstance(price_value, (int, float)):
            price_decimal = Decimal(str(price_value))
        elif isinstance(price_value, Decimal):
            price_decimal = price_value
        else:
            return False

        return price_decimal > comparison_value

    except (ValueError, InvalidOperation, TypeError):
        return False


def safe_price_equals(price_value, comparison_value=0):
    """
    🔧 安全な価格等価比較関数
    """
    if price_value is None:
        return comparison_value == 0

    try:
        if isinstance(price_value, str):
            cleaned_price = price_value.replace(',', '').replace('¥', '').strip()
            if not cleaned_price:
                return comparison_value == 0
            price_decimal = Decimal(cleaned_price)
        elif isinstance(price_value, (int, float)):
            price_decimal = Decimal(str(price_value))
        elif isinstance(price_value, Decimal):
            price_decimal = price_value
        else:
            return False

        return price_decimal == comparison_value

    except (ValueError, InvalidOperation, TypeError):
        return False


def top(request):
    return render(request, 'top.html')


def material_list(request):
    """原料一覧ページ（型エラー修正版）"""

    # 🔧 デバッグ情報の収集
    total_in_db = Material.objects.count()
    active_in_db = Material.objects.filter(is_active=True).count()
    inactive_in_db = Material.objects.filter(is_active=False).count()

    # 🔧 修正: 安全な単価フィルタリング
    try:
        # データベースレベルでの単価チェック（型安全）
        with_price = 0
        for material in Material.objects.all():
            if safe_price_comparison(material.unit_price, 0):
                with_price += 1
    except Exception as e:
        logger.error(f"単価統計計算エラー: {e}")
        with_price = 0

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

    # 🔧 修正: 単価ソートの場合は特別処理
    if sort_key == 'unit_price':
        # 単価を安全にソートするため、Pythonレベルでソート
        materials_list = list(materials)
        try:
            def sort_by_price(material):
                try:
                    if safe_price_comparison(material.unit_price, -1):  # 値があるかチェック
                        if isinstance(material.unit_price, str):
                            cleaned = material.unit_price.replace(',', '').replace('¥', '').strip()
                            return Decimal(cleaned) if cleaned else Decimal('0')
                        elif isinstance(material.unit_price, Decimal):
                            return material.unit_price
                        else:
                            return Decimal(str(material.unit_price))
                    else:
                        return Decimal('0')
                except:
                    return Decimal('0')

            materials_list.sort(key=sort_by_price, reverse=(sort_order == 'desc'))
            # ソート済みリストからQuerySetを再構築
            sorted_ids = [m.id for m in materials_list]
            materials = Material.objects.filter(id__in=sorted_ids)
            # IDの順序を保持
            materials = sorted(materials, key=lambda x: sorted_ids.index(x.id))
        except Exception as e:
            logger.error(f"単価ソートエラー: {e}")
            # フォールバック: IDでソート
            materials = materials.order_by('material_id')
    else:
        # 通常のソート
        order_prefix = '' if sort_order == 'asc' else '-'
        materials = materials.order_by(f'{order_prefix}{sort_key}')

    # ページネーション
    per_page = int(request.GET.get('per_page', 50))
    if per_page not in [25, 50, 100, 200]:
        per_page = 50

    # 🔧 修正: ソート済みリストの場合はそのまま使用
    if isinstance(materials, list):
        paginator = Paginator(materials, per_page)
    else:
        paginator = Paginator(materials, per_page)

    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    # 🔧 修正: データサンプルの安全な確認
    if page_obj.object_list:
        try:
            first_item = page_obj.object_list[0]
            logger.info(f"📋 1件目のデータ例:")
            logger.info(f"   ID: {first_item.material_id}")
            logger.info(f"   名前: {first_item.material_name}")
            logger.info(f"   有効: {first_item.is_active}")
            logger.info(f"   単価: {first_item.unit_price} (型: {type(first_item.unit_price)})")

            # 🔧 修正: 安全な単価統計計算
            current_page_materials = list(page_obj.object_list)
            price_stats = {
                'null_count': sum(1 for m in current_page_materials if m.unit_price is None),
                'zero_count': sum(1 for m in current_page_materials if safe_price_equals(m.unit_price, 0)),
                'positive_count': sum(1 for m in current_page_materials if safe_price_comparison(m.unit_price, 0)),
            }
            logger.info(f"   現在ページの単価統計: {price_stats}")

        except Exception as e:
            logger.error(f"データサンプル確認エラー: {e}")

    # 連番計算
    start_index = (page_obj.number - 1) * per_page + 1
    serial_numbers = (start_index, start_index + len(page_obj.object_list) - 1)

    # 🔧 修正: 総件数の安全な計算
    try:
        if isinstance(materials, list):
            total_count = len(materials)
        else:
            total_count = materials.count()
    except:
        total_count = 0

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
        'total_count': total_count,
        'serial_numbers': serial_numbers,
        'debug': settings.DEBUG,
    }

    return render(request, 'materials/material_list.html', context)


def material_detail(request, pk):
    """原料詳細ページ（修正版）"""
    material = get_object_or_404(Material, pk=pk)

    # 🔧 フィールド情報を動的に取得
    field_data = []
    for field in material._meta.fields:
        if field.name not in ['id']:
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

    # 🔧 修正: 安全な単価統計計算
    materials_with_price = 0
    total_price = Decimal('0')
    price_count = 0

    try:
        for material in Material.objects.all():
            if safe_price_comparison(material.unit_price, 0):
                materials_with_price += 1
                try:
                    if isinstance(material.unit_price, str):
                        cleaned = material.unit_price.replace(',', '').replace('¥', '').strip()
                        if cleaned:
                            price_decimal = Decimal(cleaned)
                            total_price += price_decimal
                            price_count += 1
                    elif isinstance(material.unit_price, Decimal):
                        total_price += material.unit_price
                        price_count += 1
                except:
                    pass
    except Exception as e:
        logger.error(f"ダッシュボード統計計算エラー: {e}")

    avg_price = total_price / price_count if price_count > 0 else 0

    context = {
        'total_materials': total_materials,
        'active_materials': active_materials,
        'materials_with_price': materials_with_price,
        'avg_price': avg_price,
        'material_count': total_materials,
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


def debug_material_data(request):
    """デバッグ用: 原料データの詳細確認"""
    if not settings.DEBUG:
        return JsonResponse({'error': 'デバッグモードでのみ利用可能'})

    try:
        # 🔧 修正: 安全なデータ統計
        materials = Material.objects.all()
        total_count = materials.count()
        active_count = materials.filter(is_active=True).count()

        with_price_count = 0
        zero_price_count = 0
        null_price_count = 0

        for material in materials:
            if material.unit_price is None:
                null_price_count += 1
            elif safe_price_equals(material.unit_price, 0):
                zero_price_count += 1
            elif safe_price_comparison(material.unit_price, 0):
                with_price_count += 1

        stats = {
            'total_count': total_count,
            'active_count': active_count,
            'with_price_count': with_price_count,
            'zero_price_count': zero_price_count,
            'null_price_count': null_price_count,
        }

        # サンプルデータ
        sample_materials = materials[:5]
        sample_data = []
        for material in sample_materials:
            sample_data.append({
                'id': material.material_id,
                'name': material.material_name,
                'price': str(material.unit_price),
                'price_type': str(type(material.unit_price)),
                'is_active': material.is_active,
                'safe_price_check': safe_price_comparison(material.unit_price, 0),
            })

        result = {
            'success': True,
            'stats': stats,
            'sample_data': sample_data,
        }

        return JsonResponse(result)

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


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
                original_price = material.unit_price
                fixed = False

                # 文字列の単価をDecimalに変換
                if isinstance(material.unit_price, str):
                    try:
                        if material.unit_price.strip():
                            cleaned_price = material.unit_price.replace(',', '').replace('¥', '').strip()
                            if cleaned_price:
                                material.unit_price = Decimal(cleaned_price)
                                fixed = True
                        else:
                            material.unit_price = None
                            fixed = True
                    except (ValueError, TypeError, InvalidOperation):
                        material.unit_price = None
                        fixed = True

                if fixed:
                    material.save()
                    fixed_count += 1
                    logger.info(f"修正: {material.material_id} {original_price} → {material.unit_price}")

            messages.success(request, f"{fixed_count}件の単価データを修正しました")
            logger.info(f"単価データ一括修正完了: {fixed_count}件")

        except Exception as e:
            messages.error(request, f"修正中にエラー: {str(e)}")
            logger.error(f"単価データ修正エラー: {e}")

    return redirect('materials:material_list')


def load_csv_with_options(request):
    """CSV読み込みオプション画面"""
    if request.method == 'POST':
        try:
            overwrite_mode = request.POST.get('overwrite_mode', 'update')
            csv_loader = MaterialCSVLoader()
            result = csv_loader.load_materials_with_overwrite(overwrite_mode)

            if result.get('success'):
                Material.objects.all().update(is_active=True)

                success_msg = f"""
CSV読み込み完了！
• 新規作成: {result.get('created', 0)}件
• 更新: {result.get('updated', 0)}件
• スキップ: {result.get('skipped', 0)}件
• 上書きモード: {result.get('overwrite_mode', '不明')}
• 使用エンコーディング: {result.get('encoding_used', '不明')}
                """
                messages.success(request, success_msg)
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

    # GET リクエストの場合: オプション選択画面を表示
    try:
        csv_loader = MaterialCSVLoader()
        csv_analysis = csv_loader.analyze_csv_structure()

        # データベースの現在の状況を取得
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


def upload_csv_import(request):
    """38フィールド完全対応CSVアップロード機能"""

    if request.method == 'POST':
        action = request.POST.get('action', 'preview')

        if action == 'preview':
            # プレビュー段階
            if 'csv_file' not in request.FILES:
                messages.error(request, 'CSVファイルが選択されていません。')
                return redirect('materials:upload_csv_import')

            uploaded_file = request.FILES['csv_file']

            try:
                import tempfile
                import os
                import pandas as pd

                # 一時ファイルに保存
                with tempfile.NamedTemporaryFile(delete=False, suffix='.csv') as tmp_file:
                    for chunk in uploaded_file.chunks():
                        tmp_file.write(chunk)
                    tmp_file_path = tmp_file.name

                # 複数エンコーディングで読み込み
                encodings = ['cp932', 'shift_jis', 'utf-8', 'utf-8-sig']
                df = None
                used_encoding = None

                for encoding in encodings:
                    try:
                        df = pd.read_csv(tmp_file_path, encoding=encoding)
                        used_encoding = encoding
                        break
                    except:
                        continue

                if df is None:
                    messages.error(request, 'CSVファイルを読み込めませんでした。')
                    return redirect('materials:upload_csv_import')

                # 原料ID列を確認
                id_column = None
                for col in df.columns:
                    if '原料ID' in col or 'ID' in col.upper():
                        id_column = col
                        break

                if id_column is None:
                    messages.error(request, '原料ID列が見つかりませんでした。')
                    return redirect('materials:upload_csv_import')

                # 重複チェック
                existing_ids = []
                new_ids = []

                for _, row in df.iterrows():
                    material_id = str(row.get(id_column, '')).strip()
                    if material_id:
                        if Material.objects.filter(material_id=material_id).exists():
                            existing_ids.append(material_id)
                        else:
                            new_ids.append(material_id)

                # セッションに情報を保存
                request.session['csv_preview_data'] = {
                    'filename': uploaded_file.name,
                    'total_rows': len(df),
                    'columns': list(df.columns),
                    'encoding': used_encoding,
                    'id_column': id_column,
                    'existing_count': len(existing_ids),
                    'new_count': len(new_ids),
                    'existing_ids': existing_ids[:10],
                    'new_ids': new_ids[:10]
                }

                # 一時ファイルを削除
                os.unlink(tmp_file_path)

                return render(request, 'materials/csv_preview.html', {
                    'preview_data': request.session['csv_preview_data']
                })

            except Exception as e:
                messages.error(request, f'ファイル処理エラー: {str(e)}')
                return redirect('materials:upload_csv_import')

        elif action == 'import':
            # インポート実行段階
            overwrite_mode = request.POST.get('overwrite_mode', 'update')

            if 'csv_file' not in request.FILES:
                messages.error(request, 'CSVファイルが選択されていません。')
                return redirect('materials:upload_csv_import')

            uploaded_file = request.FILES['csv_file']

            try:
                import tempfile
                import os
                import pandas as pd
                from django.db import transaction

                # 一時ファイルに保存
                with tempfile.NamedTemporaryFile(delete=False, suffix='.csv') as tmp_file:
                    for chunk in uploaded_file.chunks():
                        tmp_file.write(chunk)
                    tmp_file_path = tmp_file.name

                # CSVファイル読み込み
                encodings = ['cp932', 'shift_jis', 'utf-8', 'utf-8-sig']
                df = None

                for encoding in encodings:
                    try:
                        df = pd.read_csv(tmp_file_path, encoding=encoding)
                        break
                    except:
                        continue

                if df is None:
                    messages.error(request, 'CSVファイルを読み込めませんでした。')
                    return redirect('materials:upload_csv_import')

                # 原料ID列を確認
                id_column = None
                for col in df.columns:
                    if '原料ID' in col or 'ID' in col.upper():
                        id_column = col
                        break

                # 完全フィールドマッピング
                field_mapping = {
                    'ラベル用備考': 'label_note',
                    'ラベル発行枚数': 'label_issue_count',
                    'リテスト延長使用期限': 'retest_extension_expiry',
                    'リテスト試験日数': 'retest_days',
                    '使用剤形': 'usage_form',
                    '使用期限表示': 'expiry_display',
                    '保障期間': 'guarantee_period',
                    '公差使用': 'tolerance_usage',
                    '分類': 'category',
                    '単価': 'unit_price',
                    '原料コード': 'material_code',
                    '原料区分': 'material_category',
                    '原料名': 'material_name',
                    '原料簿コード（サブ）': 'material_sub_code',
                    '原料簿コード（メイン）': 'material_main_code',
                    '原産国表示': 'origin_country',
                    '受入試験後使用期限': 'post_test_expiry',
                    '品質管理備考': 'qc_note',
                    '商品名': 'product_name',
                    '商品名カナ': 'product_kana',
                    '在庫単位（係数）': 'stock_unit_coefficient',
                    '変更申請／変更指示': 'change_request',
                    '差分警告割合': 'diff_warn_rate',
                    '正袋秤量': 'main_bag_weighing',
                    '正袋重量': 'main_bag_weight',
                    '生産本部備考': 'hq_note',
                    '画像パス': 'image_path',
                    '発注単位': 'order_unit',
                    '荷姿': 'packaging',
                    '補正情報': 'correction_info',
                    '製造所': 'manufacturer',
                    '規格': 'standard',
                    '調達区分': 'procurement_type',
                    '販売者': 'supplier',
                    '風袋重量': 'tare_weight',
                    'Unnamed: 36': 'unnamed_36',
                    'Unnamed: 37': 'unnamed_37',
                }

                # データベース処理
                created_count = 0
                updated_count = 0
                skipped_count = 0
                error_count = 0

                with transaction.atomic():
                    for index, row in df.iterrows():
                        try:
                            material_id = str(row.get(id_column, '')).strip()
                            if not material_id:
                                skipped_count += 1
                                continue

                            # 全フィールドをマッピング
                            field_data = {}

                            for csv_column, model_field in field_mapping.items():
                                if csv_column in df.columns:
                                    value = row.get(csv_column, '')

                                    # 単価の特別処理
                                    if csv_column == '単価':
                                        if pd.notna(value) and str(value).strip():
                                            try:
                                                # カンマと通貨記号を除去
                                                cleaned_price = str(value).replace(',', '').replace('¥', '').replace(
                                                    '￥', '').strip()
                                                if cleaned_price and cleaned_price not in ['nan', 'NaN', '']:
                                                    field_data[model_field] = cleaned_price
                                                else:
                                                    field_data[model_field] = '0'
                                            except:
                                                field_data[model_field] = '0'
                                        else:
                                            field_data[model_field] = '0'
                                    else:
                                        # 通常フィールドの処理
                                        if pd.notna(value):
                                            field_data[model_field] = str(value).strip()
                                        else:
                                            field_data[model_field] = ''

                            # 必須フィールド設定
                            field_data['is_active'] = True

                            # 上書きモード処理
                            if overwrite_mode == 'update':
                                material, created = Material.objects.update_or_create(
                                    material_id=material_id,
                                    defaults=field_data
                                )
                                if created:
                                    created_count += 1
                                else:
                                    updated_count += 1

                            elif overwrite_mode == 'skip':
                                if Material.objects.filter(material_id=material_id).exists():
                                    skipped_count += 1
                                else:
                                    field_data['material_id'] = material_id
                                    Material.objects.create(**field_data)
                                    created_count += 1

                            elif overwrite_mode == 'replace':
                                Material.objects.filter(material_id=material_id).delete()
                                field_data['material_id'] = material_id
                                Material.objects.create(**field_data)
                                created_count += 1

                        except Exception as e:
                            error_count += 1
                            logger.error(f"行処理エラー (原料ID: {material_id}): {e}")

                # 全データを有効化
                Material.objects.all().update(is_active=True)

                # 一時ファイルを削除
                os.unlink(tmp_file_path)

                # 結果メッセージ
                success_msg = f"""
CSVインポート完了！
• ファイル名: {uploaded_file.name}
• 処理モード: {overwrite_mode}
• 新規作成: {created_count}件
• 更新: {updated_count}件
• スキップ: {skipped_count}件
• エラー: {error_count}件
• 全38フィールド対応
                """
                messages.success(request, success_msg)

                # セッションクリア
                if 'csv_preview_data' in request.session:
                    del request.session['csv_preview_data']

                return redirect('materials:material_list')

            except Exception as e:
                messages.error(request, f'インポート処理エラー: {str(e)}')
                return redirect('materials:upload_csv_import')

    # GET リクエスト: アップロード画面
    context = {
        'db_status': {
            'total_count': Material.objects.count(),
            'active_count': Material.objects.filter(is_active=True).count(),
        }
    }

    return render(request, 'materials/csv_upload_complete.html', context)

def clear_csv_session(request):
    """とりあえず動くバージョン"""
    return redirect('materials:material_list')