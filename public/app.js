// DOM Elements
const uploadBox = document.getElementById('upload-box');
const fileInput = document.getElementById('file-input');
const fileList = document.getElementById('file-list');
const transcriptionSection = document.getElementById('transcription-section');
const transcriptionContent = document.getElementById('transcription-content');
const statsSection = document.getElementById('stats-section');
const statsContent = document.getElementById('stats-content');

// API Endpoints
const API_BASE = '/api';
const ENDPOINTS = {
    FILES: `${API_BASE}/files`,
    UPLOAD: `${API_BASE}/upload`,
    TRANSCRIBE: (filename) => `${API_BASE}/transcribe/${encodeURIComponent(filename)}`,
    TRANSCRIPTION: (filename) => `${API_BASE}/transcription/${encodeURIComponent(filename)}`
};

// State
let activeFile = null;
let pollingInterval = null;

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

// Initialize
loadFiles();

// File Handling Functions
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

async function uploadFile(file) {
    const formData = new FormData();
    formData.append('file', file);

    try {
        const response = await fetch(ENDPOINTS.UPLOAD, {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) {
            throw new Error('Upload failed');
        }

        const data = await response.json();
        console.log('Upload successful:', data);
        loadFiles();
        
        // Start transcription
        startTranscription(file.name);
    } catch (error) {
        console.error('Error uploading file:', error);
        alert('Error uploading file. Please try again.');
    }
}

// File List Functions
async function loadFiles() {
    try {
        const response = await fetch(ENDPOINTS.FILES);
        if (!response.ok) {
            throw new Error('Failed to load files');
        }
        
        const data = await response.json();
        displayFiles(data.files);
    } catch (error) {
        console.error('Error loading files:', error);
    }
}

function displayFiles(files) {
    fileList.innerHTML = '';
    
    if (files.length === 0) {
        fileList.innerHTML = '<p class="text-muted">No files uploaded yet</p>';
        return;
    }

    const table = document.createElement('table');
    table.className = 'table';
    table.innerHTML = `
        <thead>
            <tr>
                <th>File</th>
                <th>Size</th>
                <th>Status</th>
                <th>Action</th>
            </tr>
        </thead>
        <tbody></tbody>
    `;

    files.forEach(file => {
        const row = document.createElement('tr');
        const progressBar = file.transcription_status === 'processing' ? 
            `<div class="progress ms-2" style="width: 100px;">
                <div class="progress-bar progress-bar-striped progress-bar-animated" 
                     style="width: ${file.stats?.progress || 0}%"></div>
            </div>` : '';

        const actionButton = file.transcription_status === 'complete' ? 
            `<button class="btn btn-sm btn-primary view-btn" data-filename="${file.filename}">
                View Transcription
            </button>` :
            file.transcription_status === null ? 
            `<button class="btn btn-sm btn-success transcribe-btn" data-filename="${file.filename}">
                Start Transcription
            </button>` : '';

        row.innerHTML = `
            <td>${file.filename}</td>
            <td>${file.size.toFixed(2)} MB</td>
            <td>
                <div class="d-flex align-items-center">
                    ${getStatusBadge(file.transcription_status)}
                    ${progressBar}
                </div>
            </td>
            <td>${actionButton}</td>
        `;

        const viewBtn = row.querySelector('.view-btn');
        if (viewBtn) {
            viewBtn.addEventListener('click', () => viewTranscription(file.filename));
        }

        const transcribeBtn = row.querySelector('.transcribe-btn');
        if (transcribeBtn) {
            transcribeBtn.addEventListener('click', () => startTranscription(file.filename));
        }

        table.querySelector('tbody').appendChild(row);
    });

    fileList.appendChild(table);
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
    try {
        const response = await fetch(ENDPOINTS.TRANSCRIBE(filename));
        if (!response.ok) {
            throw new Error('Failed to start transcription');
        }
        
        activeFile = filename;
        startPolling();
    } catch (error) {
        console.error('Error starting transcription:', error);
        alert('Error starting transcription. Please try again.');
    }
}

function startPolling() {
    if (pollingInterval) {
        clearInterval(pollingInterval);
    }
    
    pollingInterval = setInterval(loadFiles, 5000);
}

async function viewTranscription(filename) {
    try {
        const response = await fetch(ENDPOINTS.TRANSCRIPTION(filename));
        if (!response.ok) {
            throw new Error('Failed to load transcription');
        }
        
        const data = await response.json();
        displayTranscription(data.transcription);
        displayStats(data.stats);
    } catch (error) {
        console.error('Error loading transcription:', error);
        alert('Error loading transcription. Please try again.');
    }
}

function displayTranscription(segments) {
    transcriptionSection.style.display = 'block';
    transcriptionContent.innerHTML = '';

    segments.forEach(segment => {
        const div = document.createElement('div');
        div.className = 'mb-3';
        div.innerHTML = `
            <div class="d-flex">
                <strong class="me-2">${segment.speaker}:</strong>
                <span>${segment.text}</span>
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
                        `<li>${step}: ${time.toFixed(2)}s</li>`
                    ).join('')}
                    <li><strong>Total Time: ${stats.total_time.toFixed(2)}s</strong></li>
                </ul>
            </div>
        </div>
    `;
}

function formatTime(seconds) {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
}
