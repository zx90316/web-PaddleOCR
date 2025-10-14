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

app = FastAPI(title="CLIP 圖像匹配服務", description="基於 CLIP 的圖像相似度匹配服務")

# 全局模型變量（延遲載入）
clip_model = None
clip_processor = None

def get_clip_model():
    """延遲載入 CLIP 模型"""
    global clip_model, clip_processor
    if clip_model is None:
        print("載入 CLIP 模型...")
        clip_model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
        clip_processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
        print("CLIP 模型載入完成")
    return clip_model, clip_processor

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

    # 返回平均相似度
    return similarities.mean().item()

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

class PageMatchRequest(BaseModel):
    """頁面匹配請求模型"""
    positive_threshold: float = 0.25
    negative_threshold: float = 0.30

class PageMatchResponse(BaseModel):
    """頁面匹配響應模型"""
    success: bool
    matched_page_number: Optional[int] = None
    matching_score: Optional[float] = None
    matched_page_base64: Optional[str] = None  # Base64 編碼的圖像
    all_page_scores: Optional[List[dict]] = None
    error: Optional[str] = None

@app.post("/match-page", response_model=PageMatchResponse)
async def match_pdf_page(
    pdf_file: UploadFile = File(...),
    positive_templates: List[UploadFile] = File(...),
    negative_templates: List[UploadFile] = File(default=[]),
    positive_threshold: float = Form(0.25),
    negative_threshold: float = Form(0.30),
):
    """
    找出 PDF 中最匹配的頁面
    """
    temp_pdf_path = None

    try:
        # 檢查 PDF 檔案類型
        if pdf_file.content_type != 'application/pdf':
            raise HTTPException(status_code=400, detail="請上傳有效的 PDF 檔案")

        # 載入 CLIP 模型
        model, processor = get_clip_model()

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

        best_page_index = -1
        best_score = -1
        best_page_image = None
        all_scores = []

        # 找出最匹配的頁面
        print(f"開始分析 PDF，正例範本數量: {len(positive_images)}, 反例範本數量: {len(negative_images)}")

        for idx, page_image in enumerate(pages):
            # 計算與正例的相似度
            pos_similarity = compute_image_similarity(page_image, positive_images, model, processor)

            # 計算與反例的相似度（如果有提供）
            neg_similarity = 0
            if negative_images:
                neg_similarity = compute_image_similarity(page_image, negative_images, model, processor)

            # 計算綜合分數：正例相似度 - 反例相似度
            score = pos_similarity - neg_similarity

            all_scores.append({
                "page": idx + 1,
                "positive_similarity": float(pos_similarity),
                "negative_similarity": float(neg_similarity),
                "final_score": float(score)
            })

            # 檢查是否符合條件：正例相似度高於閾值，反例相似度低於閾值
            if pos_similarity >= positive_threshold and neg_similarity <= negative_threshold:
                if score > best_score:
                    best_score = score
                    best_page_index = idx
                    best_page_image = page_image

        if best_page_index == -1:
            return PageMatchResponse(
                success=False,
                error=f"未找到符合條件的頁面。請調整閾值參數。",
                all_page_scores=all_scores
            )

        print(f"找到最佳匹配頁面: 第 {best_page_index + 1} 頁, 分數: {best_score:.4f}")

        # 將匹配的頁面轉換為 Base64
        buffered = io.BytesIO()
        best_page_image.save(buffered, format="PNG")
        img_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')

        return PageMatchResponse(
            success=True,
            matched_page_number=best_page_index + 1,
            matching_score=float(best_score),
            matched_page_base64=img_base64,
            all_page_scores=all_scores
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
    print("🚀 啟動 CLIP 圖像匹配服務...")
    print("🌐 請訪問: http://localhost:8081")
    uvicorn.run(app, host="0.0.0.0", port=8081)
