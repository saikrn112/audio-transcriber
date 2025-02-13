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

1. Clone the repository:
```bash
git clone https://github.com/yourusername/audio-transcription-app.git
cd audio-transcription-app
```

2. Create a Python virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows use: venv\Scripts\activate
```

3. Install the required packages:
```bash
pip install -r requirements.txt
```

4. Set up your environment variables by copying the example file:
```bash
cp .env.example .env
```

5. Edit `.env` and add your HuggingFace token (required for speaker diarization):
```env
HUGGINGFACE_TOKEN=your_token_here
USE_GPU=1  # Set to 0 for CPU-only
FLASK_PORT=7000
FLASK_DEBUG=0
```

Get your HuggingFace token from: https://huggingface.co/settings/tokens

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
http://localhost:7000
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
- `FLASK_PORT`: Web server port (default: 7000)
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


## ToDos
- [ ] add agentic workflow to identify tasks based on the audio meetings

## License

This project is licensed under the MIT License - see the LICENSE file for details.
