#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
測試 Excel 匯出功能的效能
"""

import time
import task_database as batch_db

def test_export_query_performance(task_id: str):
    """
    測試匯出查詢效能

    Args:
        task_id: 要測試的任務ID
    """
    print(f"\n{'='*60}")
    print(f"測試任務 ID: {task_id}")
    print(f"{'='*60}\n")

    # 取得任務資訊
    task = batch_db.get_task_by_id(task_id)
    if not task:
        print("❌ 任務不存在")
        return

    print(f"任務名稱: {task['task_name']}")
    print(f"總檔案數: {task['total_files']}")
    print()

    # 測試1: 舊方法 - 包含 ocr_result
    print("📊 測試 1: 包含 OCR 原始結果 (舊方法)")
    batch_size = 100
    offset = 0
    total_rows = 0

    start_time = time.time()
    iteration_times = []

    while True:
        iter_start = time.time()

        files = batch_db.get_task_files(
            task_id,
            limit=batch_size,
            offset=offset,
            exclude_base64=True,
            exclude_ocr_result=False  # 舊方法:包含 OCR 原始結果
        )

        iter_time = time.time() - iter_start
        iteration_times.append(iter_time)

        if not files:
            break

        total_rows += len(files)
        offset += batch_size

        print(f"  批次 {offset//batch_size}: {len(files)} 筆資料, 耗時 {iter_time:.3f} 秒")

        if len(files) < batch_size:
            break

    old_total_time = time.time() - start_time
    old_avg_time = sum(iteration_times) / len(iteration_times) if iteration_times else 0

    print(f"\n舊方法統計:")
    print(f"  總資料筆數: {total_rows}")
    print(f"  總耗時: {old_total_time:.3f} 秒")
    print(f"  平均每批耗時: {old_avg_time:.3f} 秒")
    print(f"  處理速度: {total_rows/old_total_time:.1f} 筆/秒")
    print()

    # 測試2: 新方法 - 排除 ocr_result
    print("📊 測試 2: 排除 OCR 原始結果 (新方法)")
    offset = 0
    total_rows = 0

    start_time = time.time()
    iteration_times = []

    while True:
        iter_start = time.time()

        files = batch_db.get_task_files(
            task_id,
            limit=batch_size,
            offset=offset,
            exclude_base64=True,
            exclude_ocr_result=True  # 新方法:排除 OCR 原始結果
        )

        iter_time = time.time() - iter_start
        iteration_times.append(iter_time)

        if not files:
            break

        total_rows += len(files)
        offset += batch_size

        print(f"  批次 {offset//batch_size}: {len(files)} 筆資料, 耗時 {iter_time:.3f} 秒")

        if len(files) < batch_size:
            break

    new_total_time = time.time() - start_time
    new_avg_time = sum(iteration_times) / len(iteration_times) if iteration_times else 0

    print(f"\n新方法統計:")
    print(f"  總資料筆數: {total_rows}")
    print(f"  總耗時: {new_total_time:.3f} 秒")
    print(f"  平均每批耗時: {new_avg_time:.3f} 秒")
    print(f"  處理速度: {total_rows/new_total_time:.1f} 筆/秒")
    print()

    # 效能對比
    print(f"{'='*60}")
    print("📈 效能對比結果:")
    print(f"{'='*60}")
    speedup = old_total_time / new_total_time if new_total_time > 0 else 0
    time_saved = old_total_time - new_total_time
    improvement = ((old_total_time - new_total_time) / old_total_time * 100) if old_total_time > 0 else 0

    print(f"  舊方法總耗時: {old_total_time:.3f} 秒")
    print(f"  新方法總耗時: {new_total_time:.3f} 秒")
    print(f"  節省時間: {time_saved:.3f} 秒")
    print(f"  效能提升: {improvement:.1f}%")
    print(f"  加速倍數: {speedup:.2f}x")
    print()

    if improvement > 50:
        print("✅ 優化效果顯著!")
    elif improvement > 20:
        print("✅ 優化效果良好")
    else:
        print("⚠️  優化效果有限")
    print()


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("使用方式: python test_export_performance.py <task_id>")
        print("\n可用的任務:")
        tasks = batch_db.get_all_tasks()
        for task in tasks[:5]:
            print(f"  - {task['task_id']}: {task['task_name']} ({task['total_files']} 個檔案)")
        sys.exit(1)

    task_id = sys.argv[1]
    test_export_query_performance(task_id)
