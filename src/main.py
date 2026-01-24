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
        
        # Filter to only pending files
        pending_files = []
        for file_path in files:
            abs_path = str(file_path.resolve())
            status = self.store.get_indexing_status(abs_path)
            if not status or status.status != 'completed':
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
            abs_path = str(file_path.resolve())
            
            try:
                self.ui.show_indexing_progress(i, total, file_path.name)
                
                # Mark as indexing
                self.store.set_indexing_status(abs_path, 'indexing')
                
                # Process file
                doc_data = self.processor.process(file_path)
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

    # -------- Stage 2 helpers --------

    def get_related_passages(self, passage: Passage, top_k: int = 2) -> list[Passage]:
        """Get related passages using semantic similarity (with fallback)."""
        return self.similarity.find_related_passages(self.store, passage, top_k=top_k)

    def get_context_for_passage(self, passage: Passage) -> str:
        """Get ~400-word context around a passage."""
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
                # Get a small set of pending files
                pending = self.store.get_pending_files(
                    limit=self.config.get("progressive_indexing_batch_size", 4)
                )
                if not pending:
                    logger.info("Background indexing: no more pending files.")
                    break
                with self._indexing_lock:
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
        
        # Initial indexing (small batch)
        logger.info("Starting initial indexing...")
        with self._indexing_lock:
            self.index_files(
                library_path,
                batch_size=self.config.get("initial_indexing_batch_size", 8),
            )

        # Start background progressive indexing
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
                        self.ui.show_message(
                            "No passages available. Try resetting session history with --reset-sessions",
                            'warning'
                        )
                        break
                    current_passage = passage
                else:
                    passage = current_passage

                # Display passage
                self.ui.clear()
                self.ui.display_passage(passage, self.store)
                
                # Get user action
                action = self.ui.get_user_input()
                
                if action == 'q':
                    self.ui.show_message("Goodbye!", 'info')
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
    
    # Handle reset sessions
    if args.reset_sessions:
        from .passage_store import SessionHistory
        store = PassageStore()
        session = store.get_session()
        try:
            session.query(SessionHistory).delete()
            session.commit()
            logger.info("Session history cleared")
            print("Session history cleared")
        finally:
            session.close()
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
