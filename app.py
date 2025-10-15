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
import task_database as batch_db
import batch_processor
from urllib.parse import quote

# 初始化 FastAPI 應用程式
app = FastAPI(title="PaddleOCR 圖片識別服務", description="上傳圖片並提取指定的關鍵字")

# 設定靜態檔案服務
output_dir = "output"
os.makedirs(output_dir, exist_ok=True)

# 初始化資料庫
database.init_database()
batch_db.init_database()

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
CLIP_SERVICE_URL = os.getenv("CLIP_SERVICE_URL", "http://192.168.80.24:8081")

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

async def call_clip_service(pdf_file_path: str, positive_templates: List[UploadFile], negative_templates: List[UploadFile], positive_threshold: float, negative_threshold: float, skip_voided: bool = False, top_n_for_void_check: int = 5):
    """
    調用 CLIP 服務進行頁面匹配
    Args:
        pdf_file_path: PDF 文件路徑
        positive_templates: 正例範本圖片列表
        negative_templates: 反例範本圖片列表
        positive_threshold: 正例相似度閾值
        negative_threshold: 反例相似度閾值
        skip_voided: 是否跳過廢止頁面
        top_n_for_void_check: 檢查前 N 個候選頁面是否為廢止
    Returns:
        (matched_page_number, matched_page_image, matching_score, all_scores, voided_pages_checked)
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
            'negative_threshold': negative_threshold,
            'skip_voided': skip_voided,
            'top_n_for_void_check': top_n_for_void_check
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
            result.get('all_page_scores', []),
            result.get('voided_pages_checked', [])
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
    skip_voided: bool = Form(False),
    top_n_for_void_check: int = Form(5),
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
        best_page_number, best_page_image, best_score, all_scores, voided_pages = await call_clip_service(
            temp_pdf_path,
            positive_templates,
            negative_templates,
            positive_threshold,
            negative_threshold,
            skip_voided,
            top_n_for_void_check
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

        # 如果有跳過的廢止頁面，添加到結果中
        if voided_pages:
            response_data["voided_pages_checked"] = voided_pages

        # 更新 settings 以包含匹配閾值
        response_data["settings"]["positive_threshold"] = positive_threshold
        response_data["settings"]["negative_threshold"] = negative_threshold
        response_data["settings"]["skip_voided"] = skip_voided
        response_data["settings"]["top_n_for_void_check"] = top_n_for_void_check

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

# ==================== 批次任務管理 API ====================

@app.get("/batch-tasks", response_class=HTMLResponse)
async def batch_tasks_page(request: Request):
    """批次任務管理頁面"""
    return templates.TemplateResponse("batch_tasks.html", {"request": request})

@app.get("/batch-tasks/{task_id}/detail", response_class=HTMLResponse)
async def batch_task_detail_page(request: Request, task_id: str):
    """批次任務詳情頁面"""
    try:
        task = batch_db.get_task_by_id(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="任務不存在")

        statistics = batch_db.get_task_statistics(task_id)
        keywords = batch_db.get_task_keywords(task_id)

        return templates.TemplateResponse("batch_task_detail.html", {
            "request": request,
            "task": task,
            "statistics": statistics,
            "keywords": keywords
        })
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/batch-tasks/create")
async def create_batch_task(
    task_name: str = Form(...),
    source_path: str = Form(...)
):
    """創建新的批次任務並掃描檔案"""
    try:
        # 驗證路徑
        if not os.path.exists(source_path):
            return {"success": False, "error": "指定的路徑不存在"}

        if not os.path.isdir(source_path):
            return {"success": False, "error": "指定的路徑不是目錄"}

        # 創建任務
        task_id = str(uuid.uuid4())
        batch_db.create_batch_task(task_id, task_name, source_path)

        # 掃描檔案
        files = batch_processor.scan_directory(source_path)

        if not files:
            return {"success": False, "error": "未找到任何 PDF 檔案"}

        # 添加檔案到任務
        batch_db.add_files_to_task(task_id, files)

        return {
            "success": True,
            "task_id": task_id,
            "total_files": len(files),
            "message": f"成功創建任務，找到 {len(files)} 個 PDF 檔案"
        }

    except Exception as e:
        import traceback
        return {"success": False, "error": f"創建任務失敗: {str(e)}\n{traceback.format_exc()}"}

@app.get("/api/batch-tasks")
async def get_batch_tasks(include_deleted: bool = False):
    """取得所有批次任務"""
    try:
        tasks = batch_db.get_all_tasks(include_deleted=include_deleted)
        return {"success": True, "tasks": tasks}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.get("/api/batch-tasks/{task_id}")
async def get_batch_task_detail(task_id: str):
    """取得批次任務詳情"""
    try:
        task = batch_db.get_task_by_id(task_id)
        if not task:
            return {"success": False, "error": "任務不存在"}

        # 取得統計資訊
        stats = batch_db.get_task_statistics(task_id)

        # 取得關鍵字
        keywords = batch_db.get_task_keywords(task_id)

        return {
            "success": True,
            "task": task,
            "statistics": stats,
            "keywords": keywords
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.get("/api/batch-tasks/{task_id}/keywords")
async def get_batch_task_keywords(task_id: str):
    """取得批次任務的關鍵字"""
    try:
        keywords = batch_db.get_task_keywords(task_id)
        return {"success": True, "keywords": keywords}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.get("/api/batch-tasks/{task_id}/files")
async def get_batch_task_files(
    task_id: str,
    status: Optional[str] = None,
    stage1_status: Optional[str] = None,
    stage2_status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
):
    """取得任務的檔案列表"""
    try:
        files = batch_db.get_task_files(
            task_id,
            status=status,
            stage1_status=stage1_status,
            stage2_status=stage2_status,
            limit=limit,
            offset=offset
        )
        return {"success": True, "files": files}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/api/batch-tasks/{task_id}/stage1/config")
async def configure_stage1(
    task_id: str,
    positive_templates: List[UploadFile] = File(...),
    negative_templates: List[UploadFile] = File(default=[]),
    positive_threshold: float = Form(0.25),
    negative_threshold: float = Form(0.30),
    skip_voided: bool = Form(False),
    top_n_for_void_check: int = Form(5)
):
    """配置第一階段參數"""
    try:
        # 將範本圖片轉換為 Base64
        positive_b64_list = []
        for template in positive_templates:
            content = await template.read()
            b64_str = base64.b64encode(content).decode('utf-8')
            positive_b64_list.append(b64_str)

        negative_b64_list = []
        for template in negative_templates:
            content = await template.read()
            b64_str = base64.b64encode(content).decode('utf-8')
            negative_b64_list.append(b64_str)

        # 保存配置
        config = {
            'positive_templates': positive_b64_list,
            'negative_templates': negative_b64_list,
            'positive_threshold': positive_threshold,
            'negative_threshold': negative_threshold,
            'skip_voided': skip_voided,
            'top_n_for_void_check': top_n_for_void_check
        }

        batch_db.save_task_stage1_config(task_id, config)

        return {"success": True, "message": "第一階段配置已保存"}

    except Exception as e:
        import traceback
        return {"success": False, "error": f"配置失敗: {str(e)}\n{traceback.format_exc()}"}

@app.post("/api/batch-tasks/{task_id}/stage2/config")
async def configure_stage2(
    task_id: str,
    keywords: str = Form(...),
    use_doc_orientation_classify: bool = Form(False),
    use_doc_unwarping: bool = Form(False),
    use_textline_orientation: bool = Form(False),
    use_seal_recognition: bool = Form(False),
    use_table_recognition: bool = Form(True),
    use_llm: bool = Form(True)
):
    """配置第二階段參數"""
    try:
        # 解析關鍵字
        keywords_list = json.loads(keywords)

        # 保存配置
        config = {
            'use_doc_orientation_classify': use_doc_orientation_classify,
            'use_doc_unwarping': use_doc_unwarping,
            'use_textline_orientation': use_textline_orientation,
            'use_seal_recognition': use_seal_recognition,
            'use_table_recognition': use_table_recognition,
            'use_llm': use_llm
        }

        batch_db.save_task_stage2_config(task_id, config, keywords_list)

        return {"success": True, "message": "第二階段配置已保存"}

    except Exception as e:
        import traceback
        return {"success": False, "error": f"配置失敗: {str(e)}\n{traceback.format_exc()}"}

@app.post("/api/batch-tasks/{task_id}/stage1/start")
async def start_stage1_processing(task_id: str):
    """開始第一階段處理"""
    try:
        batch_processor.start_task_stage1(task_id, CLIP_SERVICE_URL)
        return {"success": True, "message": "第一階段處理已啟動"}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/api/batch-tasks/{task_id}/stage2/start")
async def start_stage2_processing(task_id: str):
    """開始第二階段處理"""
    try:
        batch_processor.start_task_stage2(task_id)
        return {"success": True, "message": "第二階段處理已啟動"}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/api/batch-tasks/{task_id}/pause")
async def pause_task_processing(task_id: str):
    """暫停任務"""
    try:
        batch_processor.pause_task(task_id)
        return {"success": True, "message": "任務已暫停"}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/api/batch-tasks/{task_id}/resume")
async def resume_task_processing(task_id: str):
    """恢復任務"""
    try:
        batch_processor.resume_task(task_id)
        return {"success": True, "message": "任務已恢復"}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/api/batch-tasks/{task_id}/stop")
async def stop_task_processing(task_id: str):
    """停止任務"""
    try:
        batch_processor.stop_task(task_id)
        return {"success": True, "message": "任務已停止"}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/api/batch-tasks/{task_id}/stage1/restart")
async def restart_stage1_processing(task_id: str):
    """重新開始第一階段"""
    try:
        batch_processor.restart_task_stage1(task_id, CLIP_SERVICE_URL)
        return {"success": True, "message": "第一階段已重新啟動"}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/api/batch-tasks/{task_id}/stage2/restart")
async def restart_stage2_processing(task_id: str):
    """重新開始第二階段"""
    try:
        batch_processor.restart_task_stage2(task_id)
        return {"success": True, "message": "第二階段已重新啟動"}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.delete("/api/batch-tasks/{task_id}")
async def delete_batch_task(task_id: str):
    """刪除批次任務"""
    try:
        batch_db.mark_task_deleted(task_id)
        return {"success": True, "message": "任務已刪除"}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.get("/api/batch-tasks/{task_id}/files/{file_id}")
async def get_file_detail(task_id: str, file_id: int):
    """取得單個檔案的詳細資訊（包含圖片）"""
    try:
        conn = batch_db.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT * FROM batch_files
            WHERE id = ? AND task_id = ?
        ''', (file_id, task_id))

        row = cursor.fetchone()
        if not row:
            return {"success": False, "error": "檔案不存在"}

        file_info = dict(row)

        # 解析 JSON 資料
        if file_info['ocr_result']:
            try:
                file_info['ocr_result'] = json.loads(file_info['ocr_result'])
            except:
                pass

        if file_info['extracted_keywords']:
            try:
                file_info['extracted_keywords'] = json.loads(file_info['extracted_keywords'])
            except:
                pass

        return {"success": True, "file": file_info}

    except Exception as e:
        return {"success": False, "error": str(e)}

@app.get("/api/batch-tasks/{task_id}/files/{file_id}/image")
async def get_file_matched_image(task_id: str, file_id: int):
    """取得檔案的匹配頁面圖片"""
    try:
        from fastapi.responses import Response

        conn = batch_db.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT matched_page_base64 FROM batch_files
            WHERE id = ? AND task_id = ?
        ''', (file_id, task_id))

        row = cursor.fetchone()
        if not row or not row['matched_page_base64']:
            return {"success": False, "error": "圖片不存在"}

        # 解碼 Base64
        img_data = base64.b64decode(row['matched_page_base64'])

        return Response(
            content=img_data,
            media_type="image/png",
            headers={"Content-Disposition": f"inline; filename=page_{file_id}.png"}
        )

    except Exception as e:
        return {"success": False, "error": str(e)}

@app.get("/api/batch-tasks/{task_id}/files/{file_id}/pdf")
async def get_file_original_pdf(task_id: str, file_id: int):
    """取得檔案的原始 PDF"""
    try:
        from fastapi.responses import FileResponse
        import os

        conn = batch_db.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT file_path, file_name FROM batch_files
            WHERE id = ? AND task_id = ?
        ''', (file_id, task_id))

        row = cursor.fetchone()
        if not row or not row['file_path']:
            raise HTTPException(status_code=404, detail="檔案不存在")

        file_path = row['file_path']
        file_name = row['file_name']

        # 返回文件 - 使用URL編碼處理中文檔名
        
        encoded_filename = quote(file_name)

        headers = {
            'Content-Disposition': f'inline; filename*=UTF-8\'\'{encoded_filename}'
        }

        return FileResponse(
            path=file_path,
            media_type="application/pdf",
            headers=headers
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/batch-tasks/{task_id}/preview")
async def get_task_preview(task_id: str, limit: int = 10):
    """取得任務的預覽資訊（包含部分檔案的縮圖）"""
    try:
        # 取得已完成第一階段的檔案
        files = batch_db.get_task_files(
            task_id,
            stage1_status='completed',
            limit=limit
        )

        preview_data = []
        for f in files:
            preview_data.append({
                'id': f['id'],
                'file_name': f['file_name'],
                'matched_page_number': f['matched_page_number'],
                'matching_score': f['matching_score'],
                'stage2_status': f['stage2_status'],
                # Base64 圖片（可選擇性返回縮圖）
                'has_image': bool(f['matched_page_base64'])
            })

        return {"success": True, "files": preview_data}

    except Exception as e:
        return {"success": False, "error": str(e)}

@app.get("/api/batch-tasks/{task_id}/export")
async def export_task_to_excel(task_id: str):
    """匯出任務結果為 Excel"""
    try:
        from fastapi.responses import StreamingResponse
        import openpyxl
        from openpyxl.styles import Font, Alignment, PatternFill
        from io import BytesIO

        # 取得任務資訊
        task = batch_db.get_task_by_id(task_id)
        if not task:
            return {"success": False, "error": "任務不存在"}

        # 取得所有檔案
        files = batch_db.get_task_files(task_id)

        # 取得關鍵字
        keywords = batch_db.get_task_keywords(task_id)

        # 創建 Excel
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "OCR 結果"

        # 設定標題樣式
        title_font = Font(bold=True, size=12)
        title_fill = PatternFill(start_color="CCE5FF", end_color="CCE5FF", fill_type="solid")
        title_alignment = Alignment(horizontal="center", vertical="center")

        # 寫入標題行
        headers = ["檔案名稱", "檔案路徑", "狀態", "匹配頁面", "匹配分數"]
        headers.extend(keywords)
        headers.extend(["處理時間", "錯誤訊息"])

        for col_idx, header in enumerate(headers, start=1):
            cell = ws.cell(row=1, column=col_idx, value=header)
            cell.font = title_font
            cell.fill = title_fill
            cell.alignment = title_alignment

        # 寫入數據
        for row_idx, file_info in enumerate(files, start=2):
            ws.cell(row=row_idx, column=1, value=file_info['file_name'])
            ws.cell(row=row_idx, column=2, value=file_info['file_path'])
            ws.cell(row=row_idx, column=3, value=file_info['status'])
            ws.cell(row=row_idx, column=4, value=file_info['matched_page_number'])
            ws.cell(row=row_idx, column=5, value=file_info['matching_score'])

            # 解析提取的關鍵字
            extracted_keywords = {}
            if file_info['extracted_keywords']:
                try:
                    extracted_keywords = json.loads(file_info['extracted_keywords'])
                except:
                    pass

            # 寫入關鍵字值
            for kw_idx, keyword in enumerate(keywords):
                col_idx = 6 + kw_idx
                value = extracted_keywords.get(keyword, "")
                ws.cell(row=row_idx, column=col_idx, value=value)

            # 處理時間和錯誤訊息
            ws.cell(row=row_idx, column=6 + len(keywords), value=file_info['processed_at'])
            ws.cell(row=row_idx, column=7 + len(keywords), value=file_info['error_message'])

        # 自動調整欄寬
        for column in ws.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = min(max_length + 2, 50)
            ws.column_dimensions[column_letter].width = adjusted_width

        # 保存到內存
        output = BytesIO()
        wb.save(output)
        output.seek(0)

        # 返回文件 - 使用URL編碼處理中文檔名
        filename = f"{task['task_name']}_{task_id[:8]}.xlsx"
        encoded_filename = quote(filename)
        return StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"}
        )

    except Exception as e:
        import traceback
        return {"success": False, "error": f"匯出失敗: {str(e)}\n{traceback.format_exc()}"}

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