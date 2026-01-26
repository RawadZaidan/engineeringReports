from django.urls import path
from .views import (
    DashboardView, ServiceReportCreateView, ServiceReportUpdateView, ServiceReportDetailView,
    ProductListView, ProductCreateView, product_create_ajax,
    MaintenanceRequestListView, MaintenanceRequestCreateView, MaintenanceRequestDetailView, MaintenanceRequestUpdateView
)

urlpatterns = [
    path('', DashboardView.as_view(), name='dashboard'),
    path('report/new/', ServiceReportCreateView.as_view(), name='report_create'),
    path('report/<int:pk>/edit/', ServiceReportUpdateView.as_view(), name='report_update'),
    path('report/<int:pk>/', ServiceReportDetailView.as_view(), name='report_detail'),
    path('products/', ProductListView.as_view(), name='product_list'),
    path('products/new/', ProductCreateView.as_view(), name='product_create'),
    path('products/create-ajax/', product_create_ajax, name='product_create_ajax'),
    
    # Maintenance Requests
    path('requests/', MaintenanceRequestListView.as_view(), name='request_list'),
    path('requests/new/', MaintenanceRequestCreateView.as_view(), name='request_create'),
    path('requests/<int:pk>/', MaintenanceRequestDetailView.as_view(), name='request_detail'),
    path('requests/<int:pk>/edit/', MaintenanceRequestUpdateView.as_view(), name='request_update'),
]
