from django import forms
from .models import ServiceReport, Product, ReportItem, MaintenanceRequest, MaintenanceRequestEquipment
from django.forms import inlineformset_factory

class MaintenanceRequestForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user and not user.is_staff:
            restricted_fields = ['status', 'billing_status', 'estimated_cost']
            for field in restricted_fields:
                if field in self.fields:
                    del self.fields[field]

    class Meta:
        model = MaintenanceRequest
        fields = [
            'customer_contact_date', 'availability_start', 'availability_end', 'urgency',
            'contact_name', 'contact_number', 'contact_email', 'facility_name', 'location', 'donor',
            'request_details', 'status', 'billing_status', 'estimated_cost'
        ]
        widgets = {
            'customer_contact_date': forms.DateInput(attrs={'type': 'date'}),
            'availability_start': forms.DateInput(attrs={'type': 'date'}),
            'availability_end': forms.DateInput(attrs={'type': 'date'}),
            'request_details': forms.Textarea(attrs={'rows': 3}),
        }

class MaintenanceRequestEquipmentForm(forms.ModelForm):
    class Meta:
        model = MaintenanceRequestEquipment
        fields = ['equipment_type', 'model_name']
        widgets = {
            'equipment_type': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Instrument Type'}),
            'model_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Model Name'}),
        }

MaintenanceRequestEquipmentFormSet = inlineformset_factory(
    MaintenanceRequest, MaintenanceRequestEquipment,
    form=MaintenanceRequestEquipmentForm,
    extra=1, can_delete=True
)

class ServiceReportForm(forms.ModelForm):
    client_signature = forms.CharField(widget=forms.HiddenInput(), required=False)
    
    SERVICE_TYPE_CHOICES = [
        ('Preventive Maintenance', 'Preventive Maintenance'),
        ('Training', 'Training'),
        ('Installation', 'Installation'),
        ('Repair', 'Repair'),
        ('Commissioning', 'Commissioning'),
    ]
    
    BILLING_CATEGORY_CHOICES = [
        ('Paid Service', 'Paid Service'),
        ('Contract', 'Contract'),
        ('Warranty', 'Warranty'),
        ('Other', 'Other'),
    ]
    
    FINAL_STATUS_CHOICES = [
        ('Returned to working conditions', 'Returned to working conditions'),
        ('Needs Follow up', 'Needs Follow up'),
        ('Collected for maintenance', 'Collected for maintenance'),
    ]

    service_type = forms.MultipleChoiceField(
        choices=SERVICE_TYPE_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        required=False
    )
    
    billing_category = forms.MultipleChoiceField(
        choices=BILLING_CATEGORY_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        required=False
    )
    
    final_status = forms.MultipleChoiceField(
        choices=FINAL_STATUS_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        required=False
    )

    class Meta:
        model = ServiceReport
        fields = [
            'maintenance_request', 'client_name', 'project_reference', 'location', 'donor', 'service_date',
            'client_representative_name', 'client_phone_number',
            'issue_description', 'work_performed', 'parts_used', 'status',
            'follow_up_required', 'service_type', 'billing_category', 'final_status'
        ]
        widgets = {
            'maintenance_request': forms.Select(attrs={'class': 'form-control'}),
            'service_date': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'issue_description': forms.Textarea(attrs={'rows': 3}),
            'work_performed': forms.Textarea(attrs={'rows': 3}),
            'parts_used': forms.Textarea(attrs={'rows': 2}),
            # client_signature widget is defined in field above
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter maintenance requests to show only open/active ones
        self.fields['maintenance_request'].queryset = MaintenanceRequest.objects.exclude(status__in=['Completed', 'Cancelled']).order_by('-created_at')
        
        if self.instance.pk:
            if self.instance.service_type:
                self.fields['service_type'].initial = [x.strip() for x in self.instance.service_type.split(',')]
            if self.instance.billing_category:
                self.fields['billing_category'].initial = [x.strip() for x in self.instance.billing_category.split(',')]
            if self.instance.final_status:
                self.fields['final_status'].initial = [x.strip() for x in self.instance.final_status.split(',')]

    def clean_service_type(self):
        data = self.cleaned_data.get('service_type')
        if isinstance(data, list):
            return ', '.join(data)
        return data or ''

    def clean_billing_category(self):
        data = self.cleaned_data.get('billing_category')
        if isinstance(data, list):
            return ', '.join(data)
        return data or ''
        
    def clean_final_status(self):
        data = self.cleaned_data.get('final_status')
        if isinstance(data, list):
            return ', '.join(data)
        return data or ''

    def clean(self):
        cleaned_data = super().clean()
        status = cleaned_data.get('status')
        
        if status == 'Completed':
            required_fields = [
                'client_name', 'location', 'service_date', 
                'issue_description', 'work_performed', 
                'client_representative_name'
            ]
            for field in required_fields:
                if not cleaned_data.get(field):
                    self.add_error(field, "This field is required when marking as Completed.")
        
        return cleaned_data

class ReportItemForm(forms.ModelForm):
    class Meta:
        model = ReportItem
        fields = ['product', 'serial_number', 'equipment_note']
        widgets = {
            'product': forms.Select(attrs={'class': 'form-control product-select'}),
            'serial_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Serial Number'}),
            'equipment_note': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Specific note for this equipment'}),
        }

class BaseReportItemFormSet(forms.BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return
        
        items = []
        for form in self.forms:
            if self.can_delete and self._should_delete_form(form):
                continue
            
            product = form.cleaned_data.get('product')
            sn = form.cleaned_data.get('serial_number')
            
            if product:
                item_key = (product.id, sn)
                if item_key in items:
                    raise forms.ValidationError(
                        f"Duplicate entry: {product.name} with serial number '{sn or 'N/A'}' is already added."
                    )
                items.append(item_key)

ReportItemFormSet = inlineformset_factory(
    ServiceReport, ReportItem, form=ReportItemForm,
    formset=BaseReportItemFormSet,
    extra=1, can_delete=True
)

class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = '__all__'
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 3}),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        manufacturer = cleaned_data.get('manufacturer')
        model = cleaned_data.get('model')
        
        if manufacturer and model:
            # Check if this combination already exists (excluding current instance if editing)
            existing = Product.objects.filter(manufacturer=manufacturer, model=model)
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            
            if existing.exists():
                raise forms.ValidationError(
                    f'A product with manufacturer "{manufacturer}" and model "{model}" already exists. '
                    f'Please use a different manufacturer or model number.'
                )
        
        return cleaned_data
