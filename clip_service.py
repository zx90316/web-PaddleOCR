#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CLIP 圖像匹配服務
獨立運行以避免與 PaddlePaddle 的 cuDNN 衝突
"""

from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import torch
from transformers import CLIPProcessor, CLIPModel
from PIL import Image
import fitz  # PyMuPDF
import io
import tempfile
import os
import base64
import httpx  # 用於調用 PaddleOCR 服務

app = FastAPI(title="CLIP 圖像匹配服務", description="基於 CLIP 的圖像相似度匹配服務")

# 全局模型變量（延遲載入）
clip_model = None
clip_processor = None
device = None # 新增一個變數來存放設備資訊

# PaddleOCR 服務配置
PADDLEOCR_SERVICE_URL = os.getenv("PADDLEOCR_SERVICE_URL", "http://localhost:8080")

def get_clip_model():
    """延遲載入 CLIP 模型"""
    global clip_model, clip_processor ,device
    if clip_model is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"偵測到設備: {device}。準備載入 CLIP 模型...")
        print("載入 CLIP 模型...")

        # 使用 local_files_only=True 確保只從本地緩存加載，不會從網絡下載
        # 這已經滿足安全要求，因為不會下載任意版本的模型
        clip_model = CLIPModel.from_pretrained(
            "openai/clip-vit-base-patch32",
            local_files_only=True,
            # 如果需要固定版本，可以指定 revision
            # revision="specific_commit_hash"
        )  # nosec B615 - 使用 local_files_only=True，不會從網絡下載
        clip_processor = CLIPProcessor.from_pretrained(
            "openai/clip-vit-base-patch32",
            local_files_only=True
        )  # nosec B615 - 使用 local_files_only=True，不會從網絡下載

        clip_model.to(device)
        print("CLIP 模型載入完成")
    return clip_model, clip_processor , device

def compute_image_similarity(image, template_images, model, processor):
    """
    計算圖像與範本圖像的相似度
    Args:
        image: PIL Image 對象
        template_images: 範本圖像列表 (PIL Image 對象)
        model: CLIP 模型
        processor: CLIP 處理器
    Returns:
        平均相似度分數
    """
    # 處理圖像
    inputs = processor(images=[image] + template_images, return_tensors="pt", padding=True)
    inputs = {key: tensor.to(device) for key, tensor in inputs.items()}

    with torch.no_grad():
        image_features = model.get_image_features(**inputs)

    # 正規化特徵向量
    image_features = image_features / image_features.norm(dim=-1, keepdim=True)

    # 計算查詢圖像與所有範本的相似度
    query_features = image_features[0:1]
    template_features = image_features[1:]

    similarities = torch.matmul(query_features, template_features.T).squeeze()

    # 如果只有一個範本，確保返回標量
    if len(template_images) == 1:
        return similarities.item()

    # 返回最高的相似度分數
    return similarities.max().item()

def pdf_to_images(pdf_path, dpi=200):
    """
    使用 PyMuPDF 將 PDF 轉換為圖像列表
    Args:
        pdf_path: PDF 文件路徑
        dpi: 圖像解析度
    Returns:
        PIL Image 對象列表
    """
    pdf_document = fitz.open(pdf_path)
    images = []

    # 計算縮放因子（DPI / 72，因為 PDF 默認是 72 DPI）
    zoom = dpi / 72
    mat = fitz.Matrix(zoom, zoom)

    for page_num in range(len(pdf_document)):
        page = pdf_document[page_num]
        pix = page.get_pixmap(matrix=mat)

        # 轉換為 PIL Image
        img_data = pix.tobytes("png")
        img = Image.open(io.BytesIO(img_data))
        images.append(img)

    pdf_document.close()
    return images

async def check_page_voided(page_image: Image.Image) -> tuple[bool, dict]:
    """
    檢查頁面是否包含廢止關鍵字
    Args:
        page_image: PIL Image 對象
    Returns:
        (is_voided, ocr_result) - 是否為廢止頁面, OCR 結果
    """
    try:
        # 將圖片轉換為 bytes
        img_byte_arr = io.BytesIO()
        page_image.save(img_byte_arr, format='PNG')
        img_byte_arr.seek(0)

        # 調用 PaddleOCR 服務進行 OCR
        async with httpx.AsyncClient(timeout=600.0, trust_env=False) as client:
            files = {
                'file': ('page.png', img_byte_arr, 'image/png')
            }
            data = {
                'key_list': '[]',  # 不需要提取關鍵字
                'use_llm': 'false'  # 不使用 LLM
            }

            response = await client.post(
                f"{PADDLEOCR_SERVICE_URL}/ocr",
                files=files,
                data=data
            )

            if response.status_code != 200:
                print(f"OCR 服務調用失敗: {response.text}")
                return False, {}

            result = response.json()

            if not result.get('success'):
                print(f"OCR 處理失敗: {result.get('error')}")
                return False, {}

            # 從 visual_info_list 中提取所有文字 - 將整個 visual_info 轉成純文字
            visual_info_list = result.get('data', {}).get('visual_info_list', [])

            # 將 visual_info 轉換為字串
            import json
            all_text = json.dumps(visual_info_list, ensure_ascii=False)
            all_text = all_text.upper()  # 轉為大寫便於比對

            # 檢查是否包含廢止關鍵字
            void_keywords = ['廢止', '作廢', 'VOID', 'CANCELLED', 'CANCELED']
            is_voided = any(keyword.upper() in all_text for keyword in void_keywords)

            return is_voided, {
                'is_voided': is_voided,
                'found_keywords': [kw for kw in void_keywords if kw.upper() in all_text],
                'text_snippet': all_text[:200]  # 保存前 200 個字元作為預覽
            }

    except Exception as e:
        print(f"廢止檢測失敗: {str(e)}")
        return False, {'error': str(e)}

class PageMatchRequest(BaseModel):
    """頁面匹配請求模型"""
    positive_threshold: float = 0.95
    negative_threshold: float = 0.55
    skip_voided: bool = False  # 是否跳過廢止頁面
    top_n_for_void_check: int = 5  # 檢查前 N 個候選頁面是否為廢止

class PageMatchResponse(BaseModel):
    """頁面匹配響應模型"""
    success: bool
    matched_page_number: Optional[int] = None
    matching_score: Optional[float] = None
    matched_page_base64: Optional[str] = None  # Base64 編碼的圖像
    all_page_scores: Optional[List[dict]] = None
    voided_pages_checked: Optional[List[dict]] = None  # 被跳過的廢止頁面資訊
    error: Optional[str] = None

@app.post("/match-page", response_model=PageMatchResponse)
async def match_pdf_page(
    pdf_file: UploadFile = File(...),
    positive_templates: List[UploadFile] = File(...),
    negative_templates: List[UploadFile] = File(default=[]),
    positive_threshold: float = Form(0.95),
    negative_threshold: float = Form(0.55),
    skip_voided: bool = Form(False),
    top_n_for_void_check: int = Form(5),
):
    """
    找出 PDF 中最匹配的頁面
    如果 skip_voided 為 True，則會檢查 TOP N 候選頁面是否包含廢止關鍵字
    """
    temp_pdf_path = None

    try:
        # 檢查 PDF 檔案類型
        if pdf_file.content_type != 'application/pdf':
            raise HTTPException(status_code=400, detail="請上傳有效的 PDF 檔案")

        # 載入 CLIP 模型
        model, processor , current_device = get_clip_model()

        # 保存 PDF 到臨時檔案
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_pdf:
            content = await pdf_file.read()
            temp_pdf.write(content)
            temp_pdf_path = temp_pdf.name

        # 讀取正例範本圖片
        positive_images = []
        for template in positive_templates:
            try:
                # 檢查文件名
                if not template.filename:
                    raise HTTPException(status_code=400, detail="正例範本文件名為空")
                
                # 讀取文件內容
                content = await template.read()
                
                # 檢查內容是否為空
                if not content or len(content) == 0:
                    raise HTTPException(status_code=400, detail=f"正例範本 {template.filename} 內容為空")
                
                # 嘗試打開圖片
                image = Image.open(io.BytesIO(content)).convert('RGB')
                positive_images.append(image)
                print(f"成功載入正例範本: {template.filename}")
                
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(
                    status_code=400, 
                    detail=f"無法讀取正例範本 {template.filename}: {str(e)}。請確認上傳的是有效的圖片檔案（PNG、JPG 等格式）"
                )

        if not positive_images:
            raise HTTPException(status_code=400, detail="至少需要提供一張正例範本圖片")

        # 讀取反例範本圖片（可選）
        negative_images = []
        for template in negative_templates:
            try:
                # 檢查是否有實際的文件內容
                if not template.filename:
                    continue
                    
                content = await template.read()
                
                # 檢查內容是否為空
                if not content or len(content) == 0:
                    print(f"警告: 反例範本 {template.filename} 內容為空，跳過")
                    continue
                
                # 嘗試打開圖片
                image = Image.open(io.BytesIO(content)).convert('RGB')
                negative_images.append(image)
                print(f"成功載入反例範本: {template.filename}")
                
            except Exception as e:
                # 如果某個反例範本無法載入，只記錄警告但繼續處理
                print(f"警告: 無法載入反例範本 {template.filename}: {str(e)}，跳過此文件")
                continue

        # 將 PDF 轉換為圖像
        pages = pdf_to_images(temp_pdf_path, dpi=200)

        all_scores = []
        candidates = []  # 候選頁面列表

        # 找出最匹配的頁面
        print(f"開始分析 PDF，正例範本數量: {len(positive_images)}, 反例範本數量: {len(negative_images)}")

        for idx, page_image in enumerate(pages):
            # 計算與正例的相似度
            pos_similarity = compute_image_similarity(page_image, positive_images, model, processor)

            # 計算與反例的相似度（如果有提供）
            neg_similarity = 0
            if negative_images:
                neg_similarity = compute_image_similarity(page_image, negative_images, model, processor)

            all_scores.append({
                "page": idx + 1,
                "positive_similarity": float(pos_similarity),
                "negative_similarity": float(neg_similarity),
            })

            # 檢查是否符合條件：正例相似度高於閾值，且反例相似度低於閾值
            if pos_similarity >= positive_threshold and neg_similarity <= negative_threshold:
                candidates.append({
                    "page_index": idx,
                    "page_image": page_image,
                    "positive_similarity": pos_similarity,
                    "negative_similarity": neg_similarity
                })

        if not candidates:
            # 找出最高的正例分數
            max_pos = max((s["positive_similarity"] for s in all_scores), default=0)

            # 找出達到正例閾值的頁面，並顯示它們的反例分數
            qualified_pos_pages = [s for s in all_scores if s["positive_similarity"] >= positive_threshold]

            if qualified_pos_pages:
                # 有達到正例閾值但反例不符合的情況
                min_neg_in_qualified = min((s["negative_similarity"] for s in qualified_pos_pages))
                error_msg = f"未找到符合條件的頁面。有 {len(qualified_pos_pages)} 頁達到正例閾值 >= {positive_threshold}，但它們的反例分數（最低: {min_neg_in_qualified:.4f}）都未低於反例閾值 <= {negative_threshold}。請降低反例閾值。"
            else:
                # 沒有任何頁面達到正例閾值
                error_msg = f"未找到符合條件的頁面。所有頁面的正例分數（最高: {max_pos:.4f}）都未達到正例閾值 >= {positive_threshold}。請降低正例閾值。"

            return PageMatchResponse(
                success=False,
                error=error_msg,
                all_page_scores=all_scores
            )

        # 按正例分數排序，選出 TOP N 候選頁面
        candidates.sort(key=lambda x: x["positive_similarity"], reverse=True)

        voided_pages_info = []  # 記錄被跳過的廢止頁面
        best_candidate = None

        # 如果啟用跳過廢止功能
        if skip_voided:
            print(f"啟用廢止檢測，將檢查前 {top_n_for_void_check} 個候選頁面")

            # 檢查 TOP N 候選頁面
            check_count = min(top_n_for_void_check, len(candidates))

            for i in range(check_count):
                candidate = candidates[i]
                page_num = candidate["page_index"] + 1

                print(f"檢查第 {page_num} 頁是否為廢止頁面...")
                is_voided, void_info = await check_page_voided(candidate["page_image"])

                if is_voided:
                    print(f"  第 {page_num} 頁包含廢止關鍵字，跳過")
                    voided_pages_info.append({
                        "page": page_num,
                        "positive_similarity": float(candidate["positive_similarity"]),
                        "negative_similarity": float(candidate["negative_similarity"]),
                        "void_detection": void_info
                    })
                else:
                    print(f"  第 {page_num} 頁未包含廢止關鍵字，選為最佳匹配")
                    best_candidate = candidate
                    break

            # 如果所有 TOP N 候選都是廢止頁面
            if best_candidate is None:
                # 檢查是否還有其他候選
                if len(candidates) > check_count:
                    print(f"前 {check_count} 個候選都是廢止頁面，從剩餘候選中選擇")
                    # 從剩餘候選中選出反例分數最低的
                    remaining_candidates = candidates[check_count:]
                    top5_remaining = remaining_candidates[:5]
                    best_candidate = min(top5_remaining, key=lambda x: x["negative_similarity"])
                else:
                    return PageMatchResponse(
                        success=False,
                        error=f"前 {check_count} 個候選頁面都包含廢止關鍵字，沒有找到有效頁面",
                        voided_pages_checked=voided_pages_info,
                        all_page_scores=all_scores
                    )
        else:
            # 未啟用跳過廢止功能，使用原邏輯
            # 從 TOP 5 中選出反例分數最低的
            top5_candidates = candidates[:5]
            best_candidate = min(top5_candidates, key=lambda x: x["negative_similarity"])

        best_page_index = best_candidate["page_index"]
        best_page_image = best_candidate["page_image"]

        print(f"找到最佳匹配頁面: 第 {best_page_index + 1} 頁")
        print(f"  正例相似度: {best_candidate['positive_similarity']:.4f}")
        print(f"  反例相似度: {best_candidate['negative_similarity']:.4f}")
        print(f"  候選頁面總數: {len(candidates)}")
        if voided_pages_info:
            print(f"  跳過的廢止頁面數: {len(voided_pages_info)}")

        # 將匹配的頁面轉換為 Base64
        buffered = io.BytesIO()
        best_page_image.save(buffered, format="PNG")
        img_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')

        return PageMatchResponse(
            success=True,
            matched_page_number=best_page_index + 1,
            matching_score=float(best_candidate["positive_similarity"]),
            matched_page_base64=img_base64,
            all_page_scores=all_scores,
            voided_pages_checked=voided_pages_info if voided_pages_info else None
        )

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_detail = f"處理過程中發生錯誤: {str(e)}\n{traceback.format_exc()}"
        print(error_detail)
        return PageMatchResponse(success=False, error=error_detail)

    finally:
        # 清理臨時檔案
        if temp_pdf_path and os.path.exists(temp_pdf_path):
            try:
                os.unlink(temp_pdf_path)
            except Exception as e:
                print(f"清理臨時檔案失敗: {temp_pdf_path}, 錯誤: {e}")

@app.get("/health")
async def health_check():
    """健康檢查端點"""
    return {"status": "healthy", "message": "CLIP 服務運行正常"}

if __name__ == "__main__":
    import uvicorn
    import os

    # 從環境變量讀取配置，默認只綁定 localhost
    # 生產環境若需要對外訪問，請設置環境變量 CLIP_HOST=0.0.0.0
    host = os.getenv("CLIP_HOST", "127.0.0.1")
    port = int(os.getenv("CLIP_PORT", "8081"))

    print("🚀 啟動 CLIP 圖像匹配服務...")
    print(f"🌐 服務地址: http://{host}:{port}")
    print(f"🌐 本機訪問: http://localhost:{port}")

    # nosec B104: 從環境變量讀取 host，默認為安全的 127.0.0.1
    # 只有明確設置環境變量才會綁定到所有接口，並會顯示警告
    if host == "0.0.0.0":  # nosec B104
        print("⚠️  警告: 服務綁定到所有網絡接口 (0.0.0.0)，請確保已設置適當的防火牆規則")

    uvicorn.run(app, host=host, port=port)
