# 自簽憑證產生腳本 (Windows PowerShell)
# 用於產生 PaddleOCR 系統的 SSL 自簽憑證

param(
    [Parameter(Mandatory=$true)]
    [string]$ServerIP,

    [int]$DaysValid = 365,

    [string]$CertDir = "ssl_certificates"
)

Write-Host "========================================" -ForegroundColor Green
Write-Host "  PaddleOCR SSL 自簽憑證產生工具" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""

# 建立目錄
if (-not (Test-Path $CertDir)) {
    New-Item -ItemType Directory -Path $CertDir | Out-Null
}

$CertFile = Join-Path $CertDir "server-cert.pem"
$KeyFile = Join-Path $CertDir "server-key.pem"

Write-Host "設定資訊:" -ForegroundColor Green
Write-Host "  伺服器 IP/域名: $ServerIP"
Write-Host "  憑證有效期: $DaysValid 天"
Write-Host "  輸出目錄: $CertDir"
Write-Host ""

# 檢查 OpenSSL
$opensslPath = Get-Command openssl -ErrorAction SilentlyContinue

if (-not $opensslPath) {
    Write-Host "錯誤: 找不到 OpenSSL" -ForegroundColor Red
    Write-Host ""
    Write-Host "請先安裝 OpenSSL for Windows:" -ForegroundColor Yellow
    Write-Host "  方法1: 使用 Chocolatey"
    Write-Host "    choco install openssl"
    Write-Host ""
    Write-Host "  方法2: 手動下載安裝"
    Write-Host "    https://slproweb.com/products/Win32OpenSSL.html"
    Write-Host ""
    exit 1
}

Write-Host "正在產生 SSL 憑證..." -ForegroundColor Green

# 產生私鑰和自簽憑證
$opensslCmd = "openssl req -x509 -nodes -days $DaysValid -newkey rsa:2048 " +
              "-keyout `"$KeyFile`" " +
              "-out `"$CertFile`" " +
              "-subj `"/C=TW/ST=Taiwan/L=Taipei/O=PaddleOCR/OU=IT/CN=$ServerIP`""

Invoke-Expression $opensslCmd 2>$null

if ($LASTEXITCODE -ne 0) {
    Write-Host "錯誤: 憑證產生失敗" -ForegroundColor Red
    exit 1
}

Write-Host "✓ 憑證產生成功！" -ForegroundColor Green
Write-Host ""

Write-Host "憑證檔案位置:" -ForegroundColor Green
Write-Host "  憑證: $(Resolve-Path $CertFile)"
Write-Host "  私鑰: $(Resolve-Path $KeyFile)"
Write-Host ""

# 顯示憑證資訊
Write-Host "憑證資訊:" -ForegroundColor Green
$certInfo = & openssl x509 -in $CertFile -noout -subject -dates
Write-Host $certInfo
Write-Host ""

Write-Host "下一步操作:" -ForegroundColor Yellow
Write-Host "1. 將憑證複製到 Nginx SSL 目錄"
Write-Host "   copy $CertFile C:\nginx\ssl\"
Write-Host "   copy $KeyFile C:\nginx\ssl\"
Write-Host ""
Write-Host "2. 更新 Nginx 配置檔案 (nginx_https.conf)"
Write-Host "   ssl_certificate C:/nginx/ssl/server-cert.pem;"
Write-Host "   ssl_certificate_key C:/nginx/ssl/server-key.pem;"
Write-Host ""
Write-Host "3. 重新載入 Nginx"
Write-Host "   C:\nginx\nginx.exe -t"
Write-Host "   C:\nginx\nginx.exe -s reload"
Write-Host ""
Write-Host "4. 將憑證加入 Windows 信任清單 (可選)"
Write-Host "   - 雙擊 $CertFile"
Write-Host "   - 點擊「安裝憑證」"
Write-Host "   - 選擇「本機電腦」"
Write-Host "   - 放入「受信任的根憑證授權單位」"
Write-Host ""

Write-Host "注意事項:" -ForegroundColor Yellow
Write-Host "- 這是自簽憑證，瀏覽器會顯示不信任警告"
Write-Host "- 需要將憑證加入客戶端信任清單才能消除警告"
Write-Host "- 私鑰檔案必須妥善保管，不要外洩"
Write-Host ""

Write-Host "完成！" -ForegroundColor Green
