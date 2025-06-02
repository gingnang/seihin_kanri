"""
URL Configuration for genryou_kanri project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.urls import path
from . import views

app_name = 'materials'

# materials/urls.py の urlpatterns に以下を追加
# （既存のpathの後に追加してください）

urlpatterns = [
    path('', views.material_list, name='material_list'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('load-csv/', views.load_csv_data, name='load_csv_data'),
    # ↓ これらの行を追加
    path('upload-csv/', views.upload_csv_import, name='upload_csv_import'),
    path('clear-csv-session/', views.clear_csv_session, name='clear_csv_session'),
    # ↑ ここまで追加
    path('analyze-csv/', views.analyze_csv_structure, name='analyze_csv_structure'),
    path('detail/<int:pk>/', views.material_detail, name='material_detail'),
    path('debug-materials/', views.debug_material_data, name='debug_material_data'),
    path('fix-price-data/', views.fix_price_data, name='fix_price_data'),
]

# 開発環境でのメディアファイル配信
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)