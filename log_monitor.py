"""
日誌監控模組
監控應用程式日誌系統的健康狀態，並在日誌失效時發出警報
"""

import os
import time
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# 配置
LOG_DIR = "logs"
LOG_FILE = "app.log"
MONITOR_LOG = "logs/monitor.log"
ALERT_LOG = "logs/alerts.log"
CHECK_INTERVAL = 300  # 檢查間隔：5分鐘
MAX_LOG_AGE = 600  # 日誌最大年齡：10分鐘（如果系統運行但10分鐘無日誌，視為異常）
ALERT_COOLDOWN = 3600  # 警報冷卻時間：1小時（避免重複發送警報）

# 設定監控日誌
monitor_logger = logging.getLogger("log_monitor")
monitor_logger.setLevel(logging.INFO)
os.makedirs(LOG_DIR, exist_ok=True)

monitor_handler = logging.FileHandler(MONITOR_LOG, encoding='utf-8')
monitor_handler.setFormatter(logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
))
monitor_logger.addHandler(monitor_handler)

# 同時輸出到控制台
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
monitor_logger.addHandler(console_handler)


class LogHealthStatus:
    """日誌健康狀態"""
    def __init__(self):
        self.last_check_time: Optional[datetime] = None
        self.last_log_time: Optional[datetime] = None
        self.last_alert_time: Optional[datetime] = None
        self.log_file_size: int = 0
        self.is_healthy: bool = True
        self.error_message: Optional[str] = None
        self.check_count: int = 0
        self.alert_count: int = 0


class LogMonitor:
    """日誌監控器"""

    def __init__(self, log_path: str = None, config: Dict[str, Any] = None):
        """
        初始化日誌監控器

        Args:
            log_path: 要監控的日誌檔案路徑
            config: 監控配置字典
        """
        self.log_path = log_path or os.path.join(LOG_DIR, LOG_FILE)
        self.config = config or {}
        self.status = LogHealthStatus()

        # 從配置讀取參數
        self.check_interval = self.config.get('check_interval', CHECK_INTERVAL)
        self.max_log_age = self.config.get('max_log_age', MAX_LOG_AGE)
        self.alert_cooldown = self.config.get('alert_cooldown', ALERT_COOLDOWN)

        # 警報配置
        self.enable_email_alert = self.config.get('enable_email_alert', False)
        self.email_config = self.config.get('email_config', {})

        monitor_logger.info(f"日誌監控器初始化完成，監控檔案: {self.log_path}")

    def check_log_health(self) -> Dict[str, Any]:
        """
        檢查日誌健康狀態

        Returns:
            包含健康狀態的字典
        """
        self.status.last_check_time = datetime.now()
        self.status.check_count += 1

        result = {
            'check_time': self.status.last_check_time.isoformat(),
            'is_healthy': True,
            'issues': []
        }

        try:
            # 檢查1: 日誌檔案是否存在
            if not os.path.exists(self.log_path):
                result['is_healthy'] = False
                result['issues'].append({
                    'type': 'FILE_NOT_FOUND',
                    'severity': 'HIGH',
                    'message': f'日誌檔案不存在: {self.log_path}'
                })
                monitor_logger.warning(f"日誌檔案不存在: {self.log_path}")
                self._trigger_alert(result['issues'][-1])
                return result

            # 檢查2: 日誌檔案是否可讀
            if not os.access(self.log_path, os.R_OK):
                result['is_healthy'] = False
                result['issues'].append({
                    'type': 'FILE_NOT_READABLE',
                    'severity': 'HIGH',
                    'message': f'日誌檔案無法讀取: {self.log_path}'
                })
                monitor_logger.warning(f"日誌檔案無法讀取: {self.log_path}")
                self._trigger_alert(result['issues'][-1])
                return result

            # 檢查3: 取得檔案資訊
            stat_info = os.stat(self.log_path)
            self.status.log_file_size = stat_info.st_size
            file_mtime = datetime.fromtimestamp(stat_info.st_mtime)
            self.status.last_log_time = file_mtime

            result['file_size'] = self.status.log_file_size
            result['last_modified'] = file_mtime.isoformat()

            # 檢查4: 日誌檔案大小是否為0（可能寫入失敗）
            if self.status.log_file_size == 0:
                result['is_healthy'] = False
                result['issues'].append({
                    'type': 'EMPTY_LOG_FILE',
                    'severity': 'MEDIUM',
                    'message': '日誌檔案大小為0，可能尚未寫入或寫入失敗'
                })
                monitor_logger.warning("日誌檔案大小為0")

            # 檢查5: 日誌是否長時間未更新
            time_since_last_log = (datetime.now() - file_mtime).total_seconds()
            result['seconds_since_last_log'] = int(time_since_last_log)

            if time_since_last_log > self.max_log_age:
                result['is_healthy'] = False
                result['issues'].append({
                    'type': 'LOG_TOO_OLD',
                    'severity': 'MEDIUM',
                    'message': f'日誌已超過 {int(time_since_last_log/60)} 分鐘未更新 (閾值: {int(self.max_log_age/60)} 分鐘)',
                    'seconds_since_last_log': int(time_since_last_log)
                })
                monitor_logger.warning(f"日誌已超過 {int(time_since_last_log/60)} 分鐘未更新")
                self._trigger_alert(result['issues'][-1])

            # 檢查6: 讀取最後幾行日誌，檢查是否有錯誤
            try:
                recent_errors = self._check_recent_errors()
                if recent_errors:
                    result['recent_errors'] = recent_errors
                    result['issues'].append({
                        'type': 'RECENT_ERRORS',
                        'severity': 'LOW',
                        'message': f'發現 {len(recent_errors)} 個最近的錯誤日誌',
                        'error_count': len(recent_errors)
                    })
            except Exception as e:
                monitor_logger.error(f"檢查錯誤日誌時發生異常: {e}")

            # 更新整體健康狀態
            self.status.is_healthy = result['is_healthy']
            if not result['is_healthy']:
                self.status.error_message = '; '.join([issue['message'] for issue in result['issues']])
            else:
                self.status.error_message = None
                monitor_logger.info(f"日誌健康檢查通過 (檢查次數: {self.status.check_count})")

        except Exception as e:
            result['is_healthy'] = False
            result['issues'].append({
                'type': 'CHECK_FAILED',
                'severity': 'HIGH',
                'message': f'健康檢查失敗: {str(e)}'
            })
            monitor_logger.error(f"健康檢查失敗: {e}", exc_info=True)
            self._trigger_alert(result['issues'][-1])

        return result

    def _check_recent_errors(self, lines: int = 100) -> list:
        """
        檢查最近的錯誤日誌

        Args:
            lines: 檢查最後幾行

        Returns:
            錯誤日誌列表
        """
        errors = []
        try:
            with open(self.log_path, 'r', encoding='utf-8') as f:
                # 讀取最後 N 行
                all_lines = f.readlines()
                recent_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines

                for line in recent_lines:
                    if ' - ERROR - ' in line or ' - CRITICAL - ' in line:
                        errors.append(line.strip())
        except Exception as e:
            monitor_logger.error(f"讀取日誌檔案時發生錯誤: {e}")

        return errors

    def _trigger_alert(self, issue: Dict[str, Any]):
        """
        觸發警報

        Args:
            issue: 問題資訊字典
        """
        # 檢查警報冷卻時間
        now = datetime.now()
        if self.status.last_alert_time:
            time_since_last_alert = (now - self.status.last_alert_time).total_seconds()
            if time_since_last_alert < self.alert_cooldown:
                monitor_logger.debug(f"警報冷卻中，距離上次警報 {int(time_since_last_alert)} 秒")
                return

        # 更新警報時間
        self.status.last_alert_time = now
        self.status.alert_count += 1

        # 記錄警報
        alert_message = f"[警報 #{self.status.alert_count}] {issue['severity']} - {issue['message']}"
        monitor_logger.warning(alert_message)

        # 寫入警報日誌
        try:
            with open(ALERT_LOG, 'a', encoding='utf-8') as f:
                alert_record = {
                    'timestamp': now.isoformat(),
                    'alert_id': self.status.alert_count,
                    'issue': issue
                }
                f.write(json.dumps(alert_record, ensure_ascii=False) + '\n')
        except Exception as e:
            monitor_logger.error(f"寫入警報日誌失敗: {e}")

        # 發送郵件警報（如果啟用）
        if self.enable_email_alert and self.email_config:
            try:
                self._send_email_alert(issue)
            except Exception as e:
                monitor_logger.error(f"發送郵件警報失敗: {e}")

    def _send_email_alert(self, issue: Dict[str, Any]):
        """
        發送郵件警報

        Args:
            issue: 問題資訊字典
        """
        smtp_server = self.email_config.get('smtp_server')
        smtp_port = self.email_config.get('smtp_port', 587)
        sender = self.email_config.get('sender')
        password = self.email_config.get('password')
        recipients = self.email_config.get('recipients', [])

        if not all([smtp_server, sender, password, recipients]):
            monitor_logger.warning("郵件配置不完整，跳過郵件警報")
            return

        # 建立郵件
        msg = MIMEMultipart()
        msg['From'] = sender
        msg['To'] = ', '.join(recipients)
        msg['Subject'] = f"[日誌監控警報] {issue['severity']} - PaddleOCR系統"

        body = f"""
日誌監控系統檢測到問題：

問題類型: {issue['type']}
嚴重程度: {issue['severity']}
問題描述: {issue['message']}
檢測時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
日誌檔案: {self.log_path}

請盡快檢查系統狀態。

---
PaddleOCR 日誌監控系統
"""

        msg.attach(MIMEText(body, 'plain', 'utf-8'))

        # 發送郵件
        try:
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.starttls()
                server.login(sender, password)
                server.send_message(msg)
            monitor_logger.info(f"郵件警報已發送至: {', '.join(recipients)}")
        except Exception as e:
            monitor_logger.error(f"發送郵件時發生錯誤: {e}")

    def get_status_summary(self) -> Dict[str, Any]:
        """
        取得監控狀態摘要

        Returns:
            狀態摘要字典
        """
        return {
            'is_healthy': self.status.is_healthy,
            'last_check_time': self.status.last_check_time.isoformat() if self.status.last_check_time else None,
            'last_log_time': self.status.last_log_time.isoformat() if self.status.last_log_time else None,
            'log_file_size': self.status.log_file_size,
            'check_count': self.status.check_count,
            'alert_count': self.status.alert_count,
            'error_message': self.status.error_message
        }

    def run_continuous_monitoring(self):
        """
        持續監控模式（背景執行）
        """
        monitor_logger.info(f"開始持續監控，檢查間隔: {self.check_interval} 秒")

        try:
            while True:
                result = self.check_log_health()

                if not result['is_healthy']:
                    monitor_logger.warning(f"日誌健康檢查未通過，發現 {len(result['issues'])} 個問題")
                    for issue in result['issues']:
                        monitor_logger.warning(f"  - {issue['severity']}: {issue['message']}")

                time.sleep(self.check_interval)

        except KeyboardInterrupt:
            monitor_logger.info("收到中斷信號，停止監控")
        except Exception as e:
            monitor_logger.error(f"監控過程中發生錯誤: {e}", exc_info=True)


def load_config(config_path: str = "log_monitor_config.json") -> Dict[str, Any]:
    """
    載入監控配置

    Args:
        config_path: 配置檔案路徑

    Returns:
        配置字典
    """
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            monitor_logger.info(f"已載入配置檔案: {config_path}")
            return config
        except Exception as e:
            monitor_logger.error(f"載入配置檔案失敗: {e}")

    return {}


def create_default_config(config_path: str = "log_monitor_config.json"):
    """
    建立預設配置檔案

    Args:
        config_path: 配置檔案路徑
    """
    default_config = {
        "check_interval": 300,
        "max_log_age": 600,
        "alert_cooldown": 3600,
        "enable_email_alert": False,
        "email_config": {
            "smtp_server": "smtp.example.com",
            "smtp_port": 587,
            "sender": "monitor@example.com",
            "password": "your_password_here",
            "recipients": ["admin@example.com"]
        }
    }

    try:
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(default_config, f, indent=2, ensure_ascii=False)
        monitor_logger.info(f"已建立預設配置檔案: {config_path}")
    except Exception as e:
        monitor_logger.error(f"建立配置檔案失敗: {e}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='PaddleOCR 日誌監控系統')
    parser.add_argument('--log-path', type=str, help='要監控的日誌檔案路徑')
    parser.add_argument('--config', type=str, default='log_monitor_config.json', help='配置檔案路徑')
    parser.add_argument('--create-config', action='store_true', help='建立預設配置檔案')
    parser.add_argument('--once', action='store_true', help='執行一次檢查後退出')

    args = parser.parse_args()

    # 建立預設配置
    if args.create_config:
        create_default_config(args.config)
        print(f"預設配置檔案已建立: {args.config}")
        print("請編輯配置檔案後再執行監控")
        exit(0)

    # 載入配置
    config = load_config(args.config)

    # 建立監控器
    monitor = LogMonitor(log_path=args.log_path, config=config)

    if args.once:
        # 執行一次檢查
        result = monitor.check_log_health()
        print(json.dumps(result, indent=2, ensure_ascii=False))
        print(f"\n健康狀態: {'✅ 正常' if result['is_healthy'] else '❌ 異常'}")
    else:
        # 持續監控
        monitor.run_continuous_monitoring()
