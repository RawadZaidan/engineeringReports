from django.contrib import admin
from .models import TenderSummary

@admin.register(TenderSummary)
class TenderSummaryAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'tenderer', 'deadline', 'user', 'status', 'created_at')
    list_filter = ('status', 'user', 'created_at')
    search_fields = ('title', 'tenderer', 'location', 'raw_summary')
    readonly_fields = ('created_at', 'updated_at')
