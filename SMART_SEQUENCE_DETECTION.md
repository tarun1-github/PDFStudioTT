# Smart Sequence Detection Architecture

## Overview
`backend/services/document_sequence_service.py` analyses uploaded images, PDFs, Office documents (`DOCX`, `PPTX`, `XLSX`), and text/HTML/Markdown files to determine chapter and page order before PDF compilation or Learning Book generation.

## Supported Patterns
- **Page numbers**: `Page 1`, `Page 01`, `Page 1 of 10`, `1/10`, `1 of 10`, `Pg. 1`, `p. 12`, Roman numerals (`i`, `ii`, `iii`, `iv`), and standalone header/footer numbers.
- **Chapters & Sections**: `Chapter 1`, `CHAPTER 03`, `Unit 1`, `Module 2`, `Section 3`, `Appendix A`/`B`, and hierarchical numbers (`1.1`, `1.2`, `1.10`, `2.1`, `2.10`) sorted naturally.
- **False-Positive Filtering**: Excludes dates (`2026-11-26`), IP addresses (`10.106.44.24`), phone numbers, software versions (`Version 2.10`), figure labels (`Figure 3`), and model/port numbers (`Model 1234`).

## Confidence & Safety Rules
- **High confidence** (`>= 80%`), **Medium confidence** (`55–79%`), **Low confidence** (`< 55%`), **Not detected** (`0%`), **Duplicate page**, **Missing sequence number**.
- Unclassified files are preserved in original upload order and never discarded.
- Duplicate pages are flagged with warnings and never auto-removed.
