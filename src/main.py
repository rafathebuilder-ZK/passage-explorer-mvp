"""Main entry point for Passage Explorer."""
import sys
import logging
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .cli import CLI
from .config import Config
from .logger import setup_logging
from .passage_store import PassageStore, Passage
from .document_processor import DocumentProcessor
from .passage_extractor import PassageExtractor
from .ui import PassageUI
from .similarity import SimilarityEngine

logger = logging.getLogger(__name__)


class PassageExplorer:
    """Main application class."""
    
    def __init__(self, config: Config):
        """Initialize application.
        
        Args:
            config: Configuration object.
        """
        self.config = config
        self.store = PassageStore()
        self.processor = DocumentProcessor()
        self.extractor = PassageExtractor(
            min_length=100,
            max_length=config.get('max_passage_length', 420)
        )
        self.ui = PassageUI()
        self.similarity = SimilarityEngine(config)
        # Background indexing
        import threading
        self._indexing_lock = threading.Lock()
        self._indexing_thread_started = False
        self._cancel_indexing_event = threading.Event()  # For cooperative cancellation
    
    def _has_supported_files(self, library_path: Path) -> tuple[bool, int]:
        """Check if library has any supported files.
        
        Args:
            library_path: Path to library directory.
            
        Returns:
            Tuple of (has_files, total_count) where has_files is True if any supported
            files exist, and total_count is the total number of supported files found.
        """
        supported_extensions = {
            '.txt',
            '.html',
            '.htm',
            '.md',
            '.markdown',
            '.pdf',
        }
        files = []
        
        for ext in supported_extensions:
            files.extend(library_path.rglob(f'*{ext}'))
        
        return (len(files) > 0, len(files))
    
    def _discover_and_register_files(self, library_path: Path) -> int:
        """Discover all supported files and register them as pending if not already registered.
        
        Args:
            library_path: Path to library directory.
            
        Returns:
            Number of newly registered files.
        """
        supported_extensions = {
            '.txt',
            '.html',
            '.htm',
            '.md',
            '.markdown',
            '.pdf',
        }
        files = []
        
        for ext in supported_extensions:
            files.extend(library_path.rglob(f'*{ext}'))
        
        newly_registered = 0
        for file_path in files:
            abs_path = str(file_path.resolve())
            status = self.store.get_indexing_status(abs_path)
            if not status:
                # File not yet registered - register as pending
                self.store.set_indexing_status(abs_path, 'pending')
                newly_registered += 1
        
        if newly_registered > 0:
            logger.info(f"Discovered and registered {newly_registered} new file(s) as pending")
        
        return newly_registered
    
    def index_files(self, library_path: Path, batch_size: Optional[int] = None):
        """Index files from library directory.
        
        Args:
            library_path: Path to library directory.
            batch_size: Maximum number of files to index. If None, uses config default.
        """
        # Find all supported files
        supported_extensions = {
            '.txt',
            '.html',
            '.htm',
            '.md',
            '.markdown',
            '.pdf',  # Stage 4: PDF support
        }
        files = []
        
        for ext in supported_extensions:
            files.extend(library_path.rglob(f'*{ext}'))
        
        if not files:
            logger.warning(f"No supported files found in {library_path}")
            return
        
        # Filter to only pending files and register them in database
        pending_files = []
        for file_path in files:
            abs_path = str(file_path.resolve())
            status = self.store.get_indexing_status(abs_path)
            if not status:
                # File not yet registered - register as pending
                self.store.set_indexing_status(abs_path, 'pending')
                pending_files.append(file_path)
            elif status.status != 'completed':
                # File is pending, indexing, or failed - include it
                pending_files.append(file_path)
        
        if not pending_files:
            logger.info("All files already indexed")
            return
        
        # Limit batch size
        if batch_size is None:
            batch_size = self.config.get('initial_indexing_batch_size', 8)
        
        files_to_index = pending_files[:batch_size]
        total = len(files_to_index)
        
        logger.info(f"Indexing {total} file(s)...")
        
        for i, file_path in enumerate(files_to_index, 1):
            # Check for cancellation before processing each file
            if self._cancel_indexing_event.is_set():
                logger.info("Indexing cancelled by user")
                # Mark current file as pending if it was marked as indexing
                abs_path = str(file_path.resolve())
                status = self.store.get_indexing_status(abs_path)
                if status and status.status == 'indexing':
                    self.store.set_indexing_status(abs_path, 'pending')
                break
            
            abs_path = str(file_path.resolve())
            
            try:
                self.ui.show_indexing_progress(i, total, file_path.name)
                
                # Mark as indexing
                self.store.set_indexing_status(abs_path, 'indexing')
                
                # Process file - apply 5-minute timeout for PDF files
                is_pdf = file_path.suffix.lower() == '.pdf'
                timeout_seconds = 300.0 if is_pdf else None  # 5 minutes = 300 seconds
                
                try:
                    doc_data = self.processor.process(file_path, timeout_seconds=timeout_seconds, cancellation_event=self._cancel_indexing_event)
                except TimeoutError as e:
                    # PDF indexing exceeded timeout - mark as failed and continue
                    error_msg = f"PDF indexing timeout after 5 minutes: {e}"
                    logger.warning(error_msg)
                    self.store.set_indexing_status(abs_path, 'failed', error_msg)
                    continue
                
                if not doc_data:
                    self.store.set_indexing_status(abs_path, 'failed', 'Unsupported format or processing error')
                    continue
                
                # Extract passages
                passages = self.extractor.extract_passages(doc_data, file_path)
                
                # Store passages (with embeddings where available)
                for passage_data in passages:
                    if self.similarity.enabled:
                        emb = self.similarity.embed_text(passage_data['text'])
                        if emb is not None:
                            passage_data['embedding'] = json.dumps(emb)
                    self.store.add_passage(passage_data)
                
                # Mark as completed
                self.store.set_indexing_status(abs_path, 'completed')
                logger.info(f"Indexed {file_path.name}: {len(passages)} passages")
                
            except Exception as e:
                logger.error(f"Error indexing {file_path}: {e}")
                self.store.set_indexing_status(abs_path, 'failed', str(e))
    
    def index_files_until_passage_available(self, library_path: Path, max_files: int = 2):
        """Index files until at least one passage is available.
        
        Args:
            library_path: Path to library directory.
            max_files: Maximum number of files to index before giving up.
            
        Returns:
            True if at least one passage was created, False otherwise.
        """
        # Find all supported files
        supported_extensions = {
            '.txt',
            '.html',
            '.htm',
            '.md',
            '.markdown',
            '.pdf',
        }
        files = []
        
        for ext in supported_extensions:
            files.extend(library_path.rglob(f'*{ext}'))
        
        if not files:
            logger.warning(f"No supported files found in {library_path}")
            return False
        
        # Filter to only pending files and register them in database
        pending_files = []
        for file_path in files:
            abs_path = str(file_path.resolve())
            status = self.store.get_indexing_status(abs_path)
            if not status:
                # File not yet registered - register as pending
                self.store.set_indexing_status(abs_path, 'pending')
                pending_files.append(file_path)
            elif status.status != 'completed':
                # File is pending, indexing, or failed - include it
                pending_files.append(file_path)
        
        if not pending_files:
            logger.info("All files already indexed")
            # Check if we have passages
            return self.store.has_any_passages()
        
        # Limit to max_files
        files_to_index = pending_files[:max_files]
        
        logger.info(f"Indexing up to {len(files_to_index)} file(s) to get first passage...")
        
        for i, file_path in enumerate(files_to_index, 1):
            abs_path = str(file_path.resolve())
            
            try:
                self.ui.show_indexing_progress(i, len(files_to_index), file_path.name)
                
                # Mark as indexing
                self.store.set_indexing_status(abs_path, 'indexing')
                
                # Process file - apply 5-minute timeout for PDF files
                is_pdf = file_path.suffix.lower() == '.pdf'
                timeout_seconds = 300.0 if is_pdf else None  # 5 minutes = 300 seconds
                
                try:
                    doc_data = self.processor.process(file_path, timeout_seconds=timeout_seconds, cancellation_event=self._cancel_indexing_event)
                except TimeoutError as e:
                    # PDF indexing exceeded timeout - mark as failed and continue
                    error_msg = f"PDF indexing timeout after 5 minutes: {e}"
                    logger.warning(error_msg)
                    self.store.set_indexing_status(abs_path, 'failed', error_msg)
                    continue
                
                if not doc_data:
                    self.store.set_indexing_status(abs_path, 'failed', 'Unsupported format or processing error')
                    continue
                
                # Extract passages
                passages = self.extractor.extract_passages(doc_data, file_path)
                
                # Store passages (with embeddings where available)
                for passage_data in passages:
                    if self.similarity.enabled:
                        emb = self.similarity.embed_text(passage_data['text'])
                        if emb is not None:
                            passage_data['embedding'] = json.dumps(emb)
                    self.store.add_passage(passage_data)
                
                # Mark as completed
                self.store.set_indexing_status(abs_path, 'completed')
                logger.info(f"Indexed {file_path.name}: {len(passages)} passages")
                
                # Check if we now have at least one passage
                if self.store.has_any_passages():
                    logger.info("Passage available, stopping minimal indexing")
                    return True
                
            except Exception as e:
                logger.error(f"Error indexing {file_path}: {e}")
                self.store.set_indexing_status(abs_path, 'failed', str(e))
        
        # Check if we have passages after all attempts
        return self.store.has_any_passages()

    # -------- Stage 2 helpers --------

    def get_related_passages(self, passage: Passage, top_k: int = 2) -> list[Passage]:
        """Get related passages using semantic similarity (with fallback)."""
        return self.similarity.find_related_passages(self.store, passage, top_k=top_k)

    def get_context_for_passage(self, passage: Passage) -> str:
        """Get ~400-word context around a passage."""
        # Use PDF-specific extraction for PDF files
        if passage.file_type == 'pdf':
            return self._get_pdf_context_for_passage(passage)
        
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
    
    def _get_pdf_context_for_passage(self, passage: Passage) -> str:
        """Get context for a PDF passage using pdfplumber.
        
        Args:
            passage: Passage object with PDF file information.
            
        Returns:
            Context text around the passage (~400 words).
        """
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
                    logger.warning(f"Invalid page number {page_num} for passage, trying all pages")
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
                    logger.warning(f"Passage text not found in page {page_num}, returning full page")
                    return page_text.strip()
                
                # Extract context around the passage (~400 words = ~2000 chars)
                # Aim for ~400 words, which is roughly 2000 characters
                context_size = 2000
                start = max(0, passage_pos - context_size)
                end = min(len(page_text), passage_pos + len(passage.text) + context_size)
                context = page_text[start:end]
                
                # Clean up whitespace - normalize multiple spaces/newlines
                import re
                context = re.sub(r'\n{3,}', '\n\n', context)  # Max 2 newlines
                context = re.sub(r' {2,}', ' ', context)  # Max 1 space
                
                return context.strip()
                
        except Exception as e:
            logger.error(f"Error extracting PDF context: {e}", exc_info=True)
            return passage.text

    def save_passage_to_csv(self, passage: Passage) -> None:
        """Append passage metadata to CSV export."""
        project_root = Path(__file__).parent.parent
        data_dir = project_root / "data"
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

    def manual_index_next_batch(self, library_path: Path) -> None:
        """Manually trigger indexing of the next batch of files."""
        # Avoid running if background indexing is actively holding the lock
        if self._indexing_lock.locked():
            self.ui.show_message("Indexing already in progress.", "info")
            return

        # Check if there are any pending files
        pending = self.store.get_pending_files(
            limit=self.config.get("progressive_indexing_batch_size", 4)
        )
        if not pending:
            self.ui.show_message("No files pending indexing.", "info")
            return

        self.ui.show_message("Indexing next batch of files...", "info")
        logger.info("User requested manual indexing of next batch.")
        with self._indexing_lock:
            self.index_files(
                library_path,
                batch_size=self.config.get("progressive_indexing_batch_size", 4),
            )
        # Log usage event
        self.store.log_usage_event("index_batch")
        total_indexed = self.store.get_indexed_file_count()
        self.ui.show_message(
            f"Indexing batch complete. Files indexed so far: {total_indexed}.",
            "success",
        )

    # -------- Stage 5: background progressive indexing --------

    def start_background_indexing(self, library_path: Path) -> None:
        """Start background indexing thread if not already started."""
        if self._indexing_thread_started:
            return

        import threading

        def worker():
            logger.info("Background indexing thread started.")
            while True:
                # Check for cancellation
                if self._cancel_indexing_event.is_set():
                    logger.info("Background indexing cancelled by user")
                    break
                
                # Get a small set of pending files
                pending = self.store.get_pending_files(
                    limit=self.config.get("progressive_indexing_batch_size", 4)
                )
                if not pending:
                    logger.info("Background indexing: no more pending files.")
                    break
                
                # Check for cancellation again before acquiring lock
                if self._cancel_indexing_event.is_set():
                    logger.info("Background indexing cancelled by user")
                    break
                
                with self._indexing_lock:
                    # Check once more after acquiring lock
                    if self._cancel_indexing_event.is_set():
                        logger.info("Background indexing cancelled by user")
                        break
                    self.index_files(
                        library_path,
                        batch_size=self.config.get("progressive_indexing_batch_size", 4),
                    )
            logger.info("Background indexing thread finished.")

        t = threading.Thread(target=worker, daemon=True)
        t.start()
        self._indexing_thread_started = True

    def run(self):
        """Run the main application loop."""
        # Validate library path
        is_valid, error_msg = self.config.validate_library_path()
        if not is_valid:
            self.ui.show_message(f"Error: {error_msg}", 'error')
            logger.error(error_msg)
            sys.exit(2)
        
        library_path = self.config.library_path
        
        # Fast startup: Check if passages already exist
        fast_startup = self.config.get('fast_startup', True)
        has_passages = self.store.has_any_passages()
        
        if fast_startup and has_passages:
            # Passages exist - skip blocking indexing, show passage immediately
            logger.info("Passages found in database, skipping initial indexing")
            # Discover and register any new files before starting background indexing
            self._discover_and_register_files(library_path)
            # Start background indexing in parallel
            self.start_background_indexing(library_path)
        else:
            # No passages - do minimal blocking index
            logger.info("No passages found, running minimal initial indexing...")
            
            # Check if library has any supported files
            has_files, file_count = self._has_supported_files(library_path)
            if not has_files:
                self.ui.show_message(
                    f"Error: No supported files found in library: {library_path}\n"
                    "Supported formats: .txt, .html, .md, .pdf",
                    'error'
                )
                logger.error(f"No supported files in library: {library_path}")
                sys.exit(2)
            
            # Index just enough to get at least one passage
            min_indexing = self.config.get('min_first_run_indexing', 2)
            with self._indexing_lock:
                success = self.index_files_until_passage_available(library_path, max_files=min_indexing)
            
            if not success:
                # No passages after minimal indexing - show helpful error
                self.ui.show_message(
                    f"Error: No passages could be extracted from the first {min_indexing} file(s).\n"
                    "Possible causes:\n"
                    "  - Files are empty or corrupted\n"
                    "  - Files contain no extractable text\n"
                    "  - Permission errors\n"
                    "Check the logs for details. Background indexing will continue.",
                    'error'
                )
                logger.error("No passages extracted after minimal indexing")
                # Continue anyway - background indexing might succeed
            
            # Start background indexing for remaining files
            self.start_background_indexing(library_path)
        
        # Main loop
        current_passage: Optional[Passage] = None
        while self.ui.running:
            try:
                # Get or reuse current passage
                if current_passage is None:
                    passage = self.store.get_random_passage(
                        exclude_days=self.config.get('session_history_days', 30)
                    )
                    if not passage:
                        # Check if we have any passages at all
                        if not self.store.has_any_passages():
                            self.ui.show_message(
                                "Error: No passages available in database.\n"
                                "Possible causes:\n"
                                "  - Library is empty or contains no supported files\n"
                                "  - All files failed to index\n"
                                "  - No passages could be extracted from files\n"
                                "Check the logs for details. Background indexing may still be in progress.",
                                'error'
                            )
                        else:
                            # Passages exist but all shown in last 30 days
                            self.ui.show_message(
                                "No new passages available (all shown in last 30 days).\n"
                                "Options:\n"
                                "  - Wait for background indexing to complete\n"
                                "  - Reset session history: --reset-sessions\n"
                                "  - Press 'i' to manually trigger next batch",
                                'warning'
                            )
                        break
                    current_passage = passage
                else:
                    passage = current_passage

                # Display passage with indexing status
                self.ui.clear()
                # Check if background indexing is running
                pending_files = self.store.get_pending_files()
                indexing_status = {
                    'is_indexing': self._indexing_thread_started and len(pending_files) > 0,
                    'pending_count': len(pending_files)
                }
                self.ui.display_passage(passage, self.store, indexing_status=indexing_status)
                
                # Get user action
                action = self.ui.get_user_input()
                
                if action == 'q':
                    self.ui.show_message("Goodbye!", 'info')
                    # Signal cancellation for background indexing
                    self._cancel_indexing_event.set()
                    break
                elif action == '?':
                    self.ui.clear()
                    self.ui.show_help()
                    self.ui.console.input("\nPress Enter to continue...")
                elif action == 'n':
                    # New passage - loop will continue
                    self.store.log_usage_event("new", passage_id=passage.id)
                     # Clear current passage so a new one is fetched on next loop
                    current_passage = None
                    continue
                elif action == 'h':
                    related = self.get_related_passages(passage, top_k=2)
                    if not related:
                        self.ui.show_message("No related passages found.", 'warning')
                        self.ui.console.input("\nPress Enter to continue...")
                    else:
                        self.ui.show_horizontal(passage, related)
                        self.ui.console.input("\nPress Enter to return...")
                    self.store.log_usage_event("horizontal", passage_id=passage.id)
                elif action == 'c':
                    context_text = self.get_context_for_passage(passage)
                    self.ui.show_context(passage, context_text)
                    self.ui.console.input("\nPress Enter to return...")
                    self.store.log_usage_event("context", passage_id=passage.id)
                elif action == 's':
                    # Save to DB + CSV
                    self.store.save_passage(passage.id)
                    self.save_passage_to_csv(passage)
                    self.ui.show_message("Passage saved.", 'success')
                    self.store.log_usage_event("save", passage_id=passage.id)
                elif action == 'i':
                    # Show current indexing status, then optionally trigger next batch
                    total_indexed = self.store.get_indexed_file_count()
                    pending = self.store.get_pending_files()
                    pending_count = len(pending)
                    self.ui.show_message(
                        f"Files indexed so far: {total_indexed}. Pending: {pending_count}.",
                        "info",
                    )
                    answer = self.ui.console.input(
                        "\nIndex next batch now? [y/N]: "
                    ).strip().lower()
                    if answer in ("y", "yes"):
                        self.manual_index_next_batch(library_path)
                    else:
                        self.ui.show_message("Indexing skipped.", "info")
                        self.store.log_usage_event(
                            "index_batch_skipped",
                            info={"indexed": total_indexed, "pending": pending_count},
                        )
                else:
                    self.ui.show_message(f"Unknown action: {action}. Press ? for help.", 'warning')
                
            except KeyboardInterrupt:
                self.ui.show_message("\nGoodbye!", 'info')
                # Signal cancellation for background indexing
                self._cancel_indexing_event.set()
                break
            except Exception as e:
                logger.error(f"Error in main loop: {e}", exc_info=True)
                self.ui.show_message(f"Error: {e}", 'error')
                break


def main():
    """Main entry point."""
    cli = CLI()
    args = cli.parse_args()
    
    # Validate arguments
    is_valid, exit_code = cli.validate_args(args)
    if not is_valid:
        sys.exit(exit_code)
    
    # Set up logging
    setup_logging(verbose=args.verbose, quiet=args.quiet)
    logger.info("Starting Passage Explorer")
    
    # Load configuration
    try:
        config = Config(config_path=args.config)
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        sys.exit(1)
    
    # Override library path if specified
    if args.library:
        config.set('library_path', args.library)
        config.set('library_path_absolute', False)
    
    # Handle reset commands with triple confirmation
    def confirm_reset(action_name: str, item_name: str) -> bool:
        """Triple confirmation for destructive operations.
        
        Args:
            action_name: Name of the action (e.g., "reset session history")
            item_name: Name of items being reset (e.g., "sessions")
            
        Returns:
            True if user confirmed three times, False otherwise.
        """
        print(f"\n⚠️  WARNING: You are about to {action_name}.")
        print(f"   This will archive all {item_name} to data/archive/ before deletion.")
        print(f"   This action cannot be undone (except by restoring from archive).\n")
        
        confirmations = [
            f"Type 'YES' to confirm {action_name}: ",
            f"Type 'CONFIRM' to confirm {action_name}: ",
            f"Type 'DELETE' to finalize {action_name}: "
        ]
        
        expected = ['YES', 'CONFIRM', 'DELETE']
        
        for i, (prompt, expected_value) in enumerate(zip(confirmations, expected), 1):
            response = input(prompt).strip()
            if response != expected_value:
                print(f"\n❌ Confirmation {i} failed. Reset cancelled.")
                return False
        
        print(f"\n✅ All confirmations received. Proceeding with {action_name}...\n")
        return True
    
    if args.reset_sessions:
        if not confirm_reset("reset session history", "sessions"):
            sys.exit(0)
        store = PassageStore()
        count = store.reset_sessions(archive=True)
        print(f"✅ Session history reset complete. {count} sessions archived and deleted.")
        logger.info(f"Session history reset: {count} sessions archived and deleted")
        return
    
    if args.reset_indexing:
        if not confirm_reset("reset indexing status", "indexing status records"):
            sys.exit(0)
        store = PassageStore()
        count = store.reset_indexing_status(archive=True)
        print(f"✅ Indexing status reset complete. {count} records archived and deleted.")
        print("   Note: Files will need to be re-indexed.")
        logger.info(f"Indexing status reset: {count} records archived and deleted")
        return
    
    if args.reset_saved:
        if not confirm_reset("reset saved passages", "saved passages"):
            sys.exit(0)
        store = PassageStore()
        count = store.reset_saved_passages(archive=True)
        print(f"✅ Saved passages reset complete. {count} passages archived and deleted.")
        logger.info(f"Saved passages reset: {count} passages archived and deleted")
        return
    
    if args.reset_all:
        if not confirm_reset("reset all application data", "all data (sessions, indexing status, saved passages)"):
            sys.exit(0)
        store = PassageStore()
        results = store.reset_all(archive=True)
        print(f"✅ All data reset complete:")
        print(f"   - {results['sessions']} sessions archived and deleted")
        print(f"   - {results['indexing_status']} indexing status records archived and deleted")
        print(f"   - {results['saved_passages']} saved passages archived and deleted")
        print(f"\n   All archives saved to: data/archive/")
        print(f"   Note: Files will need to be re-indexed.")
        logger.info(f"All data reset: {results}")
        return
    
    # Create and run application
    try:
        app = PassageExplorer(config)
        # Log app start usage event
        app.store.log_usage_event("app_start")
        app.run()
        app.store.log_usage_event("app_exit")
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        try:
            # Signal cancellation for background indexing
            app._cancel_indexing_event.set()
            app.store.log_usage_event("app_interrupt")
        except Exception:
            pass
        sys.exit(4)
    except Exception as e:
        logger.critical(f"Fatal error: {e}", exc_info=True)
        try:
            app.store.log_usage_event("app_crash", info={"error": str(e)})
        except Exception:
            pass
        sys.exit(1)


if __name__ == '__main__':
    main()
