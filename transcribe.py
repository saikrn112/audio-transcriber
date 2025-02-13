import os
import json
import logging
from typing import Dict, Any, Optional

from core.transcription import BaseTranscriptionService, TranscriptionResult
from core.whisperx_provider import WhisperXProvider
import config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def process_audio(audio_path: str, output_dir: str, max_speakers: int = None) -> Optional[Dict[str, Any]]:
    """Process audio file with transcription and diarization."""
    try:
        filename = os.path.basename(audio_path)
        paths = config.get_file_paths(filename)
        
        # Initialize WhisperX provider
        provider = WhisperXProvider(
            model_name=config.WHISPER_MODEL,
            device=config.DEVICE,
            compute_type=config.COMPUTE_TYPE,
            hf_token=config.HUGGINGFACE_TOKEN,
            max_speakers=max_speakers
        )
        
        # Initialize transcription service
        service = BaseTranscriptionService(provider, paths['stats'])
        
        # Process audio
        result = service.process_audio(audio_path)
        if not result:
            return None
            
        # Save results
        os.makedirs(output_dir, exist_ok=True)
        with open(paths['transcript'], 'w') as f:
            json.dump(result.__dict__, f, indent=2)
            
        return result.__dict__
        
    except Exception as e:
        logger.error(f"Error processing audio: {e}")
        raise

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Process audio file with WhisperX')
    parser.add_argument('audio_path', help='Path to audio file')
    parser.add_argument('--output-dir', default='static/transcriptions', help='Output directory')
    parser.add_argument('--max-speakers', type=int, help='Maximum number of speakers for diarization')
    
    args = parser.parse_args()
    result = process_audio(args.audio_path, args.output_dir, args.max_speakers)
    if result:
        print(json.dumps(result, indent=2))
