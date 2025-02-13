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

app = Flask(__name__, static_folder='public', static_url_path='/static')
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

@app.route('/')
def index():
    """Serve the main application page."""
    return send_from_directory('public', 'index.html')

@app.route('/app.js')
def serve_js():
    """Serve the application JavaScript file."""
    return send_from_directory('public', 'app.js')

@app.route('/api/files', methods=['GET'])
def list_files():
    """List all uploaded files and their transcription status."""
    try:
        files = []
        for filename in os.listdir(config.UPLOADS_DIR):
            if config.is_allowed_file(filename):
                file_info = get_file_info(filename)
                if file_info:
                    files.append(file_info)
        return jsonify({'files': files})
    except Exception as e:
        logger.error(f"Error listing files: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/upload', methods=['POST'])
def upload_file():
    """Handle file upload."""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400

        if not config.is_allowed_file(file.filename):
            return jsonify({'error': 'File type not allowed'}), 400

        filename = secure_filename(file.filename)
        file_path = os.path.join(config.UPLOADS_DIR, filename)
        
        # Save the uploaded file
        file.save(file_path)
        logger.info(f"File saved: {file_path}")

        # Return file info
        file_info = get_file_info(filename)
        return jsonify(file_info)

    except Exception as e:
        logger.error(f"Error uploading file: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/transcribe/<filename>', methods=['GET'])
def transcribe_file(filename):
    """Start transcription for a file."""
    try:
        if not config.is_allowed_file(filename):
            return jsonify({'error': 'Invalid file type'}), 400

        file_path = os.path.join(config.UPLOADS_DIR, filename)
        if not os.path.exists(file_path):
            return jsonify({'error': 'File not found'}), 404

        # Get output paths
        paths = config.get_file_paths(filename)

        # Start transcription in a background thread
        import threading
        thread = threading.Thread(target=process_audio, args=(
            file_path,
            paths['transcript'],
            paths['stats'],
            config.DEFAULT_MAX_SPEAKERS
        ))
        thread.start()

        return jsonify({'message': 'Transcription started'})

    except Exception as e:
        logger.error(f"Error starting transcription: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/transcription/<filename>', methods=['GET'])
def get_transcription(filename):
    """Get transcription results for a file."""
    try:
        paths = config.get_file_paths(filename)
        
        if not os.path.exists(paths['transcript']):
            return jsonify({'error': 'Transcription not found'}), 404

        with open(paths['transcript'], 'r') as f:
            transcription = json.load(f)
        
        with open(paths['stats'], 'r') as f:
            stats = json.load(f)

        return jsonify({
            'transcription': transcription,
            'stats': stats
        })

    except Exception as e:
        logger.error(f"Error getting transcription: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=config.FLASK_DEBUG, port=config.FLASK_PORT)
