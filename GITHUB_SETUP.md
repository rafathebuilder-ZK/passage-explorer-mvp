# GitHub Repository Setup Guide

This document outlines the recommended settings for publishing Passage Explorer to GitHub.

## Repository Settings

### Repository Name
**Recommended**: `passage-explorer` or `passage-explorer-mvp`

**Alternatives**:
- `passage-explorer-app`
- `multi-format-passage-explorer`
- `passage-discovery-tool`

### Description
**Recommended**: 
```
A terminal-based application for discovering and exploring meaningful passages from PDFs, HTML, Markdown, and text documents. Perfect for writers and researchers.
```

**Shorter alternative**:
```
Terminal app for serendipitous discovery of passages from multi-format document libraries
```

### Visibility
**Recommended**: **Public** ✅

**Rationale**:
- Wishlist item #9 explicitly mentions "Open Source on GitHub"
- MIT License is appropriate for open source projects
- The codebase doesn't contain sensitive information (user data is excluded via .gitignore)
- Public visibility encourages contributions and adoption

**If you prefer Private initially**:
- You can start with Private to test the setup
- Change to Public when ready (Settings → Danger Zone → Change visibility)

### Topics/Tags
Add these topics to help discoverability:
- `python`
- `terminal-app`
- `document-processing`
- `pdf-parser`
- `text-analysis`
- `passage-extraction`
- `semantic-search`
- `cli-tool`
- `document-explorer`
- `writer-tools`

## Files Status

### ✅ Already Configured

1. **`.gitignore`** - Updated to exclude:
   - `Library/` directory (your personal documents)
   - `config.yaml` (user-specific configuration)
   - `data/` directory (database and logs)
   - `venv/` (virtual environment)
   - Python cache files
   - IDE files
   - OS files

2. **`config.yaml.example`** - Template for users to copy

3. **`LICENSE`** - MIT License added

4. **`README.md`** - Updated with:
   - License information
   - Privacy & Security section
   - Configuration instructions

### 📝 Files to Commit

**Include in repository**:
- ✅ `src/` - All source code
- ✅ `Library-Sample/` - Sample test documents (public domain)
- ✅ `requirements.txt` - Dependencies
- ✅ `README.md` - Documentation
- ✅ `SPEC_PHASE1.md` - Phase 1 specification (original MVP)
- ✅ `SPEC_PHASE2.md` - Phase 2 specification (fast startup improvements)
- ✅ `SPEC_PHASE3.md` - Phase 3 specification (full-featured web demo)
- ✅ `WISHLIST.md` - Future enhancements
- ✅ `LICENSE` - MIT License
- ✅ `config.yaml.example` - Configuration template
- ✅ `.gitignore` - Git ignore rules

**Exclude from repository** (already in .gitignore):
- ❌ `Library/` - Your personal documents
- ❌ `config.yaml` - Your personal configuration
- ❌ `data/` - Database and logs
- ❌ `venv/` - Virtual environment
- ❌ `__pycache__/` - Python cache

## GitHub Repository Settings

### General Settings

1. **Description**: Use the recommended description above
2. **Website**: (Optional) Leave blank or add `passages.rafael.fyi` if deployed
3. **Topics**: Add the topics listed above

### Features

1. **Issues**: ✅ Enable
   - Useful for bug reports and feature requests
   - Aligns with wishlist item #9 (open source)

2. **Projects**: ⚠️ Optional
   - Can be useful for tracking development stages
   - Not necessary for MVP

3. **Wiki**: ❌ Disable
   - README.md is sufficient for documentation

4. **Discussions**: ⚠️ Optional
   - Can be useful for community engagement
   - Not necessary initially

5. **Sponsors**: ⚠️ Optional
   - Enable if you want to accept sponsorships

### Security

1. **Dependency graph**: ✅ Enable
   - Helps identify security vulnerabilities

2. **Dependabot alerts**: ✅ Enable
   - Automatically alerts about vulnerable dependencies

3. **Secret scanning**: ✅ Enable
   - Prevents accidental commit of API keys or secrets

### Actions

1. **Actions**: ⚠️ Optional (for future)
   - Can add CI/CD later
   - Not necessary for initial setup

## Initial Commit Checklist

Before pushing to GitHub:

- [ ] Verify `.gitignore` is correct (run `git status` to check)
- [ ] Ensure `Library/` is not tracked
- [ ] Ensure `config.yaml` is not tracked
- [ ] Ensure `data/` is not tracked
- [ ] Verify `config.yaml.example` exists
- [ ] Verify `LICENSE` file exists
- [ ] Review `README.md` for accuracy
- [ ] Test that the app works with `Library-Sample/`
- [ ] Commit all changes
- [ ] Create initial commit message: "Initial commit: Passage Explorer MVP"

## Post-Setup Steps

After creating the repository:

1. **Add repository description and topics** on GitHub
2. **Create initial release** (optional):
   - Tag: `v0.1.0` or `v1.0.0`
   - Title: "Initial Release - MVP Phase 1 & 2"
   - Description: Brief summary of current features (see README.md for complete list)

3. **Add badges** to README (optional):
   ```markdown
   ![License](https://img.shields.io/badge/license-MIT-blue.svg)
   ![Python](https://img.shields.io/badge/python-3.9+-blue.svg)
   ```

4. **Consider adding**:
   - `CONTRIBUTING.md` - Contribution guidelines (if accepting contributions)
   - `CHANGELOG.md` - Version history
   - Issue templates (for bug reports, feature requests)

## Privacy Verification

Before making the repository public, verify:

1. **No personal data in code**:
   ```bash
   git log --all --full-history --source -- "*Library*"
   git log --all --full-history --source -- "*config.yaml*"
   ```

2. **Check for API keys or secrets**:
   ```bash
   git grep -i "api_key\|secret\|password\|token" -- "*.py" "*.yaml" "*.md"
   ```

3. **Verify .gitignore is working**:
   ```bash
   git status
   # Should NOT show Library/, config.yaml, data/, venv/
   ```

## Recommended Repository Structure

```
passage-explorer/
├── .gitignore              ✅ (excludes private files)
├── LICENSE                 ✅ (MIT License)
├── README.md               ✅ (updated with privacy info)
├── SPEC.md                 ✅ (Phase 2 specification)
├── SPEC_ORIGINAL.md        ✅ (original MVP specification)
├── WISHLIST.md             ✅ (future enhancements)
├── config.yaml.example     ✅ (template)
├── requirements.txt        ✅ (dependencies)
├── src/                    ✅ (source code)
│   ├── __init__.py
│   ├── main.py
│   ├── cli.py
│   ├── config.py
│   ├── logger.py
│   ├── passage_store.py
│   ├── document_processor.py
│   ├── passage_extractor.py
│   └── ui.py
└── Library-Sample/         ✅ (public domain test data)
    ├── txt/
    ├── html/
    ├── md/
    └── pdf/
```

## Summary

✅ **Repository Name**: `passage-explorer`  
✅ **Description**: "A terminal-based application for discovering and exploring meaningful passages from PDFs, HTML, Markdown, and text documents."  
✅ **Visibility**: **Public**  
✅ **License**: MIT (already added)  
✅ **`.gitignore`**: Updated to exclude private files  
✅ **`config.yaml.example`**: Created as template  
✅ **README.md**: Updated with privacy section and license info  

You're ready to create the GitHub repository! 🚀
