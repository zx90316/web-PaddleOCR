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
import io
import uuid
from datetime import datetime
import database
import httpx  # 用於調用 CLIP 服務
import base64

# 初始化 FastAPI 應用程式
app = FastAPI(title="PaddleOCR 圖片識別服務", description="上傳圖片並提取指定的關鍵字")

# 設定靜態檔案服務
output_dir = "output"
os.makedirs(output_dir, exist_ok=True)

# 初始化資料庫
database.init_database()

app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/output", StaticFiles(directory=output_dir), name="output")

# 設定模板引擎
templates = Jinja2Templates(directory="templates")

# 初始化 PaddleOCR 管線
pipeline = create_pipeline(
    pipeline="./PP-ChatOCRv4-doc.yaml",
    initial_predictor=False
    )

# CLIP 服務配置
CLIP_SERVICE_URL = os.getenv("CLIP_SERVICE_URL", "http://localhost:8081")

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

async def call_clip_service(pdf_file_path: str, positive_templates: List[UploadFile], negative_templates: List[UploadFile], positive_threshold: float, negative_threshold: float):
    """
    調用 CLIP 服務進行頁面匹配
    Args:
        pdf_file_path: PDF 文件路徑
        positive_templates: 正例範本圖片列表
        negative_templates: 反例範本圖片列表
        positive_threshold: 正例相似度閾值
        negative_threshold: 反例相似度閾值
    Returns:
        (matched_page_number, matched_page_image, matching_score, all_scores)
    """
    async with httpx.AsyncClient(timeout=300.0) as client:
        # 準備文件
        files = []

        # PDF 文件
        with open(pdf_file_path, 'rb') as f:
            files.append(('pdf_file', (os.path.basename(pdf_file_path), f.read(), 'application/pdf')))

        # 正例範本
        for template in positive_templates:
            await template.seek(0)  # 重置文件指針
            content = await template.read()
            files.append(('positive_templates', (template.filename, content, template.content_type)))

        # 反例範本
        for template in negative_templates:
            await template.seek(0)
            content = await template.read()
            files.append(('negative_templates', (template.filename, content, template.content_type)))

        # 準備表單數據
        data = {
            'positive_threshold': positive_threshold,
            'negative_threshold': negative_threshold
        }

        # 調用 CLIP 服務
        response = await client.post(
            f"{CLIP_SERVICE_URL}/match-page",
            files=files,
            data=data
        )

        if response.status_code != 200:
            raise HTTPException(status_code=500, detail=f"CLIP 服務調用失敗: {response.text}")

        result = response.json()

        if not result.get('success'):
            raise HTTPException(status_code=400, detail=result.get('error', '未知錯誤'))

        # 解碼 Base64 圖像
        matched_page_image = None
        if result.get('matched_page_base64'):
            img_data = base64.b64decode(result['matched_page_base64'])
            matched_page_image = Image.open(io.BytesIO(img_data))

        return (
            result.get('matched_page_number'),
            matched_page_image,
            result.get('matching_score'),
            result.get('all_page_scores', [])
        )

def perform_ocr_on_file(
    file_path: str,
    key_list_parsed: list,
    original_filename: str,
    task_output_dir: str,
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
        task_output_dir: 任務專屬的輸出目錄
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
        # 執行保存操作
        layout_parsing_result.save_to_img(task_output_dir)

        # 獲取保存後的檔案列表
        files = set(os.listdir(task_output_dir)) if os.path.exists(task_output_dir) else set()

        for file in files:
            if file.endswith('.png'):
                output_images.append(file)

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
    task_id = str(uuid.uuid4())
    task_output_dir = os.path.join(output_dir, task_id)

    try:
        # 檢查檔案類型
        if not (file.content_type.startswith('image/') or file.content_type == 'application/pdf'):
            raise HTTPException(status_code=400, detail="請上傳有效的圖片檔案或PDF檔案")

        # 解析關鍵字列表
        try:
            key_list_parsed = json.loads(key_list)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="關鍵字列表格式錯誤")

        # 創建任務專屬輸出目錄
        os.makedirs(task_output_dir, exist_ok=True)

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
            task_output_dir=task_output_dir,
            use_doc_orientation_classify=use_doc_orientation_classify,
            use_doc_unwarping=use_doc_unwarping,
            use_textline_orientation=use_textline_orientation,
            use_seal_recognition=use_seal_recognition,
            use_table_recognition=use_table_recognition,
            use_llm=use_llm
        )

        # 保存 response_data 到 JSON 檔案
        response_file = os.path.join(task_output_dir, "response.json")
        with open(response_file, 'w', encoding='utf-8') as f:
            json.dump(response_data, f, ensure_ascii=False, indent=2)

        # 添加 task_id 到回應
        response_data["task_id"] = task_id

        # 更新輸出圖片路徑為相對於 output 的路徑
        response_data["output_images"] = [f"{task_id}/{img}" for img in response_data["output_images"]]

        # 儲存任務資訊到資料庫
        database.insert_task(
            task_id=task_id,
            original_filename=file.filename,
            output_directory=task_output_dir,
            response_file=response_file,
            file_type='pdf' if file.content_type == 'application/pdf' else 'image',
            matched_page_number=None,
            settings=response_data["settings"]
        )

        return OCRResponse(success=True, data=response_data)

    except HTTPException:
        raise
    except Exception as e:
        # 如果發生錯誤，清理輸出目錄
        if os.path.exists(task_output_dir):
            shutil.rmtree(task_output_dir)
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
    2. 調用 CLIP 服務找出最相似的頁面
    3. 對該頁面執行 OCR 處理
    """
    temp_pdf_path = None
    task_id = str(uuid.uuid4())
    task_output_dir = os.path.join(output_dir, task_id)

    try:
        # 檢查 PDF 檔案類型
        if pdf_file.content_type != 'application/pdf':
            raise HTTPException(status_code=400, detail="請上傳有效的 PDF 檔案")

        # 解析關鍵字列表
        try:
            key_list_parsed = json.loads(key_list)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="關鍵字列表格式錯誤")

        # 創建任務專屬輸出目錄
        os.makedirs(task_output_dir, exist_ok=True)

        # 保存 PDF 到臨時檔案
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_pdf:
            content = await pdf_file.read()
            temp_pdf.write(content)
            temp_pdf_path = temp_pdf.name

        # 調用 CLIP 服務進行頁面匹配
        print(f"調用 CLIP 服務進行頁面匹配...")
        best_page_number, best_page_image, best_score, all_scores = await call_clip_service(
            temp_pdf_path,
            positive_templates,
            negative_templates,
            positive_threshold,
            negative_threshold
        )

        if best_page_number is None:
            # 清理輸出目錄
            if os.path.exists(task_output_dir):
                shutil.rmtree(task_output_dir)
            return OCRResponse(
                success=False,
                error=f"未找到符合條件的頁面。請調整閾值參數。所有頁面分數: {all_scores}"
            )

        print(f"找到最佳匹配頁面: 第 {best_page_number} 頁, 分數: {best_score:.4f}")

        # 將匹配的頁面保存到任務輸出目錄
        matched_page_filename = f"matched_page_{best_page_number}.png"
        matched_page_path = os.path.join(task_output_dir, matched_page_filename)
        best_page_image.save(matched_page_path, 'PNG')

        # 調用核心 OCR 處理函數
        ocr_response_data = perform_ocr_on_file(
            file_path=matched_page_path,
            key_list_parsed=key_list_parsed,
            original_filename=pdf_file.filename,
            task_output_dir=task_output_dir,
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
            "matched_page_number": best_page_number,
            "matching_score": float(best_score),
            "all_page_scores": all_scores,
            "matched_page_path": f"{task_id}/{matched_page_filename}",
        }

        # 更新 settings 以包含匹配閾值
        response_data["settings"]["positive_threshold"] = positive_threshold
        response_data["settings"]["negative_threshold"] = negative_threshold

        # 保存 response_data 到 JSON 檔案
        response_file = os.path.join(task_output_dir, "response.json")
        with open(response_file, 'w', encoding='utf-8') as f:
            json.dump(response_data, f, ensure_ascii=False, indent=2)

        # 添加 task_id 到回應
        response_data["task_id"] = task_id

        # 更新輸出圖片路徑為相對於 output 的路徑
        response_data["output_images"] = [f"{task_id}/{img}" for img in response_data["output_images"]]

        # 儲存任務資訊到資料庫
        database.insert_task(
            task_id=task_id,
            original_filename=pdf_file.filename,
            output_directory=task_output_dir,
            response_file=response_file,
            file_type='pdf',
            matched_page_number=best_page_number,
            settings=response_data["settings"]
        )

        return OCRResponse(success=True, data=response_data)

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_detail = f"處理過程中發生錯誤: {str(e)}\n{traceback.format_exc()}"
        print(error_detail)
        # 如果發生錯誤，清理輸出目錄
        if os.path.exists(task_output_dir):
            shutil.rmtree(task_output_dir)
        return OCRResponse(success=False, error=error_detail)

    finally:
        # 清理臨時檔案
        if temp_pdf_path and os.path.exists(temp_pdf_path):
            try:
                os.unlink(temp_pdf_path)
            except Exception as e:
                print(f"清理臨時檔案失敗: {temp_pdf_path}, 錯誤: {e}")

@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request):
    """返回管理後台頁面"""
    return templates.TemplateResponse("admin.html", {"request": request})

@app.get("/admin/tasks")
async def get_all_tasks(include_deleted: bool = False):
    """取得所有任務列表"""
    try:
        tasks = database.get_all_tasks(include_deleted=include_deleted)
        return {"success": True, "tasks": tasks}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.get("/admin/task/{task_id}", response_class=HTMLResponse)
async def view_task_detail(request: Request, task_id: str):
    """查看任務詳情頁面"""
    task = database.get_task_by_id(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任務不存在")

    # 讀取 response.json
    response_data = None
    if os.path.exists(task['response_file']):
        with open(task['response_file'], 'r', encoding='utf-8') as f:
            response_data = json.load(f)

    return templates.TemplateResponse("task_detail.html", {
        "request": request,
        "task": task,
        "response_data": response_data
    })

@app.delete("/admin/task/{task_id}")
async def delete_task(task_id: str):
    """刪除任務"""
    try:
        # 取得任務資訊
        task = database.get_task_by_id(task_id)
        if not task:
            return {"success": False, "error": "任務不存在"}

        if task['is_deleted']:
            return {"success": False, "error": "任務已被刪除"}

        # 刪除實體檔案
        if os.path.exists(task['output_directory']):
            shutil.rmtree(task['output_directory'])

        # 標記資料庫為已刪除
        database.mark_task_deleted(task_id)

        return {"success": True, "message": "任務已刪除"}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.get("/health")
async def health_check():
    """健康檢查端點"""
    return {"status": "healthy", "message": "PaddleOCR 服務運行正常"}

if __name__ == "__main__":
    import uvicorn
    print("🚀 啟動 PaddleOCR 網站服務...")
    print("🌐 請訪問: http://localhost:8080")
    print("🛠️ 管理後台: http://localhost:8080/admin")
    uvicorn.run(app, host="0.0.0.0", port=8080)