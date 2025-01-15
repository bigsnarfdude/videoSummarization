import datetime
import os
import subprocess
import logging
from .utils import get_filename, slugify


def process_local_video(video_path, output_path="files/audio/"):
    """
    Processes a local video file and saves the converted audio to the given output
    path. Returns the path to the processed wav file.
    """
    logging.basicConfig(filename='video_processing.log', level=logging.INFO)

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
        return_code = subprocess.call(cmd, shell=True)
        logging.info(f"ffmpeg return code: {return_code}")
        if return_code == 0:
            logging.info(f"Converted video to wav: {wav_path}")
            # Optional: Add logic to handle deleting the original file here
    except subprocess.CalledProcessError as e:
        logging.error(f"Error converting video: {e}")
        raise


if __name__ == "__main__":
    if len(sys.argv) > 1:
        video_path = sys.argv[1]
        wav_path = process_local_video(video_path)
        print("Audio processed to: ", wav_path)
    else:
        print("Usage: python -m gpt_summarize.source_video.py <local_video_path>")
