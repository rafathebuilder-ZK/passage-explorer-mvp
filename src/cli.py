"""Command-line interface for Passage Explorer."""
import argparse
import sys
import signal
from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class CLI:
    """Command-line interface handler."""
    
    def __init__(self):
        """Initialize CLI."""
        self.shutdown_requested = False
        self._setup_signal_handlers()
    
    def _setup_signal_handlers(self):
        """Set up signal handlers for graceful shutdown."""
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, shutting down gracefully...")
            self.shutdown_requested = True
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    def parse_args(self) -> argparse.Namespace:
        """Parse command-line arguments.
        
        Returns:
            Parsed arguments namespace.
        """
        parser = argparse.ArgumentParser(
            description='Multi-Format Passage Explorer - Discover and explore meaningful passages from your document library.',
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Examples:
  %(prog)s                    # Launch interactive mode
  %(prog)s --help             # Show help message
  %(prog)s --version          # Show version information
  %(prog)s --library ./docs   # Override library path
  %(prog)s --verbose          # Enable debug logging
            """
        )
        
        parser.add_argument(
            '--version', '-v',
            action='version',
            version='%(prog)s 0.1.0'
        )
        
        parser.add_argument(
            '--config', '-c',
            type=str,
            help='Path to configuration file (default: ./config.yaml)'
        )
        
        parser.add_argument(
            '--library', '-l',
            type=str,
            help='Override library path from config (temporary, does not save)'
        )
        
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Enable debug-level logging'
        )
        
        parser.add_argument(
            '--quiet', '-q',
            action='store_true',
            help='Suppress non-essential output (errors only)'
        )
        
        parser.add_argument(
            '--reset-sessions',
            action='store_true',
            help='Clear session history (useful for testing)'
        )
        
        return parser.parse_args()
    
    def validate_args(self, args: argparse.Namespace) -> tuple[bool, Optional[int]]:
        """Validate command-line arguments.
        
        Args:
            args: Parsed arguments.
            
        Returns:
            (is_valid, exit_code)
        """
        if args.quiet and args.verbose:
            print("Error: Cannot use --quiet and --verbose together", file=sys.stderr)
            return False, 1
        
        return True, 0
