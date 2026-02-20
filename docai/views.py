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
                # Protect memory on Render free tier: limit text to ~400k characters (approx 100k tokens max for safety)
                if len(extracted) > 400000:
                    logger.warning(f"File {document.name} is very large. Truncating text to prevent memory issues.")
                    extracted = extracted[:400000] + "\n... [CONTENT TRUNCATED FOR SERVER SAFETY] ..."
                
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
You are extracting tender information. Be fast and accurate.

CRITICAL RULES:
1. Procuring Entity = The buyer organization (e.g., "Ministry of Health", "UNICEF")
2. Donor = Same as procuring entity (no separate donor field needed)
3. Certificates: ONLY extract if you see "required", "must", "mandatory", "shall"
   Examples: ISO 9001, ISO 13485, CE Marking, FDA Approval, Certificate of Origin, Manufacturer Authorization
4. Multi-sheet Excel: If you see "SHEET 1 of X", read ALL sheets and combine ALL lots

EXTRACT:
- Title, deadline, location, country, continent
- Procuring entity (the buyer/issuing organization)
- Lots with items (if Excel has multiple sheets, combine ALL lots from ALL sheets)
- Quality certificates (ISO 9001, CE, FDA, COO, etc.) - ONLY if explicitly required
- Bid security, financial thresholds, evaluation method
- Important notes and killer clauses

RETURN ONLY THIS JSON (no markdown):
{
  "summary": {
    "title": "...",
    "id_reference": "...",
    "country": "...",
    "continent": "Africa/Asia/Europe/Americas/Oceania/Middle East",
    "location": "City/Region",
    "category": "medical/lab/agricultural/industrial/educational/research/mix",
    "procuring_entity": "The buyer organization",
    "donor_entity": "Same as procuring_entity",
    "submission_deadline": "Date and time",
    "clarification_deadline": "...",
    "currency_code": "USD/EUR/etc",
    "overall_summary": "Brief summary"
  },
  "logic": {
    "lot_hierarchy": [
      {
        "lot_number": "Lot 1",
        "lot_name": "Description",
        "items": [
          {"item_number": "1", "name": "Item name", "quantity": "10 units", "specifications": "..."}
        ]
      }
    ],
    "evaluation_method": "Technical/Financial split"
  },
  "compliance": {
    "local_presence_required": true/false,
    "quality_certificates": ["ISO 9001", "CE Marking", "FDA Approval", "Certificate of Origin", "Manufacturer Authorization"],
    "bid_security": "Amount and format",
    "financial_vitals": "Minimum turnover requirements"
  },
  "risks": {
    "tax_and_vat": "...",
    "penalties": "...",
    "killer_clauses": ["Critical requirements"],
    "maintenance_warranty": "...",
    "key_experts": "...",
    "past_performance": "...",
    "site_visit": "..."
  },
  "document_checklist": ["List of required documents"]
}

REMEMBER:
- For multi-sheet Excel: Extract lots from EVERY sheet
- Certificates: Only if explicitly required (not just mentioned)
  Common certificates: ISO 9001, ISO 13485, CE Marking, FDA Approval, Certificate of Origin, Manufacturer Authorization Letter
- Return ONLY JSON, no explanations
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
            model="gpt-5-mini",
            messages=messages_list,
            response_format={"type": "json_object"}
        )
        
        # 4. Parse Results (90%)
        summary_obj.current_step = "Parsing AI response and saving analysis..."
        summary_obj.analysis_progress = 90
        summary_obj.save()

        data = json.loads(response.choices[0].message.content.strip())
        
        # DEBUG: Log what AI returned
        logger.info(f"AI Response parsed successfully")
        logger.info(f"Lots data: {data.get('logic', {}).get('lot_hierarchy', [])}")
        logger.info(f"Certificates data: {data.get('compliance', {}).get('quality_certificates', [])}")
        
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
        logger.info(f"Saving lots to database: {summary_obj.lots[:200]}...")  # Log first 200 chars
        summary_obj.technical_financial_split = logic.get('evaluation_method', 'Not specified')
        
        # Ensure boolean and handle potential nulls from AI
        raw_local_req = compliance.get('local_presence_required')
        summary_obj.local_presence_required = bool(raw_local_req) if raw_local_req is not None else False
        
        summary_obj.bid_security = compliance.get('bid_security', 'Not specified')
        summary_obj.financial_thresholds = compliance.get('financial_vitals', 'Not specified')
        
        # Store high-level certificates
        certs = compliance.get('quality_certificates', [])
        summary_obj.quality_certificates = ", ".join(certs) if isinstance(certs, list) else str(certs)
        logger.info(f"Saving certificates to database: {summary_obj.quality_certificates}")
        
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
