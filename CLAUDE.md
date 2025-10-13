# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A web-based OCR application built with FastAPI that provides a UI for PaddleOCR document recognition. Supports image and PDF uploads with keyword extraction and structured text recognition.

## Development Commands

### Running the Application
```bash
python app.py
```
Server starts on `http://localhost:8080`

### Installing Dependencies
```bash
pip install -r requirements.txt
```

Note: The project uses PaddleX with OCR and information extraction modules (`paddlex[ie]` and `paddlex[ocr]`).

## Architecture

### Core Components

**app.py** - Main FastAPI application with two key pipelines:
- `visual_predict()` - Handles OCR detection and recognition on uploaded files
- `chat()` - Uses LLM to extract specified keywords from OCR results

**PP-ChatOCRv4-doc.yaml** - Pipeline configuration defining the entire OCR processing chain:
- Layout detection (RT-DETR-H_layout_3cls)
- Document preprocessing (orientation classification, unwarping)
- Text detection (PP-OCRv5_server_det)
- Text recognition (PP-OCRv4_server_rec_doc)
- Table recognition (SLANet_plus)
- Seal recognition pipeline
- LLM integration for keyword extraction (configured for Ollama with gemma3:4b)

### Directory Structure

- `official_models/` - Contains PaddleOCR model directories (detection, recognition, layout, etc.)
- `templates/` - Jinja2 HTML templates for web UI
- `static/` - CSS and JavaScript assets
- `output/` - Temporary directory for processed images (cleared on startup)

### API Endpoints

**POST /ocr** - Main OCR processing endpoint
- Accepts: image files or PDF
- Form parameters:
  - `key_list` (JSON string array) - Keywords to extract
  - `use_doc_orientation_classify` (bool)
  - `use_doc_unwarping` (bool)
  - `use_textline_orientation` (bool)
  - `use_seal_recognition` (bool)
  - `use_table_recognition` (bool)
  - `use_llm` (bool)
- Returns: JSON with OCR results, extracted keywords, and output image paths

**GET /** - Serves web UI

**GET /health** - Health check endpoint

### LLM Configuration

The pipeline uses a local Ollama instance for LLM-based keyword extraction. Configuration in PP-ChatOCRv4-doc.yaml:
- LLM_Chat and MLLM_Chat point to `http://localhost:11434/v1` (Ollama API)
- Model: gemma3:4b
- Prompt engineering includes rules for text extraction from OCR results and tables

### Processing Flow

1. File upload → temporary file creation
2. `pipeline.visual_predict()` → OCR processing with configurable options
3. Results saved to `output/` directory
4. `pipeline.chat()` → LLM extracts keywords from OCR results (if `use_llm=True`)
5. Return structured JSON with visual info, chat results, and output image references
6. Cleanup temporary files

## Important Notes

- Output directory is cleared on application startup (`clear_output_dir()`)
- Temporary uploaded files are cleaned up after processing
- Model paths in PP-ChatOCRv4-doc.yaml reference `./official_models/`
- The application serves processed images via `/output` static mount
