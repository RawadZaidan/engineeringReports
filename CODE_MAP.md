# Codebase Map

This document provides a detailed map of the functions, classes, and components in the Medilab Maintenance Database.

## 📂 Core Application (`core/`)
The primary application containing business logic, database models, and views.

### 🗄️ Models (`core/models.py`)
| Model | Description | Key Fields |
|-------|-------------|------------|
| `Product` | Templates/blueprints for equipment. | `name`, `category`, `manufacturer`, `model` |
| `Equipment` | Physical units. | `product` (FK), `serial_number`, `location`, `status` |
| `ServiceReport` | Main service record. | `client_name`, `service_date`, `engineer`, `status`, `client_signature` |
| `ReportItem` | Equipment items within a report. | `report` (FK), `equipment` (FK), `equipment_note` |
| `ReportImage` | Photos attached to reports. | `report` (FK), `image`, `caption` |
| `MaintenanceRequest` | Requests for service. | `request_type`, `urgency`, `status`, `description` |
| `MaintenanceRequestEquipment` | Equipment linked to a request. | `request` (FK), `equipment` (FK) |
| `Driver` | Driver profiles for scheduling. | `name`, `photo`, `license_info`, `is_active` |

### 🔍 Views (`core/views.py`)
**Dashboard & Lists**
- `DashboardView`: Main landing page with analytics and recent reports.
- `ServiceReportListView`: Filterable list of all service reports.
- `ProductListView`: Catalogue list.
- `EquipmentListView`: Registry list.
- `MaintenanceRequestListView`: List of maintenance requests.

**CRUD Operations (Create/Read/Update/Delete)**
- `ServiceReportCreateView`: Handles report creation. *Key Logic: `form_valid` processes signature.*
- `ServiceReportUpdateView`: Handles report editing.
- `ServiceReportDetailView`: Displays single report with signature and photos.
- `ProductCreateView`: Adds new catalogue items.
- `MaintenanceRequestCreateView` / `UpdateView` / `DetailView`: Request management.

**AJAX / API Endpoints**
- `product_create_ajax`: JSON endpoint to create a Product from within the Report form.
- `equipment_create_ajax`: JSON endpoint to register Equipment dynamically.
- `update_pricing_ajax`: Updates pricing calculations on request forms.
- `driver_request_action`: Handles accept/reject actions for driver requests.
- `get_driver_occupancy`: Returns driver availability data.
- **Note**: `DriverSchedulingView` serializes monthly request data to JSON for the frontend calendar.

### 📝 Forms (`core/forms.py`)
- `ServiceReportForm`: Main report form. Includes hidden `client_signature` field.
- `ReportItemFormSet`: Inline formset for adding multiple equipment items to a report.
- `MaintenanceRequestForm`: Request creation form.
- `ProductForm`, `EquipmentForm`: Standard model forms.

### 🌐 URLs (`core/urls.py`)
Maps views to URL paths.
- Reports: `/reports/`, `/report/new/`, `/report/<pk>/`
- Products: `/products/`
- Registry: `/registry/`
- Requests: `/requests/`
- Scheduling: `/scheduling/`

---

## 📄 Document AI (`docai/`)
Specialized application for AI-powered document analysis and summarization.

### 🧠 Views (`docai/views.py`)
- `docai_home`: Landing page for document upload.
- `summarize_document`: Handles file upload and initiates analysis.
- `perform_analysis_task`: **Background Task**. Extracts text, calls LLM, and saves `TenderSummary`.
- `analysis_progress_api`: Returns status of running analysis tasks.
- `summary_detail`: Displays the generated summary.
- `edit_summary`: Allows manual editing of AI-generated content.

### 🛠️ Utilities (`docai/utils.py`)
- `extract_text_from_file`: Dispatcher function. Determines file type and calls specific extractor.
- `extract_text_from_pdf`: Uses `pdfplumber`.
- `extract_text_from_docx`: Uses `python-docx`.
- `extract_text_from_excel`: Uses `pandas`.
- `extract_text_from_rtf`: Uses `striprtf`.

---

## 🎨 Frontend Architecture
**Tech Stack:** Django Templates, Vanilla CSS, Vanilla JS.

### 🖌️ Styling (`static/css/`)
- `custom.css` (or main CSS file): Contains variables for colors (premium blue, grey) and utility classes.

### 📜 Scripts (`static/js/`)
- `service-worker.js`: Handles PWA caching and offline capabilities.
- **Inline Scripts**: Much of the dynamic logic (Signature Pad, Formset adding/removing) resides in `<script>` tags within:
    - `templates/core/report_form.html` (Signature, Formsets)
    - `templates/core/request_form.html`

### 🖼️ Templates (`templates/`)
- `base.html`: Main layout (Sidebar, Navbar, Footer).
- `core/`: Application-specific templates.
- `docai/`: AI feature templates.
