# -*- coding: utf-8 -*-
from django import template
from decimal import Decimal, InvalidOperation

register = template.Library()


@register.filter
def mul(value, arg):
    """
    乗算フィルタ: {{ value|mul:arg }}
    例: {{ 100|mul:5 }} → 500
    """
    try:
        if value is None or arg is None:
            return 0

        # Decimalまたはfloatで計算
        if isinstance(value, Decimal) or isinstance(arg, Decimal):
            return Decimal(str(value)) * Decimal(str(arg))
        else:
            return float(value) * float(arg)

    except (ValueError, TypeError, InvalidOperation, OverflowError):
        return 0


@register.filter
def div(value, arg):
    """
    除算フィルタ: {{ value|div:arg }}
    例: {{ 100|div:5 }} → 20
    """
    try:
        if value is None or arg is None:
            return 0

        arg_float = float(arg)
        if arg_float == 0:
            return 0  # ゼロ除算を防ぐ

        # Decimalまたはfloatで計算
        if isinstance(value, Decimal) or isinstance(arg, Decimal):
            return Decimal(str(value)) / Decimal(str(arg))
        else:
            return float(value) / float(arg)

    except (ValueError, TypeError, InvalidOperation, ZeroDivisionError, OverflowError):
        return 0


@register.filter
def sub(value, arg):
    """
    減算フィルタ: {{ value|sub:arg }}
    例: {{ 100|sub:30 }} → 70
    """
    try:
        if value is None or arg is None:
            return 0

        # Decimalまたはfloatで計算
        if isinstance(value, Decimal) or isinstance(arg, Decimal):
            return Decimal(str(value)) - Decimal(str(arg))
        else:
            return float(value) - float(arg)

    except (ValueError, TypeError, InvalidOperation, OverflowError):
        return 0


@register.filter
def add_filter(value, arg):
    """
    加算フィルタ: {{ value|add_filter:arg }}
    例: {{ 100|add_filter:50 }} → 150
    注：Djangoには標準でaddフィルタがあるため、別名で定義
    """
    try:
        if value is None or arg is None:
            return 0

        # Decimalまたはfloatで計算
        if isinstance(value, Decimal) or isinstance(arg, Decimal):
            return Decimal(str(value)) + Decimal(str(arg))
        else:
            return float(value) + float(arg)

    except (ValueError, TypeError, InvalidOperation, OverflowError):
        return 0


@register.filter
def percentage(value, total):
    """
    パーセンテージ計算フィルタ: {{ value|percentage:total }}
    例: {{ 25|percentage:100 }} → 25.0
    """
    try:
        if value is None or total is None:
            return 0

        total_float = float(total)
        if total_float == 0:
            return 0  # ゼロ除算を防ぐ

        return (float(value) / total_float) * 100

    except (ValueError, TypeError, InvalidOperation, ZeroDivisionError, OverflowError):
        return 0


@register.filter
def abs_filter(value):
    """
    絶対値フィルタ: {{ value|abs_filter }}
    例: {{ -50|abs_filter }} → 50
    """
    try:
        if value is None:
            return 0
        return abs(float(value))
    except (ValueError, TypeError, OverflowError):
        return 0


@register.filter
def round_filter(value, digits=0):
    """
    四捨五入フィルタ: {{ value|round_filter:2 }}
    例: {{ 3.14159|round_filter:2 }} → 3.14
    """
    try:
        if value is None:
            return 0
        digits = int(digits) if digits else 0
        return round(float(value), digits)
    except (ValueError, TypeError, OverflowError):
        return 0


@register.filter
def min_filter(value, minimum):
    """
    最小値フィルタ: {{ value|min_filter:0 }}
    例: {{ -10|min_filter:0 }} → 0
    """
    try:
        if value is None:
            return minimum
        return max(float(value), float(minimum))
    except (ValueError, TypeError, OverflowError):
        return minimum


@register.filter
def max_filter(value, maximum):
    """
    最大値フィルタ: {{ value|max_filter:100 }}
    例: {{ 150|max_filter:100 }} → 100
    """
    try:
        if value is None:
            return maximum
        return min(float(value), float(maximum))
    except (ValueError, TypeError, OverflowError):
        return maximum


@register.filter
def format_currency(value):
    """
    通貨フォーマットフィルタ: {{ value|format_currency }}
    例: {{ 1234.56|format_currency }} → ¥1,235
    """
    try:
        if value is None or value == 0:
            return "¥0"

        # 整数に丸める
        rounded_value = round(float(value))
        # カンマ区切りで表示
        return f"¥{rounded_value:,}"

    except (ValueError, TypeError, OverflowError):
        return "¥0"


@register.filter
def format_weight(value):
    """
    重量フォーマットフィルタ: {{ value|format_weight }}
    例: {{ 25.5|format_weight }} → 25.5kg
    """
    try:
        if value is None or value == 0:
            return "0kg"

        # 小数点1桁で表示
        return f"{float(value):.1f}kg"

    except (ValueError, TypeError, OverflowError):
        return "0kg"


@register.filter
def is_positive(value):
    """
    正の数かチェック: {{ value|is_positive }}
    例: {{ 10|is_positive }} → True
    """
    try:
        if value is None:
            return False
        return float(value) > 0
    except (ValueError, TypeError, OverflowError):
        return False


@register.filter
def safe_divide(value, divisor, default=0):
    """
    安全な除算（ゼロ除算時はデフォルト値を返す）
    例: {{ 100|safe_divide:0:999 }} → 999
    """
    try:
        if value is None or divisor is None:
            return default

        divisor_float = float(divisor)
        if divisor_float == 0:
            return default

        return float(value) / divisor_float

    except (ValueError, TypeError, OverflowError):
        return default

# materials/templatetags/material_filters.py
# このファイルを materials/templatetags/ ディレクトリに作成してください

from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """辞書から指定されたキーの値を取得する"""
    if isinstance(dictionary, dict):
        return dictionary.get(key, '')
    return ''

@register.filter
def class_name(obj):
    """オブジェクトのクラス名を取得する"""
    return obj.__class__.__name__