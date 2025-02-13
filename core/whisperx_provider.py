import whisperx
import torch
from typing import Dict, Any, Optional
import logging
from .transcription import TranscriptionProvider

logger = logging.getLogger(__name__)

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
        logger.info(f"CUDA available: {torch.cuda.is_available()}")
        
        if torch.cuda.is_available():
            logger.info(f"CUDA device: {torch.cuda.get_device_name()}")
            
        self.model = whisperx.load_model(
            self.model_name,
            self.device,
            compute_type=self.compute_type
        )
        
    def transcribe_audio(self, audio_path: str) -> Dict[str, Any]:
        """Perform audio transcription using WhisperX."""
        if not self.model:
            raise RuntimeError("Models not loaded. Call load_models() first.")
            
        # Transcribe with WhisperX
        result = self.model.transcribe(audio_path, batch_size=16)
        
        # Load alignment model
        self.align_model, metadata = whisperx.load_align_model(
            language_code=result["language"],
            device=self.device
        )
        
        # Align whisper output
        result = whisperx.align(
            result["segments"],
            self.align_model,
            metadata,
            audio_path,
            self.device
        )
        
        return result
        
    def perform_diarization(self, audio_path: str, transcription: Dict[str, Any]) -> Dict[str, Any]:
        """Perform speaker diarization using WhisperX."""
        if not self.hf_token or not self.max_speakers:
            logger.warning("Skipping diarization: missing token or max_speakers")
            return transcription
            
        try:
            # Initialize diarization model
            if not self.diarize_model:
                self.diarize_model = whisperx.DiarizationPipeline(
                    use_auth_token=self.hf_token,
                    device=self.device
                )
                
            # Perform diarization
            diarize_segments = self.diarize_model(
                audio_path,
                min_speakers=1,
                max_speakers=self.max_speakers
            )
            
            # Assign speaker labels
            result = whisperx.assign_word_speakers(diarize_segments, transcription)
            
            return result
            
        except Exception as e:
            logger.error(f"Diarization failed: {e}")
            return transcription
