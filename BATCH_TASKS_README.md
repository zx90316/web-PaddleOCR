# 批次任務管理系統使用說明

## 概述

批次任務管理系統允許您批量處理大量 PDF 文件，自動執行 CLIP 圖像匹配和 OCR 識別，並將結果匯出為 Excel 文件。

## 功能特點

### ✅ 核心功能

1. **批次檔案掃描**
   - 遞迴掃描指定目錄（支援本地路徑和網路磁碟）
   - 自動識別所有 PDF 文件
   - 記錄檔案路徑、名稱、大小等資訊

2. **兩階段處理流程**
   - **第一階段（CLIP 匹配）**：使用 CLIP 模型從每個 PDF 中找出最相似的頁面
   - **第二階段（OCR 識別）**：對匹配的頁面執行 PaddleOCR 識別並提取關鍵字

3. **任務控制**
   - 開始：啟動任務處理
   - 暫停：暫停處理，可隨時恢復
   - 停止：完全停止任務
   - 重來：重新執行某個階段

4. **進度監控**
   - 實時查看任務進度
   - 查看每個階段的完成情況
   - 查看處理失敗的檔案

5. **結果預覽與匯出**
   - 查看匹配的頁面圖片
   - 查看提取的關鍵字
   - 匯出結果為 Excel 格式

## 使用流程

### 1. 創建批次任務

1. 訪問 `http://localhost:8080/batch-tasks`
2. 點擊「新增任務」按鈕
3. 輸入任務名稱（例如：2025年1月報告批次處理）
4. 輸入來源目錄路徑（例如：`C:\Documents\Reports` 或 `\\server\shared\documents`）
5. 點擊「創建任務」

系統會自動掃描指定目錄下的所有 PDF 文件並記錄到資料庫。

### 2. 配置第一階段（CLIP 匹配）

1. 在任務列表中點擊剛創建的任務
2. 點擊「配置第一階段」按鈕
3. 上傳正例範本圖片（必填）：選擇您想要匹配的頁面範本
4. 上傳反例範本圖片（可選）：選擇您想要排除的頁面範本
5. 調整相似度閾值：
   - **正例閾值**（預設 0.25）：匹配頁面與正例的最低相似度
   - **反例閾值**（預設 0.30）：匹配頁面與反例的最高相似度
6. 點擊「保存配置並開始處理」

系統會自動開始處理所有 PDF 文件，從每個 PDF 中找出最相似的頁面。

### 3. 監控第一階段進度

- 在任務卡片上可以看到實時進度
- 統計資訊顯示：
  - 總檔案數
  - 第一階段完成數
  - 平均匹配分數
- 可以使用「暫停」或「停止」按鈕控制處理

### 4. 配置第二階段（OCR 識別）

當第一階段完成後：

1. 點擊「配置第二階段」按鈕
2. 輸入需要提取的關鍵字：
   - 在輸入框中輸入關鍵字
   - 按 Enter 鍵添加
   - 可以添加多個關鍵字
3. 選擇 OCR 處理選項：
   - 文檔方向分類
   - 文檔展平
   - 文字行方向檢測
   - 印章識別
   - 表格識別（預設勾選）
   - 使用 LLM 提取關鍵字（預設勾選）
4. 點擊「保存配置並開始處理」

系統會對第一階段匹配的頁面執行 OCR 識別並提取關鍵字。

### 5. 匯出結果

當第二階段完成後：

1. 點擊「匯出 Excel」按鈕
2. 系統會自動生成 Excel 文件並下載

Excel 文件包含以下欄位：
- 檔案名稱
- 檔案路徑
- 狀態
- 匹配頁面
- 匹配分數
- 提取的關鍵字（動態欄位，根據配置）
- 處理時間
- 錯誤訊息（如果有）

## 資料庫架構

### 批次任務表 (batch_tasks)
- `task_id`: 任務 ID
- `task_name`: 任務名稱
- `source_path`: 來源目錄路徑
- `status`: 任務狀態
- `stage`: 當前階段
- `progress`: 進度百分比
- `total_files`: 總檔案數
- `processed_files`: 已處理檔案數
- `stage1_config`: 第一階段配置（JSON）
- `stage2_config`: 第二階段配置（JSON）

### 檔案清單表 (batch_files)
- `id`: 檔案 ID
- `task_id`: 所屬任務 ID
- `file_path`: 檔案完整路徑
- `file_name`: 檔案名稱
- `stage1_status`: 第一階段狀態
- `stage2_status`: 第二階段狀態
- `matched_page_number`: 匹配的頁碼
- `matched_page_base64`: 匹配頁面的 Base64 圖像
- `matching_score`: 匹配分數
- `ocr_result`: OCR 結果（JSON）
- `extracted_keywords`: 提取的關鍵字（JSON）

### 任務關鍵字表 (task_keywords)
- `id`: 關鍵字 ID
- `task_id`: 所屬任務 ID
- `keyword_name`: 關鍵字名稱
- `keyword_order`: 關鍵字順序

## API 端點

### 任務管理
- `POST /api/batch-tasks/create` - 創建新任務
- `GET /api/batch-tasks` - 獲取所有任務
- `GET /api/batch-tasks/{task_id}` - 獲取任務詳情
- `DELETE /api/batch-tasks/{task_id}` - 刪除任務

### 配置管理
- `POST /api/batch-tasks/{task_id}/stage1/config` - 配置第一階段
- `POST /api/batch-tasks/{task_id}/stage2/config` - 配置第二階段

### 任務控制
- `POST /api/batch-tasks/{task_id}/stage1/start` - 開始第一階段
- `POST /api/batch-tasks/{task_id}/stage2/start` - 開始第二階段
- `POST /api/batch-tasks/{task_id}/pause` - 暫停任務
- `POST /api/batch-tasks/{task_id}/resume` - 恢復任務
- `POST /api/batch-tasks/{task_id}/stop` - 停止任務
- `POST /api/batch-tasks/{task_id}/stage1/restart` - 重新執行第一階段
- `POST /api/batch-tasks/{task_id}/stage2/restart` - 重新執行第二階段

### 結果匯出
- `GET /api/batch-tasks/{task_id}/export` - 匯出為 Excel

## 注意事項

1. **路徑格式**
   - Windows: `C:\path\to\folder` 或 `\\\\server\\share\\folder`
   - Linux/Mac: `/path/to/folder`

2. **檔案類型**
   - 目前僅支援 PDF 檔案
   - 可以在 `batch_processor.py` 中修改 `allowed_extensions` 參數以支援其他格式

3. **效能建議**
   - 建議每個任務處理的檔案數量不超過 1000 個
   - 大量檔案可以分成多個任務處理
   - 批次大小預設為 5，可在 `batch_processor.py` 中調整

4. **資料庫**
   - 批次任務資料儲存在 `batch_tasks.db`
   - 定期備份資料庫以防資料遺失

5. **磁碟空間**
   - 匹配的頁面圖片以 Base64 格式儲存在資料庫中
   - 大量任務會佔用較多磁碟空間
   - 完成的任務可以匯出後刪除以釋放空間

## 故障排除

### 任務一直停留在 "處理中" 狀態
- 檢查 CLIP 服務是否正常運行（port 8081）
- 檢查 PaddleOCR 服務日誌是否有錯誤
- 嘗試停止任務後重新啟動

### 匹配結果不理想
- 調整正例/反例相似度閾值
- 使用更多或更清晰的範本圖片
- 檢查 PDF 文件品質

### OCR 識別錯誤
- 檢查匹配的頁面是否正確
- 調整 OCR 參數（方向分類、展平等）
- 確認 LLM 服務（Ollama）是否正常運行

### Excel 匯出失敗
- 確認已安裝 openpyxl 套件
- 檢查是否有關鍵字配置
- 查看服務日誌獲取詳細錯誤資訊

## 技術架構

### 檔案結構
```
web-PaddleOCR/
├── task_database.py          # 批次任務資料庫模組
├── batch_processor.py         # 批次處理邏輯
├── app.py                     # FastAPI 主應用（包含批次任務 API）
├── templates/
│   └── batch_tasks.html      # 批次任務管理介面
├── batch_tasks.db            # 批次任務資料庫
└── temp_ocr/                 # 臨時 OCR 檔案目錄
```

### 處理流程
```
創建任務 → 掃描檔案 → 配置第一階段 → CLIP 匹配 → 配置第二階段 → OCR 識別 → 匯出結果
```

### 多執行緒處理
- 每個任務使用獨立的執行緒處理
- 支援多個任務同時執行
- 使用控制信號實現暫停/停止功能

## 未來改進

- [ ] 支援更多檔案格式（JPG, PNG 等）
- [ ] 添加任務優先級設定
- [ ] 實現分散式處理以提高效能
- [ ] 添加更詳細的處理日誌
- [ ] 支援自訂匯出格式（CSV, JSON 等）
- [ ] 添加任務排程功能（定時執行）
- [ ] 實現結果預覽功能（顯示匹配圖片和 OCR 結果）

## 授權

本批次任務管理系統為 PaddleOCR Web Interface 的一部分，遵循與主項目相同的授權協議。
