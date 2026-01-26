import base64
from django.core.files.base import ContentFile
from django.shortcuts import render, redirect
from django.views.generic import ListView, CreateView, UpdateView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy
from django.db.models import Q
from .models import ServiceReport, Product, ReportImage, MaintenanceRequest, MaintenanceRequestEquipment
from django.db import transaction
from .forms import (
    ServiceReportForm, ProductForm, ReportItemFormSet, 
    MaintenanceRequestForm, MaintenanceRequestEquipmentFormSet
)

class DashboardView(LoginRequiredMixin, ListView):
    model = ServiceReport
    template_name = 'core/dashboard.html'
    context_object_name = 'reports'
    paginate_by = 20

    def get_queryset(self):
        queryset = super().get_queryset().order_by('-created_at')
        search_query = self.request.GET.get('q')
        status_filter = self.request.GET.get('status')
        
        if search_query:
            queryset = queryset.filter(
                Q(client_name__icontains=search_query) |
                Q(location__icontains=search_query) |
                Q(items__product__name__icontains=search_query)
            ).distinct()
        
        if status_filter:
            queryset = queryset.filter(status=status_filter)
            
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from django.db.models import Count
        from datetime import datetime, timedelta
        
        # Get date ranges
        today = datetime.now().date()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)
        
        # Total counts
        context['total_reports'] = ServiceReport.objects.count()
        context['reports_this_week'] = ServiceReport.objects.filter(created_at__gte=week_ago).count()
        context['reports_this_month'] = ServiceReport.objects.filter(created_at__gte=month_ago).count()
        
        # Status breakdown
        context['draft_count'] = ServiceReport.objects.filter(status='Draft').count()
        context['pending_count'] = ServiceReport.objects.filter(status='Pending').count()
        context['completed_count'] = ServiceReport.objects.filter(status='Completed').count()
        
        # Follow-ups
        context['follow_ups_needed'] = ServiceReport.objects.filter(follow_up_required=True, status__in=['Completed', 'Pending']).count()
        
        # Maintenance requests
        context['open_requests'] = MaintenanceRequest.objects.filter(status='Open').count()
        context['urgent_requests'] = MaintenanceRequest.objects.filter(urgency='Emergency', status__in=['Open', 'Scheduled']).count()
        
        # Most serviced equipment (top 5)
        from .models import ReportItem
        context['top_equipment'] = (
            ReportItem.objects
            .values('product__name')
            .annotate(count=Count('id'))
            .order_by('-count')[:5]
        )
        
        return context

class ServiceReportCreateView(LoginRequiredMixin, CreateView):
    model = ServiceReport
    form_class = ServiceReportForm
    template_name = 'core/report_form.html'
    success_url = reverse_lazy('dashboard')

    def get_initial(self):
        initial = super().get_initial()
        request_id = self.request.GET.get('request_id')
        if request_id:
            try:
                maintenance_request = MaintenanceRequest.objects.get(pk=request_id)
                initial['maintenance_request'] = maintenance_request
                initial['client_name'] = maintenance_request.facility_name
                initial['location'] = maintenance_request.get_location_display()
                initial['donor'] = maintenance_request.donor
                initial['issue_description'] = maintenance_request.request_details
            except MaintenanceRequest.DoesNotExist:
                pass
        return initial

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        if self.request.POST:
            data['items'] = ReportItemFormSet(self.request.POST)
        else:
            data['items'] = ReportItemFormSet()
        return data

    def form_valid(self, form):
        context = self.get_context_data()
        items = context['items']
        
        if form.is_valid() and items.is_valid():
            with transaction.atomic():
                self.object = form.save(commit=False)
                self.object.engineer = self.request.user
                
                # Handle Signature Base64
                signature_data = form.cleaned_data.get('client_signature')
                if signature_data and hasattr(signature_data, 'startswith') and signature_data.startswith('data:image'):
                    format, imgstr = signature_data.split(';base64,') 
                    ext = format.split('/')[-1] 
                    data = ContentFile(base64.b64decode(imgstr), name=f'signature_{self.object.client_name}_{self.object.service_date}.{ext}')
                    self.object.client_signature = data
                
                # Manually sync categorical fields
                self.object.service_type = form.cleaned_data.get('service_type', '')
                self.object.billing_category = form.cleaned_data.get('billing_category', '')
                self.object.final_status = form.cleaned_data.get('final_status', '')
                
                self.object.save()
                
                items.instance = self.object
                items.save()
                
                # Handle Images
                images = self.request.FILES.getlist('images')
                for image in images:
                    ReportImage.objects.create(report=self.object, image=image)
                    
            return redirect(self.success_url)
        else:
            return self.render_to_response(self.get_context_data(form=form))

class ServiceReportUpdateView(LoginRequiredMixin, UpdateView):
    model = ServiceReport
    form_class = ServiceReportForm
    template_name = 'core/report_form.html'
    success_url = reverse_lazy('dashboard')

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        if self.request.POST:
            data['items'] = ReportItemFormSet(self.request.POST, instance=self.object)
        else:
            data['items'] = ReportItemFormSet(instance=self.object)
        return data

    def form_valid(self, form):
        context = self.get_context_data()
        items = context['items']
        
        if form.is_valid() and items.is_valid():
            with transaction.atomic():
                self.object = form.save(commit=False)
                
                # Handle Signature Base64 (Only if changed/new)
                signature_data = form.cleaned_data.get('client_signature')
                if signature_data and hasattr(signature_data, 'startswith') and signature_data.startswith('data:image'):
                    format, imgstr = signature_data.split(';base64,') 
                    ext = format.split('/')[-1] 
                    data = ContentFile(base64.b64decode(imgstr), name=f'signature_{self.object.client_name}_{self.object.service_date}.{ext}')
                    self.object.client_signature = data
                
                # Manually sync categorical fields
                self.object.service_type = form.cleaned_data.get('service_type', '')
                self.object.billing_category = form.cleaned_data.get('billing_category', '')
                self.object.final_status = form.cleaned_data.get('final_status', '')
                
                self.object.save()
                items.instance = self.object
                items.save()
                
                images = self.request.FILES.getlist('images')
                for image in images:
                    ReportImage.objects.create(report=self.object, image=image)
                    
            return redirect(self.success_url)
        else:
            return self.render_to_response(self.get_context_data(form=form))

class ServiceReportDetailView(LoginRequiredMixin, DetailView):
    model = ServiceReport
    template_name = 'core/report_detail.html'
    context_object_name = 'report'

class ProductListView(LoginRequiredMixin, ListView):
    model = Product
    template_name = 'core/product_list.html'
    context_object_name = 'products'

from django.http import JsonResponse
from django.views.decorators.http import require_POST

class ProductCreateView(LoginRequiredMixin, CreateView):
    model = Product
    form_class = ProductForm
    template_name = 'core/product_form.html'
    success_url = reverse_lazy('product_list')

@require_POST
def product_create_ajax(request):
    form = ProductForm(request.POST)
    if form.is_valid():
        product = form.save()
        return JsonResponse({
            'success': True,
            'id': product.id,
            'name': str(product)
        })
    
    # Extract error messages
    error_messages = []
    if form.non_field_errors():
        error_messages.extend(form.non_field_errors())
    for field, errors in form.errors.items():
        if field != '__all__':
            error_messages.append(f"{field}: {', '.join(errors)}")
    
    return JsonResponse({
        'success': False,
        'errors': form.errors,
        'message': ' '.join(error_messages) if error_messages else 'Please correct the errors below.'
    }, status=400)
# Maintenance Request Views
class MaintenanceRequestListView(LoginRequiredMixin, ListView):
    model = MaintenanceRequest
    template_name = 'core/request_list.html'
    context_object_name = 'requests'
    paginate_by = 20

    def get_queryset(self):
        queryset = super().get_queryset().order_by('-created_at')
        if not self.request.user.is_staff:
            queryset = queryset.filter(created_by=self.request.user)
            
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
            
        q = self.request.GET.get('q')
        if q:
            queryset = queryset.filter(
                Q(facility_name__icontains=q) | 
                Q(location__icontains=q) |
                Q(equipment_list__icontains=q) |
                Q(equipment_items__equipment_type__icontains=q) |
                Q(equipment_items__model_name__icontains=q)
            ).distinct()
        return queryset

class MaintenanceRequestCreateView(LoginRequiredMixin, CreateView):
    model = MaintenanceRequest
    form_class = MaintenanceRequestForm
    template_name = 'core/request_form.html'
    success_url = reverse_lazy('request_list')

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        if self.request.POST:
            data['equipment_formset'] = MaintenanceRequestEquipmentFormSet(self.request.POST)
        else:
            data['equipment_formset'] = MaintenanceRequestEquipmentFormSet()
        return data

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        context = self.get_context_data()
        equipment_formset = context['equipment_formset']
        if form.is_valid() and equipment_formset.is_valid():
            with transaction.atomic():
                form.instance.created_by = self.request.user
                self.object = form.save()
                equipment_formset.instance = self.object
                equipment_formset.save()
            return redirect(self.success_url)
        return self.render_to_response(self.get_context_data(form=form))

class MaintenanceRequestDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    model = MaintenanceRequest
    template_name = 'core/request_detail.html'
    context_object_name = 'request'

    def test_func(self):
        obj = self.get_object()
        return self.request.user.is_staff or obj.created_by == self.request.user

class MaintenanceRequestUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = MaintenanceRequest
    form_class = MaintenanceRequestForm
    template_name = 'core/request_form.html'
    success_url = reverse_lazy('request_list')

    def test_func(self):
        obj = self.get_object()
        return self.request.user.is_staff or obj.created_by == self.request.user

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        if self.request.POST:
            data['equipment_formset'] = MaintenanceRequestEquipmentFormSet(self.request.POST, instance=self.object)
        else:
            data['equipment_formset'] = MaintenanceRequestEquipmentFormSet(instance=self.object)
        return data

    def form_valid(self, form):
        context = self.get_context_data()
        equipment_formset = context['equipment_formset']
        if form.is_valid() and equipment_formset.is_valid():
            with transaction.atomic():
                self.object = form.save()
                equipment_formset.instance = self.object
                equipment_formset.save()
            return redirect(self.success_url)
        return self.render_to_response(self.get_context_data(form=form))
