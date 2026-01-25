# Passage Explorer - Phase 2 Specification

> **Note**: This document describes Phase 2 improvements. For the original MVP specification, see [SPEC_PHASE1.md](SPEC_PHASE1.md). For current status, see [README.md](README.md).

## Overview

Phase 2 focuses on improving the user experience by implementing fast startup with deferred background indexing. This addresses the critical UX issue where the app blocked on initial indexing before displaying any passages.

## Problem Statement

The original implementation blocked on initial indexing (8 files) before displaying any passages, creating a poor first-run experience. Users had to wait for indexing to complete before seeing any content, even when passages already existed in the database.

## Phase 2 Goals

1. **Fast Startup**: Show passages immediately if they exist in the database
2. **Minimal First-Run Indexing**: Index only 1-2 files before showing first passage
3. **Background Indexing**: Never block UI, always run indexing in background
4. **Cooperative Cancellation**: Graceful shutdown during indexing
5. **Better Error Handling**: Clear, actionable error messages
6. **Status Indicators**: Non-intrusive background indexing status

## Key Features

### Fast Startup with Deferred Indexing

- **Check for existing passages first**: Before any indexing, check if passages already exist
- **Immediate passage display**: If passages exist, skip blocking indexing and show passage immediately
- **Minimal first-run indexing**: If no passages exist, index only 1-2 files (configurable) before showing content
- **Background indexing**: Always run progressive indexing in background, never blocking UI

### Cooperative Cancellation

- Background indexing can be cancelled gracefully
- Cancellation checks between files and PDF pages
- Proper cleanup on shutdown (Ctrl+C or 'q')

### Enhanced Error Handling

- Specific error messages for common failure scenarios:
  - Empty library
  - All files corrupted/unreadable
  - No passages extracted from valid files
  - Permission errors
- Actionable suggestions in error messages

### Background Indexing Status

- Non-intrusive status indicator in UI header
- Shows pending file count when indexing
- Updates dynamically

## Configuration Options

New configuration options in `config.yaml`:

```yaml
# Fast startup settings
fast_startup: true              # Skip blocking indexing if passages exist
min_first_run_indexing: 2       # Max files to index on first run before showing passage
```

## Implementation Details

### Database Helpers

Added to `PassageStore`:
- `has_any_passages()`: Check if any passages exist
- `get_passage_count()`: Get total passage count

### New Methods

- `index_files_until_passage_available()`: Index files until at least one passage is available
- `_has_supported_files()`: Validate library has supported files

### Threading

- `_cancel_indexing_event`: Threading.Event for cooperative cancellation
- Background indexing worker checks cancellation flag
- PDF handler checks cancellation between pages

## Files Modified

- `src/passage_store.py`: Added passage count helpers
- `src/main.py`: Refactored startup flow, added minimal indexing, cancellation
- `src/document_processor.py`: Added cancellation support to PDF handler
- `src/config.py`: Added new config options
- `src/ui.py`: Added background indexing status indicator
- `config.yaml.example`: Added example config values

## Success Criteria

- ✅ App shows passage immediately if passages exist in database
- ✅ App indexes max 1-2 files on first run before showing passage
- ✅ Background indexing never blocks UI
- ✅ App can be cancelled gracefully during indexing
- ✅ Clear error messages for edge cases
- ✅ Status indicator shows indexing progress
- ✅ No regression in existing functionality

## Related Documents

- [SPEC_PHASE1.md](SPEC_PHASE1.md): Phase 1 - Original MVP specification
- [README.md](README.md): Current features and usage
- [WISHLIST.md](WISHLIST.md): Future enhancements
- `.cursor/plans/phase_2_*.plan.md`: Detailed implementation plan
