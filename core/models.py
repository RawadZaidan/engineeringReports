from django.db import models
from django.contrib.auth.models import User
from PIL import Image
from io import BytesIO
from django.core.files.base import ContentFile
import os
from django.utils import timezone
from django.core.cache import cache


def _invalidate_dashboard_caches():
    """
    Clears per-user dashboard stats and notification-count caches for ALL users.
    Called whenever a MaintenanceRequest or ServiceReport changes so the next
    page load gets fresh data.  The team is small so iterating users is cheap.
    """
    for uid in User.objects.values_list('id', flat=True):
        cache.delete(f'dashboard_stats_{uid}')
        cache.delete(f'notification_counts_{uid}')

class Product(models.Model):
    """Product Catalogue - Blueprints/Templates (Manufacturer + Model)"""
    name = models.CharField(max_length=255)
    category = models.CharField(max_length=255)
    manufacturer = models.CharField(max_length=255)
    model = models.CharField(max_length=255)
    notes = models.TextField(blank=True, null=True)
    
    class Meta:
        unique_together = [['manufacturer', 'model']]
        ordering = ['manufacturer', 'model']

    def __str__(self):
        return f"{self.manufacturer} {self.model} ({self.name})"

class Equipment(models.Model):
    """Equipment Registry - Specific Physical Units (Linked to Catalogue + Serial Number)"""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='instances')
    serial_number = models.CharField(max_length=255)
    current_facility = models.CharField(max_length=255, blank=True, null=True)
    current_location = models.CharField(max_length=255, blank=True, null=True)
    installation_date = models.DateField(blank=True, null=True)
    warranty_expiration_date = models.DateField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True)

    class Meta:
        unique_together = [['product', 'serial_number']]
        verbose_name_plural = "Equipment Registry"
        ordering = ['product', 'serial_number']

    def __str__(self):
        return f"{self.product.manufacturer} {self.product.model} | S/N: {self.serial_number}"

class ServiceReport(models.Model):
    STATUS_CHOICES = [
        ('Draft', 'Draft'),
        ('Pending', 'Pending Review'),
        ('Completed', 'Completed'),
    ]

    client_name = models.CharField(max_length=200, blank=True, null=True)
    project_reference = models.CharField(max_length=100, blank=True, null=True, help_text="Project Reference / Contract Number")
    location = models.CharField(max_length=200, blank=True, null=True, help_text="City / Facility / Department")
    donor = models.CharField(max_length=200, blank=True, null=True)
    service_date = models.DateTimeField(blank=True, null=True)
    
    maintenance_request = models.ForeignKey('MaintenanceRequest', on_delete=models.SET_NULL, null=True, blank=True, related_name='service_reports')
    engineer = models.ForeignKey(User, on_delete=models.CASCADE)

    issue_description = models.TextField(blank=True, null=True)
    work_performed = models.TextField(blank=True, null=True)
    parts_used = models.TextField(blank=True, null=True)

    service_type = models.CharField(max_length=255, help_text="Comma-separated service types", blank=True, null=True)
    billing_category = models.CharField(max_length=255, help_text="Comma-separated billing categories", blank=True, null=True)
    final_status = models.CharField(max_length=255, help_text="Comma-separated final status outcomes", blank=True, null=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Draft', db_index=True)
    follow_up_required = models.BooleanField(default=False, db_index=True)

    warranty_start_on_submission = models.BooleanField(
        default=False, 
        verbose_name="Warranty starts the day the report is submitted",
        help_text="If checked, linked equipment warranty will be updated."
    )
    warranty_duration_years = models.PositiveIntegerField(
        choices=[(i, f"{i} Year{'s' if i > 1 else ''}") for i in range(1, 6)],
        null=True,
        blank=True,
        verbose_name="Warranty Duration"
    )

    client_representative_name = models.CharField(max_length=200, blank=True, null=True)
    client_phone_number = models.CharField(max_length=20, blank=True, null=True, help_text="Contact number for the client")
    client_signature = models.ImageField(upload_to='signatures/', blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        _invalidate_dashboard_caches()

    class Meta:
        indexes = [
            models.Index(fields=['engineer', 'status'], name='core_sr_eng_status_idx'),
            models.Index(fields=['status'], name='core_sr_status_idx'),
        ]

    def __str__(self):
        return f"SR-{self.id} | {self.client_name}"

class ReportItem(models.Model):
    report = models.ForeignKey(ServiceReport, on_delete=models.CASCADE, related_name='items')
    equipment = models.ForeignKey(Equipment, on_delete=models.CASCADE, related_name='service_history', null=True, blank=True)
    equipment_note = models.TextField(blank=True, null=True, help_text="Specific note for this equipment during this service")

    def __str__(self):
        return f"{self.equipment} (Report {self.report.id})"

class ReportImage(models.Model):
    report = models.ForeignKey(ServiceReport, related_name='images', on_delete=models.CASCADE)
    image = models.ImageField(upload_to='report_photos/')
    thumbnail = models.ImageField(upload_to='report_thumbnails/', blank=True, null=True)
    caption = models.CharField(max_length=255, blank=True, null=True)

    def save(self, *args, **kwargs):
        if self.image:
            # Generate thumbnail
            try:
                img = Image.open(self.image)
                # Convert RGBA to RGB if needed
                if img.mode in ('RGBA', 'P'):
                    img = img.convert('RGB')
                
                # Resize keeping aspect ratio
                img.thumbnail((600, 600), Image.Resampling.LANCZOS)
                
                # Save to buffer
                thumb_io = BytesIO()
                img.save(thumb_io, format='JPEG', quality=85)
                
                # Create thumbnail filename
                name, ext = os.path.splitext(os.path.basename(self.image.name))
                thumb_name = f"{name}_thumb.jpg"
                
                # Save thumbnail file
                self.thumbnail.save(thumb_name, ContentFile(thumb_io.getvalue()), save=False)
            except Exception as e:
                print(f"Error creating thumbnail: {e}")
                # Fallback handled in template (if thumbnail is null)

        super().save(*args, **kwargs)

    def __str__(self):
        return f"Image for Report {self.report.id}"

class MaintenanceRequest(models.Model):
    URGENCY_CHOICES = [
        ('Low', 'Low'),
        ('Medium', 'Medium'),
        ('High', 'High'),
        ('Emergency', 'Emergency'),
    ]

    REQUEST_STATUS_CHOICES = [
        ('Open', 'Open'),
        ('Scheduled', 'Scheduled'),
        ('In Progress', 'In Progress'),
        ('Completed', 'Completed'),
        ('Cancelled', 'Cancelled'),
    ]

    LEBANON_LOCATIONS = [
        ('Beirut', (('Beirut', 'Beirut'),)),
        ('Mount Lebanon', (
            ('Baabda', 'Baabda'), ('Matn', 'Matn'), ('Chouf', 'Chouf'),
            ('Aley', 'Aley'), ('Keserwan', 'Keserwan'), ('Jbeil', 'Jbeil'),
        )),
        ('North Lebanon', (
            ('Tripoli', 'Tripoli'), ('Zgharta', 'Zgharta'), ('Bsharri', 'Bsharri'),
            ('Batroun', 'Batroun'), ('Koura', 'Koura'), ('Minieh-Danniyeh', 'Minieh-Danniyeh'),
        )),
        ('Akkar', (('Akkar', 'Akkar'),)),
        ('Beqaa', (('Zahle', 'Zahle'), ('Rashaya', 'Rashaya'), ('West Beqaa', 'West Beqaa'),)),
        ('Baalbek-Hermel', (('Baalbek', 'Baalbek'), ('Hermel', 'Hermel'),)),
        ('South Lebanon', (('Sidon', 'Sidon'), ('Jezzine', 'Jezzine'), ('Tyre', 'Tyre'),)),
        ('Nabatieh', (('Nabatieh', 'Nabatieh'), ('Marjeyoun', 'Marjeyoun'), ('Hasbaya', 'Hasbaya'), ('Bint Jbeil', 'Bint Jbeil'),)),
    ]

    BILLING_STATUS_CHOICES = [
        ('Warranty', 'Under Warranty'),
        ('Billable', 'Billable'),
        ('Contract', 'Under Contract'),
        ('FOC', 'Free of Charge'),
    ]

    customer_contact_date = models.DateField(default=timezone.now)
    availability_start = models.DateField(blank=True, null=True)
    availability_end = models.DateField(blank=True, null=True)
    urgency = models.CharField(max_length=20, choices=URGENCY_CHOICES, default='Medium', db_index=True)
    
    contact_name = models.CharField(max_length=255, blank=True, null=True)
    contact_number = models.CharField(max_length=50, blank=True, null=True)
    contact_email = models.EmailField(max_length=255, blank=True, null=True)
    facility_name = models.CharField(max_length=255, blank=True, null=True)
    location = models.CharField(max_length=100, choices=LEBANON_LOCATIONS, blank=True, null=True)
    donor = models.CharField(max_length=255, blank=True, null=True)
    
    equipment_list = models.TextField(blank=True, null=True, help_text="Legacy list of names for equipment")
    request_details = models.TextField(blank=True, null=True)
    service_type = models.CharField(max_length=255, blank=True, null=True)
    
    billing_status = models.CharField(max_length=20, choices=BILLING_STATUS_CHOICES, default='Billable')
    estimated_cost = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    
    pricing_set_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='priced_requests')
    pricing_set_at = models.DateTimeField(null=True, blank=True)
    
    status = models.CharField(max_length=20, choices=REQUEST_STATUS_CHOICES, default='Open', db_index=True)
    
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        _invalidate_dashboard_caches()

    class Meta:
        indexes = [
            models.Index(fields=['status'], name='core_mr_status_idx'),
            models.Index(fields=['urgency', 'created_at'], name='core_mr_urg_created_idx'),
        ]

    def __str__(self):
        return f"MR-{self.id} | {self.facility_name or 'No Facility'}"

class MaintenanceRequestEquipment(models.Model):
    request = models.ForeignKey(MaintenanceRequest, related_name='equipment_items', on_delete=models.CASCADE)
    equipment = models.ForeignKey(Equipment, on_delete=models.SET_NULL, null=True, blank=True)
    notes = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.equipment} (MR-{self.request.id})"

class SavedFilter(models.Model):
    FILTER_TYPE_CHOICES = [
        ('report', 'Service Report'),
        ('request', 'Maintenance Request'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='saved_filters')
    name = models.CharField(max_length=100)
    filter_type = models.CharField(max_length=20, choices=FILTER_TYPE_CHOICES)
    filter_params = models.JSONField()
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        unique_together = [['user', 'name', 'filter_type']]
    
class Driver(models.Model):
    user = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='driver_profile')
    name = models.CharField(max_length=100)
    photo = models.ImageField(upload_to='drivers/', blank=True, null=True)
    license_info = models.CharField(max_length=255, blank=True, null=True, help_text="e.g., Class A CDL Holder", default="Class A CDL Holder")
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

class DriverRequest(models.Model):
    DEPARTMENT_CHOICES = [
        ('Engineering', 'Engineering'),
        ('Sales', 'Sales'),
        ('Procurement', 'Procurement'),
        ('Management', 'Management'),
    ]
    
    STATUS_CHOICES = [
        ('Pending', 'Pending Review'),
        ('Approved', 'Approved'),
        ('Denied', 'Denied'),
        ('Edit Requested', 'Edit Requested'),
        ('Completed', 'Completed'),
        ('Cancelled', 'Cancelled'),
    ]

    VEHICLE_CHOICES = [
        ('Truck', 'Truck'),
        ('Car', 'Car'),
        ('Moto', 'Moto'),
    ]

    requester = models.ForeignKey(User, on_delete=models.CASCADE, related_name='driver_requests')
    driver = models.ForeignKey(Driver, on_delete=models.CASCADE, related_name='assignments')
    maintenance_request = models.ForeignKey('MaintenanceRequest', on_delete=models.SET_NULL, null=True, blank=True, related_name='driver_trips')
    department = models.CharField(max_length=50, choices=DEPARTMENT_CHOICES)
    
    location = models.CharField(max_length=100, choices=MaintenanceRequest.LEBANON_LOCATIONS, verbose_name="Destination")
    estimated_distance = models.CharField(max_length=50, blank=True, null=True, help_text="e.g., 30 km")
    
    client_name = models.CharField(max_length=255, blank=True, null=True, verbose_name="End User (Client)")
    contact_person = models.CharField(max_length=255, blank=True, null=True)
    contact_number = models.CharField(max_length=50, blank=True, null=True)
    
    date = models.DateField()
    
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    
    duration = models.CharField(max_length=100, help_text="e.g., 2 hours, Full day", blank=True, null=True)
    vehicle_type = models.CharField(max_length=20, choices=VEHICLE_CHOICES, default='Car')
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending', db_index=True)
    admin_notes = models.TextField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-date', '-created_at']
        indexes = [
            models.Index(fields=['date'], name='core_dr_date_idx'),
        ]

    def __str__(self):
        return f"{self.requester.username} - {self.driver.name} ({self.date})"

class Engineer(models.Model):
    user = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='engineer_profile')
    name = models.CharField(max_length=100)
    photo = models.ImageField(upload_to='engineers/', blank=True, null=True)
    specialization = models.CharField(max_length=255, blank=True, null=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

class MaintenanceAssignment(models.Model):
    engineer = models.ForeignKey(Engineer, on_delete=models.CASCADE, related_name='assignments')
    maintenance_request = models.ForeignKey(MaintenanceRequest, on_delete=models.CASCADE, related_name='assignments')
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['date', 'start_time']
        indexes = [
            models.Index(fields=['engineer', 'date'], name='core_ma_eng_date_idx'),
            models.Index(fields=['date'], name='core_ma_date_idx'),
        ]

    def __str__(self):
        return f"{self.engineer.name} - MR-{self.maintenance_request.id} ({self.date})"
