/**
 * PaddleOCR Web Interface - Frontend Application
 * Copyright (c) 2025
 * 
 * This project provides a web interface for PaddleOCR.
 * Core OCR functionality is provided by PaddleOCR (Apache License 2.0).
 */

// 狀態管理
function updateStatus(status, message) {
    const indicator = document.getElementById('statusIndicator');
    indicator.className = `status-indicator status-${status}`;
    indicator.textContent = message;
}

// 當前選擇的模式
let currentMode = 'standard';

// DOM 載入完成後執行
document.addEventListener('DOMContentLoaded', function() {
    const keyListTextarea = document.getElementById('keyList');

    // 初始化圖片modal功能
    initImageModal();

    // 處理模式切換
    document.querySelectorAll('.mode-tab').forEach(tab => {
        tab.addEventListener('click', function() {
            const mode = this.getAttribute('data-mode');
            switchMode(mode);
        });
    });

    // 處理檔案選擇事件 - 標準模式
    document.getElementById('imageFile').addEventListener('change', function(e) {
        const file = e.target.files[0];
        if (file) {
            previewFile(file);
        }
    });

    // 處理檔案選擇事件 - 匹配模式
    document.getElementById('pdfFile').addEventListener('change', function(e) {
        const file = e.target.files[0];
        if (file) {
            previewPdfFile(file);
        }
    });

    document.getElementById('positiveTemplates').addEventListener('change', function(e) {
        previewTemplates(e.target.files, 'positive');
    });

    document.getElementById('negativeTemplates').addEventListener('change', function(e) {
        previewTemplates(e.target.files, 'negative');
    });

    // 閾值滑桿即時更新
    document.getElementById('positiveThreshold').addEventListener('input', function(e) {
        document.getElementById('posThresholdValue').textContent = e.target.value;
    });

    document.getElementById('negativeThreshold').addEventListener('input', function(e) {
        document.getElementById('negThresholdValue').textContent = e.target.value;
    });

    // 處理預設關鍵字按鈕點擊事件
    document.querySelectorAll('.keyword-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            const keyword = this.getAttribute('data-keyword');
            const currentValue = keyListTextarea.value;
            const keywords = currentValue.split('\n').filter(k => k.trim().length > 0);
            
            // 避免重複添加
            if (!keywords.includes(keyword)) {
                if (currentValue.trim()) {
                    keyListTextarea.value = currentValue + '\n' + keyword;
                } else {
                    keyListTextarea.value = keyword;
                }
                
                // 成功添加的視覺反饋
                showButtonFeedback(this, 'success');
            } else {
                // 已存在的提示反饋
                showButtonFeedback(this, 'warning');
            }
        });
    });
    
    // 清空關鍵字按鈕
    document.querySelector('.clear-btn').addEventListener('click', function() {
        keyListTextarea.value = '';
        keyListTextarea.focus();
        updateStatus('ready', '準備就緒');
    });
    
    // 表單提交處理
    document.getElementById('uploadForm').addEventListener('submit', handleFormSubmit);
});

// 模式切換函數
function switchMode(mode) {
    currentMode = mode;

    // 更新按鈕狀態
    document.querySelectorAll('.mode-tab').forEach(tab => {
        tab.classList.remove('active');
    });
    document.querySelector(`.mode-tab[data-mode="${mode}"]`).classList.add('active');

    // 切換顯示的內容
    if (mode === 'standard') {
        document.getElementById('standardMode').style.display = 'block';
        document.getElementById('matchingMode').style.display = 'none';
    } else {
        document.getElementById('standardMode').style.display = 'none';
        document.getElementById('matchingMode').style.display = 'block';
    }

    updateStatus('ready', '準備就緒');
}

// 按鈕反饋效果
function showButtonFeedback(button, type) {
    const colors = {
        success: { bg: '#28a745', border: '#28a745', color: 'white' },
        warning: { bg: '#ffc107', border: '#ffc107', color: '#212529' }
    };

    const color = colors[type];
    button.style.backgroundColor = color.bg;
    button.style.borderColor = color.border;
    button.style.color = color.color;

    setTimeout(() => {
        button.style.backgroundColor = '';
        button.style.borderColor = '';
        button.style.color = '';
    }, 300);
}

// PDF 檔案預覽
function previewPdfFile(file) {
    const preview = document.getElementById('pdfFilePreview');
    const fileName = document.getElementById('pdfFileName');

    fileName.textContent = `檔案名稱：${file.name}`;
    preview.style.display = 'block';
}

// 範本圖片預覽
function previewTemplates(files, type) {
    const previewDiv = document.getElementById(type === 'positive' ? 'positivePreview' : 'negativePreview');
    previewDiv.innerHTML = '';

    if (files.length === 0) return;

    previewDiv.innerHTML = `<p style="margin: 5px 0; font-size: 12px; color: #666;">已選擇 ${files.length} 張圖片</p>`;
    const container = document.createElement('div');
    container.style.display = 'flex';
    container.style.flexWrap = 'wrap';
    container.style.gap = '5px';

    Array.from(files).forEach(file => {
        const reader = new FileReader();
        reader.onload = function(e) {
            const img = document.createElement('img');
            img.src = e.target.result;
            img.style.width = '60px';
            img.style.height = '60px';
            img.style.objectFit = 'cover';
            img.style.border = type === 'positive' ? '2px solid #28a745' : '2px solid #dc3545';
            img.style.borderRadius = '4px';
            img.title = file.name;
            container.appendChild(img);
        };
        reader.readAsDataURL(file);
    });

    previewDiv.appendChild(container);
}

// 檔案預覽功能
function previewFile(file) {
    const imagePreview = document.getElementById('imagePreview');
    const uploadedImage = document.getElementById('uploadedImage');
    const pdfPreview = document.getElementById('pdfPreview');
    const imageFileName = document.getElementById('imageFileName');
    
    imageFileName.textContent = `檔案名稱：${file.name}`;
    imagePreview.style.display = 'block';
    
    // 檢查檔案類型
    if (file.type.startsWith('image/')) {
        // 處理圖片檔案
        const reader = new FileReader();
        reader.onload = function(e) {
            uploadedImage.src = e.target.result;
            uploadedImage.setAttribute('data-caption', file.name);
            uploadedImage.classList.add('clickable-image');
            uploadedImage.style.display = 'block';
            pdfPreview.style.display = 'none';
            
            // 為上傳的預覽圖片綁定點擊事件
            bindImageClickEvents();
        };
        reader.readAsDataURL(file);
    } else if (file.type === 'application/pdf') {
        // 處理PDF檔案
        uploadedImage.style.display = 'none';
        pdfPreview.style.display = 'flex';
    }
}

// 表單提交處理函數
async function handleFormSubmit(e) {
    e.preventDefault();

    if (currentMode === 'standard') {
        await handleStandardSubmit();
    } else {
        await handleMatchingSubmit();
    }
}

// 標準模式提交
async function handleStandardSubmit() {
    const formData = new FormData();
    const fileInput = document.getElementById('imageFile');
    const keyListInput = document.getElementById('keyList');
    const useOrientation = document.getElementById('useOrientation').checked;
    const useUnwarping = document.getElementById('useUnwarping').checked;
    const useTextlineOrientation = document.getElementById('useTextlineOrientation').checked;
    const useSealRecognition = document.getElementById('useSealRecognition').checked;
    const useTableRecognition = document.getElementById('useTableRecognition').checked;
    const useLLM = document.getElementById('useLLM').checked;

    // 驗證輸入
    if (!fileInput.files[0]) {
        alert('請選擇一個圖片或PDF檔案');
        return;
    }

    if (!keyListInput.value.trim() && useLLM) {
        alert('請輸入需要提取的關鍵字');
        return;
    }

    // 準備表單資料
    formData.append('file', fileInput.files[0]);

    const keyList = keyListInput.value.split('\n')
        .map(key => key.trim())
        .filter(key => key.length > 0);

    formData.append('key_list', JSON.stringify(keyList));
    formData.append('use_doc_orientation_classify', useOrientation);
    formData.append('use_doc_unwarping', useUnwarping);
    formData.append('use_textline_orientation', useTextlineOrientation);
    formData.append('use_seal_recognition', useSealRecognition);
    formData.append('use_table_recognition', useTableRecognition);
    formData.append('use_llm', useLLM);

    // 更新UI狀態
    const submitButton = document.querySelector('button[type="submit"]');
    const resultDiv = document.getElementById('result');
    const placeholder = document.getElementById('placeholder');

    updateStatus('processing', '處理中...');
    submitButton.disabled = true;
    submitButton.textContent = '處理中...';
    placeholder.style.display = 'none';
    resultDiv.style.display = 'block';
    resultDiv.innerHTML = createLoadingHTML();

    try {
        const response = await fetch('/ocr', {
            method: 'POST',
            body: formData
        });

        const result = await response.json();

        if (result.success) {
            resultDiv.innerHTML = createSuccessHTML(result.data);
            updateStatus('success', '處理完成');
            bindImageClickEvents();
        } else {
            resultDiv.innerHTML = createErrorHTML('識別失敗', result.detail);
            updateStatus('error', '處理失敗');
        }
    } catch (error) {
        resultDiv.innerHTML = createErrorHTML('請求失敗', `連接服務器時發生錯誤: ${error.message}`);
        updateStatus('error', '請求失敗');
    }

    submitButton.disabled = false;
    submitButton.textContent = '上傳並識別';
}

// 匹配模式提交
async function handleMatchingSubmit() {
    const formData = new FormData();
    const pdfInput = document.getElementById('pdfFile');
    const positiveInput = document.getElementById('positiveTemplates');
    const negativeInput = document.getElementById('negativeTemplates');
    const keyListInput = document.getElementById('keyList');
    const useOrientation = document.getElementById('useOrientation').checked;
    const useUnwarping = document.getElementById('useUnwarping').checked;
    const useTextlineOrientation = document.getElementById('useTextlineOrientation').checked;
    const useSealRecognition = document.getElementById('useSealRecognition').checked;
    const useTableRecognition = document.getElementById('useTableRecognition').checked;
    const useLLM = document.getElementById('useLLM').checked;
    const positiveThreshold = document.getElementById('positiveThreshold').value;
    const negativeThreshold = document.getElementById('negativeThreshold').value;

    // 驗證輸入
    if (!pdfInput.files[0]) {
        alert('請選擇PDF檔案');
        return;
    }

    if (positiveInput.files.length === 0) {
        alert('請至少選擇一張正例範本圖片');
        return;
    }

    if (!keyListInput.value.trim() && useLLM) {
        alert('請輸入需要提取的關鍵字');
        return;
    }

    // 準備表單資料
    formData.append('pdf_file', pdfInput.files[0]);

    // 添加正例範本
    for (let file of positiveInput.files) {
        formData.append('positive_templates', file);
    }

    // 添加反例範本
    for (let file of negativeInput.files) {
        formData.append('negative_templates', file);
    }

    const keyList = keyListInput.value.split('\n')
        .map(key => key.trim())
        .filter(key => key.length > 0);

    formData.append('key_list', JSON.stringify(keyList));
    formData.append('use_doc_orientation_classify', useOrientation);
    formData.append('use_doc_unwarping', useUnwarping);
    formData.append('use_textline_orientation', useTextlineOrientation);
    formData.append('use_seal_recognition', useSealRecognition);
    formData.append('use_table_recognition', useTableRecognition);
    formData.append('use_llm', useLLM);
    formData.append('positive_threshold', positiveThreshold);
    formData.append('negative_threshold', negativeThreshold);

    // 更新UI狀態
    const submitButton = document.querySelector('button[type="submit"]');
    const resultDiv = document.getElementById('result');
    const placeholder = document.getElementById('placeholder');

    updateStatus('processing', '頁面匹配與OCR處理中...');
    submitButton.disabled = true;
    submitButton.textContent = '處理中...';
    placeholder.style.display = 'none';
    resultDiv.style.display = 'block';
    resultDiv.innerHTML = createLoadingHTML('正在分析PDF並尋找最匹配的頁面...');

    try {
        const response = await fetch('/ocr-with-matching', {
            method: 'POST',
            body: formData
        });

        const result = await response.json();

        if (result.success) {
            resultDiv.innerHTML = createMatchingSuccessHTML(result.data);
            updateStatus('success', '處理完成');
            bindImageClickEvents();
        } else {
            resultDiv.innerHTML = createErrorHTML('識別失敗', result.detail || '未知錯誤');
            updateStatus('error', '處理失敗');
        }
    } catch (error) {
        resultDiv.innerHTML = createErrorHTML('請求失敗', `連接服務器時發生錯誤: ${error.message}`);
        updateStatus('error', '請求失敗');
    }

    submitButton.disabled = false;
    submitButton.textContent = '上傳並識別';
}

// 創建載入中的HTML
function createLoadingHTML(message = '請稍候，系統正在分析您的檔案並提取關鍵字...') {
    return `
        <div class="loading">
            <h3>📈 正在處理檔案</h3>
            <p>${message}</p>
        </div>
    `;
}

// 創建匹配模式成功結果的HTML
function createMatchingSuccessHTML(data) {
    console.log('Matching OCR Response data:', data);

    // 頁面匹配結果
    let matchingResultHTML = `
        <div class="result-section matching-result">
            <h4>🎯 頁面匹配結果</h4>
            <p><strong>匹配頁碼：</strong>第 ${data.matched_page_number} 頁</p>
            <p><strong>匹配分數：</strong>${data.matching_score.toFixed(4)}</p>
            <details>
                <summary>查看所有頁面分數</summary>
                <pre class="json-result">${JSON.stringify(data.all_page_scores, null, 2)}</pre>
            </details>
        </div>
    `;

    // OCR 結果圖片
    let outputImagesHTML = '';
    if (data.output_images && data.output_images.length > 0) {
        outputImagesHTML = `
            <div class="result-section">
                <h4>🔍 OCR 處理結果圖片</h4>
                <div class="output-images">
                    ${data.output_images.map(imageName => `
                        <div class="output-image">
                            <img src="/output/${imageName}" alt="OCR處理結果" class="result-image clickable-image"
                                 data-caption="${imageName}">
                            <p class="image-caption">${imageName}</p>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
    }

    let htmlContent = `
        <div class="result success">
            <h3>✅ 頁面匹配與OCR識別成功</h3>

            ${matchingResultHTML}

            ${outputImagesHTML}

            <div class="result-section">
                <h4>📝 關鍵字提取結果</h4>
                <pre class="json-result">${JSON.stringify(data.chat_result, null, 2)}</pre>
            </div>

            <div class="result-section">
                <h4>⚙️ 處理設定</h4>
                <p><strong>原始檔案：</strong> ${data.original_filename || 'N/A'}</p>
                <p><strong>查詢的關鍵字：</strong> ${data.key_list.join(', ')}</p>
                <p><strong>正例相似度閾值：</strong> ${data.settings.positive_threshold}</p>
                <p><strong>反例相似度閾值：</strong> ${data.settings.negative_threshold}</p>
                <p><strong>使用大模型提取結果：</strong> ${data.settings.use_llm ? '已啟用' : '未啟用'}</p>
                <p><strong>文檔方向分類：</strong> ${data.settings.use_doc_orientation_classify ? '已啟用' : '未啟用'}</p>
                <p><strong>文檔去彎曲：</strong> ${data.settings.use_doc_unwarping ? '已啟用' : '未啟用'}</p>
                <p><strong>文本行方向分類：</strong> ${data.settings.use_textline_orientation ? '已啟用' : '未啟用'}</p>
                <p><strong>印章文本識別：</strong> ${data.settings.use_seal_recognition ? '已啟用' : '未啟用'}</p>
                <p><strong>表格識別：</strong> ${data.settings.use_table_recognition ? '已啟用' : '未啟用'}</p>
            </div>

            <div class="result-section">
                <h4>📊 完整資料 (JSON)</h4>
                <details>
                    <summary>點擊查看完整回應資料</summary>
                    <pre class="json-result">${JSON.stringify(data, null, 2)}</pre>
                </details>
            </div>
        </div>
    `;

    return htmlContent;
}

// 創建成功結果的HTML
function createSuccessHTML(data) {
    console.log('OCR Response data:', data); // 調試信息
    
    let outputImagesHTML = '';
    if (data.output_images && data.output_images.length > 0) {
        console.log('Output images found:', data.output_images); // 調試信息
        outputImagesHTML = `
            <div class="result-section">
                <h4>🔍 OCR 處理結果圖片</h4>
                <div class="output-images">
                    ${data.output_images.map(imageName => `
                        <div class="output-image">
                            <img src="/output/${imageName}" alt="OCR處理結果" class="result-image clickable-image" 
                                 data-caption="${imageName}"
                                 onload="console.log('圖片載入成功: ${imageName}')" 
                                 onerror="console.error('圖片載入失敗: ${imageName}')">
                            <p class="image-caption">${imageName}</p>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
    } else {
        console.log('No output images found'); // 調試信息
        outputImagesHTML = `
            <div class="result-section">
                <h4>⚠️ 未找到OCR結果圖片</h4>
                <p>處理完成但未生成結果圖片</p>
            </div>
        `;
    }
    
    let htmlContent = `
        <div class="result success">
            <h3>✅ 識別成功</h3>
            
            ${outputImagesHTML}
            
            <div class="result-section">
                <h4>🎯 關鍵字提取結果</h4>
                <pre class="json-result">${JSON.stringify(data.chat_result, null, 2)}</pre>
            </div>
            
            <div class="result-section">
                <h4>⚙️ 處理設定</h4>
                <p><strong>原始檔案：</strong> ${data.original_filename || 'N/A'}</p>
                <p><strong>查詢的關鍵字：</strong> ${data.key_list.join(', ')}</p>
                <p><strong>使用大模型提取結果：</strong> ${data.settings.use_llm ? '已啟用' : '未啟用'}</p>
                <p><strong>文檔方向分類：</strong> ${data.settings.use_doc_orientation_classify ? '已啟用' : '未啟用'}</p>
                <p><strong>文檔去彎曲：</strong> ${data.settings.use_doc_unwarping ? '已啟用' : '未啟用'}</p>
                <p><strong>文本行方向分類：</strong> ${data.settings.use_textline_orientation ? '已啟用' : '未啟用'}</p>
                <p><strong>印章文本識別：</strong> ${data.settings.use_seal_recognition ? '已啟用' : '未啟用'}</p>
                <p><strong>表格識別：</strong> ${data.settings.use_table_recognition ? '已啟用' : '未啟用'}</p>
            </div>
            
            <div class="result-section">
                <h4>📊 完整資料 (JSON)</h4>
                <details>
                    <summary>點擊查看完整回應資料</summary>
                    <pre class="json-result">${JSON.stringify(data, null, 2)}</pre>
                </details>
            </div>
        </div>
    `;
    
    return htmlContent;
}

// 創建錯誤結果的HTML
function createErrorHTML(title, message) {
    return `
        <div class="result error">
            <h3>❌ ${title}</h3>
            <p>${message}</p>
        </div>
    `;
}

// ===================
// 圖片放大預覽功能
// ===================

// 初始化圖片Modal功能
function initImageModal() {
    const modal = document.getElementById('imageModal');
    const modalImage = document.getElementById('modalImage');
    const modalCaption = document.querySelector('.modal-caption');
    const closeBtn = document.querySelector('.modal-close');
    
    // 點擊關閉按鈕
    closeBtn.addEventListener('click', closeModal);
    
    // 點擊Modal背景關閉
    modal.addEventListener('click', function(e) {
        if (e.target === modal) {
            closeModal();
        }
    });
    
    // 按ESC鍵關閉
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape' && modal.classList.contains('show')) {
            closeModal();
        }
    });
    
    // 防止點擊圖片時觸發背景點擊事件
    modalImage.addEventListener('click', function(e) {
        e.stopPropagation();
    });
}

// 為所有可點擊圖片綁定事件
function bindImageClickEvents() {
    const clickableImages = document.querySelectorAll('.clickable-image');
    clickableImages.forEach(img => {
        // 移除之前的事件監聽器（如果有的話）
        img.removeEventListener('click', handleImageClick);
        // 添加新的事件監聽器
        img.addEventListener('click', handleImageClick);
    });
}

// 處理圖片點擊事件
function handleImageClick(e) {
    const img = e.target;
    const src = img.src;
    const caption = img.getAttribute('data-caption') || img.alt || '圖片預覽';
    
    openModal(src, caption);
}

// 打開Modal
function openModal(imageSrc, caption) {
    const modal = document.getElementById('imageModal');
    const modalImage = document.getElementById('modalImage');
    const modalCaption = document.querySelector('.modal-caption');
    
    modalImage.src = imageSrc;
    modalCaption.textContent = caption;
    modal.classList.add('show');
    
    // 禁用頁面滾動
    document.body.style.overflow = 'hidden';
    
    console.log('打開圖片預覽:', caption);
}

// 關閉Modal
function closeModal() {
    const modal = document.getElementById('imageModal');
    modal.classList.remove('show');
    
    // 恢復頁面滾動
    document.body.style.overflow = 'auto';
    
    console.log('關閉圖片預覽');
}
