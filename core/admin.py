from django.contrib import admin
from .models import (
    Product, Equipment, ServiceReport, ReportItem,
    ReportImage, SavedFilter, MaintenanceRequest,
    MaintenanceRequestEquipment
)

class ReportItemInline(admin.TabularInline):
    model = ReportItem
    extra = 0

class ReportImageInline(admin.TabularInline):
    model = ReportImage
    extra = 0

class MaintenanceRequestEquipmentInline(admin.TabularInline):
    model = MaintenanceRequestEquipment
    extra = 0

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'manufacturer', 'model', 'category')
    search_fields = ('name', 'model', 'manufacturer')
    list_filter = ('category',)

@admin.register(Equipment)
class EquipmentAdmin(admin.ModelAdmin):
    list_display = ('product', 'serial_number', 'current_facility', 'current_location', 'installation_date')
    search_fields = ('serial_number', 'product__name', 'current_facility')
    list_filter = ('product__category', 'installation_date')

@admin.register(ServiceReport)
class ServiceReportAdmin(admin.ModelAdmin):
    list_display = ('id', 'client_name', 'location', 'service_date', 'engineer', 'status')
    list_filter = ('status', 'service_date', 'engineer')
    search_fields = ('client_name', 'location', 'issue_description')
    inlines = [ReportItemInline, ReportImageInline]
    readonly_fields = ('created_at', 'updated_at')

admin.site.register(ReportItem)
admin.site.register(ReportImage)

@admin.register(SavedFilter)
class SavedFilterAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'filter_type', 'is_default', 'created_at')
    list_filter = ('filter_type', 'is_default')
    search_fields = ('name', 'user__username')
