from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import MaintenanceRequest
from webpush import send_group_notification

@receiver(post_save, sender=MaintenanceRequest)
def send_maintenance_notification(sender, instance, created, **kwargs):
    if created:
        payload = {
            "head": "New Maintenance Request",
            "body": f"{instance.facility_name}\n({instance.urgency}) - {instance.get_location_display() or instance.location}",
            "icon": "/static/icons/icon-192x192.png",
            "url": f"/requests/{instance.id}/"
        }
        
        # Send to all Engineers
        try:
            send_group_notification(group_name="Engineer", payload=payload, ttl=1000)
        except Exception as e:
            # Avoid crashing the entire request creation if notification fails
            print(f"Webpush notification failed: {e}")
