# PDF Outline Extractor - Round 1A

## Approach

This solution extracts structured outlines from PDF documents by analyzing text formatting and patterns. The approach combines:

1. **Text Extraction with Formatting**: Uses PyMuPDF to extract text while preserving font information
2. **Title Detection**: Identifies document title from the largest text on the first page
3. **Heading Classification**: Uses font size, style, and pattern matching to classify headings
4. **Level Determination**: Assigns H1, H2, H3 levels based on relative font sizes and numbering patterns

## Key Features

- **Multi-criteria Heading Detection**: Font size, bold formatting, numbering patterns, and ALL CAPS
- **Adaptive Level Assignment**: Relative font size analysis for different document styles
- **Pattern Recognition**: Supports various heading formats (1., 1.1, Chapter N, etc.)
- **Deduplication**: Removes duplicate headings across pages

## Models/Libraries Used

- **PyMuPDF (fitz)**: PDF text extraction with formatting information
- **NumPy**: Numerical operations for text analysis
- **Standard Python libraries**: re, json, collections

## Build and Run

