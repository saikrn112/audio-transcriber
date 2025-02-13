import whisperx
import torch
from typing import Dict, Any, Optional
import logging
from .transcription import TranscriptionProvider
import os
import subprocess
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

def convert_to_wav(input_path: str) -> Optional[str]:
    """Convert audio file to WAV format using ffmpeg."""
    try:
        # Create temp directory if it doesn't exist
        temp_dir = os.path.join(os.path.dirname(input_path), 'temp')
        os.makedirs(temp_dir, exist_ok=True)
        
        # Generate temp WAV file path
        wav_path = os.path.join(temp_dir, f"{Path(input_path).stem}_temp.wav")
        logger.info(f"Converting {input_path} to WAV: {wav_path}")
        
        # Convert to WAV using ffmpeg
        cmd = [
            'ffmpeg', '-y',  # Overwrite output file if it exists
            '-i', input_path,  # Input file
            '-acodec', 'pcm_s16le',  # Output codec
            '-ar', '16000',  # Sample rate
            '-ac', '1',  # Mono audio
            wav_path  # Output file
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.error(f"FFmpeg conversion failed: {result.stderr}")
            return None
            
        if not os.path.exists(wav_path):
            logger.error("Converted WAV file not found")
            return None
            
        logger.info("Audio conversion successful")
        return wav_path
        
    except Exception as e:
        logger.error(f"Error converting audio: {e}")
        return None

def cleanup_temp_files(temp_dir: str):
    """Clean up temporary WAV files."""
    try:
        if os.path.exists(temp_dir):
            for file in os.listdir(temp_dir):
                if file.endswith('_temp.wav'):
                    try:
                        os.remove(os.path.join(temp_dir, file))
                        logger.info(f"Cleaned up temp file: {file}")
                    except Exception as e:
                        logger.warning(f"Failed to remove temp file {file}: {e}")
            try:
                os.rmdir(temp_dir)
                logger.info("Removed temp directory")
            except Exception as e:
                logger.warning(f"Failed to remove temp directory: {e}")
    except Exception as e:
        logger.error(f"Error cleaning up temp files: {e}")

class WhisperXProvider(TranscriptionProvider):
    """WhisperX implementation of TranscriptionProvider."""
    
    def __init__(self, model_name: str = "base", device: str = "cuda", 
                 compute_type: str = "float16", hf_token: Optional[str] = None,
                 max_speakers: Optional[int] = None):
        self.model_name = model_name
        self.device = device
        self.compute_type = compute_type
        self.hf_token = hf_token
        self.max_speakers = max_speakers
        self.model = None
        self.align_model = None
        self.diarize_model = None
        
    def load_models(self) -> None:
        """Load WhisperX models."""
        logger.info(f"Loading WhisperX model: {self.model_name}")
        logger.info(f"PyTorch version: {torch.__version__}")
        logger.info(f"Device: {self.device}")
        logger.info(f"Compute type: {self.compute_type}")
        
        # Check CUDA availability
        if self.device == "cuda":
            if not torch.cuda.is_available():
                logger.warning("CUDA requested but not available, falling back to CPU")
                self.device = "cpu"
                self.compute_type = "int8"
            else:
                device_name = torch.cuda.get_device_name()
                device_capability = torch.cuda.get_device_capability()
                logger.info(f"Using CUDA device: {device_name} (Compute {device_capability[0]}.{device_capability[1]})")
                
        # Load WhisperX model
        self.model = whisperx.load_model(
            self.model_name,
            self.device,
            compute_type=self.compute_type,
            language=None  # Auto-detect language
        )
        
        logger.info("WhisperX model loaded successfully")
        
    def transcribe_audio(self, audio_path: str) -> Dict[str, Any]:
        """Transcribe audio using WhisperX."""
        if not self.model:
            raise RuntimeError("Models not loaded. Call load_models() first.")
            
        # Convert to WAV
        wav_path = convert_to_wav(audio_path)
        if not wav_path:
            raise RuntimeError("Failed to convert audio to WAV format")
            
        try:
            # Transcribe with WhisperX
            logger.info(f"Transcribing audio using device: {self.device}")
            result = self.model.transcribe(
                wav_path,
                batch_size=16 if self.device == "cuda" else 1
            )
            
            # Load alignment model and align
            if result["language"]:
                logger.info(f"Loading alignment model for language: {result['language']}")
                try:
                    self.align_model, metadata = whisperx.load_align_model(
                        language_code=result["language"],
                        device=self.device
                    )
                    
                    logger.info("Aligning transcription")
                    result = whisperx.align(
                        result["segments"],
                        self.align_model,
                        metadata,
                        wav_path,
                        self.device
                    )
                except Exception as e:
                    logger.warning(f"Alignment failed: {e}")
                    # Continue without alignment
                    
            return result
            
        finally:
            # Clean up temp WAV file
            cleanup_temp_files(os.path.dirname(wav_path))
        
    def perform_diarization(self, audio_path: str, transcription: Dict[str, Any]) -> Dict[str, Any]:
        """Perform speaker diarization using WhisperX."""
        if not self.hf_token or not self.max_speakers:
            logger.warning("Skipping diarization: missing token or max_speakers")
            return transcription
        
        try:
            # Initialize diarization model
            if not self.diarize_model:
                logger.info("Initializing diarization model with token")
                try:
                    # Use WhisperX's diarization pipeline
                    self.diarize_model = whisperx.DiarizationPipeline(
                        use_auth_token=self.hf_token,
                        device=self.device
                    )
                    
                    logger.info("Diarization model initialized successfully")
                except Exception as e:
                    logger.error(f"Failed to initialize diarization model: {str(e)}")
                    if "401 Client Error" in str(e):
                        logger.error("Authentication failed. Please check your Hugging Face token")
                    elif "403 Client Error" in str(e):
                        logger.error("Access denied. Please accept the model terms at: https://huggingface.co/pyannote/speaker-diarization-3.1")
                    return transcription
                
            # Perform diarization
            logger.info(f"Starting diarization with max_speakers={self.max_speakers}")
            try:
                # Convert to WAV
                wav_path = convert_to_wav(audio_path)
                if not wav_path:
                    logger.error("Failed to convert audio to WAV format")
                    return transcription
                    
                diarize_segments = self.diarize_model(
                    wav_path,
                    min_speakers=1,
                    max_speakers=self.max_speakers
                )
                
                if not diarize_segments:
                    logger.warning("Diarization returned no segments")
                    return transcription
                    
                # Assign speaker labels
                logger.info("Assigning speaker labels to segments")
                result = whisperx.assign_word_speakers(diarize_segments, transcription)
                
                # Ensure speaker labels are consistent (SPEAKER_1, SPEAKER_2, etc.)
                speaker_map = {}
                speakers = []
                for segment in result["segments"]:
                    if "speaker" in segment:
                        speaker = segment["speaker"]
                        if speaker not in speaker_map:
                            speaker_id = f"SPEAKER_{len(speaker_map) + 1}"
                            speaker_map[speaker] = speaker_id
                            speakers.append(speaker_id)
                        segment["speaker"] = speaker_map[speaker]
                
                # Add speakers list to result
                result["speakers"] = speakers
                logger.info(f"Diarization completed with {len(speakers)} speakers")
                return result
                
            except Exception as e:
                logger.error(f"Diarization failed: {e}")
                return transcription
                
        except Exception as e:
            logger.error(f"Diarization failed: {str(e)}")
            logger.error(f"Token status: {'Set' if self.hf_token else 'Not set'}")
            logger.error(f"Device: {self.device}")
            return transcription
            
        finally:
            # Clean up temp WAV file
            cleanup_temp_files(os.path.dirname(wav_path))
