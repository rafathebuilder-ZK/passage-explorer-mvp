#!/usr/bin/env python3
"""
Script to create PDF files from text files in Library-Sample/txt/
Creates basic PDFs using only standard library (no external dependencies).
"""

import os
from pathlib import Path
from datetime import datetime

def escape_pdf_string(text):
    """Escape special characters for PDF strings."""
    return text.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')

def create_pdf_from_text(txt_path, pdf_path, title, author):
    """Create a basic PDF from a text file."""
    
    # Read the text file
    with open(txt_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Process content into lines
    lines = content.split('\n')
    
    # Skip title and author lines if they're at the start
    i = 0
    if i < len(lines) and lines[i].strip().upper() == title.upper():
        i += 1
    if i < len(lines) and not lines[i].strip():
        i += 1
    if i < len(lines) and lines[i].strip() == author:
        i += 1
    if i < len(lines) and not lines[i].strip():
        i += 1
    
    # Collect processed lines
    processed_lines = []
    while i < len(lines):
        line = lines[i].strip()
        if line:
            processed_lines.append(line)
        else:
            processed_lines.append('')  # Preserve paragraph breaks
        i += 1
    
    # PDF constants
    page_width = 612  # 8.5 inches * 72 points/inch
    page_height = 792  # 11 inches * 72 points/inch
    margin = 72
    line_height = 14
    font_size = 11
    y_start = page_height - margin
    y = y_start
    current_page = 1
    
    # PDF content buffer
    pdf_content = []
    page_objects = []
    
    def add_text(x, y_pos, text, font='Helvetica', size=11, style=''):
        """Add text to PDF content."""
        if style == 'B':
            font = 'Helvetica-Bold'
        elif style == 'I':
            font = 'Helvetica-Oblique'
        return f"BT\n/F{font} {size} Tf\n{x} {y_pos} Td\n({escape_pdf_string(text)}) Tj\nET"
    
    def new_page():
        """Start a new page."""
        nonlocal y, current_page
        current_page += 1
        y = y_start
        return f"\n{current_page} 0 obj\n<<\n/Type /Page\n/Parent 2 0 R\n/Resources <<\n/Font <<\n/FHelvetica <<\n/Type /Font\n/Subtype /Type1\n/BaseFont /Helvetica\n>>\n/FHelvetica-Bold <<\n/Type /Font\n/Subtype /Type1\n/BaseFont /Helvetica-Bold\n>>\n/FHelvetica-Oblique <<\n/Type /Font\n/Subtype /Type1\n/BaseFont /Helvetica-Oblique\n>>\n>>\n>>\n/MediaBox [0 0 {page_width} {page_height}]\n/Contents {current_page + 10} 0 R\n>>\nendobj\n"
    
    # Build PDF structure
    obj_count = 1
    
    # Catalog
    catalog_obj = f"{obj_count} 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n"
    obj_count += 1
    
    # Pages object (will be updated with page count)
    pages_obj_start = f"{obj_count} 0 obj\n<<\n/Type /Pages\n/Kids ["
    obj_count += 1
    
    # Title page
    page_content = []
    y = y_start
    page_content.append(add_text(page_width/2 - 100, y, title, 'Helvetica', 20, 'B'))
    y -= 40
    if author:
        page_content.append(add_text(page_width/2 - 50, y, author, 'Helvetica', 14))
        y -= 30
    y -= 20
    
    # Add page number
    page_content.append(add_text(page_width - 100, 30, f"Page {current_page}", 'Helvetica', 9))
    
    page_objects.append(f"{obj_count} 0 obj\n<<\n/Type /Page\n/Parent 2 0 R\n/Resources <<\n/Font <<\n/FHelvetica <<\n/Type /Font\n/Subtype /Type1\n/BaseFont /Helvetica\n>>\n/FHelvetica-Bold <<\n/Type /Font\n/Subtype /Type1\n/BaseFont /Helvetica-Bold\n>>\n>>\n>>\n/MediaBox [0 0 {page_width} {page_height}]\n/Contents {obj_count + 1} 0 R\n>>\nendobj\n")
    obj_count += 1
    
    # Content stream for title page
    content_stream = f"q\n" + "\n".join(page_content) + "\nQ\n"
    page_objects.append(f"{obj_count} 0 obj\n<<\n/Length {len(content_stream)}\n>>\nstream\n{content_stream}endstream\nendobj\n")
    obj_count += 1
    
    current_page = 1
    
    # Process text lines
    y = y_start
    page_content = []
    
    for line in processed_lines:
        if not line:
            y -= line_height
            if y < margin + 20:
                # New page
                page_objects.append(f"{obj_count} 0 obj\n<<\n/Type /Page\n/Parent 2 0 R\n/Resources <<\n/Font <<\n/FHelvetica <<\n/Type /Font\n/Subtype /Type1\n/BaseFont /Helvetica\n>>\n/FHelvetica-Bold <<\n/Type /Font\n/Subtype /Type1\n/BaseFont /Helvetica-Bold\n>>\n>>\n>>\n/MediaBox [0 0 {page_width} {page_height}]\n/Contents {obj_count + 1} 0 R\n>>\nendobj\n")
                obj_count += 1
                content_stream = f"q\n" + "\n".join(page_content) + "\nQ\n"
                page_objects.append(f"{obj_count} 0 obj\n<<\n/Length {len(content_stream)}\n>>\nstream\n{content_stream}endstream\nendobj\n")
                obj_count += 1
                current_page += 1
                y = y_start
                page_content = []
            continue
        
        # Check if heading
        is_heading = (line.isupper() and len(line) > 5) or line.startswith('CHAPTER') or line.startswith('Chapter')
        
        if is_heading:
            y -= 15
            if y < margin + 20:
                # New page
                page_objects.append(f"{obj_count} 0 obj\n<<\n/Type /Page\n/Parent 2 0 R\n/Resources <<\n/Font <<\n/FHelvetica <<\n/Type /Font\n/Subtype /Type1\n/BaseFont /Helvetica\n>>\n/FHelvetica-Bold <<\n/Type /Font\n/Subtype /Type1\n/BaseFont /Helvetica-Bold\n>>\n>>\n>>\n/MediaBox [0 0 {page_width} {page_height}]\n/Contents {obj_count + 1} 0 R\n>>\nendobj\n")
                obj_count += 1
                content_stream = f"q\n" + "\n".join(page_content) + "\nQ\n"
                page_objects.append(f"{obj_count} 0 obj\n<<\n/Length {len(content_stream)}\n>>\nstream\n{content_stream}endstream\nendobj\n")
                obj_count += 1
                current_page += 1
                y = y_start
                page_content = []
            
            page_content.append(add_text(margin, y, line, 'Helvetica', 14, 'B'))
            y -= 20
        else:
            # Regular text - wrap if needed
            words = line.split()
            current_line = []
            line_width = 0
            max_width = page_width - 2 * margin
            
            for word in words:
                word_width = len(word) * 6  # Approximate
                if line_width + word_width > max_width and current_line:
                    # Output current line
                    line_text = ' '.join(current_line)
                    if y < margin + 20:
                        # New page
                        page_objects.append(f"{obj_count} 0 obj\n<<\n/Type /Page\n/Parent 2 0 R\n/Resources <<\n/Font <<\n/FHelvetica <<\n/Type /Font\n/Subtype /Type1\n/BaseFont /Helvetica\n>>\n/FHelvetica-Bold <<\n/Type /Font\n/Subtype /Type1\n/BaseFont /Helvetica-Bold\n>>\n>>\n>>\n/MediaBox [0 0 {page_width} {page_height}]\n/Contents {obj_count + 1} 0 R\n>>\nendobj\n")
                        obj_count += 1
                        content_stream = f"q\n" + "\n".join(page_content) + "\nQ\n"
                        page_objects.append(f"{obj_count} 0 obj\n<<\n/Length {len(content_stream)}\n>>\nstream\n{content_stream}endstream\nendobj\n")
                        obj_count += 1
                        current_page += 1
                        y = y_start
                        page_content = []
                    
                    page_content.append(add_text(margin, y, line_text, 'Helvetica', font_size))
                    y -= line_height
                    current_line = [word]
                    line_width = len(word) * 6
                else:
                    current_line.append(word)
                    line_width += word_width + 6  # word + space
            
            # Output remaining words
            if current_line:
                line_text = ' '.join(current_line)
                if y < margin + 20:
                    # New page
                    page_objects.append(f"{obj_count} 0 obj\n<<\n/Type /Page\n/Parent 2 0 R\n/Resources <<\n/Font <<\n/FHelvetica <<\n/Type /Font\n/Subtype /Type1\n/BaseFont /Helvetica\n>>\n/FHelvetica-Bold <<\n/Type /Font\n/Subtype /Type1\n/BaseFont /Helvetica-Bold\n>>\n>>\n>>\n/MediaBox [0 0 {page_width} {page_height}]\n/Contents {obj_count + 1} 0 R\n>>\nendobj\n")
                    obj_count += 1
                    content_stream = f"q\n" + "\n".join(page_content) + "\nQ\n"
                    page_objects.append(f"{obj_count} 0 obj\n<<\n/Length {len(content_stream)}\n>>\nstream\n{content_stream}endstream\nendobj\n")
                    obj_count += 1
                    current_page += 1
                    y = y_start
                    page_content = []
                
                page_content.append(add_text(margin, y, line_text, 'Helvetica', font_size))
                y -= line_height
        
        # Add page number
        if not page_content or 'Page' not in str(page_content[-1]):
            page_content.append(add_text(page_width - 100, 30, f"Page {current_page}", 'Helvetica', 9))
    
    # Final page
    if page_content:
        page_objects.append(f"{obj_count} 0 obj\n<<\n/Type /Page\n/Parent 2 0 R\n/Resources <<\n/Font <<\n/FHelvetica <<\n/Type /Font\n/Subtype /Type1\n/BaseFont /Helvetica\n>>\n/FHelvetica-Bold <<\n/Type /Font\n/Subtype /Type1\n/BaseFont /Helvetica-Bold\n>>\n>>\n>>\n/MediaBox [0 0 {page_width} {page_height}]\n/Contents {obj_count + 1} 0 R\n>>\nendobj\n")
        obj_count += 1
        content_stream = f"q\n" + "\n".join(page_content) + "\nQ\n"
        page_objects.append(f"{obj_count} 0 obj\n<<\n/Length {len(content_stream)}\n>>\nstream\n{content_stream}endstream\nendobj\n")
        obj_count += 1
    
    total_pages = current_page
    
    # Complete pages object
    page_refs = ' '.join([f"{i*2 + 3} 0 R" for i in range(total_pages)])
    pages_obj = f"2 0 obj\n<<\n/Type /Pages\n/Kids [{page_refs}]\n/Count {total_pages}\n>>\nendobj\n"
    
    # Build complete PDF
    pdf_parts = [
        "%PDF-1.4",
        catalog_obj,
        pages_obj,
    ] + page_objects
    
    # Add xref table
    xref_offset = sum(len(part.encode('utf-8')) for part in pdf_parts) + len("%PDF-1.4\n".encode('utf-8'))
    xref = f"xref\n0 {obj_count}\n0000000000 65535 f \n"
    offset = len("%PDF-1.4\n".encode('utf-8'))
    
    for i, part in enumerate(pdf_parts[1:], 1):
        xref += f"{offset:010d} 00000 n \n"
        offset += len(part.encode('utf-8'))
    
    # Trailer
    now = datetime.now()
    creation_date = now.strftime("D:%Y%m%d%H%M%S")
    trailer = f"trailer\n<<\n/Size {obj_count}\n/Root 1 0 R\n/Info <<\n/Title ({escape_pdf_string(title)})\n/Author ({escape_pdf_string(author or 'Unknown')})\n/CreationDate ({creation_date})\n>>\n>>\nstartxref\n{offset}\n%%EOF"
    
    # Write PDF
    with open(pdf_path, 'wb') as f:
        f.write("%PDF-1.4\n".encode('utf-8'))
        for part in pdf_parts[1:]:
            f.write(part.encode('utf-8'))
        f.write(xref.encode('utf-8'))
        f.write(trailer.encode('utf-8'))

def main():
    """Generate PDFs for all text files."""
    base_dir = Path(__file__).parent
    txt_dir = base_dir / 'Library-Sample' / 'txt'
    pdf_dir = base_dir / 'Library-Sample' / 'pdf'
    
    # Ensure PDF directory exists
    pdf_dir.mkdir(parents=True, exist_ok=True)
    
    # Map of files to their metadata
    files_metadata = {
        'alice-in-wonderland.txt': {
            'title': "Alice's Adventures in Wonderland",
            'author': 'Lewis Carroll'
        },
        'pride-and-prejudice.txt': {
            'title': 'Pride and Prejudice',
            'author': 'Jane Austen'
        },
        'moby-dick.txt': {
            'title': 'Moby-Dick; or The Whale',
            'author': 'Herman Melville'
        },
        'sherlock-holmes.txt': {
            'title': 'A Scandal in Bohemia',
            'author': 'Arthur Conan Doyle'
        },
        'tale-of-two-cities.txt': {
            'title': 'A Tale of Two Cities',
            'author': 'Charles Dickens'
        }
    }
    
    for filename, metadata in files_metadata.items():
        txt_path = txt_dir / filename
        pdf_filename = filename.replace('.txt', '.pdf')
        pdf_path = pdf_dir / pdf_filename
        
        if txt_path.exists():
            print(f"Creating {pdf_filename}...")
            try:
                create_pdf_from_text(
                    txt_path,
                    pdf_path,
                    metadata['title'],
                    metadata['author']
                )
                print(f"  ✓ Created {pdf_filename}")
            except Exception as e:
                print(f"  ✗ Error creating {pdf_filename}: {e}")
                import traceback
                traceback.print_exc()
        else:
            print(f"  ✗ Source file not found: {txt_path}")

if __name__ == '__main__':
    main()
