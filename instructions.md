# MedilabERP — Product Requirements & Build Specification

This document captures the original MVP goals and all requirements added since launch.
Last updated: 2026-05-07

---

## Product Overview

**MedilabERP** is an internal web application for the Engineering Department to manage the full lifecycle of medical equipment service events — from inbound maintenance requests to completed service reports — including scheduling, logistics, and document analysis.

**Target Users:**
- Engineering staff (primary report creators)
- Engineering managers (oversight, scheduling, pricing approval)
- Drivers (logistics trip management only)

**Core Value:** A single, centralized, visually clean system that replaces manual paperwork with searchable, auditable digital records.

---

## Technical Constraints (Strict)

| Constraint | Value |
|-----------|-------|
| Backend | Django 5.0 (monolithic, Django ORM) |
| Database | PostgreSQL (Supabase) |
| Frontend | Server-rendered HTML, custom CSS, vanilla JS |
| Authentication | Django built-in authentication |
| Architecture | One Django project, minimal apps (`core`, `docai`) |
| Storage | Cloudflare R2 for all media files |
| Deployment | Gunicorn + Whitenoise, environment-agnostic via `.env` |

---

## Feature Requirements

### 1. Service Report Management

Users must be able to create, view, edit, and search service reports.

**Service Report fields:**
- Auto-generated Report ID
- Client / Facility Name
- Project Reference
- Location (Lebanon region)
- Donor / Funding Source
- Service Date (datetime)
- Engineer (linked to authenticated user)
- Equipment items (multiple, via formset)
- Issue Description
- Work / Service Performed
- Parts Used
- Service Type (multi-select: Preventive, Corrective, Installation, etc.)
- Billing Category (multi-select: Warranty, Billable, Contract, FOC)
- Final Status (multi-select)
- Report Status (Draft / Pending Review / Completed)
- Follow-up Required (boolean)
- Warranty activation option + duration
- Client Representative Name + Phone
- Client Signature (canvas-drawn, stored as image)
- Created At / Updated At

---

### 2. Signature Capture

- Draw signature directly in the browser using HTML5 Canvas.
- Clear and re-draw option before submission.
- Signature saved as PNG image, attached to the service report.
- Displayed in the report detail view.

---

### 3. Photo Attachments

- Attach multiple photos to a service report.
- JPEG / PNG only, size-limited.
- Thumbnails generated automatically.
- Photos stored in Cloudflare R2 (`report_photos/`, `report_thumbnails/`).
- Displayed as a clean gallery grid in the report view, clickable for full-size preview.

---

### 4. Product & Equipment Registry

**Product (catalogue blueprint):**
- Name, Category, Manufacturer, Model, Notes
- Unique on (Manufacturer, Model)

**Equipment (physical instance):**
- Linked to a Product
- Serial Number, Current Facility, Current Location
- Installation Date, Warranty Expiration Date, Notes

Users can create Products inline from within the Service Report form via an AJAX modal.

---

### 5. Maintenance Request Management

Capture inbound service requests before a report is created.

**Maintenance Request fields:**
- Customer Contact Date
- Availability Window (start / end dates)
- Urgency (Low / Medium / High / Emergency)
- Contact Name, Number, Email
- Facility Name
- Location (Lebanon region — detailed nested choices across 8 regions)
- Donor
- Equipment List (free text)
- Request Details
- Service Type
- Billing Status (Warranty / Billable / Contract / FOC)
- Estimated Cost (set by authorized users with timestamp)
- Status (Open → Scheduled → In Progress → Completed / Cancelled)
- Equipment line items (formset)

A **"Create Service Report"** button on the request detail page pre-fills the report form by mapping all relevant request fields automatically.

---

### 6. Driver / Logistics Scheduling

Manage driver trip requests for field visits.

**Driver Request fields:**
- Requesting staff member
- Driver assignment
- Linked Maintenance Request (optional)
- Department (Engineering / Sales / Procurement / Management)
- Location (Lebanon region)
- Client Name, Contact Person, Contact Number
- Date, Start Time, End Time (30-min increments, 6 AM–6 PM)
- Vehicle Type (Truck / Car / Moto)
- Estimated Distance, Duration
- Status: Pending → Approved / Denied / Edit Requested → Completed / Cancelled
- Admin Notes

**Driver Profile:** Name, photo, license info, active status, linked user account.

**Access Control:** Users in the "Driver" group can only access the scheduling module. All other pages redirect them to `/scheduling/`.

---

### 7. Engineer Scheduling

Assign engineers to maintenance requests on a calendar.

**Engineer Assignment fields:**
- Engineer
- Linked Maintenance Request
- Date (must fall within request availability window)
- Start / End Time (30-min increments, validated for conflicts)
- Notes

**Engineer Profile:** Name, photo, specialization, active status, linked user account.

---

### 8. Search, Filter & Retrieval

Users must be able to search and filter:
- Service reports by: client, location, donor, engineer, status, date range, service type
- Maintenance requests by: facility, urgency, status, billing status, date range
- Results use AND logic across combined filters.
- Saved filter presets: users can save, name, and set a default filter for both reports and requests.

---

### 9. Dashboard

- Stat cards: total reports, open requests, pending driver trips, recent activity.
- Recent service reports and maintenance requests.
- Notification badges in the navigation for pending actions.
- Badge counts are cached (60-second TTL) and invalidated on save via Django signals.

---

### 10. Document AI — Tender Analysis

AI-powered analysis of uploaded tender documents.

**Supported formats:** PDF, DOCX, XLSX, RTF

**Workflow:**
1. User uploads document at `/docai/`.
2. Text is extracted incrementally (page/sheet-by-sheet for memory efficiency).
3. OpenAI API structures the tender data as JSON.
4. Result saved to `TenderSummary` model (27 fields).
5. User views, edits, or deletes the generated summary.

**Memory optimization:** Explicit `del` after each page/sheet, `MemoryError` handled gracefully.

---

### 11. Cloud Storage (Cloudflare R2)

All user-uploaded media stored in Cloudflare R2:
- `signatures/` — Client signatures
- `report_photos/` / `report_thumbnails/` — Report photos
- `drivers/` — Driver profile photos
- `engineers/` — Engineer profile photos
- `tender_docs/` — Uploaded tender documents

Requires a publicly accessible R2 bucket and environment variables:
`R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_NAME`, `R2_ENDPOINT_URL`, `R2_PUBLIC_URL`

---

### 12. Web Push Notifications

Push notifications delivered via `django-webpush` (VAPID protocol).
Used for notifying drivers of request approvals/denials and staff of new requests.

---

### 13. Progressive Web App (PWA)

- Installable on desktop and mobile.
- Offline caching via `service-worker.js`.
- App manifest with icons (192×192, 512×512).

---

### 14. Security Requirements

- All views require authentication (`LoginRequiredMixin` / `@login_required`).
- Mutation AJAX endpoints use `@login_required` and CSRF protection.
- `SECRET_KEY` loaded from `.env`, never hardcoded.
- Production: `DEBUG=False`, HTTPS redirect, HSTS, secure session cookies.
- XSS and clickjacking protection headers enabled.

---

## UI / UX Requirements

- **Aesthetic:** Premium, minimalistic, engineering/medical professional tone.
- **Color palette:** Blues, greys, whites — subtle accent colors only.
- **Layout:** Sidebar navigation + top navbar. Card-based content areas.
- **Typography:** Clean, consistent spacing and visual hierarchy.
- **Responsiveness:** Desktop-first, mobile-friendly.
- **Forms:** Optimized for fast data entry; clear validation feedback.
- **No clutter:** No unnecessary animations, no placeholder UI.
- **Feedback states:** Success, error, and validation messages on all forms.

---

## Non-Goals (Explicitly Out of Scope)

- Role-based access beyond the Engineer / Driver / Staff distinction
- External integrations (ERP, LIMS, billing systems)
- Email / SMS notifications
- Advanced analytics or BI dashboards
- Multi-organization / multi-tenant support
- Multi-language support

---

## Definition of Done

- All listed features are fully implemented — no stubs, no mock data in production.
- Engineers can create a complete service report (equipment + photos + signature) end-to-end.
- Reports and requests are searchable and retrievable within seconds.
- UI is visually polished and consistent with the design system.
- Application is stable and deployable without code changes (config via `.env`).
- All database migrations are applied and schema is in sync.
