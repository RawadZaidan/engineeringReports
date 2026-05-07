from django.core.cache import cache
from .models import MaintenanceRequest, DriverRequest


def user_roles(request):
    """
    Adds role flags to every template context.
    Uses the session so group queries only fire ONCE per login session.
    Covers: is_engineer, is_driver, is_sales, is_procurement
    (Admin/superuser is already available via user.is_staff / user.is_superuser)
    """
    if not request.user.is_authenticated:
        return {
            'is_engineer': False,
            'is_driver': False,
            'is_sales': False,
            'is_procurement': False,
        }

    def _get_role(key, group_name):
        val = request.session.get(key)
        if val is None:
            val = request.user.groups.filter(name=group_name).exists()
            request.session[key] = val
        return val

    return {
        'is_engineer': _get_role('is_engineer', 'Engineer'),
        'is_driver': _get_role('is_driver', 'Driver'),
        'is_sales': _get_role('is_sales', 'Sales'),
        'is_procurement': _get_role('is_procurement', 'Procurement'),
    }


# Keep backward-compatible alias so any existing reference to is_engineer still works
def is_engineer(request):
    return {'is_engineer': user_roles(request)['is_engineer']}


def notification_counts(request):
    """
    Provides notification badge counts for the nav sidebar.
    Caches the result per-user for 60 seconds to avoid a DB round-trip
    on every page load.
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
