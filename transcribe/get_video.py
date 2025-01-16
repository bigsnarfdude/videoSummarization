import datetime
import os
import sys
import subprocess
import logging
from utils import get_filename, slugify

# Configure logging 
logging.basicConfig(
    filename='video_processing.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def process_video_list(list_file_path, output_path="files/audio/"):
    """
    Process a text file containing a list of video paths.
    Each line in the file should contain one video path.
    
    Args:
        list_file_path: Path to the text file containing video paths
        output_path: Directory where processed audio files will be saved
    
    Returns:
        list: List of processed WAV file paths
    """
    if not os.path.exists(list_file_path):
        raise FileNotFoundError(f"List file not found: {list_file_path}")
        
    processed_files = []
    
    try:
        with open(list_file_path, 'r') as file:
            video_paths = [line.strip() for line in file if line.strip()]
            
        logging.info(f"Found {len(video_paths)} videos to process in {list_file_path}")
        
        for i, video_path in enumerate(video_paths, 1):
            try:
                logging.info(f"Processing video {i}/{len(video_paths)}: {video_path}")
                wav_path = process_local_video(video_path, output_path)
                processed_files.append(wav_path)
                logging.info(f"Successfully processed: {video_path} -> {wav_path}")
            except Exception as e:
                logging.error(f"Error processing video {video_path}: {e}")
                print(f"Error processing video {video_path}: {e}")
                continue
                
        return processed_files
        
    except Exception as e:
        logging.error(f"Error reading video list file: {e}")
        raise

def process_local_video(video_path, output_path="files/audio/"):
    """
    Processes a local video file and saves the converted audio to the given output
    path. Returns the path to the processed wav file.
    """
    if not os.path.exists(output_path):
        os.makedirs(output_path)
        logging.info(f"Created output directory: {output_path}")
    
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video file not found: {video_path}")

    original_path, original_filename = os.path.split(video_path)
    original_file_base, file_ext = os.path.splitext(original_filename)
    slugified_base = slugify(original_file_base)
    new_file_path = os.path.join(
        output_path, f"{slugified_base}.wav"
    )
    convert_to_wav(video_path, new_file_path)
    return new_file_path

def convert_to_wav(movie_path, wav_path):
    """
    Converts a video file to a wav file. Returns the path to the wav file.
    """
    cmd = (f'ffmpeg -y -i "{movie_path}" -ar 16000 -ac 1 -c:a pcm_s16le "{wav_path}"')
    logging.info(f"Converting to wav with command: {cmd}")
    try:
        process = subprocess.run(
            cmd,
            shell=True,
            check=True,
            capture_output=True,
            text=True
        )
        logging.info(f"Converted video to wav: {wav_path}")
        return wav_path
    except subprocess.CalledProcessError as e:
        logging.error(f"Error converting video: {e.stderr}")
        raise

def is_video_file(filepath):
    """
    Check if the given file is a video file based on its extension.
    """
    video_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.m4v'}
    return os.path.splitext(filepath)[1].lower() in video_extensions

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage:")
        print("  For single video: python get_video.py <video_path>")
        print("  For list of videos: python get_video.py <path_to_video_list.txt>")
        sys.exit(1)

    input_path = sys.argv[1]
    
    try:
        if input_path.lower().endswith('.txt'):
            # Process list of videos
            processed_files = process_video_list(input_path)
            print("\nProcessed files:")
            for wav_file in processed_files:
                print(f"- {wav_file}")
        elif is_video_file(input_path):
            # Process single video
            wav_path = process_local_video(input_path)
            print(f"\nAudio processed to: {wav_path}")
        else:
            print("Error: Input file must be either a video file or a .txt file containing video paths")
            sys.exit(1)
            
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)
