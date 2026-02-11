# AI Agent Assistance Guide - Medilab Maintenance DB

This document is designed to help AI agents (like Antigravity) navigate, understand, and modify the Medilab Maintenance Database codebase efficiently.

## 🚀 Project Overview
**Medilab** is a Django-based MVP for the Engineering Department to manage service reports, maintenance requests, and equipment inventory. It features signature capture, photo attachments, and a premium, minimalistic aesthetic.

---

## 🏗️ Architecture & Stack
- **Backend:** Django 5.0 (Monolithic)
- **Database:** Supabase PostgreSQL (Production)
- **Frontend:** Server-rendered HTML, Vanilla CSS (custom), Vanilla JS.
- **Key Dependencies:** Pillow (Images), python-dotenv (Config), Whitenoise (Static files), boto3 (Cloud Storage), django-storages (R2 Integration), psycopg2-binary (PostgreSQL).
- **Cloud Storage:** Cloudflare R2 (S3-compatible) for media files.

---

## 📂 Directory Structure Highlights

> **See [CODE_MAP.md](CODE_MAP.md) for a detailed breakdown of models, views, and functions.**

### `config/`
- `settings.py`: Core configuration.
- `urls.py`: Main routing.

### `core/` (Main App)
- Contains the primary business logic for Reports, Equipment, and Requests.
- Key files: `models.py`, `views.py`, `forms.py`, `urls.py`.

### `docai/` (Document AI)
- Handles AI-powered document summarization (Gemini/OpenAI).
- Key files: `views.py` (Analysis logic), `utils.py` (Text extraction).

### `templates/`
- `base.html`: Global layout.
- `core/`: Dashboard and Report forms.
- `docai/`: Document upload and summary views.

### `static/`
- `css/`: Custom styling.
- `js/`: Utility scripts (e.g., `service-worker.js`).

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

### 6. Supabase PostgreSQL Database
- **Purpose:** Primary database for the application.
- **Configuration:** Located in `config/settings.py` using `dj_database_url`.
- **Environment Variables:**
    - `DATABASE_URL`: Connection string for Supabase PostgreSQL.
- **Notes:** 
    - Migrations must be run against this database (`python manage.py migrate`).
    - The project uses `psycopg2-binary` as the adapter.

### 7. Security Configuration
- **SECRET_KEY**: Loaded from `.env` file (never hardcoded).
- **DEBUG**: Controlled via `DEBUG` environment variable (default: `False` in production).
- **Security Headers**: XSS filter, content-type sniffing protection, clickjacking protection.
- **Session Security**: Secure cookies enabled in production.
- **HTTPS**: SSL redirect and HSTS enabled in production.
- **Authentication**: AJAX endpoints protected with `@login_required`.

### 8. Document AI Analysis
- **Workflow:** User uploads a document (PDF, DOCX, etc.) → Backend extracts text (`docai/utils.py`) → Background Thread (`perform_analysis_task`) calls LLM → Result saved to `TenderSummary`.
- **Text Extraction:** Uses `PyPDF2` (memory-efficient), `python-docx`, `pandas`, and `striprtf` to normalize text from various formats.
- **Memory Optimization:** 
    - **Full Document Processing:** Processes entire documents without page/sheet limits
    - **Incremental Processing:** Page-by-page (PDF) and sheet-by-sheet (Excel) to minimize memory footprint
    - **Explicit Memory Cleanup:** Uses `del` to free memory after processing each page/sheet
    - **Progress Logging:** Logs progress every 10 pages (PDF) or 5 sheets (Excel) for large documents
    - **Graceful Error Handling:** Catches MemoryError with user-friendly messages
- **LLM Integration:** Uses OpenAI/Gemini API (via `openai` client) to structure the tender data which is then saved as JSON.

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

