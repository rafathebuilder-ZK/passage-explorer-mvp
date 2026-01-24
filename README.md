# Multi-Format Passage Explorer MVP

A terminal-based application that helps writers discover and explore meaningful passages from a collection of documents (PDFs, HTML files, plain text, Markdown) stored in nested folders.

## Features

- **Serendipitous Discovery**: Each session reveals new, previously unseen passages
- **Multi-Format Support**: Works with TXT, HTML, MD, and PDF files (staged implementation)
- **Session Tracking**: Excludes passages shown in the last 30 days
- **Beautiful Terminal UI**: Rich formatting with clear metadata display

## Installation

1. Clone or download this repository
2. Create a virtual environment (recommended):

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

## Usage

### Basic Usage

```bash
python -m src.main
```

### Command-Line Options

```bash
python -m src.main --help              # Show help message
python -m src.main --version           # Show version information
python -m src.main --library ./docs    # Override library path
python -m src.main --verbose           # Enable debug logging
python -m src.main --quiet             # Suppress non-essential output
python -m src.main --reset-sessions    # Clear session history
```

### Configuration

On first run, a `config.yaml` file will be created with default settings. You can also copy `config.yaml.example` to `config.yaml` and customize it:

```bash
cp config.yaml.example config.yaml
```

Default settings:

```yaml
library_path: "./Library-Sample"
max_passage_length: 420
session_history_days: 30
initial_indexing_batch_size: 8
progressive_indexing_batch_size: 4
```

Edit `config.yaml` to customize settings.

### Keyboard Shortcuts

- `n` - Load a new unique passage
- `h` - Expand horizontally (Stage 2)
- `c` - Expand context (Stage 2)
- `s` - Save passage (Stage 2)
- `?` - Show help
- `q` - Quit
- `Ctrl+C` - Exit gracefully

## Development Status

This is Stage 1 of the MVP, which includes:

- ✅ Project setup and configuration management
- ✅ Database schema for passages and sessions
- ✅ Text file (.txt) processing
- ✅ Basic passage extraction
- ✅ Session tracking (30-day exclusion)
- ✅ Terminal UI with rich library
- ✅ CLI interface with argument parsing
- ✅ Logging system

**Coming in Stage 2:**
- Semantic embeddings and passage quality scoring
- Horizontal expansion (related passages)
- Context expansion
- Save functionality with CSV export

**Coming in Stage 3:**
- HTML and Markdown file support

**Coming in Stage 4:**
- PDF file support

**Coming in Stage 5:**
- Progressive background indexing

## Project Structure

```
npcapp/
├── src/
│   ├── __init__.py
│   ├── main.py              # Entry point
│   ├── cli.py               # Command-line interface
│   ├── config.py            # Configuration management
│   ├── logger.py            # Logging setup
│   ├── passage_store.py     # Database operations
│   ├── document_processor.py # Document processing
│   ├── passage_extractor.py # Passage extraction
│   └── ui.py                # Terminal UI
├── data/                    # Application data
│   ├── passages.db         # SQLite database
│   └── app.log             # Log file
├── Library-Sample/          # Sample documents for testing (public domain)
├── Library/                 # Your personal library (not in git, keep private)
├── config.yaml             # Configuration file (created on first run, not in git)
├── config.yaml.example     # Configuration template
├── requirements.txt         # Python dependencies
├── LICENSE                  # MIT License
└── README.md               # This file
```

## Testing

The app includes a sample library (`Library-Sample/`) with test documents in multiple formats. Use this for testing during development.

## Privacy & Security

**Important**: Your personal library contents are kept private:
- The `Library/` directory is excluded from git (see `.gitignore`)
- Your `config.yaml` file (which may contain personal paths) is also excluded
- Only `Library-Sample/` (public domain test content) is included in the repository
- Database files and logs in `data/` are excluded from version control

When setting up your own library, create a `Library/` directory and add your documents there. This directory will never be committed to the repository.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
