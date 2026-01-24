# Sample Library for MVP Testing

This folder contains sample documents in multiple formats for testing the Passage Explorer MVP during development.

## Structure

- `txt/` - 5 plain text files (public domain novels)
- `html/` - 5 HTML files (same content as TXT)
- `md/` - 5 Markdown files (same content as TXT)
- `pdf/` - 5 PDF files (same content as TXT, ready for Stage 4 testing)

## Files Included

All files contain excerpts from public domain works:

1. **Alice's Adventures in Wonderland** by Lewis Carroll
2. **Pride and Prejudice** by Jane Austen
3. **Moby-Dick** by Herman Melville
4. **A Scandal in Bohemia** (Sherlock Holmes) by Arthur Conan Doyle
5. **A Tale of Two Cities** by Charles Dickens

## Usage

This sample library contains test documents in all supported formats:
- **TXT files**: Plain text format (`txt/` folder)
- **HTML files**: HTML format (`html/` folder)
- **Markdown files**: Markdown format (`md/` folder)
- **PDF files**: PDF format (`pdf/` folder)

All formats are fully supported. The files are clean, uncorrupted, and contain sufficient text for passage extraction testing.

### Testing the App

Use this sample library to test Passage Explorer:

```bash
# Use default library path (Library-Sample)
python -m src.main

# Or specify explicitly
python -m src.main --library ./Library-Sample
```

## Note

This is a separate test library. Your actual Library folder with your documents remains untouched at `/Users/rafa/Documents/npcapp/Library/`.
