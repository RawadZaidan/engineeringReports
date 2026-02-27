import base64
import json
import datetime
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

from .models import ServiceReport, Product, Equipment, ReportItem, ReportImage, MaintenanceRequest, MaintenanceRequestEquipment, Driver, DriverRequest, Engineer, MaintenanceAssignment
from .forms import (
    ServiceReportForm, ProductForm, EquipmentForm, ReportItemFormSet, 
    MaintenanceRequestForm, MaintenanceRequestEquipmentFormSet, DriverRequestForm,
    MaintenanceAssignmentForm
)

from django.views.generic import TemplateView

class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'core/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Read is_engineer from session — the is_engineer context processor already
        # populated it (and cached it in the session) so we NEVER need a DB query here.
        is_engineer = self.request.session.get('is_engineer', False)
        engineer_profile = None
        if is_engineer:
            try:
                engineer_profile = user.engineer_profile
            except Engineer.DoesNotExist:
                pass
        
        import calendar
        from datetime import date
        today = timezone.now().date()
        
        # Cache key matching what notification_counts processor uses so we can
        # reuse its cached open_maintenance_count without a second DB hit.
        notif_cache_key = f'notification_counts_{user.id}'
        
        # Per-user stats cache key (was previously broken: invalidated under
        # 'dashboard_stats' but cached under 'dashboard_stats_{user.id}_{is_engineer}')
        stats_cache_key = f'dashboard_stats_{user.id}'
        cached_stats = cache.get(stats_cache_key)
        
        if cached_stats:
            context['stats'] = cached_stats
        else:
            visit_week_filter = Q(date__range=[today, today + timedelta(days=7)])
            if is_engineer and engineer_profile:
                visit_week_filter &= Q(engineer=engineer_profile)
            
            my_pending_count = ServiceReport.objects.filter(
                engineer=user, 
                status__in=['Draft', 'Pending']
            ).count()
            
            # Reuse notification_counts cache to avoid double-querying open requests.
            # If cache is cold we fall back to a fresh query.
            cached_notif = cache.get(notif_cache_key)
            if cached_notif:
                open_requests_count = cached_notif['open_maintenance_count']
            else:
                open_requests_count = MaintenanceRequest.objects.filter(status='Open').count()
            
            visits_this_week_count = MaintenanceAssignment.objects.filter(
                visit_week_filter
            ).count()
            
            context['stats'] = {
                'my_pending': my_pending_count,
                'open_requests': open_requests_count,
                'visits_this_week': visits_this_week_count
            }
            
            # Cache for 5 minutes
            cache.set(stats_cache_key, context['stats'], 300)
        
        # Use only() to fetch only needed fields for pending reports
        context['my_pending_reports'] = ServiceReport.objects.filter(
            engineer=user,
            status__in=['Draft', 'Pending']
        ).select_related('engineer').only(
            'id', 'client_name', 'status', 'updated_at', 'location', 
            'project_reference', 'created_at', 'service_type', 
            'engineer__username', 'engineer__first_name', 'engineer__last_name'
        ).order_by('-updated_at')[:5]

        # select_related prevents N+1 queries on created_by
        context['recent_requests'] = MaintenanceRequest.objects.filter(
            status__in=['Open', 'Scheduled', 'In Progress']
        ).select_related('created_by').only(
            'id', 'facility_name', 'status', 'urgency', 'created_at', 
            'location', 'request_details', 'contact_name', 
            'created_by__username', 'created_by__first_name', 'created_by__last_name'
        ).order_by('-urgency', '-created_at')[:10]

        context['awaiting_response'] = ServiceReport.objects.filter(
            follow_up_required=True,
            status__in=['Completed', 'Pending']
        ).only(
            'id', 'client_name', 'status', 'updated_at'
        ).order_by('-updated_at')[:5]

        # Fetch 3 most recent reports for the dashboard section
        context['recent_reports'] = ServiceReport.objects.select_related('maintenance_request').only(
            'id', 'client_name', 'status', 'created_at', 'maintenance_request__id'
        ).order_by('-created_at')[:3]

        # Calendar data
        year = int(self.request.GET.get('year', today.year))
        month = int(self.request.GET.get('month', today.month))
        
        cal = calendar.Calendar(firstweekday=0)
        month_days_raw = cal.monthdayscalendar(year, month)
        
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
        
        # Get days that have assignments for this month
        assignment_filter = Q(date__year=year, date__month=month)
        if is_engineer and engineer_profile:
            assignment_filter &= Q(engineer=engineer_profile)

        visit_days = MaintenanceAssignment.objects.filter(
            assignment_filter
        ).values_list('date__day', flat=True).distinct()

        # Get upcoming visits detail list for the side panel
        selected_date = self.request.GET.get('date')
        
        visits_query = MaintenanceAssignment.objects.select_related(
            'maintenance_request', 'engineer'
        ).only(
            'id', 'date', 'start_time', 'end_time', 'notes',
            'maintenance_request__id', 'maintenance_request__facility_name',
            'maintenance_request__location', 'engineer__name'
        )
        
        if is_engineer and engineer_profile:
            visits_query = visits_query.filter(engineer=engineer_profile)

        if selected_date:
             visits_list = visits_query.filter(date=selected_date)
        else:
             visits_list = visits_query.filter(date__gte=today).order_by('date', 'start_time')[:5]

        context.update({
            'calendar_weeks': calendar_weeks,
            'visit_days': list(visit_days),
            'current_month': month,
            'current_year': year,
            'month_name': calendar.month_name[month],
            'today_month': today.month,
            'today_year': today.year,
            'selected_date': selected_date,
            'upcoming_visits': visits_list,
            'is_engineer': is_engineer
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
    paginate_by = 10

    def get_queryset(self):
        queryset = Equipment.objects.select_related('product').annotate(
            report_count=Count('service_history')
        )
        
        # Filter by Search (Name or Serial)
        query = self.request.GET.get('q')
        if query:
            queryset = queryset.filter(
                Q(product__name__icontains=query) | 
                Q(serial_number__icontains=query) |
                Q(product__model__icontains=query)
            )
            
        # Filter by Location
        location = self.request.GET.get('location')
        if location:
            queryset = queryset.filter(current_facility=location)
            
        # Filter by Warranty
        warranty = self.request.GET.get('warranty')
        today = timezone.now().date()
        if warranty == 'active':
            queryset = queryset.filter(warranty_expiration_date__gte=today)
        elif warranty == 'expired':
            queryset = queryset.filter(warranty_expiration_date__lt=today)
            
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.now().date()
        context['today'] = today
        
        # Get all unique locations for the filter dropdown
        context['locations'] = Equipment.objects.values_list('current_facility', flat=True).distinct().order_by('current_facility')
        
        # Pass current filter values to context
        context['current_q'] = self.request.GET.get('q', '')
        context['current_location'] = self.request.GET.get('location', '')
        context['current_warranty'] = self.request.GET.get('warranty', '')
        
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
        data['products'] = Product.objects.all()
        
        equipments_qs = Equipment.objects.select_related('product').all()
        list(equipments_qs)  # evaluate and cache
        data['equipments'] = equipments_qs
        form_kwargs = {'equipment_qs': equipments_qs}
        
        if self.request.POST:
            data['items'] = ReportItemFormSet(self.request.POST, prefix='items', form_kwargs=form_kwargs)
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
            
            data['items'] = ReportItemFormSet(initial=initial_items, prefix='items', form_kwargs=form_kwargs)
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
        obj = self.get_object()
        # Allow if Admin OR if the user is the engineer who created the report
        return self.request.user.is_staff or obj.engineer == self.request.user

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        data['products'] = Product.objects.all()
        
        equipments_qs = Equipment.objects.select_related('product').all()
        list(equipments_qs)  # evaluate
        data['equipments'] = equipments_qs
        form_kwargs = {'equipment_qs': equipments_qs}
        
        if self.request.POST:
            data['items'] = ReportItemFormSet(self.request.POST, instance=self.object, prefix='items', form_kwargs=form_kwargs)
        else:
            data['items'] = ReportItemFormSet(instance=self.object, prefix='items', form_kwargs=form_kwargs)
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

class ServiceReportListView(LoginRequiredMixin, ListView):
    model = ServiceReport
    template_name = 'core/report_list.html'
    context_object_name = 'reports'
    paginate_by = 20

    def get_queryset(self):
        queryset = super().get_queryset().select_related(
            'engineer', 'maintenance_request'
        ).prefetch_related(
            'items__equipment__product',
            'images'
        ).order_by('-created_at')
        
        # Search Filter
        search_query = self.request.GET.get('q')
        if search_query:
            queryset = queryset.filter(
                Q(client_name__icontains=search_query) |
                Q(location__icontains=search_query) |
                Q(project_reference__icontains=search_query) |
                Q(id__icontains=search_query)
            ).distinct()
        
        # Status Filter
        status_filter = self.request.GET.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
            
        # "For Me" Filter (Toggle)
        if self.request.GET.get('for_me'):
            # Filter reports assigned to the user (engineer) or created by the user
            queryset = queryset.filter(
                Q(engineer__user=self.request.user) |
                Q(engineer__user__isnull=True, engineer__name__icontains=self.request.user.first_name) # Fallback if no user link
            ).distinct()
            
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Pass status counts for filter UI
        context['status_counts'] = {
            'draft': ServiceReport.objects.filter(status='Draft').count(),
            'pending': ServiceReport.objects.filter(status='Pending').count(),
            'completed': ServiceReport.objects.filter(status='Completed').count(),
            'all': ServiceReport.objects.count()
        }
        return context

# --- MAINTENANCE REQUESTS ---

class MaintenanceRequestListView(LoginRequiredMixin, ListView):
    model = MaintenanceRequest
    template_name = 'core/request_list.html'
    context_object_name = 'requests'
    paginate_by = 20

    def get_queryset(self):
        # Optimize: prefetch only created_by user and limit selected columns to what the template actually uses
        queryset = super().get_queryset().select_related(
            'created_by'
        ).only(
            'id', 'status', 'urgency', 'facility_name', 'service_type', 
            'location', 'customer_contact_date', 'created_by__username', 
            'created_by__first_name', 'created_by__last_name'
        )
        
        # Filtering
        if not self.request.user.is_staff:
            queryset = queryset.filter(created_by=self.request.user)
        
        # "For Me" Filter (Toggle)
        if self.request.GET.get('for_me'):
            queryset = queryset.filter(
                Q(created_by=self.request.user) |
                Q(assignments__engineer__user=self.request.user)
            ).distinct()

        status = self.request.GET.get('status')
        if status: 
            queryset = queryset.filter(status=status)
            
        q = self.request.GET.get('q')
        if q:
            queryset = queryset.filter(
                Q(facility_name__icontains=q) | Q(location__icontains=q) |
                Q(equipment_items__equipment__product__name__icontains=q) |
                Q(equipment_items__equipment__serial_number__icontains=q)
            ).distinct()

        # Sorting
        sort = self.request.GET.get('sort', 'timeline')
        if sort == 'urgency':
            from django.db.models import Case, When, Value, IntegerField
            queryset = queryset.annotate(
                urgency_rank=Case(
                    When(urgency='Emergency', then=Value(0)),
                    When(urgency='High', then=Value(1)),
                    When(urgency='Medium', then=Value(2)),
                    When(urgency='Low', then=Value(3)),
                    default=Value(4),
                    output_field=IntegerField(),
                )
            ).order_by('urgency_rank', '-customer_contact_date')
        else: # Default: timeline
            queryset = queryset.order_by('-customer_contact_date', '-created_at')
            
        return queryset

    def get(self, request, *args, **kwargs):
        self.object_list = self.get_queryset()
        
        # Check if it's an AJAX request
        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.GET.get('ajax') == '1':
            self.template_name = 'core/partials/request_cards_partial.html'
        
        return self.render_to_response(self.get_context_data())

class MaintenanceRequestCreateView(LoginRequiredMixin, CreateView):
    model = MaintenanceRequest
    form_class = MaintenanceRequestForm
    template_name = 'core/request_form.html'
    success_url = reverse_lazy('request_list')

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        # Use only() to avoid fetching heavy text columns not needed for dropdowns
        products_qs = Product.objects.only('id', 'name', 'manufacturer', 'model').order_by('manufacturer', 'model')
        list(products_qs)
        data['products'] = products_qs
        
        equipments_qs = Equipment.objects.select_related('product').only(
            'id', 'serial_number', 'current_facility', 'product__name', 'product__manufacturer', 'product__model'
        )
        list(equipments_qs)
        data['equipments'] = equipments_qs
        form_kwargs = {'equipment_qs': equipments_qs}

        if self.request.POST:
            data['equipment_formset'] = MaintenanceRequestEquipmentFormSet(self.request.POST, form_kwargs=form_kwargs)
        else:
            data['equipment_formset'] = MaintenanceRequestEquipmentFormSet(form_kwargs=form_kwargs)
        
        # Read from session — set by is_engineer context processor on login, no DB hit
        data['is_engineer'] = self.request.session.get('is_engineer', False)
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

class MaintenanceRequestDetailView(LoginRequiredMixin, DetailView):
    model = MaintenanceRequest
    template_name = 'core/request_detail.html'
    context_object_name = 'request'

    def get_queryset(self):
        return super().get_queryset().select_related(
            'created_by', 'pricing_set_by'
        ).prefetch_related(
            'equipment_items__equipment__product',
            'service_reports',
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['is_engineer'] = self.request.session.get('is_engineer', False)
        return context


class MaintenanceRequestUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = MaintenanceRequest
    form_class = MaintenanceRequestForm
    template_name = 'core/request_form.html'
    success_url = reverse_lazy('request_list')

    def test_func(self):
        obj = self.get_object()
        # Allow if Admin OR Creator OR Assigned Engineer
        is_admin = self.request.user.is_staff
        is_creator = obj.created_by == self.request.user
        is_assigned = obj.assignments.filter(engineer__user=self.request.user).exists()
        
        return is_admin or is_creator or is_assigned

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs(); kwargs['user'] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        products_qs = Product.objects.only('id', 'name', 'manufacturer', 'model').order_by('manufacturer', 'model')
        list(products_qs)
        data['products'] = products_qs
        
        equipments_qs = Equipment.objects.select_related('product').only(
            'id', 'serial_number', 'current_facility', 'product__name', 'product__manufacturer', 'product__model'
        )
        list(equipments_qs)
        data['equipments'] = equipments_qs
        form_kwargs = {'equipment_qs': equipments_qs}

        if self.request.POST:
            data['equipment_formset'] = MaintenanceRequestEquipmentFormSet(self.request.POST, instance=self.object, form_kwargs=form_kwargs)
        else:
            data['equipment_formset'] = MaintenanceRequestEquipmentFormSet(instance=self.object, form_kwargs=form_kwargs)
        
        data['is_engineer'] = self.request.session.get('is_engineer', False)
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
        today = timezone.now().date()
        
        # Auto-complete past approved requests
        DriverRequest.objects.filter(
            status='Approved', 
            date__lt=today
        ).update(status='Completed')

        # OPTIMIZATION: Prevent N+1 queries when rendering driver and requester names
        queryset = super().get_queryset().select_related('driver', 'requester')
        
        # Date Filter (Specific Day)
        selected_date = self.request.GET.get('date')
        if selected_date:
            try:
                queryset = queryset.filter(date=selected_date)
            except (ValueError, TypeError):
                pass
            return queryset # specific date usually overrides status filters

        # Status/Time Filters
        filter_type = self.request.GET.get('filter', 'approved') # Default to 'approved' (Active/Schedule)
        today = timezone.now().date()
        
        if filter_type == 'pending':
            queryset = queryset.filter(status__in=['Pending', 'Edit Requested'])
        elif filter_type == 'approved': # "Approved, Schedule"
            queryset = queryset.filter(status='Approved', date__gte=today)
        elif filter_type == 'archived': # "Completed, Archived" (Past)
            queryset = queryset.filter(date__lt=today)
        else: # Fallback or 'active' -> Approved
            queryset = queryset.filter(status='Approved', date__gte=today)
            
        return queryset.order_by('date', 'start_time')

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
        
        # --- NEW: Fetch and serialize ALL requests for the month for Full Calendar ---
        month_requests_qs = DriverRequest.objects.filter(
            date__year=year,
            date__month=month
        ).select_related('driver', 'requester')
        
        # --- PHASE 2 OPTIMIZATION ---
        # Instead of asking the database for distinct days (which takes a 250ms round trip), 
        # compute it instantly in Python from the requests already fetched for the month loop.
        shift_days = set(req.date.day for req in month_requests_qs)
        
        serialized_requests = []
        for req in month_requests_qs:
            # Combine date and time for start/end
            start_dt = datetime.datetime.combine(req.date, req.start_time)
            end_dt = datetime.datetime.combine(req.date, req.end_time)
            
            serialized_requests.append({
                'id': req.id,
                'title': f"{req.get_location_display()} ({req.client_name or 'General'})",
                'start': start_dt.isoformat(),
                'end': end_dt.isoformat(),
                'driver': req.driver.name if req.driver else "Unassigned",
                'status': req.status,
                'vehicle': req.vehicle_type,
                'location': req.get_location_display(),
                'details': f"{req.requester.get_full_name() or req.requester.username} - {req.department}",
                'day': req.date.day, 
                'requester_id': req.requester.id,
            })
        
        # --- OPTIMIZATION (Phase 2) ---
        # The template only needs the COUNT of active drivers. Calling Driver.objects.all()
        # triggers redundant queries. Cache the count for 1 hour to drop DB pings.
        active_driver_count = cache.get_or_set('active_drivers_count', Driver.objects.filter(is_active=True).count, 3600)
        
        context.update({
            'active_driver_count': active_driver_count,
            'is_admin': self.request.user.is_staff,
            'calendar_weeks': calendar_weeks,
            'shift_days': list(shift_days),
            'current_month': month,
            'current_year': year,
            'month_name': calendar.month_name[month],
            'selected_date': self.request.GET.get('date'),
            'active_filter': self.request.GET.get('filter', 'approved'),
            'month_requests_json': json.dumps(serialized_requests), # Pass as JSON string
            'today': timezone.now().date(),
        })
        return context

    def get(self, request, *args, **kwargs):
        self.object_list = self.get_queryset()
        
        # Check if it's an AJAX request (either via header or param)
        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.GET.get('ajax') == '1':
            self.template_name = 'core/partials/driver_scheduling_partial.html'
            
        return self.render_to_response(self.get_context_data())

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

# --- ENGINEER SCHEDULING ---

class EngineerSchedulingView(LoginRequiredMixin, ListView):
    model = MaintenanceAssignment
    template_name = 'core/engineer_scheduling.html'
    context_object_name = 'assignments'

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
        
        shift_days = MaintenanceAssignment.objects.filter(
            date__year=year, 
            date__month=month
        ).values_list('date__day', flat=True).distinct()
        
        month_assignments_qs = MaintenanceAssignment.objects.filter(
            date__year=year,
            date__month=month
        ).select_related('engineer', 'maintenance_request')
        
        serialized_assignments = []
        for ass in month_assignments_qs:
            start_dt = datetime.datetime.combine(ass.date, ass.start_time)
            end_dt = datetime.datetime.combine(ass.date, ass.end_time)
            
            serialized_assignments.append({
                'id': ass.id,
                'title': f"{ass.maintenance_request.facility_name or 'Request'} (#MR-{ass.maintenance_request.id})",
                'start': start_dt.isoformat(),
                'end': end_dt.isoformat(),
                'engineer': ass.engineer.name,
                'location': ass.maintenance_request.get_location_display() or "On-site",
                'details': ass.notes or "",
                'day': ass.date.day,
                'request_id': ass.maintenance_request.id,
            })
        
        context.update({
            'engineers': Engineer.objects.filter(is_active=True),
            'is_admin': self.request.user.is_staff,
            'calendar_weeks': calendar_weeks,
            'shift_days': list(shift_days),
            'current_month': month,
            'current_year': year,
            'month_name': calendar.month_name[month],
            'selected_date': self.request.GET.get('date'),
            'month_requests_json': json.dumps(serialized_assignments),
        })
        return context

    def get(self, request, *args, **kwargs):
        self.object_list = self.get_queryset()
        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.GET.get('ajax') == '1':
            self.template_name = 'core/partials/engineer_scheduling_partial.html'
        return self.render_to_response(self.get_context_data())

class MaintenanceAssignmentCreateView(LoginRequiredMixin, CreateView):
    model = MaintenanceAssignment
    form_class = MaintenanceAssignmentForm
    template_name = 'core/maintenance_assignment_form.html'
    success_url = reverse_lazy('engineer_scheduling')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        request_id = self.request.GET.get('request_id')
        if request_id:
            context['maintenance_request'] = get_object_or_404(MaintenanceRequest, pk=request_id)
        return context

    def get_initial(self):
        initial = super().get_initial()
        request_id = self.request.GET.get('request_id')
        if request_id:
            initial['maintenance_request'] = request_id
        return initial

    def form_valid(self, form):
        response = super().form_valid(form)
        # Turn request status to 'Scheduled'
        mr = form.instance.maintenance_request
        if mr.status == 'Open':
            mr.status = 'Scheduled'
            mr.save()
        return response

class MaintenanceAssignmentUpdateView(LoginRequiredMixin, UpdateView):
    model = MaintenanceAssignment
    form_class = MaintenanceAssignmentForm
    template_name = 'core/maintenance_assignment_form.html'
    success_url = reverse_lazy('engineer_scheduling')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if hasattr(self, 'object') and self.object:
            context['maintenance_request'] = self.object.maintenance_request
        return context

    def get_queryset(self):
        if self.request.user.is_staff:
            return MaintenanceAssignment.objects.all()
        # For engineers, maybe they can only see their own? For now, allow staff to edit any.
        return MaintenanceAssignment.objects.all()

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

def get_driver_occupancy(request):
    driver_id = request.GET.get('driver_id')
    date_str = request.GET.get('date')
    request_id = request.GET.get('request_id')

    if not driver_id or not date_str:
        return JsonResponse({'occupied_slots': []})

    try:
        from datetime import datetime, timedelta
        
        # Base query for conflicting requests
        query = DriverRequest.objects.filter(
            driver_id=driver_id,
            date=date_str,
            status__in=['Pending', 'Approved', 'Edit Requested']
        )
        
        if request_id:
            query = query.exclude(pk=request_id)
            
        occupied_slots = []
        for trip in query:
            if trip.start_time and trip.end_time:
                occupied_slots.append({
                    'start': trip.start_time.strftime('%H:%M'),
                    'end': trip.end_time.strftime('%H:%M')
                })
        
        return JsonResponse({'occupied_slots': occupied_slots})
    except Exception as e:
        return JsonResponse({'occupied_slots': [], 'error': str(e)}, status=500)
