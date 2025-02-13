# Audio Transcription App

A Flask-based web application for transcribing audio files with speaker diarization using WhisperX.

## Features

- Audio file upload and management
- Automatic transcription using WhisperX
- Speaker diarization (when HuggingFace token is provided)
- Progress tracking and status updates
- Clean and simple web interface
- Support for multiple audio formats (WAV, MP3, OGG, FLAC, M4A)

## Prerequisites

- Python 3.10 or higher
- CUDA-capable GPU (recommended) or CPU
- FFmpeg installed on your system

## Installation

### Quick Start with Docker
```bash
# Clone the repository
git clone https://github.com/saikrn112/audio-transcription-app.git
cd audio-transcription-app

# Build and run with Docker
docker compose up
```

The app will be available at `http://localhost:5000`

### Manual Installation

1. **Prerequisites**
   ```bash
   # Ubuntu/Debian
   sudo apt-get update
   sudo apt-get install -y python3.9 python3-pip ffmpeg

   # macOS
   brew install python@3.9 ffmpeg
   ```

2. **Clone and Setup**
   ```bash
   # Clone repository
   git clone https://github.com/saikrn112/audio-transcription-app.git
   cd audio-transcription-app

   # Create virtual environment
   python3 -m venv venv
   source venv/bin/activate  # On Windows: .\venv\Scripts\activate
   ```

3. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Environment Setup**
   ```bash
   # Copy example env file
   cp .env.example .env

   # Edit .env file with your Hugging Face token
   # Get token from: https://huggingface.co/settings/tokens
   nano .env
   ```

5. **Run the App**
   ```bash
   python app.py
   ```

Visit `http://localhost:5000` in your browser.

### Docker Setup

1. **Development Setup**
   ```dockerfile
   # Development Dockerfile
   FROM python:3.9-slim

   # Install system dependencies
   RUN apt-get update && apt-get install -y \
       ffmpeg \
       && rm -rf /var/lib/apt/lists/*

   # Install Python dependencies
   COPY requirements.txt .
   RUN pip install -r requirements.txt

   # Copy application
   COPY . .

   # Run the application
   CMD ["python", "app.py"]
   ```

2. **Production Setup**
   ```yaml
   # docker-compose.yml
   version: '3.8'
   services:
     app:
       build: .
       ports:
         - "5000:5000"
       volumes:
         - ./data:/app/data
       environment:
         - HUGGINGFACE_TOKEN=${HUGGINGFACE_TOKEN}
       restart: unless-stopped
   ```

3. **Build and Run**
   ```bash
   # Development
   docker build -t audio-transcriber-dev .
   docker run -p 5000:5000 audio-transcriber-dev

   # Production
   docker compose up -d
   ```

### Common Issues

1. **FFmpeg Missing**
   ```bash
   # Ubuntu/Debian
   sudo apt-get install ffmpeg

   # macOS
   brew install ffmpeg

   # Windows
   # Download from: https://www.gyan.dev/ffmpeg/builds/
   # Add to PATH
   ```

2. **GPU Support**
   ```bash
   # Install CUDA dependencies
   pip install torch==2.0.0+cu117 torchaudio==2.0.0+cu117 -f https://download.pytorch.org/whl/cu117/torch_stable.html
   ```

### TODOs for Installation

1. **Docker Integration**
   - [ ] Create optimized Dockerfile for production
   - [ ] Add Docker Compose for easy deployment
   - [ ] Include GPU support in Docker
   - [ ] Add volume mounting for data persistence

2. **Installation Script**
   - [ ] Create single-command installation script
   - [ ] Add system requirement checks
   - [ ] Automate environment setup
   - [ ] Add GPU detection and setup

3. **Documentation**
   - [ ] Add troubleshooting guide
   - [ ] Include performance optimization tips
   - [ ] Document all environment variables
   - [ ] Add deployment guides for different platforms

## Directory Structure

```
audio-transcription-app/
├── app.py              # Flask application
├── config.py           # Shared configuration
├── transcribe.py       # Audio processing logic
├── public/            # Frontend files
│   ├── index.html     # Main page
│   └── app.js         # Frontend JavaScript
├── data/              # Audio files and transcripts
├── requirements.txt    # Python dependencies
└── .env              # Environment variables
```

## Usage

1. Start the Flask server:
```bash
python app.py
```

2. Open your web browser and navigate to:
```
http://localhost:5000
```

3. Upload an audio file and wait for the transcription to complete.

## File Processing

The application follows this workflow:

1. Audio files are uploaded to the `data/` directory
2. Files are preprocessed to ensure consistent format
3. WhisperX processes the audio for transcription
4. If enabled, speaker diarization is performed
5. Results are saved as JSON files in the `data/` directory

## Configuration Options

Edit `.env` to customize:

- `HUGGINGFACE_TOKEN`: Required for speaker diarization
- `USE_GPU`: Enable/disable GPU acceleration (1/0)
- `FLASK_PORT`: Web server port (default: 5000)
- `FLASK_DEBUG`: Enable debug mode (1/0)
- `DEFAULT_MAX_SPEAKERS`: Maximum number of speakers to detect

## Supported Audio Formats

- WAV
- MP3
- OGG
- FLAC
- M4A

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## TODOs and Known Issues

### High Priority

1. **Audio Format Support**
   - [ ] Replace WAV conversion with direct torchaudio support for m4a files
   - [ ] Update file type validation to properly check audio formats
   - [ ] Fix incorrect error messages about invalid file types during upload

2. **Diarization Improvements**
   - [ ] Investigate torchaudio for direct m4a support in diarization
   - [ ] Add fallback options when diarization fails
   - [ ] Improve speaker labeling consistency

3. **Status and Statistics**
   - [ ] Fix incorrect stats display in UI
   - [ ] Add proper progress tracking for each step (transcription, diarization)
   - [ ] Improve error messages and warnings
   - [ ] Add detailed metadata about processing steps

### Implementation Details

#### Audio Processing
Currently, the app converts audio files to WAV format before processing, which causes several issues:
- Unnecessary disk usage from temporary WAV files
- Potential quality loss from format conversion
- Extra processing time
- Issues with m4a files

Proposed solution:
1. Use torchaudio for direct m4a support:
```python
import torchaudio

# Load audio directly
waveform, sample_rate = torchaudio.load("audio.m4a")
```

2. Update validation to use proper MIME types and file signatures
3. Remove WAV conversion step entirely

#### Status Reporting
Current issues with status reporting:
- Incorrect progress percentages
- Missing or delayed status updates
- Unclear error messages
- Incomplete metadata about processing steps

Needed improvements:
1. Track individual step progress:
```json
{
    "status": "processing",
    "steps": {
        "transcription": {
            "status": "complete",
            "duration": "5.2s"
        },
        "diarization": {
            "status": "processing",
            "progress": 45,
            "warnings": []
        }
    }
}
```

2. Add detailed error reporting:
```json
{
    "status": "error",
    "error": {
        "step": "diarization",
        "message": "Failed to process audio",
        "details": "Unsupported sample rate: 44100Hz",
        "suggestions": ["Convert to 16kHz sample rate"]
    }
}
```

### Future Improvements

1. **Performance**
   - [ ] Add caching for processed audio files
   - [ ] Implement batch processing for multiple files
   - [ ] Add support for distributed processing

2. **User Experience**
   - [ ] Add real-time transcription preview
   - [ ] Improve error messages and recovery options
   - [ ] Add support for custom diarization settings

3. **Quality**
   - [ ] Add automated testing for different audio formats
   - [ ] Implement validation for transcription quality
   - [ ] Add confidence scores for speaker diarization

## License

This project is licensed under the MIT License - see the LICENSE file for details.
