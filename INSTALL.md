# Installation Guide

## Quick Start with Docker
```bash
# Clone the repository
git clone https://github.com/yourusername/audio-transcription-app.git
cd audio-transcription-app

# Build and run with Docker
docker compose up
```

The app will be available at `http://localhost:5000`

## Manual Installation

### Prerequisites
```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install -y python3.9 python3-pip ffmpeg

# macOS
brew install python@3.9 ffmpeg
```

### Setup Steps
1. **Clone and Setup**
   ```bash
   # Clone repository
   git clone https://github.com/yourusername/audio-transcription-app.git
   cd audio-transcription-app

   # Create virtual environment
   python3 -m venv venv
   source venv/bin/activate  # On Windows: .\venv\Scripts\activate
   ```

2. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Environment Setup**
   ```bash
   # Copy example env file
   cp .env.example .env

   # Edit .env file with your Hugging Face token
   # Get token from: https://huggingface.co/settings/tokens
   nano .env
   ```

4. **Run the App**
   ```bash
   python app.py
   ```

Visit `http://localhost:5000` in your browser.

## Docker Details

### Development Setup
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

### Production Setup
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

### Build and Run
```bash
# Development
docker build -t audio-transcriber-dev .
docker run -p 5000:5000 audio-transcriber-dev

# Production
docker compose up -d
```

## Common Issues

### FFmpeg Missing
```bash
# Ubuntu/Debian
sudo apt-get install ffmpeg

# macOS
brew install ffmpeg

# Windows
# Download from: https://www.gyan.dev/ffmpeg/builds/
# Add to PATH
```

### GPU Support
```bash
# Install CUDA dependencies
pip install torch==2.0.0+cu117 torchaudio==2.0.0+cu117 -f https://download.pytorch.org/whl/cu117/torch_stable.html
```

## Environment Variables

- `HUGGINGFACE_TOKEN`: Required for speaker diarization
- `USE_GPU`: Enable/disable GPU acceleration (1/0)
- `FLASK_PORT`: Web server port (default: 5000)
- `FLASK_DEBUG`: Enable debug mode (1/0)
- `DEFAULT_MAX_SPEAKERS`: Maximum number of speakers to detect
