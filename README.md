# PaddleOCR 圖片識別網站

一個基於 FastAPI 和 PaddleOCR 的簡單圖片文字識別網站，允許用戶上傳圖片並提取指定的關鍵字。

## 功能特色

- 🖼️ 支援多種圖片格式上傳
- 🔍 基於 PaddleOCR 的高精度文字識別
- 💬 智慧關鍵字提取功能
- 🏷️ 預設關鍵字快速選擇（車輛、證件、公司、發票等分類）
- 👁️ 完整的圖片識別資訊顯示（包含文字區塊和座標）
- 📄 多頁面文件支援
- 🌐 簡潔美觀的網頁介面
- 📊 JSON 格式的結構化回應
- ⚙️ 可調整的處理設定選項

## 安裝步驟

1. 安裝依賴套件：
```bash
pip install -r requirements.txt
```

2. 確保本地運行 Ollama 服務（如果使用聊天功能）：
```bash
ollama serve
```

## 使用方法

1. 啟動網站：
```bash
python web_app.py
```

2. 開啟瀏覽器訪問：
```
http://localhost:8000
```

3. 在網頁上：
   - 選擇要識別的圖片檔案
   - 輸入需要提取的關鍵字（每行一個）
   - 選擇是否使用文檔方向分類和去彎曲功能
   - 點擊「上傳並識別」按鈕

4. 系統會返回包含提取結果的 JSON 資料

## API 端點

### GET /
返回網站首頁

### POST /ocr
處理圖片 OCR 請求

**請求參數：**
- `file`: 圖片檔案
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

在 `web_app.py` 中，您可以修改以下配置：

```python
chat_bot_config = {
    "module_name": "chat_bot",
    "model_name": "gemma3:4b",
    "base_url": "http://localhost:11434/v1",
    "api_type": "openai",
    "api_key": "sk-123456789",  # 您的 API 金鑰
}
```

## 注意事項

- 確保 PaddleOCR 和相關依賴正確安裝
- 如果使用聊天功能，需要本地運行 Ollama 服務
- 支援的圖片格式：JPG、PNG、BMP 等常見格式
- 臨時檔案會在處理完成後自動清理

## 故障排除

如果遇到問題，請檢查：
1. 所有依賴套件是否正確安裝
2. Ollama 服務是否正常運行
3. 圖片檔案格式是否支援
4. 網路連線是否正常
