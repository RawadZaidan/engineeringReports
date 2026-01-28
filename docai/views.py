import os
import google.generativeai as genai
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.conf import settings
from .models import TenderSummary
from django.contrib import messages
import json

# Configure Gemini
if settings.GEMINI_API_KEY:
    genai.configure(api_key=settings.GEMINI_API_KEY)

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
        
        try:
            # Initialize model
            model = genai.GenerativeModel('gemini-1.5-flash')
            
            # Read file content
            file_data = document.read()
            # If it's a PDF or Image, Gemini can handle it directly if we provide the right mime type
            # For simplicity, we'll try to send it as a part
            mime_type = document.content_type
            
            prompt = """
            You are an expert tender document analyst. 
            Analyze the provided document and extract the following information in a structured JSON format:
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
            Output ONLY the JSON.
            """
            
            # Generate content
            response = model.generate_content([
                prompt,
                {'mime_type': mime_type, 'data': file_data}
            ])
            
            # Parse response
            raw_text = response.text.strip()
            # Remove markdown code blocks if present
            if raw_text.startswith('```json'):
                raw_text = raw_text[7:-3].strip()
            elif raw_text.startswith('```'):
                raw_text = raw_text[3:-3].strip()
                
            data = json.loads(raw_text)
            
            # Update summary object
            summary_obj.title = data.get('title')
            summary_obj.deadline = data.get('deadline')
            summary_obj.lots = data.get('lots')
            summary_obj.location = data.get('location')
            summary_obj.tenderer = data.get('tenderer')
            summary_obj.important_notes = data.get('important_notes')
            summary_obj.quality_certificates = data.get('quality_certificates')
            summary_obj.raw_summary = data.get('summary')
            summary_obj.status = 'completed'
            summary_obj.save()
            
            messages.success(request, "Document summarized successfully!")
            return redirect('docai:detail', summary_id=summary_obj.id)
            
        except Exception as e:
            summary_obj.status = 'failed'
            summary_obj.save()
            messages.error(request, f"Error processing document: {str(e)}")
            return redirect('docai:home')
            
    return redirect('docai:home')

@login_required
def summary_detail(request, summary_id):
    summary = get_object_or_404(TenderSummary, id=summary_id, user=request.user)
    return render(request, 'docai/detail.html', {'summary': summary})
