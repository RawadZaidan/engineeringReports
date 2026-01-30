import base64
from django.core.files.base import ContentFile
from django.shortcuts import render, redirect
from django.views.generic import ListView, CreateView, UpdateView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy
from django.db.models import Q, Count
from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from datetime import datetime, timedelta
from django.utils import timezone

from .models import ServiceReport, Product, Equipment, ReportItem, ReportImage, MaintenanceRequest, MaintenanceRequestEquipment
from .forms import (
    ServiceReportForm, ProductForm, EquipmentForm, ReportItemFormSet, 
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
                Q(items__equipment__product__name__icontains=search_query) |
                Q(items__equipment__serial_number__icontains=search_query)
            ).distinct()
        
        if status_filter:
            queryset = queryset.filter(status=status_filter)
            
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        now = timezone.now()
        week_ago = now - timedelta(days=7)
        month_ago = now - timedelta(days=30)
        
        context.update({
            'total_reports': ServiceReport.objects.count(),
            'reports_this_week': ServiceReport.objects.filter(created_at__gte=week_ago).count(),
            'reports_this_month': ServiceReport.objects.filter(created_at__gte=month_ago).count(),
            'draft_count': ServiceReport.objects.filter(status='Draft').count(),
            'pending_count': ServiceReport.objects.filter(status='Pending').count(),
            'completed_count': ServiceReport.objects.filter(status='Completed').count(),
            'follow_ups_needed': ServiceReport.objects.filter(follow_up_required=True, status__in=['Completed', 'Pending']).count(),
            'open_requests': MaintenanceRequest.objects.filter(status='Open').count(),
            'urgent_requests': MaintenanceRequest.objects.filter(urgency='Emergency', status__in=['Open', 'Scheduled']).count(),
            'top_equipment': (
                ReportItem.objects.values('equipment__product__name')
                .annotate(count=Count('id')).order_by('-count')[:5]
            )
        })
        return context

# --- PRODUCT CATALOGUE & EQUIPMENT REGISTRY ---

class ProductListView(LoginRequiredMixin, ListView):
    model = Product
    template_name = 'core/product_list.html'
    context_object_name = 'products'

class ProductCreateView(LoginRequiredMixin, CreateView):
    model = Product
    form_class = ProductForm
    template_name = 'core/product_form.html'
    success_url = reverse_lazy('product_list')

@require_POST
def product_create_ajax(request):
    form = ProductForm(request.POST)
    if form.is_valid():
        obj = form.save()
        return JsonResponse({'success': True, 'id': obj.id, 'name': str(obj)})
    return JsonResponse({'success': False, 'message': 'Invalid data'}, status=400)

class EquipmentListView(LoginRequiredMixin, ListView):
    model = Equipment
    template_name = 'core/equipment_list.html'
    context_object_name = 'equipments'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.now().date()
        context['today'] = today
        # Under Warranty items
        context['under_warranty'] = Equipment.objects.filter(
            warranty_expiration_date__gte=today
        ).order_by('warranty_expiration_date')
        return context

@require_POST
def equipment_create_ajax(request):
    form = EquipmentForm(request.POST)
    if form.is_valid():
        obj = form.save()
        return JsonResponse({'success': True, 'id': obj.id, 'name': str(obj)})
    return JsonResponse({'success': False, 'message': 'Invalid data or duplicate serial number'}, status=400)

# --- SERVICE REPORTS ---

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
                mr = MaintenanceRequest.objects.get(pk=request_id)
                initial.update({
                    'maintenance_request': mr,
                    'client_name': mr.facility_name,
                    'location': mr.get_location_display(),
                    'donor': mr.donor,
                    'service_type': [x.strip() for x in mr.service_type.split(',')] if mr.service_type else [],
                    'issue_description': mr.request_details,
                    'client_representative_name': mr.contact_name,
                    'client_phone_number': mr.contact_number,
                })
            except MaintenanceRequest.DoesNotExist: pass
        return initial

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        data['equipments'] = Equipment.objects.all()
        data['products'] = Product.objects.all()
        if self.request.POST:
            data['items'] = ReportItemFormSet(self.request.POST)
        else:
            request_id = self.request.GET.get('request_id')
            initial_items = []
            if request_id:
                try:
                    mr = MaintenanceRequest.objects.get(pk=request_id)
                    for eq in mr.equipment_items.all():
                        if eq.equipment:
                            initial_items.append({'equipment': eq.equipment})
                except MaintenanceRequest.DoesNotExist: pass
            
            data['items'] = ReportItemFormSet(initial=initial_items)
            data['items'].extra = max(1, len(initial_items))
        return data

    def form_valid(self, form):
        context = self.get_context_data()
        items = context['items']
        if form.is_valid() and items.is_valid():
            with transaction.atomic():
                self.object = form.save(commit=False)
                self.object.engineer = self.request.user
                
                sig_data = form.cleaned_data.get('client_signature')
                if sig_data and hasattr(sig_data, 'startswith') and sig_data.startswith('data:image'):
                    fmt, imgstr = sig_data.split(';base64,') 
                    ext = fmt.split('/')[-1] 
                    self.object.client_signature = ContentFile(base64.b64decode(imgstr), name=f"sig_{self.object.id}.{ext}")
                
                self.object.service_type = form.cleaned_data.get('service_type', '')
                self.object.billing_category = form.cleaned_data.get('billing_category', '')
                self.object.final_status = form.cleaned_data.get('final_status', '')
                self.object.save()
                items.instance = self.object
                items.save()
                
                for image in self.request.FILES.getlist('images'):
                    ReportImage.objects.create(report=self.object, image=image)

                # Update Equipment Warranty if requested
                if self.object.warranty_start_on_submission and self.object.warranty_duration_years:
                    start_date = self.object.service_date or timezone.now()
                    try:
                        expiration_date = start_date.replace(year=start_date.year + self.object.warranty_duration_years)
                    except ValueError:
                        expiration_date = start_date + timedelta(days=self.object.warranty_duration_years * 365 + (self.object.warranty_duration_years // 4))
                    
                    for item in self.object.items.all():
                        if item.equipment:
                            item.equipment.warranty_expiration_date = expiration_date.date()
                            item.equipment.save()
            return redirect(self.success_url)
        return self.render_to_response(self.get_context_data(form=form))

class ServiceReportUpdateView(LoginRequiredMixin, UpdateView):
    model = ServiceReport
    form_class = ServiceReportForm
    template_name = 'core/report_form.html'
    success_url = reverse_lazy('dashboard')

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        data['equipments'] = Equipment.objects.all()
        data['products'] = Product.objects.all()
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
                sig_data = form.cleaned_data.get('client_signature')
                if sig_data and hasattr(sig_data, 'startswith') and sig_data.startswith('data:image'):
                    fmt, imgstr = sig_data.split(';base64,') 
                    data = ContentFile(base64.b64decode(imgstr), name=f"sig_{self.object.id}.png")
                    self.object.client_signature = data
                
                self.object.service_type = form.cleaned_data.get('service_type', '')
                self.object.billing_category = form.cleaned_data.get('billing_category', '')
                self.object.final_status = form.cleaned_data.get('final_status', '')
                self.object.save()
                items.instance = self.object
                items.save()
                for image in self.request.FILES.getlist('images'):
                    ReportImage.objects.create(report=self.object, image=image)

                # Update Equipment Warranty if requested
                if self.object.warranty_start_on_submission and self.object.warranty_duration_years:
                    start_date = self.object.service_date or timezone.now()
                    try:
                        expiration_date = start_date.replace(year=start_date.year + self.object.warranty_duration_years)
                    except ValueError:
                        expiration_date = start_date + timedelta(days=self.object.warranty_duration_years * 365 + (self.object.warranty_duration_years // 4))
                    
                    for item in self.object.items.all():
                        if item.equipment:
                            item.equipment.warranty_expiration_date = expiration_date.date()
                            item.equipment.save()
            return redirect(self.success_url)
        return self.render_to_response(self.get_context_data(form=form))

class ServiceReportDetailView(LoginRequiredMixin, DetailView):
    model = ServiceReport
    template_name = 'core/report_detail.html'
    context_object_name = 'report'

# --- MAINTENANCE REQUESTS ---

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
        if status: queryset = queryset.filter(status=status)
        q = self.request.GET.get('q')
        if q:
            queryset = queryset.filter(
                Q(facility_name__icontains=q) | Q(location__icontains=q) |
                Q(equipment_items__equipment__product__name__icontains=q) |
                Q(equipment_items__equipment__serial_number__icontains=q)
            ).distinct()
        return queryset

class MaintenanceRequestCreateView(LoginRequiredMixin, CreateView):
    model = MaintenanceRequest
    form_class = MaintenanceRequestForm
    template_name = 'core/request_form.html'
    success_url = reverse_lazy('request_list')

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        data['products'] = Product.objects.all()
        data['equipments'] = Equipment.objects.all()
        if self.request.POST:
            data['equipment_formset'] = MaintenanceRequestEquipmentFormSet(self.request.POST)
        else:
            data['equipment_formset'] = MaintenanceRequestEquipmentFormSet()
        return data

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs(); kwargs['user'] = self.request.user
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
        kwargs = super().get_form_kwargs(); kwargs['user'] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        data['products'] = Product.objects.all()
        data['equipments'] = Equipment.objects.all()
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
