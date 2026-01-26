from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

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

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Draft')
    follow_up_required = models.BooleanField(default=False)

    client_representative_name = models.CharField(max_length=200, blank=True, null=True)
    client_phone_number = models.CharField(max_length=20, blank=True, null=True, help_text="Contact number for the client")
    client_signature = models.ImageField(upload_to='signatures/', blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"SR-{self.id} | {self.client_name}"

class ReportItem(models.Model):
    report = models.ForeignKey(ServiceReport, on_delete=models.CASCADE, related_name='items')
    equipment = models.ForeignKey(Equipment, on_delete=models.CASCADE, related_name='service_history')
    equipment_note = models.TextField(blank=True, null=True, help_text="Specific note for this equipment during this service")

    def __str__(self):
        return f"{self.equipment} (Report {self.report.id})"

class ReportImage(models.Model):
    report = models.ForeignKey(ServiceReport, related_name='images', on_delete=models.CASCADE)
    image = models.ImageField(upload_to='report_photos/')
    caption = models.CharField(max_length=255, blank=True, null=True)

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
    urgency = models.CharField(max_length=20, choices=URGENCY_CHOICES, default='Medium')
    
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
    
    status = models.CharField(max_length=20, choices=REQUEST_STATUS_CHOICES, default='Open')
    
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

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
    
    def __str__(self):
        return f"{self.name} ({self.user.username})"
