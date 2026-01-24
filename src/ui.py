"""Terminal UI for Passage Explorer."""
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.layout import Layout
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class PassageUI:
    """Terminal UI for displaying passages and handling user input."""
    
    def __init__(self):
        """Initialize UI."""
        self.console = Console()
        self.running = True
    
    def display_passage(self, passage, store):
        """Display a passage with metadata and actions.
        
        Args:
            passage: Passage object from database.
            store: PassageStore instance.
        """
        # Record that this passage was shown
        store.record_session_passage(passage.id)
        
        # Build metadata text
        metadata_lines = []
        
        if passage.document_title:
            metadata_lines.append(f"Source: {passage.document_title}")
        
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
            metadata_lines.append(f"Location: {' / '.join(location_parts)}")
        
        # File info
        file_path = Path(passage.source_file)
        metadata_lines.append(f"File: {file_path.name}")
        metadata_lines.append(f"Type: {passage.file_type.upper()}")
        
        if passage.author:
            metadata_lines.append(f"Author: {passage.author}")
        
        # Create layout
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="passage", ratio=2),
            Layout(name="metadata", ratio=1),
            Layout(name="actions", size=4)
        )
        
        # Header
        layout["header"].update(Panel(
            "[bold cyan]Passage Explorer[/bold cyan]",
            border_style="cyan"
        ))
        
        # Passage text
        passage_text = Text(passage.text)
        layout["passage"].update(Panel(
            passage_text,
            title="[bold]Passage[/bold]",
            border_style="blue"
        ))
        
        # Metadata
        metadata_text = "\n".join(metadata_lines)
        layout["metadata"].update(Panel(
            metadata_text,
            title="[bold]Metadata[/bold]",
            border_style="green"
        ))
        
        # Actions - format as compact list
        # Use Text to properly handle the square brackets
        actions_display = Text()
        actions_display.append("Actions: ", style="bold")
        actions_display.append("[n]", style="bold yellow")
        actions_display.append("ew  ", style="")
        actions_display.append("[h]", style="bold yellow")
        actions_display.append("orizontal  ", style="")
        actions_display.append("[c]", style="bold yellow")
        actions_display.append("ontext  ", style="")
        actions_display.append("[s]", style="bold yellow")
        actions_display.append("ave  ", style="")
        actions_display.append("[i]", style="bold yellow")
        actions_display.append("ndex  ", style="")
        actions_display.append("[?]", style="bold yellow")
        actions_display.append("help  ", style="")
        actions_display.append("[q]", style="bold yellow")
        actions_display.append("uit", style="")
        layout["actions"].update(Panel(
            actions_display,
            border_style="yellow",
            padding=(0, 1)
        ))
        
        self.console.print(layout)
    
    def show_help(self):
        """Display help information."""
        help_text = """
[bold cyan]Passage Explorer - Help[/bold cyan]

[bold]Keyboard Shortcuts:[/bold]
  [n] - Load a new unique passage (not shown in last 30 days)
  [h] - Expand horizontally (show 2 related passages)
  [c] - Expand context (~400 words around passage)
  [s] - Save current passage to CSV collection
  [i] - Index next batch of files (if any pending)
  [?] - Show this help screen
  [q] - Quit application
  [Ctrl+C] - Exit gracefully

[bold]About:[/bold]
  Passage Explorer helps you discover and explore meaningful passages
  from your document library. Each session shows you new passages that
  haven't been displayed in the last 30 days.

[bold]Configuration:[/bold]
  Edit config.yaml to change library path and other settings.
        """
        
        self.console.print(Panel(
            help_text,
            title="[bold]Help[/bold]",
            border_style="cyan"
        ))
    
    def show_message(self, message: str, style: str = "info"):
        """Show a status message.
        
        Args:
            message: Message to display.
            style: Style ('info', 'success', 'warning', 'error').
        """
        styles = {
            'info': 'blue',
            'success': 'green',
            'warning': 'yellow',
            'error': 'red'
        }
        color = styles.get(style, 'blue')
        self.console.print(f"[{color}]{message}[/{color}]")
    
    def show_horizontal(self, base_passage, related_passages):
        """Display horizontal expansion: base + related passages."""
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="rows", ratio=3),
            Layout(name="footer", size=3),
        )

        layout["header"].update(Panel(
            "[bold cyan]Horizontal Expansion[/bold cyan]",
            border_style="cyan"
        ))

        rows = Layout()
        rows.split_row(
            Layout(name="base"),
            Layout(name="rel1"),
            Layout(name="rel2"),
        )

        def panel_for(p, title: str):
            meta = Path(p.source_file).name
            if p.document_title:
                title_text = f"{title} - {p.document_title}"
            else:
                title_text = title
            return Panel(
                Text(p.text),
                title=f"[bold]{title_text}[/bold]",
                subtitle=meta,
                border_style="blue",
            )

        rows["base"].update(panel_for(base_passage, "Base"))
        if related_passages:
            rows["rel1"].update(panel_for(related_passages[0], "Related 1"))
        if len(related_passages) > 1:
            rows["rel2"].update(panel_for(related_passages[1], "Related 2"))

        layout["rows"].update(rows)
        layout["footer"].update(Panel(
            "Press Enter to return",
            border_style="yellow",
        ))

        self.console.clear()
        self.console.print(layout)

    def show_context(self, passage, context_text: str):
        """Display context expansion around a passage."""
        text = Text(context_text)
        # Highlight the passage text if present
        if passage.text:
            text.highlight_words([passage.text], style="reverse")

        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="body", ratio=3),
            Layout(name="footer", size=3),
        )

        layout["header"].update(Panel(
            "[bold cyan]Context Expansion[/bold cyan]",
            border_style="cyan",
        ))
        layout["body"].update(Panel(
            text,
            title="[bold]Context[/bold]",
            border_style="green",
        ))
        layout["footer"].update(Panel(
            "Press Enter to return",
            border_style="yellow",
        ))

        self.console.clear()
        self.console.print(layout)
    
    def show_indexing_progress(self, current: int, total: int, filename: str):
        """Show indexing progress.
        
        Args:
            current: Current file number.
            total: Total files to index.
            filename: Name of current file being indexed.
        """
        self.console.print(f"[cyan]Indexing [{current}/{total}]: {filename}[/cyan]")
    
    def get_user_input(self) -> str:
        """Get user input (single character).
        
        Returns:
            User input character (lowercase).
        """
        try:
            # Use console input for better compatibility
            response = self.console.input("\n[bold]Action:[/bold] ").strip().lower()
            return response[0] if response else ''
        except (EOFError, KeyboardInterrupt):
            return 'q'
    
    def clear(self):
        """Clear the console."""
        self.console.clear()
