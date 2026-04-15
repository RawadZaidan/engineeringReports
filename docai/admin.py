from django.contrib import admin
from .models import TenderSummary

@admin.register(TenderSummary)
class TenderSummaryAdmin(admin.ModelAdmin):
    list_display = ('title', 'tenderer', 'deadline', 'user', 'status', 'created_at')
    list_filter = ('status', 'user', 'created_at')
    search_fields = ('title', 'tenderer', 'location', 'raw_summary')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('user', 'document', 'status', 'title', 'tenderer', 'location', 'deadline', 'clarification_deadline')
        }),
        ('Commercial & Financial', {
            'fields': ('financial_thresholds', 'bid_security', 'technical_financial_split', 'maintenance_warranty')
        }),
        ('Technical & Requirements', {
            'fields': ('lots', 'key_experts', 'past_performance', 'quality_certificates', 'important_notes')
        }),
        ('Analysis Results', {
            'fields': ('raw_summary', 'killer_clauses', 'document_checklist', 'failure_reason')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
