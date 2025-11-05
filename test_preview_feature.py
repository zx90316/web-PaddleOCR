#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
測試處理狀態查看功能
"""

import sys
import requests
import json

# 設定輸出編碼為 UTF-8
if sys.platform == "win32":
    import codecs
    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter("utf-8")(sys.stderr.buffer, 'strict')

BASE_URL = "http://localhost:8080"
# 請求超時時間（秒）
REQUEST_TIMEOUT = 30

def test_api_endpoints(task_id):
    """測試所有新增的 API 端點"""
    print("=" * 60)
    print("測試處理狀態查看 API 端點")
    print("=" * 60)

    # 測試 1: 取得任務預覽
    print("\n[測試 1] 取得任務預覽")
    try:
        response = requests.get(f"{BASE_URL}/api/batch-tasks/{task_id}/preview?limit=5", timeout=REQUEST_TIMEOUT)
        data = response.json()

        if data.get('success'):
            files = data.get('files', [])
            print(f"✅ 成功取得 {len(files)} 個檔案預覽")

            if files:
                print("\n前 3 個檔案:")
                for f in files[:3]:
                    print(f"  - {f['file_name']}")
                    print(f"    匹配頁面: 第 {f['matched_page_number']} 頁")
                    print(f"    匹配分數: {f['matching_score']:.4f}")
                    print(f"    有圖片: {'是' if f['has_image'] else '否'}")

                # 測試取得單個檔案詳情
                test_file_id = files[0]['id']
                print(f"\n[測試 2] 取得檔案詳情 (ID: {test_file_id})")

                response = requests.get(f"{BASE_URL}/api/batch-tasks/{task_id}/files/{test_file_id}", timeout=REQUEST_TIMEOUT)
                data = response.json()

                if data.get('success'):
                    file_info = data['file']
                    print(f"✅ 成功取得檔案詳情")
                    print(f"  - 檔案名稱: {file_info['file_name']}")
                    print(f"  - 檔案路徑: {file_info['file_path']}")
                    print(f"  - 第一階段狀態: {file_info['stage1_status']}")
                    print(f"  - 第二階段狀態: {file_info['stage2_status']}")

                    if file_info.get('extracted_keywords'):
                        keywords = file_info['extracted_keywords']
                        if isinstance(keywords, str):
                            keywords = json.loads(keywords)

                        print(f"  - 提取的關鍵字:")
                        for key, value in keywords.items():
                            print(f"    • {key}: {value}")

                # 測試取得圖片
                print(f"\n[測試 3] 取得匹配頁面圖片 (ID: {test_file_id})")

                response = requests.get(f"{BASE_URL}/api/batch-tasks/{task_id}/files/{test_file_id}/image", timeout=REQUEST_TIMEOUT)

                if response.status_code == 200:
                    print(f"✅ 成功取得圖片")
                    print(f"  - 圖片大小: {len(response.content)} bytes")
                    print(f"  - Content-Type: {response.headers.get('Content-Type')}")

                    # 可選：保存圖片到本地
                    output_path = f"test_image_{test_file_id}.png"
                    with open(output_path, 'wb') as f:
                        f.write(response.content)
                    print(f"  - 已保存到: {output_path}")
                else:
                    print(f"❌ 取得圖片失敗: {response.text}")

            else:
                print("⚠️ 沒有已完成的檔案可供預覽")
                print("請先執行第一階段處理")

        else:
            print(f"❌ 取得預覽失敗: {data.get('error')}")

    except Exception as e:
        print(f"❌ 測試失敗: {e}")
        import traceback
        traceback.print_exc()

    # 測試 4: 取得所有檔案列表
    print(f"\n[測試 4] 取得所有檔案列表")
    try:
        response = requests.get(f"{BASE_URL}/api/batch-tasks/{task_id}/files?limit=10", timeout=REQUEST_TIMEOUT)
        data = response.json()

        if data.get('success'):
            files = data.get('files', [])
            print(f"✅ 成功取得 {len(files)} 個檔案")

            # 統計各狀態的數量
            stage1_stats = {}
            stage2_stats = {}

            for f in files:
                s1 = f['stage1_status']
                s2 = f['stage2_status']
                stage1_stats[s1] = stage1_stats.get(s1, 0) + 1
                stage2_stats[s2] = stage2_stats.get(s2, 0) + 1

            print("\n第一階段狀態統計:")
            for status, count in stage1_stats.items():
                print(f"  - {status}: {count} 個")

            print("\n第二階段狀態統計:")
            for status, count in stage2_stats.items():
                print(f"  - {status}: {count} 個")

        else:
            print(f"❌ 取得檔案列表失敗: {data.get('error')}")

    except Exception as e:
        print(f"❌ 測試失敗: {e}")

    print("\n" + "=" * 60)
    print("測試完成")
    print("=" * 60)

    print("\n下一步:")
    print(f"1. 訪問任務詳情頁面: {BASE_URL}/batch-tasks/{task_id}/detail")
    print(f"2. 或訪問任務列表: {BASE_URL}/batch-tasks")
    print("3. 點擊「查看詳情」按鈕查看圖片預覽")

def list_tasks():
    """列出所有任務"""
    print("=" * 60)
    print("可用的任務列表")
    print("=" * 60)

    try:
        response = requests.get(f"{BASE_URL}/api/batch-tasks", timeout=REQUEST_TIMEOUT)
        data = response.json()

        if data.get('success'):
            tasks = data.get('tasks', [])

            if not tasks:
                print("⚠️ 目前沒有任務")
                print("請先創建一個批次任務")
                return None

            print(f"\n找到 {len(tasks)} 個任務:\n")

            for idx, task in enumerate(tasks, 1):
                print(f"{idx}. {task['task_name']}")
                print(f"   ID: {task['task_id']}")
                print(f"   狀態: {task['status']}")
                print(f"   總檔案數: {task['total_files']}")
                print(f"   已處理: {task['processed_files']}")
                print(f"   進度: {task['progress']:.1f}%")
                print()

            # 選擇有處理結果的任務
            suitable_task = None
            for task in tasks:
                if task['processed_files'] > 0:
                    suitable_task = task
                    break

            if suitable_task:
                return suitable_task['task_id']
            else:
                return tasks[0]['task_id']

        else:
            print(f"❌ 取得任務列表失敗: {data.get('error')}")
            return None

    except Exception as e:
        print(f"❌ 連接失敗: {e}")
        print("\n請確認:")
        print("1. PaddleOCR 服務正在運行 (port 8080)")
        print("2. 使用 python app.py 或 python start_services.py 啟動服務")
        return None

def main():
    """主函數"""
    print("\n" + "🧪" * 30)
    print("處理狀態查看功能測試")
    print("🧪" * 30 + "\n")

    # 列出所有任務並選擇一個
    task_id = list_tasks()

    if not task_id:
        return 1

    print("\n選擇的任務 ID:", task_id)

    # 詢問是否繼續
    try:
        response = input("\n是否測試此任務的 API 端點? (y/n): ")
        if response.lower() != 'y':
            print("測試已取消")
            return 0
    except:
        print("\n自動繼續測試...")

    # 測試 API 端點
    test_api_endpoints(task_id)

    return 0

if __name__ == "__main__":
    exit(main())
