#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
安全檢測腳本
執行靜態分析 (bandit) 和依賴漏洞掃描 (pip-audit)
"""

import subprocess  # nosec B404 - 安全檢測腳本需要調用 bandit 和 pip-audit
import sys
import os
import json
from datetime import datetime

# 設置 UTF-8 輸出（Windows 相容性）
if sys.platform == 'win32':
    try:
        # 嘗試設置控制台為 UTF-8
        os.system('chcp 65001 > nul 2>&1')  # nosec B605, B607 - 安全的系統命令，僅設置編碼
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    except Exception:  # nosec B110
        # 如果設置編碼失敗，繼續執行（使用默認編碼）
        pass

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
        # 執行安全工具（bandit, pip-audit），命令參數由腳本控制
        result = subprocess.run(  # nosec B603
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
    # 執行 pip show 檢查工具安裝狀態，工具名由腳本指定
    result = subprocess.run(  # nosec B603
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

    # 文字格式報告
    result_txt = run_command(
        [sys.executable, "-m", "bandit", "-r", ".",
         "-f", "txt",
         "--exclude", "./venv_*,./official_models,./output,./logs,./temp_ocr,./.git"],
        "Bandit 靜態分析 (文字格式)"
    )

    if result_txt and result_txt.stdout:
        # 儲存文字報告
        with open(txt_report, 'w', encoding='utf-8') as f:
            f.write(result_txt.stdout)

        print(f"\n📄 報告已儲存:")
        print(f"   - JSON: {json_report}")
        print(f"   - TXT:  {txt_report}")

        # 解析並顯示詳細結果
        try:
            with open(json_report, 'r', encoding='utf-8') as f:
                data = json.load(f)

            results = data.get('results', [])
            metrics = data.get('metrics', {})

            # 統計總數
            total_issues = len(results)
            high_severity = sum(1 for r in results if r.get('issue_severity') == 'HIGH')
            medium_severity = sum(1 for r in results if r.get('issue_severity') == 'MEDIUM')
            low_severity = sum(1 for r in results if r.get('issue_severity') == 'LOW')

            print(f"\n📊 掃描結果總覽:")
            print(f"   總問題數: {total_issues}")
            print(f"   🔴 高風險: {high_severity}")
            print(f"   🟡 中風險: {medium_severity}")
            print(f"   🟢 低風險: {low_severity}")

            # 顯示前10個最重要的問題
            if results:
                print(f"\n⚠️  發現的安全問題 (按嚴重程度排序):")
                print("=" * 70)

                # 按嚴重程度排序
                severity_order = {'HIGH': 0, 'MEDIUM': 1, 'LOW': 2}
                sorted_results = sorted(results,
                                      key=lambda x: (severity_order.get(x.get('issue_severity', 'LOW'), 3),
                                                   -x.get('issue_confidence_level', 0)))

                # 顯示前10個問題
                for i, issue in enumerate(sorted_results[:10], 1):
                    severity = issue.get('issue_severity', 'UNKNOWN')
                    confidence = issue.get('issue_confidence', 'UNKNOWN')
                    test_id = issue.get('test_id', '')
                    test_name = issue.get('test_name', '')
                    filename = issue.get('filename', '')
                    line_number = issue.get('line_number', '')
                    issue_text = issue.get('issue_text', '')

                    # 嚴重程度圖標
                    severity_icon = {'HIGH': '🔴', 'MEDIUM': '🟡', 'LOW': '🟢'}.get(severity, '⚪')

                    print(f"\n{i}. {severity_icon} [{severity}/{confidence}] {test_name} ({test_id})")
                    print(f"   位置: {filename}:{line_number}")
                    print(f"   描述: {issue_text}")

                if len(sorted_results) > 10:
                    print(f"\n... 還有 {len(sorted_results) - 10} 個問題 (查看完整報告)")

                # 顯示低風險問題的摘要（按類型分組）
                low_issues = [r for r in results if r.get('issue_severity') == 'LOW']
                if low_issues:
                    print(f"\n📝 低風險問題摘要 (共 {len(low_issues)} 個):")
                    print("=" * 70)

                    # 按測試ID分組統計
                    issue_counts = {}
                    for issue in low_issues:
                        test_name = issue.get('test_name', 'unknown')
                        test_id = issue.get('test_id', '')
                        issue_text = issue.get('issue_text', '')
                        key = f"{test_name} ({test_id})"

                        if key not in issue_counts:
                            issue_counts[key] = {'count': 0, 'description': issue_text}
                        issue_counts[key]['count'] += 1

                    # 顯示統計
                    for idx, (key, info) in enumerate(sorted(issue_counts.items(), key=lambda x: -x[1]['count']), 1):
                        print(f"\n{idx}. {key}: {info['count']} 處")
                        print(f"   {info['description']}")

            else:
                print("\n✅ 未發現安全問題!")

            return True

        except Exception as e:
            print(f"❌ 解析報告失敗: {str(e)}")
            # 降級到基本輸出
            print("\n基本掃描結果:")
            print(result_txt.stdout[:1000])  # 只顯示前1000字符
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

    if result_txt and result_txt.stdout:
        # 儲存文字報告
        with open(txt_report, 'w', encoding='utf-8') as f:
            f.write(result_txt.stdout)
            if result_txt.stderr:
                f.write("\n\n=== 警告訊息 ===\n")
                f.write(result_txt.stderr)

        print(f"\n📄 報告已儲存:")
        print(f"   - JSON: {json_report}")
        print(f"   - TXT:  {txt_report}")

        # 解析並顯示詳細結果
        try:
            with open(json_report, 'r', encoding='utf-8') as f:
                data = json.load(f)

            dependencies = data.get('dependencies', [])
            # 只統計有漏洞的套件
            vulnerable_packages = [dep for dep in dependencies if dep.get('vulns', [])]
            total_vulnerabilities = sum(len(dep.get('vulns', [])) for dep in vulnerable_packages)

            print(f"\n📊 掃描結果總覽:")
            print(f"   掃描套件總數: {len(dependencies)}")
            print(f"   有漏洞的套件: {len(vulnerable_packages)}")
            print(f"   總漏洞數: {total_vulnerabilities}")

            if vulnerable_packages:
                print(f"\n🔍 發現的漏洞詳情:")
                print("=" * 70)

                for pkg_index, dep in enumerate(vulnerable_packages, 1):
                    name = dep.get('name', '')
                    version = dep.get('version', '')
                    vulns = dep.get('vulns', [])

                    print(f"\n📦 套件 {pkg_index}: {name} (版本 {version})")
                    print(f"   發現 {len(vulns)} 個漏洞:")

                    for vuln_index, vuln in enumerate(vulns, 1):
                        vuln_id = vuln.get('id', '')
                        description = vuln.get('description', '')
                        fix_versions = vuln.get('fix_versions', [])
                        aliases = vuln.get('aliases', [])

                        print(f"\n   {vuln_index}. 🚨 {vuln_id}")
                        if aliases:
                            print(f"      別名: {', '.join(aliases)}")
                        if description:
                            # 截斷過長的描述
                            desc_preview = description[:200] + "..." if len(description) > 200 else description
                            print(f"      描述: {desc_preview}")
                        if fix_versions:
                            print(f"      ✅ 修復版本: {', '.join(fix_versions)}")
                        else:
                            print(f"      ⚠️  尚無修復版本")

                print(f"\n{'=' * 70}")
                print("\n💡 修復建議:")
                for dep in vulnerable_packages:
                    name = dep.get('name', '')
                    version = dep.get('version', '')
                    # 找出所有漏洞的最高修復版本
                    fix_versions = []
                    for vuln in dep.get('vulns', []):
                        fix_versions.extend(vuln.get('fix_versions', []))

                    if fix_versions:
                        # 取最新的修復版本
                        latest_fix = sorted(fix_versions, reverse=True)[0]
                        print(f"   pip install --upgrade {name}>={latest_fix}")
                    else:
                        print(f"   ⚠️  {name}: 目前無修復版本，建議關注官方更新")

            else:
                print("\n✅ 未發現已知漏洞!")

            return True

        except Exception as e:
            print(f"❌ 解析 JSON 報告失敗: {str(e)}")
            # 降級到基本輸出
            print("\n基本掃描結果:")
            print(result_txt.stdout)
            if result_txt.returncode != 0:
                print("\n⚠️  發現潛在的安全漏洞!")
            return True

    return False

def calculate_risk_score(bandit_data, pip_audit_data):
    """計算風險評分 (0-100，越低越好)"""
    score = 0

    # Bandit 問題計分
    if bandit_data:
        results = bandit_data.get('results', [])
        high_count = sum(1 for r in results if r.get('issue_severity') == 'HIGH')
        medium_count = sum(1 for r in results if r.get('issue_severity') == 'MEDIUM')
        low_count = sum(1 for r in results if r.get('issue_severity') == 'LOW')

        score += high_count * 25  # 每個高風險 +25
        score += medium_count * 3  # 每個中風險 +3
        score += low_count * 0.5  # 每個低風險 +0.5

    # pip-audit 漏洞計分（只計算有漏洞的套件）
    if pip_audit_data:
        dependencies = pip_audit_data.get('dependencies', [])
        vulnerable_packages = [dep for dep in dependencies if dep.get('vulns', [])]
        for dep in vulnerable_packages:
            vulns = dep.get('vulns', [])
            score += len(vulns) * 10  # 每個依賴漏洞 +10

    return min(int(score), 100)  # 最高100分

def get_risk_level(score):
    """根據評分返回風險等級"""
    if score == 0:
        return "🟢 優秀", "green"
    elif score <= 15:
        return "🟡 良好", "yellow"
    elif score <= 40:
        return "🟠 中等", "orange"
    elif score <= 70:
        return "🔴 需要關注", "red"
    else:
        return "🔥 需要緊急處理", "critical"

def main():
    """主函數"""
    print("🔒 PaddleOCR 安全檢測工具")
    print("=" * 70)
    print(f"執行時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 儲存檢測數據
    bandit_data = None
    pip_audit_data = None

    # 執行 bandit
    bandit_success = run_bandit()
    if bandit_success:
        try:
            # 找到最新的 bandit 報告
            reports = sorted([f for f in os.listdir("security_reports") if f.startswith("bandit_report_") and f.endswith(".json")])
            if reports:
                with open(f"security_reports/{reports[-1]}", 'r', encoding='utf-8') as f:
                    bandit_data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError, OSError):  # nosec B110
            # 如果無法讀取報告，繼續執行（不影響 pip-audit）
            pass

    # 執行 pip-audit
    pip_audit_success = run_pip_audit()
    if pip_audit_success:
        try:
            # 找到最新的 pip-audit 報告
            reports = sorted([f for f in os.listdir("security_reports") if f.startswith("pip_audit_report_") and f.endswith(".json")])
            if reports:
                with open(f"security_reports/{reports[-1]}", 'r', encoding='utf-8') as f:
                    pip_audit_data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError, OSError):  # nosec B110
            # 如果無法讀取報告，繼續執行（不影響統計）
            pass

    # 總結
    print_section("檢測完成")

    if bandit_success and pip_audit_success:
        # 計算風險評分
        risk_score = calculate_risk_score(bandit_data, pip_audit_data)
        risk_level, risk_color = get_risk_level(risk_score)

        print("\n📊 整體安全評估:")
        print(f"   風險評分: {risk_score}/100")
        print(f"   風險等級: {risk_level}")

        # 統計總問題數
        total_bandit_issues = len(bandit_data.get('results', [])) if bandit_data else 0

        # 統計有漏洞的套件數和總漏洞數
        vulnerable_packages_count = 0
        total_pip_issues = 0
        if pip_audit_data:
            dependencies = pip_audit_data.get('dependencies', [])
            vulnerable_packages = [dep for dep in dependencies if dep.get('vulns', [])]
            vulnerable_packages_count = len(vulnerable_packages)
            total_pip_issues = sum(len(dep.get('vulns', [])) for dep in vulnerable_packages)

        print(f"\n   總計發現:")
        print(f"   • Bandit 代碼問題: {total_bandit_issues}")
        print(f"   • 有漏洞的依賴套件: {vulnerable_packages_count} 個 (共 {total_pip_issues} 個漏洞)")

        print("\n✅ 所有安全檢測已完成")
        print("📁 詳細報告儲存在 security_reports/ 目錄")

        # 提供優先級建議
        if risk_score > 30:
            print("\n🚨 緊急行動建議:")
            action_num = 1
            if bandit_data:
                high_issues = [r for r in bandit_data.get('results', []) if r.get('issue_severity') == 'HIGH']
                medium_issues = [r for r in bandit_data.get('results', []) if r.get('issue_severity') == 'MEDIUM']
                if high_issues:
                    print(f"   {action_num}. 立即修復 {len(high_issues)} 個 Bandit 高風險問題")
                    action_num += 1
                elif medium_issues:
                    print(f"   {action_num}. 修復 {len(medium_issues)} 個 Bandit 中風險問題")
                    action_num += 1
            if vulnerable_packages_count > 0:
                print(f"   {action_num}. 更新 {vulnerable_packages_count} 個有漏洞的依賴套件")
        elif risk_score > 0:
            print("\n💡 改進建議:")
            if total_bandit_issues > 0:
                print(f"   • 審查並修復 {total_bandit_issues} 個 Bandit 檢測到的問題")
            if vulnerable_packages_count > 0:
                print(f"   • 更新 {vulnerable_packages_count} 個有漏洞的依賴套件")

    elif bandit_success or pip_audit_success:
        print("⚠️  部分安全檢測已完成")
        print("📁 報告儲存在 security_reports/ 目錄")
    else:
        print("❌ 安全檢測失敗，請確認工具已正確安裝")
        print("\n安裝指令:")
        print("  pip install bandit pip-audit")
        return 1

    print("\n💡 最佳實踐建議:")
    print("  1. 定期執行此腳本 (建議每週一次)")
    print("  2. 在部署前執行一次完整檢測")
    print("  3. 優先修復高風險問題和已知漏洞")
    print("  4. 保持依賴套件為最新穩定版本")
    print("  5. 將安全檢測整合到 CI/CD 流程")

    return 0

if __name__ == "__main__":
    sys.exit(main())
