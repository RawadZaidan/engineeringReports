from django.core.cache import cache
from .models import MaintenanceRequest, DriverRequest


def is_engineer(request):
    """
    Adds `is_engineer` to every template context.
    Uses the session so the group query only fires ONCE per login session,
    not on every single page request.
    """
    if not request.user.is_authenticated:
        return {'is_engineer': False}

    # Check session cache first — avoids a DB hit on every request
    is_eng = request.session.get('is_engineer')
    if is_eng is None:
        is_eng = request.user.groups.filter(name='Engineer').exists()
        request.session['is_engineer'] = is_eng

    return {'is_engineer': is_eng}


def notification_counts(request):
    """
    Provides notification badge counts for the nav sidebar.
    Caches the result per-user for 60 seconds to avoid a DB round-trip
    on every page load.  The DashboardView shares the same cache key so
    both callers benefit from the same cached value.
    """
    if not request.user.is_authenticated:
        return {
            'open_maintenance_count': 0,
            'open_driver_request_count': 0,
        }

    cache_key = f'notification_counts_{request.user.id}'
    cached = cache.get(cache_key)
    if cached:
        return cached

    # Single query for maintenance count (shared with DashboardView stats)
    open_maintenance_count = MaintenanceRequest.objects.filter(status='Open').count()

    open_driver_request_count = 0
    if request.user.is_staff:
        open_driver_request_count = DriverRequest.objects.filter(
            status__in=['Pending', 'Edit Requested']
        ).count()

    counts = {
        'open_maintenance_count': open_maintenance_count,
        'open_driver_request_count': open_driver_request_count,
    }

    cache.set(cache_key, counts, 60)
    return counts
