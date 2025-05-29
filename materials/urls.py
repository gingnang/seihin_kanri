from django.urls import path
from . import views

app_name = 'materials'

urlpatterns = [
    path('', views.material_list, name='material_list'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('load-csv/', views.load_csv_data, name='load_csv_data'),
    path('analyze-csv/', views.analyze_csv_structure, name='analyze_csv_structure'),
    path('detail/<int:pk>/', views.material_detail, name='material_detail'),
]