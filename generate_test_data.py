#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成測試資料
創建多個包含目標頁面的多頁 PDF 文件，分布在多個子資料夾中

安全說明:
此腳本用於生成測試數據，使用 random 模組生成隨機內容（文字、顏色、線條等）。
random 模組不用於任何安全目的（如密碼生成、令牌生成等），因此使用是安全的。
"""

import os
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import random  # nosec B311 - 僅用於測試數據生成，非安全目的

# 設定輸出編碼為 UTF-8
if sys.platform == "win32":
    import codecs
    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter("utf-8")(sys.stderr.buffer, 'strict')

def create_test_page(text, page_number, color='white'):
    """
    創建一個測試頁面
    Args:
        text: 頁面上的文字
        page_number: 頁碼
        color: 背景顏色
    Returns:
        PIL Image 對象
    """
    # 創建 A4 大小的圖片（595 x 842 像素，72 DPI）
    width, height = 595, 842
    img = Image.new('RGB', (width, height), color=color)
    draw = ImageDraw.Draw(img)

    try:
        # 嘗試使用系統字體
        font_large = ImageFont.truetype("arial.ttf", 48)
        font_medium = ImageFont.truetype("arial.ttf", 32)
        font_small = ImageFont.truetype("arial.ttf", 24)
    except:
        # 如果找不到字體，使用預設字體
        font_large = ImageFont.load_default()
        font_medium = ImageFont.load_default()
        font_small = ImageFont.load_default()

    # 繪製頁碼
    draw.text((width - 100, height - 50), f"Page {page_number}", fill='black', font=font_small)

    # 繪製主要文字
    text_bbox = draw.textbbox((0, 0), text, font=font_medium)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]
    text_x = (width - text_width) // 2
    text_y = (height - text_height) // 2
    draw.text((text_x, text_y), text, fill='black', font=font_medium)

    # 添加一些隨機線條使頁面看起來不同
    for _ in range(3):
        x1, y1 = random.randint(0, width), random.randint(0, height)  # nosec B311
        x2, y2 = random.randint(0, width), random.randint(0, height)  # nosec B311
        draw.line([(x1, y1), (x2, y2)], fill='lightgray', width=2)

    return img

def create_multi_page_pdf(output_path, target_page_img, target_page_position, total_pages=10):
    """
    創建多頁 PDF 文件
    Args:
        output_path: 輸出路徑
        target_page_img: 目標頁面圖片
        target_page_position: 目標頁面在 PDF 中的位置（1-based）
        total_pages: 總頁數
    """
    pages = []

    for i in range(1, total_pages + 1):
        if i == target_page_position:
            # 插入目標頁面
            pages.append(target_page_img.copy())
        else:
            # 創建普通頁面
            page_texts = [
                "This is a test page",
                "Sample Document",
                "Random Content",
                "Test Data Page",
                "Filler Page"
            ]
            text = random.choice(page_texts)  # nosec B311
            color = random.choice(['white', 'lightblue', 'lightyellow', 'lightgreen'])  # nosec B311
            page = create_test_page(text, i, color)
            pages.append(page)

    # 保存為 PDF
    if pages:
        pages[0].save(
            output_path,
            save_all=True,
            append_images=pages[1:],
            resolution=72.0,
            quality=95
        )
        print(f"✅ 已創建 PDF: {output_path} (共 {total_pages} 頁，目標頁在第 {target_page_position} 頁)")

def generate_test_data():
    """生成測試資料"""
    print("=" * 60)
    print("開始生成測試資料")
    print("=" * 60)

    # 讀取目標頁面圖片
    target_image_path = Path("positive_images.png")
    if not target_image_path.exists():
        print(f"❌ 找不到目標頁面圖片: {target_image_path}")
        return False

    target_img = Image.open(target_image_path).convert('RGB')
    print(f"✅ 已載入目標頁面圖片: {target_image_path}")

    # 創建主測試資料夾
    base_dir = Path("files")
    base_dir.mkdir(exist_ok=True)

    # 定義子資料夾結構
    folder_structure = [
        "batch1/2024",
        "batch1/2025",
        "batch2/Q1",
        "batch2/Q2",
        "batch3/reports",
        "batch3/documents/important",
        "batch4",
        "batch5/archive/old"
    ]

    # 創建資料夾並生成 PDF
    pdf_count = 0

    for folder in folder_structure:
        folder_path = base_dir / folder
        folder_path.mkdir(parents=True, exist_ok=True)

        # 在每個資料夾中生成 2-4 個 PDF
        num_pdfs = random.randint(2, 4)  # nosec B311

        for i in range(num_pdfs):
            pdf_count += 1
            pdf_name = f"document_{pdf_count:03d}.pdf"
            pdf_path = folder_path / pdf_name

            # 隨機選擇 PDF 的頁數和目標頁位置
            total_pages = random.randint(5, 15)  # nosec B311
            target_position = random.randint(1, total_pages)  # nosec B311

            create_multi_page_pdf(
                str(pdf_path),
                target_img,
                target_position,
                total_pages
            )

    print("\n" + "=" * 60)
    print("測試資料生成完成")
    print("=" * 60)
    print(f"總共創建了 {pdf_count} 個 PDF 文件")
    print(f"分布在 {len(folder_structure)} 個資料夾中")
    print(f"基礎路徑: {base_dir.absolute()}")
    print("\n資料夾結構:")
    for folder in sorted(folder_structure):
        folder_path = base_dir / folder
        pdf_files = list(folder_path.glob("*.pdf"))
        print(f"  📁 {folder}: {len(pdf_files)} 個 PDF 文件")

    # 創建一個包含關鍵字的測試頁面
    print("\n正在生成包含關鍵字的目標頁面...")
    create_target_page_with_keywords(base_dir)

    return True

def create_target_page_with_keywords(base_dir):
    """創建包含關鍵字的目標頁面"""

    # 讀取原始目標圖片
    target_img = Image.open("positive_images.png").convert('RGB')

    # 在圖片上添加一些測試關鍵字
    draw = ImageDraw.Draw(target_img)

    try:
        font_large = ImageFont.truetype("arial.ttf", 32)
        font_medium = ImageFont.truetype("arial.ttf", 24)
    except:
        font_large = ImageFont.load_default()
        font_medium = ImageFont.load_default()

    # 添加測試關鍵字（模擬 OCR 可識別的文字）
    keywords_data = {
        "製作日期": "2007/04/10",
        "報告編號": "A123CC456-789",
        "申請者名稱": "車安有限公司",
        "申請者地址": "台中市大里區",
        "廠牌": "MITSUBA"
    }

    # 在圖片底部添加關鍵字（白色背景黑色文字）
    y_offset = target_img.height - 200
    for key, value in keywords_data.items():
        text = f"{key}: {value}"
        draw.text((20, y_offset), text, fill='black', font=font_medium)
        y_offset += 35

    # 保存修改後的圖片
    enhanced_target_path = base_dir / "enhanced_target.png"
    target_img.save(enhanced_target_path)
    print(f"✅ 已創建增強目標頁面: {enhanced_target_path}")

    # 使用增強後的目標頁面創建幾個特殊的 PDF
    special_folder = base_dir / "special_documents"
    special_folder.mkdir(exist_ok=True)

    for i in range(3):
        pdf_name = f"special_doc_{i+1}.pdf"
        pdf_path = special_folder / pdf_name

        total_pages = random.randint(8, 12)  # nosec B311
        target_position = random.randint(2, total_pages - 1)  # nosec B311

        create_multi_page_pdf(
            str(pdf_path),
            target_img,
            target_position,
            total_pages
        )

    print(f"✅ 已在 special_documents 資料夾創建 3 個包含關鍵字的 PDF")

def create_readme():
    """創建測試資料說明文件"""
    readme_content = """# 測試資料說明

## 資料結構

此測試資料集用於測試批次任務管理系統的以下功能：

1. **遞迴掃描功能**
   - 測試系統是否能正確掃描所有子資料夾
   - 驗證深層巢狀資料夾的處理能力

2. **第一階段（CLIP 匹配）**
   - 每個 PDF 包含 5-15 頁
   - 目標頁面隨機插入在不同位置
   - 測試系統是否能正確找出目標頁面

3. **第二階段（OCR 識別）**
   - special_documents 資料夾包含帶有關鍵字的文件
   - 可用於測試關鍵字提取功能

## 使用方式

### 1. 生成測試資料
```bash
python generate_test_data.py
```

### 2. 創建批次任務
- 任務名稱：測試批次處理
- 來源路徑：`完整路徑\\files`

### 3. 配置第一階段
- 正例範本：使用 positive_images.png 或 enhanced_target.png
- 正例閾值：0.25
- 反例閾值：0.30

### 4. 配置第二階段（針對 special_documents）
- 關鍵字：製作日期、報告編號、申請者名稱、申請者地址、廠牌

## 預期結果

- 應該掃描到所有資料夾中的所有 PDF 文件
- 第一階段應該為每個 PDF 找到包含目標頁面的頁碼
- special_documents 中的文件應該能成功提取關鍵字

## 檔案統計

請查看執行 generate_test_data.py 後的輸出統計資訊。
"""

    readme_path = Path("files") / "README.md"
    readme_path.write_text(readme_content, encoding='utf-8')
    print(f"\n✅ 已創建說明文件: {readme_path}")

if __name__ == "__main__":
    success = generate_test_data()

    if success:
        create_readme()
        print("\n🎉 所有測試資料已成功生成！")
        print("\n下一步:")
        print("1. 啟動服務: python start_services.py")
        print("2. 訪問批次任務管理: http://localhost:8080/batch-tasks")
        print("3. 創建新任務並指定 files 資料夾的完整路徑")
    else:
        print("\n❌ 測試資料生成失敗")
