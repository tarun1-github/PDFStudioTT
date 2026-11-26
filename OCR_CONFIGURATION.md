# Local OCR Configuration

## Offline OCR Engines
PDF Studio uses 100% local, offline OCR with zero cloud or external AI APIs:
1. **Tesseract OCR** (used automatically if `tesseract.exe` is in `PATH`).
2. **Windows 11 Built-in OCR (`Windows.Media.Ocr.OcrEngine`)** via `scripts/win_ocr.ps1` (active default on Windows 11 when Tesseract is not installed).

## Performance & Memory Controls
- PDFs and Office documents extract embedded text first (`PyMuPDF`, `python-docx`, `python-pptx`, `openpyxl`); OCR runs **only** on images or scanned PDFs with `< 15` characters of embedded text.
- Images larger than `1800px` are downscaled in a temporary directory prior to OCR so full-size copies are not held in memory.
- Analysis results are cached in Streamlit `st.session_state` per upload batch.

## Limitations
- Handwritten notes with low contrast or heavily skewed scans may yield `Low confidence` or `Not detected` and should be reviewed/adjusted in the Smart Sequence Detection table before compiling.
