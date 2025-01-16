import os
import sys
import timeit
import subprocess
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class TranscriptionConfig:
    """Configuration for the transcription service"""
    def __init__(self):
        # Set correct paths for your system
        self.whisper_path = "/Users/vincent/development/whisper.cpp/main"
        self.model_path = "/Users/vincent/development/whisper.cpp/models/ggml-large-v3.bin"
        self.validate()

    def validate(self):
        """Validate the configuration"""
        if not os.path.exists(self.whisper_path):
            raise FileNotFoundError(f"Whisper executable not found at {self.whisper_path}")
        if not os.path.exists(self.model_path):
            raise FileNotFoundError(f"Model file not found at {self.model_path}")

def get_filename(file_path):
    """Returns the filename without extension"""
    return os.path.basename(file_path).split('.')[0]

def validate_audio_file(file_path):
    """Checks if the given path points to a valid WAV audio file."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"WAV file not found: {file_path}")
    if not file_path.lower().endswith(".wav"):
        raise ValueError(f"Invalid file format. Expected WAV file, got: {file_path}")

def transcribe(audio_file, output_path="files/transcripts", config=None):
    """
    Transcribes the given audio file using whisper.cpp.
    
    Args:
        audio_file: Path to the WAV audio file
        output_path: Directory to save the transcript
        config: Optional TranscriptionConfig instance
    """
    try:
        filename_only = get_filename(audio_file)
        validate_audio_file(audio_file)
        
        logging.info(f"Starting transcription of {audio_file}")
        
        # Get or create config
        if config is None:
            config = TranscriptionConfig()

        # Print debug info
        logging.info("Transcription config:")
        logging.info(f"  Whisper path: {config.whisper_path}")
        logging.info(f"  Model path: {config.model_path}")
        logging.info(f"  Audio file: {audio_file}")

        start_time = timeit.default_timer()
        
        # Set working directory to whisper.cpp directory
        whisper_dir = os.path.dirname(config.whisper_path)
        command = [
            config.whisper_path,
            "-m", config.model_path,
            "-f", os.path.abspath(audio_file),  # Use absolute path for audio file
            "-l", "en",
            "-np",
            "-nt"
        ]
        
        logging.info(f"Running command from {whisper_dir}: {' '.join(command)}")
        
        process = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            cwd=whisper_dir
        )

        # Log all output regardless of success/failure
        if process.stdout:
            logging.info(f"Whisper stdout: {process.stdout}")
        if process.stderr:
            logging.error(f"Whisper stderr: {process.stderr}")

        # Check for errors
        if process.returncode != 0:
            error_msg = process.stderr.strip()
            logging.error(f"Whisper error (code {process.returncode}): {error_msg}")
            if "failed to initialize whisper context" in error_msg:
                raise RuntimeError(
                    f"Failed to initialize whisper model. Please verify model file is valid: {error_msg}"
                )
            raise RuntimeError(f"Transcription failed: {error_msg}")

        # Process output
        processed_str = process.stdout.replace('[BLANK_AUDIO]', '').strip()
        if not processed_str:
            logging.error("No transcript generated (empty output)")
            raise RuntimeError("Transcription produced empty output")
            
        end_time = timeit.default_timer()
        elapsed_time = int(end_time - start_time)

        # Ensure output_path is absolute
        output_path = os.path.abspath(output_path)
        os.makedirs(output_path, exist_ok=True)
        text_path = os.path.join(output_path, f"{filename_only}.txt")
        
        logging.info(f"Writing transcript of length {len(processed_str)} to {text_path}")
        
        with open(text_path, "w") as file:
            file.write(processed_str)

        logging.info(f"Transcription completed in {elapsed_time}s. Saved to {text_path}")
        return elapsed_time, processed_str, text_path

    except subprocess.CalledProcessError as e:
        error_msg = f"Whisper transcription failed: {e.stderr}"
        logging.error(error_msg)
        raise RuntimeError(error_msg)
    except Exception as e:
        logging.error(f"Transcription error: {str(e)}")
        raise

if __name__ == "__main__":
    if len(sys.argv) > 1:
        audio_path = sys.argv[1]
        try:
            elapsed_time, transcript, transcript_path = transcribe(audio_path)
            print(f"Audio transcribed in {elapsed_time} seconds")
            print(f"Transcript saved to: {transcript_path}")
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        print("Usage: python transcribe.py <audio_path>")
