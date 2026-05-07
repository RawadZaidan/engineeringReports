# AI Agent Assistance Guide — MedilabERP

Designed for AI agents navigating, understanding, and modifying MedilabERP efficiently.
Last updated: 2026-05-07

---

## Project Overview

**MedilabERP** is a Django-based internal web application for the Engineering Department. It manages:
- Service reports with signature capture and photo attachments
- Maintenance requests and scheduling
- Equipment and product catalogue
- Driver logistics / trip scheduling
- Engineer assignment scheduling
- AI-powered document (tender) analysis

> See [CODE_MAP.md](CODE_MAP.md) for the complete model/view/form/URL reference.

---

## Architecture & Stack

| Layer | Technology |
|-------|-----------|
| Backend | Django 5.0 (monolithic) |
| Database | Supabase PostgreSQL (production) |
| Frontend | Server-rendered HTML + Vanilla CSS + Vanilla JS |
| Cloud Storage | Cloudflare R2 (S3-compatible) via `django-storages` |
| Auth | Django built-in authentication |
| Caching | `LocMemCache` (dashboard stats, session roles) |
| Sessions | `cached_db` (persistent across restarts) |
| PWA | `service-worker.js` + `manifest.json` |
| Push Notifications | `django-webpush` + VAPID keys |
| Document AI | OpenAI API via background thread |

---

## Directory Map

```
MedilabERP/
├── config/          Django project (settings, root URLs)
├── core/            Main app — Reports, Requests, Scheduling, Equipment, Drivers, Engineers
├── docai/           Document AI app — Tender document analysis
├── templates/       HTML templates (base.html + per-app)
├── static/          CSS, JS, images, PWA assets
├── media/           User uploads (signatures, photos, driver photos, tender docs)
└── staticfiles/     collectstatic output (production)
```

---

## Key Logic & Systems

### 1. Role-Based Access & DriverRedirectMixin

`DriverRedirectMixin` (in `core/views.py`) is applied to all non-logistics views. Users in the **"Driver"** group are redirected to `/scheduling/` and cannot access reports, requests, or engineering pages.

`core/context_processors.py`:
- `user_roles()` — Session-cached flags: `is_engineer`, `is_driver`, `is_sales`, `is_procurement`.
- `notification_counts()` — 60-second TTL badge counts for pending driver requests and open maintenance requests.

---

### 2. Maintenance Request → Service Report Flow

When a user clicks **"Create Service Report"** from a `MaintenanceRequest` detail page, `request_id` is passed as a URL query param.

`ServiceReportCreateView` handles this in:
- `get_initial()` — Maps `facility_name`, `contact_name`, `contact_number`, `donor`, translates `billing_status` → `billing_category`, maps `service_type` selections.
- `get_context_data()` — Attempts to auto-match `Product` records from the request's `equipment_list` text and pre-fills `ReportItemFormSet`.

---

### 3. Signature Capture

- **Frontend:** HTML5 Canvas in `templates/core/report_form.html`. Draw → convert to Base64 → write into a hidden `<input>`.
- **Backend:** `ServiceReportCreateView.form_valid()` reads the Base64 string, converts it to a Django `ContentFile`, saves to `ServiceReport.client_signature` (uploaded to R2 `signatures/`).

---

### 4. Multi-Equipment Reports (Inline Formset)

- A `ServiceReport` has many `ReportItem` instances via inline formset.
- `ReportItemFormSet` (defined in `core/forms.py`) uses `BaseReportItemFormSet.clean()` to prevent duplicate equipment entries.
- Frontend: dynamic add/remove rows via a `<script>` block in `report_form.html` using Django's formset prefix approach.

---

### 5. Product AJAX Creation

Users can create a `Product` without leaving the report form:
- Frontend: `fetch()` call to `products/create-ajax/` inside a modal.
- Backend: `product_create_ajax` view returns JSON `{status, product_id, display_name}`.

Additional product AJAX endpoints allow cascading dropdowns: category → brand → model.

---

### 6. Driver Scheduling System

- `DriverRequest` links a `requester` (any staff) to a `Driver` for a specific `date`, `start_time`, `end_time`, `location`.
- Status flow: Pending → Approved / Denied / Edit Requested → Completed / Cancelled.
- `DriverSchedulingView` serializes monthly trip data as JSON for a calendar frontend.
- `get_driver_occupancy` returns availability for a given driver/month (used by the scheduling UI).
- `driver_request_action` handles approve/deny/complete actions (POST, `@login_required`).

---

### 7. Engineer Scheduling System

- `MaintenanceAssignment` links an `Engineer` to a `MaintenanceRequest` for a specific `date`, `start_time`, `end_time`.
- `MaintenanceAssignmentForm` validates:
  - Date falls within `MaintenanceRequest.availability_start` / `availability_end`.
  - No overlapping assignments for the same engineer on the same day.
- `EngineerSchedulingView` serializes monthly assignment data for the calendar frontend.

---

### 8. Cloudflare R2 Storage

All media files go to Cloudflare R2 (not local disk). Configured in `config/settings.py`.

**Required environment variables:**

| Variable | Purpose |
|----------|---------|
| `R2_ACCESS_KEY_ID` | R2 API authentication |
| `R2_SECRET_ACCESS_KEY` | R2 API secret |
| `R2_BUCKET_NAME` | Bucket name (e.g. "medilab") |
| `R2_ENDPOINT_URL` | R2 S3-compatible endpoint |
| `R2_PUBLIC_URL` | Public CDN URL for serving files |

**Upload paths:**
- Signatures → `signatures/`
- Report photos → `report_photos/`
- Thumbnails → `report_thumbnails/`
- Driver photos → `drivers/`
- Engineer photos → `engineers/`
- Tender docs → `tender_docs/`

---

### 9. Supabase PostgreSQL

**Required environment variable:** `DATABASE_URL` (connection string)

Uses `dj_database_url` with PgBouncer pooling config. Always run `python manage.py migrate` against the Supabase DB when making schema changes.

---

### 10. Document AI (Tender Analysis)

**Workflow:**
1. User uploads a file (PDF, DOCX, XLSX, RTF) at `/docai/`.
2. `summarize_document` creates a `TenderSummary` record and spawns a background thread.
3. `perform_analysis_task` extracts text (`docai/utils.py`) → sends to OpenAI → saves structured JSON to `TenderSummary`.
4. Frontend polls `analysis_progress_api` for completion status.

**Memory optimization:** Incremental page-by-page (PDF) / sheet-by-sheet (Excel) processing with explicit `del` calls after each chunk.

**Required env var:** `OPENAI_API_KEY`

---

### 11. Caching & Cache Invalidation

- Dashboard stats and notification counts use `LocMemCache` with short TTLs.
- `core/signals.py` fires cache invalidation on `ServiceReport` and `MaintenanceRequest` post-save/post-delete to keep badge counts fresh.

---

### 12. Security Configuration

| Setting | Detail |
|---------|--------|
| `SECRET_KEY` | From `.env`, never hardcoded |
| `DEBUG` | Controlled by `DEBUG` env var (default: False in production) |
| HTTPS | `SECURE_SSL_REDIRECT`, `HSTS` enabled in production |
| Session Cookies | `SESSION_COOKIE_SECURE = True` in production |
| AJAX | All mutation endpoints protected with `@login_required` |
| CSRF | Enabled on all forms and AJAX POST calls |

---

## How to Locate Things

| What you need | Where to look |
|---------------|--------------|
| Models | `core/models.py` |
| Business logic | `core/views.py`, `core/forms.py` |
| URL routes | `core/urls.py`, `config/urls.py` |
| Global styles | `static/css/styles.css` |
| Page-specific styles | `<style>` blocks inside the relevant template |
| Global config | `config/settings.py` |
| Role/notification logic | `core/context_processors.py` |
| Cache invalidation | `core/signals.py` |
| Product seed data | `core/catalogue_data.py` |
| DocAI text extraction | `docai/utils.py` |

---

## Common Workflows

### Add a Field to ServiceReport

1. Update `ServiceReport` in `core/models.py`.
2. `python manage.py makemigrations && python manage.py migrate`.
3. Update `ServiceReportForm` in `core/forms.py`.
4. Update `report_form.html` and `report_detail.html`.

### Add a New AJAX Endpoint

1. Write the view function in `core/views.py` (decorate with `@login_required`, `@require_POST` / `@require_GET`).
2. Register it in `core/urls.py`.
3. Call it via `fetch()` in the relevant template, including the CSRF token header.

### Modify the Scheduling Calendar

- Driver calendar: `DriverSchedulingView.get_context_data()` → `driver_scheduling.html`.
- Engineer calendar: `EngineerSchedulingView.get_context_data()` → `engineer_scheduling.html`.
- Both serialize assignments/trips as JSON injected into a `<script>` block for the JS calendar.

### Change a Form's Allowed Fields by Role

- `MaintenanceRequestForm.__init__()` already gates fields by `user` arg.
- Pass the request user when instantiating: `form = MaintenanceRequestForm(user=self.request.user)`.

### Maintaining the Design System

Follow the existing "premium, minimalistic" aesthetic:
- Color palette: blues, greys, whites.
- Subtle shadows and clean horizontal dividers.
- Check `base.html` for CSS custom properties (design tokens).
- Add page-specific overrides in `<style>` blocks; only touch `styles.css` for global changes.

---

## Maintaining This Guide

This is a living document. When a feature is added, an architectural decision changes, or a non-obvious behavior is discovered:

1. Update **Directory Map** if new apps or folders are added.
2. Update **Key Logic & Systems** for new complex systems.
3. Update **Common Workflows** if a process changes.
4. Bump the **Last updated** date at the top.

**Rule:** After completing any non-trivial task, verify whether this file needs an update.
