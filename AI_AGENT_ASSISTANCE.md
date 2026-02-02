# AI Agent Assistance Guide - Medilab Maintenance DB

This document is designed to help AI agents (like Antigravity) navigate, understand, and modify the Medilab Maintenance Database codebase efficiently.

## 🚀 Project Overview
**Medilab** is a Django-based MVP for the Engineering Department to manage service reports, maintenance requests, and equipment inventory. It features signature capture, photo attachments, and a premium, minimalistic aesthetic.

---

## 🏗️ Architecture & Stack
- **Backend:** Django 5.0 (Monolithic)
- **Database:** SQLite (default)
- **Frontend:** Server-rendered HTML, Vanilla CSS (custom), Vanilla JS.
- **Key Dependencies:** Pillow (Images), python-dotenv (Config), Whitenoise (Static files), boto3 (Cloud Storage), django-storages (R2 Integration).
- **Cloud Storage:** Cloudflare R2 (S3-compatible) for media files.

---

## 📂 Directory Structure Highlights

### `config/`
- `settings.py`: Core configuration, including `MEDIA_URL` and `STATIC_URL`.
- `urls.py`: Main routing. Includes `core.urls` and media serving configuration.

### `core/` (Main App)
- `models.py`:
  - `Product`: (Catalogue) Stores templates/blueprints (Manufacturer, Model).
  - `Equipment`: (Registry) Stores specific physical units (FK to Product + Serial Number).
  - `ServiceReport`: Main report model (linked to engineer/user).
  - `ReportItem`: Intersection linking Report to a specific `Equipment` instance.
  - `ReportImage`: Associated photos.
  - `MaintenanceRequest`: High-level service requests.
  - `MaintenanceRequestEquipment`: Links requests to specific `Equipment` instances.
- `views.py`: Class-based views for most CRUD operations. 
  - *Note:* Base64 signature processing happens in `form_valid` of `ServiceReportCreateView` and `ServiceReportUpdateView`.
- `forms.py`: Custom Django forms and formsets (`ReportItemFormSet`, `MaintenanceRequestEquipmentFormSet`).

### `templates/`
- `base.html`: Global layout, navigation, and sidebar.
- `core/`:
  - `dashboard.html`: Analytics and recent reports.
  - `report_form.html`: Complex form with Signature Pad (Canvas API) and Inline Formsets.
  - `report_detail.html`: Final rendered report with signature and image gallery.

### `static/`
- `css/`: Custom styling. Look here for design tokens and "premium" look logic.
- `js/`: Utility scripts (e.g., `service-worker.js` for PWA capabilities).

---

## 🔧 Key Logic & Features

### 1. Signature Capture
- **Frontend:** Located in `templates/core/report_form.html`. Uses HTML5 Canvas.
- **Backend:** Processed in `core/views.py`. Converts Base64 data from a hidden input into a Django `ContentFile`.

### 2. Multi-Equipment Reports
- A `ServiceReport` can have multiple `ReportItem` instances.
- Implementation uses Django **Inline Formsets**. 
- Adding items dynamically on the frontend is handled via a `<script>` block in `report_form.html` using a template literal/prefix approach.

### 3. Product Creation AJAX
- Users can create a `Product` without leaving the `ServiceReport` form.
- Logic is in `report_form.html` (JS `fetch`) and `core/views.py` (`product_create_ajax`).

### 4. Maintenance Request to Service Report Mapping
- Clicking **"Create Service Report"** from a Maintenance Request detail page passes `request_id` in the URL.
- `ServiceReportCreateView` handles this in:
    - `get_initial()`: Maps client info, contact details, donor, and translates `billing_status` to `billing_category`. **New:** It also maps the `service_type` selections from the request to the report.
    - `get_context_data()`: Attempts to auto-match `Product` records based on the equipment type/model strings in the request and pre-fills the `ReportItemFormSet`.



### 5. Cloudflare R2 Cloud Storage
- **Purpose:** All media files (signatures, report photos, tender documents) are stored in Cloudflare R2 instead of the local filesystem.
- **Configuration:** Located in `config/settings.py` under "Cloudflare R2 Storage Configuration".
- **Environment Variables Required:**
    - `R2_ACCESS_KEY_ID`: Access key for R2 API authentication
    - `R2_SECRET_ACCESS_KEY`: Secret key for R2 API authentication
    - `R2_BUCKET_NAME`: Name of the R2 bucket (e.g., "medilab")
    - `R2_ENDPOINT_URL`: R2 endpoint URL for API calls
    - `R2_PUBLIC_URL`: Public URL for accessing uploaded files
- **Storage Backend:** Uses `django-storages` with S3-compatible backend (`storages.backends.s3boto3.S3Boto3Storage`)
- **Public Access:** The R2 bucket must have public read access enabled in Cloudflare dashboard for files to be viewable.
- **Media Files Affected:** 
    - `ServiceReport.client_signature` → `signatures/`
    - `ReportImage.image` → `report_photos/`
    - `TenderDocument.document` → `tender_docs/`

---

---

## 🔍 How to Locate Things

- **Models:** Always check `core/models.py`.
- **Business Logic:** Primarily in `core/views.py` and `core/forms.py`.
- **Styling:** Main layout styles are in `static/css/`. Page-specific styles are often in `<style>` blocks within the template.
- **Global Config:** `config/settings.py`.

---

## 🛠️ Common Workflows for AI

### Adding a New Field to a Report
1. Update model in `core/models.py`.
2. Run `python manage.py makemigrations` and `python manage.py migrate`.
3. Update `ServiceReportForm` in `core/forms.py`.
4. Update `report_form.html` and `report_detail.html`.

### Modifying the Aesthetics
- The project follows a "premium" design language. Ensure horizontal lines, subtle shadows, and a clean color palette (Blues/Greys/Whites) are maintained.
- Check `base.html` for the global design system.

---

## 🔄 Maintaining This Guide
**This guide is a living document.** 
When you add a new feature, change an architectural decision, or find a nuance in the code that isn't documented:
1. **Update the Directory Structure** if new folders/apps are added.
2. **Add to Key Logic & Features** if a new complex system is implemented.
3. **Update Common Workflows** if a process changes.
**CRITICAL:** Every time you complete a task, verify if `AI_AGENT_ASSISTANCE.md` needs an update to reflect the new state of the project.

