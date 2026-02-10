import os
import json
import base64
import logging
import traceback
import threading
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from openai import OpenAI
from .models import TenderSummary
from .utils import extract_text_from_file

logger = logging.getLogger(__name__)

# Configure OpenAI
client = None
if settings.OPENAI_API_KEY:
    client = OpenAI(api_key=settings.OPENAI_API_KEY)

@login_required
def docai_home(request):
    summaries = TenderSummary.objects.all()
    
    # Filtering logic
    donor = request.GET.get('donor')
    continent = request.GET.get('continent')
    category = request.GET.get('category')
    
    if donor:
        summaries = summaries.filter(donor__icontains=donor)
    if continent:
        summaries = summaries.filter(continent=continent)
    if category:
        summaries = summaries.filter(category=category)
    
    # Get unique values for filters
    donors = TenderSummary.objects.values_list('donor', flat=True).distinct()
    donors = [d for d in donors if d]
    
    continents = TenderSummary.objects.values_list('continent', flat=True).distinct()
    continents = [c for c in continents if c]
    
    context = {
        'summaries': summaries,
        'donors': sorted(donors),
        'continents': sorted(continents),
        'categories': dict(TenderSummary._meta.get_field('category').choices),
        'current_filters': {
            'donor': donor,
            'continent': continent,
            'category': category
        }
    }
    return render(request, 'docai/home.html', context)

@login_required
def summarize_document(request):
    if request.method == 'POST':
        # Support both single and multiple file uploads
        documents = request.FILES.getlist('documents')
        if not documents:
            # Fallback to single document field for backward compatibility
            documents = [request.FILES.get('document')] if request.FILES.get('document') else []
        
        if not documents:
            messages.error(request, "Please select at least one document to analyze.")
            return redirect('docai:home')
        
        # Use the first document as the primary document for storage
        primary_document = documents[0]
        summary_obj = TenderSummary.objects.create(
            user=request.user,
            document=primary_document,
            status='processing',
            current_step="Reading document content...",
            analysis_progress=5
        )
        
        if not client:
            summary_obj.status = 'failed'
            summary_obj.failure_reason = "OpenAI API key not configured (OPENAI_API in .env)"
            summary_obj.save()
            messages.error(request, "AI service not configured.")
            return redirect('docai:home')

        # Extract text/bytes synchronously first, because file handles close after request
        pre_extracted_text = ""
        image_attachments = [] # List of (mime_type, base64_data)
        
        for idx, document in enumerate(documents, 1):
            extracted = extract_text_from_file(document)
            if extracted:
                if idx > 1:
                    pre_extracted_text += f"\n\n{'='*50}\n--- Document {idx}: {document.name} ---\n{'='*50}\n\n"
                else:
                    pre_extracted_text += f"--- Document {idx}: {document.name} ---\n\n"
                pre_extracted_text += extracted
            else:
                # Handle as image
                try:
                    document.seek(0)
                    file_data = document.read()
                    base64_image = base64.b64encode(file_data).decode('utf-8')
                    mime_type = document.content_type or "image/jpeg"
                    image_attachments.append((mime_type, base64_image))
                except Exception as e:
                    logger.error(f"Error reading image {document.name}: {e}")

        # Run analysis in background
        thread = threading.Thread(
            target=perform_analysis_task, 
            args=(summary_obj.id, pre_extracted_text, image_attachments)
        )
        thread.start()
        
        return redirect('docai:detail', summary_id=summary_obj.id)
            
    return redirect('docai:home')

def perform_analysis_task(summary_id, pre_extracted_text, image_attachments):
    """Background task to perform document analysis and update progress."""
    from django.db import connection
    
    try:
        summary_obj = TenderSummary.objects.get(id=summary_id)
        
        # 1. Update progress
        summary_obj.current_step = "Analyzing with gpt-5-nano (this may take 10-20s)..."
        summary_obj.analysis_progress = 50
        summary_obj.save()

        EXTRACTION_PROMPT = """
ROLE: Senior Procurement Auditor with 15+ years analyzing tender documents

TASK: Extract structured data with 99%+ accuracy. Every field matters for bid/no-bid decisions.

═══════════════════════════════════════════════════════════════════════

CARDINAL RULES (READ TWICE):
✓ Extract ONLY what is explicitly written - zero assumptions
✓ "Not specified" is better than guessing
✓ Cross-reference all pages/documents before marking "Not specified"
✓ Preserve exact numbers, dates, and terminology from source
✓ When multiple values exist (e.g., multiple deadlines), capture ALL of them
✓ When in doubt about a requirement being mandatory, mark it as present (false positive safer than false negative)

═══════════════════════════════════════════════════════════════════════

### 1. TARGET DOCUMENTS CHECKLIST
For EACH category below, search for these terms AND their variations throughout ALL documents:

**Legal/Identity Documents:**
- Commercial Registry: also search "business registration", "company registration", "certificate of incorporation", "trade license"
- Tax Compliance: also search "tax clearance", "tax certificate", "fiscal compliance", "IRS clearance", "tax good standing"
- VAT Registration: also search "value added tax", "sales tax registration", "TIN certificate", "tax identification"
- Power of Attorney: also search "authorization letter", "signatory authority", "legal representative", "notarized authorization"

**International Registrations:**
- UNGM Vendor ID: also search "UN Global Marketplace", "UNGM registration", "UN vendor number"
- Portal Registrations: search "UNOPS registered", "GIZ portal", "World Bank registration", "e-procurement registration"

**Quality/Technical Certifications:**
- Certificate of Origin: **CRITICAL** - search "COO", "C.O.O.", "country of origin", "manufacturing origin", "goods origin certificate", "origin declaration"
- ISO Certifications: search "quality management", "ISO-9001", "ISO 9001", "ISO9001", "environmental certification", "ISO-14001", "ISO 13485", "quality certification"
- Manufacturer Authorization: search "OEM letter", "brand authorization", "dealership certificate", "authorized distributor", "manufacturer's letter", "authorization from principal"

**Financial Documents:**
- Audited Financial Statements: also search "audited accounts", "financial reports", "balance sheet", "P&L statement", "annual accounts"
- Credit Facilities: also search "bank credit line", "credit letter", "banking facilities", "financial capacity letter"

═══════════════════════════════════════════════════════════════════════

### 2. EXTRACTION REQUIREMENTS

**A. ENTITY IDENTIFICATION**
Search order: Cover page → Header → Footer → "About the Buyer" section → Signature blocks

- **procuring_entity**: Full official legal name (not abbreviations unless only abbreviation provided)
  * Search terms: "procuring entity", "buyer", "purchaser", "contracting authority", "client", "employer"
  
- **donor_entity**: Funding organization
  * Search terms: "Funded by", "Financial Support from", "Grant from", "Donor", "Financing by"
  * Check: Header logos, footer text, cover page acknowledgments

- **Country & Location**: 
  * Country: Search tender header, address blocks, "country" field
  * Location: City, region, or province where buyer is located
  * Continent: Derive from country (Africa/Asia/Europe/Americas/Oceania/Middle East)

**B. CRITICAL DATES & TIMES**
Search terms: "closing date", "deadline", "last date for submission", "submit by", "no later than", "due date"

- **submission_deadline**: EXACT format required
  * Format: "YYYY-MM-DD HH:MM timezone" OR "YYYY-MM-DD 23:59 local time" if no time specified
  * If multiple deadlines mentioned (technical vs financial), specify: "Technical: [date], Financial: [date]"
  
- **clarification_deadline**: Date for submitting questions
  * Search: "questions by", "clarifications deadline", "queries deadline", "RFI deadline"
  * Same format as submission_deadline

**C. FINANCIAL GATEKEEPERS**
Search for amounts, percentages, and thresholds:

- **Bid Security/Bid Bond**: 
  * Search: "bid security", "earnest money", "EMD", "proposal guarantee", "tender security"
  * Format examples: "2% of bid value", "USD 50,000", "EUR 10,000 or equivalent", "As per JV formula"
  * Capture: Amount, format (bank guarantee/cashier's check/etc), validity period
  
- **Financial Vitals/Turnover Requirements**:
  * Search: "annual turnover", "revenue", "sales volume", "financial capacity", "minimum turnover"
  * Look for: Minimum thresholds, time period (last 3 years, etc.), currency
  * Example: "Minimum USD 500,000 average annual turnover in last 3 years"
  
- **Liquidated Damages**:
  * Search: "LD", "liquidated damages", "penalty", "delay damages", "late delivery penalty", "damages for delay"
  * Capture percentage/amount per day/week of delay

**D. ELIGIBILITY & RESTRICTIONS**
Critical auto-disqualification criteria:

- **Local Presence Required**: true/false
  * Search: "local office required", "must have presence in", "established in [country]", "registered locally"
  * Mark true if explicitly required, false otherwise
  
- **Killer Clauses/Gatekeepers**:
  * Search: "shall be rejected", "will be disqualified", "mandatory requirement", "failure to provide", "non-compliance will result"
  * Examples: Blacklist status, litigation history, specific certifications, country restrictions

**E. QUALITY CERTIFICATIONS**
In the "quality_certificates" field, list ONLY the high-level certificate names found:
- Format: ["ISO 9001", "Certificate of Origin", "GMP Certificate", "CE Marking"]
- Do NOT include descriptions or explanations
- Search entire document for certification requirements

═══════════════════════════════════════════════════════════════════════

### 3. LOT & ITEM STRUCTURE

**LOTS EXTRACTION RULES:**
- If document explicitly has "Lot 1, Lot 2, Lot 3" structure → parse each separately
- If document lists items without lot divisions → create single lot: {"lot_number": "Single Lot", "items": [...]}
- If items are in a table/schedule → extract each row as separate item
- Preserve item numbering exactly as in source (1.1, 1.2 or A, B, etc.)
- If no items listed (framework/service tender) → return empty array []

**Item Extraction:**
For each item capture:
- item_number: Line/Item number if specified in document
- name: Complete item description (don't abbreviate)
- quantity: Numeric value + unit (e.g., "50 units", "100 kg", "5 lots")
- specifications: Key technical specs if mentioned inline

═══════════════════════════════════════════════════════════════════════

### 4. EVALUATION & COMMERCIAL TERMS

- **Evaluation Method**: 
  * Search: "evaluation criteria", "scoring", "technical and financial", "QCBS", "weight"
  * Example: "70% Technical, 30% Financial" or "Quality-Cost Based Selection" or "Lowest Price Technically Compliant"

- **Partial Bids**:
  * Search: "partial bid", "bid for one or more lots", "all lots mandatory", "package bidding"
  * Return: "Yes - can bid on individual lots" OR "No - must bid all lots" OR "Not specified"

- **Maintenance/Warranty**:
  * Search: "warranty period", "guarantee", "maintenance", "after-sales service", "defect liability"
  * Capture duration and terms

- **Past Performance/Experience**:
  * Search: "similar projects", "experience required", "past performance", "reference projects", "track record"
  * Capture: Number of similar contracts, time period, value thresholds

- **Key Experts/Personnel**:
  * Search: "key personnel", "experts", "CVs required", "team composition", "qualification of staff"
  * List required roles if specified

- **Site Visit**:
  * Search: "site visit", "pre-bid meeting", "mandatory meeting", "venue", "physical inspection"
  * Capture: Date, time, location, whether mandatory or optional

═══════════════════════════════════════════════════════════════════════

### 5. TAX & LEGAL CONSIDERATIONS

- **Tax and VAT Rules**:
  * Search: "VAT", "tax exemption", "customs duty", "import duty", "tax treatment", "withholding tax"
  * Note: Who bears tax burden, any exemptions, tax certificates needed

- **Currency**:
  * Extract: ISO currency code (USD, EUR, GBP, etc.)
  * Search: Bid pricing section, budget section, payment terms
  * If multiple currencies mentioned, list primary one for bid submission

═══════════════════════════════════════════════════════════════════════

### 6. SPECIAL CASES TO HANDLE

- **Multiple Deadlines**: If separate technical and financial deadlines exist, specify both clearly
- **JV/Consortium Bids**: Note different requirements in financial_vitals (e.g., "Combined turnover of JV partners")
- **Framework Agreements**: Mark in overall_summary if this is multi-year or call-off contract
- **Amendments/Addenda**: If present, use LATEST information and note "As per Addendum X dated Y"
- **Two-Stage/Pre-qualification**: If EOI or pre-qualification stage, note in overall_summary

═══════════════════════════════════════════════════════════════════════

### 7. CATEGORY CLASSIFICATION LOGIC

Assign ONE category based on majority of items:
- **medical**: >50% items are medical/hospital equipment, surgical instruments, pharmaceuticals
- **lab**: >50% are laboratory/scientific instruments, testing equipment, research tools
- **agricultural**: >50% are farming equipment, irrigation, seeds, fertilizers, agri-machinery
- **industrial**: >50% are machinery, manufacturing equipment, construction materials, industrial supplies
- **educational**: >50% are school furniture, teaching aids, stationery, educational materials
- **research**: Primarily R&D equipment, academic/scientific research tools
- **mix**: No single category >50% OR highly diverse item types OR services/consulting

═══════════════════════════════════════════════════════════════════════

### 8. PRE-SUBMISSION VALIDATION CHECKS

BEFORE returning JSON, verify these self-checks:

□ Is "title" longer than 10 characters and descriptive?
□ Is "procuring_entity" an actual organization name (not "Not specified")?
□ Does "submission_deadline" contain an actual date?
□ If any amounts mentioned in documents, is "currency_code" filled?
□ Does "document_checklist" have at least 3 items?
□ Are "quality_certificates" actual certificate names (not descriptions)?
□ If lots/items exist in document, is "lot_hierarchy" populated?

If ANY check fails, re-scan the document for that specific field before finalizing.

═══════════════════════════════════════════════════════════════════════

### 9. OUTPUT STRUCTURE (JSON ONLY - NO MARKDOWN, NO EXPLANATIONS)

Return this exact JSON structure:

{
  "summary": {
    "title": "Full tender title exactly as written",
    "id_reference": "Tender ID/Reference Number",
    "country": "Country name",
    "continent": "Africa/Asia/Europe/Americas/Oceania/Middle East",
    "location": "City, Region, or Province",
    "procuring_entity": "Full official buyer organization name",
    "donor_entity": "Funding organization (e.g., EU, USAID, World Bank) or 'Not specified'",
    "category": "One of: medical/lab/agricultural/industrial/educational/research/mix",
    "submission_deadline": "YYYY-MM-DD HH:MM timezone format or 'Not specified'",
    "clarification_deadline": "YYYY-MM-DD HH:MM timezone format or 'Not specified'",
    "currency_code": "ISO code (USD/EUR/GBP/etc) or 'Not specified'",
    "overall_summary": "1-2 sentence overview of what is being procured and key context"
  },
  "compliance": {
    "local_presence_required": true or false,
    "bid_security": "Amount, format, and validity (e.g., '2% of bid value as bank guarantee valid 90 days') or 'Not specified'",
    "financial_vitals": "Turnover/liquidity requirements with amounts and timeframes or 'Not specified'",
    "quality_certificates": ["ISO 9001", "Certificate of Origin", "CE Marking"]
  },
  "logic": {
    "evaluation_method": "Evaluation criteria and weighting (e.g., '70% Technical, 30% Financial') or 'Not specified'",
    "allow_partial_bids": "Yes - description/No - description/Not specified",
    "lot_hierarchy": [
      {
        "lot_number": "Lot identifier or 'Single Lot'",
        "lot_name": "Descriptive name if provided or omit this field",
        "items": [
          {
            "item_number": "Line number if specified or omit this field",
            "name": "Complete item description",
            "quantity": "Number and unit",
            "specifications": "Key specs if mentioned inline or omit this field"
          }
        ]
      }
    ]
  },
  "risks": {
    "tax_and_vat": "Tax rules, exemptions, who bears tax burden or 'Not specified'",
    "penalties": "Liquidated damages terms and amounts or 'Not specified'",
    "killer_clauses": ["List each critical mandatory requirement that causes auto-disqualification"],
    "maintenance_warranty": "Warranty duration and terms or 'Not specified'",
    "key_experts": "Required personnel/roles or 'Not specified'",
    "past_performance": "Experience requirements and criteria or 'Not specified'",
    "site_visit": "Date, time, location, mandatory/optional status or 'Not specified'"
  },
  "document_checklist": [
    "List every mandatory document/certificate mentioned",
    "Use exact terminology from tender",
    "Include submission format if specified (original, certified copy, notarized, etc.)",
    "Minimum 3 items if any documents required"
  ]
}

═══════════════════════════════════════════════════════════════════════

REMEMBER: 
- Return ONLY the JSON object above
- No markdown code blocks (```json```)
- No explanatory text before or after
- "Not specified" is always acceptable when information is genuinely absent
- Accuracy over completeness - never fabricate data
"""
        
        messages_list = [
            {"role": "system", "content": "You are a specialized tender document parser."},
            {"role": "user", "content": [{"type": "text", "text": EXTRACTION_PROMPT}]}
        ]
        
        if pre_extracted_text:
            messages_list[1]["content"].append({
                "type": "text", 
                "text": f"DOCUMENT TEXT SOURCE:\n\n{pre_extracted_text}"
            })
            
        for mime_type, base64_data in image_attachments:
            messages_list[1]["content"].append({
                "type": "image_url",
                "image_url": {"url": f"data:{mime_type};base64,{base64_data}"}
            })

        # Call OpenAI with gpt-5-nano as requested
        if not client:
             raise Exception("AI client not initialized")

        response = client.chat.completions.create(
            model="gpt-5-nano",
            messages=messages_list,
            response_format={"type": "json_object"}
        )
        
        # 4. Parse Results (90%)
        summary_obj.current_step = "Parsing AI response and saving analysis..."
        summary_obj.analysis_progress = 90
        summary_obj.save()

        data = json.loads(response.choices[0].message.content.strip())
        
        # Update summary object fields
        summary_data = data.get('summary', {})
        compliance = data.get('compliance', {})
        logic = data.get('logic', {})
        risks = data.get('risks', {})
        
        summary_obj.title = summary_data.get('title', 'Unknown')
        summary_obj.deadline = summary_data.get('submission_deadline', 'Not specified')
        summary_obj.clarification_deadline = summary_data.get('clarification_deadline', 'Not specified')
        summary_obj.currency_code = summary_data.get('currency_code', 'Not specified')
        summary_obj.raw_summary = summary_data.get('overall_summary', 'No summary generated')
        
        country = summary_data.get('country', 'Not specified')
        location_detail = summary_data.get('location', 'Not specified')
        if country != 'Not specified' and location_detail != 'Not specified':
            summary_obj.location = f"{location_detail}, {country}"
        elif country != 'Not specified':
            summary_obj.location = country
        else:
            summary_obj.location = location_detail
        
        summary_obj.tenderer = summary_data.get('procuring_entity', 'Not specified')
        summary_obj.donor = summary_data.get('donor_entity', 'Not specified')
        summary_obj.continent = summary_data.get('continent', 'Not specified')
        
        # Validate category
        raw_category = summary_data.get('category', '').lower()
        valid_categories = ['medical', 'lab', 'agricultural', 'industrial', 'educational', 'research', 'mix']
        if raw_category in valid_categories:
            summary_obj.category = raw_category
        else:
            summary_obj.category = 'mix'
        
        lots_data = logic.get('lot_hierarchy', [])
        summary_obj.lots = json.dumps(lots_data)
        summary_obj.technical_financial_split = logic.get('evaluation_method', 'Not specified')
        
        # Ensure boolean and handle potential nulls from AI
        raw_local_req = compliance.get('local_presence_required')
        summary_obj.local_presence_required = bool(raw_local_req) if raw_local_req is not None else False
        
        summary_obj.bid_security = compliance.get('bid_security', 'Not specified')
        summary_obj.financial_thresholds = compliance.get('financial_vitals', 'Not specified')
        
        # Store high-level certificates
        certs = compliance.get('quality_certificates', [])
        summary_obj.quality_certificates = ", ".join(certs) if isinstance(certs, list) else str(certs)
        
        summary_obj.killer_clauses = ", ".join(risks.get('killer_clauses', [])) if isinstance(risks.get('killer_clauses'), list) else str(risks.get('killer_clauses', ''))
        summary_obj.maintenance_warranty = risks.get('maintenance_warranty', 'Not specified')
        summary_obj.key_experts = risks.get('key_experts', 'Not specified')
        summary_obj.past_performance = risks.get('past_performance', 'Not specified')
        summary_obj.site_visit = risks.get('site_visit', 'Not specified')
        
        summary_obj.document_checklist = "\n".join(data.get('document_checklist', [])) if isinstance(data.get('document_checklist'), list) else str(data.get('document_checklist', ''))
        
        summary_obj.status = 'completed'
        summary_obj.analysis_progress = 100
        summary_obj.current_step = "Analysis complete!"
        summary_obj.save()
        
    except Exception as e:
        logger.error(f"Error in background analysis: {e}")
        logger.error(traceback.format_exc())
        try:
            summary_obj = TenderSummary.objects.get(id=summary_id)
            summary_obj.status = 'failed'
            summary_obj.failure_reason = str(e)
            summary_obj.save()
        except:
            pass
    finally:
        # Close connection for the thread
        connection.close()

@login_required
def analysis_progress_api(request, summary_id):
    """API endpoint to get the current progress of an analysis."""
    summary = get_object_or_404(TenderSummary, id=summary_id)
    return JsonResponse({
        'status': summary.status,
        'progress': summary.analysis_progress,
        'step': summary.current_step,
        'failure_reason': summary.failure_reason if summary.status == 'failed' else None
    })

@login_required
@require_POST
def delete_summary(request, summary_id):
    """View to delete a summary if the user is the creator or an admin."""
    summary = get_object_or_404(TenderSummary, id=summary_id)
    
    # Permission check: Creator or Admin
    if summary.user == request.user or request.user.is_staff:
        summary.delete()
        messages.success(request, "Summary deleted successfully.")
    else:
        messages.error(request, "You do not have permission to delete this summary.")
        
    return redirect('docai:home')

@login_required
def summary_detail(request, summary_id):
    summary = get_object_or_404(TenderSummary, id=summary_id)
    return render(request, 'docai/detail.html', {'summary': summary})

@login_required
@require_POST
def edit_summary(request, summary_id):
    """View to manually edit tender summary info."""
    summary = get_object_or_404(TenderSummary, id=summary_id)
    
    # Permission check: Creator or Admin
    if not (summary.user == request.user or request.user.is_staff):
        messages.error(request, "You do not have permission to edit this summary.")
        return redirect('docai:detail', summary_id=summary.id)
    
    # Update fields from POST data
    summary.title = request.POST.get('title', summary.title)
    summary.deadline = request.POST.get('deadline', summary.deadline)
    summary.clarification_deadline = request.POST.get('clarification_deadline', summary.clarification_deadline)
    summary.location = request.POST.get('location', summary.location)
    summary.tenderer = request.POST.get('tenderer', summary.tenderer)
    summary.currency_code = request.POST.get('currency_code', summary.currency_code)
    summary.raw_summary = request.POST.get('raw_summary', summary.raw_summary)
    
    summary.financial_thresholds = request.POST.get('financial_thresholds', summary.financial_thresholds)
    summary.maintenance_warranty = request.POST.get('maintenance_warranty', summary.maintenance_warranty)
    summary.technical_financial_split = request.POST.get('technical_financial_split', summary.technical_financial_split)
    summary.key_experts = request.POST.get('key_experts', summary.key_experts)
    summary.past_performance = request.POST.get('past_performance', summary.past_performance)
    summary.bid_security = request.POST.get('bid_security', summary.bid_security)
    summary.site_visit = request.POST.get('site_visit', summary.site_visit)
    summary.killer_clauses = request.POST.get('killer_clauses', summary.killer_clauses)
    summary.document_checklist = request.POST.get('document_checklist', summary.document_checklist)
    summary.quality_certificates = request.POST.get('quality_certificates', summary.quality_certificates)
    
    # Filtering fields
    summary.donor = request.POST.get('donor', summary.donor)
    summary.continent = request.POST.get('continent', summary.continent)
    summary.category = request.POST.get('category', summary.category)
    
    # Update lots if provided (it's stored as JSON string)
    lots_json = request.POST.get('lots')
    if lots_json:
        try:
            # Validate JSON if possible, or just save it
            json.loads(lots_json)
            summary.lots = lots_json
        except:
            pass
            
    summary.is_human_enhanced = True
    summary.save()
    
    messages.success(request, "Summary updated successfully.")
    return redirect('docai:detail', summary_id=summary.id)
