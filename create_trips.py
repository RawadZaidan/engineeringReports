import os
import django
import random
from datetime import datetime, timedelta, time

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.contrib.auth.models import User
from core.models import Driver, DriverRequest, MaintenanceRequest

def schedule_trips():
    users = list(User.objects.all())
    if not users:
        print("No users found to create requests.")
        return

    drivers = list(Driver.objects.filter(is_active=True))
    if not drivers:
        print("No active drivers found. Creating a generic one.")
        d = Driver.objects.create(name="Generic Driver", license_info="Class A")
        drivers = [d]

    departments = [c[0] for c in DriverRequest.DEPARTMENT_CHOICES]
    locations = [c[0] for c in MaintenanceRequest.LEBANON_LOCATIONS]
    vehicle_types = [c[0] for c in DriverRequest.VEHICLE_CHOICES]
    statuses = [c[0] for c in DriverRequest.STATUS_CHOICES]

    today = datetime.now().date()
    
    for i in range(10):
        # Pick a date within the next 5 days
        delta_days = random.randint(0, 5)
        trip_date = today + timedelta(days=delta_days)
        
        # Pick random start and end times (e.g. 08:00 to 16:00)
        start_hour = random.randint(7, 14)
        start_min = random.choice([0, 30])
        end_hour = start_hour + random.randint(1, 3)
        end_min = random.choice([0, 30])
        
        start_t = time(hour=start_hour, minute=start_min)
        end_t = time(hour=end_hour, minute=end_min)
        
        dept = random.choice(departments)
        loc = random.choice(locations)
        veh = random.choice(vehicle_types)
        stat = random.choice(statuses)
        driver = random.choice(drivers)
        requester = random.choice(users)
        
        dr = DriverRequest.objects.create(
            requester=requester,
            driver=driver,
            department=dept,
            origin="Beirut",
            location=loc,
            date=trip_date,
            start_time=start_t,
            end_time=end_t,
            vehicle_type=veh,
            status=stat,
            client_name=f"Random Client {i+1} Inc.",
            contact_person=f"Contact {i+1}",
            contact_number=f"03 12{i} 45{i}",
            estimated_distance=f"{random.randint(5, 50)} km"
        )
        print(f"Created: {dr}")

if __name__ == '__main__':
    schedule_trips()
