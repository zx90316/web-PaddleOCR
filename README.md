# PaddleOCR 文檔識別網站 / PaddleOCR Document Recognition Web Application

[English](#english) | [繁體中文](#繁體中文)

---

## 繁體中文

一個基於 FastAPI 和 PaddleOCR 的文檔識別網站，支援圖片和 PDF 檔案的文字識別與關鍵字提取。

## 功能特色

- 🖼️ 支援多種圖片格式上傳（JPG、PNG、BMP等）
- 📄 支援 PDF 檔案上傳和多頁處理
- 🔍 基於 PaddleOCR 的高精度文字識別
- 💬 智慧關鍵字提取功能
- 🏷️ 預設關鍵字快速選擇（車輛、證件、公司、發票等分類）
- 👁️ 完整的圖片識別資訊顯示（包含文字區塊和座標）
- 📑 多頁面文件支援
- 🌐 簡潔美觀的網頁介面
- 📊 JSON 格式的結構化回應
- ⚙️ 可調整的處理設定選項

## 安裝步驟

**重要：本專案使用雙服務架構以避免 PyTorch 和 PaddlePaddle 的 cuDNN 衝突。**

### 方法一：使用啟動腳本（推薦）

1. 創建兩個虛擬環境並安裝依賴：

```bash
# CLIP 服務環境
python -m venv venv_clip
venv_clip\Scripts\activate  # Windows
# source venv_clip/bin/activate  # Linux/Mac
pip install -r requirements_clip.txt
deactivate

# PaddleOCR 服務環境
python -m venv venv_paddle
venv_paddle\Scripts\activate  # Windows
# source venv_paddle/bin/activate  # Linux/Mac
pip install -r requirements_paddle.txt
deactivate
```

2. 安裝並啟動 Ollama（用於 LLM 關鍵字提取）：

```bash
# 下載並安裝 Ollama: https://ollama.ai
ollama serve

# 在另一個終端下載模型
ollama pull gemma3:4b
```

3. 配置 LLM 設定（可選）：

編輯 `PP-ChatOCRv4-doc.yaml` 中的 LLM 配置：
```yaml
SubModules:
  LLM_Chat:
    module_name: chat_bot
    model_name: gemma3:4b  # 修改為您使用的模型
    base_url: "http://localhost:11434/v1"  # Ollama API 端點
    api_type: openai
    api_key: "sk-123456789"
```

4. 使用啟動腳本啟動兩個服務：

```bash
python start_services.py
```

這將自動啟動：
- CLIP 服務（Port 8081）
- PaddleOCR 服務（Port 8080）

### 方法二：手動啟動

在兩個不同的終端中分別啟動服務：

```bash
# 終端 1: CLIP 服務
venv_clip\Scripts\activate
python clip_service.py

# 終端 2: PaddleOCR 服務
venv_paddle\Scripts\activate
python app.py
```

## 使用方法

1. 開啟瀏覽器訪問：
```
http://localhost:8080         # 主頁面
http://localhost:8080/admin   # 管理後台
http://localhost:8080/batch-tasks  # 批次處理
```

2. 在網頁上：
   - 選擇要識別的圖片或PDF檔案
   - 輸入需要提取的關鍵字（每行一個）
   - 選擇是否使用文檔方向分類和去彎曲功能
   - 點擊「上傳並識別」按鈕

3. 系統會返回包含提取結果的 JSON 資料

## API 端點

### GET /
返回網站首頁

### POST /ocr
處理圖片 OCR 請求

**請求參數：**
- `file`: 圖片或PDF檔案
- `key_list`: JSON 格式的關鍵字列表
- `use_doc_orientation_classify`: 是否使用文檔方向分類（布林值）
- `use_doc_unwarping`: 是否使用文檔去彎曲（布林值）

**回應格式：**
```json
{
  "success": true,
  "data": {
    "chat_result": {
      // 關鍵字提取結果
    },
    "visual_info_list": [
      {
        "image_width": 1024,
        "image_height": 768,
        "text_regions": [
          {
            "text": "識別到的文字",
            "points": [{"x": 100, "y": 200}, ...]
          }
        ]
      }
    ],
    "key_list": ["關鍵字1", "關鍵字2"],
    "settings": {
      "use_doc_orientation_classify": false,
      "use_doc_unwarping": false
    }
  },
  "error": null
}
```

### GET /health
健康檢查端點

## 配置說明

### LLM 配置

編輯 `PP-ChatOCRv4-doc.yaml` 來配置 LLM 服務：

```yaml
SubModules:
  LLM_Chat:
    module_name: chat_bot
    model_name: gemma3:4b  # 模型名稱
    base_url: "http://localhost:11434/v1"  # Ollama API 端點
    api_type: openai
    api_key: "sk-123456789"  # API 金鑰（本地 Ollama 可以是任意值）
```

支援的模型：
- `gemma3:4b`（推薦，較快）
- `llama3:8b`
- `qwen2.5:7b`
- 其他支援 OpenAI API 格式的模型

### CLIP 服務配置

通過環境變數配置 CLIP 服務 URL（可選）：

```bash
export CLIP_SERVICE_URL=http://localhost:8081  # Linux/Mac
set CLIP_SERVICE_URL=http://localhost:8081     # Windows
```

## 注意事項

- **必須啟動 Ollama 服務**才能使用關鍵字提取功能（`use_llm=True`）
- 確保 PaddleOCR 和相關依賴正確安裝在各自的虛擬環境中
- 支援的檔案格式：JPG、PNG、BMP 等圖片格式以及 PDF 檔案
- 臨時檔案會在處理完成後自動清理
- PDF 頁面匹配需要兩個服務都在運行

## 故障排除

如果遇到問題，請檢查：

1. **Ollama 相關**
   - Ollama 服務是否正在運行：`ollama serve`
   - 模型是否已下載：`ollama list`
   - API 端點是否正確：檢查 `PP-ChatOCRv4-doc.yaml` 中的 `base_url`

2. **服務啟動問題**
   - 確認虛擬環境已正確創建並安裝依賴
   - 確認端口 8080 和 8081 未被佔用
   - 檢查 CLIP 服務是否啟動成功

3. **cuDNN 衝突**
   - 確保 PyTorch 和 PaddlePaddle 在不同的虛擬環境中
   - 使用 `requirements_clip.txt` 和 `requirements_paddle.txt` 分別安裝

4. **其他問題**
   - 檢查檔案格式是否支援
   - 確認網路連線正常
   - 查看控制台錯誤訊息

## 授權聲明

本項目採用 MIT 授權。詳細資訊請見 [LICENSE](LICENSE) 檔案。

### 第三方授權

本項目使用了以下開源軟體：

- **PaddleOCR** - Apache License 2.0
  - 版權所有 (c) 2020 PaddlePaddle Authors
  - 官方網站：https://github.com/PaddlePaddle/PaddleOCR
  - 授權詳情：https://github.com/PaddlePaddle/PaddleOCR/blob/release/2.7/LICENSE

### 致謝

- 感謝 PaddlePaddle 團隊提供優秀的 OCR 解決方案
- 本項目僅為 PaddleOCR 的網頁界面封裝，核心 OCR 功能由 PaddleOCR 提供

## 免責聲明

本軟體按「現狀」提供，不提供任何明示或暗示的保證。使用本軟體所產生的任何後果，作者不承擔責任。

---

## English

A web-based document recognition application built with FastAPI and PaddleOCR, supporting image and PDF file text recognition with keyword extraction.

## Features

- 🖼️ Support for multiple image formats (JPG, PNG, BMP, etc.)
- 📄 PDF file upload and multi-page processing
- 🔍 High-precision text recognition based on PaddleOCR
- 💬 Intelligent keyword extraction with LLM
- 🏷️ Preset keyword categories (vehicles, documents, companies, invoices, etc.)
- 👁️ Complete OCR information display (text blocks and coordinates)
- 📑 Multi-page document support
- 🌐 Clean and beautiful web interface
- 📊 Structured JSON responses
- ⚙️ Adjustable processing settings
- 🔄 Batch processing for large-scale PDF operations
- 📤 Excel export for batch results

## Installation

**Important: This project uses a dual-service architecture to avoid cuDNN conflicts between PyTorch and PaddlePaddle.**

### Method 1: Using Startup Script (Recommended)

1. Create two virtual environments and install dependencies:

```bash
# CLIP service environment
python -m venv venv_clip
venv_clip\Scripts\activate  # Windows
# source venv_clip/bin/activate  # Linux/Mac
pip install -r requirements_clip.txt
deactivate

# PaddleOCR service environment
python -m venv venv_paddle
venv_paddle\Scripts\activate  # Windows
# source venv_paddle/bin/activate  # Linux/Mac
pip install -r requirements_paddle.txt
deactivate
```

2. Install and start Ollama (for LLM keyword extraction):

```bash
# Download and install Ollama: https://ollama.ai
ollama serve

# In another terminal, download the model
ollama pull gemma3:4b
```

3. Configure LLM settings (optional):

Edit the LLM configuration in `PP-ChatOCRv4-doc.yaml`:
```yaml
SubModules:
  LLM_Chat:
    module_name: chat_bot
    model_name: gemma3:4b  # Change to your preferred model
    base_url: "http://localhost:11434/v1"  # Ollama API endpoint
    api_type: openai
    api_key: "sk-123456789"
```

4. Start both services using the startup script:

```bash
python start_services.py
```

This will automatically start:
- CLIP service (Port 8081)
- PaddleOCR service (Port 8080)

### Method 2: Manual Startup

Start services in two separate terminals:

```bash
# Terminal 1: CLIP service
venv_clip\Scripts\activate
python clip_service.py

# Terminal 2: PaddleOCR service
venv_paddle\Scripts\activate
python app.py
```

## Usage

1. Open your browser and visit:
```
http://localhost:8080              # Main page
http://localhost:8080/admin        # Admin dashboard
http://localhost:8080/batch-tasks  # Batch processing
```

2. On the web page:
   - Select an image or PDF file to recognize
   - Enter keywords to extract (one per line)
   - Choose whether to use document orientation classification and unwarping
   - Click the "Upload and Recognize" button

3. The system will return JSON data containing extraction results

## API Endpoints

### Single File Processing

**GET /** - Homepage

**POST /ocr** - Main OCR processing endpoint
- Accepts: image files or PDF
- Form parameters:
  - `file`: Image or PDF file
  - `key_list`: JSON array of keywords
  - `use_doc_orientation_classify`: Boolean
  - `use_doc_unwarping`: Boolean
  - `use_textline_orientation`: Boolean
  - `use_seal_recognition`: Boolean
  - `use_table_recognition`: Boolean
  - `use_llm`: Boolean

**POST /ocr-with-matching** - PDF page matching + OCR
- Accepts: PDF file, positive templates, negative templates
- Additional parameters:
  - `positive_threshold`: float (default: 0.25)
  - `negative_threshold`: float (default: 0.30)

### Batch Processing

**GET /batch-tasks** - Batch task management UI

**POST /api/batch-tasks/create** - Create batch task and scan directory

**POST /api/batch-tasks/{task_id}/stage1/config** - Configure CLIP matching parameters

**POST /api/batch-tasks/{task_id}/stage2/config** - Configure OCR parameters and keywords

**POST /api/batch-tasks/{task_id}/stage1/start** - Start Stage 1 processing

**POST /api/batch-tasks/{task_id}/stage2/start** - Start Stage 2 processing

**GET /api/batch-tasks/{task_id}/export** - Export results to Excel

**GET /health** - Health check endpoint

## Configuration

### LLM Configuration

Edit `PP-ChatOCRv4-doc.yaml` to configure the LLM service:

```yaml
SubModules:
  LLM_Chat:
    module_name: chat_bot
    model_name: gemma3:4b  # Model name
    base_url: "http://localhost:11434/v1"  # Ollama API endpoint
    api_type: openai
    api_key: "sk-123456789"  # API key (can be any value for local Ollama)
```

Supported models:
- `gemma3:4b` (recommended, faster)
- `llama3:8b`
- `qwen2.5:7b`
- Any model supporting OpenAI API format

### CLIP Service Configuration

Configure CLIP service URL via environment variable (optional):

```bash
export CLIP_SERVICE_URL=http://localhost:8081  # Linux/Mac
set CLIP_SERVICE_URL=http://localhost:8081     # Windows
```

## Important Notes

- **Ollama service must be running** to use keyword extraction (`use_llm=True`)
- Ensure PaddleOCR and dependencies are correctly installed in separate virtual environments
- Supported file formats: JPG, PNG, BMP images and PDF files
- Temporary files are cleaned up after processing
- PDF page matching requires both services running
- Batch processing runs in background threads with progress tracking

## Troubleshooting

If you encounter issues:

1. **Ollama Related**
   - Check if Ollama service is running: `ollama serve`
   - Check if model is downloaded: `ollama list`
   - Verify API endpoint in `PP-ChatOCRv4-doc.yaml`

2. **Service Startup Issues**
   - Confirm virtual environments are created and dependencies installed
   - Check if ports 8080 and 8081 are available
   - Verify CLIP service started successfully

3. **cuDNN Conflicts**
   - Ensure PyTorch and PaddlePaddle are in separate virtual environments
   - Use `requirements_clip.txt` and `requirements_paddle.txt` separately

4. **Other Issues**
   - Check file format compatibility
   - Verify network connection
   - Review console error messages

## Architecture

**Dual-Service Architecture:**

1. **PaddleOCR Service** (app.py, Port 8080)
   - Main FastAPI application
   - Handles OCR processing with PaddleOCR
   - Manages batch processing tasks
   - Calls CLIP service for PDF page matching

2. **CLIP Service** (clip_service.py, Port 8081)
   - Independent image matching service
   - Uses PyTorch + CLIP model
   - Provides `/match-page` endpoint for PDF page matching

**Databases:**
- `ocr_tasks.db` - Single OCR task history
- `batch_tasks.db` - Batch processing tasks and files

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

### Third-Party Licenses

This project uses the following open-source software:

- **PaddleOCR** - Apache License 2.0
  - Copyright (c) 2020 PaddlePaddle Authors
  - Official website: https://github.com/PaddlePaddle/PaddleOCR
  - License details: https://github.com/PaddlePaddle/PaddleOCR/blob/release/2.7/LICENSE

### Acknowledgments

- Thanks to the PaddlePaddle team for providing excellent OCR solutions
- This project is a web interface wrapper for PaddleOCR; core OCR functionality is provided by PaddleOCR

## Disclaimer

This software is provided "as is," without warranty of any kind, express or implied. The author assumes no responsibility for any consequences arising from the use of this software.