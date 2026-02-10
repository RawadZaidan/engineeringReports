from django.db import models
from django.contrib.auth.models import User

class TenderSummary(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tender_summaries')
    document = models.FileField(upload_to='tender_docs/')
    
    # Processed data
    title = models.CharField(max_length=255, blank=True, null=True)
    deadline = models.CharField(max_length=255, blank=True, null=True)
    lots = models.TextField(blank=True, null=True)
    location = models.CharField(max_length=255, blank=True, null=True)
    tenderer = models.CharField(max_length=255, blank=True, null=True)
    important_notes = models.TextField(blank=True, null=True)
    quality_certificates = models.TextField(blank=True, null=True)
    
    # New fields requested
    financial_thresholds = models.TextField(blank=True, null=True, help_text="Minimum annual turnover and financial requirements")
    maintenance_warranty = models.TextField(blank=True, null=True, help_text="Post-delivery obligations and warranty terms")
    technical_financial_split = models.CharField(max_length=255, blank=True, null=True, help_text="Evaluation weighting (e.g. 60/40)")
    key_experts = models.TextField(blank=True, null=True, help_text="Specific roles and certifications required")
    past_performance = models.TextField(blank=True, null=True, help_text="Similar project requirements")
    clarification_deadline = models.CharField(max_length=255, blank=True, null=True, help_text="Deadline for asking questions")
    bid_security = models.CharField(max_length=255, blank=True, null=True, help_text="Bond amount and format")
    site_visit = models.TextField(blank=True, null=True, help_text="Mandatory or optional site visits/meetings")
    killer_clauses = models.TextField(blank=True, null=True, help_text="Unusual or high-risk clauses")
    document_checklist = models.TextField(blank=True, null=True, help_text="List of all required submission files")
    
    # Filtering fields
    donor = models.CharField(max_length=255, blank=True, null=True)
    continent = models.CharField(max_length=100, blank=True, null=True)
    category = models.CharField(max_length=50, choices=[
        ('medical', 'Medical'),
        ('lab', 'Lab'),
        ('agricultural', 'Agricultural'),
        ('industrial', 'Industrial'),
        ('educational', 'Educational'),
        ('research', 'Research'),
        ('mix', 'Mix')
    ], blank=True, null=True)
    
    # Smart Agent Enhancements
    local_presence_required = models.BooleanField(default=False, help_text="Is a local partner or office mandatory?")
    currency_code = models.CharField(max_length=100, blank=True, null=True, help_text="Currency code (e.g., USD, EUR, LBP)")
    
    # Progress Tracking
    analysis_progress = models.IntegerField(default=0)
    current_step = models.CharField(max_length=255, blank=True, null=True)
    
    is_human_enhanced = models.BooleanField(default=False, help_text="Has this summary been manually edited by a human?")
    
    raw_summary = models.TextField(blank=True, null=True)
    failure_reason = models.TextField(blank=True, null=True)
    
    status = models.CharField(max_length=20, choices=[
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed')
    ], default='pending')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def get_lots(self):
        """Returns the lots field as a list of dictionaries if it's JSON."""
        if not self.lots:
            return []
        try:
            # Handle if it's already a list/dict
            if isinstance(self.lots, (list, dict)):
                data = self.lots
            else:
                # Use json.loads with some cleanup for single quotes
                content = self.lots.replace("'", '"')
                import json
                data = json.loads(content)
            
            # Normalize data: ensure it's a list of lots, and each lot has an 'items' list
            if isinstance(data, dict): # Sometimes AI returns a single dict instead of list
                data = [data]
            
            return data
        except:
            # Fallback for old/malformed data
            return [{'lot_number': '-', 'items': [{'name': self.lots, 'quantity': '-'}]}]

    def get_flattened_items(self):
        """Helper to get a flat list of items across all lots for the table."""
        lots = self.get_lots()
        flat_list = []
        for lot in lots:
            lot_num = lot.get('lot_number', '-')
            # Handle the old structure if it exists
            if 'items' in lot:
                for item in lot['items']:
                    flat_list.append({
                        'lot_number': lot_num,
                        'name': item.get('name', '-'),
                        'quantity': item.get('quantity', '-')
                    })
            else:
                # Fallback for the intermediate structure we just had
                flat_list.append({
                    'lot_number': lot_num,
                    'name': lot.get('description', '-'),
                    'quantity': lot.get('quantities', '-')
                })
        return flat_list

    def __str__(self):
        return f"Tender Summary: {self.title or self.document.name}"

    class Meta:
        verbose_name_plural = "Tender Summaries"
        ordering = ['-created_at']
