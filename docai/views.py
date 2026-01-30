import os
import json
import base64
import logging
import traceback
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.contrib import messages
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
    summaries = TenderSummary.objects.filter(user=request.user)
    return render(request, 'docai/home.html', {'summaries': summaries})

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
            status='processing'
        )
        
        if not client:
            summary_obj.status = 'failed'
            summary_obj.failure_reason = "OpenAI API key not configured (OPENAI_API in .env)"
            summary_obj.save()
            messages.error(request, "AI service not configured.")
            return redirect('docai:home')

        try:
            # Extract text from all uploaded files and combine them
            combined_text = ""
            for idx, document in enumerate(documents, 1):
                extracted_text = extract_text_from_file(document)
                if extracted_text:
                    # Add a separator between documents for clarity
                    if idx > 1:
                        combined_text += f"\n\n{'='*50}\n--- Document {idx}: {document.name} ---\n{'='*50}\n\n"
                    else:
                        combined_text += f"--- Document {idx}: {document.name} ---\n\n"
                    combined_text += extracted_text
            
            # Use combined_text instead of extracted_text from single file
            
            EXTRACTION_PROMPT = """
Analyze the attached tender document as a Senior Procurement Specialist. 
Your goal is to extract structured data while flagging critical 'Bid/No-Bid' risks.

### EXTRACTION CATEGORIES:
1. **Administrative Metadata:** Reference numbers, entities, and critical timeline dates (Clarification vs. Submission).
2. **Eligibility & 'Gatekeeper' Clauses:** Extract any mandatory requirements that disqualify a bidder (e.g., local residency, specific portal registrations like UNGM, or mandatory site visits).
3. **Financial Requirements:** Extract minimum annual turnover, liquidity ratios, and bid security (bond) amounts.
4. **Lot & Award Logic:** Identify if the tender is 'All-or-Nothing' or if it allows 'Partial Bidding' (per Lot or per Item). 
5. **Contractual 'Tripwires':** Extract liquidated damages (penalties), tax/VAT status, and payment terms (e.g., net 30 days, no advance payments).

### OUTPUT STRUCTURE (JSON):
Return ONLY a JSON object with this schema. CRITICAL: Always extract the country/location and procuring entity name - these are mandatory fields that MUST be populated.
{
  "summary": {
    "title": "Full tender title exactly as written",
    "id_reference": "Tender reference number or ID",
    "country": "MANDATORY - The country where the tender is located (e.g., Lebanon, Jordan, Iraq, Egypt, etc.)",
    "location": "MANDATORY - City, region, or specific project location",
    "procuring_entity": "MANDATORY - The FULL NAME of the organization issuing the tender (Ministry, Agency, Company, NGO, etc.)",
    "submission_deadline": "Exact date and time for bid submission",
    "clarification_deadline": "Deadline for asking questions",
    "currency_code": "Currency code (USD/EUR/LBP/etc)",
    "overall_summary": "Brief overview of what the tender is for"
  },
  "compliance_check": {
    "mandatory_registrations": ["List all required portal/entity registrations"],
    "local_presence_required": true/false,
    "bid_security": "Amount and format, or 'None'",
    "financial_vitals": "Minimum turnover/liquidity requirements"
  },
  "bid_logic": {
    "evaluation_method": "e.g., Lowest Price vs. Technical Weighted",
    "allow_partial_bids": "Can the bidder quote for just one Lot/Item?",
    "lot_hierarchy": [
        {
            "lot_number": "1",
            "items": [
                {"name": "Item Name", "quantity": "Qty"}
            ]
        }
    ]
  },
  "risk_assessment": {
    "tax_and_vat": "Exemption details or inclusive/exclusive rules",
    "penalties": "Liquidated damages percentage and caps",
    "killer_clauses": ["List any high-risk terms found in the text"],
    "maintenance_warranty": "Post-delivery obligations and warranty terms",
    "key_experts": "Required roles and certifications",
    "past_performance": "Similar project requirements",
    "site_visit": "Details on meetings/visits"
  },
  "document_checklist": ["List every form/certificate explicitly mentioned as 'Mandatory'"]
}

IMPORTANT EXTRACTION RULES:
1. Look for the country in headers, addresses, or procurement entity details
2. The procuring entity is usually in the header or first page - extract the COMPLETE organization name
3. Do NOT leave country, location, or procuring_entity as "Not specified" unless they are truly absent
4. Common entity names include: Ministry of [X], [Country] Health Authority, UNICEF, UNHCR, WHO, etc.
"""
            
            messages_list = [
                {"role": "system", "content": "You are a specialized tender document parser."},
                {"role": "user", "content": [{"type": "text", "text": EXTRACTION_PROMPT}]}
            ]
            
            if combined_text:
                messages_list[1]["content"].append({
                    "type": "text", 
                    "text": f"DOCUMENT SOURCE:\n\n{combined_text}"
                })
            else:
                # No text extracted from any file - use the first document as image
                documents[0].seek(0)
                file_data = documents[0].read()
                base64_image = base64.b64encode(file_data).decode('utf-8')
                mime_type = documents[0].content_type or "image/jpeg"
                messages_list[1]["content"].append({
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime_type};base64,{base64_image}"}
                })

            # Call OpenAI with gpt-5-nano as requested
            response = client.chat.completions.create(
                model="gpt-5-nano",
                messages=messages_list,
                response_format={"type": "json_object"}
            )
            
            data = json.loads(response.choices[0].message.content.strip())
            
            # Update summary object from new schema
            summary = data.get('summary', {})
            compliance = data.get('compliance_check', {})
            bid = data.get('bid_logic', {})
            risk = data.get('risk_assessment', {})
            
            
            summary_obj.title = summary.get('title', 'Unknown')
            summary_obj.deadline = summary.get('submission_deadline', 'Not specified')
            summary_obj.clarification_deadline = summary.get('clarification_deadline', 'Not specified')
            summary_obj.currency_code = summary.get('currency_code', 'Not specified')
            summary_obj.raw_summary = summary.get('overall_summary', 'No summary generated')
            
            # Location and Entity Information
            country = summary.get('country', 'Not specified')
            location_detail = summary.get('location', 'Not specified')
            # Combine country and location for better context
            if country != 'Not specified' and location_detail != 'Not specified':
                summary_obj.location = f"{location_detail}, {country}"
            elif country != 'Not specified':
                summary_obj.location = country
            else:
                summary_obj.location = location_detail
            
            summary_obj.tenderer = summary.get('procuring_entity', 'Not specified')
            
            # Lots and technical aspects
            lots_data = bid.get('lot_hierarchy', [])
            summary_obj.lots = json.dumps(lots_data)
            summary_obj.technical_financial_split = bid.get('evaluation_method', 'Not specified')
            
            # Risk and Compliance
            summary_obj.local_presence_required = compliance.get('local_presence_required', False)
            summary_obj.bid_security = compliance.get('bid_security', 'Not specified')
            summary_obj.financial_thresholds = compliance.get('financial_vitals', 'Not specified')
            
            summary_obj.killer_clauses = ", ".join(risk.get('killer_clauses', [])) if isinstance(risk.get('killer_clauses'), list) else str(risk.get('killer_clauses', ''))
            summary_obj.maintenance_warranty = risk.get('maintenance_warranty', 'Not specified')
            summary_obj.key_experts = risk.get('key_experts', 'Not specified')
            summary_obj.past_performance = risk.get('past_performance', 'Not specified')
            summary_obj.site_visit = risk.get('site_visit', 'Not specified')
            
            summary_obj.document_checklist = "\n".join(data.get('document_checklist', [])) if isinstance(data.get('document_checklist'), list) else str(data.get('document_checklist', ''))
            
            summary_obj.status = 'completed'
            summary_obj.save()
            
            
            file_count_msg = f"{len(documents)} documents" if len(documents) > 1 else "document"
            messages.success(request, f"Tender {file_count_msg} analyzed successfully. Critical risks flagged.")
            return redirect('docai:detail', summary_id=summary_obj.id)
            
        except Exception as e:
            traceback.print_exc()
            summary_obj.status = 'failed'
            summary_obj.failure_reason = str(e)
            summary_obj.save()
            messages.error(request, f"Error processing document: {str(e)}")
            return redirect('docai:home')
            
    return redirect('docai:home')

@login_required
def summary_detail(request, summary_id):
    summary = get_object_or_404(TenderSummary, id=summary_id, user=request.user)
    return render(request, 'docai/detail.html', {'summary': summary})
