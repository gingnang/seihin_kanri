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

urlpatterns = [
    path('materials/', views.material_list, name='material_list'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('load-csv/', views.load_csv_data, name='load_csv_data'),
    path('analyze-csv/', views.analyze_csv_structure, name='analyze_csv_structure'),
    path('detail/<int:pk>/', views.material_detail, name='material_detail'),
]

# 開発環境でのメディアファイル配信
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)