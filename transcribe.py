import os
import json
import logging
import time
from typing import Optional, Dict, Any
import torch
import whisperx
from datetime import datetime
from pathlib import Path
import config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize configuration
config.init()

def update_progress(filename: str, status: str, progress: float = None, **kwargs):
    """Update the progress/status of transcription."""
    paths = config.get_file_paths(filename)
    stats = {
        'status': status,
        'last_updated': datetime.now().isoformat(),
        **kwargs
    }
    if progress is not None:
        stats['progress'] = progress
        
    os.makedirs(os.path.dirname(paths['stats']), exist_ok=True)
    with open(paths['stats'], 'w') as f:
        json.dump(stats, f, indent=2)

def process_audio(audio_path: str, output_dir: str, max_speakers: int = None) -> Dict[str, Any]:
    """Process audio file with WhisperX for transcription and speaker diarization."""
    try:
        filename = os.path.basename(audio_path)
        logging.info(f"Starting audio processing for {audio_path}")
        logging.info(f"PyTorch version: {torch.__version__}")
        logging.info(f"CUDA available: {torch.cuda.is_available()}")
        if torch.cuda.is_available():
            logging.info(f"CUDA device: {torch.cuda.get_device_name()}")
            
        stats = {"start_time": time.time()}
        update_progress(filename, "processing", progress=0)
        
        # Step 1: Load models
        logging.info("Loading WhisperX model...")
        
        # Load WhisperX model
        model = whisperx.load_model(config.WHISPER_MODEL, config.DEVICE, compute_type=config.COMPUTE_TYPE)
        stats["model_load_time"] = time.time()
        update_progress(filename, "processing", progress=20, step="Model loaded")
        
        # Step 2: Transcribe audio
        step_start = time.time()
        logger.info("Transcribing audio...")
        result = model.transcribe(audio_path)
        stats['steps'] = {}
        stats['steps']['transcription'] = time.time() - step_start
        update_progress(filename, "processing", progress=50, step="Audio transcribed")
        
        # Get detected language
        detected_language = result.get('language', 'en')  # Default to English if not detected
        
        # Step 3: Align whisper output
        logger.info("Aligning timestamps...")
        model_a, metadata = whisperx.load_align_model(language_code=detected_language, device=config.DEVICE)
        result = whisperx.align(result["segments"], model_a, metadata, audio_path, config.DEVICE)
        update_progress(filename, "processing", progress=70, step="Timestamps aligned")
        
        # Step 4: Attempt speaker diarization if HuggingFace token is available
        step_start = time.time()
        diarization_available = False
        
        if config.HUGGINGFACE_TOKEN:
            try:
                logger.info("Performing diarization...")
                diarize_model = whisperx.DiarizationPipeline(use_auth_token=config.HUGGINGFACE_TOKEN, device=config.DEVICE)
                diarize_segments = diarize_model(audio_path, min_speakers=1, max_speakers=max_speakers or config.DEFAULT_MAX_SPEAKERS)
                result = whisperx.assign_word_speakers(diarize_segments, result)
                diarization_available = True
                stats['steps']['diarization'] = time.time() - step_start
                update_progress(filename, "processing", progress=90, step="Speaker diarization complete")
            except Exception as e:
                logger.warning(f"Speaker diarization failed: {str(e)}")
                logger.warning("Continuing without speaker diarization...")
        else:
            logger.warning("No HuggingFace token found. Skipping speaker diarization.")
            logger.warning("Set HUGGINGFACE_TOKEN environment variable to enable speaker diarization.")
        
        # Step 5: Format results
        step_start = time.time()
        logger.info("Formatting results...")
        segments = []
        
        for segment in result["segments"]:
            formatted_segment = {
                "speaker": f"SPEAKER_{segment.get('speaker', 'UNKNOWN')}" if diarization_available else "SPEAKER_1",
                "start": segment["start"],
                "end": segment["end"],
                "text": segment["text"].strip()
            }
            segments.append(formatted_segment)
        
        stats['steps']['combining'] = time.time() - step_start
        stats['total_time'] = time.time() - stats['start_time']
        
        # Add transcription metadata
        stats['transcription_info'] = {
            'language': detected_language,
            'num_speakers': len(set(s["speaker"] for s in segments)) if diarization_available else 1,
            'duration': result["segments"][-1]["end"] if segments else 0,
            'diarization_available': diarization_available
        }
        
        # Save results
        paths = config.get_file_paths(filename)
        
        # Save transcription
        os.makedirs(os.path.dirname(paths['transcript']), exist_ok=True)
        with open(paths['transcript'], 'w') as f:
            json.dump(segments, f, indent=2)
        
        # Save stats
        os.makedirs(os.path.dirname(paths['stats']), exist_ok=True)
        with open(paths['stats'], 'w') as f:
            json.dump(stats, f, indent=2)
        
        update_progress(filename, "complete", progress=100)
        return {"segments": segments, "stats": stats}
        
    except Exception as e:
        logging.error(f"Error processing audio: {str(e)}", exc_info=True)
        if output_dir:
            update_progress(os.path.basename(audio_path), "error", error=str(e))
        raise

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python transcribe.py <audio_file> [output_dir] [max_speakers]")
        sys.exit(1)
        
    audio_file = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else config.DATA_DIR
    max_speakers = int(sys.argv[3]) if len(sys.argv) > 3 else config.DEFAULT_MAX_SPEAKERS
    
    result = process_audio(audio_file, output_dir, max_speakers)
    print(json.dumps(result, indent=2))
