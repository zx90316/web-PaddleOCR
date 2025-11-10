#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批次處理模組
負責檔案掃描、CLIP 處理、OCR 處理
"""

import os
import json
from pathlib import Path
from typing import List, Dict, Optional
import threading
import time
import uuid
import httpx
import base64
from PIL import Image
import io
import task_database as db
from paddlex import create_pipeline

# 全局變數
processing_tasks = {}  # task_id -> threading.Thread
task_control = {}  # task_id -> {"pause": bool, "stop": bool}

# PaddleOCR 管線（延遲初始化）
paddle_pipeline = None

def get_paddle_pipeline():
    """獲取 PaddleOCR 管線"""
    global paddle_pipeline
    if paddle_pipeline is None:
        paddle_pipeline = create_pipeline(
            pipeline="./PP-ChatOCRv4-doc.yaml",
            initial_predictor=False
        )
    return paddle_pipeline

def scan_directory(directory_path: str, allowed_extensions: List[str] = None) -> List[Dict]:
    """
    遞迴掃描目錄，找出所有 PDF 文件
    Args:
        directory_path: 目錄路徑
        allowed_extensions: 允許的副檔名列表，預設為 ['.pdf']
    Returns:
        檔案資訊列表
    """
    if allowed_extensions is None:
        allowed_extensions = ['.pdf']

    files = []
    directory = Path(directory_path)

    if not directory.exists():
        raise ValueError(f"目錄不存在: {directory_path}")

    if not directory.is_dir():
        raise ValueError(f"路徑不是目錄: {directory_path}")

    print(f"開始掃描目錄: {directory_path}")

    try:
        for file_path in directory.rglob('*'):
            if file_path.is_file() and file_path.suffix.lower() in allowed_extensions:
                try:
                    file_size = file_path.stat().st_size
                    files.append({
                        'file_path': str(file_path),
                        'file_name': file_path.name,
                        'file_size': file_size,
                        'file_type': file_path.suffix.lower()
                    })
                except Exception as e:
                    print(f"無法讀取檔案資訊: {file_path}, 錯誤: {e}")

    except Exception as e:
        print(f"掃描目錄時發生錯誤: {e}")
        raise

    print(f"掃描完成，找到 {len(files)} 個檔案")
    return files

async def process_file_stage1(file_info: Dict, task_config: Dict, clip_service_url: str) -> Dict:
    """
    處理單個檔案的第一階段（CLIP 匹配）
    Args:
        file_info: 檔案資訊
        task_config: 任務配置（包含正例/反例圖片、閾值）
        clip_service_url: CLIP 服務 URL
    Returns:
        處理結果
    """
    try:
        async with httpx.AsyncClient(timeout=600.0, trust_env=False) as client:
            # 準備文件
            files = []

            # PDF 文件
            with open(file_info['file_path'], 'rb') as f:
                files.append(('pdf_file', (file_info['file_name'], f.read(), 'application/pdf')))

            # 正例範本（從 base64 解碼）
            for idx, template_b64 in enumerate(task_config['positive_templates']):
                img_data = base64.b64decode(template_b64)
                files.append(('positive_templates', (f'positive_{idx}.png', img_data, 'image/png')))

            # 反例範本（從 base64 解碼）
            for idx, template_b64 in enumerate(task_config.get('negative_templates', [])):
                img_data = base64.b64decode(template_b64)
                files.append(('negative_templates', (f'negative_{idx}.png', img_data, 'image/png')))

            # 準備表單數據
            data = {
                'positive_threshold': task_config.get('positive_threshold', 0.25),
                'negative_threshold': task_config.get('negative_threshold', 0.30),
                'skip_voided': task_config.get('skip_voided', False),
                'top_n_for_void_check': task_config.get('top_n_for_void_check', 5)
            }

            # 調用 CLIP 服務
            response = await client.post(
                f"{clip_service_url}/match-page",
                files=files,
                data=data
            )

            if response.status_code != 200:
                raise Exception(f"CLIP 服務調用失敗: {response.text}")

            result = response.json()

            if not result.get('success'):
                raise Exception(result.get('error', '未知錯誤'))

            return {
                'success': True,
                'matched_page_number': result.get('matched_page_number'),
                'matched_page_base64': result.get('matched_page_base64'),
                'matching_score': result.get('matching_score'),
                'all_page_scores': result.get('all_page_scores', []),
                'voided_pages_checked': result.get('voided_pages_checked', [])
            }

    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }

def process_file_stage2(file_info: Dict, matched_page_base64: str, task_config: Dict,
                        keywords: List[str]) -> Dict:
    """
    處理單個檔案的第二階段（OCR）
    Args:
        file_info: 檔案資訊
        matched_page_base64: 匹配的頁面圖片（Base64）
        task_config: 任務配置
        keywords: 關鍵字列表
    Returns:
        處理結果
    """
    try:
        # 解碼圖片
        img_data = base64.b64decode(matched_page_base64)
        image = Image.open(io.BytesIO(img_data))

        # 保存臨時圖片
        temp_dir = Path("temp_ocr")
        temp_dir.mkdir(exist_ok=True)
        temp_image_path = temp_dir / f"{uuid.uuid4()}.png"
        image.save(temp_image_path, 'PNG')

        try:
            # 執行 OCR
            pipeline = get_paddle_pipeline()

            visual_predict_res = pipeline.visual_predict(
                input=str(temp_image_path),
                use_doc_orientation_classify=task_config.get('use_doc_orientation_classify', False),
                use_doc_unwarping=task_config.get('use_doc_unwarping', False),
                use_textline_orientation=task_config.get('use_textline_orientation', False),
                use_common_ocr=True,
                use_seal_recognition=task_config.get('use_seal_recognition', False),
                use_table_recognition=task_config.get('use_table_recognition', True),
            )

            visual_info_list = []
            for res in visual_predict_res:
                visual_info_list.append(res["visual_info"])

            # 執行 LLM 提取關鍵字
            extracted_keywords = {}
            if task_config.get('use_llm', True) and keywords:
                use_mllm = task_config.get('use_mllm', False)
                
                if use_mllm:
                    try:
                        # 使用 MLLM 進行多模態預測
                        mllm_predict_res = pipeline.mllm_pred(
                            input=str(temp_image_path),
                            key_list=keywords,
                        )
                        mllm_predict_info = mllm_predict_res["mllm_res"]
                        
                        chat_result = pipeline.chat(
                            key_list=keywords,
                            visual_info=visual_info_list,
                            mllm_predict_info=mllm_predict_info,
                        )
                    except Exception as e:
                        # MLLM 失敗時退回標準 LLM
                        print(f"MLLM 處理失敗，退回標準 LLM: {str(e)}")
                        chat_result = pipeline.chat(
                            key_list=keywords,
                            visual_info=visual_info_list
                        )
                else:
                    # 使用標準 LLM
                    chat_result = pipeline.chat(
                        key_list=keywords,
                        visual_info=visual_info_list
                    )
                
                extracted_keywords = chat_result.get("chat_res", {})

            return {
                'success': True,
                'visual_info': visual_info_list,
                'extracted_keywords': extracted_keywords
            }

        finally:
            # 清理臨時檔案
            if temp_image_path.exists():
                temp_image_path.unlink()

    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }

def process_task_stage1_worker(task_id: str, clip_service_url: str = "http://localhost:8081"):
    """
    第一階段處理工作執行緒
    """
    import asyncio

    print(f"任務 {task_id} 第一階段處理開始")

    try:
        # 更新任務狀態
        db.update_task_status(task_id, 'running', stage=1)

        # 獲取任務配置
        task = db.get_task_by_id(task_id)
        if not task:
            raise Exception("任務不存在")

        stage1_config = json.loads(task['stage1_config']) if task['stage1_config'] else {}

        # 批次處理檔案
        batch_size = 5
        while True:
            # 檢查控制信號
            control = task_control.get(task_id, {})
            if control.get('stop'):
                print(f"任務 {task_id} 已停止")
                db.update_task_status(task_id, 'stopped', stage=1)
                break

            if control.get('pause'):
                print(f"任務 {task_id} 已暫停")
                db.update_task_status(task_id, 'paused', stage=1)
                time.sleep(1)
                continue

            # 獲取待處理檔案
            pending_files = db.get_pending_files_for_stage1(task_id, limit=batch_size)

            if not pending_files:
                print(f"任務 {task_id} 第一階段處理完成")
                db.update_task_status(task_id, 'stage1_completed', stage=1)
                break

            # 處理每個檔案
            for file_info in pending_files:
                # 再次檢查控制信號
                control = task_control.get(task_id, {})
                if control.get('stop') or control.get('pause'):
                    break

                print(f"處理檔案: {file_info['file_name']}")

                # 異步處理
                result = asyncio.run(process_file_stage1(file_info, stage1_config, clip_service_url))

                if result['success']:
                    db.update_file_stage1_result(
                        file_info['id'],
                        result['matched_page_number'],
                        result['matched_page_base64'],
                        result['matching_score'],
                        status='completed'
                    )
                    print(f"檔案處理成功: {file_info['file_name']}, 匹配頁面: {result['matched_page_number']}")
                else:
                    db.update_file_stage1_result(
                        file_info['id'],
                        None, None, None,
                        status='failed',
                        error_message=result.get('error')
                    )
                    print(f"檔案處理失敗: {file_info['file_name']}, 錯誤: {result.get('error')}")

                # 更新進度
                db.update_task_progress(task_id)

            # 小延遲避免過度佔用資源
            time.sleep(0.1)

    except Exception as e:
        print(f"任務 {task_id} 第一階段處理失敗: {e}")
        db.update_task_status(task_id, 'failed', stage=1, error_message=str(e))
    finally:
        # 清理
        if task_id in processing_tasks:
            del processing_tasks[task_id]
        if task_id in task_control:
            del task_control[task_id]

def process_task_stage2_worker(task_id: str):
    """
    第二階段處理工作執行緒
    """
    print(f"任務 {task_id} 第二階段處理開始")

    try:
        # 更新任務狀態
        db.update_task_status(task_id, 'running', stage=2)

        # 獲取任務配置和關鍵字
        task = db.get_task_by_id(task_id)
        if not task:
            raise Exception("任務不存在")

        stage2_config = json.loads(task['stage2_config']) if task['stage2_config'] else {}
        keywords = db.get_task_keywords(task_id)

        # 批次處理檔案
        batch_size = 5
        while True:
            # 檢查控制信號
            control = task_control.get(task_id, {})
            if control.get('stop'):
                print(f"任務 {task_id} 已停止")
                db.update_task_status(task_id, 'stopped', stage=2)
                break

            if control.get('pause'):
                print(f"任務 {task_id} 已暫停")
                db.update_task_status(task_id, 'paused', stage=2)
                time.sleep(1)
                continue

            # 獲取待處理檔案
            pending_files = db.get_pending_files_for_stage2(task_id, limit=batch_size)

            if not pending_files:
                print(f"任務 {task_id} 第二階段處理完成")
                db.update_task_status(task_id, 'completed', stage=2)
                break

            # 處理每個檔案
            for file_info in pending_files:
                # 再次檢查控制信號
                control = task_control.get(task_id, {})
                if control.get('stop') or control.get('pause'):
                    break

                print(f"OCR 處理檔案: {file_info['file_name']}")

                result = process_file_stage2(
                    file_info,
                    file_info['matched_page_base64'],
                    stage2_config,
                    keywords
                )

                if result['success']:
                    db.update_file_stage2_result(
                        file_info['id'],
                        json.dumps(result['visual_info'], ensure_ascii=False),
                        json.dumps(result['extracted_keywords'], ensure_ascii=False),
                        status='completed'
                    )
                    print(f"OCR 處理成功: {file_info['file_name']}")
                else:
                    db.update_file_stage2_result(
                        file_info['id'],
                        None, None,
                        status='failed',
                        error_message=result.get('error')
                    )
                    print(f"OCR 處理失敗: {file_info['file_name']}, 錯誤: {result.get('error')}")

                # 更新進度
                db.update_task_progress(task_id)

            # 小延遲避免過度佔用資源
            time.sleep(0.1)

    except Exception as e:
        print(f"任務 {task_id} 第二階段處理失敗: {e}")
        db.update_task_status(task_id, 'failed', stage=2, error_message=str(e))
    finally:
        # 清理
        if task_id in processing_tasks:
            del processing_tasks[task_id]
        if task_id in task_control:
            del task_control[task_id]

def start_task_stage1(task_id: str, clip_service_url: str = "http://localhost:8081"):
    """啟動第一階段處理"""
    if task_id in processing_tasks:
        raise Exception("任務已在處理中")

    task_control[task_id] = {"pause": False, "stop": False}

    thread = threading.Thread(
        target=process_task_stage1_worker,
        args=(task_id, clip_service_url),
        daemon=True
    )
    processing_tasks[task_id] = thread
    thread.start()

def start_task_stage2(task_id: str):
    """啟動第二階段處理"""
    if task_id in processing_tasks:
        raise Exception("任務已在處理中")

    task_control[task_id] = {"pause": False, "stop": False}

    thread = threading.Thread(
        target=process_task_stage2_worker,
        args=(task_id,),
        daemon=True
    )
    processing_tasks[task_id] = thread
    thread.start()

def pause_task(task_id: str):
    """暫停任務"""
    if task_id not in task_control:
        raise Exception("任務不在處理中")

    task_control[task_id]["pause"] = True

def resume_task(task_id: str):
    """恢復任務"""
    if task_id not in task_control:
        raise Exception("任務不在處理中")

    task_control[task_id]["pause"] = False
    db.update_task_status(task_id, 'running')

def stop_task(task_id: str):
    """停止任務"""
    if task_id not in task_control:
        raise Exception("任務不在處理中")

    task_control[task_id]["stop"] = True

def restart_task_stage1(task_id: str, CLIP_SERVICE_URL : str):
    """重新開始第一階段"""
    # 停止現有任務
    if task_id in processing_tasks:
        stop_task(task_id)
        time.sleep(2)

    # 重置所有檔案的第一階段狀態
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE batch_files
        SET stage1_status = 'pending',
            stage1_result = NULL,
            matched_page_number = NULL,
            matched_page_base64 = NULL,
            matching_score = NULL
        WHERE task_id = ?
    ''', (task_id,))
    conn.commit()

    # 重新啟動
    start_task_stage1(task_id,CLIP_SERVICE_URL)

def restart_task_stage2(task_id: str):
    """重新開始第二階段"""
    # 停止現有任務
    if task_id in processing_tasks:
        stop_task(task_id)
        time.sleep(2)

    # 重置所有檔案的第二階段狀態
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE batch_files
        SET stage2_status = 'pending',
            stage2_result = NULL,
            ocr_result = NULL,
            extracted_keywords = NULL
        WHERE task_id = ? AND stage1_status = 'completed'
    ''', (task_id,))
    conn.commit()

    # 重新啟動
    start_task_stage2(task_id)

def resume_task_from_failure(task_id: str, clip_service_url: str = "http://localhost:8081"):
    """
    從失敗點繼續執行任務

    此函數會:
    1. 檢查任務當前的階段
    2. 重置任務狀態為 'running'
    3. 繼續處理 pending 狀態的檔案
    4. 不會重新處理已完成或已失敗的檔案

    使用場景:
    - 任務執行到 1200/3000 時因錯誤中斷
    - 狀態變為 'failed'
    - 調用此函數後,從第 1201 個檔案繼續執行

    Args:
        task_id: 任務ID
        clip_service_url: CLIP 服務 URL
    """
    # 獲取任務資訊
    task = db.get_task_by_id(task_id)
    if not task:
        raise Exception("任務不存在")

    # 檢查任務狀態
    if task['status'] not in ['failed', 'stopped' , 'paused']:
        raise Exception(f"只有失敗或已停止或暫停的任務才能繼續執行,當前狀態: {task['status']}")

    # 檢查是否已在處理中
    if task_id in processing_tasks:
        raise Exception("任務已在處理中")

    current_stage = task['stage']

    print(f"任務 {task_id} 準備從第 {current_stage} 階段繼續執行")

    # 取得統計資訊
    stats = db.get_task_statistics(task_id)
    if current_stage == 1:
        pending_count = stats.get('stage1_pending', 0)
        completed_count = stats.get('stage1_completed', 0)
        failed_count = stats.get('stage1_failed', 0)
        print(f"第一階段: 已完成 {completed_count}, 已失敗 {failed_count}, 待處理 {pending_count}")
    elif current_stage == 2:
        pending_count = stats.get('stage2_pending', 0)
        completed_count = stats.get('stage2_completed', 0)
        failed_count = stats.get('stage2_failed', 0)
        print(f"第二階段: 已完成 {completed_count}, 已失敗 {failed_count}, 待處理 {pending_count}")

    if pending_count == 0:
        print(f"沒有待處理的檔案,任務已完成或所有檔案都已處理")
        return

    # 重置任務狀態
    db.reset_task_status_for_resume(task_id, current_stage)

    # 根據階段繼續執行
    if current_stage == 1:
        start_task_stage1(task_id, clip_service_url)
        print(f"已從第一階段繼續執行,將處理剩餘的 {pending_count} 個檔案")
    elif current_stage == 2:
        start_task_stage2(task_id)
        print(f"已從第二階段繼續執行,將處理剩餘的 {pending_count} 個檔案")
    else:
        raise Exception(f"無效的階段: {current_stage}")
