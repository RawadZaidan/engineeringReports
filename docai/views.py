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
    if request.method == 'POST' and request.FILES.get('document'):
        document = request.FILES['document']
        summary_obj = TenderSummary.objects.create(
            user=request.user,
            document=document,
            status='processing'
        )
        
        if not client:
            summary_obj.status = 'failed'
            summary_obj.failure_reason = "OpenAI API key not configured (OPENAI_API in .env)"
            summary_obj.save()
            messages.error(request, "AI service not configured.")
            return redirect('docai:home')

        try:
            # 1. Try to extract text using local libraries (PDF/Word/Excel)
            extracted_text = extract_text_from_file(document)
            
            prompt = """
            You are an expert tender document analyst. 
            Analyze the provided data and extract the following information in a structured JSON format:
            {
                "title": "Tender Title",
                "deadline": "Submission Deadline",
                "lots": "Description of lots or batches",
                "location": "Project Location",
                "tenderer": "Name of the procuring entity / tenderer",
                "important_notes": "Key things to keep in mind (short list)",
                "quality_certificates": "Required quality certificates (ISO, etc.)",
                "summary": "A concise overall summary of the tender"
            }
            Focus strictly on the important data. If a field is not found, use "Not specified".
            Output ONLY the raw JSON.
            """
            
            messages_list = [
                {"role": "system", "content": "You are a specialized tender document parser."},
                {"role": "user", "content": [{"type": "text", "text": prompt}]}
            ]
            
            if extracted_text:
                # We have raw text from PDF/Word/Excel
                messages_list[1]["content"].append({
                    "type": "text", 
                    "text": f"DOCUMENT CONTENT:\n\n{extracted_text}"
                })
            else:
                # No text extracted (likely image or scanned PDF). 
                # We'll treat it as an image for GPT-4o-mini
                document.seek(0)
                file_data = document.read()
                base64_image = base64.b64encode(file_data).decode('utf-8')
                mime_type = document.content_type or "image/jpeg"
                
                messages_list[1]["content"].append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{mime_type};base64,{base64_image}"
                    }
                })

            # Call OpenAI
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages_list,
                response_format={"type": "json_object"}
            )
            
            # Parse response
            raw_text = response.choices[0].message.content.strip()
            data = json.loads(raw_text)
            
            # Update summary object
            summary_obj.title = data.get('title', 'Unknown')
            summary_obj.deadline = data.get('deadline', 'Not specified')
            summary_obj.lots = data.get('lots', 'Not specified')
            summary_obj.location = data.get('location', 'Not specified')
            summary_obj.tenderer = data.get('tenderer', 'Not specified')
            summary_obj.important_notes = data.get('important_notes', 'None')
            summary_obj.quality_certificates = data.get('quality_certificates', 'None')
            summary_obj.raw_summary = data.get('summary', 'No summary generated')
            summary_obj.status = 'completed'
            summary_obj.save()
            
            messages.success(request, "Document summarized successfully with GPT-4o-mini!")
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
