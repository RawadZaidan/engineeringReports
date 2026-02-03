import base64
from django.core.files.base import ContentFile
from django.shortcuts import redirect, get_object_or_404
from django.views.generic import ListView, CreateView, UpdateView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy
from django.db.models import Q, Count
from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from datetime import timedelta
from django.utils import timezone
from django.core.cache import cache

from .models import ServiceReport, Product, Equipment, ReportItem, ReportImage, MaintenanceRequest, MaintenanceRequestEquipment, Driver, DriverRequest
from .forms import (
    ServiceReportForm, ProductForm, EquipmentForm, ReportItemFormSet, 
    MaintenanceRequestForm, MaintenanceRequestEquipmentFormSet, DriverRequestForm
)

class DashboardView(LoginRequiredMixin, ListView):
    model = ServiceReport
    template_name = 'core/dashboard.html'
    context_object_name = 'reports'
    paginate_by = 20

    def get_queryset(self):
        # Optimize: prefetch related data to avoid N+1 queries in template
        queryset = super().get_queryset().select_related(
            'engineer'
        ).prefetch_related(
            'items__equipment__product',
            'images'
        ).order_by('-created_at')
        
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
        
        # Try to get stats from cache first
        stats = cache.get('dashboard_stats')
        
        if not stats:
            now = timezone.now()
            week_ago = now - timedelta(days=7)
            month_ago = now - timedelta(days=30)
            
            # Optimize: Use aggregation to get all stats in ONE query instead of 7
            report_stats = ServiceReport.objects.aggregate(
                total=Count('id'),
                this_week=Count('id', filter=Q(created_at__gte=week_ago)),
                this_month=Count('id', filter=Q(created_at__gte=month_ago)),
                draft=Count('id', filter=Q(status='Draft')),
                pending=Count('id', filter=Q(status='Pending')),
                completed=Count('id', filter=Q(status='Completed')),
                follow_ups=Count('id', filter=Q(follow_up_required=True, status__in=['Completed', 'Pending'])),
            )
            
            # Optimize: Get maintenance request stats in ONE query
            request_stats = MaintenanceRequest.objects.aggregate(
                open_count=Count('id', filter=Q(status='Open')),
                urgent_count=Count('id', filter=Q(urgency='Emergency', status__in=['Open', 'Scheduled'])),
            )
            
            stats = {
                'total_reports': report_stats['total'],
                'reports_this_week': report_stats['this_week'],
                'reports_this_month': report_stats['this_month'],
                'draft_count': report_stats['draft'],
                'pending_count': report_stats['pending'],
                'completed_count': report_stats['completed'],
                'follow_ups_needed': report_stats['follow_ups'],
                'open_requests': request_stats['open_count'],
                'urgent_requests': request_stats['urgent_count'],
                'top_equipment': list(
                    ReportItem.objects.values('equipment__product__name')
                    .annotate(count=Count('id')).order_by('-count')[:5]
                )
            }
            # Cache for 10 minutes
            cache.set('dashboard_stats', stats, 600)
            
        context.update(stats)
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

@login_required
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

@login_required
@require_POST
def equipment_create_ajax(request):
    form = EquipmentForm(request.POST)
    if form.is_valid():
        obj = form.save()
        return JsonResponse({'success': True, 'id': obj.id, 'name': str(obj)})
    return JsonResponse({'success': False, 'message': 'Invalid data or duplicate serial number'}, status=400)

# --- SERVICE REPORTS ---

class ServiceReportCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = ServiceReport
    form_class = ServiceReportForm
    template_name = 'core/report_form.html'
    success_url = reverse_lazy('dashboard')

    def test_func(self):
        return self.request.user.groups.filter(name='Engineer').exists()

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
            data['items'] = ReportItemFormSet(self.request.POST, prefix='items')
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
            
            data['items'] = ReportItemFormSet(initial=initial_items, prefix='items')
            data['items'].extra = len(initial_items)
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

class ServiceReportUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = ServiceReport
    form_class = ServiceReportForm
    template_name = 'core/report_form.html'
    success_url = reverse_lazy('dashboard')

    def test_func(self):
        return self.request.user.groups.filter(name='Engineer').exists()

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        data['equipments'] = Equipment.objects.all()
        data['products'] = Product.objects.all()
        if self.request.POST:
            data['items'] = ReportItemFormSet(self.request.POST, instance=self.object, prefix='items')
        else:
            data['items'] = ReportItemFormSet(instance=self.object, prefix='items')
            data['items'].extra = 0
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

    def get_queryset(self):
        # Optimize: prefetch all related data for detail view
        return super().get_queryset().select_related(
            'engineer', 'maintenance_request'
        ).prefetch_related(
            'items__equipment__product',
            'images'
        )

# --- MAINTENANCE REQUESTS ---

class MaintenanceRequestListView(LoginRequiredMixin, ListView):
    model = MaintenanceRequest
    template_name = 'core/request_list.html'
    context_object_name = 'requests'
    paginate_by = 20

    def get_queryset(self):
        # Optimize: prefetch related equipment data
        queryset = super().get_queryset().select_related(
            'created_by'
        ).prefetch_related(
            'equipment_items__equipment__product'
        ).order_by('-created_at')
        
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
        
        data['is_engineer'] = self.request.user.groups.filter(name='Engineer').exists()
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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['is_engineer'] = self.request.user.groups.filter(name='Engineer').exists()
        return context

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
        
        data['is_engineer'] = self.request.user.groups.filter(name='Engineer').exists()
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

@require_POST
def update_pricing_ajax(request):
    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=403)
    
    # Check if user is Engineer
    if not request.user.groups.filter(name='Engineer').exists():
        return JsonResponse({'success': False, 'message': 'Only Engineers can update pricing.'}, status=403)

    request_id = request.POST.get('request_id')
    price = request.POST.get('price')

    if not request_id or not price:
        return JsonResponse({'success': False, 'message': 'Missing data'}, status=400)

    try:
        mr = MaintenanceRequest.objects.get(pk=request_id)
        # Optional: Check logic if needed (e.g. only Billable requests)
        mr.estimated_cost = float(price)
        mr.pricing_set_by = request.user
        mr.pricing_set_at = timezone.now()
        mr.save()
        
        return JsonResponse({
            'success': True, 
            'formatted_price': f"${mr.estimated_cost:.2f}",
            'updated_by': request.user.get_full_name() or request.user.username,
            'updated_at': mr.pricing_set_at.strftime("%b %d, %Y, %I:%M %p")
        })
    except MaintenanceRequest.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Request not found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

# --- DRIVER SCHEDULING ---

class DriverSchedulingView(LoginRequiredMixin, ListView):
    model = DriverRequest
    template_name = 'core/driver_scheduling.html'
    context_object_name = 'requests'

    def get_queryset(self):
        queryset = super().get_queryset()
        selected_date = self.request.GET.get('date')
        if selected_date:
            try:
                queryset = queryset.filter(date=selected_date)
            except (ValueError, TypeError):
                pass
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        import calendar
        from datetime import date, timedelta
        
        today = date.today()
        year = int(self.request.GET.get('year', today.year))
        month = int(self.request.GET.get('month', today.month))
        
        cal = calendar.Calendar(firstweekday=0)
        month_days_raw = cal.monthdayscalendar(year, month)
        
        # Build structured calendar data with ISO dates
        calendar_weeks = []
        for week in month_days_raw:
            week_data = []
            for day in week:
                if day == 0:
                    week_data.append({'day': 0, 'iso': None})
                else:
                    iso_str = f"{year}-{month:02d}-{day:02d}"
                    week_data.append({
                        'day': day,
                        'iso': iso_str,
                        'is_today': today.year == year and today.month == month and today.day == day
                    })
            calendar_weeks.append(week_data)
        
        # Get days that have shifts
        shift_days = DriverRequest.objects.filter(
            date__year=year, 
            date__month=month
        ).values_list('date__day', flat=True).distinct()
        
        context.update({
            'drivers': Driver.objects.filter(is_active=True),
            'is_admin': self.request.user.is_staff,
            'calendar_weeks': calendar_weeks,
            'shift_days': list(shift_days),
            'current_month': month,
            'current_year': year,
            'month_name': calendar.month_name[month],
            'selected_date': self.request.GET.get('date'),
        })
        return context

class DriverRequestCreateView(LoginRequiredMixin, CreateView):
    model = DriverRequest
    form_class = DriverRequestForm
    template_name = 'core/driver_request_form.html'
    success_url = reverse_lazy('driver_scheduling')

    def form_valid(self, form):
        form.instance.requester = self.request.user
        return super().form_valid(form)

class DriverRequestUpdateView(LoginRequiredMixin, UpdateView):
    model = DriverRequest
    form_class = DriverRequestForm
    template_name = 'core/driver_request_form.html'
    success_url = reverse_lazy('driver_scheduling')

    def get_queryset(self):
        # Users can edit their own, staff can edit any
        if self.request.user.is_staff:
            return DriverRequest.objects.all()
        return DriverRequest.objects.filter(requester=self.request.user)

    def form_valid(self, form):
        # If a non-staff user edits, revert to pending for re-approval
        if not self.request.user.is_staff:
            form.instance.status = 'Pending'
        return super().form_valid(form)

@require_POST
def driver_request_action(request, pk):
    if not request.user.is_staff:
        return JsonResponse({'success': False, 'message': 'Permission denied.'}, status=403)
    
    driver_request = get_object_or_404(DriverRequest, pk=pk)
    action = request.POST.get('action')
    notes = request.POST.get('notes', '')

    if action == 'approve':
        driver_request.status = 'Approved'
    elif action == 'deny':
        driver_request.status = 'Denied'
    elif action == 'request_edit':
        driver_request.status = 'Edit Requested'
    elif action == 'cancel':
        # Requesters can cancel their own, or admin can cancel any
        if not request.user.is_staff and driver_request.requester != request.user:
            return JsonResponse({'success': False, 'message': 'Permission denied.'}, status=403)
        driver_request.status = 'Cancelled'
    
    driver_request.admin_notes = notes
    driver_request.save()
    
    return JsonResponse({'success': True})
