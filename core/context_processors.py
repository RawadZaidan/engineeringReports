from .models import MaintenanceRequest, DriverRequest

def is_engineer(request):
    if not request.user.is_authenticated:
        return {'is_engineer': False}
    
    # Check session cache first
    is_eng = request.session.get('is_engineer')
    if is_eng is None:
        is_eng = request.user.groups.filter(name='Engineer').exists()
        request.session['is_engineer'] = is_eng
        
    return {'is_engineer': is_eng}

from django.core.cache import cache

def notification_counts(request):
    if not request.user.is_authenticated:
        return {
            'open_maintenance_count': 0,
            'open_driver_request_count': 0,
        }
    
    # Try to get from cache first
    cache_key = f'notification_counts_{request.user.id}'
    cached_counts = cache.get(cache_key)
    if cached_counts:
        return cached_counts

    # Maintenance Requests count (Open)
    open_maintenance_count = MaintenanceRequest.objects.filter(status='Open').count()
    
    # Driver Requests count (Pending / Edit Requested)
    open_driver_request_count = 0
    if request.user.is_staff:
        open_driver_request_count = DriverRequest.objects.filter(
            status__in=['Pending', 'Edit Requested']
        ).count()
        
    counts = {
        'open_maintenance_count': open_maintenance_count,
        'open_driver_request_count': open_driver_request_count,
    }
    
    # Cache for 60 seconds
    cache.set(cache_key, counts, 60)
    
    return counts

