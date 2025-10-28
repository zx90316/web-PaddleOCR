#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批次任務資料庫管理模組
"""

import sqlite3
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
import threading

# 線程安全的資料庫連接
_local = threading.local()

def get_connection():
    """
    獲取線程本地的資料庫連接

    優化重點:
    - 啟用 WAL 模式以提升並發讀寫效能 (允許同時讀寫)
    - 設定適當的 timeout 避免 "database is locked" 錯誤
    - 優化快取和同步設定以提升效能
    """
    if not hasattr(_local, 'conn'):
        _local.conn = sqlite3.connect(
<<<<<<< HEAD
            'V:\\行政服務部\\協同作業\\資訊\\內部\\99.其它\\batch_tasks.db',
=======
            'batch_tasks.db',
>>>>>>> bcf65d000bb021e40a78ab43cc2c1cbfbc26a120
            check_same_thread=False,
            timeout=30.0  # 增加 timeout 到 30 秒避免鎖定錯誤
        )
        _local.conn.row_factory = sqlite3.Row

        # 啟用 WAL 模式 - 這是關鍵優化!
        # WAL 允許多個讀取者同時與一個寫入者工作,大幅減少鎖定問題
        _local.conn.execute('PRAGMA journal_mode=WAL')

        # 優化設定
        _local.conn.execute('PRAGMA synchronous=NORMAL')  # 平衡效能和安全性
        _local.conn.execute('PRAGMA cache_size=-64000')  # 64MB 快取
        _local.conn.execute('PRAGMA temp_store=MEMORY')  # 臨時資料存在記憶體
        _local.conn.execute('PRAGMA busy_timeout=30000')  # 30 秒忙碌 timeout

    return _local.conn

def init_database():
    """
    初始化批次任務資料庫

    優化重點:
    - 建立覆蓋索引以加速統計查詢
    - 複合索引支援多條件查詢
    """
    conn = get_connection()
    cursor = conn.cursor()

    # 批次任務表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS batch_tasks (
            task_id TEXT PRIMARY KEY,
            task_name TEXT NOT NULL,
            source_path TEXT NOT NULL,
            status TEXT NOT NULL,
            stage INTEGER DEFAULT 0,
            progress REAL DEFAULT 0.0,
            total_files INTEGER DEFAULT 0,
            processed_files INTEGER DEFAULT 0,
            failed_files INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            started_at TEXT,
            updated_at TEXT,
            completed_at TEXT,
            estimated_completion TEXT,
            stage1_config TEXT,
            stage2_config TEXT,
            error_message TEXT,
            is_deleted INTEGER DEFAULT 0
        )
    ''')

    # 檔案清單表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS batch_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_name TEXT NOT NULL,
            file_size INTEGER,
            file_type TEXT,
            status TEXT DEFAULT 'pending',
            stage1_status TEXT DEFAULT 'pending',
            stage2_status TEXT DEFAULT 'pending',
            stage1_result TEXT,
            stage2_result TEXT,
            matched_page_number INTEGER,
            matched_page_base64 TEXT,
            matching_score REAL,
            ocr_result TEXT,
            extracted_keywords TEXT,
            error_message TEXT,
            processed_at TEXT,
            FOREIGN KEY (task_id) REFERENCES batch_tasks(task_id)
        )
    ''')

    # 任務關鍵字表（動態關鍵字）
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS task_keywords (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT NOT NULL,
            keyword_name TEXT NOT NULL,
            keyword_order INTEGER NOT NULL,
            FOREIGN KEY (task_id) REFERENCES batch_tasks(task_id),
            UNIQUE(task_id, keyword_name)
        )
    ''')

    # 創建索引
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_batch_files_task_id ON batch_files(task_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_batch_files_status ON batch_files(status)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_batch_tasks_status ON batch_tasks(status)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_task_keywords_task_id ON task_keywords(task_id)')

    # 複合索引優化 - 加速統計查詢和狀態篩選
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_batch_files_task_stage1 ON batch_files(task_id, stage1_status)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_batch_files_task_stage2 ON batch_files(task_id, stage2_status)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_batch_files_task_stages ON batch_files(task_id, stage1_status, stage2_status)')

    # 覆蓋索引優化 - 包含統計所需的欄位,避免回表查詢
    cursor.execute('''CREATE INDEX IF NOT EXISTS idx_batch_files_stats_covering
                      ON batch_files(task_id, stage1_status, stage2_status, matching_score)''')

    conn.commit()

    print("批次任務資料庫初始化完成")
    print("已啟用 WAL 模式以提升並發效能")

def create_batch_task(task_id: str, task_name: str, source_path: str) -> bool:
    """創建新的批次任務"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO batch_tasks (
                task_id, task_name, source_path, status, created_at, updated_at
            ) VALUES (?, ?, ?, 'created', ?, ?)
        ''', (task_id, task_name, source_path, datetime.now().isoformat(), datetime.now().isoformat()))

        conn.commit()
        return True
    except Exception as e:
        print(f"創建批次任務失敗: {e}")
        return False

def add_files_to_task(task_id: str, files: List[Dict[str, Any]]) -> int:
    """批次新增檔案到任務"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        file_data = [
            (task_id, f['file_path'], f['file_name'], f.get('file_size'), f.get('file_type'))
            for f in files
        ]

        cursor.executemany('''
            INSERT INTO batch_files (task_id, file_path, file_name, file_size, file_type)
            VALUES (?, ?, ?, ?, ?)
        ''', file_data)

        # 更新任務的總檔案數
        cursor.execute('''
            UPDATE batch_tasks
            SET total_files = (SELECT COUNT(*) FROM batch_files WHERE task_id = ?),
                updated_at = ?
            WHERE task_id = ?
        ''', (task_id, datetime.now().isoformat(), task_id))

        conn.commit()
        return len(files)
    except Exception as e:
        print(f"新增檔案到任務失敗: {e}")
        return 0

def update_task_status(task_id: str, status: str, stage: Optional[int] = None,
                       error_message: Optional[str] = None):
    """更新任務狀態"""
    conn = get_connection()
    cursor = conn.cursor()

    updates = ['status = ?', 'updated_at = ?']
    params = [status, datetime.now().isoformat()]

    if stage is not None:
        updates.append('stage = ?')
        params.append(stage)

    if error_message:
        updates.append('error_message = ?')
        params.append(error_message)

    if status == 'running' and stage == 1:
        updates.append('started_at = ?')
        params.append(datetime.now().isoformat())

    if status == 'completed':
        updates.append('completed_at = ?')
        params.append(datetime.now().isoformat())

    params.append(task_id)

    cursor.execute(f'''
        UPDATE batch_tasks
        SET {', '.join(updates)}
        WHERE task_id = ?
    ''', params)

    conn.commit()

def update_task_progress(task_id: str):
    """
    更新任務進度

    優化重點:
    - 只查詢必要的狀態欄位,避免讀取 Base64 和其他大型欄位
    - 使用子查詢明確指定欄位
    """
    conn = get_connection()
    cursor = conn.cursor()

    # 只選擇狀態欄位進行計算,避免讀取 Base64 等大型欄位
    cursor.execute('''
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN stage2_status = 'completed' THEN 1 ELSE 0 END) as completed,
            SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed
        FROM (
            SELECT stage2_status, status
            FROM batch_files
            WHERE task_id = ?
        )
    ''', (task_id,))

    row = cursor.fetchone()
    total = row['total']
    completed = row['completed']
    failed = row['failed']

    progress = (completed / total * 100) if total > 0 else 0

    cursor.execute('''
        UPDATE batch_tasks
        SET progress = ?,
            processed_files = ?,
            failed_files = ?,
            updated_at = ?
        WHERE task_id = ?
    ''', (progress, completed, failed, datetime.now().isoformat(), task_id))

    conn.commit()

def update_file_stage1_result(file_id: int, matched_page_number: Optional[int],
                               matched_page_base64: Optional[str], matching_score: Optional[float],
                               status: str = 'completed', error_message: Optional[str] = None):
    """更新檔案第一階段結果"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        UPDATE batch_files
        SET stage1_status = ?,
            matched_page_number = ?,
            matched_page_base64 = ?,
            matching_score = ?,
            error_message = ?,
            processed_at = ?
        WHERE id = ?
    ''', (status, matched_page_number, matched_page_base64, matching_score,
          error_message, datetime.now().isoformat(), file_id))

    conn.commit()

def update_file_stage2_result(file_id: int, ocr_result: str, extracted_keywords: str,
                               status: str = 'completed', error_message: Optional[str] = None):
    """更新檔案第二階段結果"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        UPDATE batch_files
        SET stage2_status = ?,
            ocr_result = ?,
            extracted_keywords = ?,
            status = ?,
            error_message = ?,
            processed_at = ?
        WHERE id = ?
    ''', (status, ocr_result, extracted_keywords, status,
          error_message, datetime.now().isoformat(), file_id))

    conn.commit()

def get_task_by_id(task_id: str) -> Optional[Dict]:
    """根據 ID 取得任務"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT * FROM batch_tasks
        WHERE task_id = ? AND is_deleted = 0
    ''', (task_id,))

    row = cursor.fetchone()
    return dict(row) if row else None

def get_all_tasks(include_deleted: bool = False) -> List[Dict]:
    """取得所有任務"""
    conn = get_connection()
    cursor = conn.cursor()

    if include_deleted:
        cursor.execute('SELECT * FROM batch_tasks ORDER BY created_at DESC')
    else:
        cursor.execute('SELECT * FROM batch_tasks WHERE is_deleted = 0 ORDER BY created_at DESC')

    return [dict(row) for row in cursor.fetchall()]

def get_task_files(task_id: str, status: Optional[str] = None,
                   stage1_status: Optional[str] = None,
                   stage2_status: Optional[str] = None,
                   limit: Optional[int] = None,
                   offset: int = 0,
                   exclude_base64: bool = True) -> List[Dict]:
    """
    取得任務的檔案列表

    Args:
        task_id: 任務ID
        status: 篩選狀態
        stage1_status: 第一階段狀態
        stage2_status: 第二階段狀態
        limit: 限制數量
        offset: 偏移量
        exclude_base64: 是否排除 Base64 圖片資料(預設True以節省記憶體)
    """
    conn = get_connection()
    cursor = conn.cursor()

    # 選擇性排除 Base64 欄位以節省記憶體
    if exclude_base64:
        query = '''SELECT id, task_id, file_path, file_name, file_size, file_type,
                   status, stage1_status, stage2_status, stage1_result, stage2_result,
                   matched_page_number, NULL as matched_page_base64, matching_score,
                   ocr_result, extracted_keywords, error_message, processed_at
                   FROM batch_files WHERE task_id = ?'''
    else:
        query = 'SELECT * FROM batch_files WHERE task_id = ?'

    params = [task_id]

    if status:
        query += ' AND status = ?'
        params.append(status)

    if stage1_status:
        query += ' AND stage1_status = ?'
        params.append(stage1_status)

    if stage2_status:
        query += ' AND stage2_status = ?'
        params.append(stage2_status)

    query += ' ORDER BY id'

    if limit:
        query += ' LIMIT ? OFFSET ?'
        params.extend([limit, offset])

    cursor.execute(query, params)
    return [dict(row) for row in cursor.fetchall()]

def get_pending_files_for_stage1(task_id: str, limit: int = 10) -> List[Dict]:
    """取得待處理的第一階段檔案"""
    return get_task_files(task_id, stage1_status='pending', limit=limit)

def get_pending_files_for_stage2(task_id: str, limit: int = 10) -> List[Dict]:
    """取得待處理的第二階段檔案"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT * FROM batch_files
        WHERE task_id = ?
        AND stage1_status = 'completed'
        AND stage2_status = 'pending'
        ORDER BY id
        LIMIT ?
    ''', (task_id, limit))

    return [dict(row) for row in cursor.fetchall()]

def save_task_stage1_config(task_id: str, config: Dict):
    """保存第一階段配置"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        UPDATE batch_tasks
        SET stage1_config = ?,
            updated_at = ?
        WHERE task_id = ?
    ''', (json.dumps(config, ensure_ascii=False), datetime.now().isoformat(), task_id))

    conn.commit()

def save_task_stage2_config(task_id: str, config: Dict, keywords: List[str]):
    """保存第二階段配置和關鍵字"""
    conn = get_connection()
    cursor = conn.cursor()

    # 保存配置
    cursor.execute('''
        UPDATE batch_tasks
        SET stage2_config = ?,
            updated_at = ?
        WHERE task_id = ?
    ''', (json.dumps(config, ensure_ascii=False), datetime.now().isoformat(), task_id))

    # 刪除舊的關鍵字
    cursor.execute('DELETE FROM task_keywords WHERE task_id = ?', (task_id,))

    # 插入新的關鍵字
    for idx, keyword in enumerate(keywords):
        cursor.execute('''
            INSERT INTO task_keywords (task_id, keyword_name, keyword_order)
            VALUES (?, ?, ?)
        ''', (task_id, keyword, idx))

    conn.commit()

def get_task_keywords(task_id: str) -> List[str]:
    """取得任務的關鍵字列表"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT keyword_name
        FROM task_keywords
        WHERE task_id = ?
        ORDER BY keyword_order
    ''', (task_id,))

    return [row['keyword_name'] for row in cursor.fetchall()]

def mark_task_deleted(task_id: str):
    """標記任務為已刪除"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        UPDATE batch_tasks
        SET is_deleted = 1,
            updated_at = ?
        WHERE task_id = ?
    ''', (datetime.now().isoformat(), task_id))

    conn.commit()

def get_task_statistics(task_id: str) -> Dict:
    """
    取得任務統計資訊

    優化重點:
    - 明確指定所需欄位,避免讀取 matched_page_base64 欄位
    - 減少 I/O 和記憶體使用
    """
    conn = get_connection()
    cursor = conn.cursor()

    # 只選擇統計所需的欄位,明確排除 Base64 圖片欄位
    cursor.execute('''
        SELECT
            COUNT(*) as total_files,
            SUM(CASE WHEN stage1_status = 'completed' THEN 1 ELSE 0 END) as stage1_completed,
            SUM(CASE WHEN stage1_status = 'failed' THEN 1 ELSE 0 END) as stage1_failed,
            SUM(CASE WHEN stage1_status = 'pending' THEN 1 ELSE 0 END) as stage1_pending,
            SUM(CASE WHEN stage2_status = 'completed' THEN 1 ELSE 0 END) as stage2_completed,
            SUM(CASE WHEN stage2_status = 'failed' THEN 1 ELSE 0 END) as stage2_failed,
            SUM(CASE WHEN stage2_status = 'pending' THEN 1 ELSE 0 END) as stage2_pending,
            AVG(CASE WHEN matching_score IS NOT NULL THEN matching_score ELSE NULL END) as avg_matching_score
        FROM (
            SELECT stage1_status, stage2_status, matching_score
            FROM batch_files
            WHERE task_id = ?
        )
    ''', (task_id,))

    row = cursor.fetchone()
    return dict(row) if row else {}

def get_task_files_count(task_id: str, status: Optional[str] = None,
                         stage1_status: Optional[str] = None,
                         stage2_status: Optional[str] = None) -> int:
    """
    取得任務的檔案數量(不載入資料,僅計數)

    Args:
        task_id: 任務ID
        status: 篩選狀態
        stage1_status: 第一階段狀態
        stage2_status: 第二階段狀態

    Returns:
        符合條件的檔案數量
    """
    conn = get_connection()
    cursor = conn.cursor()

    query = 'SELECT COUNT(*) as count FROM batch_files WHERE task_id = ?'
    params = [task_id]

    if status:
        query += ' AND status = ?'
        params.append(status)

    if stage1_status:
        query += ' AND stage1_status = ?'
        params.append(stage1_status)

    if stage2_status:
        query += ' AND stage2_status = ?'
        params.append(stage2_status)

    cursor.execute(query, params)
    row = cursor.fetchone()
    return row['count'] if row else 0

def reset_task_status_for_resume(task_id: str, stage: int):
    """
    重置任務狀態以便繼續執行(從中斷點繼續)

    此函數不會重置已完成或已失敗的檔案,只重置任務本身的狀態
    讓處理器可以繼續處理 pending 狀態的檔案

    Args:
        task_id: 任務ID
        stage: 要繼續的階段 (1 或 2)
    """
    conn = get_connection()
    cursor = conn.cursor()

    # 只重置任務狀態,不動檔案狀態
    # 處理器會自動跳過 completed 和 failed 的檔案,只處理 pending 的
    cursor.execute('''
        UPDATE batch_tasks
        SET status = 'running',
            stage = ?,
            error_message = NULL,
            updated_at = ?
        WHERE task_id = ?
    ''', (stage, datetime.now().isoformat(), task_id))

    conn.commit()
    print(f"任務 {task_id} 狀態已重置,準備從第 {stage} 階段繼續執行")

def vacuum_database():
    """
    清理資料庫並重建索引

    建議在以下情況執行:
    - 刪除大量資料後
    - 資料庫變得很慢
    - 定期維護 (例如每月一次)

    注意: VACUUM 需要暫時使用額外的磁碟空間
    """
    conn = get_connection()
    print("開始清理資料庫...")
    conn.execute('VACUUM')
    print("資料庫清理完成")

def analyze_database():
    """
    分析資料庫並更新統計資訊

    這有助於查詢優化器選擇更好的執行計劃
    建議定期執行 (例如每週一次)
    """
    conn = get_connection()
    print("開始分析資料庫...")
    conn.execute('ANALYZE')
    print("資料庫分析完成")

def checkpoint_wal():
    """
    執行 WAL checkpoint

    將 WAL 檔案的變更合併回主資料庫檔案
    有助於控制 WAL 檔案大小
    """
    conn = get_connection()
    print("執行 WAL checkpoint...")
    conn.execute('PRAGMA wal_checkpoint(TRUNCATE)')
    print("WAL checkpoint 完成")

def get_database_stats():
    """
    取得資料庫統計資訊

    Returns:
        Dict: 包含資料庫大小、表格資訊等
    """
    conn = get_connection()
    cursor = conn.cursor()

    stats = {}

    # 資料庫檔案大小
    cursor.execute("PRAGMA page_count")
    page_count = cursor.fetchone()[0]
    cursor.execute("PRAGMA page_size")
    page_size = cursor.fetchone()[0]
    stats['database_size_mb'] = (page_count * page_size) / (1024 * 1024)

    # WAL 模式狀態
    cursor.execute("PRAGMA journal_mode")
    stats['journal_mode'] = cursor.fetchone()[0]

    # 各表格的記錄數
    cursor.execute("SELECT COUNT(*) FROM batch_tasks")
    stats['total_tasks'] = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM batch_files")
    stats['total_files'] = cursor.fetchone()[0]

    # Base64 欄位佔用估計
    cursor.execute("""
        SELECT
            COUNT(*) as files_with_images,
            SUM(LENGTH(matched_page_base64)) as total_base64_size
        FROM batch_files
        WHERE matched_page_base64 IS NOT NULL
    """)
    row = cursor.fetchone()
    stats['files_with_images'] = row[0] if row[0] else 0
    stats['base64_size_mb'] = (row[1] / (1024 * 1024)) if row[1] else 0

    return stats

if __name__ == "__main__":
    init_database()
    print("\n資料庫統計:")
    stats = get_database_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")
