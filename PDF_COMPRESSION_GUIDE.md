# PDF Compression Guide (`pdf_optimization_service.py`)

| Mode | Target DPI | JPEG Quality | Behavior |
|---|---|---|---|
| **Original Quality** | Native | Native | Preserves full resolution with stream optimization |
| **High Quality** | 200 DPI | 88 | Light downsampling for large raster images |
| **Balanced** | 150 DPI | 75 | Recommended for mixed sketchnotes & manuals |
| **Small File Size** | 100 DPI | 55 | Maximum size reduction; displays a readability notice |

All modes preserve **searchable text**, **hyperlinks**, **PDF bookmarks**, and **document metadata**, and never modify the original source file.
