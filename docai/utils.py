import pdfplumber
import docx
import pandas as pd
import io
import logging

logger = logging.getLogger(__name__)

def extract_text_from_pdf(file_obj):
    """Extracts text from a digital PDF file."""
    text = ""
    try:
        # Seek to beginning
        file_obj.seek(0)
        with pdfplumber.open(file_obj) as pdf:
            for page in pdf.pages:
                extracted = page.extract_text()
                if extracted:
                    text += extracted + "\n"
    except Exception as e:
        logger.error(f"Error extracting PDF: {e}")
        return f"[Error extracting PDF: {str(e)}]"
    return text

def extract_text_from_docx(file_obj):
    """Extracts text from a Word document."""
    try:
        file_obj.seek(0)
        doc = docx.Document(file_obj)
        text = "\n".join([para.text for para in doc.paragraphs])
        return text
    except Exception as e:
        logger.error(f"Error extracting DOCX: {e}")
        return f"[Error extracting Word doc: {str(e)}]"

def extract_text_from_excel(file_obj):
    """Extracts text from an Excel spreadsheet."""
    try:
        file_obj.seek(0)
        # Read all sheets
        df_dict = pd.read_excel(file_obj, sheet_name=None)
        text = ""
        for sheet_name, df in df_dict.items():
            text += f"--- Sheet: {sheet_name} ---\n"
            text += df.to_string(index=False) + "\n\n"
        return text
    except Exception as e:
        logger.error(f"Error extracting Excel: {e}")
        return f"[Error extracting Excel: {str(e)}]"

def extract_text_from_file(file_obj):
    """
    Dispatcher to extract text based on file extension.
    Returns the extracted text or None if the file should be handled by Gemini vision (images).
    """
    filename = file_obj.name.lower()
    
    if filename.endswith('.pdf'):
        return extract_text_from_pdf(file_obj)
    elif filename.endswith(('.docx', '.doc')):
        return extract_text_from_docx(file_obj)
    elif filename.endswith(('.xlsx', '.xls')):
        return extract_text_from_excel(file_obj)
    elif filename.endswith(('.png', '.jpg', '.jpeg', '.webp')):
        # Gemini handles these directly with its vision model
        return None
    else:
        # Try to read as plain text if all else fails
        try:
            file_obj.seek(0)
            return file_obj.read().decode('utf-8', errors='ignore')
        except:
            return None
