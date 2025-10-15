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
    """獲取線程本地的資料庫連接"""
    if not hasattr(_local, 'conn'):
        _local.conn = sqlite3.connect('D:\\web-PaddleOCR\\batch_tasks.db', check_same_thread=False)
        _local.conn.row_factory = sqlite3.Row
    return _local.conn

def init_database():
    """初始化批次任務資料庫"""
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

    conn.commit()
    print("批次任務資料庫初始化完成")

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
    """更新任務進度"""
    conn = get_connection()
    cursor = conn.cursor()

    # 計算進度
    cursor.execute('''
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN stage2_status = 'completed' THEN 1 ELSE 0 END) as completed,
            SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed
        FROM batch_files
        WHERE task_id = ?
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
                   offset: int = 0) -> List[Dict]:
    """取得任務的檔案列表"""
    conn = get_connection()
    cursor = conn.cursor()

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
    """取得任務統計資訊"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT
            COUNT(*) as total_files,
            SUM(CASE WHEN stage1_status = 'completed' THEN 1 ELSE 0 END) as stage1_completed,
            SUM(CASE WHEN stage1_status = 'failed' THEN 1 ELSE 0 END) as stage1_failed,
            SUM(CASE WHEN stage1_status = 'pending' THEN 1 ELSE 0 END) as stage1_pending,
            SUM(CASE WHEN stage2_status = 'completed' THEN 1 ELSE 0 END) as stage2_completed,
            SUM(CASE WHEN stage2_status = 'failed' THEN 1 ELSE 0 END) as stage2_failed,
            SUM(CASE WHEN stage2_status = 'pending' THEN 1 ELSE 0 END) as stage2_pending,
            AVG(matching_score) as avg_matching_score
        FROM batch_files
        WHERE task_id = ?
    ''', (task_id,))

    row = cursor.fetchone()
    return dict(row) if row else {}

if __name__ == "__main__":
    init_database()
