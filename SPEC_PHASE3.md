# Passage Explorer - Phase 3 Specification

> **Note**: This document describes Phase 3: Full-Featured Web Demo. For previous phases, see [SPEC_ORIGINAL.md](SPEC_ORIGINAL.md) (Phase 1) and [SPEC.md](SPEC.md) (Phase 2). For current status, see [README.md](README.md).

## Overview

Phase 3 transforms the read-only Streamlit feed demo into a fully interactive web application that replicates all functionality from the terminal app. The web demo uses Library-Sample as the demo library and provides a terminal-style, mobile-friendly interface for exploring passages.

## Summary

Phase 3 builds on Phases 1 and 2 by adding a complete web interface:

- **Phase 1** (SPEC_ORIGINAL.md): Core terminal application with passage extraction, session tracking, and terminal UI
- **Phase 2** (SPEC.md): Fast startup with deferred background indexing, improved UX
- **Phase 3** (this document): Full-featured web demo with feed-based interface, terminal styling, and all terminal app actions

## Problem Statement

The original Streamlit demo (`web_app.py`) only provided a read-only feed view with pagination. Users could browse passages but couldn't interact with them using the same actions available in the terminal app (new passage, horizontal expansion, context, save, index).

## Phase 3 Goals

1. **Full Feature Parity**: Replicate all terminal app functionality in the web interface
2. **Feed-Based Interface**: Accumulate passages in a feed (up to 100) instead of single-passage view
3. **Terminal Aesthetic**: Apply terminal-style design (monospace font, dark theme, green buttons)
4. **Better Passage Presentation**: Format passages to handle broken line breaks from raw files
5. **Professional Citations**: Display metadata as Chicago-style citations
6. **Mobile-Friendly**: Responsive design that works on small screens
7. **Performance**: Lazy-load heavy components (similarity engine) to avoid blocking UI

## Key Features

### Interactive Passage Feed

- **Accumulating Feed**: Clicking "New Passage" adds passages to a feed (newest first)
- **Maximum 100 Passages**: Feed automatically limits to 100, removing oldest when exceeded
- **Timestamp Tracking**: Each passage shows when it was added to the feed
- **Passage Formatting**: Normalizes whitespace and line breaks for clean presentation

### All Terminal Actions

- **New Passage (n)**: Load random passage not shown in last 30 days, add to feed
- **Horizontal Exploration (h)**: Show 2 semantically related passages as "responses" to original
- **Context Expansion (c)**: Show ~400 words of context around passage
- **Save Passage (s)**: Save to database and CSV export
- **Index Next Batch (i)**: Manually trigger indexing of pending files with confirmation
- **Help (?)**: Show usage information

### Terminal-Style Design

- **Monospace Font**: Courier New throughout for terminal aesthetic
- **Dark Theme**: Dark background (#1e1e1e) with light text (#d4d4d4)
- **Green Buttons**: 
  - Neon green (#39ff14) with black bold text for "New Passage" (prominent)
  - Dark green for other main menu buttons (calm)
  - Subtle dark green for passage action buttons (less intense)
- **Terminal Colors**: Green headers (#4ec9b0), terminal-style passage boxes

### UI/UX Improvements

- **Main Menu**: All primary actions (New Passage, Clear Feed, Index, Help) in single row under title
- **Passage Feed Tracker**: Moved to top-right corner, passive display with smaller font
- **Location Info**: Moved below passage text (was in header)
- **Chicago Citations**: Metadata formatted as proper citations (Author. "Title." Location. File type.)
- **Copy Functionality**: Copy button for each passage (passage text + citation)
- **Return Buttons**: Moved to top of exploration views for better navigation
- **No Emojis**: Clean, text-only interface

### Passage Formatting

- **Normalized Whitespace**: Removes excessive spaces and newlines
- **Line Break Handling**: Joins broken lines that shouldn't be separated
- **Clean Presentation**: Passages display as readable paragraphs without formatting artifacts

### Performance Optimizations

- **Lazy Loading**: Similarity engine only loads when first needed (horizontal expansion)
- **Deferred Embeddings**: Embeddings skipped during indexing, computed on-demand
- **Immediate UI**: Header and basic UI render before heavy operations
- **Loading Indicators**: Spinners for heavy operations (similarity model, initial indexing)

## Implementation Details

### Feed Management

- **Session State**: `passage_feed` list stores up to 100 Passage objects
- **Timestamp Tracking**: `passage_timestamps` dict maps passage.id -> datetime
- **Automatic Cleanup**: Oldest passages removed when limit exceeded

### Passage Formatting

New `format_passage_text()` function:
- Normalizes all whitespace (multiple spaces/newlines → single space)
- Trims leading/trailing whitespace
- Applied to all passage displays (feed, horizontal, context)

### Chicago Citation Format

New `format_chicago_citation()` function:
- Format: `Author. "Title." Location. File type.`
- Handles missing author gracefully
- Uses page numbers, line numbers, chapters, sections appropriately

### Horizontal Exploration

- **Stacked Layout**: Related passages shown as "responses" below original (not side-by-side)
- **Visual Hierarchy**: Original passage first, then related passages with left border accent
- **No Duplicate Titles**: Removed "Related Passage 1" subheadings, kept "Related Passages" header

### Button Styling

CSS customizations:
- Primary button (New Passage): Neon green (#39ff14) with black bold text
- Regular buttons: Dark green (#2d5016) with white text
- Passage action buttons: Very dark green (#1e3d0f) with light green text, smaller font (0.85em)

### Lazy Loading Architecture

- Similarity engine initialized only when `get_related_passages()` is called
- Shows spinner on first use: "Loading similarity model (first time only, ~10-30 seconds)..."
- Embeddings computed on-demand during horizontal expansion, not during indexing

## Files Modified

- **`web_app.py`**: Complete rewrite
  - Replaced feed/pagination with interactive feed
  - Added all user actions (new, horizontal, context, save, index)
  - Added terminal styling CSS
  - Added passage formatting and citation functions
  - Added session state management for feed and timestamps
  - Integrated PassageExplorer components (SimilarityEngine, DocumentProcessor, etc.)

## Configuration

Uses Library-Sample as the demo library:
- Hardcoded path: `Library-Sample/`
- Same database: `data/passages.db`
- Same file formats: `.txt`, `.html`, `.md`, `.pdf`

## Success Criteria

- ✅ Web app shows accumulating passage feed (not single passage)
- ✅ All terminal actions work: new, horizontal, context, save, index, help
- ✅ Session tracking works (30-day exclusion)
- ✅ Horizontal exploration shows related passages as responses
- ✅ Context expansion shows ~400 words with highlighting
- ✅ Save functionality works (DB + CSV)
- ✅ Index next batch works with confirmation
- ✅ Background indexing status displays
- ✅ Terminal-style design applied throughout
- ✅ Passage formatting handles broken line breaks
- ✅ Chicago-style citations display correctly
- ✅ Copy button works for each passage
- ✅ Mobile-friendly responsive layout
- ✅ Uses Library-Sample as demo library
- ✅ Lazy loading prevents UI blocking
- ✅ No emojis, clean text-only interface

## User Interface Layout

### Main Feed View

```
┌─────────────────────────────────────────────────┐
│ Passage Explorer          [Indexing status]     │
│                          [Passage Feed (X/100)] │
├─────────────────────────────────────────────────┤
│ [New Passage] [Clear Feed] [Index] [Help]       │
├─────────────────────────────────────────────────┤
│ [Timestamp]                                      │
│ ┌─────────────────────────────────────────────┐ │
│ │ Passage text (formatted, clean)            │ │
│ └─────────────────────────────────────────────┘ │
│ Location: Page X / Chapter Y                    │
│ Author. "Title." p. X. PDF file.                │
│ [Copy] [Horizontal] [Context] [Save]            │
├─────────────────────────────────────────────────┤
│ [Next passage...]                                │
└─────────────────────────────────────────────────┘
```

### Horizontal Exploration View

```
┌─────────────────────────────────────────────────┐
│ Horizontal Exploration                          │
│ [Return]                                        │
├─────────────────────────────────────────────────┤
│ Original Passage                                │
│ ┌─────────────────────────────────────────────┐ │
│ │ Original passage text                      │ │
│ └─────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────┤
│ Related Passages                                │
│ ┌─────────────────────────────────────────────┐ │
│ │ Related passage 1 (left border accent)     │ │
│ └─────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────┐ │
│ │ Related passage 2 (left border accent)     │ │
│ └─────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────┘
```

## Related Documents

- [SPEC_ORIGINAL.md](SPEC_ORIGINAL.md): Phase 1 - Original MVP specification
- [SPEC.md](SPEC.md): Phase 2 - Fast startup improvements
- [README.md](README.md): Current features and usage
- [WISHLIST.md](WISHLIST.md): Future enhancements

## Technical Notes

### Streamlit Session State

The app uses Streamlit's session state to manage:
- `passage_feed`: List of Passage objects (max 100)
- `passage_timestamps`: Dict mapping passage.id -> datetime
- `view_mode`: Current view ('main', 'horizontal', 'context', 'help', 'confirm_index')
- `selected_passage_id`: ID of passage for actions
- `related_passages`: List of related passages for horizontal view
- `context_text`: Context string for context view
- Component instances: PassageStore, Config, SimilarityEngine, etc.

### Threading Considerations

- Background indexing runs in daemon thread
- Similarity engine loading happens synchronously but with spinner
- Streamlit reruns on each interaction, so state is preserved in session_state

### Browser Compatibility

- Uses modern JavaScript for clipboard functionality (fallback to code block selection)
- CSS uses standard properties (compatible with modern browsers)
- Responsive design works on mobile and desktop
