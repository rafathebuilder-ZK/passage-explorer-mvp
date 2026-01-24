## Wishlist / Future Enhancements

This file tracks post-MVP feature ideas that extend the core Passage Explorer experience.

### 1. `open` Action – Jump to Source File Location

- **Goal**: From a displayed passage, press a single key (e.g. `o`) to open the **original source file** at the exact passage location for deeper reading or editing.

- **Behavior**:
  - Available from the main passage view (not from expansion views).
  - Uses `passage.source_file`, `start_char`, `end_char`, and (where relevant) `line_number` to calculate the precise position.
  - Opens the file in the user’s preferred editor or pager, configured via:
    - `config.yaml` (e.g. `editor: "code"`, `editor_args: ["-g"]`) _or_
    - `$EDITOR` / `$PAGER` environment variables as a fallback.
  - For terminal-first behavior, there should also be a mode that:
    - Shows the surrounding lines in a pager-like view (e.g. `less +{line}`),
    - Or prints a small window (e.g. ±10 lines) with the passage highlighted.

- **Minimum Implementation Sketch**:
  - **Config**:
    - Add fields:
      - `editor_command` (string, optional)
      - `editor_args` (list of strings, optional)
      - `open_mode` (enum: `"editor" | "pager" | "print"`, default `"pager"`)
  - **Core logic**:
    - Helper function `open_source_for_passage(passage, config)` that:
      1. Resolves `passage.source_file` (must already be absolute).
      2. Computes a best-effort line number from `line_number` or by counting `\n` up to `start_char`.
      3. Dispatches based on `open_mode`:
         - `"editor"`: `subprocess.run([editor_command, *editor_args_with_line, source_file])`
         - `"pager"`: `less +{line}` or equivalent.
         - `"print"`: Reads a small line window and prints it via `rich`, with the passage highlighted.
  - **UI / Keybinding**:
    - New key: `o` = **open**.
    - Update help text and actions footer to include `[o]pen`.
    - On failure (missing editor, file, or permissions), show a clear error message and keep the app running.

- **Notes / Edge Cases**:
  - If the stored `line_number` is `None`, fall back to a character-based window around `start_char` when printing or estimating a line.
  - For PDFs, where page/char mapping is approximate, start at the passage’s stored `page_number` if available and note that the position may be approximate.
  - Should never corrupt or modify the source document—strictly read/open only.

### 2. Smarter Passage Randomization / Source Balancing

- **Goal**: Avoid over-sampling very large sources (e.g., a big book) when the library contains many smaller documents (articles, essays), so sessions feel more “varied” and horizontally exploratory across sources.

- **Behavior**:
  - Passage selection should:
    - Consider **source-level balancing**, not just uniform random over all passages.
    - Prevent a single huge PDF or TXT from dominating the stream of passages.
    - Prefer showing passages from **under-sampled documents** within the 30-day window.
  - Possible user-facing options in `config.yaml`:
    - `source_balancing_mode: "uniform_sources" | "proportional" | "off"` (default `"uniform_sources"`).
    - `min_sources_per_session` to encourage rotation across at least N different documents.

- **Minimum Implementation Sketch**:
  - Add per-source stats to the DB (or derive from `passages` + `session_history`):
    - `total_passages_per_source`
    - `shown_passages_per_source_last_30_days`
  - Passage selection algorithm:
    1. Start from the usual candidate set (not shown in last 30 days).
    2. Group by `source_file` and compute a **weight** per source:
       - For `"uniform_sources"`: weight each document equally, regardless of size.
       - For `"proportional"`: weight by number of passages, but dampened (e.g. sqrt).
    3. Sample a source by weight, then randomly sample a passage within that source.
  - Optionally log selection stats in `usage_events` to tune the weighting (e.g. track which sources are under- or over-sampled).- **Notes / Edge Cases**:
  - For very small libraries (few documents), the behavior should effectively match current uniform passage sampling.
  - When new documents are indexed, initially **boost** their weight so they show up early and get “broken in.”
  - Respect the 30-day exclusion window when computing “under-sampled” status.

### 3. Fast First Passage with Deferred Indexing

- **Goal**: Make the app feel instantly responsive on startup by showing a passage **immediately**, then running indexing in the background instead of blocking the first run on a full initial indexing batch.

- **Current behavior (simplified)**:
  - On app launch:
    1. Validate config and library path.
    2. Run an initial blocking indexing batch (default 8 files).
    3. Only after that, fetch and display the first passage.
    4. Start background progressive indexing.

- **Desired behavior**:
  - On app launch:
    1. Validate config and library path.
    2. If there are already indexed passages, **immediately** show a passage (skip blocking initial indexing).
    3. If no passages exist yet:
       - Index just enough to show a single passage (or a very small batch).
       - Show the passage as soon as it is available.
    4. Kick off progressive indexing in the background for the rest of the library.

- **Minimum Implementation Sketch**:
  - Add a helper in `PassageStore`:
    - `has_any_passages()` or `get_indexed_passage_count()`.
  - Startup flow:
    - If `has_any_passages()` is true:
      - **Skip** blocking `initial_indexing_batch`.
      - Immediately enter the main loop and fetch a passage.
      - Start background indexing thread in parallel (if there are pending files).
    - If no passages:
      - Run a minimal blocking index (e.g. 1–2 files or until at least one passage is available).
      - Show the first passage as soon as it’s inserted into the DB.
      - Start background indexing for remaining files.
  - Optional config:
    - `first_run_fast_start: true/false` to enable/disable this behavior.

- **Notes / Edge Cases**:
  - If the library is empty or contains only unreadable/corrupted files, still show a clear “No passages available” message as today.
  - Ensure background indexing never blocks UI, and keep `[i]` (manual index) as an override.
  - Avoid race conditions between “first passage” fetch and the background indexer on first run.

### 4. Lightweight Web UI (Mobile-Friendly) with PIN Access

- **Goal**: Allow accessing Passage Explorer from a phone or other devices via a simple web page, optionally shareable with trusted friends using a short PIN code (e.g., 4 digits), while keeping the underlying library local/private.

- **Behavior**:
  - Run a small HTTP server alongside the terminal app (or as a separate mode), serving:
    - A minimal, mobile-friendly web UI:
      - Shows the current passage and metadata.
      - Supports the same core actions: new (`n`), horizontal (`h`), context (`c`), save (`s`), index (`i`).
    - A simple “session” concept so multiple clients see their own passage flow.
  - Access control:
    - When the web UI is enabled, require a short **PIN** on first visit:
      - PIN configured in `config.yaml` (e.g., `web_pin: "1234"`).
      - Optionally allow a `web_readonly: true/false` mode for friends (e.g., no save/index from guest devices).
    - PIN is checked per browser session (e.g., stored in a signed cookie).

- **Minimum Implementation Sketch**:
  - Add a `--web` flag or mode:
    - `python -m src.main --web` starts both the terminal UI and an HTTP server (or just the web UI).
  - Use a lightweight framework (e.g. `fastapi` or `flask`) to:
    - Expose endpoints:
      - `GET /` – main page (HTML/JS).
      - `GET /passage` – fetch current or next passage JSON.
      - `POST /action` – apply actions: `{"action": "n"|"h"|"c"|"s"|"i"}`.
      - `POST /login` – submit PIN, set a signed session cookie on success.
    - Reuse the existing `PassageExplorer` logic behind an internal API layer.
  - UI:
    - Single-page view with big touch-friendly buttons:
      - New, Horizontal, Context, Save, Index.
    - Responsive layout that works well on small screens.

- **Notes / Edge Cases**:
  - Network:
    - Initially limit to `localhost` or a single LAN IP; exposing to the public internet is out of scope for MVP.
  - Security:
    - PIN is **not** strong authentication; it’s meant for trusted local networks.
    - Clearly document that the library remains on the host machine; only passages are sent over HTTP.
  - Concurrency:
    - Decide whether all web clients share a single “session” or each gets an independent session.
    - Use existing `usage_events` logging to track web vs terminal usage (e.g., `source: "web"` in `info`).

### 5. PDF Context View – Preserve Layout & Avoid Scrambled Text

- **Goal**: When using the context (`c`) action on passages from PDFs, ensure the expanded context is readable and not “scrambled” (e.g., broken line ordering, merged columns, or odd spacing from PDF extraction).

- **Behavior**:
  - Detect when a passage’s `file_type` is `pdf` and use a PDF-aware context extraction strategy.
  - Prefer page-aware extraction from `pdfplumber`:
    - Use the passage’s `page_number`, `start_char`, and `end_char` to:
      - Re-extract only the relevant page(s).
      - Build a context window that respects line/paragraph boundaries on that page.
  - Clean up PDF quirks:
    - Normalize whitespace and line breaks.
    - Avoid mixing columns or headers/footers into the middle of the passage when possible.

- **Minimum Implementation Sketch**:
  - Add a PDF-specific helper, e.g. `get_pdf_context_for_passage(passage)`:
    - Uses `pdfplumber` to load the page containing the passage.
    - Reconstructs paragraphs based on PDF layout (`extract_words` / `extract_text` with layout hints).
    - Builds a ~400-word window around the passage that preserves logical reading order.
  - In `get_context_for_passage`:
    - If `file_type == "pdf"`, delegate to `get_pdf_context_for_passage`.
    - Otherwise, keep the current text-file/HTML/MD logic.

- **Notes / Edge Cases**:
  - Scanned/OCR PDFs may still have messy text; handle gracefully and fall back to the simpler char-window approach when layout info is unreliable.
  - Multi-column PDFs are hard; start with “good enough” heuristics and refine later.
  - Log problematic PDFs (via `usage_events` or regular logs) to identify cases where context quality is poor and needs tuning.

### 6. Cooperative Cancellation for Background Indexing

- **Goal**: Make shutdowns more responsive, even when indexing large PDFs or long documents, by allowing background indexing to cooperatively check for a “stop” signal and exit quickly.

- **Behavior**:
  - When the user triggers shutdown (Ctrl+C or `q`):
    - Signal the background indexing thread(s) to stop as soon as it’s safe.
    - Long-running operations (e.g., indexing a huge PDF) should periodically check this signal and abort early rather than processing the entire file.
  - The app should:
    - Finish any already-committed work.
    - Leave the DB in a consistent state.
    - Mark partially processed files as `failed` or `pending` so they can be re-indexed later.

- **Minimum Implementation Sketch**:
  - Add a shared cancellation flag/event (e.g., `threading.Event()`):
    - Stored on `PassageExplorer` (e.g., `self._cancel_indexing_event`).
  - In the background indexing worker and `index_files`:
    - Check `event.is_set()` between files and, where feasible, inside per-file loops (e.g., page-by-page for PDFs).
    - If set:
      - Break out of loops.
      - Mark any in-progress file appropriately (e.g. `status="failed"` or leave as `pending`).
  - Hook signal handling:
    - On SIGINT/SIGTERM (and on `q`), set the cancellation event before starting graceful shutdown.

- **Notes / Edge Cases**:
  - Don’t attempt to interrupt low-level library calls that aren’t easily cancellable; instead, check the flag at natural boundaries (e.g., between pages).
  - Ensure the lock (`_indexing_lock`) is always released, even on early exit.
  - Log when indexing is cancelled for a file so users can see which documents may need re-indexing later.

### 7. PDF to Text Pre-Processing Pipeline

- **Goal**: Convert all PDFs in the library to properly formatted text files, then remove PDF indexing support entirely. This simplifies the codebase, improves text quality, and avoids PDF-specific quirks.

- **Behavior**:
  - Add a one-time conversion tool/script:
    - Scans the library for `.pdf` files.
    - Converts each PDF to a `.txt` file (or `.md` if structure is preserved) with:
      - Proper spacing and line breaks.
      - Page breaks marked (e.g., `--- Page N ---`).
      - Cleaned-up text (normalized whitespace, removed artifacts).
    - Optionally preserves metadata (title, author) in the text file header or filename.
  - After conversion:
    - Remove PDF handler from `DocumentProcessor`.
    - Remove PDF-specific code paths (e.g., `page_number` handling can be simplified or removed).
    - Update documentation to reflect that only TXT, HTML, and MD are supported.

- **Minimum Implementation Sketch**:
  - Create a standalone script: `scripts/convert_pdfs_to_text.py`:
    - Uses `pdfplumber` to extract text page-by-page.
    - Applies text cleaning/normalization.
    - Writes to `Library/` (or a subdirectory) as `.txt` files.
    - Logs conversion status and any failures.
  - Migration path:
    - Run the conversion script once.
    - Optionally migrate existing PDF passages in the DB to point to the new `.txt` files (or mark them for re-indexing).
  - Update `DocumentProcessor`:
    - Remove `PDFHandler` class.
    - Remove `.pdf` from `supported_extensions`.

- **Notes / Edge Cases**:
  - Handle very large PDFs gracefully (stream processing, progress indicators).
  - Preserve original PDFs (don’t delete them) unless user explicitly requests it.
  - For scanned/OCR PDFs, text quality may vary; document this limitation.
  - Consider keeping PDF support as an optional/experimental feature flag if some users prefer direct PDF indexing.

### 8. Deploy as Public Website (passages.rafael.fyi)

- **Goal**: Host Passage Explorer as a publicly accessible web application at `passages.rafael.fyi`, allowing access from any device with internet connectivity.

- **Behavior**:
  - Deploy the web UI (from wishlist item #4) to a production server:
    - Domain: `passages.rafael.fyi` (already owned and controlled).
    - HTTPS enabled.
    - Persistent database and library storage on the server.
  - Access control:
    - PIN-based authentication (as described in wishlist item #4).
    - Optional: user accounts for multiple users (future enhancement).
  - Infrastructure considerations:
    - Server hosting (e.g., VPS, cloud provider).
    - Database backups.
    - Library file storage and management.
    - Auto-restart on server reboot (systemd service, Docker, etc.).

- **Minimum Implementation Sketch**:
  - **Deployment options**:
    - Option A: Traditional VPS with systemd service.
    - Option B: Docker container with docker-compose.
    - Option C: Cloud platform (Heroku, Railway, Fly.io, etc.).
  - **Domain setup**:
    - DNS configuration pointing `passages.rafael.fyi` to server IP.
    - SSL certificate (Let’s Encrypt via certbot).
    - Reverse proxy (nginx or Caddy) to handle HTTPS and route to the app.
  - **Application changes**:
    - Ensure web UI is production-ready (from wishlist item #4).
    - Add environment variable configuration for production settings.
    - Set up logging and monitoring.
    - Configure CORS if needed for API access.

- **Notes / Edge Cases**:
  - Security: PIN authentication is minimal; consider stronger auth for public deployment.
  - Performance: Ensure the app can handle concurrent users if sharing with friends.
  - Data privacy: Library contents will be on a server; ensure appropriate access controls.
  - Backup strategy: Regular backups of database and library files.
  - Cost: Consider hosting costs for storage and bandwidth.

### 9. Open Source on GitHub

- **Goal**: Publish the Passage Explorer codebase to GitHub as an open-source project, making it available for others to use, contribute to, and learn from.

- **Behavior**:
  - Create a GitHub repository (e.g., `rafael/passage-explorer` or similar).
  - Add proper project documentation:
    - Clear README with installation and usage instructions.
    - LICENSE file (choose appropriate license, e.g., MIT, Apache 2.0).
    - CONTRIBUTING.md if accepting contributions.
    - CHANGELOG.md for version history.
  - Code quality:
    - Ensure code is clean and well-documented.
    - Add `.gitignore` for sensitive files (config.yaml with paths, data/ directory, etc.).
    - Consider adding example config files.

- **Minimum Implementation Sketch**:
  - **Repository setup**:
    - Initialize git repository (if not already done).
    - Create `.gitignore`:
      - `data/` (database, logs, CSV exports).
      - `config.yaml` (may contain sensitive paths).
      - `venv/`, `__pycache__/`, etc.
      - `Library/` (user's actual documents - too large and private).
    - Add `config.yaml.example` as a template.
  - **Documentation**:
    - Update README.md with:
      - Project description and goals.
      - Installation steps.
      - Usage examples.
      - Configuration guide.
    - Add LICENSE file.
  - **Initial commit and push**:
    - Commit all code (excluding ignored files).
    - Push to GitHub.
    - Optionally create initial release/tag.

- **Notes / Edge Cases**:
  - Privacy: Ensure no sensitive data (library contents, personal paths) is committed.
  - License choice: Consider project goals when selecting a license.
  - Community: Decide if accepting contributions, issue tracking, etc.

### 10. Web UI: Clickable Menu & Scrollable Passage Feed

- **Goal**: Improve the web interface (from wishlist item #4) to be more intuitive and efficient, replacing the “click new each time” pattern with a scrollable feed and persistent navigation menu.

- **Behavior**:
  - **Scrollable passage feed**:
    - Display multiple passages in a vertical scrollable list (like a social media feed).
    - Auto-load new passages as user scrolls (infinite scroll) or provide a “Load More” button.
    - Each passage card shows:
      - Passage text.
      - Metadata (title, author, location, file type).
      - Action buttons (horizontal, context, save) per passage.
  - **Persistent navigation menu**:
    - Fixed or sticky menu bar at top/bottom with:
      - “New Passages” button (loads next batch).
      - “Saved Passages” view (shows user’s saved collection).
      - Settings/Config access.
      - User info (if logged in).
  - **Improved UX**:
    - No need to click “new” for each passage; scroll to see more.
    - Quick actions (save, expand) available per passage without navigation.
    - Mobile-friendly touch targets and responsive design.

- **Minimum Implementation Sketch**:
  - **Frontend changes**:
    - Replace single-passage view with a feed component:
      - React/Vue component or vanilla JS with a feed container.
      - Fetch multiple passages at once (e.g., 10-20 per batch).
      - Implement infinite scroll or pagination.
    - Add persistent navigation component:
      - Sticky header/footer with main actions.
      - Routing or state management for different views (feed, saved, settings).
  - **Backend API updates**:
    - `GET /passages?limit=20&offset=0` – fetch multiple passages.
    - `GET /saved` – fetch user’s saved passages.
    - Keep existing action endpoints (`POST /action`) but allow per-passage actions.
  - **State management**:
    - Track which passages have been shown to avoid duplicates.
    - Maintain scroll position if user navigates away and returns.

- **Notes / Edge Cases**:
  - Performance: Loading many passages at once may be slow; implement pagination or virtual scrolling.
  - Mobile: Ensure smooth scrolling and touch interactions on phones.
  - Session management: Each user/browser session should have its own passage feed state.
  - 30-day exclusion: Still respect the exclusion window when loading new passages.

### 11. Keep Library Private in Public Repository

- **Goal**: When publishing the codebase to GitHub (wishlist item #9), ensure the personal library contents remain private and are never committed to the public repository, even if the code itself is open source.

- **Behavior**:
  - The `Library/` directory and its contents should be:
    - Excluded from git via `.gitignore`.
    - Never referenced in example configs or documentation with real paths.
    - Clearly documented as user-specific and private.
  - Repository should include:
    - `Library-Sample/` as example/test data (already public domain content).
    - `config.yaml.example` with placeholder paths.
    - Clear documentation that users should keep their `Library/` directory private.

- **Minimum Implementation Sketch**:
  - **`.gitignore` updates**:
    - Ensure `Library/` is explicitly ignored (not just `Library-Sample/`).
    - Add patterns to catch any accidental library references:
      - `Library/`
      - `config.yaml` (may contain absolute paths to user's library).
      - `data/` (database may contain file paths).
  - **Documentation**:
    - Add a `PRIVACY.md` or section in README explaining:
      - Library contents are private and never committed.
      - How to set up your own library directory.
      - Best practices for keeping library paths out of version control.
  - **Pre-commit checks** (optional):
    - Add a git hook or CI check to scan commits for accidental library paths or sensitive data.

- **Notes / Edge Cases**:
  - If library paths are ever accidentally committed, provide guidance on removing them from git history.
  - Consider using environment variables or separate config files for deployment-specific paths.
  - Make it clear in documentation that `Library-Sample/` is for testing only, not a template for real libraries.

### 12. RSS Feed with Automated Updates

- **Goal**: Provide an RSS feed of new passages that updates automatically (via cron job or scheduled task), allowing users to subscribe and receive new passages in their RSS reader.

- **Behavior**:
  - Generate an RSS feed (XML format) containing:
    - Recent passages (e.g., last 50-100, or passages from last 7 days).
    - Each item includes:
      - Passage text as description/content.
      - Metadata (title, author, source file, location).
      - Publication date (when passage was indexed or shown).
      - Link to view passage in web UI (if deployed).
  - Automated updates:
    - Cron job or scheduled task runs periodically (e.g., daily, hourly).
    - Triggers indexing of new files (if any).
    - Regenerates RSS feed XML file.
    - Optionally publishes to a web-accessible location.

- **Minimum Implementation Sketch**:
  - **RSS generation**:
    - Create `src/rss_generator.py`:
      - Queries database for recent passages (ordered by `extracted_at` or `created_at`).
      - Formats as RSS 2.0 XML.
      - Writes to `data/passages.rss` or web-accessible location.
  - **Cron job setup**:
    - Script: `scripts/update_rss.sh` or `scripts/update_rss.py`:
      - Runs indexing (if needed).
      - Generates RSS feed.
      - Optionally uploads to web server.
    - Cron entry: `0 * * * *` (hourly) or `0 0 * * *` (daily).
  - **Web integration**:
    - If deployed, serve RSS at `/feed.xml` or `/rss.xml`.
    - Set proper `Content-Type: application/rss+xml` header.

- **Notes / Edge Cases**:
  - RSS feed should respect 30-day exclusion (only show passages that would be shown to users).
  - Consider pagination if feed gets very large (RSS readers typically handle 50-100 items well).
  - Privacy: RSS feed exposes passage content publicly; ensure this aligns with privacy goals.
  - Feed validation: Use RSS validators to ensure compatibility with common readers.

### 13. Code Optimization & Efficient Database Design

- **Goal**: Optimize the codebase for performance and ensure saved passages are persistently remembered, while keeping the RSS feed database operations lean and efficient to avoid excessive data consumption.

- **Behavior**:
  - **Saved passages**:
    - Ensure saved passages are fully persistent and never lost.
    - Optimize queries for saved passages (indexed lookups, efficient joins).
    - Provide fast access to saved passages collection.
  - **RSS feed efficiency**:
    - RSS generation should be lightweight:
      - Query only necessary fields (not full passage text if not needed).
      - Use efficient date-based queries with proper indexes.
      - Cache RSS XML if content hasn't changed.
    - Avoid storing redundant data in database for RSS purposes.
  - **General optimizations**:
    - Database indexes on frequently queried fields.
    - Query optimization (avoid N+1 queries, use joins where appropriate).
    - Connection pooling for database access.
    - Lazy loading of embeddings (only load when needed for similarity search).

- **Minimum Implementation Sketch**:
  - **Database optimization**:
    - Review and add indexes:
      - `passages.source_file` (already indexed).
      - `passages.extracted_at` (for RSS date ordering).
      - `saved_passages.passage_id` and `saved_passages.saved_at`.
      - `usage_events.action` and `usage_events.created_at`.
    - Consider database vacuum/optimization for SQLite.
  - **RSS generation**:
    - Query only: `id`, `text`, `document_title`, `author`, `extracted_at`, `source_file`.
    - Use `LIMIT` and `ORDER BY extracted_at DESC`.
    - Cache RSS XML with timestamp; regenerate only if new passages added since last generation.
  - **Code profiling**:
    - Profile slow operations (indexing, similarity search, passage selection).
    - Optimize hot paths (e.g., passage selection query).
  - **Saved passages**:
    - Ensure `saved_passages` table has proper foreign key constraints.
    - Add method to efficiently fetch all saved passages with metadata (single query with join).

- **Notes / Edge Cases**:
  - Balance between optimization and code readability/maintainability.
  - Monitor database size; implement archiving/cleanup for old usage events if needed.
  - Consider database migrations if schema changes are needed for optimization.
  - Test optimizations with realistic data volumes (e.g., 10k+ passages).

### 14. Deploy Domain After Stable Website (Cost Optimization)

- **Goal**: Deploy the website to `passages.rafael.fyi` only after the web interface is stable and working well, and minimize recurring hosting/infrastructure costs.

- **Behavior**:
  - **Phased deployment approach**:
    1. First: Develop and test web UI locally or on a free/low-cost platform.
    2. Second: Deploy to a staging/test domain or subdomain for validation.
    3. Third: Only after stability is confirmed, deploy to `passages.rafael.fyi`.
  - **Cost minimization strategies**:
    - Use free/low-cost hosting options where possible:
      - Free tier cloud services (e.g., Railway, Fly.io free tier, Render free tier).
      - Low-cost VPS providers (e.g., DigitalOcean $5/month, Linode, Vultr).
      - Static site hosting for frontend (if separated) + serverless functions.
    - Optimize resource usage:
      - Lightweight web framework (FastAPI, Flask) with minimal dependencies.
      - Efficient database usage (SQLite may be sufficient for single-user or small scale).
      - Consider serverless/edge functions for API if traffic is low.
    - Minimize storage costs:
      - Library files stored efficiently (compression if needed).
      - Database backups to free storage (e.g., GitHub releases, free cloud storage).

- **Minimum Implementation Sketch**:
  - **Development phase**:
    - Build and test web UI locally.
    - Use `localhost` or local network for initial testing.
    - No domain or hosting costs during development.
  - **Staging phase**:
    - Deploy to free platform (Railway, Render, etc.) with a test subdomain.
    - Validate all features work in production-like environment.
    - Monitor performance and fix issues.
  - **Production deployment**:
    - Choose hosting based on requirements:
      - If low traffic: Free tier or $5-10/month VPS.
      - If higher traffic: Scale up as needed.
    - Set up domain DNS and SSL (Let's Encrypt is free).
    - Configure monitoring and backups.
  - **Cost tracking**:
    - Document expected monthly costs.
    - Set up alerts if costs exceed budget.
    - Review and optimize regularly.

- **Notes / Edge Cases**:
  - Free tiers often have limitations (e.g., sleep after inactivity, resource limits); plan accordingly.
  - Domain registration is typically $10-15/year (one-time or annual cost).
  - SSL certificates are free via Let's Encrypt.
  - Consider backup strategies that don't add significant cost (e.g., automated backups to free cloud storage).
  - If costs become prohibitive, consider making the app self-hostable so users can run it on their own infrastructure.
