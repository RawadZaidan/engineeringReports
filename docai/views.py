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
Analyze the attached tender documents with the precision of a Senior Procurement Auditor. 
Your primary goal is to extract strictly grounded information. Do NOT hypothesize or assume. If a value is missing, return "Not specified".

### 1. TARGET DOCUMENTS CHECKLIST
Identify if the following specific documents are explicitly required for submission:
- **Legal/Identity**: Commercial Registry, Tax Compliance/Clearance, VAT Registration, Power of Attorney.
- **Registrations**: UNGM Vendor ID, UNOPS/GIZ/WB Portal registration.
- **Technical/Quality**: Certificate of Origin of Goods (MANDATORY CHECK), ISO Certifications (9001, 14001, 13485, etc.), Manufacturer Authorization Letter.
- **Financial**: Audited Financial Statements, Credit Facilities.

### 2. EXTRACTION REQUIREMENTS:
- **Country & Entity**: Grounded identification of the location and the full official name of the buyer.
- **Eligibility**: Mandatory disqualification criteria (Gatekeepers).
- **Financial Vitals**: Turnover, Bid Bonds, and Liquidated Damages.
- **Schedule**: Key dates (Clarification vs. Submission).

### 3. OUTPUT STRUCTURE (JSON):
Return a JSON object only. In "quality_certificates", list only the high-level certificate names found (e.g. "Certificate of Origin", "ISO 9001").

{
  "summary": {
    "title": "Full tender title",
    "id_reference": "Tender ID",
    "country": "Country",
    "continent": "Africa/Asia/Europe/etc.",
    "location": "City/Region",
    "procuring_entity": "Full Buyer Name",
    "donor_entity": "Funding Organization (e.g. EU, USAID)",
    "category": "Pick: medical, lab, agricultural, industrial, educational, research, mix",
    "submission_deadline": "Date & Time",
    "clarification_deadline": "Date & Time",
    "currency_code": "USD/EUR/etc",
    "overall_summary": "1-2 sentence overview"
  },
  "compliance": {
    "local_presence_required": true/false,
    "bid_security": "Amount and format",
    "financial_vitals": "Turnover/Liquidity rules",
    "quality_certificates": ["ISO 9001", "Certificate of Origin", "etc"]
  },
  "logic": {
    "evaluation_method": "Evaluation criteria weighting",
    "allow_partial_bids": "Yes/No",
    "lot_hierarchy": [
        {
            "lot_number": "1",
            "items": [
                {"name": "Item Name", "quantity": "Qty"}
            ]
        }
    ]
  },
  "risks": {
    "tax_and_vat": "Rules & Exemptions",
    "penalties": "Liquidated damages",
    "killer_clauses": ["High risk terms"],
    "maintenance_warranty": "Warranty terms",
    "key_experts": "Required roles",
    "past_performance": "Experience rules",
    "site_visit": "Meeting/Visit details"
  },
  "document_checklist": ["Complete list of every mandatory file mentioned"]
}
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
