// 將以下函數替換到 batch_task_detail.html 中對應的位置

// loadResults 函數 - 優化為分頁載入
async function loadResults() {
    try {
        const list = document.getElementById('resultsList');
        list.innerHTML = '<p style="text-align: center; color: #6b7280; padding: 40px;">載入中...</p>';

        // 使用分頁載入所有結果
        let offset = 0;
        const limit = 100;
        let allResultsData = [];

        while (true) {
            const response = await fetch(
                `/api/batch-tasks/${taskId}/files?stage2_status=completed&limit=${limit}&offset=${offset}`
            );
            const data = await response.json();

            if (data.success) {
                allResultsData = allResultsData.concat(data.files);

                if (!data.pagination || !data.pagination.has_more) {
                    break;
                }
                offset += limit;
            } else {
                break;
            }
        }

        if (allResultsData.length === 0) {
            list.innerHTML = '<p style="text-align: center; color: #6b7280; padding: 40px;">尚無 OCR 結果</p>';
            return;
        }

        const folderTree = buildFolderTree(allResultsData);
        const sortedFolders = Object.keys(folderTree).sort();

        list.innerHTML = sortedFolders.map(folderPath => {
            const folderFiles = folderTree[folderPath];
            const folderId = 'results_folder_' + safeBtoa(folderPath).replace(/[^a-zA-Z0-9]/g, '_');

            return `
                <div class="result-tree-folder">
                    <div class="result-folder-header" onclick="toggleResultsFolder('${folderId}')">
                        <span class="file-folder-toggle" id="${folderId}_toggle">▶</span>
                        <span class="file-folder-path">📁 ${folderPath}</span>
                        <span class="file-folder-count">(${folderFiles.length} 個檔案)</span>
                    </div>
                    <div class="result-folder-content" id="${folderId}">
                        ${renderResultItems(folderFiles)}
                    </div>
                </div>
            `;
        }).join('');
    } catch (error) {
        console.error('載入 OCR 結果失敗:', error);
        list.innerHTML = '<p style="text-align: center; color: #dc2626; padding: 40px;">載入失敗</p>';
    }
}

// updateErrorCount 函數 - 使用統計API而不是載入所有檔案
async function updateErrorCount() {
    try {
        // 使用統計資訊取得錯誤計數,避免載入大量資料
        const response = await fetch(`/api/batch-tasks/${taskId}`);
        const data = await response.json();

        if (data.success && data.statistics) {
            const failedCount = (data.statistics.stage1_failed || 0) + (data.statistics.stage2_failed || 0);
            document.getElementById('errorCount').textContent = failedCount;
        }
    } catch (error) {
        console.error('更新錯誤計數失敗:', error);
    }
}

// loadErrors 函數 - 分頁載入失敗的檔案
async function loadErrors() {
    try {
        const list = document.getElementById('errorsList');
        list.innerHTML = '<p style="text-align: center; color: #6b7280; padding: 40px;">載入中...</p>';

        // 分頁載入所有檔案,然後在客戶端過濾失敗的
        let offset = 0;
        const limit = 100;
        let allFilesData = [];

        while (true) {
            const response = await fetch(`/api/batch-tasks/${taskId}/files?limit=${limit}&offset=${offset}`);
            const data = await response.json();

            if (data.success) {
                allFilesData = allFilesData.concat(data.files);

                if (!data.pagination || !data.pagination.has_more) {
                    break;
                }
                offset += limit;
            } else {
                break;
            }
        }

        // 過濾出失敗的檔案
        const failedFiles = allFilesData.filter(f =>
            f.stage1_status === 'failed' || f.stage2_status === 'failed'
        );

        if (failedFiles.length === 0) {
            list.innerHTML = '<p style="text-align: center; color: #6b7280; padding: 40px;">🎉 沒有錯誤！所有檔案處理正常</p>';
            return;
        }

        const folderTree = buildFolderTree(failedFiles);
        const sortedFolders = Object.keys(folderTree).sort();

        list.innerHTML = sortedFolders.map(folderPath => {
            const folderFiles = folderTree[folderPath];
            const folderId = 'errors_folder_' + safeBtoa(folderPath).replace(/[^a-zA-Z0-9]/g, '_');

            return `
                <div class="result-tree-folder">
                    <div class="result-folder-header" onclick="toggleErrorsFolder('${folderId}')">
                        <span class="file-folder-toggle" id="${folderId}_toggle">▶</span>
                        <span class="file-folder-path">📁 ${folderPath}</span>
                        <span class="file-folder-count">(${folderFiles.length} 個錯誤)</span>
                    </div>
                    <div class="result-folder-content" id="${folderId}">
                        ${renderErrorItems(folderFiles)}
                    </div>
                </div>
            `;
        }).join('');
    } catch (error) {
        console.error('載入錯誤列表失敗:', error);
        list.innerHTML = '<p style="text-align: center; color: #dc2626; padding: 40px;">載入失敗</p>';
    }
}
