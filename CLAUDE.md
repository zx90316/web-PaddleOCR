# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A web-based OCR application built with FastAPI that provides a UI for PaddleOCR document recognition. Supports image and PDF uploads with keyword extraction and structured text recognition.

## Development Commands

### Running the Application

**IMPORTANT**: This project uses a dual-service architecture to avoid cuDNN conflicts between PyTorch and PaddlePaddle.

#### Quick Start (Recommended)
Use the startup script to launch both services simultaneously:
```bash
python start_services.py
```

This will:
1. Check for virtual environments `venv_clip` and `venv_paddle`
2. Launch CLIP service on port 8081
3. Launch PaddleOCR service on port 8080
4. Monitor both services and allow graceful shutdown with Ctrl+C

#### Manual Setup

##### 1. Setup CLIP Service (PyTorch environment)
In a separate virtual environment:
```bash
python -m venv venv_clip
venv_clip\Scripts\activate  # Windows
# source venv_clip/bin/activate  # Linux/Mac
pip install -r requirements_clip.txt
python clip_service.py
```
CLIP service starts on `http://localhost:8081`

##### 2. Setup PaddleOCR Service (PaddlePaddle environment)
In another virtual environment:
```bash
python -m venv venv_paddle
venv_paddle\Scripts\activate  # Windows
# source venv_paddle/bin/activate  # Linux/Mac
pip install -r requirements_paddle.txt
python app.py
```
Main service starts on `http://localhost:8080`

### Installing Dependencies

The project is split into two services with separate dependency files to avoid cuDNN version conflicts:

- **requirements_paddle.txt** - For the main PaddleOCR service (uses PaddlePaddle)
- **requirements_clip.txt** - For the CLIP image matching service (uses PyTorch)

Note: The legacy `requirements.txt` contains combined dependencies but should NOT be used due to cuDNN conflicts.

## Architecture

### Dual-Service Architecture

The application is split into two independent services to resolve cuDNN dependency conflicts:

**1. PaddleOCR Service (app.py)** - Main FastAPI application on port 8080:
- `visual_predict()` - Handles OCR detection and recognition on uploaded files
- `chat()` - Uses LLM to extract specified keywords from OCR results
- Calls CLIP service via HTTP for PDF page matching

**2. CLIP Service (clip_service.py)** - Image matching service on port 8081:
- Uses PyTorch + CLIP model for image similarity computation
- Provides `/match-page` endpoint for PDF page matching
- Returns matched page as Base64-encoded image

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

### PaddleOCR Service Endpoints (Port 8080)

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

**POST /ocr-with-matching** - PDF page matching + OCR endpoint
- Accepts: PDF file, positive template images, negative template images
- Calls CLIP service to find best matching page
- Performs OCR on the matched page
- Additional form parameters:
  - `positive_threshold` (float, default: 0.25)
  - `negative_threshold` (float, default: 0.30)

**GET /** - Serves web UI

**GET /admin** - Admin dashboard for task management

**GET /health** - Health check endpoint

### CLIP Service Endpoints (Port 8081)

**POST /match-page** - PDF page matching endpoint
- Accepts: PDF file, positive/negative template images
- Uses CLIP model to compute image similarity
- Returns: matched page number, score, Base64 image, all page scores

**GET /health** - Health check endpoint

### LLM Configuration

The pipeline uses a local Ollama instance for LLM-based keyword extraction. Configuration in PP-ChatOCRv4-doc.yaml:
- LLM_Chat and MLLM_Chat point to `http://localhost:11434/v1` (Ollama API)
- Model: gemma3:4b
- Prompt engineering includes rules for text extraction from OCR results and tables

### Processing Flow

#### Standard OCR Flow (/ocr endpoint)
1. File upload → temporary file creation
2. `pipeline.visual_predict()` → OCR processing with configurable options
3. Results saved to `output/` directory
4. `pipeline.chat()` → LLM extracts keywords from OCR results (if `use_llm=True`)
5. Return structured JSON with visual info, chat results, and output image references
6. Cleanup temporary files

#### PDF Page Matching Flow (/ocr-with-matching endpoint)
1. PDF and template images uploaded
2. Main service calls CLIP service via HTTP POST to `/match-page`
3. CLIP service:
   - Converts PDF to images
   - Computes similarity scores using CLIP model
   - Returns matched page as Base64 + scores
4. Main service receives matched page image
5. Performs standard OCR on matched page
6. Returns combined results (matching + OCR)

## Important Notes

- **Dual-Service Requirement**: Both services must be running for PDF page matching to work
- CLIP service URL can be configured via `CLIP_SERVICE_URL` environment variable (default: `http://localhost:8081`)
- Output directory is cleared on application startup
- Temporary uploaded files are cleaned up after processing
- Model paths in PP-ChatOCRv4-doc.yaml reference `./official_models/`
- The application serves processed images via `/output` static mount
- Task results are stored in SQLite database (`ocr_tasks.db`)

## Environment Variables

- `CLIP_SERVICE_URL` - URL of the CLIP service (default: `http://localhost:8081`)

## Troubleshooting

### cuDNN Conflicts
If you encounter cuDNN version conflicts, ensure you are using separate virtual environments:
- One for PaddleOCR service (with PaddlePaddle)
- One for CLIP service (with PyTorch)

### Connection Errors
If the main service cannot connect to CLIP service:
1. Verify CLIP service is running on port 8081
2. Check firewall settings
3. Verify `CLIP_SERVICE_URL` environment variable if using custom URL
