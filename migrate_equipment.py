import os
import django

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from core.models import Equipment, ReportItem, MaintenanceRequestEquipment, Product

def migrate_data():
    print("Migrating ReportItem data to Equipment Registry...")
    for item in ReportItem.objects.all():
        if item.product and item.serial_number:
            equipment, created = Equipment.objects.get_or_create(
                product=item.product,
                serial_number=item.serial_number,
                defaults={
                    'current_facility': item.report.client_name,
                    'current_location': item.report.location
                }
            )
            item.equipment = equipment
            item.save()
            if created:
                print(f"Created Registry entry: {equipment}")
    
    print("\nMigrating MaintenanceRequestEquipment data to Equipment Registry...")
    for req_eq in MaintenanceRequestEquipment.objects.all():
        if req_eq.product:
            # We don't have a serial number here usually, let's see if we can find one 
            # or just leave it blank for now or create a "Placeholder"
            # User will have to link them manually if S/N is unknown.
            pass

if __name__ == "__main__":
    migrate_data()
