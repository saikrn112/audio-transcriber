# Audio Transcription App

A Flask-based web application for transcribing audio files with speaker diarization support.

## Features

- Audio file transcription using WhisperX
- Speaker diarization using pyannote.audio
- Support for multiple audio formats
- Simple web interface for file upload and management
- Real-time status updates
- Download transcriptions in TXT or JSON format

## Installation

For detailed installation instructions, including Docker setup, see [INSTALL.md](INSTALL.md).

## Usage

1. Start the application
2. Open your web browser and navigate to `http://localhost:5000`
3. Upload an audio file and wait for the transcription to complete
4. View the transcription with speaker labels
5. Download the results in your preferred format

## TODOs

1. **Audio Processing**
   - [ ] Replace WAV conversion with direct torchaudio support for m4a files
   - [ ] Fix file type validation and error messages
   - [ ] Improve speaker diarization with fallback options

2. **User Interface**
   - [ ] Fix incorrect stats display
   - [ ] Add proper progress tracking
   - [ ] Improve error messages and warnings

3. **Deployment**
   - [ ] Add Docker support with easy installation and GPU support

4. **Incorrect reporting**
   - [ ] Incorrect progress percentages
   - [ ] Missing or delayed status updates
   - [ ] Unclear error messages
   - [ ] Incomplete metadata about processing steps

5. **Track individual step progress**
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

6. Add detailed error reporting:
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