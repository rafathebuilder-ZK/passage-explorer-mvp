# Multi-Format Passage Explorer MVP

A terminal-based application that helps writers discover and explore meaningful passages from a collection of documents (PDFs, HTML files, plain text, Markdown) stored in nested folders.

## Features

- **Serendipitous Discovery**: Each session reveals new, previously unseen passages
- **Multi-Format Support**: Works with TXT, HTML, MD, and PDF files
- **Session Tracking**: Excludes passages shown in the last 30 days
- **Fast Startup**: Shows passages immediately if available, minimal indexing on first run
- **Background Indexing**: Progressive indexing runs in background without blocking UI
- **Beautiful Terminal UI**: Rich formatting with clear metadata display and indexing status

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
python -m src.main --verbose             # Enable debug logging
python -m src.main --quiet             # Suppress non-essential output
```

### Reset Commands

**⚠️ Important**: All reset commands require **triple confirmation** and **archive data** before deletion. Archives are saved to `data/archive/` with timestamps.

```bash
# Reset session history (allows passages to be shown again)
python -m src.main --reset-sessions

# Reset indexing status (forces re-indexing of all files)
python -m src.main --reset-indexing

# Reset saved passages collection
python -m src.main --reset-saved

# Reset everything (sessions, indexing, saved passages)
python -m src.main --reset-all
```

**Reset Process**:
1. You'll be prompted to type `YES`, then `CONFIRM`, then `DELETE` (triple confirmation)
2. Data is automatically archived to `data/archive/` with timestamp
3. Original data is then deleted from the database
4. Archives can be restored manually if needed (CSV format)

**What Gets Reset**:
- `--reset-sessions`: Clears 30-day session history (passages can be shown again)
- `--reset-indexing`: Clears file indexing status (files will be re-indexed on next run)
- `--reset-saved`: Clears your saved passages collection
- `--reset-all`: Resets all of the above

**Fully Reset Application**:

To completely reset the application to a fresh state:

```bash
# Option 1: Reset all data (recommended - archives everything)
python -m src.main --reset-all

# Option 2: Manual full reset (if you want to reset database too)
# 1. Archive and reset all data
python -m src.main --reset-all

# 2. (Optional) Delete database to start completely fresh
#    Note: This will also delete all passages
rm data/passages.db

# 3. Restart app - it will recreate database and re-index files
python -m src.main
```

**Archive Location**: All archived data is saved to `data/archive/` with timestamps:
- `sessions_archive_YYYYMMDD_HHMMSS.csv`
- `indexing_status_archive_YYYYMMDD_HHMMSS.csv`
- `saved_passages_archive_YYYYMMDD_HHMMSS.csv`

Archives are in CSV format and can be manually restored if needed.

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
fast_startup: true              # Skip blocking indexing if passages exist
min_first_run_indexing: 2        # Max files to index on first run before showing passage
```

Edit `config.yaml` to customize settings.

### Keyboard Shortcuts

- `n` - Load a new unique passage
- `h` - Expand horizontally (show 2 related passages)
- `c` - Expand context (~400 words around passage)
- `s` - Save passage to CSV collection
- `i` - Manually trigger next indexing batch
- `?` - Show help
- `q` - Quit
- `Ctrl+C` - Exit gracefully (cancels background indexing)

## Development Status

### Phase 1 (Completed)
- ✅ Project setup and configuration management
- ✅ Database schema for passages and sessions
- ✅ Multi-format support (TXT, HTML, MD, PDF)
- ✅ Passage extraction with semantic scoring
- ✅ Session tracking (30-day exclusion)
- ✅ Terminal UI with rich library
- ✅ CLI interface with argument parsing
- ✅ Logging system
- ✅ Horizontal expansion (related passages)
- ✅ Context expansion
- ✅ Save functionality with CSV export
- ✅ Progressive background indexing

### Phase 2 (Completed)
- ✅ Fast startup: Immediate passage display if available
- ✅ Minimal first-run indexing: Only 1-2 files before showing first passage
- ✅ Background indexing status indicator
- ✅ Cooperative cancellation: Graceful shutdown during indexing
- ✅ Enhanced error handling and edge case management
- ✅ Improved user experience with better error messages

### Future Enhancements
See [WISHLIST.md](WISHLIST.md) for planned features including:
- Source balancing for passage selection
- Web UI
- RSS feed
- And more...

## Documentation Files

- **README.md** (this file) - Main documentation: features, installation, usage
- **SPEC_PHASE1.md** - Phase 1 specification (original MVP, detailed, all stages)
- **SPEC_PHASE2.md** - Phase 2 specification (fast startup improvements)
- **SPEC_PHASE3.md** - Phase 3 specification (full-featured web demo)
- **WISHLIST.md** - Future enhancement ideas and feature requests
- **GITHUB_SETUP.md** - Guide for setting up GitHub repository
- **NEXT_STEPS.md** - Step-by-step guide for pushing to GitHub
- **config.yaml.example** - Configuration template (copy to `config.yaml`)

## Project Structure

```
npcapp/
├── src/                     # Source code
│   ├── __init__.py
│   ├── main.py              # Entry point and application orchestration
│   ├── cli.py               # Command-line interface
│   ├── config.py            # Configuration management
│   ├── logger.py            # Logging setup
│   ├── passage_store.py     # Database operations (passages, sessions, indexing status)
│   ├── document_processor.py # Multi-format document processing (TXT, HTML, MD, PDF)
│   ├── passage_extractor.py # Passage extraction and quality scoring
│   ├── similarity.py        # Semantic similarity and embeddings
│   └── ui.py                # Terminal UI with Rich library
├── data/                    # Application data (not in git)
│   ├── passages.db         # SQLite database
│   ├── app.log             # Log file
│   ├── saved_passages.csv  # Saved passages export
│   └── archive/             # Archived data (created on reset)
│       ├── sessions_archive_YYYYMMDD_HHMMSS.csv
│       ├── indexing_status_archive_YYYYMMDD_HHMMSS.csv
│       └── saved_passages_archive_YYYYMMDD_HHMMSS.csv
├── Library-Sample/          # Sample documents for testing (public domain)
├── Library/                 # Your personal library (not in git, keep private)
├── config.yaml             # Your configuration (created on first run, not in git)
├── config.yaml.example     # Configuration template
├── requirements.txt         # Python dependencies
├── LICENSE                  # MIT License
├── web_app.py              # Streamlit web demo entrypoint (NPC Library)
└── README.md               # This file
```

## Web Demo (NPC Library)

A minimal web demo is available on top of the existing terminal app. It lets you browse passages from the sample **NPC Library** (`Library-Sample/`) in a bare-bones, mobile-friendly web UI.

### Prerequisites

- Install dependencies (including Streamlit):

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Prepare the demo database

Make sure the sample library has been indexed at least once using the existing terminal app:

```bash
python -m src.main --library ./Library-Sample
```

This populates `data/passages.db`, which the web demo reads in **read-only** mode.

### Run the web demo locally

```bash
streamlit run web_app.py
```

This starts a local web server and opens a browser tab where you can:
- Select a work from the NPC Library (Alice, Moby-Dick, etc.)
- Browse extracted passages with simple pagination

The terminal app remains unchanged and can still be run with:

```bash
python -m src.main --library ./Library-Sample
```

### Deploying the web demo

To share a public link (e.g. in Discord), deploy `web_app.py` to a Streamlit-compatible host (such as Streamlit Community Cloud or Hugging Face Spaces) and configure the command:

```bash
streamlit run web_app.py --server.port $PORT --server.address 0.0.0.0
```

The hosted app will provide an HTTPS URL you can share. The web UI is intentionally minimal and text-focused so it works well on both desktop and mobile browsers.

## How It Works

### Startup Behavior

1. **First Run** (no passages in database):
   - Validates library path and checks for supported files
   - Indexes 1-2 files (configurable) to get first passage
   - Shows passage immediately when available
   - Starts background indexing for remaining files

2. **Subsequent Runs** (passages exist):
   - Checks for existing passages
   - Shows passage immediately (skips blocking indexing)
   - Starts background indexing in parallel

### Background Indexing

- Runs automatically in background thread
- Never blocks the UI
- Processes files in small batches (default: 4 files per batch)
- Status indicator shows pending file count in UI header
- Can be cancelled gracefully with Ctrl+C or 'q'

## Testing

The app includes a sample library (`Library-Sample/`) with test documents in multiple formats. Use this for testing during development.

### Quick Test

```bash
# Run with sample library (default)
python -m src.main

# Test with custom library
python -m src.main --library ./your-library-path

# Reset session history for testing (requires triple confirmation)
python -m src.main --reset-sessions
```

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
