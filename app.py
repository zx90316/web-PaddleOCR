#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PaddleOCR Web Interface
Copyright (c) 2025

This project provides a web interface for PaddleOCR.
This software uses PaddleOCR, which is licensed under Apache License 2.0.

PaddleOCR Copyright (c) 2020 PaddlePaddle Authors. All Rights Reserved.
Licensed under the Apache License, Version 2.0.
See: https://github.com/PaddlePaddle/PaddleOCR

本項目僅為 PaddleOCR 的網頁界面封裝，核心 OCR 功能由 PaddleOCR 提供。
"""
import torch
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import List, Optional
import json
import os
import tempfile
from paddlex import create_pipeline
import shutil
import numpy as np
from PIL import Image
from transformers import CLIPProcessor, CLIPModel
import fitz  # PyMuPDF
import io

# 初始化 FastAPI 應用程式
app = FastAPI(title="PaddleOCR 圖片識別服務", description="上傳圖片並提取指定的關鍵字")

# 設定靜態檔案服務
output_dir = "output"
os.makedirs(output_dir, exist_ok=True)

def clear_output_dir():
    shutil.rmtree(output_dir)
    os.makedirs(output_dir)

clear_output_dir()

app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/output", StaticFiles(directory=output_dir), name="output")

# 設定模板引擎
templates = Jinja2Templates(directory="templates")

# 初始化 PaddleOCR 管線
pipeline = create_pipeline(
    pipeline="./PP-ChatOCRv4-doc.yaml",
    initial_predictor=False
    )

# 初始化 CLIP 模型（延遲載入）
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

# 請求模型
class OCRRequest(BaseModel):
    key_list: List[str]
    use_doc_orientation_classify: Optional[bool] = False
    use_doc_unwarping: Optional[bool] = False

# 響應模型
class OCRResponse(BaseModel):
    success: bool
    data: Optional[dict] = None
    error: Optional[str] = None

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

def find_best_matching_page(pdf_path, positive_images, negative_images, model, processor, positive_threshold=0.25, negative_threshold=0.30):
    """
    從 PDF 中找出最匹配的頁面
    Args:
        pdf_path: PDF 文件路徑
        positive_images: 正例範本圖像列表 (PIL Image 對象)
        negative_images: 反例範本圖像列表 (PIL Image 對象)
        model: CLIP 模型
        processor: CLIP 處理器
        positive_threshold: 正例相似度閾值
        negative_threshold: 反例相似度閾值
    Returns:
        (best_page_index, best_page_image, best_score, all_scores)
    """
    # 將 PDF 轉換為圖像
    pages = pdf_to_images(pdf_path, dpi=200)

    best_page_index = -1
    best_score = -1
    best_page_image = None
    all_scores = []

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

    return best_page_index, best_page_image, best_score, all_scores

def perform_ocr_on_file(
    file_path: str,
    key_list_parsed: list,
    original_filename: str,
    use_doc_orientation_classify: bool = False,
    use_doc_unwarping: bool = False,
    use_textline_orientation: bool = False,
    use_seal_recognition: bool = False,
    use_table_recognition: bool = True,
    use_llm: bool = True,
):
    """
    對檔案執行 OCR 處理的核心邏輯
    Args:
        file_path: 圖片或PDF檔案路徑
        key_list_parsed: 已解析的關鍵字列表
        original_filename: 原始檔案名
        其他參數: OCR 處理選項
    Returns:
        處理結果字典
    """
    # 執行視覺預測
    visual_predict_res = pipeline.visual_predict(
        input=file_path,
        use_doc_orientation_classify=use_doc_orientation_classify,
        use_doc_unwarping=use_doc_unwarping,
        use_textline_orientation=use_textline_orientation,
        use_common_ocr=True,
        use_seal_recognition=use_seal_recognition,
        use_table_recognition=use_table_recognition,
    )

    visual_info_list = []
    output_images = []
    for res in visual_predict_res:
        visual_info_list.append(res["visual_info"])
        layout_parsing_result = res["layout_parsing_result"]

        # 保存處理結果圖片並記錄文件名
        output_dir = "output"
        os.makedirs(output_dir, exist_ok=True)

        # 獲取輸入檔案的檔名資訊（用於預測生成的檔案名）
        from pathlib import Path
        temp_path = Path(file_path)
        input_stem = temp_path.stem

        # 獲取保存前的檔案列表
        files_before = set(os.listdir(output_dir)) if os.path.exists(output_dir) else set()

        # 執行保存操作
        layout_parsing_result.save_to_img(output_dir)

        # 獲取保存後的檔案列表
        files_after = set(os.listdir(output_dir)) if os.path.exists(output_dir) else set()
        new_files = files_after - files_before

        # 找出包含 input_stem 的新檔案
        for file_name in new_files:
            if input_stem in file_name and file_name.endswith('.png'):
                output_images.append(file_name)

    # 執行聊天查詢
    if use_llm:
        chat_result = pipeline.chat(
            key_list=key_list_parsed,
            visual_info=visual_info_list
        )

    # 組合回應資料
    response_data = {
        "chat_result": chat_result["chat_res"] if use_llm else None,
        "visual_info_list": visual_info_list,
        "key_list": key_list_parsed,
        "output_images": output_images,
        "original_filename": original_filename,
        "settings": {
            "use_doc_orientation_classify": use_doc_orientation_classify,
            "use_doc_unwarping": use_doc_unwarping,
            "use_textline_orientation": use_textline_orientation,
            "use_seal_recognition": use_seal_recognition,
            "use_table_recognition": use_table_recognition,
            "use_llm": use_llm
        }
    }

    return response_data

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """返回上傳頁面"""
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/ocr", response_model=OCRResponse)
async def process_ocr(
    file: UploadFile = File(...),
    key_list: str = Form(...),
    use_doc_orientation_classify: bool = Form(False),
    use_doc_unwarping: bool = Form(False),
    use_textline_orientation: bool = Form(False),
    use_seal_recognition: bool = Form(False),
    use_table_recognition: bool = Form(True),
    use_llm: bool = Form(True),
):
    """處理圖片 OCR 請求"""
    temp_file_path = None
    try:
        # 檢查檔案類型
        if not (file.content_type.startswith('image/') or file.content_type == 'application/pdf'):
            raise HTTPException(status_code=400, detail="請上傳有效的圖片檔案或PDF檔案")

        # 解析關鍵字列表
        try:
            key_list_parsed = json.loads(key_list)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="關鍵字列表格式錯誤")

        # 創建臨時檔案
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_file_path = temp_file.name

        # 調用核心 OCR 處理函數
        response_data = perform_ocr_on_file(
            file_path=temp_file_path,
            key_list_parsed=key_list_parsed,
            original_filename=file.filename,
            use_doc_orientation_classify=use_doc_orientation_classify,
            use_doc_unwarping=use_doc_unwarping,
            use_textline_orientation=use_textline_orientation,
            use_seal_recognition=use_seal_recognition,
            use_table_recognition=use_table_recognition,
            use_llm=use_llm
        )

        return OCRResponse(success=True, data=response_data)

    except HTTPException:
        raise
    except Exception as e:
        return OCRResponse(success=False, error=f"處理過程中發生錯誤: {str(e)}")
    finally:
        # 清理臨時檔案
        if temp_file_path and os.path.exists(temp_file_path):
            os.unlink(temp_file_path)

@app.post("/ocr-with-matching", response_model=OCRResponse)
async def process_ocr_with_matching(
    pdf_file: UploadFile = File(...),
    positive_templates: List[UploadFile] = File(...),
    negative_templates: List[UploadFile] = File(default=[]),
    key_list: str = Form(...),
    use_doc_orientation_classify: bool = Form(False),
    use_doc_unwarping: bool = Form(False),
    use_textline_orientation: bool = Form(False),
    use_seal_recognition: bool = Form(False),
    use_table_recognition: bool = Form(True),
    use_llm: bool = Form(True),
    positive_threshold: float = Form(0.25),
    negative_threshold: float = Form(0.30),
):
    """
    處理 PDF 頁面匹配和 OCR 請求
    1. 接受 PDF 文件、正例範本圖片、反例範本圖片
    2. 使用 CLIP 找出最相似的頁面
    3. 對該頁面執行 OCR 處理
    """
    temp_pdf_path = None
    temp_positive_paths = []
    temp_negative_paths = []
    temp_matched_page_path = None

    try:
        # 檢查 PDF 檔案類型
        if pdf_file.content_type != 'application/pdf':
            raise HTTPException(status_code=400, detail="請上傳有效的 PDF 檔案")

        # 解析關鍵字列表
        try:
            key_list_parsed = json.loads(key_list)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="關鍵字列表格式錯誤")

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
            if not template.content_type.startswith('image/'):
                raise HTTPException(status_code=400, detail=f"正例範本 {template.filename} 不是有效的圖片檔案")
            content = await template.read()
            image = Image.open(io.BytesIO(content)).convert('RGB')
            positive_images.append(image)

        if not positive_images:
            raise HTTPException(status_code=400, detail="至少需要提供一張正例範本圖片")

        # 讀取反例範本圖片（可選）
        negative_images = []
        for template in negative_templates:
            if template.content_type.startswith('image/'):
                content = await template.read()
                image = Image.open(io.BytesIO(content)).convert('RGB')
                negative_images.append(image)

        # 找出最匹配的頁面
        print(f"開始分析 PDF，正例範本數量: {len(positive_images)}, 反例範本數量: {len(negative_images)}")
        best_page_index, best_page_image, best_score, all_scores = find_best_matching_page(
            temp_pdf_path,
            positive_images,
            negative_images,
            model,
            processor,
            positive_threshold,
            negative_threshold
        )

        if best_page_index == -1:
            return OCRResponse(
                success=False,
                error=f"未找到符合條件的頁面。請調整閾值參數。所有頁面分數: {all_scores}"
            )

        print(f"找到最佳匹配頁面: 第 {best_page_index + 1} 頁, 分數: {best_score:.4f}")

        # 將匹配的頁面保存為臨時圖片
        with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as temp_img:
            best_page_image.save(temp_img.name, 'PNG')
            temp_matched_page_path = temp_img.name

        # 調用核心 OCR 處理函數
        ocr_response_data = perform_ocr_on_file(
            file_path=temp_matched_page_path,
            key_list_parsed=key_list_parsed,
            original_filename=pdf_file.filename,
            use_doc_orientation_classify=use_doc_orientation_classify,
            use_doc_unwarping=use_doc_unwarping,
            use_textline_orientation=use_textline_orientation,
            use_seal_recognition=use_seal_recognition,
            use_table_recognition=use_table_recognition,
            use_llm=use_llm
        )

        # 在 OCR 結果中添加頁面匹配資訊
        response_data = {
            **ocr_response_data,  # 包含所有 OCR 結果
            "matched_page_number": best_page_index + 1,
            "matching_score": float(best_score),
            "all_page_scores": all_scores,
        }

        # 更新 settings 以包含匹配閾值
        response_data["settings"]["positive_threshold"] = positive_threshold
        response_data["settings"]["negative_threshold"] = negative_threshold

        return OCRResponse(success=True, data=response_data)

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_detail = f"處理過程中發生錯誤: {str(e)}\n{traceback.format_exc()}"
        print(error_detail)
        return OCRResponse(success=False, error=error_detail)

    finally:
        # 清理臨時檔案
        for path in [temp_pdf_path, temp_matched_page_path] + temp_positive_paths + temp_negative_paths:
            if path and os.path.exists(path):
                try:
                    os.unlink(path)
                except Exception as e:
                    print(f"清理臨時檔案失敗: {path}, 錯誤: {e}")

@app.get("/health")
async def health_check():
    """健康檢查端點"""
    return {"status": "healthy", "message": "PaddleOCR 服務運行正常"}

if __name__ == "__main__":
    import uvicorn
    print("🚀 啟動 PaddleOCR 網站服務...")
    print("🌐 請訪問: http://localhost:8080")
    uvicorn.run(app, host="0.0.0.0", port=8080)