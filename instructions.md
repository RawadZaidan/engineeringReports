MVP BUILD PROMPT — Medilab (Engineering Department)
Objective (MVP Goal)

Build a minimum viable product (MVP) web application named Medilab for the Engineering Department to create, store, retrieve, and search service reports related to medical equipment and engineering activities.
The MVP must deliver immediate operational value, emphasize clarity, speed, and visual quality, and remain intentionally minimal while being fully functional.

Target Users

Engineering staff (primary creators)

Engineering managers (review, search, oversight)

Core Value Proposition

Provide a single, centralized, visually clean system for engineering service documentation that replaces manual reports with searchable, auditable, and well-presented digital records, including signatures and photo evidence.

Technical Constraints (Strict)

Backend: Django (monolithic project, Django ORM)

Database: SQLite (MVP default) or PostgreSQL-ready

Frontend:

Server-rendered HTML

Custom CSS (no frameworks unless absolutely necessary)

Vanilla JavaScript

Authentication: Django built-in authentication

Architecture: One Django project, minimal apps

Deployment-ready but environment-agnostic

MVP Functional Scope (Must-Have Features)
1. Service Report Management (Core Feature)

Users must be able to:

Create, view, edit, and retrieve Service Reports

View historical reports

Access detailed report pages

Service Report — Proposed MVP Data Model

Report ID (auto-generated)

Client / Facility Name

Location (City + Facility / Department)

Donor / Funding Source

Service Date (date + optional time)

Engineer (linked to authenticated user)

Product / Equipment (foreign key)

Issue Description

Work / Service Performed

Parts Used (free text or linked items)

Status (Draft / Completed / Pending)

Follow-up Required (boolean)

Client / Representative Name

Client Signature (drawn, stored as image)

Created At / Updated At

2. Signature Capture (New MVP Requirement)

Ability to draw a signature directly in the browser

Use a JavaScript canvas-based signature pad

Signature is saved as an image (PNG or Base64)

Signature is:

Attached to the service report

Displayed in the report detail view

Clear and re-draw option before submission

3. Photo Attachments (New MVP Requirement)

Ability to attach multiple photos to a service report

Photos may represent:

Equipment condition

Faults

Completed service work

Image upload requirements:

JPEG / PNG only

Size-limited (MVP-safe defaults)

Photos are:

Stored in Django media storage

Displayed as a clean gallery/grid in the report view

Clickable for full-size preview

4. Product & Equipment Registry

Users must be able to:

Create and manage a Product / Equipment database

Select products during service report creation

Product Model (MVP)

Product Name

Category (e.g., Lab Equipment, Diagnostics, Consumables)

Manufacturer

Model

Serial Number (optional)

Notes

Active / Inactive status

5. Search, Filter & Retrieval (High-Value Feature)

Users must be able to:

Search service reports by:

Client

Location

Donor

Product

Engineer

Status

Date range

Combine multiple filters (basic AND logic)

Results update efficiently

6. Dashboard & Card-Based UI

Service reports displayed in a tile/card layout

Each card shows:

Client

Location

Service Date

Status (visual indicator)

Product

Cards are clickable to full report view

Pagination or simple infinite scroll

UI / UX & Styling Requirements (High Priority)

Clean, modern, minimalistic design

Engineering/medical professional aesthetic

Consistent spacing, typography, and alignment

Neutral color palette with subtle accent colors

Visual hierarchy for readability

Clear form layouts optimized for fast data entry

Responsive layout (desktop-first, mobile-friendly)

No clutter, no unnecessary animations

Feedback states (success, error, validation)

Explicit MVP Non-Goals

Role-based access beyond basic authentication

External integrations

Notifications or emails

Advanced analytics

Multi-organization support

Multi-language support

Definition of Done (MVP Acceptance Criteria)

Engineers can create a complete service report including:

Equipment

Photos

Client signature

Reports are searchable and retrievable within seconds

UI is visually polished and professional

System is stable, usable, and deployable without refactoring

No placeholder or mock functionality

Assumptions

Internal departmental tool

Moderate data volume

Trust-based user environment

MVP designed for rapid iteration post-launch

Instruction to Builder

This is a single-pass MVP build.
Prioritize correctness, clarity, and polish over feature expansion.
All features included must be fully implemented—no stubs, no demos.
I placed an example of a dashboard design in the main folder called 'screen.png' to draw inspiration of the UI. 