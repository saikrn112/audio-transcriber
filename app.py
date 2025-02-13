from flask import Flask, request, jsonify, send_from_directory, render_template
from flask_cors import CORS
from werkzeug.utils import secure_filename
import os
import json
import logging
from transcribe import process_audio
import config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize configuration
config.init()

app = Flask(__name__, 
    static_folder='public',
    static_url_path='',
    template_folder='public'
)
CORS(app)  # Enable CORS for all routes

def get_transcription_status(filename):
    """Get the transcription status and progress for a file."""
    paths = config.get_file_paths(filename)
    
    if os.path.exists(paths['transcript']) and os.path.exists(paths['stats']):
        try:
            with open(paths['stats'], 'r') as f:
                stats = json.load(f)
            return 'complete', stats
        except Exception as e:
            logger.error(f"Error reading stats: {e}")
            return 'error', None
    return None, None

def get_file_info(filename):
    """Get information about an uploaded file including transcription status."""
    paths = config.get_file_paths(filename)
    status, stats = get_transcription_status(filename)
    
    try:
        size_mb = os.path.getsize(paths['upload']) / (1024 * 1024)
        
        info = {
            'filename': filename,
            'size': size_mb,
            'transcription_status': status
        }
        
        if stats:
            info['stats'] = stats
            
        return info
    except Exception as e:
        logger.error(f"Error getting file info: {e}")
        return None

def is_processed_file(filename):
    """Check if a file is a processed temporary file."""
    return '_processed.' in filename

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/files')
def list_files():
    logger.info("Listing files from %s", config.UPLOADS_DIR)
    files = []
    try:
        for filename in os.listdir(config.UPLOADS_DIR):
            if os.path.isfile(os.path.join(config.UPLOADS_DIR, filename)) and not is_processed_file(filename):
                file_info = get_file_info(filename)
                if file_info:
                    files.append(file_info)
    except Exception as e:
        logger.error("Error listing files: %s", str(e))
        return jsonify({'error': str(e)}), 500
    return jsonify({'files': files})

@app.route('/api/upload', methods=['POST'])
def upload_file():
    logger.info("Upload request received")
    if 'file' not in request.files:
        logger.error("No file part in request")
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    if file.filename == '':
        logger.error("No selected file")
        return jsonify({'error': 'No selected file'}), 400

    if file and config.is_allowed_file(file.filename):
        filename = secure_filename(file.filename)
        paths = config.get_file_paths(filename)
        logger.info("Saving file to: %s", paths['upload'])
        try:
            file.save(paths['upload'])
            logger.info("File uploaded successfully: %s", filename)
            return jsonify({'message': 'File uploaded successfully', 'filename': filename})
        except Exception as e:
            logger.error("Error saving file: %s", str(e))
            return jsonify({'error': f'Error saving file: {str(e)}'}), 500
    
    logger.error("File type not allowed: %s", file.filename)
    return jsonify({'error': 'File type not allowed'}), 400

@app.route('/api/transcribe/<filename>')
def transcribe_file(filename):
    paths = config.get_file_paths(filename)
    if not os.path.exists(paths['upload']):
        return jsonify({'error': 'File not found'}), 404

    try:
        # Process the audio file
        logger.info(f"Starting transcription for {filename}")
        
        # Update status to processing
        os.makedirs(os.path.dirname(paths['stats']), exist_ok=True)
        with open(paths['stats'], 'w') as f:
            json.dump({'status': 'processing', 'progress': 0}, f)
            
        # Process the audio file
        transcript = process_audio(
            paths['upload'],
            output_dir=config.DATA_DIR,
            max_speakers=config.DEFAULT_MAX_SPEAKERS
        )
        
        logger.info(f"Transcription completed for {filename}")
        return jsonify({
            'message': 'Transcription completed',
            'transcript': transcript
        })
    except Exception as e:
        logger.error(f"Transcription failed for {filename}: {str(e)}")
        # Update status to error
        os.makedirs(os.path.dirname(paths['stats']), exist_ok=True)
        with open(paths['stats'], 'w') as f:
            json.dump({'status': 'error', 'error': str(e)}, f)
        return jsonify({'error': str(e)}), 500

@app.route('/api/transcription/<filename>')
def get_transcription(filename):
    paths = config.get_file_paths(filename)
    
    if not os.path.exists(paths['transcript']):
        return jsonify({'error': 'Transcription not found'}), 404
        
    try:
        with open(paths['transcript'], 'r') as f:
            transcription = json.load(f)
            
        with open(paths['stats'], 'r') as f:
            stats = json.load(f)
            
        return jsonify({
            'transcription': transcription,
            'stats': stats
        })
    except Exception as e:
        logger.error(f"Error reading transcription for {filename}: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=config.FLASK_DEBUG, port=config.FLASK_PORT)
