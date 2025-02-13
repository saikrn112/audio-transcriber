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
        # Force config initialization to detect GPU
        config.init()
        
        filename = os.path.basename(audio_path)
        paths = config.get_file_paths(filename)
        
        # Log device configuration
        logger.info(f"Using device: {config.DEVICE} with compute type: {config.COMPUTE_TYPE}")
        
        # Validate Hugging Face token
        if not config.HUGGINGFACE_TOKEN:
            logger.error("HUGGINGFACE_TOKEN is not set in .env file")
            raise ValueError("HUGGINGFACE_TOKEN is required for speaker diarization")
            
        logger.info("Hugging Face token is configured")
        
        # Initialize WhisperX provider
        provider = WhisperXProvider(
            model_name=config.WHISPER_MODEL,
            device=config.DEVICE,
            compute_type=config.COMPUTE_TYPE,
            hf_token=config.HUGGINGFACE_TOKEN,
            max_speakers=max_speakers or config.DEFAULT_MAX_SPEAKERS
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
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    parser = argparse.ArgumentParser(description='Process audio file with WhisperX')
    parser.add_argument('audio_path', help='Path to audio file')
    parser.add_argument('--output-dir', default='static/transcriptions', help='Output directory')
    parser.add_argument('--max-speakers', type=int, help='Maximum number of speakers for diarization')
    parser.add_argument('--device', choices=['cuda', 'cpu'], help='Device to use (default: auto-detect)')
    
    args = parser.parse_args()
    
    # Override device if specified
    if args.device:
        config.DEVICE = args.device
        config.COMPUTE_TYPE = 'float16' if args.device == 'cuda' else 'int8'
        
    result = process_audio(args.audio_path, args.output_dir, args.max_speakers)
    if result:
        print(json.dumps(result, indent=2))
