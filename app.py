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

# 初始化 FastAPI 應用程式
app = FastAPI(title="PaddleOCR 圖片識別服務", description="上傳圖片並提取指定的關鍵字")

# 設定靜態檔案服務
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/output", StaticFiles(directory="output"), name="output")

# 設定模板引擎
templates = Jinja2Templates(directory="templates")

# 聊天機器人配置
chat_bot_config = {
    "module_name": "chat_bot",
    "model_name": "gemma3:4b",
    "base_url": "http://localhost:11434/v1",
    "api_type": "openai",
    "api_key": "sk-123456789",  # your api_key
}

# 初始化 PaddleOCR 管線
pipeline = create_pipeline(pipeline="PP-ChatOCRv4-doc", initial_predictor=False)

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
        
        try:
            # 執行視覺預測
            visual_predict_res = pipeline.visual_predict(
                input=temp_file_path,
                use_doc_orientation_classify=use_doc_orientation_classify,  #是否在推理时使用文档方向分类模块。
                use_doc_unwarping=use_doc_unwarping,                        #是否在推理时使用文本图像矫正模块。
                use_textline_orientation=use_textline_orientation,          #是否加载并使用文本行方向分类模块。
                use_common_ocr=True,
                use_seal_recognition=use_seal_recognition,                  #是否在推理时使用印章文本识别子产线。
                use_table_recognition=use_table_recognition,                #是否在推理时使用表格识别子产线。
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
                temp_path = Path(temp_file_path)
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
                    visual_info=visual_info_list,
                    chat_bot_config=chat_bot_config,
                )
            
            # 組合回應資料，包含聊天結果和視覺資訊
            response_data = {
                "chat_result": chat_result["chat_res"] if use_llm else None,
                "visual_info_list": visual_info_list,
                "key_list": key_list_parsed,
                "output_images": output_images,
                "original_filename": file.filename,
                "settings": {
                    "use_doc_orientation_classify": use_doc_orientation_classify,
                    "use_doc_unwarping": use_doc_unwarping,
                    "use_textline_orientation": use_textline_orientation,
                    "use_seal_recognition": use_seal_recognition,
                    "use_table_recognition": use_table_recognition,
                    "use_llm": use_llm
                }
            }
            
            return OCRResponse(success=True, data=response_data)
            
        finally:
            # 清理臨時檔案
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
        
    except HTTPException:
        raise
    except Exception as e:
        return OCRResponse(success=False, error=f"處理過程中發生錯誤: {str(e)}")

@app.get("/health")
async def health_check():
    """健康檢查端點"""
    return {"status": "healthy", "message": "PaddleOCR 服務運行正常"}

if __name__ == "__main__":
    import uvicorn
    print("🚀 啟動 PaddleOCR 網站服務...")
    print("🌐 請訪問: http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
