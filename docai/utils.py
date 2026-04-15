import PyPDF2
import docx
import pandas as pd
import io
import logging
from striprtf.striprtf import rtf_to_text

logger = logging.getLogger(__name__)

def extract_text_from_pdf(file_obj):
    """
    Extracts text from a digital PDF file using memory-efficient incremental processing.
    Processes all pages one at a time to minimize memory footprint.
    """
    text = ""
    try:
        # Seek to beginning
        file_obj.seek(0)
        reader = PyPDF2.PdfReader(file_obj)
        total_pages = len(reader.pages)
        
        logger.info(f"Processing PDF with {total_pages} pages incrementally")
        
        # Process ALL pages incrementally to avoid memory issues
        for i in range(total_pages):
            try:
                # Extract one page at a time
                page = reader.pages[i]
                extracted = page.extract_text()
                if extracted:
                    text += extracted + "\n"
                
                # Explicit cleanup to free memory after each page
                del page
                
                # Log progress for large documents
                if (i + 1) % 10 == 0:
                    logger.info(f"Processed {i + 1}/{total_pages} pages")
                    
            except Exception as page_error:
                logger.warning(f"Error extracting page {i+1}: {page_error}")
                continue
        
        logger.info(f"Successfully extracted text from all {total_pages} pages")
            
    except MemoryError:
        logger.error("Memory error while extracting PDF")
        return "[Error: Document too large for available memory. Please try a smaller document.]"
    except Exception as e:
        logger.error(f"Error extracting PDF: {e}")
        return f"[Error extracting PDF: {str(e)}]"
    
    return text if text.strip() else "[No text could be extracted from PDF]"

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
    """
    Extracts text from an Excel spreadsheet using memory-efficient incremental processing.
    Processes all sheets one at a time with clear labeling for multi-sheet context.
    Optimized for tender documents with lots, annexes, and technical specifications across sheets.
    """
    try:
        file_obj.seek(0)
        # Read all sheets
        df_dict = pd.read_excel(file_obj, sheet_name=None)
        text = ""
        
        total_sheets = len(df_dict)
        logger.info(f"Processing Excel file with {total_sheets} sheets incrementally")
        
        # Add header for multi-sheet context
        if total_sheets > 1:
            text += f"═══════════════════════════════════════════════════════════\n"
            text += f"EXCEL WORKBOOK WITH {total_sheets} SHEETS\n"
            text += f"Sheet Names: {', '.join(df_dict.keys())}\n"
            text += f"═══════════════════════════════════════════════════════════\n\n"
        
        # Process ALL sheets incrementally
        for sheet_idx, (sheet_name, df) in enumerate(df_dict.items(), 1):
            # Clear sheet separator with metadata
            text += f"\n{'='*70}\n"
            text += f"SHEET {sheet_idx} of {total_sheets}: {sheet_name}\n"
            text += f"{'='*70}\n\n"
            
            # Add row count for context
            row_count = len(df)
            col_count = len(df.columns)
            text += f"[Sheet contains {row_count} rows × {col_count} columns]\n\n"
            
            # Convert entire dataframe to string (pandas handles this efficiently)
            text += df.to_string(index=False) + "\n\n"
            
            # Explicit cleanup to free memory after each sheet
            del df
            
            # Log progress for large workbooks
            if sheet_idx % 5 == 0:
                logger.info(f"Processed {sheet_idx}/{total_sheets} sheets")
        
        logger.info(f"Successfully extracted text from all {total_sheets} sheets")
        return text
        
    except MemoryError:
        logger.error("Memory error while extracting Excel")
        return "[Error: Spreadsheet too large for available memory. Please try a smaller file.]"
    except Exception as e:
        logger.error(f"Error extracting Excel: {e}")
        return f"[Error extracting Excel: {str(e)}]"

def extract_text_from_rtf(file_obj):
    """Extracts text from an RTF file."""
    try:
        file_obj.seek(0)
        content = file_obj.read()
        if isinstance(content, bytes):
            content = content.decode('utf-8', errors='ignore')
        return rtf_to_text(content)
    except Exception as e:
        logger.error(f"Error extracting RTF: {e}")
        return f"[Error extracting RTF: {str(e)}]"

def extract_text_from_file(file_obj):
    """
    Dispatcher to extract text based on file extension.
    Returns the extracted text or None if the file should be handled by gpt-5-nano vision (images).
    """
    filename = file_obj.name.lower()
    
    if filename.endswith('.pdf'):
        return extract_text_from_pdf(file_obj)
    elif filename.endswith(('.docx', '.doc')):
        return extract_text_from_docx(file_obj)
    elif filename.endswith(('.xlsx', '.xls')):
        return extract_text_from_excel(file_obj)
    elif filename.endswith('.rtf'):
        return extract_text_from_rtf(file_obj)
    elif filename.endswith(('.png', '.jpg', '.jpeg', '.webp')):
        # gpt-5-nano handles these directly with its vision model
        return None
    else:
        # Try to read as plain text if all else fails
        try:
            file_obj.seek(0)
            return file_obj.read().decode('utf-8', errors='ignore')
        except:
            return None
