import os
from pathlib import Path
import sys
import subprocess
import logging
from typing import List, Optional
from .utils import get_filename, slugify
from config import settings

# Configure logging
logger = logging.getLogger(__name__)

def process_video_list(list_file_path: str, output_path: Optional[str] = None) -> List[str]:
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
        
    if output_path is None:
        output_path = settings.OUTPUT_DIRS["audio"]
        
    processed_files = []
    
    try:
        with open(list_file_path, 'r') as file:
            video_paths = [line.strip() for line in file if line.strip()]
            
        logger.info(f"Found {len(video_paths)} videos to process in {list_file_path}")
        
        for i, video_path in enumerate(video_paths, 1):
            try:
                logger.info(f"Processing video {i}/{len(video_paths)}: {video_path}")
                wav_path = process_local_video(video_path, output_path)
                processed_files.append(wav_path)
                logger.info(f"Successfully processed: {video_path} -> {wav_path}")
            except Exception as e:
                logger.error(f"Error processing video {video_path}: {e}")
                print(f"Error processing video {video_path}: {e}")
                continue
                
        return processed_files
        
    except Exception as e:
        logger.error(f"Error reading video list file: {e}")
        raise

def process_local_video(video_path: str, output_path: Optional[str] = None) -> str:
    """Process video or audio file"""
    if output_path is None:
        output_path = settings.OUTPUT_DIRS["audio"]
    
    if not Path(output_path).exists():
        Path(output_path).mkdir(parents=True, exist_ok=True)
    
    if not Path(video_path).exists():
        raise FileNotFoundError(f"File not found: {video_path}")

    original_file_base = Path(video_path).stem
    slugified_base = slugify(original_file_base)
    
    # If it's already a WAV, just return the path
    if Path(video_path).suffix.lower() == '.wav':
        return str(video_path)
    
    new_file_path = Path(output_path) / f"{slugified_base}.wav"
    
    convert_to_wav(str(video_path), str(new_file_path))
    return str(new_file_path)

def convert_to_wav(movie_path: str, wav_path: str) -> str:
    """
    Converts a video file to a WAV file.
    
    Args:
        movie_path: Path to the input video file
        wav_path: Path where the WAV file should be saved
        
    Returns:
        str: Path to the created WAV file
        
    Raises:
        RuntimeError: If conversion fails
    """
    cmd = (f'ffmpeg -y -i "{movie_path}" -ar 16000 -ac 1 -c:a pcm_s16le "{wav_path}"')
    logger.info(f"Converting to wav with command: {cmd}")
    try:
        process = subprocess.run(
            cmd,
            shell=True,
            check=True,
            capture_output=True,
            text=True
        )
        logger.info(f"Converted video to wav: {wav_path}")
        return wav_path
    except subprocess.CalledProcessError as e:
        logger.error(f"Error converting video: {e.stderr}")
        raise RuntimeError(f"Failed to convert video: {e.stderr}")

def is_video_file(filepath: str) -> bool:
    """
    Check if the given file is a video file based on its extension.
    
    Args:
        filepath: Path to the file
        
    Returns:
        bool: True if file has a video extension
    """
    video_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.m4v'}
    return Path(filepath).suffix.lower() in video_extensions

def is_audio_file(filepath: str) -> bool:
    """Check if file is video or audio"""
    audio_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.m4v', '.mp3', '.wav'}
    return Path(filepath).suffix.lower() in audio_extensions


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
