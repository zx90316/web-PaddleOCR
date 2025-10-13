#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
資料庫管理模組
負責處理 OCR 任務的資料庫操作
"""

import sqlite3
import json
from typing import List, Dict, Optional
from datetime import datetime
from contextlib import contextmanager

DB_PATH = "ocr_tasks.db"


@contextmanager
def get_db_connection():
    """資料庫連線上下文管理器"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_database():
    """初始化資料庫"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ocr_tasks (
                task_id TEXT PRIMARY KEY,
                original_filename TEXT,
                created_at TEXT,
                output_directory TEXT,
                response_file TEXT,
                is_deleted INTEGER DEFAULT 0,
                file_type TEXT,
                matched_page_number INTEGER,
                settings TEXT
            )
        ''')
        conn.commit()


def insert_task(
    task_id: str,
    original_filename: str,
    output_directory: str,
    response_file: str,
    file_type: str,
    matched_page_number: Optional[int],
    settings: dict
):
    """
    插入新任務記錄
    Args:
        task_id: 任務唯一識別碼
        original_filename: 原始檔案名稱
        output_directory: 輸出目錄路徑
        response_file: 回應 JSON 檔案路徑
        file_type: 檔案類型 (image/pdf)
        matched_page_number: 匹配的頁碼 (可選)
        settings: 設定資訊 (dict)
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO ocr_tasks
            (task_id, original_filename, created_at, output_directory,
             response_file, file_type, matched_page_number, settings)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            task_id,
            original_filename,
            datetime.now().isoformat(),
            output_directory,
            response_file,
            file_type,
            matched_page_number,
            json.dumps(settings, ensure_ascii=False)
        ))
        conn.commit()


def get_all_tasks(include_deleted: bool = False) -> List[Dict]:
    """
    取得所有任務記錄
    Args:
        include_deleted: 是否包含已刪除的任務
    Returns:
        任務列表
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if include_deleted:
            cursor.execute('SELECT * FROM ocr_tasks ORDER BY created_at DESC')
        else:
            cursor.execute('SELECT * FROM ocr_tasks WHERE is_deleted = 0 ORDER BY created_at DESC')

        rows = cursor.fetchall()
        tasks = []
        for row in rows:
            task = dict(row)
            if task['settings']:
                task['settings'] = json.loads(task['settings'])
            tasks.append(task)
        return tasks


def get_task_by_id(task_id: str) -> Optional[Dict]:
    """
    根據任務 ID 取得任務記錄
    Args:
        task_id: 任務唯一識別碼
    Returns:
        任務資訊 dict 或 None
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM ocr_tasks WHERE task_id = ?', (task_id,))
        row = cursor.fetchone()
        if row:
            task = dict(row)
            if task['settings']:
                task['settings'] = json.loads(task['settings'])
            return task
        return None


def mark_task_deleted(task_id: str):
    """
    標記任務為已刪除
    Args:
        task_id: 任務唯一識別碼
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            'UPDATE ocr_tasks SET is_deleted = 1 WHERE task_id = ?',
            (task_id,)
        )
        conn.commit()


def delete_task_permanently(task_id: str):
    """
    永久刪除任務記錄
    Args:
        task_id: 任務唯一識別碼
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM ocr_tasks WHERE task_id = ?', (task_id,))
        conn.commit()
