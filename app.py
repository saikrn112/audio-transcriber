from flask import Flask, request, jsonify, send_from_directory, render_template
from flask_cors import CORS
from werkzeug.utils import secure_filename
import os
import json
import logging
from transcribe import process_audio
import config
import time

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize configuration
config.init()

app = Flask(__name__, static_folder='public', static_url_path='/static')
CORS(app)  # Enable CORS for all routes

# Track active transcription processes
active_processes = {}

def get_transcription_status(filename):
    """Get the transcription status and progress for a file."""
    paths = config.get_file_paths(filename)
    
    try:
        if os.path.exists(paths['stats']):
            with open(paths['stats'], 'r') as f:
                stats = json.load(f)
                return stats.get('status', None), stats
        return None, None
    except Exception as e:
        logger.error(f"Error reading stats: {e}")
        return 'error', None

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

def clear_transcription(filename):
    """Clear existing transcription files for a given file."""
    try:
        paths = config.get_file_paths(filename)
        # Remove transcription and stats files if they exist
        for path_type in ['transcript', 'stats']:
            if os.path.exists(paths[path_type]):
                os.remove(paths[path_type])
                logger.info(f"Removed {path_type} file: {paths[path_type]}")
    except Exception as e:
        logger.error(f"Error clearing transcription files: {e}")
        raise

def generate_unique_filename(filename):
    """Generate a unique filename by adding a number if file exists."""
    name, ext = os.path.splitext(filename)
    counter = 1
    new_filename = filename
    
    while os.path.exists(os.path.join(config.UPLOADS_DIR, new_filename)):
        new_filename = f"{name}_{counter}{ext}"
        counter += 1
    
    return new_filename, counter > 1

def cleanup_incomplete_files():
    """Clean up any files that were left in an incomplete state from a previous crash."""
    incomplete_files = []
    try:
        # Check all files in uploads directory
        for filename in os.listdir(config.UPLOADS_DIR):
            if not config.is_allowed_file(filename):
                continue
                
            paths = config.get_file_paths(filename)
            try:
                # Check if stats file exists and read status
                if os.path.exists(paths['stats']):
                    with open(paths['stats'], 'r') as f:
                        stats = json.load(f)
                        status = stats.get('status')
                        
                        # If file was processing or in error state
                        if status in ['processing', 'error']:
                            # Remove transcription and stats files
                            for path_type in ['transcript', 'stats']:
                                if os.path.exists(paths[path_type]):
                                    os.remove(paths[path_type])
                                    logger.info(f"Cleaned up {path_type} file for {filename}")
                            incomplete_files.append(filename)
                            
            except (json.JSONDecodeError, IOError) as e:
                # If stats file is corrupted, remove it
                logger.error(f"Error reading stats for {filename}: {e}")
                if os.path.exists(paths['stats']):
                    os.remove(paths['stats'])
                if os.path.exists(paths['transcript']):
                    os.remove(paths['transcript'])
                incomplete_files.append(filename)
                
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")
    
    return incomplete_files

# Initialize configuration and perform cleanup
config.init()
incomplete_files = cleanup_incomplete_files()

# Store cleanup results in app config for frontend to access
app.config['CLEANUP_RESULTS'] = {
    'incomplete_files': incomplete_files,
    'cleanup_time': time.time()
}

@app.route('/')
def index():
    """Serve the main application page."""
    return send_from_directory('public', 'index.html')

@app.route('/app.js')
def serve_js():
    """Serve the application JavaScript file."""
    return send_from_directory('public', 'app.js')

@app.route('/favicon.ico')
def favicon():
    """Serve the favicon."""
    return send_from_directory('public', 'favicon.ico', mimetype='image/x-icon')

@app.route('/api/files', methods=['GET'])
def list_files():
    """List all uploaded files with their transcription status."""
    try:
        files = []
        for filename in os.listdir(config.UPLOADS_DIR):
            if not config.is_allowed_file(filename):
                continue
                
            file_path = os.path.join(config.UPLOADS_DIR, filename)
            paths = config.get_file_paths(filename)
            
            # Get file size in MB
            size = os.path.getsize(file_path) / (1024 * 1024)
            
            # Get transcription status
            status = "null"
            stats = {}
            if os.path.exists(paths['stats']):
                try:
                    with open(paths['stats'], 'r') as f:
                        stats = json.load(f)
                        status = stats.get('status', 'null')
                except json.JSONDecodeError:
                    logger.error(f"Error reading stats for {filename}")
            
            files.append({
                'name': filename,
                'size': size,
                'transcription_status': status,
                'stats': stats
            })
            
        return jsonify({
            'files': files,
            'total': len(files)
        })
        
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
        new_filename, was_renamed = generate_unique_filename(filename)
        
        file_path = os.path.join(config.UPLOADS_DIR, new_filename)
        file.save(file_path)
        logger.info(f"File saved: {file_path}")

        # Return file info with rename warning if applicable
        file_info = get_file_info(new_filename)
        if was_renamed:
            file_info['warning'] = f'File renamed from {filename} to {new_filename}'
            
        return jsonify(file_info)

    except Exception as e:
        logger.error(f"Error uploading file: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/transcribe/<path:filename>', methods=['GET'])
def transcribe_file(filename):
    """Start transcription for a file."""
    try:
        if not config.is_allowed_file(filename):
            return jsonify({'error': 'Invalid file type'}), 400

        # Ensure the filename is properly decoded
        filename = secure_filename(filename)
        file_path = os.path.join(config.UPLOADS_DIR, filename)
        
        if not os.path.exists(file_path):
            return jsonify({'error': 'File not found'}), 404

        # Initialize stats file with processing status
        paths = config.get_file_paths(filename)
        os.makedirs(os.path.dirname(paths['stats']), exist_ok=True)
        with open(paths['stats'], 'w') as f:
            json.dump({
                'status': 'processing',
                'progress': 0,
                'step': 'Initializing',
                'start_time': time.time()
            }, f, indent=2)

        # Start transcription in a background thread
        import threading
        thread = threading.Thread(target=process_audio, args=(
            file_path,
            config.DATA_DIR,
            config.DEFAULT_MAX_SPEAKERS
        ))
        thread.daemon = True
        thread.start()
        
        # Track the process
        active_processes[filename] = thread

        return jsonify({
            'message': 'Transcription started',
            'status': 'processing',
            'progress': 0
        })

    except Exception as e:
        logger.error(f"Error starting transcription: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/retranscribe/<path:filename>', methods=['POST'])
def retranscribe_file(filename):
    """Clear existing transcription and start a new one."""
    try:
        if not config.is_allowed_file(filename):
            return jsonify({'error': 'Invalid file type'}), 400

        # Ensure the filename is properly decoded
        filename = secure_filename(filename)
        file_path = os.path.join(config.UPLOADS_DIR, filename)
        
        if not os.path.exists(file_path):
            return jsonify({'error': 'File not found'}), 404

        # Clear existing transcription files
        clear_transcription(filename)

        # Initialize new stats file with processing status
        paths = config.get_file_paths(filename)
        os.makedirs(os.path.dirname(paths['stats']), exist_ok=True)
        with open(paths['stats'], 'w') as f:
            json.dump({
                'status': 'processing',
                'progress': 0,
                'step': 'Initializing',
                'start_time': time.time()
            }, f, indent=2)

        # Start transcription in a background thread
        import threading
        thread = threading.Thread(target=process_audio, args=(
            file_path,
            config.DATA_DIR,
            config.DEFAULT_MAX_SPEAKERS
        ))
        thread.daemon = True
        thread.start()
        
        # Track the process
        active_processes[filename] = thread

        return jsonify({
            'message': 'Re-transcription started',
            'status': 'processing',
            'progress': 0
        })

    except Exception as e:
        logger.error(f"Error starting re-transcription: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/transcription/<path:filename>', methods=['GET'])
def get_transcription(filename):
    """Get transcription results for a file."""
    try:
        # Ensure the filename is properly decoded
        filename = secure_filename(filename)
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

@app.route('/api/stop/<path:filename>', methods=['POST'])
def stop_transcription(filename):
    """Stop an active transcription process."""
    try:
        filename = secure_filename(filename)
        
        # Check if process exists and is running
        if filename not in active_processes:
            return jsonify({'error': 'No active transcription found'}), 404
            
        process = active_processes[filename]
        if not process.is_alive():
            del active_processes[filename]
            return jsonify({'error': 'Process already completed'}), 400
            
        # Set stop flag in stats file
        paths = config.get_file_paths(filename)
        if os.path.exists(paths['stats']):
            with open(paths['stats'], 'r+') as f:
                stats = json.load(f)
                stats['status'] = 'stopped'
                stats['step'] = 'Stopped by user'
                f.seek(0)
                json.dump(stats, f, indent=2)
                f.truncate()
        
        # Remove from active processes
        del active_processes[filename]
        return jsonify({'message': 'Transcription stopped'})
        
    except Exception as e:
        logger.error(f"Error stopping transcription: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/delete/<path:filename>', methods=['DELETE'])
def delete_file(filename):
    """Delete a specific file and its associated transcription/stats."""
    try:
        # Ensure the filename is properly decoded
        filename = secure_filename(filename)
        paths = config.get_file_paths(filename)
        
        # Delete all associated files
        for path in paths.values():
            if os.path.exists(path):
                os.remove(path)
                logger.info(f"Deleted file: {path}")
        
        return jsonify({'message': 'File deleted successfully'})
    except Exception as e:
        logger.error(f"Error deleting file: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/delete-all', methods=['DELETE'])
def delete_all_files():
    """Delete all files and their associated transcriptions/stats."""
    try:
        deleted_count = 0
        
        # Get all files in uploads directory
        for filename in os.listdir(config.UPLOADS_DIR):
            if config.is_allowed_file(filename):
                paths = config.get_file_paths(filename)
                
                # Delete all associated files
                for path in paths.values():
                    if os.path.exists(path):
                        os.remove(path)
                        logger.info(f"Deleted file: {path}")
                        deleted_count += 1
        
        return jsonify({
            'message': f'Successfully deleted {deleted_count} files',
            'deleted_count': deleted_count
        })
    except Exception as e:
        logger.error(f"Error deleting all files: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/cleanup-status', methods=['GET'])
def get_cleanup_status():
    """Get the status of files cleaned up during startup."""
    cleanup_results = app.config.get('CLEANUP_RESULTS', {})
    # Only return results if they're less than 1 hour old
    if cleanup_results and (time.time() - cleanup_results.get('cleanup_time', 0)) < 3600:
        return jsonify({
            'incomplete_files': cleanup_results.get('incomplete_files', [])
        })
    return jsonify({'incomplete_files': []})

if __name__ == '__main__':
    app.run(debug=config.FLASK_DEBUG, port=config.FLASK_PORT)
