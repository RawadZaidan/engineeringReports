"""
Django management command to populate the database with realistic Lebanese mock data
for a medical, industrial, and chemical company.
"""
import random
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User, Group
from django.utils import timezone
from core.models import (
    Product, Equipment, ServiceReport, MaintenanceRequest, 
    MaintenanceRequestEquipment, Driver, DriverRequest, Engineer, MaintenanceAssignment
)


class Command(BaseCommand):
    help = 'Populate database with Lebanese mock data for medical/industrial/chemical company'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS('Starting data population...'))
        
        # Lebanese locations
        self.locations = [
            'Beirut', 'Tripoli', 'Sidon', 'Tyre', 'Zahle', 'Jounieh', 
            'Baabda', 'Nabatieh', 'Byblos', 'Batroun'
        ]
        
        # Lebanese facilities (medical, industrial, chemical)
        self.facilities = [
            # Medical
            'Rafik Hariri University Hospital', 'Hotel Dieu de France', 'American University of Beirut Medical Center',
            'Lebanese American University Medical Center', 'Makassed General Hospital', 'Mount Lebanon Hospital',
            'Clemenceau Medical Center', 'Sacre Coeur Hospital', 'Haykal Hospital',
            
            # Industrial
            'Solidere Industrial Complex', 'Tripoli Special Economic Zone', 'Zahrani Oil Installations',
            'Selaata Industrial Zone', 'Chekka Cement Factory', 'Beddawi Industrial Area',
            
            # Chemical & Pharmaceutical
            'Benta Pharma Industries', 'Pharmaline Laboratories', 'Algorithm SAL',
            'Hikma Pharmaceuticals Lebanon', 'Consolidated Contractors Company', 'Holcim Lebanon'
        ]
        
        # Equipment types for medical/industrial/chemical
        self.equipment_types = [
            # Medical Equipment
            {'name': 'MRI Scanner Siemens Magnetom', 'category': 'Medical Imaging'},
            {'name': 'CT Scanner GE Revolution', 'category': 'Medical Imaging'},
            {'name': 'X-Ray Machine Philips DigitalDiagnost', 'category': 'Medical Imaging'},
            {'name': 'Ultrasound System Samsung HS70A', 'category': 'Medical Imaging'},
            {'name': 'Ventilator Dräger Evita V800', 'category': 'Life Support'},
            {'name': 'Anesthesia Machine GE Aisys CS2', 'category': 'Life Support'},
            {'name': 'Dialysis Machine Fresenius 5008S', 'category': 'Life Support'},
            {'name': 'Autoclave Sterilizer Tuttnauer', 'category': 'Sterilization'},
            {'name': 'Laboratory Centrifuge Eppendorf', 'category': 'Lab Equipment'},
            {'name': 'PCR Machine Bio-Rad CFX96', 'category': 'Lab Equipment'},
            
            # Industrial Equipment
            {'name': 'Industrial Boiler Cleaver-Brooks', 'category': 'HVAC'},
            {'name': 'Chiller Carrier AquaEdge', 'category': 'HVAC'},
            {'name': 'Air Compressor Atlas Copco GA90', 'category': 'Compressed Air'},
            {'name': 'Generator Caterpillar C18', 'category': 'Power Generation'},
            {'name': 'Forklift Toyota 8FD25', 'category': 'Material Handling'},
            {'name': 'Conveyor System Siemens', 'category': 'Material Handling'},
            
            # Chemical Processing
            {'name': 'Reactor Vessel 5000L', 'category': 'Chemical Processing'},
            {'name': 'Distillation Column', 'category': 'Chemical Processing'},
            {'name': 'Heat Exchanger Alfa Laval', 'category': 'Chemical Processing'},
            {'name': 'Mixing Tank 10000L', 'category': 'Chemical Processing'},
            {'name': 'Filtration System Pall', 'category': 'Chemical Processing'},
            {'name': 'pH Control System Endress+Hauser', 'category': 'Process Control'},
        ]
        
        # Create users and groups
        self.create_users_and_groups()
        
        # Create products and equipment
        self.create_products_and_equipment()
        
        # Create drivers and engineers
        self.create_drivers_and_engineers()
        
        # Create maintenance requests
        self.create_maintenance_requests()
        
        # Create service reports
        self.create_service_reports()
        
        # Create driver requests
        self.create_driver_requests()
        
        # Create maintenance assignments
        self.create_maintenance_assignments()
        
        self.stdout.write(self.style.SUCCESS('✅ Data population completed successfully!'))

    def create_users_and_groups(self):
        self.stdout.write('Creating users and groups...')
        
        # Create groups
        engineer_group, _ = Group.objects.get_or_create(name='Engineer')
        
        # Create admin user if doesn't exist
        if not User.objects.filter(username='admin').exists():
            admin = User.objects.create_superuser('admin', 'admin@medilab.com', 'admin123')
            self.stdout.write(self.style.SUCCESS('  Created admin user'))
        else:
            admin = User.objects.get(username='admin')
        
        # Create engineer users with Lebanese names
        engineer_names = [
            ('Karim', 'Hariri'), ('Nadia', 'Khoury'), ('Rami', 'Gemayel'),
            ('Layla', 'Nasrallah'), ('Fadi', 'Aoun'), ('Maya', 'Salam')
        ]
        
        self.engineers_users = []
        for first, last in engineer_names:
            username = f"{first.lower()}.{last.lower()}"
            if not User.objects.filter(username=username).exists():
                user = User.objects.create_user(
                    username=username,
                    email=f"{username}@medilab.com",
                    password='engineer123',
                    first_name=first,
                    last_name=last
                )
                user.groups.add(engineer_group)
                self.engineers_users.append(user)
                self.stdout.write(f'  Created engineer: {first} {last}')
            else:
                user = User.objects.get(username=username)
                self.engineers_users.append(user)
        
        self.admin_user = admin

    def create_products_and_equipment(self):
        self.stdout.write('Creating products and equipment...')
        
        self.products = []
        self.equipment_list = []
        
        for eq_type in self.equipment_types:
            # Create product
            product, created = Product.objects.get_or_create(
                name=eq_type['name'],
                defaults={
                    'category': eq_type['category'],
                    'manufacturer': random.choice(['Siemens', 'GE', 'Philips', 'Dräger', 'Fresenius', 'Atlas Copco', 'Caterpillar']),
                    'model': f"MDL-{random.randint(1000, 9999)}",
                    'notes': f"{eq_type['category']} equipment for medical/industrial use"
                }
            )
            self.products.append(product)
            
            # Create 2-3 equipment instances per product
            for i in range(random.randint(2, 3)):
                serial = f"SN-{random.randint(100000, 999999)}"
                if not Equipment.objects.filter(serial_number=serial).exists():
                    warranty_date = timezone.now().date() + timedelta(days=random.randint(-365, 730))
                    equipment = Equipment.objects.create(
                        product=product,
                        serial_number=serial,
                        installation_date=timezone.now().date() - timedelta(days=random.randint(30, 1095)),
                        warranty_expiration_date=warranty_date,
                        notes=f"Installed at {random.choice(self.facilities)} in {random.choice(self.locations)}"
                    )
                    self.equipment_list.append(equipment)
        
        self.stdout.write(self.style.SUCCESS(f'  Created {len(self.products)} products and {len(self.equipment_list)} equipment items'))

    def create_drivers_and_engineers(self):
        self.stdout.write('Creating drivers and engineers...')
        
        # Create drivers with Lebanese names
        driver_names = ['Ahmad Khalil', 'Hassan Moussawi', 'Ali Hamdan', 'Bilal Youssef', 'Omar Saad']
        self.drivers = []
        for name in driver_names:
            driver, created = Driver.objects.get_or_create(
                name=name,
                defaults={
                    'license_info': f"Lebanese CDL Class {random.choice(['A', 'B', 'C'])}",
                    'is_active': True
                }
            )
            self.drivers.append(driver)
        
        # Create engineer profiles
        self.engineers = []
        specializations = ['Medical Equipment', 'Industrial Systems', 'Chemical Processing', 'HVAC', 'Electrical', 'Mechanical']
        for user in self.engineers_users:
            engineer, created = Engineer.objects.get_or_create(
                user=user,
                defaults={
                    'name': f"{user.first_name} {user.last_name}",
                    'specialization': random.choice(specializations),
                    'is_active': True
                }
            )
            self.engineers.append(engineer)
        
        self.stdout.write(self.style.SUCCESS(f'  Created {len(self.drivers)} drivers and {len(self.engineers)} engineers'))

    def create_maintenance_requests(self):
        self.stdout.write('Creating maintenance requests...')
        
        urgency_levels = ['Low', 'Medium', 'High', 'Emergency']
        statuses = ['Open', 'Scheduled', 'In Progress', 'Completed']
        service_types = ['Preventive Maintenance', 'Corrective Maintenance', 'Calibration', 'Installation', 'Emergency Repair']
        
        issues = [
            'Equipment not powering on', 'Unusual noise during operation', 'Calibration required',
            'Software update needed', 'Preventive maintenance due', 'Leaking fluid',
            'Temperature control malfunction', 'Display error messages', 'Performance degradation',
            'Safety inspection required', 'Filter replacement needed', 'Sensor malfunction'
        ]
        
        for i in range(50):
            facility = random.choice(self.facilities)
            location = random.choice(self.locations)
            
            request = MaintenanceRequest.objects.create(
                facility_name=facility,
                location=location,
                service_type=random.choice(service_types),
                request_details=random.choice(issues),
                urgency=random.choice(urgency_levels),
                status=random.choice(statuses),
                customer_contact_date=timezone.now().date() - timedelta(days=random.randint(0, 60)),
                contact_name=random.choice(['Dr. Samir Geagea', 'Eng. Rania Harb', 'Mr. Tony Frangieh', 'Ms. Joelle Karam']),
                contact_number=f"+961 {random.randint(3, 81)} {random.randint(100000, 999999)}",
                donor=random.choice(['USAID', 'WHO', 'EU', 'Private', 'Government']),
                created_by=random.choice(self.engineers_users + [self.admin_user])
            )
            
            # Add 1-3 equipment items to the request
            for _ in range(random.randint(1, 3)):
                equipment = random.choice(self.equipment_list)
                MaintenanceRequestEquipment.objects.create(
                    request=request,
                    equipment=equipment
                )
        
        self.stdout.write(self.style.SUCCESS(f'  Created 50 maintenance requests'))

    def create_service_reports(self):
        self.stdout.write('Creating service reports...')
        
        statuses = ['Draft', 'Pending', 'Completed']
        service_types = ['Preventive Maintenance', 'Corrective Maintenance', 'Calibration', 'Installation']
        billing_categories = ['Billable', 'Under Warranty', 'Goodwill']
        final_statuses = ['Operational', 'Needs Parts', 'Decommissioned']
        
        work_performed = [
            'Replaced faulty component and tested system',
            'Performed calibration and verification',
            'Cleaned and lubricated moving parts',
            'Updated software to latest version',
            'Replaced filters and checked performance',
            'Inspected safety systems and documented findings',
            'Repaired electrical connections',
            'Adjusted settings and optimized performance'
        ]
        
        for i in range(40):
            facility = random.choice(self.facilities)
            engineer = random.choice(self.engineers_users)
            
            report = ServiceReport.objects.create(
                engineer=engineer,
                client_name=facility,
                location=random.choice(self.locations),
                service_date=timezone.now().date() - timedelta(days=random.randint(0, 90)),
                service_type=random.choice(service_types),
                billing_category=random.choice(billing_categories),
                issue_description=random.choice([
                    'Equipment malfunction reported', 'Scheduled maintenance', 
                    'Calibration due', 'Performance issues'
                ]),
                work_performed=random.choice(work_performed),
                final_status=random.choice(final_statuses),
                status=random.choice(statuses),
                follow_up_required=random.choice([True, False]),
                client_representative_name=random.choice(['Dr. Michel Aoun', 'Eng. Saad Hariri', 'Mr. Nabih Berri']),
                client_phone_number=f"+961 {random.randint(3, 81)} {random.randint(100000, 999999)}",
                donor=random.choice(['USAID', 'WHO', 'EU', 'Private', 'Government']),
                warranty_duration_years=random.choice([1, 2, 3]) if random.random() > 0.5 else None
            )
        
        self.stdout.write(self.style.SUCCESS(f'  Created 40 service reports'))

    def create_driver_requests(self):
        self.stdout.write('Creating driver requests...')
        
        statuses = ['Pending', 'Approved', 'Cancelled']
        vehicle_types = ['Truck', 'Car', 'Moto']
        departments = ['Engineering', 'Sales', 'Procurement', 'Management']
        
        for i in range(30):
            DriverRequest.objects.create(
                requester=random.choice(self.engineers_users + [self.admin_user]),
                driver=random.choice(self.drivers),
                date=timezone.now().date() + timedelta(days=random.randint(-7, 30)),
                start_time=datetime.strptime(f"{random.randint(8, 16)}:00", "%H:%M").time(),
                end_time=datetime.strptime(f"{random.randint(12, 18)}:00", "%H:%M").time(),
                location=random.choice(self.locations),
                client_name=random.choice(self.facilities),
                department=random.choice(departments),
                vehicle_type=random.choice(vehicle_types),
                status=random.choice(statuses)
            )
        
        self.stdout.write(self.style.SUCCESS(f'  Created 30 driver requests'))

    def create_maintenance_assignments(self):
        self.stdout.write('Creating maintenance assignments...')
        
        # Get some maintenance requests
        requests = list(MaintenanceRequest.objects.filter(status__in=['Scheduled', 'In Progress'])[:20])
        
        for request in requests:
            MaintenanceAssignment.objects.create(
                maintenance_request=request,
                engineer=random.choice(self.engineers),
                date=timezone.now().date() + timedelta(days=random.randint(-14, 30)),
                start_time=datetime.strptime(f"{random.randint(8, 14)}:00", "%H:%M").time(),
                end_time=datetime.strptime(f"{random.randint(12, 17)}:00", "%H:%M").time(),
                notes=random.choice([
                    'Bring replacement parts', 'Coordinate with facility manager',
                    'Requires 2 engineers', 'Extended maintenance window needed',
                    'Priority assignment'
                ])
            )
        
        self.stdout.write(self.style.SUCCESS(f'  Created {len(requests)} maintenance assignments'))
