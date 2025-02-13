from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Callable, List
import functools
import time
import logging
from dataclasses import dataclass
from enum import Enum
import json
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TranscriptionStatus(Enum):
    """Enum for transcription status."""
    NULL = "null"
    PROCESSING = "processing"
    COMPLETE = "complete"
    ERROR = "error"
    STOPPED = "stopped"

@dataclass
class TranscriptionStep:
    """Represents a step in the transcription process."""
    name: str
    description: str
    progress_start: float
    progress_end: float
    order: int = 0
    
    @property
    def progress_range(self) -> float:
        """Get the progress range for this step."""
        return self.progress_end - self.progress_start

class StepRegistry:
    """Registry for transcription steps."""
    def __init__(self):
        self._steps: List[TranscriptionStep] = []
        self._current_step: Optional[TranscriptionStep] = None
        
    def register_step(self, name: str, description: str, 
                     progress_start: float, progress_end: float) -> Callable:
        """Decorator to register a step in the transcription process."""
        def decorator(func: Callable) -> Callable:
            step = TranscriptionStep(
                name=name,
                description=description,
                progress_start=progress_start,
                progress_end=progress_end,
                order=len(self._steps) + 1
            )
            self._steps.append(step)
            
            @functools.wraps(func)
            def wrapper(instance, *args, **kwargs):
                self._current_step = step
                return func(instance, *args, **kwargs)
            return wrapper
        return decorator
        
    @property
    def total_steps(self) -> int:
        """Get the total number of registered steps."""
        return len(self._steps)
        
    @property
    def current_step(self) -> Optional[TranscriptionStep]:
        """Get the current step being executed."""
        return self._current_step
        
    @property
    def current_step_number(self) -> int:
        """Get the current step number (1-based)."""
        if not self._current_step:
            return 0
        return self._current_step.order
        
    def get_progress_info(self, progress: float) -> Dict[str, Any]:
        """Get detailed progress information."""
        if not self._current_step:
            return {
                'step_number': 0,
                'total_steps': self.total_steps,
                'step_name': 'Not started',
                'step_description': 'Transcription not started',
                'progress': 0
            }
            
        relative_progress = (progress - self._current_step.progress_start) / self._current_step.progress_range
        
        return {
            'step_number': self.current_step_number,
            'total_steps': self.total_steps,
            'step_name': self._current_step.name,
            'step_description': self._current_step.description,
            'progress': progress,
            'relative_progress': relative_progress
        }

# Create global step registry
step_registry = StepRegistry()

@dataclass
class TranscriptionResult:
    """Represents the result of a transcription."""
    text: str
    language: str
    segments: list
    speakers: list
    duration: float
    metadata: Dict[str, Any]

class TranscriptionError(Exception):
    """Base class for transcription errors."""
    pass

def track_time(func: Callable) -> Callable:
    """Decorator to track execution time of a function."""
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        start_time = time.time()
        try:
            result = func(self, *args, **kwargs)
            return result
        finally:
            end_time = time.time()
            execution_time = end_time - start_time
            logger.info(f"{func.__name__} took {execution_time:.2f} seconds")
            # Store timing on the instance instead of the wrapper
            setattr(self, f'timing_{func.__name__}', execution_time)
    return wrapper

def update_progress(func: Callable) -> Callable:
    """Decorator to update progress of transcription steps."""
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        if not step_registry.current_step:
            return func(self, *args, **kwargs)
            
        progress_info = step_registry.get_progress_info(step_registry.current_step.progress_start)
        self._update_status(
            status=TranscriptionStatus.PROCESSING,
            progress=progress_info['progress'],
            step=progress_info['step_description'],
            step_info=progress_info
        )
        
        try:
            result = func(self, *args, **kwargs)
            
            # Update progress after step completion
            progress_info = step_registry.get_progress_info(step_registry.current_step.progress_end)
            self._update_status(
                status=TranscriptionStatus.PROCESSING,
                progress=progress_info['progress'],
                step=f"Completed {progress_info['step_name']}",
                step_info=progress_info
            )
            
            return result
        except Exception as e:
            self._update_status(
                status=TranscriptionStatus.ERROR,
                error=str(e)
            )
            raise
    return wrapper

def check_stop_signal(func: Callable) -> Callable:
    """Decorator to check for stop signal before executing a step."""
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        if self.should_stop():
            self._update_status(
                status=TranscriptionStatus.STOPPED,
                step="Stopped by user"
            )
            return None
        return func(self, *args, **kwargs)
    return wrapper

class TranscriptionProvider(ABC):
    """Abstract base class for transcription providers."""
    
    @abstractmethod
    def load_models(self) -> None:
        """Load required models."""
        pass
        
    @abstractmethod
    def transcribe_audio(self, audio_path: str) -> Dict[str, Any]:
        """Perform audio transcription."""
        pass
        
    @abstractmethod
    def perform_diarization(self, audio_path: str, transcription: Dict[str, Any]) -> Dict[str, Any]:
        """Perform speaker diarization."""
        pass

class BaseTranscriptionService:
    """Base class for transcription services."""
    
    def __init__(self, provider: TranscriptionProvider, stats_path: str):
        self.provider = provider
        self.stats_path = stats_path
        
    def should_stop(self) -> bool:
        """Check if transcription should stop."""
        try:
            if os.path.exists(self.stats_path):
                with open(self.stats_path, 'r') as f:
                    stats = json.load(f)
                    return stats.get('status') == TranscriptionStatus.STOPPED.value
        except Exception as e:
            logger.error(f"Error checking stop signal: {e}")
        return False
        
    def _update_status(self, status: TranscriptionStatus, progress: float = None, 
                      step: str = None, error: str = None, step_info: Dict[str, Any] = None) -> None:
        """Update transcription status."""
        stats = {
            'status': status.value,
            'last_updated': time.time()
        }
        if progress is not None:
            stats['progress'] = progress
        if step is not None:
            stats['step'] = step
        if error is not None:
            stats['error'] = error
        if step_info is not None:
            stats['step_info'] = step_info
            
        os.makedirs(os.path.dirname(self.stats_path), exist_ok=True)
        with open(self.stats_path, 'w') as f:
            json.dump(stats, f, indent=2)
            
    @track_time
    @check_stop_signal
    @update_progress
    @step_registry.register_step(
        name="Load Models",
        description="Loading machine learning models",
        progress_start=0,
        progress_end=20
    )
    def load_models(self) -> None:
        """Load required models."""
        self.provider.load_models()
        
    @track_time
    @check_stop_signal
    @update_progress
    @step_registry.register_step(
        name="Transcribe Audio",
        description="Converting speech to text",
        progress_start=20,
        progress_end=60
    )
    def transcribe_audio(self, audio_path: str) -> Dict[str, Any]:
        """Transcribe audio file."""
        return self.provider.transcribe_audio(audio_path)
        
    @track_time
    @check_stop_signal
    @update_progress
    @step_registry.register_step(
        name="Speaker Diarization",
        description="Identifying different speakers",
        progress_start=60,
        progress_end=90
    )
    def perform_diarization(self, audio_path: str, transcription: Dict[str, Any]) -> Dict[str, Any]:
        """Perform speaker diarization."""
        return self.provider.perform_diarization(audio_path, transcription)
        
    @track_time
    @check_stop_signal
    @update_progress
    @step_registry.register_step(
        name="Save Results",
        description="Saving transcription results",
        progress_start=90,
        progress_end=100
    )
    def save_results(self, result: TranscriptionResult) -> None:
        """Save transcription results."""
        if not result:
            return
            
        # Get the timing information from instance attributes
        timings = {}
        for step in ['load_models', 'transcribe_audio', 'perform_diarization', 'save_results']:
            timing_key = f'timing_{step}'
            if hasattr(self, timing_key):
                timings[step] = getattr(self, timing_key)
                
        # Create stats
        stats = {
            'transcription_info': {
                'language': result.language,
                'duration': result.duration,
                'num_speakers': len(result.speakers) if result.speakers else len(set(segment.get('speaker', '') for segment in result.segments)),
                'diarization_available': bool(result.speakers)
            },
            'timings': timings,
            'total_time': sum(timings.values())
        }
        
        # Save transcription result
        transcription_data = {
            'segments': result.segments,
            'metadata': {
                'language': result.language,
                'duration': result.duration,
                'speakers': result.speakers,
                'timestamp': time.time()
            }
        }
        
        with open(self.stats_path.replace('.stats.json', '.json'), 'w') as f:
            json.dump(transcription_data, f, indent=2)
            
        # Save stats
        with open(self.stats_path, 'w') as f:
            json.dump(stats, f, indent=2)

    @track_time
    @check_stop_signal
    @update_progress
    @step_registry.register_step(
        name="Process Audio",
        description="Processing audio file",
        progress_start=0,
        progress_end=100
    )
    def process_audio(self, audio_path: str) -> Optional[TranscriptionResult]:
        """Process audio file with transcription and diarization."""
        try:
            # Load models first
            self.load_models()
            
            # Perform diarization first
            logger.info("Starting speaker diarization")
            diarization = self.perform_diarization(audio_path, {})
            has_diarization = bool(diarization and "segments" in diarization)
            
            # Then do transcription
            logger.info("Starting transcription")
            transcription = self.transcribe_audio(audio_path)
            
            # Combine results
            if has_diarization:
                logger.info("Combining diarization with transcription")
                # Use diarization segments as base
                result = diarization
                # Update with transcription info
                result["language"] = transcription.get("language", "")
                result["duration"] = transcription.get("duration", 0)
            else:
                logger.info("Using transcription without diarization")
                result = transcription
            
            # Create final result
            final_result = TranscriptionResult(
                text="\n".join(segment.get("text", "") for segment in result.get("segments", [])),
                language=result.get("language", ""),
                segments=result.get("segments", []),
                speakers=result.get("speakers", []),
                duration=result.get("duration", 0),
                metadata={
                    "filename": os.path.basename(audio_path),
                    "timestamp": time.time(),
                    "model": "whisperx",
                    "has_diarization": has_diarization,
                    "diarization_error": "" if has_diarization else "Speaker diarization failed or was skipped"
                }
            )
            
            # Save results with complete status
            self._update_status(
                status=TranscriptionStatus.COMPLETE,
                progress=100,
                step="Complete",
                step_info={
                    'step_number': step_registry.total_steps,
                    'total_steps': step_registry.total_steps,
                    'step_name': 'Complete',
                    'step_description': 'Transcription complete',
                    'progress': 100,
                    'relative_progress': 1.0,
                    'warnings': [] if has_diarization else ["Speaker diarization was not performed"]
                }
            )
            
            return final_result
            
        except Exception as e:
            logger.error(f"Error processing audio: {e}")
            self._update_status(
                status=TranscriptionStatus.ERROR,
                error=str(e)
            )
            raise
