// Global variables
let activePolls = new Set();
let currentTranscriptionFile = null;

// Initialize event listeners
document.addEventListener('DOMContentLoaded', () => {
    setupUploadBox();
    setupFileTable();
    setupClearAllButton();
    loadFiles();
});

// Setup upload box drag and drop
function setupUploadBox() {
    const uploadBox = document.getElementById('upload-box');
    const fileInput = document.getElementById('file-input');

    uploadBox.addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', handleFileSelect);

    uploadBox.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadBox.style.borderColor = '#666';
    });

    uploadBox.addEventListener('dragleave', () => {
        uploadBox.style.borderColor = '#ccc';
    });

    uploadBox.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadBox.style.borderColor = '#ccc';
        const files = e.dataTransfer.files;
        if (files.length) handleFileUpload(files[0]);
    });
}

// Handle file selection
async function handleFileSelect(e) {
    const file = e.target.files[0];
    if (file) await handleFileUpload(file);
    e.target.value = ''; // Reset input
}

// Handle file upload
async function handleFileUpload(file) {
    const formData = new FormData();
    formData.append('file', file);

    try {
        const response = await fetch('/api/upload', {
            method: 'POST',
            body: formData
        });

        const result = await response.json();
        if (!response.ok) throw new Error(result.error);

        // Show warning if file was renamed
        if (result.warning) {
            showAlert(result.warning, 'warning');
        }

        await loadFiles();
        startTranscription(result.name);
    } catch (error) {
        showAlert(`Upload failed: ${error.message}`, 'danger');
    }
}

// Load file list
async function loadFiles() {
    try {
        const response = await fetch('/api/files');
        const data = await response.json();
        updateFileTable(data.files);
        document.getElementById('clear-all-container').style.display = data.files.length ? 'block' : 'none';
    } catch (error) {
        showAlert('Failed to load files', 'danger');
    }
}

// Start transcription
async function startTranscription(filename) {
    try {
        const response = await fetch(`/api/transcribe/${encodeURIComponent(filename)}`);
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || 'Failed to start transcription');
        }
        pollTranscriptionStatus(filename);
    } catch (error) {
        showAlert(`Transcription failed: ${error.message}`, 'danger');
    }
}

// Poll transcription status
function pollTranscriptionStatus(filename) {
    if (activePolls.has(filename)) return;
    activePolls.add(filename);

    const pollInterval = setInterval(async () => {
        try {
            const response = await fetch(`/api/status/${encodeURIComponent(filename)}`);
            const data = await response.json();

            updateFileStatus(filename, data);

            // Check for warnings in step_info
            if (data.step_info?.warnings?.length > 0) {
                data.step_info.warnings.forEach(warning => {
                    showAlert(warning, 'warning');
                });
            }

            // Handle completion or error
            if (['complete', 'error', 'stopped'].includes(data.status)) {
                clearInterval(pollInterval);
                activePolls.delete(filename);
                
                if (data.status === 'complete') {
                    await loadTranscription(filename);
                }
            }
        } catch (error) {
            console.error('Status poll failed:', error);
            clearInterval(pollInterval);
            activePolls.delete(filename);
        }
    }, 1000);
}

// Update file status in table
function updateFileStatus(filename, status) {
    const row = document.querySelector(`tr[data-file="${filename}"]`);
    if (!row) return;

    const statusCell = row.querySelector('.status-cell');
    const progressBar = row.querySelector('.progress-bar');
    
    if (status.error) {
        statusCell.innerHTML = `<span class="text-danger">Error: ${status.error}</span>`;
        return;
    }

    let statusText = status.status;
    if (status.status === 'processing') {
        statusText = `${status.step || 'Processing'} (${Math.round(status.progress || 0)}%)`;
        if (progressBar) {
            progressBar.style.width = `${status.progress || 0}%`;
            progressBar.setAttribute('aria-valuenow', status.progress || 0);
        }
    }

    statusCell.textContent = statusText;
}

// Load transcription
async function loadTranscription(filename) {
    try {
        const response = await fetch(`/api/transcription/${encodeURIComponent(filename)}`);
        const data = await response.json();
        
        if (!response.ok) throw new Error(data.error);
        
        displayTranscription(data);
        
        // Show warning if diarization was skipped
        if (data.stats?.metadata?.diarization_error) {
            showAlert(data.stats.metadata.diarization_error, 'warning');
        }
        
    } catch (error) {
        showAlert(`Failed to load transcription: ${error.message}`, 'danger');
    }
}

// Display transcription
function displayTranscription(data) {
    const transcriptionSection = document.getElementById('transcription-section');
    const transcriptionContent = document.getElementById('transcription-content');
    const statsSection = document.getElementById('stats-section');
    const statsContent = document.getElementById('stats-content');

    // Format and display transcription
    let html = '<div class="mb-4">';
    if (data.transcription) {
        data.transcription.forEach(segment => {
            html += `<p class="mb-2">
                <small class="text-muted">[${formatTime(segment.start)} - ${formatTime(segment.end)}]</small>
                ${segment.speaker ? `<strong>${segment.speaker}:</strong> ` : ''}
                ${segment.text}
            </p>`;
        });
    }
    html += '</div>';

    transcriptionContent.innerHTML = html;
    transcriptionSection.style.display = 'block';

    // Display stats if available
    if (data.stats) {
        let statsHtml = '<dl class="row">';
        statsHtml += `<dt class="col-sm-3">Duration</dt>
                     <dd class="col-sm-9">${formatTime(data.stats.duration)}</dd>`;
        
        if (data.stats.metadata) {
            statsHtml += `<dt class="col-sm-3">Language</dt>
                         <dd class="col-sm-9">${data.stats.language || 'Unknown'}</dd>`;
            
            if (data.stats.metadata.has_diarization) {
                statsHtml += `<dt class="col-sm-3">Speakers</dt>
                             <dd class="col-sm-9">${data.stats.speakers?.length || 0}</dd>`;
            }
        }
        statsHtml += '</dl>';
        
        statsContent.innerHTML = statsHtml;
        statsSection.style.display = 'block';
    }
}

// Helper: Format time in seconds to MM:SS
function formatTime(seconds) {
    if (!seconds && seconds !== 0) return '--:--';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
}

// Helper: Show alert message
function showAlert(message, type = 'info') {
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
    `;
    
    const container = document.querySelector('.container');
    container.insertBefore(alertDiv, container.firstChild);
    
    // Auto-dismiss after 5 seconds
    setTimeout(() => {
        alertDiv.classList.remove('show');
        setTimeout(() => alertDiv.remove(), 150);
    }, 5000);
}
