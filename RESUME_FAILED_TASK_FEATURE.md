# 批次任務恢復執行功能

## 功能概述

當批次任務在處理過程中因錯誤而失敗時(例如執行到 1200/3000 時中斷),現在可以從失敗點繼續執行,而不需要重新處理所有檔案。

## 使用場景

### 典型場景
```
任務狀態: 共 3000 個檔案
- 已完成: 1200 個
- 已失敗: 50 個
- 待處理: 1750 個
- 任務狀態: failed

使用「從失敗點繼續執行」後:
- 1200 個已完成的檔案不會重新處理
- 50 個已失敗的檔案不會重新處理
- 只處理剩餘的 1750 個待處理檔案
```

## 核心機制

### 1. 資料庫層 (task_database.py)

#### `reset_task_status_for_resume(task_id, stage)`
```python
def reset_task_status_for_resume(task_id: str, stage: int):
    """
    重置任務狀態以便繼續執行(從中斷點繼續)

    - 只重置任務本身的狀態為 'running'
    - 不修改任何檔案的狀態
    - 處理器會自動跳過 completed 和 failed 的檔案
    """
```

**關鍵點**: 不會修改 `batch_files` 表中的任何資料,只更新 `batch_tasks` 表的狀態。

### 2. 處理器層 (batch_processor.py)

#### `resume_task_from_failure(task_id, clip_service_url)`
```python
def resume_task_from_failure(task_id: str, clip_service_url: str):
    """
    從失敗點繼續執行任務

    步驟:
    1. 檢查任務狀態 (必須是 'failed' 或 'stopped')
    2. 獲取當前階段
    3. 計算待處理檔案數量
    4. 重置任務狀態
    5. 根據階段調用對應的 start_task_stage1/2
    """
```

**工作原理**:
- 現有的 `process_task_stage1_worker` 和 `process_task_stage2_worker` 已經設計為批次處理
- 它們會調用 `get_pending_files_for_stage1/2` 來獲取 `status='pending'` 的檔案
- 因此不需要修改處理邏輯,只需重置任務狀態即可

### 3. API 層 (app.py)

#### `POST /api/batch-tasks/{task_id}/resume`
```python
@app.post("/api/batch-tasks/{task_id}/resume")
async def resume_failed_task(task_id: str):
    """
    從失敗點繼續執行任務

    返回:
    - success: 是否成功
    - message: 詳細信息
    - stage: 當前階段
    - statistics: 任務統計資訊
    """
```

### 4. 前端層 (batch_tasks.html)

#### UI 變更
當任務狀態為 `failed` 時,顯示兩個按鈕:
1. **🔄 從失敗點繼續執行** - 調用 `resumeFailedTask()`
2. **🔁 從頭重新開始** - 調用 `restartFromBeginning()`

#### JavaScript 函數
```javascript
async function resumeFailedTask() {
    // 1. 獲取任務統計資訊
    // 2. 顯示確認對話框(包含已完成/失敗/待處理的數量)
    // 3. 調用 /api/batch-tasks/{task_id}/resume
    // 4. 刷新任務列表
}
```

## 檔案狀態流程

### 檔案狀態定義
```
pending -> 待處理
completed -> 已完成(不會重新處理)
failed -> 已失敗(不會重新處理)
```

### 第一階段處理流程
```
1. get_pending_files_for_stage1(task_id, limit=5)
   -> 只返回 stage1_status='pending' 的檔案

2. process_file_stage1(file_info, config, clip_url)
   -> 處理單個檔案

3. update_file_stage1_result(file_id, ..., status='completed'/'failed')
   -> 更新檔案狀態
```

### 第二階段處理流程
```
1. get_pending_files_for_stage2(task_id, limit=5)
   -> 只返回 stage1_status='completed' 且 stage2_status='pending' 的檔案

2. process_file_stage2(file_info, page_base64, config, keywords)
   -> 處理單個檔案

3. update_file_stage2_result(file_id, ..., status='completed'/'failed')
   -> 更新檔案狀態
```

## 與現有功能的區別

### 功能對比表

| 功能 | 按鈕名稱 | 適用狀態 | 檔案處理行為 |
|------|---------|---------|------------|
| **繼續執行** | 從失敗點繼續執行 | failed, stopped | 只處理 pending 檔案 |
| **暫停/恢復** | 暫停/恢復 | running, paused | 只處理 pending 檔案 |
| **重新執行** | 重新執行第一/二階段 | 任何狀態 | 重置並重新處理所有檔案 |

### 使用建議

1. **任務中途失敗** (例如執行到 1200/3000)
   - ✅ 使用「從失敗點繼續執行」
   - ❌ 不要使用「重新執行」(會浪費已處理的 1200 個檔案)

2. **參數設定錯誤** (例如閾值太低)
   - ❌ 不要使用「從失敗點繼續執行」(會繼承錯誤參數)
   - ✅ 使用「重新執行」並調整參數

3. **臨時網路中斷**
   - ✅ 使用「從失敗點繼續執行」

4. **系統維護需要暫停**
   - ✅ 使用「暫停」,維護完成後「恢復」

## 錯誤處理

### 前端驗證
```javascript
// 確認對話框會顯示:
- 當前階段
- 已完成數量
- 已失敗數量
- 待處理數量
```

### 後端驗證
```python
# batch_processor.py
if task['status'] not in ['failed', 'stopped']:
    raise Exception("只有失敗或已停止的任務才能繼續執行")

if pending_count == 0:
    print("沒有待處理的檔案,任務已完成")
    return
```

### 日誌輸出
```
任務 xxx 準備從第 1 階段繼續執行
第一階段: 已完成 1200, 已失敗 50, 待處理 1750
任務 xxx 狀態已重置,準備從第 1 階段繼續執行
已從第一階段繼續執行,將處理剩餘的 1750 個檔案
```

## 測試場景

### 測試步驟

1. **創建測試任務**
   ```
   - 準備 100 個 PDF 檔案
   - 配置第一階段並開始處理
   ```

2. **模擬中途失敗**
   ```
   - 等待處理約 30 個檔案後
   - 停止 CLIP 服務模擬失敗
   - 任務狀態變為 'failed'
   ```

3. **測試繼續執行**
   ```
   - 重啟 CLIP 服務
   - 點擊「從失敗點繼續執行」
   - 觀察是否從第 31 個檔案開始處理
   ```

4. **驗證結果**
   ```
   - 檢查前 30 個檔案未被重新處理
   - 檢查剩餘 70 個檔案正常處理
   - 檢查總統計數字正確
   ```

### 預期結果

| 檢查項目 | 預期值 |
|---------|--------|
| 已完成數量 | 100 個(包含恢復前的 30 個) |
| 處理時間 | 只花費 70 個檔案的時間 |
| 資料庫狀態 | stage1_completed=100 |
| 前 30 個檔案的 processed_at | 保持原始時間戳 |
| 後 70 個檔案的 processed_at | 新的時間戳 |

## 技術限制

### 1. 不會重新處理失敗的檔案
- 設計理念: 失敗的檔案可能有真實的問題(例如檔案損壞)
- 解決方案: 需要手動修復檔案後使用「重新執行」

### 2. 不會更新已完成檔案的結果
- 設計理念: 避免修改已確認的結果
- 解決方案: 如需更新參數,使用「重新執行」

### 3. 只支持 failed 和 stopped 狀態
- 其他狀態(running, paused, completed)有各自的控制按鈕
- failed 和 stopped 狀態才需要「繼續執行」功能

## 程式碼檔案清單

| 檔案 | 修改內容 | 行數 |
|------|---------|------|
| [task_database.py](task_database.py:480-506) | 新增 `reset_task_status_for_resume()` | 27 行 |
| [batch_processor.py](batch_processor.py:496-560) | 新增 `resume_task_from_failure()` | 65 行 |
| [app.py](app.py:828-868) | 新增 `/api/batch-tasks/{task_id}/resume` 端點 | 41 行 |
| [batch_tasks.html](templates/batch_tasks.html:825-827) | 修改 `renderActionButtons()` 新增按鈕 | 3 行 |
| [batch_tasks.html](templates/batch_tasks.html:1169-1234) | 新增 `resumeFailedTask()` 和 `restartFromBeginning()` | 66 行 |

## 總結

此功能透過以下機制實現:
1. **不修改檔案狀態** - 保留所有已處理檔案的狀態和結果
2. **只重置任務狀態** - 將任務從 'failed' 改為 'running'
3. **利用現有處理邏輯** - 處理器本就設計為批次處理 pending 檔案
4. **提供清晰的 UI** - 用戶可以明確知道會處理多少檔案

這樣設計的優點:
- ✅ 節省處理時間(不重複處理)
- ✅ 保留已有結果(不覆蓋)
- ✅ 程式碼改動最小(重用現有邏輯)
- ✅ 使用者體驗好(清楚知道會發生什麼)
