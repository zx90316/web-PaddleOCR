#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批次處理完整測試腳本
測試從檔案掃描到結果匯出的完整流程
"""

import sys
import os
from pathlib import Path
import base64

# 設定輸出編碼為 UTF-8
if sys.platform == "win32":
    import codecs
    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter("utf-8")(sys.stderr.buffer, 'strict')

import task_database as batch_db
import batch_processor
import uuid

def print_header(title):
    """打印標題"""
    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)

def test_file_scanning():
    """測試檔案掃描功能"""
    print_header("測試 1: 檔案掃描功能")

    test_dir = Path("files")
    if not test_dir.exists():
        print("❌ 測試資料夾不存在，請先執行 generate_test_data.py")
        return False

    try:
        files = batch_processor.scan_directory(str(test_dir.absolute()))
        print(f"✅ 成功掃描 {len(files)} 個 PDF 檔案")

        # 顯示資料夾分布
        folders = {}
        for f in files:
            folder = str(Path(f['file_path']).parent)
            folders[folder] = folders.get(folder, 0) + 1

        print(f"\n資料夾分布:")
        for folder, count in sorted(folders.items()):
            print(f"  📁 {folder}: {count} 個檔案")

        return len(files) > 0

    except Exception as e:
        print(f"❌ 掃描失敗: {e}")
        return False

def test_task_creation():
    """測試任務創建和檔案添加"""
    print_header("測試 2: 任務創建和檔案添加")

    try:
        # 初始化資料庫
        batch_db.init_database()
        print("✅ 資料庫初始化成功")

        # 創建任務
        task_id = f"test-{uuid.uuid4()}"
        task_name = "批次處理測試任務"
        source_path = str(Path("files").absolute())

        batch_db.create_batch_task(task_id, task_name, source_path)
        print(f"✅ 任務創建成功: {task_id}")

        # 掃描並添加檔案
        files = batch_processor.scan_directory(source_path)
        count = batch_db.add_files_to_task(task_id, files)
        print(f"✅ 成功添加 {count} 個檔案到任務")

        # 驗證
        task = batch_db.get_task_by_id(task_id)
        print(f"\n任務資訊:")
        print(f"  - 任務名稱: {task['task_name']}")
        print(f"  - 來源路徑: {task['source_path']}")
        print(f"  - 總檔案數: {task['total_files']}")
        print(f"  - 狀態: {task['status']}")

        return task_id

    except Exception as e:
        print(f"❌ 測試失敗: {e}")
        import traceback
        traceback.print_exc()
        return None

def test_stage1_config(task_id):
    """測試第一階段配置"""
    print_header("測試 3: 第一階段配置")

    try:
        # 讀取目標頁面圖片並轉為 Base64
        target_image_path = Path("positive_images.png")
        if not target_image_path.exists():
            print("❌ 找不到目標頁面圖片")
            return False

        with open(target_image_path, 'rb') as f:
            img_base64 = base64.b64encode(f.read()).decode('utf-8')

        # 保存配置
        config = {
            'positive_templates': [img_base64],
            'negative_templates': [],
            'positive_threshold': 0.25,
            'negative_threshold': 0.30
        }

        batch_db.save_task_stage1_config(task_id, config)
        print("✅ 第一階段配置已保存")

        # 驗證
        task = batch_db.get_task_by_id(task_id)
        if task['stage1_config']:
            print("✅ 配置驗證成功")
            return True
        else:
            print("❌ 配置驗證失敗")
            return False

    except Exception as e:
        print(f"❌ 測試失敗: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_stage2_config(task_id):
    """測試第二階段配置"""
    print_header("測試 4: 第二階段配置")

    try:
        # 保存配置
        config = {
            'use_doc_orientation_classify': False,
            'use_doc_unwarping': False,
            'use_textline_orientation': False,
            'use_seal_recognition': False,
            'use_table_recognition': True,
            'use_llm': True
        }

        keywords = ['製作日期', '報告編號', '申請者名稱', '申請者地址', '廠牌']

        batch_db.save_task_stage2_config(task_id, config, keywords)
        print("✅ 第二階段配置已保存")

        # 驗證
        saved_keywords = batch_db.get_task_keywords(task_id)
        print(f"✅ 保存的關鍵字: {saved_keywords}")

        return True

    except Exception as e:
        print(f"❌ 測試失敗: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_statistics(task_id):
    """測試統計功能"""
    print_header("測試 5: 統計資訊")

    try:
        stats = batch_db.get_task_statistics(task_id)

        print("📊 任務統計:")
        print(f"  - 總檔案數: {stats['total_files']}")
        print(f"  - 第一階段待處理: {stats['stage1_pending']}")
        print(f"  - 第一階段已完成: {stats['stage1_completed']}")
        print(f"  - 第一階段失敗: {stats['stage1_failed']}")
        print(f"  - 第二階段待處理: {stats['stage2_pending']}")
        print(f"  - 第二階段已完成: {stats['stage2_completed']}")
        print(f"  - 第二階段失敗: {stats['stage2_failed']}")

        return True

    except Exception as e:
        print(f"❌ 測試失敗: {e}")
        return False

def test_file_queries(task_id):
    """測試檔案查詢功能"""
    print_header("測試 6: 檔案查詢")

    try:
        # 查詢所有檔案
        all_files = batch_db.get_task_files(task_id)
        print(f"✅ 總共 {len(all_files)} 個檔案")

        # 查詢待處理的第一階段檔案
        pending_stage1 = batch_db.get_pending_files_for_stage1(task_id, limit=5)
        print(f"✅ 第一階段待處理: {len(pending_stage1)} 個 (顯示前 5 個)")

        for f in pending_stage1[:3]:
            print(f"  - {f['file_name']}: {f['stage1_status']}")

        return True

    except Exception as e:
        print(f"❌ 測試失敗: {e}")
        return False

def display_test_summary(task_id):
    """顯示測試摘要"""
    print_header("測試摘要")

    try:
        task = batch_db.get_task_by_id(task_id)
        stats = batch_db.get_task_statistics(task_id)
        keywords = batch_db.get_task_keywords(task_id)

        print("✅ 所有基礎測試通過！")
        print(f"\n任務 ID: {task_id}")
        print(f"任務名稱: {task['task_name']}")
        print(f"來源路徑: {task['source_path']}")
        print(f"總檔案數: {task['total_files']}")
        print(f"關鍵字: {', '.join(keywords)}")

        print("\n" + "=" * 60)
        print("下一步：測試實際處理")
        print("=" * 60)
        print("\n⚠️ 注意：實際處理測試需要 CLIP 服務和 PaddleOCR 服務運行")
        print("\n如要測試實際處理，請:")
        print("1. 確保兩個服務都在運行")
        print("2. 訪問 http://localhost:8080/batch-tasks")
        print(f"3. 找到任務 ID: {task_id}")
        print("4. 點擊「開始第一階段」按鈕")
        print("5. 等待處理完成後，點擊「開始第二階段」")
        print("6. 最後點擊「匯出 Excel」")

        print("\n或者使用以下 API 測試:")
        print(f"  POST http://localhost:8080/api/batch-tasks/{task_id}/stage1/start")
        print(f"  POST http://localhost:8080/api/batch-tasks/{task_id}/stage2/start")
        print(f"  GET  http://localhost:8080/api/batch-tasks/{task_id}/export")

    except Exception as e:
        print(f"❌ 顯示摘要失敗: {e}")

def main():
    """執行所有測試"""
    print("\n" + "🧪" * 30)
    print("批次處理完整測試")
    print("🧪" * 30)

    # 測試 1: 檔案掃描
    if not test_file_scanning():
        print("\n❌ 檔案掃描測試失敗，終止測試")
        return 1

    # 測試 2: 任務創建
    task_id = test_task_creation()
    if not task_id:
        print("\n❌ 任務創建測試失敗，終止測試")
        return 1

    # 測試 3: 第一階段配置
    if not test_stage1_config(task_id):
        print("\n❌ 第一階段配置測試失敗，終止測試")
        return 1

    # 測試 4: 第二階段配置
    if not test_stage2_config(task_id):
        print("\n❌ 第二階段配置測試失敗，終止測試")
        return 1

    # 測試 5: 統計功能
    if not test_statistics(task_id):
        print("\n❌ 統計功能測試失敗")

    # 測試 6: 檔案查詢
    if not test_file_queries(task_id):
        print("\n❌ 檔案查詢測試失敗")

    # 顯示測試摘要
    display_test_summary(task_id)

    return 0

if __name__ == "__main__":
    exit(main())
