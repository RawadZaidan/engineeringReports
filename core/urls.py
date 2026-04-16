from django.urls import path
from .views import (
    DashboardView, ServiceReportListView, ServiceReportCreateView, ServiceReportUpdateView, ServiceReportDetailView,
    ProductListView, ProductCreateView,
    EquipmentListView, equipment_create_ajax,
    MaintenanceRequestListView, MaintenanceRequestCreateView, MaintenanceRequestDetailView, MaintenanceRequestUpdateView,
    update_pricing_ajax, product_create_ajax, product_categories_ajax, product_names_by_category_ajax,
    product_brands_ajax, product_models_ajax, product_get_or_create_ajax,
    DriverSchedulingView, DriverRequestCreateView, DriverRequestUpdateView, driver_request_action,
    get_driver_occupancy,
    EngineerSchedulingView, MaintenanceAssignmentCreateView, MaintenanceAssignmentUpdateView
)

urlpatterns = [
    path('', DashboardView.as_view(), name='dashboard'),
    path('reports/', ServiceReportListView.as_view(), name='report_list'),
    path('report/new/', ServiceReportCreateView.as_view(), name='report_create'),
    path('report/<int:pk>/edit/', ServiceReportUpdateView.as_view(), name='report_update'),
    path('report/<int:pk>/', ServiceReportDetailView.as_view(), name='report_detail'),
    path('products/', ProductListView.as_view(), name='product_list'),
    path('products/new/', ProductCreateView.as_view(), name='product_create'),
    path('products/create-ajax/', product_create_ajax, name='product_create_ajax'),
    path('products/categories/', product_categories_ajax, name='product_categories_ajax'),
    path('products/names-by-category/', product_names_by_category_ajax, name='product_names_by_category_ajax'),
    path('products/brands/', product_brands_ajax, name='product_brands_ajax'),
    path('products/models/', product_models_ajax, name='product_models_ajax'),
    path('products/get-or-create/', product_get_or_create_ajax, name='product_get_or_create_ajax'),
    
    path('registry/', EquipmentListView.as_view(), name='equipment_list'),
    path('registry/create-ajax/', equipment_create_ajax, name='equipment_create_ajax'),
    
    # Maintenance Requests
    path('requests/', MaintenanceRequestListView.as_view(), name='request_list'),
    path('requests/new/', MaintenanceRequestCreateView.as_view(), name='request_create'),
    path('requests/<int:pk>/', MaintenanceRequestDetailView.as_view(), name='request_detail'),
    path('requests/<int:pk>/edit/', MaintenanceRequestUpdateView.as_view(), name='request_update'),
    path('requests/update-pricing/', update_pricing_ajax, name='update_pricing_ajax'),
    
    # Driver Scheduling
    path('scheduling/', DriverSchedulingView.as_view(), name='driver_scheduling'),
    path('scheduling/request/', DriverRequestCreateView.as_view(), name='driver_request_create'),
    path('scheduling/request/<int:pk>/edit/', DriverRequestUpdateView.as_view(), name='driver_request_edit'),
    path('scheduling/action/<int:pk>/', driver_request_action, name='driver_request_action'),
    path('scheduling/occupancy/', get_driver_occupancy, name='get_driver_occupancy'),
    
    # Engineer Scheduling
    path('engineering/scheduling/', EngineerSchedulingView.as_view(), name='engineer_scheduling'),
    path('engineering/scheduling/new/', MaintenanceAssignmentCreateView.as_view(), name='maintenance_assignment_create'),
    path('engineering/scheduling/<int:pk>/edit/', MaintenanceAssignmentUpdateView.as_view(), name='maintenance_assignment_update'),
]
