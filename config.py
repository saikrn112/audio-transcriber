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
ALLOWED_AUDIO_EXTENSIONS = {'wav', 'mp3', 'ogg', 'flac', 'm4a'}

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
    if os.getenv('USE_GPU', '1').lower() not in ('1', 'true', 'yes'):
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
            logger.info("CUDA test successful")
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
        logger.info("Using GPU acceleration")
    else:
        DEVICE = "cpu"
        COMPUTE_TYPE = "int8"
        logger.info("Using CPU for processing")

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
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_AUDIO_EXTENSIONS
