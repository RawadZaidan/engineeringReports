from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import MaintenanceRequest
from webpush import send_group_notification
import threading

def _send_push_async(payload):
    try:
        send_group_notification(group_name="Engineer", payload=payload, ttl=1000)
    except Exception as e:
        print(f"Webpush notification failed: {e}")

@receiver(post_save, sender=MaintenanceRequest)
def send_maintenance_notification(sender, instance, created, **kwargs):
    if created:
        payload = {
            "head": "New Maintenance Request",
            "body": f"{instance.facility_name}\n({instance.urgency}) - {instance.get_location_display() or instance.location}",
            "icon": "/static/icons/icon-192x192.png",
            "url": f"/requests/{instance.id}/"
        }
        
        # Dispatch notification to a background thread to prevent blocking
        # the HTTP response for 2-5 seconds while waiting for remote push servers
        threading.Thread(target=_send_push_async, args=(payload,), daemon=True).start()
