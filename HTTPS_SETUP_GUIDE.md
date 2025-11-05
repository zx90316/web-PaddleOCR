# HTTPS/TLS 加密設定指南

本指南說明如何為 PaddleOCR 系統配置 HTTPS/TLS 加密傳輸。

## 📋 目錄

1. [為什麼需要 HTTPS](#為什麼需要-https)
2. [前置需求](#前置需求)
3. [選項一：使用 Nginx 反向代理 (推薦)](#選項一使用-nginx-反向代理-推薦)
4. [選項二：自簽憑證 (內網環境)](#選項二自簽憑證-內網環境)
5. [選項三：Let's Encrypt 免費憑證](#選項三lets-encrypt-免費憑證)
6. [驗證 HTTPS 設定](#驗證-https-設定)
7. [安全性最佳實踐](#安全性最佳實踐)
8. [常見問題](#常見問題)

---

## 為什麼需要 HTTPS

雖然本系統部署於內部網路，但啟用 HTTPS 仍有以下優點：

- ✅ **資料加密**: 傳輸中的 OCR 文件內容被加密保護
- ✅ **完整性驗證**: 防止中間人攻擊和資料竄改
- ✅ **身分驗證**: 確認連線到正確的伺服器
- ✅ **符合法規**: 滿足資安稽核對加密傳輸的要求
- ✅ **最佳實踐**: 遵循現代網路安全標準

---

## 前置需求

### 軟體需求

- **Nginx**: 1.18+ (作為反向代理)
- **OpenSSL**: 1.1.1+ (產生憑證)
- **作業系統**: Windows Server 2016+ 或 Linux (Ubuntu 20.04+)

### 網路需求

- 確認防火牆開放 443 port (HTTPS)
- 如需 HTTP 自動重定向，開放 80 port
- 內網環境需確保客戶端可連線到伺服器 IP

---

## 選項一：使用 Nginx 反向代理 (推薦)

### 1. 安裝 Nginx

#### Windows
```powershell
# 下載 Nginx for Windows
# https://nginx.org/en/download.html

# 解壓到 C:\nginx
cd C:\nginx
```

#### Linux (Ubuntu/Debian)
```bash
sudo apt update
sudo apt install nginx
```

### 2. 準備 SSL 憑證

選擇以下其中一種方式取得憑證：

#### A. 內網自簽憑證 (測試/內網使用)

```bash
# 產生私鑰和憑證 (有效期 365 天)
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout /etc/nginx/ssl/paddleocr-key.pem \
  -out /etc/nginx/ssl/paddleocr-cert.pem \
  -subj "/C=TW/ST=Taipei/L=Taipei/O=YourCompany/OU=IT/CN=your-server-ip"
```

**Windows 版本**:
```powershell
# 使用 OpenSSL for Windows
openssl req -x509 -nodes -days 365 -newkey rsa:2048 `
  -keyout C:\nginx\ssl\paddleocr-key.pem `
  -out C:\nginx\ssl\paddleocr-cert.pem `
  -subj "/C=TW/ST=Taipei/L=Taipei/O=YourCompany/OU=IT/CN=192.168.1.100"
```

#### B. 企業憑證 (正式環境)

如果您的組織有內部 CA (憑證授權中心):

1. 產生 CSR (憑證簽署請求)
2. 提交給 IT 部門簽署
3. 取得憑證檔案

#### C. Let's Encrypt (公網環境)

若系統對外且有域名:

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

### 3. 配置 Nginx

複製提供的配置檔案：

```bash
# Linux
sudo cp nginx_https.conf /etc/nginx/sites-available/paddleocr
sudo ln -s /etc/nginx/sites-available/paddleocr /etc/nginx/sites-enabled/
```

```powershell
# Windows
copy nginx_https.conf C:\nginx\conf\paddleocr.conf
```

### 4. 修改配置檔案

編輯 `nginx_https.conf`，修改以下項目：

```nginx
server_name your-domain.com;  # 改為您的域名或內網 IP (如 192.168.1.100)

ssl_certificate /path/to/your/fullchain.pem;      # 憑證路徑
ssl_certificate_key /path/to/your/privkey.pem;    # 私鑰路徑
```

**範例 (內網 IP)**:
```nginx
server_name 192.168.1.100;

ssl_certificate C:/nginx/ssl/paddleocr-cert.pem;
ssl_certificate_key C:/nginx/ssl/paddleocr-key.pem;
```

### 5. 測試配置

```bash
# Linux
sudo nginx -t

# Windows
C:\nginx\nginx.exe -t
```

### 6. 重新載入 Nginx

```bash
# Linux
sudo systemctl reload nginx
# 或
sudo nginx -s reload

# Windows
C:\nginx\nginx.exe -s reload
```

### 7. 驗證服務

訪問 `https://your-server-ip` 或 `https://your-domain.com`

---

## 選項二：自簽憑證 (內網環境)

### 快速產生自簽憑證

我們提供了一個便捷腳本來產生自簽憑證：

```bash
# Linux/Mac
./generate_self_signed_cert.sh 192.168.1.100

# Windows (PowerShell)
.\generate_self_signed_cert.ps1 -ServerIP "192.168.1.100"
```

### 手動產生自簽憑證

```bash
# 1. 產生私鑰
openssl genrsa -out server-key.pem 2048

# 2. 產生憑證簽署請求 (CSR)
openssl req -new -key server-key.pem -out server.csr \
  -subj "/C=TW/ST=Taipei/L=Taipei/O=YourCompany/CN=192.168.1.100"

# 3. 自簽憑證 (有效期 365 天)
openssl x509 -req -days 365 -in server.csr \
  -signkey server-key.pem -out server-cert.pem

# 4. 清理 CSR 檔案
rm server.csr
```

### 客戶端信任自簽憑證

#### Windows
1. 雙擊 `server-cert.pem`
2. 點擊「安裝憑證」
3. 選擇「本機電腦」
4. 放入「受信任的根憑證授權單位」

#### Chrome
1. 設定 → 隱私權和安全性 → 安全性
2. 管理憑證 → 授信的根憑證授權單位
3. 匯入 → 選擇 `server-cert.pem`

---

## 選項三：Let's Encrypt 免費憑證

**注意**: 僅適用於可從公網存取的伺服器。

### 自動設定 (推薦)

```bash
# 安裝 Certbot
sudo apt install certbot python3-certbot-nginx

# 自動取得並配置憑證
sudo certbot --nginx -d your-domain.com

# 測試自動更新
sudo certbot renew --dry-run
```

### 手動設定

```bash
# 僅取得憑證
sudo certbot certonly --nginx -d your-domain.com

# 憑證位置
# /etc/letsencrypt/live/your-domain.com/fullchain.pem
# /etc/letsencrypt/live/your-domain.com/privkey.pem
```

### 自動更新

Let's Encrypt 憑證有效期 90 天，需設定自動更新：

```bash
# 測試更新
sudo certbot renew --dry-run

# 設定 Cron job (每天檢查)
sudo crontab -e
# 加入以下行
0 3 * * * /usr/bin/certbot renew --quiet && /usr/sbin/nginx -s reload
```

---

## 驗證 HTTPS 設定

### 1. 檢查憑證資訊

```bash
# Linux
openssl s_client -connect your-server:443 -servername your-domain.com

# 查看憑證詳細資訊
openssl x509 -in server-cert.pem -text -noout
```

### 2. 測試 TLS 版本

```bash
# 測試 TLS 1.2
openssl s_client -connect your-server:443 -tls1_2

# 測試 TLS 1.3
openssl s_client -connect your-server:443 -tls1_3

# 確認不支援 TLS 1.1 (應該失敗)
openssl s_client -connect your-server:443 -tls1_1
```

### 3. 線上工具檢測

- **SSL Labs**: https://www.ssllabs.com/ssltest/ (僅限公網)
- **testssl.sh**: 本地測試工具

```bash
# 安裝 testssl.sh
git clone https://github.com/drwetter/testssl.sh.git
cd testssl.sh
./testssl.sh https://your-server
```

### 4. 瀏覽器檢查

1. 訪問 `https://your-server`
2. 點擊網址列的鎖頭圖示
3. 查看憑證資訊
4. 確認使用 TLS 1.2 或 1.3

---

## 安全性最佳實踐

### 1. 憑證管理

- ✅ 定期更新憑證 (到期前 30 天)
- ✅ 私鑰權限設為 600 (僅擁有者可讀寫)
```bash
chmod 600 /path/to/privkey.pem
```
- ✅ 不要將私鑰提交到 Git 版控
- ✅ 使用強密碼保護私鑰 (可選)

### 2. TLS 協定配置

僅啟用安全的 TLS 版本：

```nginx
ssl_protocols TLSv1.2 TLSv1.3;  # 禁用 TLS 1.0 和 1.1
```

### 3. 加密套件選擇

使用強加密套件：

```nginx
ssl_ciphers 'ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384';
ssl_prefer_server_ciphers on;
```

### 4. 安全標頭

```nginx
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
add_header X-Frame-Options "SAMEORIGIN" always;
add_header X-Content-Type-Options "nosniff" always;
```

### 5. 防火牆規則

```bash
# 僅允許內網存取 HTTPS
sudo ufw allow from 192.168.0.0/16 to any port 443
sudo ufw deny 443

# 或使用 Nginx 配置
location / {
    allow 192.168.0.0/16;
    deny all;
}
```

---

## 常見問題

### Q1: 瀏覽器顯示「不安全的連線」或「NET::ERR_CERT_AUTHORITY_INVALID」

**A**: 這是使用自簽憑證的正常現象。解決方式：

1. **短期解決**: 點擊「進階」→「繼續前往網站」
2. **長期解決**: 將自簽憑證加入客戶端信任清單 (見上方說明)

### Q2: Nginx 啟動失敗，提示「SSL: error:0200100D:system library:fopen:Permission denied」

**A**: 檢查憑證檔案權限：

```bash
sudo chmod 644 /path/to/cert.pem
sudo chmod 600 /path/to/key.pem
sudo chown root:root /path/to/*.pem
```

### Q3: CLIP 服務無法透過 HTTPS 連線

**A**: 更新 app.py 中的 CLIP_SERVICE_URL：

```python
# 從
CLIP_SERVICE_URL = "http://localhost:8081"

# 改為
CLIP_SERVICE_URL = "https://localhost:8443"
```

或設定環境變數：
```bash
export CLIP_SERVICE_URL="https://localhost:8443"
```

### Q4: Windows 環境下如何安裝 Nginx

**A**:
1. 下載 Nginx for Windows: https://nginx.org/en/download.html
2. 解壓到 `C:\nginx`
3. 複製配置檔案到 `C:\nginx\conf\`
4. 啟動: `C:\nginx\nginx.exe`
5. 停止: `C:\nginx\nginx.exe -s quit`

### Q5: 如何強制所有連線使用 HTTPS

**A**: 在 Nginx 配置中加入 HTTP 重定向：

```nginx
server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$server_name$request_uri;
}
```

### Q6: 憑證到期後該怎麼辦

**A**:
- **自簽憑證**: 重新產生新憑證並替換
- **Let's Encrypt**: 執行 `sudo certbot renew`
- **企業憑證**: 聯絡 IT 部門續約

### Q7: 如何檢查憑證有效期限

```bash
openssl x509 -in /path/to/cert.pem -noout -dates
```

或

```bash
echo | openssl s_client -connect your-server:443 2>/dev/null | openssl x509 -noout -dates
```

---

## 📞 技術支援

如遇到設定問題，請聯絡系統管理員或參考以下資源：

- **Nginx 官方文件**: https://nginx.org/en/docs/
- **Let's Encrypt 文件**: https://letsencrypt.org/docs/
- **Mozilla SSL Configuration Generator**: https://ssl-config.mozilla.org/

---

## 📝 變更記錄

- **v1.0** (2025-01-05): 初始版本
  - 新增 Nginx HTTPS 配置範例
  - 新增自簽憑證產生指南
  - 新增 Let's Encrypt 設定說明
  - 新增安全性最佳實踐

---

**檔案結束**
