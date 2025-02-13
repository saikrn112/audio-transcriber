// DOM Elements
const uploadBox = document.getElementById('upload-box');
const fileInput = document.getElementById('file-input');
const fileList = document.getElementById('file-list');
const transcriptionSection = document.getElementById('transcription-section');
const transcriptionContent = document.getElementById('transcription-content');
const statsSection = document.getElementById('stats-section');
const statsContent = document.getElementById('stats-content');
const downloadTxtBtn = document.getElementById('download-txt');
const downloadJsonBtn = document.getElementById('download-json');
const clearAllBtn = document.getElementById('clear-all-btn');
const clearAllContainer = document.getElementById('clear-all-container');

// API Endpoints
const API_BASE = '/api';
const ENDPOINTS = {
    FILES: `${API_BASE}/files`,
    UPLOAD: `${API_BASE}/upload`,
    TRANSCRIBE: (filename) => `${API_BASE}/transcribe/${encodeURIComponent(filename)}`,
    RETRANSCRIBE: (filename) => `${API_BASE}/retranscribe/${encodeURIComponent(filename)}`,
    STOP: (filename) => `${API_BASE}/stop/${encodeURIComponent(filename)}`,
    TRANSCRIPTION: (filename) => `${API_BASE}/transcription/${encodeURIComponent(filename)}`,
    DELETE: (filename) => `${API_BASE}/delete/${encodeURIComponent(filename)}`,
    DELETE_ALL: `${API_BASE}/delete-all`,
    CLEANUP_STATUS: `${API_BASE}/cleanup-status`
};

// Helper function to sanitize filename
function sanitizeFilename(filename) {
    return filename.replace(/[^a-zA-Z0-9.-]/g, '_');
}

// State
let activeFile = null;
let pollingInterval = null;
let currentTranscription = null;

// Event Listeners
uploadBox.addEventListener('click', () => fileInput.click());
uploadBox.addEventListener('dragover', (e) => {
    e.preventDefault();
    uploadBox.style.borderColor = '#666';
});
uploadBox.addEventListener('dragleave', () => {
    uploadBox.style.borderColor = '#ccc';
});
uploadBox.addEventListener('drop', handleFileDrop);
fileInput.addEventListener('change', handleFileSelect);

// Initialize the application
document.addEventListener('DOMContentLoaded', async () => {
    const uploadBox = document.getElementById('upload-box');
    const fileInput = document.getElementById('file-input');
    const clearAllBtn = document.getElementById('clear-all-btn');
    const clearAllContainer = document.getElementById('clear-all-container');
    
    if (!uploadBox || !fileInput) {
        console.error('Required elements not found');
        return;
    }
    
    // Setup file upload handling
    uploadBox.addEventListener('click', () => fileInput.click());
    uploadBox.addEventListener('dragover', (e) => {
        e.preventDefault();
        e.stopPropagation();
        uploadBox.style.borderColor = '#666';
    });
    
    uploadBox.addEventListener('dragleave', (e) => {
        e.preventDefault();
        e.stopPropagation();
        uploadBox.style.borderColor = '#ccc';
    });
    
    uploadBox.addEventListener('drop', (e) => {
        e.preventDefault();
        e.stopPropagation();
        uploadBox.style.borderColor = '#ccc';
        
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            handleFiles(files);
        }
    });
    
    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            handleFiles(e.target.files);
        }
    });
    
    // Setup clear all button
    if (clearAllBtn) {
        clearAllBtn.addEventListener('click', async () => {
            if (confirm('Are you sure you want to delete all files? This cannot be undone.')) {
                await deleteAllFiles();
            }
        });
    }
    
    // Load initial file list
    await loadFiles();
});

async function loadFiles() {
    const table = document.getElementById('file-table');
    const clearAllContainer = document.getElementById('clear-all-container');
    
    if (!table) {
        console.error('File table not found');
        return;
    }
    
    const tbody = table.querySelector('tbody');
    if (!tbody) {
        console.error('Table body not found');
        return;
    }
    
    try {
        const response = await fetch(ENDPOINTS.FILES);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        const files = data.files || [];
        
        // Update clear all button visibility
        if (clearAllContainer) {
            clearAllContainer.style.display = files.length > 0 ? 'block' : 'none';
        }
        
        // Clear existing rows
        tbody.innerHTML = '';
        
        if (files.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="4" class="text-center text-muted py-4">
                        No files uploaded yet
                    </td>
                </tr>
            `;
            return;
        }
        
        // Add file rows
        files.forEach(file => {
            const row = createFileRow(file);
            tbody.appendChild(row);
        });
        
        // Start polling if there are processing files
        const hasProcessingFiles = files.some(f => f.transcription_status === 'processing');
        if (hasProcessingFiles) {
            startPolling();
        }
    } catch (error) {
        console.error('Error loading files:', error);
        tbody.innerHTML = `
            <tr>
                <td colspan="4" class="text-center text-danger py-4">
                    <i class="bi bi-exclamation-triangle-fill"></i>
                    Failed to load files. Please refresh the page.
                </td>
            </tr>
        `;
    }
}

// Check for cleanup status on page load
async function checkCleanupStatus() {
    try {
        const response = await fetch(ENDPOINTS.CLEANUP_STATUS);
        if (!response.ok) {
            throw new Error('Failed to get cleanup status');
        }
        
        const data = await response.json();
        if (data.incomplete_files && data.incomplete_files.length > 0) {
            const warningDiv = document.createElement('div');
            warningDiv.className = 'alert alert-warning alert-dismissible fade show mb-3';
            warningDiv.innerHTML = `
                <div>
                    <i class="bi bi-exclamation-triangle-fill"></i>
                    <strong>Notice:</strong> Some files were in an incomplete state and have been reset:
                    <ul class="mb-0 mt-1">
                        ${data.incomplete_files.map(file => `<li>${file}</li>`).join('')}
                    </ul>
                    <div class="mt-2 small text-muted">You can restart transcription for these files when ready.</div>
                </div>
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            `;
            document.querySelector('.container').insertBefore(warningDiv, document.querySelector('.container').firstChild);
            
            // Auto-dismiss after 10 seconds
            setTimeout(() => {
                warningDiv.classList.remove('show');
                setTimeout(() => warningDiv.remove(), 150);
            }, 10000);
        }
    } catch (error) {
        console.error('Error checking cleanup status:', error);
    }
}

// File Handling Functions
async function handleFiles(files) {
    for (const file of files) {
        if (!isValidAudioFile(file)) {
            alert(`Invalid file type: ${file.name}\nSupported formats: WAV, MP3, OGG, FLAC, M4A`);
            continue;
        }
        await uploadFile(file);
    }
}

function isValidAudioFile(file) {
    const validTypes = ['audio/wav', 'audio/mpeg', 'audio/ogg', 'audio/flac', 'audio/mp4'];
    return validTypes.includes(file.type);
}

async function uploadFile(file) {
    const formData = new FormData();
    formData.append('file', file);
    
    try {
        const response = await fetch(ENDPOINTS.UPLOAD, {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        await loadFiles();
    } catch (error) {
        console.error('Error uploading file:', error);
        alert(`Failed to upload ${file.name}. Please try again.`);
    }
}

function handleFileDrop(e) {
    e.preventDefault();
    uploadBox.style.borderColor = '#ccc';
    const files = e.dataTransfer.files;
    if (files.length > 0) {
        uploadFile(files[0]);
    }
}

function handleFileSelect(e) {
    const files = e.target.files;
    if (files.length > 0) {
        uploadFile(files[0]);
    }
}

// File List Functions
function createFileRow(file) {
    const row = document.createElement('tr');
    row.dataset.filename = file.name;
    
    // Create progress bar for processing status
    let progressBar = '';
    let statusInfo = '';
    
    if (file.transcription_status === 'processing') {
        const progress = file.stats?.progress || 0;
        const step = file.stats?.current_step || 'Processing';
        const totalSteps = file.stats?.total_steps || 1;
        const currentStep = file.stats?.step_number || 1;
        
        progressBar = `
            <div class="progress mt-2" style="height: 5px;">
                <div class="progress-bar progress-bar-striped progress-bar-animated" 
                     role="progressbar" style="width: ${progress}%;" 
                     aria-valuenow="${progress}" aria-valuemin="0" aria-valuemax="100">
                </div>
            </div>
        `;
        
        statusInfo = `
            <div class="text-muted small mt-1">
                ${step} (Step ${currentStep}/${totalSteps})
            </div>
        `;
    }
    
    // Prepare action buttons
    const actionButtons = [];
    
    if (file.transcription_status === 'complete') {
        actionButtons.push(`
            <button class="btn btn-sm btn-primary view-btn">
                <i class="bi bi-eye"></i> View
            </button>
            <button class="btn btn-sm btn-warning retranscribe-btn ms-2">
                <i class="bi bi-arrow-clockwise"></i> Re-transcribe
            </button>
        `);
    } else if (file.transcription_status === 'processing') {
        actionButtons.push(`
            <button class="btn btn-sm btn-danger stop-btn">
                <i class="bi bi-stop-circle"></i> Stop
            </button>
        `);
    } else {
        actionButtons.push(`
            <button class="btn btn-sm btn-success transcribe-btn">
                <i class="bi bi-play"></i> Start
            </button>
        `);
    }
    
    // Add delete button (disabled during processing)
    actionButtons.push(`
        <button class="btn btn-sm btn-danger delete-btn ms-2"
                ${file.transcription_status === 'processing' ? 'disabled' : ''}>
            <i class="bi bi-trash"></i> Delete
        </button>
    `);
    
    row.innerHTML = `
        <td>${file.name}</td>
        <td>${file.size.toFixed(2)} MB</td>
        <td class="status">
            <div class="d-flex flex-column">
                ${getStatusBadge(file.transcription_status)}
                ${statusInfo}
                ${progressBar}
            </div>
        </td>
        <td class="actions">
            <div class="btn-group">
                ${actionButtons.join('')}
            </div>
        </td>
    `;
    
    // Add event listeners
    const viewBtn = row.querySelector('.view-btn');
    if (viewBtn) {
        viewBtn.addEventListener('click', () => viewTranscription(file.name));
    }
    
    const transcribeBtn = row.querySelector('.transcribe-btn');
    if (transcribeBtn) {
        transcribeBtn.addEventListener('click', () => startTranscription(file.name));
    }
    
    const retranscribeBtn = row.querySelector('.retranscribe-btn');
    if (retranscribeBtn) {
        retranscribeBtn.addEventListener('click', () => retranscribe(file.name));
    }
    
    const stopBtn = row.querySelector('.stop-btn');
    if (stopBtn) {
        stopBtn.addEventListener('click', () => stopTranscription(file.name));
    }
    
    const deleteBtn = row.querySelector('.delete-btn');
    if (deleteBtn) {
        deleteBtn.addEventListener('click', () => deleteFile(file.name));
    }
    
    return row;
}

function getStatusBadge(status) {
    const badges = {
        'complete': '<span class="badge bg-success">Complete</span>',
        'processing': '<span class="badge bg-primary">Processing</span>',
        'error': '<span class="badge bg-danger">Error</span>'
    };
    return badges[status] || '<span class="badge bg-secondary">Not Started</span>';
}

// Transcription Functions
async function startTranscription(filename) {
    if (!filename) {
        console.error('No filename provided to startTranscription');
        return;
    }
    
    try {
        const response = await fetch(ENDPOINTS.TRANSCRIBE(filename));
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        await loadFiles(); // Refresh the file list
    } catch (error) {
        console.error('Error starting transcription:', error);
        alert('Failed to start transcription. Please try again.');
    }
}

async function retranscribe(filename) {
    if (!confirm(`Are you sure you want to re-transcribe ${filename}? This will delete the existing transcription.`)) {
        return;
    }

    try {
        const response = await fetch(ENDPOINTS.RETRANSCRIBE(filename), {
            method: 'POST'
        });
        if (!response.ok) {
            throw new Error('Failed to start re-transcription');
        }
        startPolling();
    } catch (error) {
        console.error('Error starting re-transcription:', error);
        alert('Error starting re-transcription. Please try again.');
    }
}

async function stopTranscription(filename) {
    if (!confirm(`Are you sure you want to stop the transcription of ${filename}?`)) {
        return;
    }

    try {
        const response = await fetch(ENDPOINTS.STOP(filename), {
            method: 'POST'
        });
        if (!response.ok) {
            throw new Error('Failed to stop transcription');
        }
        await loadFiles();
    } catch (error) {
        console.error('Error stopping transcription:', error);
        alert('Error stopping transcription. Please try again.');
    }
}

function startPolling() {
    if (pollingInterval) {
        clearInterval(pollingInterval);
    }
    
    // Poll every 2 seconds
    pollingInterval = setInterval(async () => {
        try {
            const response = await fetch(ENDPOINTS.FILES);
            if (!response.ok) {
                throw new Error('Failed to load files');
            }
            
            const data = await response.json();
            // Ensure we're working with the files array from the response
            const files = data.files || [];
            
            const table = document.getElementById('file-table');
            const tbody = table.querySelector('tbody');
            tbody.innerHTML = ''; // Clear existing rows
            
            if (files.length === 0) {
                tbody.innerHTML = `
                    <tr>
                        <td colspan="4" class="text-center text-muted py-4">
                            No files uploaded yet
                        </td>
                    </tr>
                `;
                return;
            }
            
            files.forEach(file => {
                const row = createFileRow(file);
                tbody.appendChild(row);
            });
            
            // Stop polling if no files are being processed
            const hasProcessingFiles = files.some(f => f.transcription_status === 'processing');
            if (!hasProcessingFiles) {
                clearInterval(pollingInterval);
                pollingInterval = null;
            }
        } catch (error) {
            console.error('Error during polling:', error);
        }
    }, 2000);
}

async function viewTranscription(filename) {
    try {
        const response = await fetch(ENDPOINTS.TRANSCRIPTION(filename));
        if (!response.ok) {
            throw new Error('Failed to load transcription');
        }
        
        const data = await response.json();
        currentTranscription = data.transcription;
        displayTranscription(currentTranscription);
        displayStats(data.stats);
        setupDownloadButtons(filename);
    } catch (error) {
        console.error('Error loading transcription:', error);
        alert('Error loading transcription. Please try again.');
    }
}

function setupDownloadButtons(filename) {
    const downloadTxtBtn = document.getElementById('download-txt');
    const downloadJsonBtn = document.getElementById('download-json');
    
    downloadTxtBtn.onclick = () => downloadTranscription(filename, 'txt');
    downloadJsonBtn.onclick = () => downloadTranscription(filename, 'json');
}

function downloadTranscription(filename, format) {
    if (!currentTranscription) {
        alert('No transcription available to download');
        return;
    }

    let content;
    let downloadFilename;
    let mimeType;

    if (format === 'txt') {
        content = currentTranscription.map(segment => 
            `[${formatTime(segment.start)} - ${formatTime(segment.end)}] ${segment.speaker || 'Unknown'}: ${segment.text}`
        ).join('\n\n');
        downloadFilename = `${filename.split('.')[0]}_transcript.txt`;
        mimeType = 'text/plain';
    } else {
        content = JSON.stringify(currentTranscription, null, 2);
        downloadFilename = `${filename.split('.')[0]}_transcript.json`;
        mimeType = 'application/json';
    }

    const blob = new Blob([content], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = downloadFilename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

function displayTranscription(segments) {
    transcriptionSection.style.display = 'block';
    transcriptionContent.innerHTML = '';

    if (!Array.isArray(segments)) {
        transcriptionContent.innerHTML = '<p class="text-muted">No transcription available</p>';
        return;
    }

    segments.forEach(segment => {
        const div = document.createElement('div');
        div.className = 'mb-3';
        div.innerHTML = `
            <div class="d-flex">
                <strong class="me-2">${segment.speaker || 'Unknown'}:</strong>
                <span>${segment.text || ''}</span>
            </div>
            <small class="text-muted">
                ${formatTime(segment.start)} - ${formatTime(segment.end)}
            </small>
        `;
        transcriptionContent.appendChild(div);
    });
}

function displayStats(stats) {
    statsSection.style.display = 'block';
    
    if (!stats) {
        statsContent.innerHTML = '<p class="text-muted">No statistics available</p>';
        return;
    }

    const transcriptionInfo = stats.transcription_info || {};
    const steps = stats.steps || {};
    
    statsContent.innerHTML = `
        <div class="row">
            <div class="col-md-6">
                <h6>Transcription Info</h6>
                <ul class="list-unstyled">
                    <li>Language: ${transcriptionInfo.language || 'Unknown'}</li>
                    <li>Number of Speakers: ${transcriptionInfo.num_speakers || 1}</li>
                    <li>Duration: ${formatTime(transcriptionInfo.duration || 0)}</li>
                    <li>Speaker Diarization: ${transcriptionInfo.diarization_available ? 'Yes' : 'No'}</li>
                </ul>
            </div>
            <div class="col-md-6">
                <h6>Processing Times</h6>
                <ul class="list-unstyled">
                    ${Object.entries(steps).map(([step, time]) => 
                        `<li>${step}: ${(time || 0).toFixed(2)}s</li>`
                    ).join('')}
                    <li><strong>Total Time: ${(stats.total_time || 0).toFixed(2)}s</strong></li>
                </ul>
            </div>
        </div>
    `;
}

function formatTime(seconds) {
    if (!seconds) return '0:00';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
}

async function deleteFile(filename) {
    if (!confirm(`Are you sure you want to delete ${filename}?`)) {
        return;
    }

    try {
        const response = await fetch(ENDPOINTS.DELETE(filename), {
            method: 'DELETE'
        });

        if (!response.ok) {
            throw new Error('Failed to delete file');
        }

        await loadFiles();
    } catch (error) {
        console.error('Error deleting file:', error);
        alert('Error deleting file. Please try again.');
    }
}

async function deleteAllFiles() {
    if (!confirm('Are you sure you want to delete all files? This action cannot be undone.')) {
        return;
    }

    try {
        const response = await fetch(ENDPOINTS.DELETE_ALL, {
            method: 'DELETE'
        });

        if (!response.ok) {
            throw new Error('Failed to delete all files');
        }

        await loadFiles();
    } catch (error) {
        console.error('Error deleting all files:', error);
        alert('Error deleting all files. Please try again.');
    }
}

function updateFileStatus(file, status) {
    const fileRow = document.querySelector(`[data-filename="${file.name}"]`);
    if (!fileRow) return;
    
    const statusCell = fileRow.querySelector('.status');
    const progressBar = fileRow.querySelector('.progress-bar');
    const actionButtons = fileRow.querySelector('.actions');
    
    // Update status text and progress
    if (status.status === 'processing') {
        const stepInfo = status.step_info || {};
        const stepNumber = stepInfo.step_number || 0;
        const totalSteps = stepInfo.total_steps || 1;
        const stepName = stepInfo.step_name || 'Processing';
        const progress = status.progress || 0;
        
        // Update status text
        statusCell.innerHTML = `
            <div class="d-flex align-items-center">
                <div class="spinner-border spinner-border-sm me-2" role="status">
                    <span class="visually-hidden">Processing...</span>
                </div>
                <div>
                    <div>${stepName} (Step ${stepNumber}/${totalSteps})</div>
                    <small class="text-muted">${status.step || ''}</small>
                </div>
            </div>
        `;
        
        // Update progress bar
        progressBar.style.width = `${progress}%`;
        progressBar.setAttribute('aria-valuenow', progress);
        
        // Show stop button
        actionButtons.innerHTML = `
            <button class="btn btn-danger btn-sm" onclick="stopTranscription('${file.name}')">
                <i class="bi bi-stop-fill"></i> Stop
            </button>
        `;
    } else if (status.status === 'complete') {
        statusCell.innerHTML = `
            <div class="text-success">
                <i class="bi bi-check-circle-fill"></i> Complete
            </div>
        `;
        progressBar.style.width = '100%';
        progressBar.classList.remove('progress-bar-striped', 'progress-bar-animated');
        progressBar.classList.add('bg-success');
        updateActionButtons(file, actionButtons);
    } else if (status.status === 'error') {
        statusCell.innerHTML = `
            <div class="text-danger">
                <i class="bi bi-exclamation-circle-fill"></i> Error
                <small class="d-block text-muted">${status.error || 'Unknown error'}</small>
            </div>
        `;
        progressBar.style.width = '100%';
        progressBar.classList.remove('progress-bar-striped', 'progress-bar-animated');
        progressBar.classList.add('bg-danger');
        updateActionButtons(file, actionButtons);
    } else if (status.status === 'stopped') {
        statusCell.innerHTML = `
            <div class="text-warning">
                <i class="bi bi-pause-circle-fill"></i> Stopped
            </div>
        `;
        progressBar.classList.remove('progress-bar-striped', 'progress-bar-animated');
        progressBar.classList.add('bg-warning');
        updateActionButtons(file, actionButtons);
    }
}

function updateActionButtons(file, actionButtons) {
    actionButtons.innerHTML = `
        <button class="btn btn-sm btn-primary view-btn" data-filename="${file.name}">
            <i class="bi bi-eye"></i> View
        </button>
        <button class="btn btn-sm btn-warning retranscribe-btn ms-2" data-filename="${file.name}">
            <i class="bi bi-arrow-clockwise"></i> Re-transcribe
        </button>
        <button class="btn btn-sm btn-danger delete-btn ms-2" data-filename="${file.name}">
            <i class="bi bi-trash"></i> Delete
        </button>
    `;
}
