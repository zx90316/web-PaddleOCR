#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
啟動 PaddleOCR 雙服務架構
同時啟動 CLIP 服務和 PaddleOCR 服務

安全說明:
此腳本用於啟動本地服務，subprocess 調用僅執行本地Python腳本（clip_service.py, app.py）
不接受外部輸入，因此是安全的。
"""

import subprocess  # nosec B404 - 服務啟動腳本，需要調用subprocess啟動Python服務
import sys
import os
import time
from pathlib import Path

def check_venv(venv_name):
    """檢查虛擬環境是否存在"""
    venv_path = Path(venv_name)
    if not venv_path.exists():
        return False

    # Windows
    if sys.platform == "win32":
        python_exe = venv_path / "Scripts" / "python.exe"
    # Linux/Mac
    else:
        python_exe = venv_path / "bin" / "python"

    return python_exe.exists()

def get_python_path(venv_name):
    """獲取虛擬環境的 Python 路徑"""
    venv_path = Path(venv_name)
    if sys.platform == "win32":
        return str(venv_path / "Scripts" / "python.exe")
    else:
        return str(venv_path / "bin" / "python")

def main():
    print("=" * 50)
    print("啟動 PaddleOCR 雙服務架構")
    print("=" * 50)
    print()

    # 檢查虛擬環境
    clip_venv = "venv_clip"
    paddle_venv = "venv_paddle"

    if not check_venv(clip_venv):
        print(f"[錯誤] 找不到 CLIP 服務虛擬環境 {clip_venv}")
        print(f"請先創建虛擬環境：python -m venv {clip_venv}")
        print(f"然後安裝依賴：")
        if sys.platform == "win32":
            print(f"  {clip_venv}\\Scripts\\activate")
        else:
            print(f"  source {clip_venv}/bin/activate")
        print(f"  pip install -r requirements_clip.txt")
        sys.exit(1)

    if not check_venv(paddle_venv):
        print(f"[錯誤] 找不到 PaddleOCR 服務虛擬環境 {paddle_venv}")
        print(f"請先創建虛擬環境：python -m venv {paddle_venv}")
        print(f"然後安裝依賴：")
        if sys.platform == "win32":
            print(f"  {paddle_venv}\\Scripts\\activate")
        else:
            print(f"  source {paddle_venv}/bin/activate")
        print(f"  pip install -r requirements_paddle.txt")
        sys.exit(1)

    # 啟動 CLIP 服務
    print("[1/2] 啟動 CLIP 圖像匹配服務 (Port 8081)...")
    clip_python = get_python_path(clip_venv)

    if sys.platform == "win32":
        # Windows: 在新視窗中啟動
        # 執行本地Python腳本（clip_service.py），路徑由腳本控制
        clip_process = subprocess.Popen(  # nosec B603
            [clip_python, "clip_service.py"],
            creationflags=subprocess.CREATE_NEW_CONSOLE
        )
    else:
        # Linux/Mac: 在背景執行
        # 執行本地Python腳本（clip_service.py），路徑由腳本控制
        clip_process = subprocess.Popen(  # nosec B603
            [clip_python, "clip_service.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

    print(f"CLIP 服務已啟動 (PID: {clip_process.pid})")

    # 等待 CLIP 服務初始化
    print("等待 CLIP 服務初始化...")
    time.sleep(5)

    print()

    # 啟動 PaddleOCR 服務
    print("[2/2] 啟動 PaddleOCR 主服務 (Port 8080)...")
    paddle_python = get_python_path(paddle_venv)

    if sys.platform == "win32":
        # Windows: 在新視窗中啟動
        # 執行本地Python腳本（app.py），路徑由腳本控制
        paddle_process = subprocess.Popen(  # nosec B603
            [paddle_python, "app.py"],
            creationflags=subprocess.CREATE_NEW_CONSOLE
        )
    else:
        # Linux/Mac: 在背景執行
        # 執行本地Python腳本（app.py），路徑由腳本控制
        paddle_process = subprocess.Popen(  # nosec B603
            [paddle_python, "app.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

    print(f"PaddleOCR 服務已啟動 (PID: {paddle_process.pid})")

    print()
    print("=" * 50)
    print("服務啟動完成！")
    print("=" * 50)
    print()
    print("CLIP 服務:     http://localhost:8081")
    print("PaddleOCR 服務: http://localhost:8080")
    print("管理後台:      http://localhost:8080/admin")
    print()
    print("按 Ctrl+C 停止所有服務")
    print("=" * 50)
    print()

    try:
        # 持續運行，直到用戶中斷
        while True:
            # 檢查進程是否還在運行
            clip_status = clip_process.poll()
            paddle_status = paddle_process.poll()

            if clip_status is not None:
                print(f"\n[警告] CLIP 服務已停止 (退出代碼: {clip_status})")

            if paddle_status is not None:
                print(f"\n[警告] PaddleOCR 服務已停止 (退出代碼: {paddle_status})")

            if clip_status is not None and paddle_status is not None:
                print("\n所有服務已停止")
                break

            time.sleep(1)

    except KeyboardInterrupt:
        print("\n\n正在停止服務...")

        # 終止進程
        try:
            clip_process.terminate()
            print("CLIP 服務已停止")
        except (OSError, AttributeError):  # nosec B110
            # 進程可能已經停止或不存在
            pass

        try:
            paddle_process.terminate()
            print("PaddleOCR 服務已停止")
        except (OSError, AttributeError):  # nosec B110
            # 進程可能已經停止或不存在
            pass

        print("\n服務已全部停止")

if __name__ == "__main__":
    main()
