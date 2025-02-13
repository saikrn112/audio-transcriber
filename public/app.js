const FileUpload = React.memo(({ onUpload }) => {
    const [isDragging, setIsDragging] = React.useState(false);
    const [isUploading, setIsUploading] = React.useState(false);
    const fileInputRef = React.useRef(null);

    const handleDragEnter = (e) => {
        e.preventDefault();
        e.stopPropagation();
        setIsDragging(true);
    };

    const handleDragLeave = (e) => {
        e.preventDefault();
        e.stopPropagation();
        setIsDragging(false);
    };

    const handleDrop = async (e) => {
        e.preventDefault();
        e.stopPropagation();
        setIsDragging(false);

        const files = e.dataTransfer.files;
        if (files.length > 0) {
            await handleFiles(files);
        }
    };

    const handleFileSelect = async (e) => {
        const files = e.target.files;
        if (files.length > 0) {
            await handleFiles(files);
        }
    };

    const handleFiles = async (files) => {
        setIsUploading(true);
        try {
            for (const file of files) {
                console.log('Uploading file:', file.name);
                const formData = new FormData();
                formData.append('file', file);

                const response = await fetch('/api/upload', {
                    method: 'POST',
                    body: formData
                });

                const data = await response.json();
                console.log('Upload response:', data);

                if (!response.ok) {
                    throw new Error(data.error || 'Upload failed');
                }

                console.log('Upload successful');
                onUpload();
            }
        } catch (error) {
            console.error('Error uploading file:', error);
            alert(`Error uploading file: ${error.message}`);
        } finally {
            setIsUploading(false);
        }
    };

    const handleClick = () => {
        if (!isUploading && fileInputRef.current) {
            fileInputRef.current.click();
        }
    };

    return React.createElement('div', {
        className: `p-8 border-2 border-dashed rounded-lg text-center cursor-pointer transition-colors ${
            isDragging ? 'border-blue-500 bg-blue-50' : 'border-gray-300'
        }`,
        onDragEnter: handleDragEnter,
        onDragOver: handleDragEnter,
        onDragLeave: handleDragLeave,
        onDrop: handleDrop,
        onClick: handleClick
    }, [
        React.createElement('input', {
            type: 'file',
            ref: fileInputRef,
            onChange: handleFileSelect,
            className: 'hidden',
            accept: '.wav,.mp3,.ogg,.flac,.m4a',
            multiple: true,
            disabled: isUploading,
            key: 'file-input'
        }),
        React.createElement('div', {
            className: 'text-gray-600',
            key: 'text-content'
        }, [
            isUploading ? [
                React.createElement('p', { 
                    className: 'mb-2',
                    key: 'uploading-text'
                }, 'Uploading...'),
                React.createElement('div', {
                    className: 'w-8 h-8 border-t-2 border-blue-500 rounded-full animate-spin mx-auto',
                    key: 'spinner'
                })
            ] : [
                React.createElement('p', { 
                    className: 'mb-2',
                    key: 'drag-text'
                }, 'Drag and drop audio files here'),
                React.createElement('p', {
                    className: 'text-sm',
                    key: 'click-text'
                }, 'or click to select files'),
                React.createElement('p', {
                    className: 'text-xs mt-2',
                    key: 'formats-text'
                }, 'Supported formats: WAV, MP3, OGG, FLAC, M4A')
            ]
        ])
    ]);
});

const FileItem = React.memo(({ file, onTranscribe, onViewTranscript }) => {
    const [isTranscribing, setIsTranscribing] = React.useState(false);
    const [error, setError] = React.useState(null);
    
    const handleTranscribe = async () => {
        setIsTranscribing(true);
        setError(null);
        try {
            const response = await fetch(`/api/transcribe/${encodeURIComponent(file.filename)}`);
            if (!response.ok) {
                throw new Error(await response.text());
            }
            // Start polling for status
            pollTranscriptionStatus(file.filename);
        } catch (err) {
            setError(err.message);
            setIsTranscribing(false);
        }
    };
    
    const pollTranscriptionStatus = async (filename) => {
        try {
            const response = await fetch(`/api/files`);
            if (!response.ok) throw new Error('Failed to get status');
            const data = await response.json();
            const fileInfo = data.files.find(f => f.filename === filename);
            
            if (fileInfo) {
                if (fileInfo.transcription_status === 'complete') {
                    setIsTranscribing(false);
                    onViewTranscript(filename);
                } else if (fileInfo.transcription_status === 'error') {
                    setIsTranscribing(false);
                    setError('Transcription failed');
                } else if (fileInfo.transcription_status === 'processing') {
                    setTimeout(() => pollTranscriptionStatus(filename), 2000);
                }
            }
        } catch (err) {
            setError(err.message);
            setIsTranscribing(false);
        }
    };
    
    return React.createElement('div', {
        className: 'bg-white p-4 rounded-lg shadow mb-4 flex items-center justify-between'
    }, [
        React.createElement('div', { key: 'info', className: 'flex-grow' }, [
            React.createElement('h3', {
                className: 'text-lg font-semibold mb-1',
                key: 'filename'
            }, file.filename),
            React.createElement('p', {
                className: 'text-sm text-gray-600',
                key: 'size'
            }, `Size: ${file.size.toFixed(2)} MB`)
        ]),
        React.createElement('div', { key: 'actions', className: 'flex items-center gap-4' }, [
            file.transcription_status === 'complete' ?
                React.createElement('button', {
                    onClick: () => onViewTranscript(file.filename),
                    className: 'bg-green-500 text-white px-4 py-2 rounded hover:bg-green-600 transition-colors',
                    key: 'view'
                }, 'View') :
                React.createElement('button', {
                    onClick: handleTranscribe,
                    disabled: isTranscribing,
                    className: `px-4 py-2 rounded transition-colors ${
                        isTranscribing ? 
                        'bg-gray-400 cursor-not-allowed' : 
                        'bg-blue-500 text-white hover:bg-blue-600'
                    }`,
                    key: 'transcribe'
                }, isTranscribing ? 'Processing...' : 'Transcribe')
        ]),
        error && React.createElement('div', {
            className: 'text-red-500 text-sm ml-4',
            key: 'error'
        }, error)
    ]);
});

const FileList = React.memo(({ files, onTranscribe, onViewTranscription }) => {
    const formatFileSize = (bytes) => {
        const mb = bytes;
        return mb.toFixed(2) + ' MB';
    };

    const getStatusBadge = (status) => {
        const colors = {
            complete: 'bg-green-100 text-green-800',
            processing: 'bg-blue-100 text-blue-800',
            error: 'bg-red-100 text-red-800',
            null: 'bg-gray-100 text-gray-800'
        };

        const text = status ? status.charAt(0).toUpperCase() + status.slice(1) : 'Not Transcribed';
        const colorClass = colors[status || 'null'];

        return React.createElement('span', {
            className: `px-2 py-1 text-sm rounded-full ${colorClass}`
        }, text);
    };

    return React.createElement('div', { className: 'mt-8' }, [
        React.createElement('h2', {
            className: 'text-xl font-semibold mb-4',
            key: 'title'
        }, 'Uploaded Files'),
        files.length === 0 ? 
            React.createElement('p', {
                className: 'text-gray-500 text-center py-4',
                key: 'no-files'
            }, 'No files uploaded yet') :
            files.map((file) => 
                React.createElement(FileItem, {
                    key: file.filename,
                    file: file,
                    onTranscribe: onTranscribe,
                    onViewTranscript: onViewTranscription
                })
            )
    ]);
});

const TranscriptionModal = React.memo(({ transcription, onClose }) => {
    React.useEffect(() => {
        const handleEscape = (e) => {
            if (e.key === 'Escape') {
                onClose();
            }
        };

        document.addEventListener('keydown', handleEscape);
        return () => document.removeEventListener('keydown', handleEscape);
    }, [onClose]);

    if (!transcription) return null;

    const segments = transcription.segments || [];
    const stats = transcription.stats || {};
    const metadata = (stats.transcription_info && stats.transcription_info) || {};

    return React.createElement('div', {
        className: 'fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50'
    }, 
        React.createElement('div', {
            className: 'bg-white rounded-lg w-full max-w-4xl max-h-[90vh] overflow-hidden flex flex-col'
        }, [
            // Header
            React.createElement('div', {
                className: 'p-4 border-b flex justify-between items-center bg-gray-50',
                key: 'header'
            }, [
                React.createElement('div', {
                    key: 'metadata',
                    className: 'flex flex-col'
                }, [
                    React.createElement('h2', {
                        className: 'text-xl font-semibold',
                        key: 'title'
                    }, 'Transcription Results'),
                    React.createElement('div', {
                        className: 'text-sm text-gray-600 mt-1 space-x-4',
                        key: 'info'
                    }, [
                        React.createElement('span', { key: 'language' }, 
                            'Language: ' + (metadata.language || 'Unknown')
                        ),
                        React.createElement('span', { key: 'speakers' }, 
                            'Speakers: ' + (metadata.num_speakers || 1)
                        ),
                        React.createElement('span', { key: 'duration' }, 
                            'Duration: ' + Math.round(metadata.duration || 0) + 's'
                        ),
                        metadata.diarization_available === false && 
                            React.createElement('span', {
                                className: 'text-yellow-600',
                                key: 'diarization-warning'
                            }, '(Speaker detection unavailable - Set HUGGINGFACE_TOKEN for speaker diarization)')
                    ])
                ]),
                React.createElement('button', {
                    onClick: onClose,
                    className: 'text-gray-500 hover:text-gray-700',
                    key: 'close'
                }, '×')
            ]),
            // Transcription content
            React.createElement('div', {
                className: 'p-6 overflow-y-auto flex-grow',
                key: 'content'
            }, 
                segments.map(function(segment, index) {
                    const speaker = segment.speaker || 'UNKNOWN';
                    const start = Math.floor(segment.start || 0);
                    const end = Math.floor(segment.end || 0);
                    const text = (segment.text || '').trim();
                    
                    return React.createElement('div', {
                        key: index,
                        className: 'mb-4'
                    }, [
                        React.createElement('div', {
                            className: 'flex items-center gap-2 text-sm text-gray-600 mb-1',
                            key: 'segment-header'
                        }, [
                            React.createElement('span', {
                                className: 'font-medium',
                                key: 'speaker'
                            }, speaker),
                            React.createElement('span', {
                                key: 'timestamp'
                            }, start + 's - ' + end + 's')
                        ]),
                        React.createElement('p', {
                            className: 'text-gray-800',
                            key: 'text'
                        }, text)
                    ]);
                })
            )
        ])
    );
});

const App = () => {
    const [files, setFiles] = React.useState([]);
    const [transcription, setTranscription] = React.useState(null);

    const loadFiles = React.useCallback(async () => {
        try {
            console.log('Fetching files list...');
            const response = await fetch('/api/files');
            const data = await response.json();
            console.log('Files list response:', data);
            
            if (!response.ok) {
                throw new Error(data.error || 'Failed to load files');
            }
            
            setFiles(data.files || []);
        } catch (error) {
            console.error('Error loading files:', error);
        }
    }, []);

    React.useEffect(() => {
        loadFiles();
        const interval = setInterval(loadFiles, 5000);
        return () => clearInterval(interval);
    }, [loadFiles]);

    const handleTranscribe = React.useCallback(async (filename) => {
        try {
            console.log('Starting transcription for:', filename);
            const response = await fetch(`/api/transcribe/${filename}`);
            const data = await response.json();
            console.log('Transcribe response:', data);
            
            if (!response.ok) {
                throw new Error(data.error || 'Transcription failed');
            }
            
            await loadFiles();
        } catch (error) {
            console.error('Error starting transcription:', error);
            alert(`Error starting transcription: ${error.message}`);
        }
    }, [loadFiles]);

    const handleViewTranscription = React.useCallback(async (filename) => {
        try {
            const response = await fetch(`/api/transcription/${filename}`);
            const data = await response.json();
            setTranscription(data.transcription);
        } catch (error) {
            console.error('Error fetching transcription:', error);
        }
    }, []);

    return React.createElement('div', {
        className: 'container mx-auto px-4 py-8 max-w-4xl'
    }, [
        React.createElement('h1', {
            className: 'text-3xl font-bold mb-8',
            key: 'title'
        }, 'Audio Transcription App'),
        React.createElement(FileUpload, {
            onUpload: loadFiles,
            key: 'upload'
        }),
        React.createElement(FileList, {
            files: files,
            onTranscribe: handleTranscribe,
            onViewTranscription: handleViewTranscription,
            key: 'list'
        }),
        React.createElement(TranscriptionModal, {
            transcription: transcription,
            onClose: () => setTranscription(null),
            key: 'modal'
        })
    ]);
};

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(React.createElement(App));
