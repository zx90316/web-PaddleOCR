#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
安全檢測腳本
執行靜態分析 (bandit) 和依賴漏洞掃描 (pip-audit)
"""

import subprocess
import sys
import os
import json
from datetime import datetime

def print_section(title):
    """列印區段標題"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)

def run_command(command, description):
    """執行命令並返回結果"""
    print(f"\n正在執行: {description}...")
    print(f"命令: {' '.join(command)}\n")

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding='utf-8'
        )
        return result
    except Exception as e:
        print(f"❌ 執行失敗: {str(e)}")
        return None

def check_tool_installed(tool_name, install_command):
    """檢查工具是否已安裝"""
    result = subprocess.run(
        [sys.executable, "-m", "pip", "show", tool_name],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        print(f"⚠️  {tool_name} 尚未安裝")
        print(f"請執行: {install_command}")
        return False
    return True

def run_bandit():
    """執行 bandit 靜態分析"""
    print_section("Bandit 靜態程式碼分析")

    if not check_tool_installed("bandit", "pip install bandit"):
        return False

    # 創建 security_reports 目錄
    os.makedirs("security_reports", exist_ok=True)

    # 執行 bandit
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_report = f"security_reports/bandit_report_{timestamp}.json"
    txt_report = f"security_reports/bandit_report_{timestamp}.txt"

    # JSON 格式報告
    result_json = run_command(
        [sys.executable, "-m", "bandit", "-r", ".",
         "-f", "json", "-o", json_report,
         "--exclude", "./venv_*,./official_models,./output,./logs,./temp_ocr,./.git"],
        "Bandit 靜態分析 (JSON 格式)"
    )

    # 文字格式報告 (顯示在控制台)
    result_txt = run_command(
        [sys.executable, "-m", "bandit", "-r", ".",
         "-f", "txt",
         "--exclude", "./venv_*,./official_models,./output,./logs,./temp_ocr,./.git"],
        "Bandit 靜態分析 (文字格式)"
    )

    if result_txt:
        print(result_txt.stdout)

        # 儲存文字報告
        with open(txt_report, 'w', encoding='utf-8') as f:
            f.write(result_txt.stdout)

        print(f"\n📄 報告已儲存:")
        print(f"   - JSON: {json_report}")
        print(f"   - TXT:  {txt_report}")

        # 解析 JSON 報告以顯示摘要
        try:
            with open(json_report, 'r', encoding='utf-8') as f:
                data = json.load(f)
                metrics = data.get('metrics', {})

                print(f"\n📊 掃描摘要:")
                for key, value in metrics.items():
                    if isinstance(value, dict):
                        print(f"   {key}:")
                        for k, v in value.items():
                            print(f"      {k}: {v}")
                    else:
                        print(f"   {key}: {value}")
        except Exception as e:
            print(f"解析報告失敗: {str(e)}")

        return True

    return False

def run_pip_audit():
    """執行 pip-audit 依賴漏洞掃描"""
    print_section("pip-audit 依賴漏洞掃描")

    if not check_tool_installed("pip-audit", "pip install pip-audit"):
        return False

    # 創建 security_reports 目錄
    os.makedirs("security_reports", exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_report = f"security_reports/pip_audit_report_{timestamp}.json"
    txt_report = f"security_reports/pip_audit_report_{timestamp}.txt"

    # JSON 格式報告
    result_json = run_command(
        [sys.executable, "-m", "pip_audit", "--format", "json", "--output", json_report],
        "pip-audit 漏洞掃描 (JSON 格式)"
    )

    # 文字格式報告
    result_txt = run_command(
        [sys.executable, "-m", "pip_audit"],
        "pip-audit 漏洞掃描 (文字格式)"
    )

    if result_txt:
        print(result_txt.stdout)
        if result_txt.stderr:
            print("錯誤輸出:", result_txt.stderr)

        # 儲存文字報告
        with open(txt_report, 'w', encoding='utf-8') as f:
            f.write(result_txt.stdout)
            if result_txt.stderr:
                f.write("\n\n=== 錯誤輸出 ===\n")
                f.write(result_txt.stderr)

        print(f"\n📄 報告已儲存:")
        print(f"   - JSON: {json_report}")
        print(f"   - TXT:  {txt_report}")

        # 檢查是否有漏洞
        if result_txt.returncode == 0:
            print("\n✅ 未發現已知漏洞!")
        else:
            print("\n⚠️  發現潛在的安全漏洞，請檢視報告!")

        return True

    return False

def main():
    """主函數"""
    print("🔒 PaddleOCR 安全檢測工具")
    print("=" * 70)
    print(f"執行時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 執行 bandit
    bandit_success = run_bandit()

    # 執行 pip-audit
    pip_audit_success = run_pip_audit()

    # 總結
    print_section("檢測完成")

    if bandit_success and pip_audit_success:
        print("✅ 所有安全檢測已完成")
        print("📁 報告儲存在 security_reports/ 目錄")
    elif bandit_success or pip_audit_success:
        print("⚠️  部分安全檢測已完成")
        print("📁 報告儲存在 security_reports/ 目錄")
    else:
        print("❌ 安全檢測失敗，請確認工具已正確安裝")
        print("\n安裝指令:")
        print("  pip install bandit pip-audit")
        return 1

    print("\n💡 建議:")
    print("  1. 定期執行此腳本 (建議每週一次)")
    print("  2. 在部署前執行一次完整檢測")
    print("  3. 修復報告中的高危問題")
    print("  4. 保持依賴套件為最新版本")

    return 0

if __name__ == "__main__":
    sys.exit(main())
