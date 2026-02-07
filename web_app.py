"""
Full-featured Streamlit web demo for Passage Explorer.

This web app replicates all functionality from the terminal app:
- New passage (n): Load random passage not shown in last 30 days
- Horizontal expansion (h): Show 2 semantically related passages
- Context expansion (c): Show ~400 words of context around passage
- Save passage (s): Save to database and CSV
- Index next batch (i): Manually trigger indexing of pending files
- Help (?): Show usage information

Uses Library SOP as the demo library.

Run locally with:
    streamlit run web_app.py
"""

from __future__ import annotations

import csv
import json
import logging
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import streamlit as st

from src.config import Config
from src.document_processor import DocumentProcessor
from src.passage_extractor import PassageExtractor
from src.passage_store import Passage, PassageStore
from src.similarity import SimilarityEngine

logger = logging.getLogger(__name__)

# ---------- Configuration ----------

PROJECT_ROOT = Path(__file__).parent
DEFAULT_LIBRARY_PATH = PROJECT_ROOT / "Library SOP"
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "passages.db"

# Initialize logging
logging.basicConfig(level=logging.INFO)


# ---------- Helper Functions ----------

def get_passage_store() -> PassageStore:
    """Get a shared PassageStore instance for the app."""
    if "passage_store" not in st.session_state:
        st.session_state.passage_store = PassageStore(str(DEFAULT_DB_PATH))
    return st.session_state.passage_store


def get_config() -> Config:
    """Get a shared Config instance for the app."""
    if "config" not in st.session_state:
        st.session_state.config = Config()
        # Override library path to Library SOP
        st.session_state.config.set("library_path", str(DEFAULT_LIBRARY_PATH))
        st.session_state.config.set("library_path_absolute", False)
    return st.session_state.config


def clear_all_database_data() -> dict:
    """Clear all database data: passages, sessions, indexing status, saved passages.
    
    Returns:
        Dictionary with counts of deleted records.
    """
    store = get_passage_store()
    passage_count = store.delete_all_passages()
    reset_results = store.reset_all(archive=True)
    return {
        'passages': passage_count,
        **reset_results
    }


def get_similarity_engine() -> SimilarityEngine:
    """Get a shared SimilarityEngine instance for the app (lazy-loaded).
    
    The similarity engine is only loaded when first needed (e.g., for horizontal expansion).
    This avoids blocking the UI during app startup.
    """
    if "similarity_engine" not in st.session_state:
        st.session_state.similarity_engine = None
    
    if st.session_state.similarity_engine is None:
        config = get_config()
        # Show spinner only if we're in a user-facing context (not during background ops)
        if st.session_state.get("view_mode") == "main" or st.session_state.get("view_mode") is None:
            with st.spinner("Loading similarity model (first time only, ~10-30 seconds)..."):
                st.session_state.similarity_engine = SimilarityEngine(config)
        else:
            # During background operations, load without spinner
            st.session_state.similarity_engine = SimilarityEngine(config)
    
    return st.session_state.similarity_engine


def get_document_processor() -> DocumentProcessor:
    """Get a shared DocumentProcessor instance for the app."""
    if "document_processor" not in st.session_state:
        st.session_state.document_processor = DocumentProcessor()
    return st.session_state.document_processor


def get_passage_extractor() -> PassageExtractor:
    """Get a shared PassageExtractor instance for the app."""
    if "passage_extractor" not in st.session_state:
        config = get_config()
        st.session_state.passage_extractor = PassageExtractor(
            min_length=100,
            max_length=config.get("max_passage_length", 420),
        )
    return st.session_state.passage_extractor


def get_context_for_passage(passage: Passage) -> str:
    """Get ~400-word context around a passage."""
    # Use PDF-specific extraction for PDF files
    if passage.file_type == "pdf":
        return _get_pdf_context_for_passage(passage)

    # For text-based files (txt, html, md), read as text
    try:
        file_path = Path(passage.source_file)
        try:
            text = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = file_path.read_text(encoding="latin-1")
    except Exception as e:
        logger.error("Failed to read source file for context: %s", e)
        return passage.text

    start = max(0, passage.start_char - 1200)
    end = min(len(text), passage.end_char + 1200)
    context = text[start:end]
    return context.strip()


def _get_pdf_context_for_passage(passage: Passage) -> str:
    """Get context for a PDF passage using pdfplumber."""
    try:
        import pdfplumber
    except ImportError:
        logger.error("pdfplumber required for PDF context extraction")
        return passage.text

    try:
        file_path = Path(passage.source_file)
        if not file_path.exists():
            logger.error(f"PDF file not found: {file_path}")
            return passage.text

        with pdfplumber.open(str(file_path)) as pdf:
            # Get the page containing the passage
            page_num = passage.page_number
            if page_num is None or page_num < 1 or page_num > len(pdf.pages):
                # Fallback: try to find page from passage text
                logger.warning(
                    f"Invalid page number {page_num} for passage, trying all pages"
                )
                # Extract text from all pages and find the passage
                full_text = ""
                for page in pdf.pages:
                    page_text = page.extract_text() or ""
                    full_text += page_text + "\n\n"

                # Find passage in full text and extract context
                passage_pos = full_text.find(passage.text)
                if passage_pos == -1:
                    return passage.text

                start = max(0, passage_pos - 1200)
                end = min(len(full_text), passage_pos + len(passage.text) + 1200)
                context = full_text[start:end]
                return context.strip()

            # Extract text from the page containing the passage
            page = pdf.pages[page_num - 1]  # pdfplumber uses 0-based indexing
            page_text = page.extract_text() or ""

            if not page_text.strip():
                logger.warning(f"Page {page_num} has no extractable text")
                return passage.text

            # Find the passage text in the page
            passage_pos = page_text.find(passage.text)
            if passage_pos == -1:
                # Passage not found in page text - return page text as context
                logger.warning(
                    f"Passage text not found in page {page_num}, returning full page"
                )
                return page_text.strip()

            # Extract context around the passage (~400 words = ~2000 chars)
            context_size = 2000
            start = max(0, passage_pos - context_size)
            end = min(len(page_text), passage_pos + len(passage.text) + context_size)
            context = page_text[start:end]

            # Clean up whitespace - normalize multiple spaces/newlines
            context = re.sub(r"\n{3,}", "\n\n", context)  # Max 2 newlines
            context = re.sub(r" {2,}", " ", context)  # Max 1 space

            return context.strip()

    except Exception as e:
        logger.error(f"Error extracting PDF context: {e}", exc_info=True)
        return passage.text


def save_passage_to_csv(passage: Passage) -> None:
    """Append passage metadata to CSV export."""
    data_dir = PROJECT_ROOT / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    csv_path = data_dir / "saved_passages.csv"

    is_new = not csv_path.exists()
    with csv_path.open("a", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        if is_new:
            writer.writerow(
                [
                    "saved_at",
                    "text",
                    "document_title",
                    "location",
                    "filename",
                    "file_type",
                    "author",
                    "chapter",
                ]
            )

        location_parts = []
        if passage.page_number:
            location_parts.append(f"Page {passage.page_number}")
        elif passage.line_number:
            location_parts.append(f"Line {passage.line_number}")
        if passage.section:
            location_parts.append(f"Section: {passage.section}")
        if passage.chapter:
            location_parts.append(f"Chapter: {passage.chapter}")
        location = " / ".join(location_parts) if location_parts else ""

        file_name = Path(passage.source_file).name
        writer.writerow(
            [
                datetime.now(timezone.utc).isoformat() + "Z",
                passage.text,
                passage.document_title or "",
                location,
                file_name,
                passage.file_type,
                passage.author or "",
                passage.chapter or "",
            ]
        )


def get_related_passages(passage: Passage, top_k: int = 2) -> list[Passage]:
    """Get related passages using semantic similarity (with fallback).
    
    This will trigger lazy loading of the similarity engine if not already loaded.
    """
    store = get_passage_store()
    # This will show a spinner on first use
    similarity = get_similarity_engine()
    return similarity.find_related_passages(store, passage, top_k=top_k)


def manual_index_next_batch(library_path: Path) -> tuple[bool, str]:
    """Manually trigger indexing of the next batch of files.
    
    Returns:
        (success, message)
    """
    store = get_passage_store()
    config = get_config()
    processor = get_document_processor()
    extractor = get_passage_extractor()
    # Don't load similarity engine here - embeddings can be computed later if needed
    # similarity = get_similarity_engine()  # Removed to avoid blocking

    # Check if there are any pending files
    pending = store.get_pending_files(
        limit=config.get("progressive_indexing_batch_size", 4)
    )
    if not pending:
        return False, "No files pending indexing."

    # Get batch size
    batch_size = config.get("progressive_indexing_batch_size", 4)
    files_to_index = [Path(p) for p in pending[:batch_size]]

    logger.info(f"Indexing {len(files_to_index)} file(s)...")

    indexed_count = 0
    for file_path in files_to_index:
        abs_path = str(file_path.resolve())

        try:
            # Mark as indexing
            store.set_indexing_status(abs_path, "indexing")

            # Process file
            is_pdf = file_path.suffix.lower() == ".pdf"
            timeout_seconds = 300.0 if is_pdf else None

            try:
                doc_data = processor.process(file_path, timeout_seconds=timeout_seconds)
            except TimeoutError as e:
                error_msg = f"PDF indexing timeout after 5 minutes: {e}"
                logger.warning(error_msg)
                store.set_indexing_status(abs_path, "failed", error_msg)
                continue

            if not doc_data:
                store.set_indexing_status(abs_path, "failed", "Unsupported format or processing error")
                continue

            # Extract passages
            passages = extractor.extract_passages(doc_data, file_path)

            # Store passages (skip embeddings for faster indexing - can be computed later)
            for passage_data in passages:
                # Embeddings will be computed on-demand when needed for horizontal expansion
                # if similarity.enabled:
                #     emb = similarity.embed_text(passage_data["text"])
                #     if emb is not None:
                #         passage_data["embedding"] = json.dumps(emb)
                store.add_passage(passage_data)

            # Mark as completed
            store.set_indexing_status(abs_path, "completed")
            indexed_count += 1
            logger.info(f"Indexed {file_path.name}: {len(passages)} passages")

        except Exception as e:
            logger.error(f"Error indexing {file_path}: {e}")
            store.set_indexing_status(abs_path, "failed", str(e))

    # Log usage event
    store.log_usage_event("index_batch")
    total_indexed = store.get_indexed_file_count()
    return True, f"Indexing batch complete. Files indexed so far: {total_indexed}."


def start_background_indexing(library_path: Path) -> None:
    """Start background indexing thread if not already started.
    
    Note: Similarity engine is NOT loaded here to avoid blocking startup.
    Embeddings can be computed later when needed for horizontal expansion.
    """
    if st.session_state.get("indexing_thread_started", False):
        return

    store = get_passage_store()
    config = get_config()
    processor = get_document_processor()
    extractor = get_passage_extractor()
    # Don't load similarity engine here - it's heavy and not needed for indexing
    # similarity = get_similarity_engine()  # Removed to avoid blocking

    def worker():
        logger.info("Background indexing thread started.")
        while True:
            # Get a small set of pending files
            pending = store.get_pending_files(
                limit=config.get("progressive_indexing_batch_size", 4)
            )
            if not pending:
                logger.info("Background indexing: no more pending files.")
                break

            # Index the batch
            batch_size = config.get("progressive_indexing_batch_size", 4)
            files_to_index = [Path(p) for p in pending[:batch_size]]

            for file_path in files_to_index:
                abs_path = str(file_path.resolve())

                try:
                    store.set_indexing_status(abs_path, "indexing")

                    is_pdf = file_path.suffix.lower() == ".pdf"
                    timeout_seconds = 300.0 if is_pdf else None

                    try:
                        doc_data = processor.process(file_path, timeout_seconds=timeout_seconds)
                    except TimeoutError:
                        error_msg = "PDF indexing timeout after 5 minutes"
                        logger.warning(error_msg)
                        store.set_indexing_status(abs_path, "failed", error_msg)
                        continue

                    if not doc_data:
                        store.set_indexing_status(abs_path, "failed", "Unsupported format")
                        continue

                    passages = extractor.extract_passages(doc_data, file_path)

                    for passage_data in passages:
                        # Skip embeddings during background indexing for speed
                        # They can be computed on-demand when needed for horizontal expansion
                        # if similarity.enabled:
                        #     emb = similarity.embed_text(passage_data["text"])
                        #     if emb is not None:
                        #         passage_data["embedding"] = json.dumps(emb)
                        store.add_passage(passage_data)

                    store.set_indexing_status(abs_path, "completed")
                    logger.info(f"Indexed {file_path.name}: {len(passages)} passages")

                except Exception as e:
                    logger.error(f"Error indexing {file_path}: {e}")
                    store.set_indexing_status(abs_path, "failed", str(e))

        logger.info("Background indexing thread finished.")
        st.session_state.indexing_thread_started = False

    t = threading.Thread(target=worker, daemon=True)
    t.start()
    st.session_state.indexing_thread_started = True


# ---------- UI Components ----------


def display_passage(passage: Passage) -> None:
    """Display a passage with metadata."""
    # Record that this passage was shown
    store = get_passage_store()
    store.record_session_passage(passage.id)

    # Build metadata
    metadata_lines = []

    if passage.document_title:
        metadata_lines.append(f"**Source:** {passage.document_title}")

    location_parts = []
    if passage.page_number:
        location_parts.append(f"Page {passage.page_number}")
    elif passage.line_number:
        location_parts.append(f"Line {passage.line_number}")
    if passage.section:
        location_parts.append(f"Section: {passage.section}")
    if passage.chapter:
        location_parts.append(f"Chapter: {passage.chapter}")

    if location_parts:
        metadata_lines.append(f"**Location:** {' / '.join(location_parts)}")

    file_path = Path(passage.source_file)
    metadata_lines.append(f"**File:** {file_path.name}")
    metadata_lines.append(f"**Type:** {passage.file_type.upper()}")

    if passage.author:
        metadata_lines.append(f"**Author:** {passage.author}")

    # Display passage
    st.markdown("### Passage")
    st.markdown(f'<div style="font-size: 1.1em; line-height: 1.6; padding: 1em; background-color: #f0f2f6; border-radius: 5px; color: #333333;">{passage.text}</div>', unsafe_allow_html=True)

    # Display metadata
    st.markdown("### Metadata")
    st.markdown("\n".join(metadata_lines))


def format_passage_text(text: str) -> str:
    """Format passage text for better presentation.
    
    Normalizes line breaks, removes excessive whitespace, and handles
    broken lines that should be joined.
    """
    import re
    
    # Normalize all whitespace - replace multiple spaces/newlines with single space
    text = re.sub(r'\s+', ' ', text)
    
    # Remove leading/trailing whitespace
    text = text.strip()
    
    return text


def display_horizontal_view(base_passage: Passage, related_passages: list[Passage]) -> None:
    """Display horizontal exploration view as responses to the original passage."""
    st.markdown("## Horizontal Exploration")
    
    # Return button at top
    if st.button("Return", use_container_width=False, key="return_horizontal"):
        st.session_state.view_mode = "main"
        st.rerun()
    
    st.markdown("---")

    # Base passage
    st.markdown("### Original Passage")
    formatted_text = format_passage_text(base_passage.text)
    passage_text_escaped = formatted_text.replace('"', '&quot;').replace("'", "&#39;")
    st.markdown(
        f'<div class="passage-box" style="font-size: 1.05em; line-height: 1.6; padding: 1em; background-color: #252526; border: 1px solid #3e3e42; border-radius: 5px; margin-bottom: 1em; color: #d4d4d4; font-family: \'Courier New\', monospace;">{passage_text_escaped}</div>',
        unsafe_allow_html=True,
    )
    st.caption(f"From: {Path(base_passage.source_file).name}")
    
    st.markdown("---")
    st.markdown("### Related Passages")
    
    # Related passages as responses (stacked vertically)
    for idx, related_passage in enumerate(related_passages, 1):
        formatted_related = format_passage_text(related_passage.text)
        related_text_escaped = formatted_related.replace('"', '&quot;').replace("'", "&#39;")
        st.markdown(
            f'<div class="passage-box" style="font-size: 1.05em; line-height: 1.6; padding: 1em; background-color: #252526; border: 1px solid #3e3e42; border-left: 3px solid #4ec9b0; border-radius: 5px; margin-bottom: 1em; color: #d4d4d4; font-family: \'Courier New\', monospace;">{related_text_escaped}</div>',
            unsafe_allow_html=True,
        )
        st.caption(f"From: {Path(related_passage.source_file).name}")
        if idx < len(related_passages):
            st.markdown("---")


def display_context_view(passage: Passage, context_text: str) -> None:
    """Display context expansion view."""
    st.markdown("## Context Expansion")
    
    # Return button at top
    if st.button("Return", use_container_width=False, key="return_context"):
        st.session_state.view_mode = "main"
        st.rerun()
    
    st.markdown("---")

    # Format the passage text for highlighting
    formatted_passage = format_passage_text(passage.text)
    
    # Highlight the passage text in context
    highlighted_context = context_text.replace(
        passage.text,
        f'<mark style="background-color: #ffeb3b; padding: 2px 0;">{formatted_passage}</mark>'
    )

    st.markdown(
        f'<div style="font-size: 1em; line-height: 1.8; padding: 1em; background-color: #252526; border: 1px solid #3e3e42; border-radius: 5px; white-space: pre-wrap; color: #d4d4d4; font-family: \'Courier New\', monospace;">{highlighted_context}</div>',
        unsafe_allow_html=True,
    )


def format_chicago_citation(passage: Passage) -> str:
    """Format passage metadata as Chicago-style citation.
    
    Format: Author. "Title." Location. File type.
    Example: Jane Austen. "Pride and Prejudice." p. 42. PDF file.
    """
    parts = []
    
    # Author
    if passage.author:
        parts.append(passage.author + ".")
    
    # Title
    if passage.document_title:
        title = f'"{passage.document_title}"'
    else:
        file_path = Path(passage.source_file)
        title = f'"{file_path.stem}"'
    parts.append(title + ".")
    
    # Location
    location_parts = []
    if passage.page_number:
        location_parts.append(f"p. {passage.page_number}")
    elif passage.line_number:
        location_parts.append(f"line {passage.line_number}")
    if passage.chapter:
        location_parts.append(f"ch. {passage.chapter}")
    if passage.section:
        location_parts.append(f"sec. {passage.section}")
    
    if location_parts:
        parts.append(" ".join(location_parts) + ".")
    
    # File type
    parts.append(f"{passage.file_type.upper()} file.")
    
    return " ".join(parts)


def display_help() -> None:
    """Display help information."""
    st.markdown("## Help - Passage Explorer")
    st.markdown("---")

    help_text = """
    **How It Works:**
    - Click **"New Passage"** to add passages to your feed (up to 100 passages)
    - Each passage in the feed has its own action buttons
    - Passages accumulate in the feed as you click "New Passage"
    
    **Actions:**
    - **New Passage**: Add a new unique passage to the feed (not shown in last 30 days)
    - **Horizontal**: Expand horizontally (show 2 related passages) for a specific passage
    - **Context**: Expand context (~400 words around passage) for a specific passage
    - **Save**: Save a specific passage to CSV collection
    - **Clear Feed**: Remove all passages from the feed
    - **Index**: Index next batch of files (if any pending)
    - **Help**: Show this help screen

    **About:**
    Passage Explorer helps you discover and explore meaningful passages
    from your document library. Each session shows you new passages that
    haven't been displayed in the last 30 days. Passages accumulate in a feed
    so you can explore multiple passages at once.

    **Library:**
    This demo uses the Library SOP collection.
    """
    st.markdown(help_text)


# ---------- Main App ----------


def main() -> None:
    """Main Streamlit app."""
    st.set_page_config(
        page_title="Passage Explorer",
        page_icon=None,
        layout="centered",
    )

    # Apply terminal-style CSS
    st.markdown("""
    <style>
    /* Terminal-style font */
    html, body, [class*="css"] {
        font-family: 'Courier New', 'Monaco', 'Menlo', 'Consolas', 'Liberation Mono', monospace !important;
    }
    
    /* Main content area - dark terminal theme */
    .main .block-container {
        background-color: #1e1e1e;
        color: #d4d4d4;
        padding: 2rem;
        max-width: 1200px;
    }
    
    /* Passage text boxes - terminal style */
    .passage-box {
        background-color: #252526;
        border: 1px solid #3e3e42;
        color: #d4d4d4;
        font-family: 'Courier New', monospace;
        white-space: pre-wrap;
        word-wrap: break-word;
    }
    
    /* Metadata text - smaller, italic */
    .metadata-text {
        font-size: 0.85em;
        font-style: italic;
        color: #858585;
        line-height: 1.4;
        font-family: 'Courier New', monospace;
    }
    
    /* Buttons - terminal style with green */
    .stButton > button {
        background-color: #2d5016;
        color: #ffffff;
        border: 1px solid #3d6b1f;
        font-family: 'Courier New', monospace;
        font-size: 0.9em;
    }
    
    .stButton > button:hover {
        background-color: #3d6b1f;
        border-color: #4d8b2f;
    }
    
    /* Primary button (New Passage) - neon green with black bold text */
    .stButton > button[kind="primary"] {
        background-color: #39ff14;
        color: #000000;
        border: 2px solid #39ff14;
        font-weight: bold;
        font-size: 1em;
    }
    
    .stButton > button[kind="primary"]:hover {
        background-color: #4aff2e;
        border-color: #4aff2e;
    }
    
    /* Smaller, calmer buttons for passage actions */
    .stButton > button[key*="h_"],
    .stButton > button[key*="c_"],
    .stButton > button[key*="s_"],
    .stButton > button[key*="copy_"] {
        background-color: #1e3d0f;
        color: #a0d080;
        border: 1px solid #2d5016;
        font-size: 0.85em;
        padding: 0.25rem 0.5rem;
    }
    
    .stButton > button[key*="h_"]:hover,
    .stButton > button[key*="c_"]:hover,
    .stButton > button[key*="s_"]:hover,
    .stButton > button[key*="copy_"]:hover {
        background-color: #2d5016;
        border-color: #3d6b1f;
    }
    
    /* Headers - terminal green */
    h1, h2, h3 {
        color: #4ec9b0;
        font-family: 'Courier New', monospace;
    }
    
    /* Regular text */
    p, div, span {
        font-family: 'Courier New', monospace;
    }
    
    /* Streamlit default text color override */
    .stMarkdown, .stText {
        color: #d4d4d4;
    }
    
    /* Code blocks */
    code {
        background-color: #252526;
        color: #d4d4d4;
        border: 1px solid #3e3e42;
    }
    </style>
    """, unsafe_allow_html=True)

    # Initialize session state
    if "view_mode" not in st.session_state:
        st.session_state.view_mode = "main"  # 'main' | 'horizontal' | 'context' | 'help' | 'confirm_index'
    if "passage_feed" not in st.session_state:
        st.session_state.passage_feed = []  # List of Passage objects (max 100)
    if "passage_timestamps" not in st.session_state:
        st.session_state.passage_timestamps = {}  # Dict mapping passage.id -> timestamp when added
    if "selected_passage_id" not in st.session_state:
        st.session_state.selected_passage_id = None  # ID of passage for actions
    if "related_passages" not in st.session_state:
        st.session_state.related_passages = []
    if "context_text" not in st.session_state:
        st.session_state.context_text = None
    if "indexing_status" not in st.session_state:
        st.session_state.indexing_status = None

    # Initialize lightweight components first
    store = get_passage_store()
    config = get_config()
    library_path = config.library_path
    
    # Clear database when switching to Library SOP (one-time)
    if "database_cleared_for_library_sop" not in st.session_state:
        if str(library_path).endswith("Library SOP"):
            with st.spinner("Clearing database for new library..."):
                clear_results = clear_all_database_data()
                st.session_state.database_cleared_for_library_sop = True
                logger.info(f"Cleared database: {clear_results}")

    # Show header immediately (before any heavy operations)
    header_col1, header_col2 = st.columns([3, 1])
    with header_col1:
        st.title("Passage Explorer")
    with header_col2:
        # This is a lightweight check, safe to do immediately
        try:
            pending_files = store.get_pending_files()
            if pending_files:
                st.caption(f"Indexing: {len(pending_files)} files pending")
            else:
                st.caption("All files indexed")
        except Exception:
            st.caption("Initializing...")
        # Passage feed tracker (passive, smaller font)
        if "passage_feed" in st.session_state:
            feed_count = len(st.session_state.passage_feed)
            st.caption(f"Passage Feed ({feed_count}/100)")

    # Check if we have passages (lightweight check)
    try:
        has_passages = store.has_any_passages()
    except Exception as exc:
        st.error(
            "Could not open the passages database. "
            "Make sure you've run the terminal app at least once to index "
            "the sample library."
        )
        st.caption(f"Internal error: {exc}")
        return

    # Discover and register new files, start background indexing (deferred with spinner)
    if not st.session_state.get("indexing_initialized", False):
        with st.spinner("Initializing indexing..."):
            # Discover files
            supported_extensions = {".txt", ".html", ".htm", ".md", ".markdown", ".pdf"}
            files = []
            for ext in supported_extensions:
                files.extend(library_path.rglob(f"*{ext}"))

            for file_path in files:
                abs_path = str(file_path.resolve())
                status = store.get_indexing_status(abs_path)
                if not status:
                    store.set_indexing_status(abs_path, "pending")

            # Start background indexing if needed
            if has_passages:
                start_background_indexing(library_path)
            else:
                # Do minimal indexing first
                if files:
                    min_indexing = config.get("min_first_run_indexing", 2)
                    files_to_index = [Path(f) for f in files[:min_indexing]]
                    # Index synchronously for first batch
                    processor = get_document_processor()
                    extractor = get_passage_extractor()
                    # DON'T load similarity engine here - it's heavy and blocks UI
                    # Embeddings can be computed later when needed for horizontal expansion
                    # similarity = get_similarity_engine()  # Removed

                    for file_path in files_to_index:
                        abs_path = str(file_path.resolve())
                        try:
                            store.set_indexing_status(abs_path, "indexing")
                            doc_data = processor.process(file_path)
                            if doc_data:
                                passages = extractor.extract_passages(doc_data, file_path)
                                for passage_data in passages:
                                    # Skip embeddings during initial indexing for speed
                                    # They can be computed on-demand when needed
                                    # if similarity.enabled:
                                    #     emb = similarity.embed_text(passage_data["text"])
                                    #     if emb is not None:
                                    #         passage_data["embedding"] = json.dumps(emb)
                                    store.add_passage(passage_data)
                                store.set_indexing_status(abs_path, "completed")
                        except Exception as e:
                            logger.error(f"Error indexing {file_path}: {e}")
                            store.set_indexing_status(abs_path, "failed", str(e))

                    # Refresh has_passages
                    has_passages = store.has_any_passages()
                    if has_passages:
                        start_background_indexing(library_path)

        st.session_state.indexing_initialized = True
        # Refresh to show updated status
        if has_passages:
            st.rerun()

    if not has_passages:
        st.warning(
            "No passages found in the demo database.\n\n"
            "From the terminal, run something like:\n\n"
            "    python -m src.main --library ./Library-Sample\n\n"
            "to index the sample library, then refresh this page."
        )
        return

    # Initialize feed with first passage if empty (with loading state)
    if len(st.session_state.passage_feed) == 0 and st.session_state.view_mode == "main":
        with st.spinner("Loading first passage..."):
            passage = store.get_random_passage(
                exclude_days=config.get("session_history_days", 30)
            )
            if not passage:
                if not store.has_any_passages():
                    st.error(
                        "No passages available in database. "
                        "Please index some files first."
                    )
                    return
                else:
                    st.warning(
                        "No new passages available (all shown in last 30 days).\n\n"
                        "Options:\n"
                        "- Wait for background indexing to complete\n"
                        "- Press 'Index' to manually trigger next batch"
                    )
                    return
            st.session_state.passage_feed = [passage]
            st.session_state.passage_timestamps[passage.id] = datetime.now(timezone.utc)
            store.log_usage_event("new", passage_id=passage.id)

    # Display based on view mode
    if st.session_state.view_mode == "help":
        display_help()
        if st.button("Back to Main", use_container_width=True):
            st.session_state.view_mode = "main"
            st.rerun()

    elif st.session_state.view_mode == "horizontal":
        # Find the selected passage from feed
        selected_passage = None
        if st.session_state.selected_passage_id:
            for p in st.session_state.passage_feed:
                if p.id == st.session_state.selected_passage_id:
                    selected_passage = p
                    break
        
        if selected_passage and st.session_state.related_passages:
            display_horizontal_view(selected_passage, st.session_state.related_passages)

    elif st.session_state.view_mode == "context":
        # Find the selected passage from feed
        selected_passage = None
        if st.session_state.selected_passage_id:
            for p in st.session_state.passage_feed:
                if p.id == st.session_state.selected_passage_id:
                    selected_passage = p
                    break
        
        if selected_passage and st.session_state.context_text:
            display_context_view(selected_passage, st.session_state.context_text)

    elif st.session_state.view_mode == "confirm_index":
        st.markdown("## Index Next Batch")
        st.markdown("---")
        
        total_indexed = store.get_indexed_file_count()
        pending = store.get_pending_files()
        pending_count = len(pending)
        
        if pending_count == 0:
            st.info("No files pending indexing.")
            if st.button("Back", use_container_width=True):
                st.session_state.view_mode = "main"
                st.rerun()
        else:
            st.info(f"Files indexed so far: **{total_indexed}**. Pending: **{pending_count}**.")
            st.markdown("Do you want to index the next batch now?")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Yes, Index Now", use_container_width=True, type="primary"):
                    success, message = manual_index_next_batch(library_path)
                    if success:
                        st.success(message)
                    else:
                        st.info(message)
                    st.session_state.view_mode = "main"
                    st.rerun()
            with col2:
                if st.button("Cancel", use_container_width=True):
                    st.session_state.view_mode = "main"
                    st.rerun()

    else:  # main view - feed display
        # Main menu: New Passage (prominent), Clear Feed, Index, Help (calm)
        menu_col1, menu_col2, menu_col3, menu_col4 = st.columns([2, 1, 1, 1])
        with menu_col1:
            if st.button("New Passage", use_container_width=True, type="primary"):
                # Get a new passage
                passage = store.get_random_passage(
                    exclude_days=config.get("session_history_days", 30)
                )
                if passage:
                    # Add to feed (prepend to show newest first)
                    st.session_state.passage_feed.insert(0, passage)
                    # Track timestamp when passage was added
                    st.session_state.passage_timestamps[passage.id] = datetime.now(timezone.utc)
                    # Limit to 100 passages
                    if len(st.session_state.passage_feed) > 100:
                        # Remove oldest passage and its timestamp
                        oldest = st.session_state.passage_feed.pop()
                        if oldest.id in st.session_state.passage_timestamps:
                            del st.session_state.passage_timestamps[oldest.id]
                    store.log_usage_event("new", passage_id=passage.id)
                    st.rerun()
                else:
                    st.warning("No new passages available (all shown in last 30 days).")
        with menu_col2:
            if st.button("Clear Feed", use_container_width=True):
                st.session_state.passage_feed = []
                st.session_state.passage_timestamps = {}
                st.rerun()
        with menu_col3:
            if st.button("Index", use_container_width=True):
                st.session_state.view_mode = "confirm_index"
                st.rerun()
        with menu_col4:
            if st.button("Help", use_container_width=True):
                st.session_state.view_mode = "help"
                st.rerun()
        
        st.markdown("---")

        # Display feed
        if len(st.session_state.passage_feed) == 0:
            st.info("Feed is empty. Click 'New Passage' to add passages.")
        else:
            st.markdown("---")
            for passage in st.session_state.passage_feed:
                with st.container():
                    # Timestamp header
                    timestamp = st.session_state.passage_timestamps.get(passage.id)
                    if timestamp:
                        # Format timestamp in local time
                        local_time = timestamp.astimezone()
                        time_str = local_time.strftime("%Y-%m-%d %H:%M:%S")
                        st.markdown(f'<div style="color: #858585; font-size: 0.85em; margin-bottom: 0.5em;">{time_str}</div>', unsafe_allow_html=True)
                    
                    # Display passage text (formatted for better presentation)
                    formatted_text = format_passage_text(passage.text)
                    passage_text_escaped = formatted_text.replace('"', '&quot;').replace("'", "&#39;")
                    st.markdown(
                        f'<div class="passage-box" style="font-size: 1.05em; line-height: 1.6; padding: 1em; background-color: #252526; border: 1px solid #3e3e42; border-radius: 5px; margin-bottom: 0.5em; color: #d4d4d4; font-family: \'Courier New\', monospace;">{passage_text_escaped}</div>',
                        unsafe_allow_html=True,
                    )
                    
                    # Location info (moved below passage)
                    location_parts = []
                    if passage.page_number:
                        location_parts.append(f"Page {passage.page_number}")
                    elif passage.line_number:
                        location_parts.append(f"Line {passage.line_number}")
                    if passage.chapter:
                        location_parts.append(f"Chapter {passage.chapter}")
                    if passage.section:
                        location_parts.append(f"Section {passage.section}")
                    
                    if location_parts:
                        location_str = " / ".join(location_parts)
                        st.markdown(f'<div style="color: #858585; font-size: 0.9em; margin-bottom: 0.5em; font-style: italic;">{location_str}</div>', unsafe_allow_html=True)
                    
                    # Metadata as Chicago citation
                    citation = format_chicago_citation(passage)
                    st.markdown(
                        f'<div class="metadata-text">{citation}</div>',
                        unsafe_allow_html=True,
                    )
                    
                    # Action buttons for this passage (smaller, less intense)
                    action_col1, action_col2, action_col3, action_col4 = st.columns(4)
                    with action_col1:
                        if st.button("Copy", key=f"copy_{passage.id}", use_container_width=True):
                            # Display in code block for easy selection (use formatted text)
                            copy_text = f"{formatted_text}\n\n{citation}"
                            st.code(copy_text, language=None)
                            st.info("Select the text above and copy (Cmd/Ctrl+C)")
                    with action_col2:
                        if st.button("Horizontal", key=f"h_{passage.id}", use_container_width=True):
                            related = get_related_passages(passage, top_k=2)
                            if not related:
                                st.warning("No related passages found.")
                            else:
                                st.session_state.selected_passage_id = passage.id
                                st.session_state.related_passages = related
                                st.session_state.view_mode = "horizontal"
                                store.log_usage_event("horizontal", passage_id=passage.id)
                                st.rerun()
                    with action_col3:
                        if st.button("Context", key=f"c_{passage.id}", use_container_width=True):
                            context = get_context_for_passage(passage)
                            st.session_state.selected_passage_id = passage.id
                            st.session_state.context_text = context
                            st.session_state.view_mode = "context"
                            store.log_usage_event("context", passage_id=passage.id)
                            st.rerun()
                    with action_col4:
                        if st.button("Save", key=f"s_{passage.id}", use_container_width=True):
                            store.save_passage(passage.id)
                            save_passage_to_csv(passage)
                            st.success("Passage saved!")
                            store.log_usage_event("save", passage_id=passage.id)
                    
                    st.markdown("---")

    # Footer
    st.markdown("---")
    st.caption(
        "This web demo uses the same passages database as the terminal Passage Explorer app."
    )


if __name__ == "__main__":
    main()
