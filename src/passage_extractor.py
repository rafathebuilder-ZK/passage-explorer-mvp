"""Passage extraction from documents."""
import re
from typing import List, Dict, Optional
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class PassageExtractor:
    """Extracts passages from document text."""
    
    def __init__(self, min_length: int = 100, max_length: int = 420):
        """Initialize passage extractor.
        
        Args:
            min_length: Minimum passage length in characters.
            max_length: Maximum passage length in characters.
        """
        self.min_length = min_length
        self.max_length = max_length
    
    def extract_passages(self, document_data: Dict, source_file: Path) -> List[Dict]:
        """Extract passages from document data.
        
        Args:
            document_data: Dictionary from document processor with 'text', 'metadata', 'paragraphs'.
            source_file: Path to source file (for absolute path storage).
            
        Returns:
            List of passage dictionaries ready for database storage.
        """
        paragraphs = document_data.get('paragraphs', [])
        full_text = document_data.get('text', '')
        metadata = document_data.get('metadata', {})
        sections = metadata.get('sections', [])
        paragraph_page_numbers = document_data.get('paragraph_page_numbers')
        
        passages = []
        char_offset = 0
        current_section = None
        
        for idx, para in enumerate(paragraphs):
            # Check if this paragraph is a section heading
            # (for HTML/MD, headings might be in paragraphs)
            para_stripped = para.strip()
            para_lower = para_stripped.lower()
            is_section_heading = False
            
            # Check if paragraph matches any section heading
            for section in sections:
                section_lower = section.lower().strip()
                # Exact match or paragraph starts with section heading
                if para_lower == section_lower or para_lower.startswith(section_lower + '\n') or para_lower.startswith(section_lower + ' '):
                    current_section = section
                    is_section_heading = True
                    break
            
            # Skip very short paragraphs
            if len(para_stripped) < self.min_length:
                char_offset += len(para) + 2  # +2 for paragraph separator
                continue
            
            # Skip section headings themselves (they're usually too short or not meaningful passages)
            if is_section_heading and len(para_stripped) < 100:
                char_offset += len(para) + 2
                continue
            
            # If paragraph fits in max_length, use it as-is
            if len(para) <= self.max_length:
                passage_text = para_stripped
                start_char = full_text.find(passage_text, char_offset)
                if start_char == -1:
                    start_char = char_offset
                end_char = start_char + len(passage_text)

                page_number = None
                if paragraph_page_numbers and 0 <= idx < len(paragraph_page_numbers):
                    page_number = paragraph_page_numbers[idx]
                
                passages.append({
                    'text': passage_text,
                    'source_file': str(source_file.resolve()),  # Absolute path
                    'file_type': metadata.get('file_type', 'txt'),
                    'page_number': page_number,
                    'line_number': self._get_line_number(full_text, start_char),
                    'chapter': None,
                    'section': current_section,
                    'document_title': metadata.get('document_title'),
                    'author': metadata.get('author'),
                    'start_char': start_char,
                    'end_char': end_char,
                })
            else:
                # Split long paragraph into sentences and combine
                sentences = self._split_sentences(para)
                current_passage: List[str] = []
                current_length = 0
                passage_start = char_offset
                
                for sentence in sentences:
                    sentence = sentence.strip()
                    if not sentence:
                        continue
                    
                    sentence_length = len(sentence)
                    
                    # If adding this sentence would exceed max_length, save current passage
                    if current_passage and current_length + sentence_length + 1 > self.max_length:
                        if current_length >= self.min_length:
                            passage_text = ' '.join(current_passage)
                            start_char = full_text.find(passage_text, passage_start)
                            if start_char == -1:
                                start_char = passage_start
                            end_char = start_char + len(passage_text)
                            
                            page_number = None
                            if paragraph_page_numbers and 0 <= idx < len(paragraph_page_numbers):
                                page_number = paragraph_page_numbers[idx]

                            passages.append({
                                'text': passage_text,
                                'source_file': str(source_file.resolve()),
                                'file_type': metadata.get('file_type', 'txt'),
                                'page_number': page_number,
                                'line_number': self._get_line_number(full_text, start_char),
                                'chapter': None,
                                'section': current_section,
                                'document_title': metadata.get('document_title'),
                                'author': metadata.get('author'),
                                'start_char': start_char,
                                'end_char': end_char,
                            })
                        
                        # Start new passage
                        current_passage = [sentence]
                        current_length = sentence_length
                        passage_start = char_offset + full_text[char_offset:].find(sentence)
                    else:
                        current_passage.append(sentence)
                        current_length += sentence_length + 1  # +1 for space
                
                # Add remaining passage if long enough
                if current_passage and current_length >= self.min_length:
                    passage_text = ' '.join(current_passage)
                    if len(passage_text) <= self.max_length:
                        start_char = full_text.find(passage_text, passage_start)
                        if start_char == -1:
                            start_char = passage_start
                        end_char = start_char + len(passage_text)
                        
                        page_number = None
                        if paragraph_page_numbers and 0 <= idx < len(paragraph_page_numbers):
                            page_number = paragraph_page_numbers[idx]

                        passages.append({
                            'text': passage_text,
                            'source_file': str(source_file.resolve()),
                            'file_type': metadata.get('file_type', 'txt'),
                            'page_number': page_number,
                            'line_number': self._get_line_number(full_text, start_char),
                            'chapter': None,
                            'section': current_section,
                            'document_title': metadata.get('document_title'),
                            'author': metadata.get('author'),
                            'start_char': start_char,
                            'end_char': end_char,
                        })
            
            # Update char_offset
            para_pos = full_text.find(para, char_offset)
            if para_pos != -1:
                char_offset = para_pos + len(para) + 2
            else:
                char_offset += len(para) + 2
        
        return passages
    
    def _split_sentences(self, text: str) -> List[str]:
        """Split text into sentences.
        
        Args:
            text: Text to split.
            
        Returns:
            List of sentences.
        """
        # Simple sentence splitting on . ! ? followed by space or end of string
        pattern = r'([.!?]+)\s+'
        sentences = re.split(pattern, text)
        
        # Recombine sentences with their punctuation
        result = []
        i = 0
        while i < len(sentences):
            if i + 1 < len(sentences) and sentences[i + 1] in ['.', '!', '?', '...']:
                result.append(sentences[i] + sentences[i + 1])
                i += 2
            elif sentences[i].strip():
                result.append(sentences[i])
                i += 1
            else:
                i += 1
        
        return [s.strip() for s in result if s.strip()]
    
    def _get_line_number(self, text: str, char_pos: int) -> Optional[int]:
        """Get line number for a character position.
        
        Args:
            text: Full text.
            char_pos: Character position.
            
        Returns:
            Line number (1-indexed) or None.
        """
        if char_pos < 0 or char_pos >= len(text):
            return None
        return text[:char_pos].count('\n') + 1
