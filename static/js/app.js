// PaddleOCR 前端應用程式主腳本

// 狀態管理
function updateStatus(status, message) {
    const indicator = document.getElementById('statusIndicator');
    indicator.className = `status-indicator status-${status}`;
    indicator.textContent = message;
}

// DOM 載入完成後執行
document.addEventListener('DOMContentLoaded', function() {
    const keyListTextarea = document.getElementById('keyList');
    
    // 初始化圖片modal功能
    initImageModal();
    
    // 處理圖片文件選擇事件
    document.getElementById('imageFile').addEventListener('change', function(e) {
        const file = e.target.files[0];
        if (file) {
            previewImage(file);
        }
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

// 圖片預覽功能
function previewImage(file) {
    const reader = new FileReader();
    const imagePreview = document.getElementById('imagePreview');
    const uploadedImage = document.getElementById('uploadedImage');
    const imageFileName = document.getElementById('imageFileName');
    
    reader.onload = function(e) {
        uploadedImage.src = e.target.result;
        uploadedImage.setAttribute('data-caption', file.name);
        uploadedImage.classList.add('clickable-image');
        imageFileName.textContent = `檔案名稱：${file.name}`;
        imagePreview.style.display = 'block';
        
        // 為上傳的預覽圖片綁定點擊事件
        bindImageClickEvents();
    };
    
    reader.readAsDataURL(file);
}

// 表單提交處理函數
async function handleFormSubmit(e) {
    e.preventDefault();
    
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
        alert('請選擇一個圖片檔案');
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
    
    // 圖片預覽在sidebar中，保持顯示
    
    try {
        const response = await fetch('/ocr', {
            method: 'POST',
            body: formData
        });
        
        const result = await response.json();
        
        if (result.success) {
            resultDiv.innerHTML = createSuccessHTML(result.data);
            updateStatus('success', '處理完成');
            // 為新生成的圖片重新綁定點擊事件
            bindImageClickEvents();
        } else {
            resultDiv.innerHTML = createErrorHTML('識別失敗', result.error);
            updateStatus('error', '處理失敗');
        }
    } catch (error) {
        resultDiv.innerHTML = createErrorHTML('請求失敗', `連接服務器時發生錯誤: ${error.message}`);
        updateStatus('error', '請求失敗');
    }
    
    // 恢復按鈕狀態
    submitButton.disabled = false;
    submitButton.textContent = '上傳並識別';
}

// 創建載入中的HTML
function createLoadingHTML() {
    return `
        <div class="loading">
            <h3>📈 正在處理圖片</h3>
            <p>請稍候，系統正在分析您的圖片並提取關鍵字...</p>
        </div>
    `;
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
