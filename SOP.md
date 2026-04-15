---
name: sop-designer
description: Standard Operating Procedure (SOP) designer — produces professionally structured, visually polished SOP documents in HTML (printable/interactive), PDF, or DOCX format. Use this skill whenever the user asks to create, write, format, or design an SOP, work instruction, process document, procedure manual, operational guide, runbook, or protocol. Trigger for ANY context: clinical/medical SOPs, NGO program SOPs (EPA/PSS sessions), procurement workflows, IT/dev runbooks, HR procedures, supplier onboarding, tender response procedures, lab protocols, or internal business processes. Even if the user just says "write me a procedure for X" — use this skill. Output should always be structured, role-aware, version-controlled, and print-ready.
---

# SOP Designer

Produces professionally structured Standard Operating Procedures with consistent anatomy, visual hierarchy, and role clarity — regardless of domain.

---

## SOP ANATOMY (Always Follow This Structure)

Every SOP produced must contain these sections, in this order:

### Header Block
```
Document Title:    [Procedure Name]
Document Code:     [ORG-DEPT-###]  e.g. EPA-PSS-001 / MED-PROC-014
Version:           [v1.0]
Effective Date:    [DD Month YYYY]
Review Date:       [DD Month YYYY + 12 months]
Owner:             [Role, not person name]
Approved By:       [Role]
Classification:    [Internal / Confidential / Public]
```

### 1. Purpose
One paragraph. Answers: *Why does this procedure exist?*
Start with: "This SOP establishes..." or "The purpose of this procedure is to..."

### 2. Scope
Who and what this applies to. What it does NOT cover (explicitly state exclusions).
Format: short bullets or two-sentence paragraph.

### 3. Definitions & Abbreviations
Table format:
| Term | Definition |
|------|-----------|
| ... | ... |

Only include terms that are non-obvious or domain-specific.

### 4. Roles & Responsibilities
RACI-style table or simple role description:
| Role | Responsibility in this procedure |
|------|----------------------------------|
| ... | ... |

### 5. Materials / Equipment / Prerequisites
What must exist before starting:
- Documents needed
- Access/permissions required
- Physical materials
- System states

### 6. Procedure Steps
**This is the core section. Format strictly:**

Each step = numbered, action-verb first, one task per step.

```
Step 1: [Action verb] + [object] + [condition/qualifier if needed]
        ▸ Detail: [Additional instruction or warning if needed]
        ▸ If [condition]: [alternate path → go to Step X]

Step 2: ...
```

**For complex procedures with sub-phases:**
```
PHASE A — [Phase Name]
  Step 1: ...
  Step 2: ...

PHASE B — [Phase Name]
  Step 3: ...
```

**Decision points:**
```
Step N: Check [condition]
        ▸ YES → Proceed to Step N+1
        ▸ NO  → Go to Step N+3 / Escalate to [Role]
```

### 7. Quality Checks / Verification Points
What to verify at key milestones. Who verifies. How.

### 8. Non-Conformance / Exception Handling
What to do when the procedure cannot be followed as written.
Who to escalate to. How to document the deviation.

### 9. Records & Documentation
What documents/logs must be created or updated as a result of this procedure.
Where they are stored. Retention period.

### 10. References
Related SOPs, standards, regulations, or templates referenced.

### 11. Revision History
| Version | Date | Author (Role) | Change Summary |
|---------|------|--------------|----------------|
| v1.0 | [date] | [role] | Initial release |

---

## OUTPUT FORMAT SELECTION

Choose output format based on context:

### HTML (default — best for interactive/printable)
Use `web-artifacts-builder` approach or direct HTML.
Apply this design philosophy:
- Clean Swiss-grid layout, A4-proportioned
- Color scheme: white background, dark navy headings (`#0f172a`), amber accent (`#f59e0b`) for step numbers and phase headers — aligns with EVA Ops / Medilab professional aesthetic
- Typography: `font-family: 'Segoe UI', system-ui, sans-serif` — no Inter, no generic AI defaults
- Step numbers in amber circles
- Phase headers as full-width dark navy bands
- Warning/caution boxes in amber-tinted background
- Print-ready: `@media print` CSS included, page breaks before major phases
- Version/header block as a formal bordered table at the top

```html
<!-- Core CSS pattern -->
<style>
  :root {
    --navy: #0f172a;
    --amber: #f59e0b;
    --amber-light: #fef3c7;
    --gray-50: #f8fafc;
    --gray-200: #e2e8f0;
    --text: #1e293b;
  }
  body { font-family: 'Segoe UI', system-ui, sans-serif; max-width: 900px;
         margin: 0 auto; padding: 2rem; color: var(--text); }
  .sop-header { border: 2px solid var(--navy); padding: 1.5rem;
                margin-bottom: 2rem; background: var(--gray-50); }
  .section-title { color: var(--navy); border-bottom: 3px solid var(--amber);
                   padding-bottom: 0.5rem; margin-top: 2rem; }
  .phase-header { background: var(--navy); color: white; padding: 0.75rem 1.5rem;
                  margin: 1.5rem -1rem; font-weight: 700; letter-spacing: 0.05em; }
  .step { display: flex; gap: 1rem; margin: 1rem 0; align-items: flex-start; }
  .step-num { background: var(--amber); color: var(--navy); font-weight: 800;
              min-width: 2rem; height: 2rem; display: flex; align-items: center;
              justify-content: center; border-radius: 50%; flex-shrink: 0; }
  .step-detail { background: var(--gray-50); border-left: 3px solid var(--amber);
                 padding: 0.5rem 1rem; margin-top: 0.5rem; font-size: 0.9em; }
  .decision { background: var(--amber-light); border: 1px solid var(--amber);
              padding: 1rem; margin: 0.5rem 0; border-radius: 4px; }
  .roles-table, .rev-table { width: 100%; border-collapse: collapse; }
  .roles-table th, .rev-table th { background: var(--navy); color: white; padding: 0.75rem; }
  .roles-table td, .rev-table td { border: 1px solid var(--gray-200); padding: 0.75rem; }
  @media print {
    .phase-header { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
    .step-num { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
    h2 { page-break-before: always; }
  }
</style>
```

### PDF
Use `pdf` skill (WeasyPrint via Python).
Apply the same design tokens above via CSS, then convert HTML → PDF.
Reference: `/mnt/skills/public/pdf/SKILL.md`

### DOCX
Use `docx` skill for Word-compatible output.
Reference: `/mnt/skills/public/docx/SKILL.md`


## QUALITY RULES

1. **Action verbs only** — every step starts with a verb: Verify, Submit, Record, Notify, Escalate, Review, Upload, Archive
2. **One action per step** — never combine two tasks in one step
3. **No passive voice in steps** — "John submits the form", not "the form is submitted"
4. **Explicit roles** — every step specifies WHO does it if multiple roles exist
5. **No ambiguity in conditionals** — every IF has an explicit THEN and ELSE
6. **Version control always** — even v1.0 documents need revision history
7. **No orphaned steps** — every decision branch must resolve back to the main flow or terminate explicitly

---

## WORKFLOW

1. Ask user for: process name, domain/context, audience (who will follow it), approx. number of steps/phases
2. If user has an existing draft or notes — read them first, extract structure, fill gaps
3. Draft SOP following the anatomy above
4. Choose output format (HTML default unless user specifies)
5. Render and present
6. Offer: "Want me to add a flowchart diagram for the decision points?"

---

## FLOWCHART OPTION

When requested, produce an ASCII or SVG process flowchart after the SOP body:
- Use the `visualize:show_widget` tool for inline SVG flowcharts
- Map: Start → Phase A steps → Decision diamond → Phase B steps → End
- Color: navy boxes for process steps, amber diamonds for decisions, gray for start/end

---

## CRITICAL DEFAULTS

- Document code format: `[ORG]-[DEPT]-[###]` — always include, even if user didn't specify
- Review date: always 12 months from effective date unless stated otherwise
- Version: always start at `v1.0` for new documents
- Owner: always a role, never a personal name (people change, roles persist)
- Never produce an SOP without a header block — it's not a real SOP without it