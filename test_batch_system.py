#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批次任務系統測試腳本
"""

import task_database as db

def test_database_initialization():
    """測試資料庫初始化"""
    print("=" * 50)
    print("測試 1: 資料庫初始化")
    print("=" * 50)

    try:
        db.init_database()
        print("✅ 資料庫初始化成功")
        return True
    except Exception as e:
        print(f"❌ 資料庫初始化失敗: {e}")
        return False

def test_create_task():
    """測試創建任務"""
    print("\n" + "=" * 50)
    print("測試 2: 創建任務")
    print("=" * 50)

    try:
        task_id = "test-task-001"
        task_name = "測試任務"
        source_path = "C:\\test"

        success = db.create_batch_task(task_id, task_name, source_path)

        if success:
            print(f"✅ 任務創建成功: {task_id}")

            # 驗證任務
            task = db.get_task_by_id(task_id)
            if task:
                print(f"   - 任務名稱: {task['task_name']}")
                print(f"   - 來源路徑: {task['source_path']}")
                print(f"   - 狀態: {task['status']}")
                return True
            else:
                print("❌ 無法讀取創建的任務")
                return False
        else:
            print("❌ 任務創建失敗")
            return False

    except Exception as e:
        print(f"❌ 測試失敗: {e}")
        return False

def test_add_files():
    """測試添加檔案"""
    print("\n" + "=" * 50)
    print("測試 3: 添加檔案到任務")
    print("=" * 50)

    try:
        task_id = "test-task-001"
        files = [
            {
                'file_path': 'C:\\test\\file1.pdf',
                'file_name': 'file1.pdf',
                'file_size': 1024,
                'file_type': '.pdf'
            },
            {
                'file_path': 'C:\\test\\file2.pdf',
                'file_name': 'file2.pdf',
                'file_size': 2048,
                'file_type': '.pdf'
            }
        ]

        count = db.add_files_to_task(task_id, files)

        if count > 0:
            print(f"✅ 成功添加 {count} 個檔案")

            # 驗證檔案
            task_files = db.get_task_files(task_id)
            print(f"   - 任務中的檔案數量: {len(task_files)}")
            for f in task_files:
                print(f"   - {f['file_name']}: {f['stage1_status']}")
            return True
        else:
            print("❌ 添加檔案失敗")
            return False

    except Exception as e:
        print(f"❌ 測試失敗: {e}")
        return False

def test_save_configs():
    """測試保存配置"""
    print("\n" + "=" * 50)
    print("測試 4: 保存階段配置")
    print("=" * 50)

    try:
        task_id = "test-task-001"

        # 保存第一階段配置
        stage1_config = {
            'positive_templates': ['base64_data_1', 'base64_data_2'],
            'negative_templates': [],
            'positive_threshold': 0.25,
            'negative_threshold': 0.30
        }
        db.save_task_stage1_config(task_id, stage1_config)
        print("✅ 第一階段配置保存成功")

        # 保存第二階段配置
        stage2_config = {
            'use_doc_orientation_classify': False,
            'use_table_recognition': True,
            'use_llm': True
        }
        keywords = ['關鍵字1', '關鍵字2', '關鍵字3']
        db.save_task_stage2_config(task_id, stage2_config, keywords)
        print("✅ 第二階段配置保存成功")

        # 驗證配置
        saved_keywords = db.get_task_keywords(task_id)
        print(f"   - 保存的關鍵字: {saved_keywords}")

        return True

    except Exception as e:
        print(f"❌ 測試失敗: {e}")
        return False

def test_update_progress():
    """測試更新進度"""
    print("\n" + "=" * 50)
    print("測試 5: 更新任務狀態和進度")
    print("=" * 50)

    try:
        task_id = "test-task-001"

        # 更新任務狀態
        db.update_task_status(task_id, 'running', stage=1)
        print("✅ 任務狀態更新為 running")

        # 模擬檔案處理完成
        files = db.get_task_files(task_id)
        if files:
            # 更新第一個檔案的第一階段結果
            db.update_file_stage1_result(
                files[0]['id'],
                matched_page_number=5,
                matched_page_base64='base64_image_data',
                matching_score=0.85,
                status='completed'
            )
            print(f"✅ 檔案 {files[0]['file_name']} 第一階段處理完成")

            # 更新進度
            db.update_task_progress(task_id)

            # 查看任務狀態
            task = db.get_task_by_id(task_id)
            print(f"   - 任務進度: {task['progress']:.1f}%")
            print(f"   - 已處理: {task['processed_files']}/{task['total_files']}")

        return True

    except Exception as e:
        print(f"❌ 測試失敗: {e}")
        return False

def test_statistics():
    """測試統計功能"""
    print("\n" + "=" * 50)
    print("測試 6: 獲取任務統計")
    print("=" * 50)

    try:
        task_id = "test-task-001"

        stats = db.get_task_statistics(task_id)

        print("✅ 統計資訊:")
        print(f"   - 總檔案數: {stats['total_files']}")
        print(f"   - 第一階段完成: {stats['stage1_completed']}")
        print(f"   - 第二階段完成: {stats['stage2_completed']}")
        print(f"   - 平均匹配分數: {stats['avg_matching_score']:.2f}" if stats['avg_matching_score'] else "   - 平均匹配分數: N/A")

        return True

    except Exception as e:
        print(f"❌ 測試失敗: {e}")
        return False

def cleanup_test_data():
    """清理測試資料"""
    print("\n" + "=" * 50)
    print("清理測試資料")
    print("=" * 50)

    try:
        task_id = "test-task-001"
        db.mark_task_deleted(task_id)
        print("✅ 測試資料已清理")
        return True
    except Exception as e:
        print(f"❌ 清理失敗: {e}")
        return False

def main():
    """執行所有測試"""
    print("\n" + "🧪" * 25)
    print("批次任務系統測試")
    print("🧪" * 25 + "\n")

    results = []

    # 執行測試
    results.append(("資料庫初始化", test_database_initialization()))
    results.append(("創建任務", test_create_task()))
    results.append(("添加檔案", test_add_files()))
    results.append(("保存配置", test_save_configs()))
    results.append(("更新進度", test_update_progress()))
    results.append(("獲取統計", test_statistics()))
    results.append(("清理測試資料", cleanup_test_data()))

    # 顯示測試結果摘要
    print("\n" + "=" * 50)
    print("測試結果摘要")
    print("=" * 50)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")

    print("\n" + "=" * 50)
    print(f"通過: {passed}/{total}")
    print("=" * 50)

    if passed == total:
        print("\n🎉 所有測試通過！")
        return 0
    else:
        print(f"\n⚠️ {total - passed} 個測試失敗")
        return 1

if __name__ == "__main__":
    exit(main())
