from flask import Flask, request, jsonify
import os
import logging
from werkzeug.utils import secure_filename
from transcribe.summarize_model import save_summaries, split_text, summarize_in_parallel
from transcribe.transcribe import transcribe
from transcribe.get_video import process_local_video
from transcribe.utils import get_filename

app = Flask(__name__)

# Configuration
UPLOAD_FOLDER = 'files/uploads'
ALLOWED_EXTENSIONS = {'mp4', 'avi', 'mov', 'mkv'}
LOG_FILE = "api.log"
SUMMARIES_DIR = "files/summaries"
LOGSEQ_DIR = "files/logseq"

# Ensure all required directories exist
for directory in [UPLOAD_FOLDER, SUMMARIES_DIR, LOGSEQ_DIR]:
    os.makedirs(directory, exist_ok=True)

# Configure logging
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def allowed_file(filename):
    """Check if the file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def create_logseq_note(summary_path, title):
    """Creates a Logseq note from a summary file."""
    try:
        with open(summary_path, "r") as f:
            lines = f.readlines()
    except FileNotFoundError:
        logging.error(f"Summary file not found: {summary_path}")
        return None

    formatted_lines = ["    " + line for line in lines]
    summary_filename = os.path.basename(summary_path)
    logseq_filename = os.path.splitext(summary_filename)[0] + ".md"
    logseq_note_path = os.path.join(LOGSEQ_DIR, logseq_filename)

    try:
        with open(logseq_note_path, "w") as f:
            f.write(f"- summarized [[{title}]]\n")
            f.write("- [[summary]]\n")
            f.writelines(formatted_lines)
        logging.info(f"Logseq note saved at {logseq_note_path}")
        return logseq_note_path
    except IOError as e:
        logging.error(f"Error writing Logseq note: {e}")
        return None

def process_video(file_path, title):
    """Process a video file and return all generated file paths"""
    try:
        # Convert video to audio
        audio_path = process_local_video(file_path)
        logging.info(f"Audio extracted to: {audio_path}")

        # Transcribe audio
        elapsed_time, _, transcript_path = transcribe(audio_path)
        logging.info(f"Audio transcribed in {elapsed_time} seconds")

        # Generate summary
        chunks = split_text(text_path=transcript_path, title=title)
        logging.info(f"Found {len(chunks)} chunks. Summarizing...")
        
        summaries = summarize_in_parallel(chunks, title)
        summary_path = save_summaries(summaries, get_filename(transcript_path))
        logging.info(f"Summary saved at {summary_path}")

        # Create Logseq note
        logseq_path = create_logseq_note(summary_path, title)
        
        return {
            'audio_path': audio_path,
            'transcript_path': transcript_path,
            'summary_path': summary_path,
            'logseq_path': logseq_path
        }

    except Exception as e:
        logging.error(f"Error processing video: {e}")
        raise

@app.route('/api/process', methods=['POST'])
def process_video_endpoint():
    """API endpoint to process a video file"""
    try:
        # Check if a file was uploaded
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
            
        if not allowed_file(file.filename):
            return jsonify({'error': 'File type not allowed'}), 400

        # Get title from form data or use filename
        title = request.form.get('title', os.path.splitext(file.filename)[0])
        
        # Save uploaded file
        filename = secure_filename(file.filename)
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(file_path)
        
        # Process the video
        result = process_video(file_path, title)
        
        # Clean up uploaded file
        os.remove(file_path)
        
        # Return paths to generated files
        return jsonify({
            'status': 'success',
            'files': {
                'audio': os.path.basename(result['audio_path']),
                'transcript': os.path.basename(result['transcript_path']),
                'summary': os.path.basename(result['summary_path']),
                'logseq': os.path.basename(result['logseq_path'])
            }
        }), 200
        
    except Exception as e:
        logging.error(f"API error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/status', methods=['GET'])
def status():
    """Simple status endpoint to check if the API is running"""
    return jsonify({'status': 'running'}), 200

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
