import fitz  # PyMuPDF
import json
import re
from collections import Counter, defaultdict
from typing import List, Dict, Tuple, Optional
import numpy as np

class PDFOutlineExtractor:
    def __init__(self):
        self.heading_patterns = [
            r'^\d+\.\s+.+',  # 1. Chapter Title
            r'^\d+\.\d+\s+.+',  # 1.1 Section Title
            r'^\d+\.\d+\.\d+\s+.+',  # 1.1.1 Subsection Title
            r'^Chapter\s+\d+.+',  # Chapter N Title
            r'^Section\s+\d+.+',  # Section N Title
            r'^Appendix\s+[A-Z].+',  # Appendix A Title
        ]
        
        # Common heading keywords
        self.heading_keywords = [
            'introduction', 'overview', 'background', 'methodology', 'results',
            'conclusion', 'references', 'appendix', 'summary', 'abstract',
            'table of contents', 'revision history', 'glossary', 'index'
        ]
    
    def extract_text_with_formatting(self, pdf_path: str) -> List[Dict]:
        """Extract text with detailed formatting information from PDF"""
        doc = fitz.open(pdf_path)
        formatted_text = []
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            blocks = page.get_text("dict")
            
            for block in blocks["blocks"]:
                if "lines" in block:
                    for line in block["lines"]:
                        # Combine all spans in a line to form complete text
                        line_text = ""
                        line_fonts = []
                        line_sizes = []
                        line_flags = []
                        
                        for span in line["spans"]:
                            text = span["text"].strip()
                            if text:
                                line_text += text + " "
                                line_fonts.append(span["font"])
                                line_sizes.append(span["size"])
                                line_flags.append(span["flags"])
                        
                        line_text = line_text.strip()
                        if line_text and len(line_text) > 2:
                            # Use dominant formatting for the line
                            avg_size = np.mean(line_sizes) if line_sizes else 12
                            dominant_font = max(set(line_fonts), key=line_fonts.count) if line_fonts else ""
                            is_bold = any(flag & 2**4 for flag in line_flags)
                            
                            formatted_text.append({
                                "text": line_text,
                                "page": page_num + 1,
                                "font": dominant_font,
                                "size": avg_size,
                                "is_bold": is_bold,
                                "bbox": line["bbox"],
                                "line_count": len(line_text.split())
                            })
        
        doc.close()
        return formatted_text
    
    def identify_title(self, formatted_text: List[Dict]) -> str:
        """Identify document title from first page with improved logic"""
        first_page_text = [item for item in formatted_text if item["page"] == 1]
        
        if not first_page_text:
            return "Untitled Document"
        
        # Sort by font size and position (larger fonts and higher position first)
        first_page_text.sort(key=lambda x: (-x["size"], x["bbox"][1]))
        
        # Look for the title in the top portion of the first page
        candidates = []
        
        for item in first_page_text[:10]:  # Check top 10 items
            text = item["text"].strip()
            
            # Filter criteria for title
            if (20 <= len(text) <= 200 and  # Reasonable title length
                item["size"] >= 14 and  # Reasonable font size for title
                not re.match(r'^\d+\.?\s*$', text) and  # Not just numbers
                not text.lower().startswith('page') and  # Not page numbers
                len(text.split()) >= 2):  # At least 2 words
                
                candidates.append((text, item["size"]))
        
        if candidates:
            # Return the largest text that meets criteria
            title = max(candidates, key=lambda x: x[1])[0]
            # Clean the title
            title = re.sub(r'[^\w\s\-\:\.]', ' ', title)
            title = ' '.join(title.split())
            return title
        
        # Fallback: combine first few meaningful texts
        meaningful_texts = []
        for item in first_page_text[:5]:
            text = item["text"].strip()
            if len(text) > 5 and len(text.split()) >= 2:
                meaningful_texts.append(text)
        
        if meaningful_texts:
            combined_title = ' '.join(meaningful_texts[:2])
            if len(combined_title) <= 200:
                return ' '.join(combined_title.split())
        
        return "Untitled Document"
    
    def analyze_document_structure(self, formatted_text: List[Dict]) -> Dict:
        """Analyze the document to understand its structure"""
        # Analyze font sizes
        sizes = [item["size"] for item in formatted_text]
        size_counter = Counter(sizes)
        
        # Get the most common font size (likely body text)
        body_text_size = size_counter.most_common(1)[0][0]
        
        # Calculate size thresholds
        all_sizes = sorted(set(sizes), reverse=True)
        size_thresholds = {
            'h1': body_text_size * 1.5,
            'h2': body_text_size * 1.3,
            'h3': body_text_size * 1.15
        }
        
        return {
            'body_text_size': body_text_size,
            'size_thresholds': size_thresholds,
            'all_sizes': all_sizes
        }
    
    def is_likely_heading(self, item: Dict, structure_info: Dict) -> bool:
        """Determine if text item is likely a heading with improved logic"""
        text = item["text"].strip()
        
        # Basic filters
        if len(text) < 3 or len(text) > 300:
            return False
        
        # Skip if too many words (likely paragraph)
        if len(text.split()) > 20:
            return False
        
        # Skip common non-heading patterns
        skip_patterns = [
            r'^\d+$',  # Just numbers
            r'^page\s+\d+',  # Page numbers
            r'^\w{1,3}$',  # Very short words
            r'^[^\w\s]+$',  # Only punctuation
        ]
        
        for pattern in skip_patterns:
            if re.match(pattern, text, re.IGNORECASE):
                return False
        
        # Positive indicators
        indicators = 0
        
        # 1. Font size indicator
        if item["size"] > structure_info['size_thresholds']['h3']:
            indicators += 2
        elif item["size"] > structure_info['body_text_size']:
            indicators += 1
        
        # 2. Bold formatting
        if item["is_bold"]:
            indicators += 2
        
        # 3. Numbered section patterns
        for pattern in self.heading_patterns:
            if re.match(pattern, text, re.IGNORECASE):
                indicators += 3
                break
        
        # 4. Contains heading keywords
        text_lower = text.lower()
        for keyword in self.heading_keywords:
            if keyword in text_lower:
                indicators += 1
                break
        
        # 5. Title case or all caps (but not too long)
        if text.istitle() and len(text.split()) <= 8:
            indicators += 1
        elif text.isupper() and 5 <= len(text) <= 50:
            indicators += 2
        
        # 6. Short, meaningful text
        if 5 <= len(text) <= 100 and len(text.split()) <= 10:
            indicators += 1
        
        # Need at least 3 indicators to be considered a heading
        return indicators >= 3
    
    def determine_heading_level(self, item: Dict, structure_info: Dict) -> str:
        """Determine heading level with improved logic"""
        text = item["text"].strip()
        size = item["size"]
        thresholds = structure_info['size_thresholds']
        
        # Pattern-based level determination (highest priority)
        if re.match(r'^\d+\.\s+', text):
            return "H1"
        elif re.match(r'^\d+\.\d+\s+', text):
            return "H2"
        elif re.match(r'^\d+\.\d+\.\d+\s+', text):
            return "H3"
        
        # Size-based level determination
        if size >= thresholds['h1']:
            return "H1"
        elif size >= thresholds['h2']:
            return "H2"
        else:
            return "H3"
    
    def clean_heading_text(self, text: str) -> str:
        """Clean and normalize heading text"""
        # Remove extra whitespace
        text = ' '.join(text.split())
        
        # Remove trailing punctuation except periods in numbered sections
        if not re.match(r'^\d+\.', text):
            text = re.sub(r'[.,:;!?]+$', '', text)
        
        # Remove leading/trailing quotes
        text = text.strip('"\'')
        
        return text
    
    def filter_and_deduplicate_headings(self, headings: List[Dict]) -> List[Dict]:
        """Filter out false positives and remove duplicates"""
        filtered_headings = []
        seen_texts = set()
        
        for heading in headings:
            text = heading["text"].lower().strip()
            
            # Skip very common false positives
            if text in {'and', 'or', 'the', 'of', 'in', 'on', 'at', 'to', 'for', 'with', 'by'}:
                continue
            
            # Skip duplicates
            if text in seen_texts:
                continue
            
            seen_texts.add(text)
            filtered_headings.append(heading)
        
        return filtered_headings
    
    def classify_headings(self, formatted_text: List[Dict]) -> List[Dict]:
        """Main heading classification with improved algorithm"""
        structure_info = self.analyze_document_structure(formatted_text)
        potential_headings = []
        
        for item in formatted_text:
            if self.is_likely_heading(item, structure_info):
                level = self.determine_heading_level(item, structure_info)
                clean_text = self.clean_heading_text(item["text"])
                
                if clean_text:  # Only add if text remains after cleaning
                    potential_headings.append({
                        "level": level,
                        "text": clean_text,
                        "page": item["page"]
                    })
        
        # Filter and deduplicate
        final_headings = self.filter_and_deduplicate_headings(potential_headings)
        
        # Sort by page and appearance order
        final_headings.sort(key=lambda x: (x["page"], x["text"]))
        
        return final_headings
    
    def extract_outline(self, pdf_path: str) -> Dict:
        """Main method to extract PDF outline with improved processing"""
        try:
            formatted_text = self.extract_text_with_formatting(pdf_path)
            
            if not formatted_text:
                return {
                    "title": "Empty Document",
                    "outline": []
                }
            
            title = self.identify_title(formatted_text)
            headings = self.classify_headings(formatted_text)
            
            return {
                "title": title,
                "outline": headings
            }
            
        except Exception as e:
            print(f"Error processing {pdf_path}: {str(e)}")
            return {
                "title": "Error Processing Document",
                "outline": []
            }
