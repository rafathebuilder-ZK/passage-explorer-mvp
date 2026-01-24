"""Document processor for extracting text from various file formats."""
from pathlib import Path
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class TextHandler:
    """Handler for plain text files."""
    
    def extract(self, file_path: Path) -> Dict:
        """Extract text and metadata from a text file.
        
        Args:
            file_path: Path to text file.
            
        Returns:
            Dictionary with 'text', 'metadata', and 'paragraphs' keys.
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            # Fallback to latin-1
            logger.warning(f"UTF-8 decode failed for {file_path}, trying latin-1")
            with open(file_path, 'r', encoding='latin-1') as f:
                content = f.read()
        
        # Extract metadata
        metadata = {
            'document_title': file_path.stem.replace('-', ' ').title(),
            'author': None,
            'file_type': 'txt',
        }
        
        # Split into paragraphs
        paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]
        
        return {
            'text': content,
            'metadata': metadata,
            'paragraphs': paragraphs,
        }


class HTMLHandler:
    """Handler for HTML files."""
    
    def extract(self, file_path: Path) -> Dict:
        """Extract text and metadata from an HTML file.
        
        Args:
            file_path: Path to HTML file.
            
        Returns:
            Dictionary with 'text', 'metadata', and 'paragraphs' keys.
        """
        try:
            from bs4 import BeautifulSoup
            import html2text
        except ImportError:
            logger.error("BeautifulSoup4 and html2text required for HTML processing")
            raise
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
        except UnicodeDecodeError:
            logger.warning(f"UTF-8 decode failed for {file_path}, trying latin-1")
            with open(file_path, 'r', encoding='latin-1') as f:
                html_content = f.read()
        
        # Parse HTML
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Extract metadata
        title_tag = soup.find('title')
        document_title = title_tag.get_text().strip() if title_tag else None
        
        # Try to get author from meta tag
        author_meta = soup.find('meta', attrs={'name': 'author'})
        author = author_meta.get('content') if author_meta else None
        
        # If no title from HTML, try h1
        if not document_title:
            h1 = soup.find('h1')
            if h1:
                document_title = h1.get_text().strip()
        
        # Fallback to filename
        if not document_title:
            document_title = file_path.stem.replace('-', ' ').title()
        
        # Convert HTML to text using html2text
        h = html2text.HTML2Text()
        h.ignore_links = True
        h.ignore_images = True
        h.body_width = 0  # Don't wrap lines
        text_content = h.handle(html_content)
        
        # Extract paragraphs from text (split by double newlines)
        paragraphs = [p.strip() for p in text_content.split('\n\n') if p.strip()]
        
        # Extract sections/chapters from headings
        sections = []
        for heading in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
            heading_text = heading.get_text().strip()
            if heading_text and heading_text not in sections:
                sections.append(heading_text)
        
        metadata = {
            'document_title': document_title,
            'author': author,
            'file_type': 'html',
            'sections': sections,
        }
        
        return {
            'text': text_content,
            'metadata': metadata,
            'paragraphs': paragraphs,
        }


class MarkdownHandler:
    """Handler for Markdown files."""
    
    def extract(self, file_path: Path) -> Dict:
        """Extract text and metadata from a Markdown file.
        
        Args:
            file_path: Path to Markdown file.
            
        Returns:
            Dictionary with 'text', 'metadata', and 'paragraphs' keys.
        """
        try:
            import markdown
            from markdown.extensions import Extension
            from markdown.treeprocessors import Treeprocessor
        except ImportError:
            logger.error("markdown library required for Markdown processing")
            raise
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                md_content = f.read()
        except UnicodeDecodeError:
            logger.warning(f"UTF-8 decode failed for {file_path}, trying latin-1")
            with open(file_path, 'r', encoding='latin-1') as f:
                md_content = f.read()
        
        # Extract metadata - look for title in first heading
        lines = md_content.split('\n')
        document_title = None
        author = None
        sections = []
        
        # Find first h1 or h2 as title
        for line in lines[:20]:  # Check first 20 lines
            line_stripped = line.strip()
            if line_stripped.startswith('# '):
                document_title = line_stripped[2:].strip()
                break
            elif line_stripped.startswith('## ') and not document_title:
                document_title = line_stripped[3:].strip()
                break
        
        # Look for author in bold on second line (common pattern)
        if len(lines) > 1:
            second_line = lines[1].strip()
            if second_line.startswith('**') and second_line.endswith('**'):
                author = second_line.strip('*').strip()
        
        # Extract all headings for sections
        for line in lines:
            line_stripped = line.strip()
            if line_stripped.startswith('#'):
                # Extract heading text (remove # and leading/trailing spaces)
                heading_text = line_stripped.lstrip('#').strip()
                if heading_text and heading_text not in sections:
                    sections.append(heading_text)
        
        # Fallback to filename if no title found
        if not document_title:
            document_title = file_path.stem.replace('-', ' ').title()
        
        # Convert Markdown to plain text (simple approach - just strip markdown syntax)
        # For better results, we could use markdown library to convert to HTML then to text
        # But for passage extraction, plain text with markdown stripped is sufficient
        text_content = md_content
        
        # Split into paragraphs (double newlines)
        paragraphs = [p.strip() for p in text_content.split('\n\n') if p.strip()]
        
        # Remove markdown syntax from paragraphs for cleaner extraction
        import re
        cleaned_paragraphs = []
        for para in paragraphs:
            # Remove markdown headers
            para = re.sub(r'^#+\s+', '', para)
            # Remove bold/italic
            para = re.sub(r'\*\*([^*]+)\*\*', r'\1', para)
            para = re.sub(r'\*([^*]+)\*', r'\1', para)
            # Remove links [text](url) -> text
            para = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', para)
            cleaned_paragraphs.append(para.strip())
        
        paragraphs = [p for p in cleaned_paragraphs if p]
        
        metadata = {
            'document_title': document_title,
            'author': author,
            'file_type': 'md',
            'sections': sections,
        }
        
        return {
            'text': text_content,
            'metadata': metadata,
            'paragraphs': paragraphs,
        }


class PDFHandler:
    """Handler for PDF files (page-aware text extraction)."""
    
    def extract(self, file_path: Path) -> Dict:
        """Extract text and metadata from a PDF file.
        
        Args:
            file_path: Path to PDF file.
            
        Returns:
            Dictionary with 'text', 'metadata', 'paragraphs', and 'paragraph_page_numbers' keys.
        """
        try:
            import pdfplumber
        except ImportError:
            logger.error("pdfplumber required for PDF processing")
            raise

        paragraphs: List[str] = []
        paragraph_page_numbers: List[int] = []
        full_text_parts: List[str] = []

        with pdfplumber.open(str(file_path)) as pdf:
            pdf_metadata = pdf.metadata or {}
            title = pdf_metadata.get("Title") or file_path.stem.replace('-', ' ').title()
            author = pdf_metadata.get("Author")

            for page_index, page in enumerate(pdf.pages, start=1):
                try:
                    page_text = page.extract_text() or ""
                except Exception as e:
                    logger.warning(f"Failed to extract text from page {page_index} of {file_path}: {e}")
                    continue

                if not page_text.strip():
                    continue

                full_text_parts.append(page_text)

                # Split page text into paragraphs by double newlines
                for para in page_text.split("\n\n"):
                    para = para.strip()
                    if not para:
                        continue
                    paragraphs.append(para)
                    paragraph_page_numbers.append(page_index)

        full_text = "\n\n".join(full_text_parts)

        metadata = {
            "document_title": title,
            "author": author,
            "file_type": "pdf",
        }

        return {
            "text": full_text,
            "metadata": metadata,
            "paragraphs": paragraphs,
            "paragraph_page_numbers": paragraph_page_numbers,
        }


class DocumentProcessor:
    """Multi-format document processor."""
    
    def __init__(self):
        """Initialize document processor with format handlers."""
        self.handlers = {
            '.txt': TextHandler(),
            '.html': HTMLHandler(),
            '.htm': HTMLHandler(),
            '.md': MarkdownHandler(),
            '.markdown': MarkdownHandler(),
            '.pdf': PDFHandler(),
        }
        # PDF handler added in Stage 4
    
    def process(self, file_path: Path) -> Optional[Dict]:
        """Process a document file.
        
        Args:
            file_path: Path to document file.
            
        Returns:
            Dictionary with extracted text and metadata, or None if unsupported format.
        """
        ext = file_path.suffix.lower()
        handler = self.handlers.get(ext)
        
        if not handler:
            logger.warning(f"Unsupported file type: {ext} for {file_path}")
            return None
        
        try:
            return handler.extract(file_path)
        except Exception as e:
            logger.error(f"Error processing {file_path}: {e}")
            return None
