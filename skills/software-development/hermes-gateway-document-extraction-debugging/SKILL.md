---
name: hermes-gateway-document-extraction-debugging
description: Investigate Telegram/gateway OCR or document-ingestion complaints in Hermes, verify real extraction behavior, and patch explicit fallbacks for PDF/Office docs.
tags: [hermes-agent, gateway, telegram, ocr, documents, pdf, docx, pptx, xlsx, debugging]
---

# Hermes Gateway Document Extraction / OCR Debugging

Use when:
- user says Telegram/gateway OCR is broken
- documents are reaching Hermes but the assistant acts like it cannot read them
- you need to confirm whether the problem is extraction logic, missing dependencies, or misleading fallback text

## Why this exists

A real failure mode happened where Telegram documents were cached correctly, but `gateway/run.py` only prepended a generic note like “file saved here, ask user what to do with it.”
That meant:
- PDF/docx/pptx/xlsx content was not actually extracted into agent context
- OCR complaints were valid even when file download worked
- PDF backend absence was hidden behind vague behavior

The fix path was not “install OCR and hope”; it required confirming the enrichment path and making failures explicit.

## Investigation flow

1. Verify the actual document-enrichment path in `gateway/run.py`.
   Look for the `MessageType.DOCUMENT` branch inside `_handle_message_with_agent` / `_handle_message` flow.

2. Check what the code currently does for document MIME types.
   Red flags:
   - only sanitizes filename and appends a generic note
   - text files are injected, but `application/*` files are not
   - no special handling for PDF/docx/pptx/xlsx

3. Check runtime dependency availability before blaming the user input.
   Useful probe:

```bash
python3 - <<'PY'
import importlib.util
for m in ['pymupdf', 'fitz', 'pytest', 'dotenv']:
    print(m, bool(importlib.util.find_spec(m)))
PY
```

Interpretation:
- `pymupdf` missing => PDF text extraction / OCR backend unavailable
- `pytest` missing => cannot rely on local pytest run for verification
- `dotenv` missing => direct import of gateway modules may fail in stripped interpreters even if `py_compile` passes

4. Confirm whether the complaint is about:
   - normal text PDF not extracted
   - scanned/image-only PDF needing OCR
   - Office docs not being read at all

## Implementation pattern that worked

### 1) Extract document enrichment into a helper
Create a helper like:
- `_build_document_context_parts(paths, media_types)`

This makes targeted tests possible without needing the full `GatewayRunner` runtime scaffold.

### 2) Keep filename sanitization reusable
Create a helper for cached filenames such as:
- `_extract_cached_document_display_name(path)`

Cached Telegram docs often look like:
- `doc_<12hex>_<original_filename>`

Strip the prefix and sanitize the remainder.

### 3) Normalize extracted text centrally
Use a helper like:
- `_normalize_document_text(text, max_chars=12000)`

Recommended behavior:
- strip `\x00`
- normalize CRLF to LF
- collapse 3+ blank lines to double newlines
- trim whitespace
- truncate large extracted payloads with an explicit truncation marker

### 4) Support Office Open XML without third-party packages
For `.docx`, `.pptx`, `.xlsx`, use stdlib only:
- `zipfile`
- `xml.etree.ElementTree`

This is a good default because it avoids introducing more dependencies just to read common Office files.

Patterns that worked:
- DOCX: parse `word/document.xml`, collect `w:t`
- PPTX: parse `ppt/slides/slide*.xml`, collect `a:t`
- XLSX:
  - parse `xl/sharedStrings.xml`
  - parse `xl/worksheets/sheet*.xml`
  - resolve `t='s'` shared-string indexes
  - join visible cell values into tab/newline separated text

### 5) Handle PDF separately and be honest about backend availability
Use a helper like `_extract_pdf_text(path) -> (text, status)`.

Recommended statuses:
- `ok`
- `backend_unavailable`
- `no_text`
- `error`

Behavior:
- if `pymupdf` is missing, return `backend_unavailable`
- if PDF opens but yields no text, return `no_text`
- if extraction crashes, log and return `error`

Important: `no_text` usually means image-only/scanned PDF, so OCR would be needed.
Do not pretend text extraction succeeded.

## Required UX behavior

Do NOT leave the agent with a vague “ask the user what to do with it” note.
Instead prepend explicit context blocks:

### When extraction succeeds
Say readable text was extracted and include it in context.

### When PDF backend is missing
Tell the agent explicitly that:
- automatic PDF text extraction / OCR is unavailable on this Hermes instance
- the file path is still available
- the user should be told OCR is not configured yet
- admin can install `PyMuPDF` / `pymupdf`

### When no readable text exists
Tell the agent explicitly that:
- embedded text could not be found
- file may be scanned / image-only
- OCR would be needed
- ask user for pasted text or a clearer export

### When extraction errors unexpectedly
Tell the agent explicitly that:
- document/OCR processing failed
- user should retry or share the text directly

This matches the user's preference for transparent failure states over silent degradation.

## Testing strategy that worked

Add focused regression tests in `tests/gateway/test_telegram_documents.py`.

Best pattern:
- test `_build_document_context_parts(...)` directly
- avoid full `GatewayRunner` scaffolding unless necessary
- build tiny synthetic OOXML files with `zipfile.writestr(...)`

Recommended cases:
1. PDF without backend -> explicit OCR fallback mentioning `PyMuPDF/pymupdf`
2. DOCX -> extracted body text appears
3. PPTX -> extracted slide text appears
4. XLSX -> extracted cell text appears

Why this mattered:
- a full runner stub became noisy and brittle
- direct helper tests were much simpler and more reusable
- environment constraints (`pytest` missing, `dotenv` missing) made thin tests more practical

## Verification checklist

1. `python3 -m py_compile gateway/run.py tests/gateway/test_telegram_documents.py`
2. If available, run targeted pytest:

```bash
python3 -m pytest tests/gateway/test_telegram_documents.py -q
```

3. If pytest or runtime deps are missing, report that explicitly:
- syntax passed
- targeted tests added
- runtime/pytest blocked by missing packages

## Pitfalls

### Pitfall 1: Download success != OCR success
Telegram caching the file only proves transport worked.
It says nothing about whether content was extracted.

### Pitfall 2: Generic fallback text hides root cause
If the code only says “file saved here,” users interpret that as OCR being flaky.
In reality extraction may never have been attempted.

### Pitfall 3: Image-only PDF is not the same as backend-missing PDF
Keep these separate:
- `backend_unavailable` => environment/config problem
- `no_text` => file content problem (scanned/image-only)

### Pitfall 4: Full-runner tests can waste time
If the bug is in enrichment logic, isolate it in a helper and test that helper directly.
This is faster and avoids huge mocking scaffolds.

## Reporting template

- root cause: document enrichment only added generic notes / backend missing / scanned PDF
- changed: helper extraction for PDF/docx/pptx/xlsx + explicit fallback notes
- verified: syntax check passed, targeted tests added
- blocked by env: mention missing `pytest`, `pymupdf`, or `dotenv` if relevant
