import os
from pathlib import Path
from dotenv import load_dotenv
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

# Base directory
BASE_DIR = Path(__file__).parent.absolute()

# Directory configuration
DATA_DIR = os.path.join(BASE_DIR, 'data')
UPLOADS_DIR = os.path.join(DATA_DIR, 'uploads')
TRANSCRIPTS_DIR = os.path.join(DATA_DIR, 'transcripts')
STATS_DIR = os.path.join(DATA_DIR, 'stats')

# API tokens
HUGGINGFACE_TOKEN = os.getenv('HUGGINGFACE_TOKEN')

# File configuration
ALLOWED_AUDIO_EXTENSIONS = {'wav', 'mp3', 'ogg', 'flac', 'm4a', 'aac', 'mp4', 'aiff', 'wma'}

# Flask configuration
FLASK_PORT = int(os.getenv('FLASK_PORT', '7000'))
FLASK_DEBUG = os.getenv('FLASK_DEBUG', '0').lower() in ('1', 'true', 'yes')

# Default to CPU for initial setup
DEVICE = "cpu"
COMPUTE_TYPE = "int8"
DEFAULT_MAX_SPEAKERS = int(os.getenv('DEFAULT_MAX_SPEAKERS', '2'))
WHISPER_MODEL = "base"

def check_cuda_availability():
    """Check if CUDA is available and properly configured"""
    if os.getenv('USE_GPU', '0').lower() not in ('1', 'true', 'yes'):
        logger.info("GPU usage disabled by configuration")
        return False

    try:
        import torch
        if not torch.cuda.is_available():
            logger.warning("CUDA not available")
            return False

        # Test CUDA functionality
        try:
            test_tensor = torch.zeros(1).cuda()
            del test_tensor
            # Get CUDA device info
            device_name = torch.cuda.get_device_name()
            device_capability = torch.cuda.get_device_capability()
            logger.info(f"CUDA test successful - Device: {device_name}, Compute Capability: {device_capability}")
            return True
        except Exception as e:
            logger.warning(f"CUDA test failed: {str(e)}")
            return False

    except ImportError:
        logger.warning("PyTorch not installed")
        return False
    except Exception as e:
        logger.warning(f"Unexpected error checking CUDA: {str(e)}")
        return False

def init():
    """Initialize application configuration"""
    global DEVICE, COMPUTE_TYPE

    # Create necessary directories
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(UPLOADS_DIR, exist_ok=True)
    os.makedirs(TRANSCRIPTS_DIR, exist_ok=True)
    os.makedirs(STATS_DIR, exist_ok=True)

    # Check CUDA availability
    if check_cuda_availability():
        DEVICE = "cuda"
        COMPUTE_TYPE = "float16"
        logger.info(f"GPU acceleration enabled - Device: {DEVICE}, Compute Type: {COMPUTE_TYPE}")
    else:
        DEVICE = "cpu"
        COMPUTE_TYPE = "int8"
        logger.info(f"Using CPU for processing - Device: {DEVICE}, Compute Type: {COMPUTE_TYPE}")

    if not HUGGINGFACE_TOKEN:
        logger.warning("HUGGINGFACE_TOKEN not set. Speaker diarization will be disabled.")

def get_file_paths(filename):
    """Get standard file paths for a given filename"""
    base_name = os.path.splitext(filename)[0]
    return {
        'upload': os.path.join(UPLOADS_DIR, filename),
        'transcript': os.path.join(TRANSCRIPTS_DIR, f"{base_name}.json"),
        'stats': os.path.join(STATS_DIR, f"{base_name}.stats.json")
    }

def is_allowed_file(filename):
    """Check if a file has an allowed extension"""
    if not filename:
        return False
    try:
        ext = filename.rsplit('.', 1)[1].lower()
        logger.info(f"Checking file extension: {ext}")
        return ext in ALLOWED_AUDIO_EXTENSIONS
    except IndexError:
        return False
