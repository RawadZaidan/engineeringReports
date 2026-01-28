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
    raw_summary = models.TextField(blank=True, null=True)
    
    status = models.CharField(max_length=20, choices=[
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed')
    ], default='pending')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Tender Summary: {self.title or self.document.name}"

    class Meta:
        verbose_name_plural = "Tender Summaries"
        ordering = ['-created_at']
