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

def notification_counts(request):
    if not request.user.is_authenticated:
        return {
            'open_maintenance_count': 0,
            'open_driver_request_count': 0,
        }
    
    # Maintenance Requests count (Open)
    # Available to everyone who can see requests (engineers/staff)
    open_maintenance_count = MaintenanceRequest.objects.filter(status='Open').count()
    
    # Driver Requests count (Pending / Edit Requested)
    # Primarily for admin/staff who handle logistics
    open_driver_request_count = 0
    if request.user.is_staff:
        open_driver_request_count = DriverRequest.objects.filter(
            status__in=['Pending', 'Edit Requested']
        ).count()
        
    return {
        'open_maintenance_count': open_maintenance_count,
        'open_driver_request_count': open_driver_request_count,
    }
