"""
資料保存期限管理模組
自動清理超過保存期限的任務資料
"""

import os
import sqlite3
import shutil
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import json

# 配置
LOG_FILE = "logs/data_retention.log"
RETENTION_POLICY_FILE = "data_retention_policy.json"

# 預設保存期限（天）
DEFAULT_RETENTION_DAYS = {
    'ocr_tasks': 1825,  # 5年
    'batch_tasks': 1825,  # 5年
    'logs': 90,  # 90天
    'temp_files': 1  # 1天
}

# 設定日誌
os.makedirs("logs", exist_ok=True)
retention_logger = logging.getLogger("data_retention")
retention_logger.setLevel(logging.INFO)

file_handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
file_handler.setFormatter(logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
))
retention_logger.addHandler(file_handler)

console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
retention_logger.addHandler(console_handler)


class RetentionPolicy:
    """資料保存政策"""

    def __init__(self, policy_file: str = RETENTION_POLICY_FILE):
        """
        初始化保存政策

        Args:
            policy_file: 政策配置檔案路徑
        """
        self.policy_file = policy_file
        self.policies = self._load_policies()

    def _load_policies(self) -> Dict[str, int]:
        """載入保存政策"""
        if os.path.exists(self.policy_file):
            try:
                with open(self.policy_file, 'r', encoding='utf-8') as f:
                    policies = json.load(f)
                retention_logger.info(f"已載入保存政策: {self.policy_file}")
                return policies
            except Exception as e:
                retention_logger.error(f"載入保存政策失敗: {e}")

        retention_logger.info("使用預設保存政策")
        return DEFAULT_RETENTION_DAYS.copy()

    def save_policies(self):
        """儲存保存政策到檔案"""
        try:
            with open(self.policy_file, 'w', encoding='utf-8') as f:
                json.dump(self.policies, f, indent=2, ensure_ascii=False)
            retention_logger.info(f"保存政策已儲存: {self.policy_file}")
        except Exception as e:
            retention_logger.error(f"儲存保存政策失敗: {e}")

    def get_retention_days(self, category: str) -> int:
        """
        取得指定類別的保存天數

        Args:
            category: 類別名稱

        Returns:
            保存天數
        """
        return self.policies.get(category, DEFAULT_RETENTION_DAYS.get(category, 365))

    def set_retention_days(self, category: str, days: int):
        """
        設定指定類別的保存天數

        Args:
            category: 類別名稱
            days: 保存天數
        """
        self.policies[category] = days
        retention_logger.info(f"設定保存政策: {category} = {days} 天")

    def get_expiry_date(self, category: str) -> datetime:
        """
        取得指定類別的過期日期

        Args:
            category: 類別名稱

        Returns:
            過期日期
        """
        retention_days = self.get_retention_days(category)
        return datetime.now() - timedelta(days=retention_days)


class DataCleanupManager:
    """資料清理管理器"""

    def __init__(self, policy: Optional[RetentionPolicy] = None, dry_run: bool = False):
        """
        初始化清理管理器

        Args:
            policy: 保存政策
            dry_run: 是否為模擬運行（不實際刪除）
        """
        self.policy = policy or RetentionPolicy()
        self.dry_run = dry_run

        self.ocr_db = "ocr_tasks.db"
        self.batch_db = "batch_tasks.db"

        if self.dry_run:
            retention_logger.info("===== 模擬運行模式 (不會實際刪除資料) =====")

    def cleanup_ocr_tasks(self) -> Dict[str, any]:
        """
        清理過期的 OCR 任務

        Returns:
            清理結果統計
        """
        retention_logger.info("開始清理 OCR 任務...")

        expiry_date = self.policy.get_expiry_date('ocr_tasks')
        retention_logger.info(f"OCR 任務保存期限: {self.policy.get_retention_days('ocr_tasks')} 天")
        retention_logger.info(f"刪除 {expiry_date.strftime('%Y-%m-%d %H:%M:%S')} 之前的任務")

        result = {
            'deleted_count': 0,
            'freed_space': 0,
            'errors': []
        }

        try:
            if not os.path.exists(self.ocr_db):
                retention_logger.warning(f"資料庫不存在: {self.ocr_db}")
                return result

            conn = sqlite3.connect(self.ocr_db)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # 查詢過期任務
            cursor.execute('''
                SELECT task_id, output_directory, created_at
                FROM tasks
                WHERE created_at < ?
                AND is_deleted = 0
            ''', (expiry_date.isoformat(),))

            expired_tasks = cursor.fetchall()

            retention_logger.info(f"找到 {len(expired_tasks)} 個過期的 OCR 任務")

            for task in expired_tasks:
                task_id = task['task_id']
                output_dir = task['output_directory']
                created_at = task['created_at']

                try:
                    # 計算目錄大小
                    dir_size = 0
                    if os.path.exists(output_dir):
                        for dirpath, dirnames, filenames in os.walk(output_dir):
                            for filename in filenames:
                                filepath = os.path.join(dirpath, filename)
                                if os.path.exists(filepath):
                                    dir_size += os.path.getsize(filepath)

                    retention_logger.info(f"刪除任務: {task_id}, 建立時間: {created_at}, 大小: {dir_size / (1024*1024):.2f} MB")

                    if not self.dry_run:
                        # 刪除檔案
                        if os.path.exists(output_dir):
                            shutil.rmtree(output_dir)

                        # 標記為已刪除
                        cursor.execute('''
                            UPDATE tasks
                            SET is_deleted = 1, deleted_at = ?
                            WHERE task_id = ?
                        ''', (datetime.now().isoformat(), task_id))

                    result['deleted_count'] += 1
                    result['freed_space'] += dir_size

                except Exception as e:
                    error_msg = f"刪除任務失敗 {task_id}: {str(e)}"
                    retention_logger.error(error_msg)
                    result['errors'].append(error_msg)

            if not self.dry_run:
                conn.commit()

            conn.close()

            retention_logger.info(f"OCR 任務清理完成: 刪除 {result['deleted_count']} 個任務, 釋放 {result['freed_space'] / (1024*1024):.2f} MB")

        except Exception as e:
            error_msg = f"清理 OCR 任務時發生錯誤: {str(e)}"
            retention_logger.error(error_msg)
            result['errors'].append(error_msg)

        return result

    def cleanup_batch_tasks(self) -> Dict[str, any]:
        """
        清理過期的批次任務

        Returns:
            清理結果統計
        """
        retention_logger.info("開始清理批次任務...")

        expiry_date = self.policy.get_expiry_date('batch_tasks')
        retention_logger.info(f"批次任務保存期限: {self.policy.get_retention_days('batch_tasks')} 天")
        retention_logger.info(f"刪除 {expiry_date.strftime('%Y-%m-%d %H:%M:%S')} 之前的任務")

        result = {
            'deleted_count': 0,
            'freed_space': 0,
            'errors': []
        }

        try:
            if not os.path.exists(self.batch_db):
                retention_logger.warning(f"資料庫不存在: {self.batch_db}")
                return result

            conn = sqlite3.connect(self.batch_db)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # 查詢過期任務
            cursor.execute('''
                SELECT task_id, task_name, created_at
                FROM batch_tasks
                WHERE created_at < ?
                AND is_deleted = 0
            ''', (expiry_date.isoformat(),))

            expired_tasks = cursor.fetchall()

            retention_logger.info(f"找到 {len(expired_tasks)} 個過期的批次任務")

            for task in expired_tasks:
                task_id = task['task_id']
                task_name = task['task_name']
                created_at = task['created_at']

                try:
                    # 計算資料庫中 Base64 圖片的大小
                    cursor.execute('''
                        SELECT SUM(LENGTH(matched_page_base64)) as total_size
                        FROM batch_files
                        WHERE task_id = ?
                    ''', (task_id,))

                    row = cursor.fetchone()
                    data_size = row['total_size'] or 0

                    retention_logger.info(f"刪除批次任務: {task_id} ({task_name}), 建立時間: {created_at}, 大小: {data_size / (1024*1024):.2f} MB")

                    if not self.dry_run:
                        # 刪除相關檔案記錄
                        cursor.execute('''
                            DELETE FROM batch_files
                            WHERE task_id = ?
                        ''', (task_id,))

                        # 刪除關鍵字
                        cursor.execute('''
                            DELETE FROM batch_keywords
                            WHERE task_id = ?
                        ''', (task_id,))

                        # 標記任務為已刪除
                        cursor.execute('''
                            UPDATE batch_tasks
                            SET is_deleted = 1, deleted_at = ?
                            WHERE task_id = ?
                        ''', (datetime.now().isoformat(), task_id))

                    result['deleted_count'] += 1
                    result['freed_space'] += data_size

                except Exception as e:
                    error_msg = f"刪除批次任務失敗 {task_id}: {str(e)}"
                    retention_logger.error(error_msg)
                    result['errors'].append(error_msg)

            if not self.dry_run:
                conn.commit()

            conn.close()

            retention_logger.info(f"批次任務清理完成: 刪除 {result['deleted_count']} 個任務, 釋放 {result['freed_space'] / (1024*1024):.2f} MB")

        except Exception as e:
            error_msg = f"清理批次任務時發生錯誤: {str(e)}"
            retention_logger.error(error_msg)
            result['errors'].append(error_msg)

        return result

    def cleanup_old_logs(self) -> Dict[str, any]:
        """
        清理過期的日誌檔案

        Returns:
            清理結果統計
        """
        retention_logger.info("開始清理日誌檔案...")

        expiry_date = self.policy.get_expiry_date('logs')
        retention_logger.info(f"日誌保存期限: {self.policy.get_retention_days('logs')} 天")
        retention_logger.info(f"刪除 {expiry_date.strftime('%Y-%m-%d %H:%M:%S')} 之前的日誌")

        result = {
            'deleted_count': 0,
            'freed_space': 0,
            'errors': []
        }

        try:
            log_dir = "logs"
            if not os.path.exists(log_dir):
                retention_logger.warning(f"日誌目錄不存在: {log_dir}")
                return result

            # 遍歷日誌檔案
            for filename in os.listdir(log_dir):
                filepath = os.path.join(log_dir, filename)

                # 跳過非檔案
                if not os.path.isfile(filepath):
                    continue

                # 跳過當前運行的日誌
                if filename in ['app.log', 'monitor.log', 'data_retention.log']:
                    continue

                # 檢查檔案修改時間
                mtime = datetime.fromtimestamp(os.path.getmtime(filepath))

                if mtime < expiry_date:
                    file_size = os.path.getsize(filepath)
                    retention_logger.info(f"刪除日誌: {filename}, 最後修改: {mtime.strftime('%Y-%m-%d')}, 大小: {file_size / 1024:.2f} KB")

                    if not self.dry_run:
                        try:
                            os.remove(filepath)
                            result['deleted_count'] += 1
                            result['freed_space'] += file_size
                        except Exception as e:
                            error_msg = f"刪除日誌檔案失敗 {filename}: {str(e)}"
                            retention_logger.error(error_msg)
                            result['errors'].append(error_msg)

            retention_logger.info(f"日誌清理完成: 刪除 {result['deleted_count']} 個檔案, 釋放 {result['freed_space'] / 1024:.2f} KB")

        except Exception as e:
            error_msg = f"清理日誌時發生錯誤: {str(e)}"
            retention_logger.error(error_msg)
            result['errors'].append(error_msg)

        return result

    def cleanup_temp_files(self) -> Dict[str, any]:
        """
        清理臨時檔案

        Returns:
            清理結果統計
        """
        retention_logger.info("開始清理臨時檔案...")

        expiry_date = self.policy.get_expiry_date('temp_files')
        retention_logger.info(f"臨時檔案保存期限: {self.policy.get_retention_days('temp_files')} 天")

        result = {
            'deleted_count': 0,
            'freed_space': 0,
            'errors': []
        }

        temp_dirs = ['temp_ocr']

        for temp_dir in temp_dirs:
            if not os.path.exists(temp_dir):
                continue

            try:
                for filename in os.listdir(temp_dir):
                    filepath = os.path.join(temp_dir, filename)

                    if not os.path.isfile(filepath):
                        continue

                    mtime = datetime.fromtimestamp(os.path.getmtime(filepath))

                    if mtime < expiry_date:
                        file_size = os.path.getsize(filepath)
                        retention_logger.info(f"刪除臨時檔案: {filepath}, 大小: {file_size / 1024:.2f} KB")

                        if not self.dry_run:
                            try:
                                os.remove(filepath)
                                result['deleted_count'] += 1
                                result['freed_space'] += file_size
                            except Exception as e:
                                error_msg = f"刪除臨時檔案失敗 {filepath}: {str(e)}"
                                retention_logger.error(error_msg)
                                result['errors'].append(error_msg)

            except Exception as e:
                error_msg = f"清理目錄時發生錯誤 {temp_dir}: {str(e)}"
                retention_logger.error(error_msg)
                result['errors'].append(error_msg)

        retention_logger.info(f"臨時檔案清理完成: 刪除 {result['deleted_count']} 個檔案, 釋放 {result['freed_space'] / 1024:.2f} KB")

        return result

    def cleanup_all(self) -> Dict[str, any]:
        """
        執行完整清理

        Returns:
            總清理結果
        """
        retention_logger.info("=" * 60)
        retention_logger.info("開始執行資料清理作業")
        retention_logger.info("=" * 60)

        results = {
            'ocr_tasks': self.cleanup_ocr_tasks(),
            'batch_tasks': self.cleanup_batch_tasks(),
            'logs': self.cleanup_old_logs(),
            'temp_files': self.cleanup_temp_files()
        }

        # 計算總計
        total_deleted = sum(r['deleted_count'] for r in results.values())
        total_freed = sum(r['freed_space'] for r in results.values())
        total_errors = sum(len(r['errors']) for r in results.values())

        retention_logger.info("=" * 60)
        retention_logger.info(f"資料清理完成")
        retention_logger.info(f"總刪除項目數: {total_deleted}")
        retention_logger.info(f"總釋放空間: {total_freed / (1024*1024):.2f} MB")
        retention_logger.info(f"錯誤數量: {total_errors}")
        retention_logger.info("=" * 60)

        return {
            'summary': {
                'total_deleted': total_deleted,
                'total_freed_mb': total_freed / (1024*1024),
                'total_errors': total_errors
            },
            'details': results
        }


def create_default_policy_file():
    """建立預設保存政策檔案"""
    policy = RetentionPolicy()
    policy.policies = DEFAULT_RETENTION_DAYS.copy()
    policy.save_policies()
    print(f"已建立預設保存政策檔案: {RETENTION_POLICY_FILE}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='資料保存期限管理工具')
    parser.add_argument('--dry-run', action='store_true', help='模擬運行（不實際刪除）')
    parser.add_argument('--create-policy', action='store_true', help='建立預設保存政策檔案')
    parser.add_argument('--ocr-only', action='store_true', help='僅清理 OCR 任務')
    parser.add_argument('--batch-only', action='store_true', help='僅清理批次任務')
    parser.add_argument('--logs-only', action='store_true', help='僅清理日誌')
    parser.add_argument('--temp-only', action='store_true', help='僅清理臨時檔案')

    args = parser.parse_args()

    # 建立政策檔案
    if args.create_policy:
        create_default_policy_file()
        exit(0)

    # 執行清理
    manager = DataCleanupManager(dry_run=args.dry_run)

    if args.ocr_only:
        result = manager.cleanup_ocr_tasks()
    elif args.batch_only:
        result = manager.cleanup_batch_tasks()
    elif args.logs_only:
        result = manager.cleanup_old_logs()
    elif args.temp_only:
        result = manager.cleanup_temp_files()
    else:
        result = manager.cleanup_all()

    # 輸出結果
    print("\n清理結果:")
    print(json.dumps(result, indent=2, ensure_ascii=False))
