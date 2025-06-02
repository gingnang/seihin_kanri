# materials/templatetags/image_filters.py
from django import template
import os

register = template.Library()


@register.filter
def image_path(value):
    """
    CSVの画像パスを正しいメディアパスに変換

    入力例: "images￥1.jpg" または "images\1.jpg"
    出力例: "materials/images/1.jpg"
    """
    if not value:
        return ""

    # 文字コードの問題で￥（全角円マーク）になった場合を考慮
    # Windowsのバックスラッシュと全角円マークをフォワードスラッシュに変換
    path = str(value).replace('\\', '/').replace('￥', '/')

    # images/ で始まる場合、materials/ を前に追加
    if path.startswith('images/'):
        path = 'materials/' + path
    # 既に materials/ で始まっている場合はそのまま
    elif path.startswith('materials/'):
        pass
    # どちらでもない場合（ファイル名のみ）、materials/images/ を前に追加
    else:
        path = 'materials/images/' + path

    return path


@register.filter
def filename_only(value):
    """
    パスからファイル名のみを抽出

    入力例: "images￥1.jpg" または "images\1.jpg"
    出力例: "1.jpg"
    """
    if not value:
        return ""

    # 文字コード問題対応：￥も\として扱う
    path = str(value).replace('\\', '/').replace('￥', '/')

    # ファイル名のみを抽出
    return os.path.basename(path)


@register.filter
def debug_path(value):
    """
    デバッグ用：パスの変換状況を表示
    """
    if not value:
        return "パスなし"

    original = str(value)
    normalized = original.replace('\\', '/').replace('￥', '/')
    final = image_path(value)

    return f"元: {original} → 正規化: {normalized} → 最終: {final}"


@register.filter
def clean_path(value):
    """
    パスから￥やバックスラッシュをクリーンアップ
    """
    if not value:
        return ""

    # ￥（全角円マーク）と\（バックスラッシュ）を/に変換
    cleaned = str(value).replace('￥', '/').replace('\\', '/')

    # images/ の部分を除去してファイル名のみにする
    if cleaned.startswith('images/'):
        cleaned = cleaned[7:]  # "images/" の7文字を除去

    return cleaned