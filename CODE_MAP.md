# Codebase Map

Detailed map of every model, view, form, URL, and utility in MedilabERP.
Last updated: 2026-05-07

---

## 📂 Core Application (`core/`)

### 🗄️ Models (`core/models.py`)

| Model | Description | Key Fields |
|-------|-------------|------------|
| `Product` | Equipment catalogue blueprints. | `name`, `category`, `manufacturer`, `model`, `notes` — unique on `(manufacturer, model)` |
| `Equipment` | Physical unit instances. | `product` (FK), `serial_number`, `current_facility`, `current_location`, `installation_date`, `warranty_expiration_date` — unique on `(product, serial_number)` |
| `ServiceReport` | Primary service record. | `client_name`, `project_reference`, `service_date`, `engineer` (FK→User), `maintenance_request` (FK, optional), `service_type`, `billing_category`, `final_status`, `status` (Draft/Pending Review/Completed), `client_signature` |
| `ReportItem` | Equipment row inside a report. | `report` (FK), `equipment` (FK, optional), `equipment_note` |
| `ReportImage` | Photos attached to a report. | `report` (FK), `image`, `thumbnail`, `caption` |
| `MaintenanceRequest` | Inbound service/maintenance request. | `urgency` (Low/Medium/High/Emergency), `facility_name`, `location` (Lebanon regions), `donor`, `service_type`, `billing_status` (Warranty/Billable/Contract/FOC), `estimated_cost`, `status` (Open→Scheduled→In Progress→Completed/Cancelled) |
| `MaintenanceRequestEquipment` | Equipment line items on a request. | `request` (FK), `equipment` (FK, optional), `notes` |
| `SavedFilter` | Persisted search filter presets. | `user` (FK), `name`, `filter_type` (report/request), `filter_params` (JSONField), `is_default` |
| `Driver` | Driver profile. | `user` (OneToOne, optional), `name`, `photo`, `license_info`, `is_active` |
| `DriverRequest` | Logistics trip request. | `requester` (FK→User), `driver` (FK), `maintenance_request` (FK, optional), `department`, `location`, `date`, `start_time`, `end_time`, `vehicle_type` (Truck/Car/Moto), `status` (Pending/Approved/Denied/Edit Requested/Completed/Cancelled) |
| `Engineer` | Engineering staff profile. | `user` (OneToOne, optional), `name`, `photo`, `specialization`, `is_active` |
| `MaintenanceAssignment` | Engineer assigned to a request on a specific date/time. | `engineer` (FK), `maintenance_request` (FK), `date`, `start_time`, `end_time`, `notes` |

---

### 🔍 Views (`core/views.py`)

**Mixin**
- `DriverRedirectMixin` — Redirects users in the "Driver" group away from non-logistics pages.

**Dashboard & Lists**
| View | Type | Description |
|------|------|-------------|
| `DashboardView` | CBV (TemplateView) | Landing page. Renders analytics, recent reports, and open request counts. |
| `ServiceReportListView` | CBV (ListView) | Filterable, searchable list of all service reports. |
| `ProductListView` | CBV (ListView) | Product catalogue list. |
| `EquipmentListView` | CBV (ListView) | Equipment registry list. |
| `MaintenanceRequestListView` | CBV (ListView) | Filterable list of maintenance requests. |
| `DriverSchedulingView` | CBV (ListView) | Driver scheduling calendar. Serializes monthly `DriverRequest` data to JSON for the frontend. |
| `EngineerSchedulingView` | CBV (ListView) | Engineer scheduling calendar. Serializes `MaintenanceAssignment` data for calendar frontend. |

**CRUD — Service Reports**
| View | Type | Description |
|------|------|-------------|
| `ServiceReportCreateView` | CBV (CreateView) | Report creation. `get_initial()` maps `MaintenanceRequest` fields; `get_context_data()` auto-matches equipment. |
| `ServiceReportUpdateView` | CBV (UpdateView) | Report editing. Restricted to report owner or staff. |
| `ServiceReportDetailView` | CBV (DetailView) | Full report display with signature, photos, and items. |

**CRUD — Maintenance Requests**
| View | Type | Description |
|------|------|-------------|
| `MaintenanceRequestCreateView` | CBV (CreateView) | New request submission. |
| `MaintenanceRequestDetailView` | CBV (DetailView) | Full request view with equipment list, driver trips, engineer assignments. |
| `MaintenanceRequestUpdateView` | CBV (UpdateView) | Request editing. |

**CRUD — Scheduling**
| View | Type | Description |
|------|------|-------------|
| `DriverRequestCreateView` | CBV (CreateView) | New driver/logistics trip request. |
| `DriverRequestUpdateView` | CBV (UpdateView) | Edit a driver trip request. |
| `MaintenanceAssignmentCreateView` | CBV (CreateView) | Assign an engineer to a maintenance request. |
| `MaintenanceAssignmentUpdateView` | CBV (UpdateView) | Edit an engineer assignment. |

**CRUD — Products & Equipment**
| View | Type | Description |
|------|------|-------------|
| `ProductCreateView` | CBV (CreateView) | Add new product to catalogue. |

**AJAX / API Endpoints**
| Endpoint | Method | Description |
|----------|--------|-------------|
| `product_create_ajax` | POST | Create a `Product` inline from the report form. |
| `product_categories_ajax` | GET | Return all product categories as JSON. |
| `product_names_by_category_ajax` | GET | Return product names filtered by category. |
| `product_brands_ajax` | GET | Return all manufacturer names as JSON. |
| `product_models_ajax` | GET | Return model names filtered by manufacturer. |
| `product_get_or_create_ajax` | POST | Get existing or create new product by category/brand/model. |
| `equipment_create_ajax` | POST | Register new equipment unit inline. |
| `update_pricing_ajax` | POST | Recalculate and persist estimated cost on a request form. |
| `driver_request_action` | POST | Accept/reject/action a driver trip request. |
| `get_driver_occupancy` | GET | Return driver availability data for scheduling. |

---

### 📝 Forms (`core/forms.py`)

| Form / FormSet | Description |
|----------------|-------------|
| `MaintenanceRequestForm` | Full request form. `service_type` uses `CheckboxSelectMultiple`; joins to CSV on save. Field visibility gated by user permissions. |
| `MaintenanceRequestEquipmentForm` | Single equipment row on a request. |
| `MaintenanceRequestEquipmentFormSet` | Inline formset (extra=1, can_delete=True). |
| `ServiceReportForm` | Main report form. Multi-choice fields: `service_type`, `billing_category`, `final_status`. Requires key fields when `status=Completed`. `client_signature` stored via HiddenInput. |
| `ReportItemForm` | Single equipment row within a report. |
| `BaseReportItemFormSet` | Prevents duplicate equipment entries via `clean()`. |
| `ReportItemFormSet` | Inline formset (extra=1, can_delete=True) using `BaseReportItemFormSet`. |
| `ProductForm` | Product creation. Validates uniqueness of `(manufacturer, model)`. |
| `EquipmentForm` | Equipment registration. Date fields use `type='date'` widget. |
| `DriverRequestForm` | Driver trip request. Time fields are 30-min increment dropdowns (6 AM–6 PM). Validates no past dates, no time conflicts, end > start. |
| `MaintenanceAssignmentForm` | Engineer scheduling form. Validates against `MaintenanceRequest` availability window and prevents engineer double-booking. |

**Module-Level Constants:** `SERVICE_TYPE_CHOICES`, `BILLING_CATEGORY_CHOICES`, `FINAL_STATUS_CHOICES`

---

### 🌐 URLs (`core/urls.py`)

| Pattern | View | Name |
|---------|------|------|
| `` | `DashboardView` | `dashboard` |
| `reports/` | `ServiceReportListView` | `report_list` |
| `report/new/` | `ServiceReportCreateView` | `report_create` |
| `report/<pk>/` | `ServiceReportDetailView` | `report_detail` |
| `report/<pk>/edit/` | `ServiceReportUpdateView` | `report_update` |
| `products/` | `ProductListView` | `product_list` |
| `products/new/` | `ProductCreateView` | `product_create` |
| `products/create-ajax/` | `product_create_ajax` | `product_create_ajax` |
| `products/categories/` | `product_categories_ajax` | `product_categories_ajax` |
| `products/names-by-category/` | `product_names_by_category_ajax` | `product_names_by_category_ajax` |
| `products/brands/` | `product_brands_ajax` | `product_brands_ajax` |
| `products/models/` | `product_models_ajax` | `product_models_ajax` |
| `products/get-or-create/` | `product_get_or_create_ajax` | `product_get_or_create_ajax` |
| `registry/` | `EquipmentListView` | `equipment_list` |
| `registry/create-ajax/` | `equipment_create_ajax` | `equipment_create_ajax` |
| `requests/` | `MaintenanceRequestListView` | `request_list` |
| `requests/new/` | `MaintenanceRequestCreateView` | `request_create` |
| `requests/<pk>/` | `MaintenanceRequestDetailView` | `request_detail` |
| `requests/<pk>/edit/` | `MaintenanceRequestUpdateView` | `request_update` |
| `requests/update-pricing/` | `update_pricing_ajax` | `update_pricing_ajax` |
| `scheduling/` | `DriverSchedulingView` | `driver_scheduling` |
| `scheduling/request/` | `DriverRequestCreateView` | `driver_request_create` |
| `scheduling/request/<pk>/edit/` | `DriverRequestUpdateView` | `driver_request_edit` |
| `scheduling/action/<pk>/` | `driver_request_action` | `driver_request_action` |
| `scheduling/occupancy/` | `get_driver_occupancy` | `get_driver_occupancy` |
| `engineering/scheduling/` | `EngineerSchedulingView` | `engineer_scheduling` |
| `engineering/scheduling/new/` | `MaintenanceAssignmentCreateView` | `maintenance_assignment_create` |
| `engineering/scheduling/<pk>/edit/` | `MaintenanceAssignmentUpdateView` | `maintenance_assignment_update` |

---

## 📄 Document AI (`docai/`)

### 🧠 Views (`docai/views.py`)

| View | Description |
|------|-------------|
| `docai_home` | Landing page for document upload. |
| `summarize_document` | Handles file upload, creates `TenderSummary`, starts analysis thread. |
| `perform_analysis_task` | **Background Thread.** Extracts text → calls LLM → saves structured JSON to `TenderSummary`. |
| `analysis_progress_api` | Returns current status of a running analysis task. |
| `summary_detail` | Displays the generated tender summary. |
| `edit_summary` | Allows manual correction of AI-generated content. |
| `delete_summary` | Deletes a `TenderSummary` record. |

### 🗄️ Model (`docai/models.py`)

| Model | Description |
|-------|-------------|
| `TenderSummary` | Stores AI-extracted tender data. 27 fields covering tender metadata, financial, technical, and compliance sections. |

### 🛠️ Utilities (`docai/utils.py`)

| Function | Description |
|----------|-------------|
| `extract_text_from_file` | Dispatcher — determines file type and calls the appropriate extractor. |
| `extract_text_from_pdf` | Uses `PyPDF2` with page-by-page incremental loading. |
| `extract_text_from_docx` | Uses `python-docx`. |
| `extract_text_from_excel` | Uses `pandas` + `openpyxl`, sheet-by-sheet. |
| `extract_text_from_rtf` | Uses `striprtf`. |

### 🌐 URLs (`docai/urls.py`)

| Pattern | Name |
|---------|------|
| `docai/` | `docai:home` |
| `docai/summarize/` | `docai:summarize` |
| `docai/summary/<id>/` | `docai:detail` |
| `docai/summary/<id>/progress/` | `docai:progress_api` |
| `docai/summary/<id>/delete/` | `docai:delete` |
| `docai/summary/<id>/edit/` | `docai:edit` |

---

## ⚙️ Configuration (`config/`)

### `config/settings.py` Highlights

| Section | Detail |
|---------|--------|
| `INSTALLED_APPS` | core, docai, storages, debug_toolbar, webpush + Django defaults |
| Database | Supabase PostgreSQL via `dj_database_url` with PgBouncer pooling |
| Storage | Cloudflare R2 (S3-compatible) via `django-storages` |
| Caching | `LocMemCache` for dashboard stats; `cached_db` sessions |
| Context Processors | `core.context_processors.user_roles`, `core.context_processors.notification_counts` |
| Security | CSRF, XSS, HSTS, SSL redirect (production) |
| Web Push | VAPID keys from environment variables |

### `config/urls.py`

| Pattern | Target |
|---------|--------|
| `admin/` | Django admin |
| `accounts/` | Django built-in auth (login, logout, password) |
| `` | `core.urls` |
| `docai/` | `docai.urls` |
| `webpush/` | `webpush.urls` |
| `__debug__/` | debug_toolbar (DEBUG only) |

---

## 🎨 Frontend Architecture

**Tech Stack:** Django Server-Rendered HTML, Vanilla CSS, Vanilla JS.

### Templates (`templates/`)

| File | Purpose |
|------|---------|
| `base.html` | Global layout — sidebar, navbar, footer, notification badges |
| `registration/login.html` | Login page |
| `core/dashboard.html` | Main dashboard with stats cards |
| `core/report_form.html` | Service report create/edit — Signature Pad, ReportItem formset, equipment modals |
| `core/report_detail.html` | Service report read view |
| `core/report_list.html` | Filterable report list |
| `core/request_form.html` | Maintenance request create/edit |
| `core/request_detail.html` | Request read view with assignments and driver trips |
| `core/request_list.html` | Filterable request list |
| `core/driver_scheduling.html` | Driver calendar view |
| `core/driver_request_form.html` | Driver trip request form |
| `core/engineer_scheduling.html` | Engineer calendar view |
| `core/maintenance_assignment_form.html` | Engineer assignment form |
| `core/equipment_list.html` | Equipment registry table |
| `core/product_list.html` | Product catalogue table |
| `core/product_form.html` | Product create form |
| `core/product_create_modal.html` | Inline product creation modal (AJAX) |
| `core/equipment_selector_modal.html` | Equipment selection modal |
| `core/partials/driver_scheduling_partial.html` | AJAX partial for driver calendar |
| `core/partials/engineer_scheduling_partial.html` | AJAX partial for engineer calendar |
| `core/partials/request_cards_partial.html` | AJAX partial for request card grid |

### Static Assets (`static/`)

| Path | Purpose |
|------|---------|
| `css/styles.css` | Global styles — design tokens, layout, components |
| `js/service-worker.js` | PWA offline caching |
| `manifest.json` | PWA manifest |
| `img/medilab_logo.png` | App logo |
| `img/iso_logo.png` | ISO certification mark |
| `icons/icon-192x192.png` / `icon-512x512.png` | PWA icons |

---

## 🧩 Supporting Modules

| File | Purpose |
|------|---------|
| `core/context_processors.py` | `user_roles()` — session-cached role flags; `notification_counts()` — 60s TTL badge counts |
| `core/signals.py` | Cache invalidation when reports/requests are saved |
| `core/catalogue_data.py` | Static product catalogue constants used by `seed_product_catalogue` command |
| `core/management/commands/populate_mock_data.py` | Generates realistic test data |
| `core/management/commands/seed_product_catalogue.py` | Loads the product catalogue from `catalogue_data.py` |

---

## 📦 Dependencies (`requirements.txt`)

| Package | Purpose |
|---------|---------|
| Django ≥5.0 | Web framework |
| Pillow | Image processing, thumbnail generation |
| python-dotenv | `.env` file loading |
| gunicorn | Production WSGI server |
| whitenoise | Static file serving |
| psycopg2-binary | PostgreSQL driver |
| dj-database-url | Database URL parsing |
| django-storages[s3] | Cloud storage backend |
| boto3 | AWS/R2 S3 SDK |
| openai | OpenAI API (DocAI LLM calls) |
| google-generativeai | Google AI API (available, not primary) |
| PyPDF2 | PDF text extraction |
| python-docx | DOCX text extraction |
| pandas / openpyxl | Excel parsing |
| striprtf | RTF parsing |
| django-debug-toolbar | Dev debugging |
| django-webpush / pywebpush | Web push notifications |
