import yt_dlp
import cv2
import numpy as np
import os
import argparse
from datetime import datetime
import re
from PIL import Image
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from tqdm import tqdm
import time
import tempfile
import logging
from dataclasses import dataclass
from typing import Optional, Tuple, List, Dict, Any, Union
from pathlib import Path
import contextlib

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class VideoConfig:
    quality_threshold: float = 12.0
    blur_threshold: float = 10.0
    watermark_threshold: float = 0.8
    interval_seconds: float = 5.0
    max_resolution: Optional[int] = None
    detect_watermarks: bool = False
    use_parallel: bool = True
    use_png: bool = False
    use_gpu: bool = False
    fast_scene: bool = False
    resume: bool = False
    verbose: bool = False
    gradfun: bool = False
    deblock: bool = False
    deband: bool = False
    method: str = 'interval'

class FFmpegNotFoundError(Exception):
    pass

@contextlib.contextmanager
def temporary_files(*suffixes: str):
    temp_files: List[tempfile.NamedTemporaryFile] = []
    try:
        for suffix in suffixes:
            temp_file = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
            temp_files.append(temp_file)
        yield temp_files
    finally:
        for temp_file in temp_files:
            try:
                os.unlink(temp_file.name)
            except OSError as e:
                logger.warning(f"Failed to delete temporary file {temp_file.name}: {e}")

def check_ffmpeg() -> bool:
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
        return True
    except (subprocess.SubprocessError, FileNotFoundError):
        return False

def detect_watermark(frame: np.ndarray, threshold: float) -> bool:
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 100, 200)
    kernel = np.ones((5,5), np.uint8)
    dilated = cv2.dilate(edges, kernel, iterations=2)
    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        aspect_ratio = float(w) / h
        fill_ratio = cv2.contourArea(contour) / (w * h)
        
        if 0.5 < aspect_ratio < 2 and fill_ratio > threshold:
            if (x < frame.shape[1] * 0.2 and y < frame.shape[0] * 0.2) or \
               (x > frame.shape[1] * 0.8 and y < frame.shape[0] * 0.2) or \
               (x < frame.shape[1] * 0.2 and y > frame.shape[0] * 0.8) or \
               (x > frame.shape[1] * 0.8 and y > frame.shape[0] * 0.8):
                return True
    
    return False

class VideoProcessor:
    def __init__(self, config: VideoConfig):
        self.config = config
        self.gpu_available = self._check_gpu_availability() if config.use_gpu else False

    @staticmethod
    def _check_gpu_availability() -> bool:
        try:
            import pycuda.driver as cuda
            import pycuda.autoinit
            return True
        except ImportError:
            logger.warning("PyCUDA not installed. GPU acceleration disabled.")
            return False

    def calculate_quality_score(self, frame: np.ndarray) -> float:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        sobelx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
        sobely = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
        laplacian = cv2.Laplacian(gray, cv2.CV_64F)
        
        sharpness = np.var(laplacian)
        edge_strength = np.mean(np.sqrt(sobelx**2 + sobely**2))
        contrast = np.std(gray) / (np.mean(gray) + 1e-6)
        brightness = np.mean(gray) / 255
        
        sharpness_norm = np.clip(sharpness / 1000, 0, 1)
        edge_strength_norm = np.clip(edge_strength / 100, 0, 1)
        
        hist = cv2.calcHist([gray], [0], None, [256], [0, 256])
        hist_norm = hist / (np.sum(hist) + 1e-6)
        entropy = -np.sum(hist_norm * np.log2(hist_norm + 1e-7))
        entropy_norm = np.clip(entropy / 8, 0, 1)
        
        weights = {
            'sharpness': 0.3,
            'edge_strength': 0.2,
            'contrast': 0.2,
            'brightness': 0.1,
            'entropy': 0.2
        }
        
        score = (
            sharpness_norm * weights['sharpness'] +
            edge_strength_norm * weights['edge_strength'] +
            contrast * weights['contrast'] +
            brightness * weights['brightness'] +
            entropy_norm * weights['entropy']
        ) * 100
        
        return np.clip(score, 0, 100)

    def apply_filters(self, frame: np.ndarray) -> np.ndarray:
        if not any([self.config.gradfun, self.config.deblock, self.config.deband]):
            return frame

        if self.config.gradfun:
            frame = self._apply_ffmpeg_filter(frame, 'gradfun=1.2:8')
        
        if self.config.deblock:
            frame = cv2.fastNlMeansDenoisingColored(frame, None, 10, 10, 7, 21)
            
        if self.config.deband:
            frame = self._apply_ffmpeg_filter(frame, 'deband')
            
        return frame

    def _apply_ffmpeg_filter(self, frame: np.ndarray, filter_string: str) -> np.ndarray:
        with temporary_files('.png', '.png') as (temp_in, temp_out):
            cv2.imwrite(temp_in.name, frame)
            try:
                subprocess.run([
                    'ffmpeg', '-i', temp_in.name,
                    '-vf', filter_string,
                    '-y', temp_out.name
                ], check=True, capture_output=True, text=True)
                return cv2.imread(temp_out.name)
            except subprocess.CalledProcessError as e:
                logger.error(f"FFmpeg filter '{filter_string}' failed: {e.stderr}")
                return frame

    def process_frame(self, frame_data: Tuple[np.ndarray, str, int]) -> Tuple[str, bool]:
        frame, output_folder, count = frame_data
        
        if self.gpu_available:
            frame = self._process_frame_gpu(frame)
        
        quality_score = self.calculate_quality_score(frame)
        blur_score = cv2.Laplacian(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), cv2.CV_64F).var()
        
        watermark_detected = False
        if self.config.detect_watermarks:
            watermark_detected = detect_watermark(frame, self.config.watermark_threshold)
        
        if quality_score >= self.config.quality_threshold and blur_score >= self.config.blur_threshold:
            frame = self.apply_filters(frame)
            frame_path = self._save_frame(frame, output_folder, count, quality_score, blur_score, watermark_detected)
            return f"Saved frame {frame_path}", True
        
        return f"Skipped frame {count} (Quality: {quality_score:.2f}, Blur: {blur_score:.2f})", False

    def _process_frame_gpu(self, frame: np.ndarray) -> np.ndarray:
        try:
            import pycuda.gpuarray as gpuarray
            
            frame_float = frame.astype(np.float32) / 255.0
            frame_gpu = gpuarray.to_gpu(frame_float)
            frame_gpu *= 1.2
            frame = (frame_gpu.get() * 255).astype(np.uint8)
            
            return frame
        except Exception as e:
            logger.error(f"GPU processing failed: {e}")
            return frame

    def _save_frame(self, frame: np.ndarray, output_folder: str, count: int,
                   quality_score: float, blur_score: float, watermark_detected: bool = False) -> str:
        filename = f"frame_{count:06d}_q{int(quality_score):02d}_b{int(blur_score):02d}"
        if watermark_detected:
            filename += "_watermarked"
        filename += ".png" if self.config.use_png else ".jpg"
        output_path = os.path.join(output_folder, filename)
        
        cv2.imwrite(output_path, frame)
        return output_path

class VideoDownloader:
    def __init__(self, config: VideoConfig):
        self.config = config

    def download(self, url: str, output_path: str) -> str:
        if not check_ffmpeg():
            logger.warning("FFmpeg not found. Some features may be limited.")

        ydl_opts = {
            'outtmpl': output_path,
            'format': self._get_format_string(),
            'merge_output_format': 'mp4',
            'verbose': self.config.verbose
        }

        max_retries = 3
        for attempt in range(max_retries):
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                    ydl.download([url])
                return info['title']
            except yt_dlp.DownloadError as e:
                if attempt == max_retries - 1:
                    raise RuntimeError(f"Failed to download video after {max_retries} attempts: {e}")
                logger.warning(f"Download attempt {attempt + 1} failed. Retrying...")

    def _get_format_string(self) -> str:
        if self.config.max_resolution:
            return f'bestvideo[height<={self.config.max_resolution}]+bestaudio/best[height<={self.config.max_resolution}]'
        return 'bestvideo+bestaudio/best'

class FrameExtractor:
    def __init__(self, config: VideoConfig):
        self.config = config
        self.processor = VideoProcessor(config)

    def extract_frames(self, video_path: str, output_folder: str) -> Tuple[int, int, int]:
        if not os.path.exists(output_folder):
            os.makedirs(output_folder)

        video = cv2.VideoCapture(video_path)
        if not video.isOpened():
            raise RuntimeError(f"Unable to open video file: {video_path}")

        try:
            return self._process_video(video, output_folder)
        finally:
            video.release()

    def _process_video(self, video: cv2.VideoCapture, output_folder: str) -> Tuple[int, int, int]:
        fps = video.get(cv2.CAP_PROP_FPS)
        total_frames = int(video.get(cv2.CAP_PROP_FRAME_COUNT))

        if self.config.method == 'interval':
            frame_interval = int(fps * self.config.interval_seconds)
        elif self.config.method == 'all':
            frame_interval = 1
        else:
            frame_interval = int(fps * self.config.interval_seconds)

        frames = self._get_frames_to_process(video, total_frames, frame_interval)
        return self._process_frames(frames, output_folder)

    def _get_frames_to_process(self, video: cv2.VideoCapture, total_frames: int, 
                             frame_interval: int) -> List[Tuple[np.ndarray, str, int]]:
        frames = []
        for frame_number in range(0, total_frames, frame_interval):
            video.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
            ret, frame = video.read()
            if ret:
                frames.append((frame, str(frame_number), len(frames)))
        return frames

    def _process_frames(self, frames: List[Tuple[np.ndarray, str, int]], 
                       output_folder: str) -> Tuple[int, int, int]:
        total_frames = len(frames)
        skipped_frames = saved_frames = 0
        progress_file = os.path.join(output_folder, "progress.json") if self.config.resume else None

        with tqdm(total=total_frames, disable=not self.config.verbose) as pbar:
            if self.config.use_parallel:
                results = self._process_parallel(frames, output_folder, pbar, progress_file)
            else:
                results = self._process_sequential(frames, output_folder, pbar, progress_file)

        for _, saved in results:
            if saved:
                saved_frames += 1
            else:
                skipped_frames += 1

        return total_frames, skipped_frames, saved_frames

    def _process_parallel(self, frames: List[Tuple[np.ndarray, str, int]], 
                         output_folder: str, pbar: tqdm, 
                         progress_file: Optional[str]) -> List[Tuple[str, bool]]:
        results = []
        with ThreadPoolExecutor() as executor:
            future_to_frame = {
                executor.submit(self.processor.process_frame, (frame, output_folder, count)): (frame, count)
                for frame, _, count in frames
            }
            
            for future in as_completed(future_to_frame):
                result = future.result()
                results.append(result)
                pbar.update(1)
                
                if progress_file:
                    self._save_progress(progress_file, len(results), results)
                    
        return results

    def _process_sequential(self, frames: List[Tuple[np.ndarray, str, int]], 
                          output_folder: str, pbar: tqdm,
                          progress_file: Optional[str]) -> List[Tuple[str, bool]]:
        results = []
        for frame, _, count in frames:
            result = self.processor.process_frame((frame, output_folder, count))
            results.append(result)
            pbar.update(1)
            
            if progress_file:
                self._save_progress(progress_file, len(results), results)
                
        return results

    def _save_progress(self, progress_file: str, processed_frames: int, 
                      results: List[Tuple[str, bool]]) -> None:
        progress = {
            "processed_frames": processed_frames,
            "skipped_frames": sum(1 for _, saved in results if not saved),
            "saved_frames": sum(1 for _, saved in results if saved)
        }
        with open(progress_file, "w") as f:
            json.dump(progress, f)

def generate_thumbnail(output_folder: str) -> None:
    frames = sorted([f for f in os.listdir(output_folder) 
                    if f.endswith(('.jpg', '.png'))])[:9]
    
    if not frames:
        logger.warning("No frames found to generate thumbnail.")
        return
    
    images = [Image.open(os.path.join(output_folder, f)) for f in frames]
    width, height = images[0].size
    thumbnail = Image.new('RGB', (width * 3, height * 3))
    
    for i, image in enumerate(images):
        thumbnail.paste(image, ((i % 3) * width, (i // 3) * height))
    
    thumbnail.save(os.path.join(output_folder, 'thumbnail_montage.jpg'))
    logger.info("Thumbnail montage generated.")

def main() -> None:
    parser = argparse.ArgumentParser(description="Extract high-quality screenshots from videos")
    parser.add_argument("source", help="YouTube video URL or path to local video file")
    parser.add_argument("--method", choices=['interval', 'all', 'keyframes', 'scene'], 
                       default='interval', help="Frame extraction method")
    parser.add_argument("--interval", type=float, default=5.0, 
                       help="Interval between frames in seconds")
    parser.add_argument("--quality", type=float, default=12.0, 
                       help="Quality threshold (0-100)")
    parser.add_argument("--blur", type=float, default=10.0, 
                       help="Blur threshold")
    parser.add_argument("--detect-watermarks", action="store_true", 
                       help="Enable watermark detection")
    parser.add_argument("--watermark-threshold", type=float, default=0.8, 
                       help="Watermark detection sensitivity (0-1)")
    parser.add_argument("--max-resolution", type=int, 
                       help="Maximum resolution for YouTube downloads")
    parser.add_argument("--output", type=str, help="Custom output folder")
    parser.add_argument("--png", action="store_true", help="Save as PNG")
    parser.add_argument("--disable-parallel", action="store_true", 
                       help="Disable parallel processing")
    parser.add_argument("--use-gpu", action="store_true", help="Use GPU acceleration")
    parser.add_argument("--fast-scene", action="store_true", 
                       help="Fast scene detection mode")
    parser.add_argument("--resume", action="store_true", 
                       help="Resume interrupted extraction")
    parser.add_argument("--thumbnail", action="store_true", 
                       help="Generate thumbnail montage")
    parser.add_argument("--verbose", action="store_true", help="Enable detailed logging")
    parser.add_argument("--config", type=str, help="Load JSON configuration file")
    parser.add_argument("--gradfun", action="store_true", 
                       help="Apply gradfun filter")
    parser.add_argument("--deblock", action="store_true", 
                       help="Apply deblocking filter")
    parser.add_argument("--deband", action="store_true", 
                       help="Apply debanding filter")
    args = parser.parse_args()

    if args.config:
        with open(args.config, 'r') as f:
            config_data = json.load(f)
            parser.set_defaults(**config_data)
            args = parser.parse_args()

    if not (0 <= args.quality <= 100):
        parser.error("Quality threshold must be between 0 and 100")
    if not (0 <= args.watermark_threshold <= 1):
        parser.error("Watermark threshold must be between 0 and 1")
    if args.interval <= 0:
        parser.error("Interval must be greater than 0")

    config = VideoConfig(
        quality_threshold=args.quality,
        blur_threshold=args.blur,
        watermark_threshold=args.watermark_threshold,
        interval_seconds=args.interval,
        max_resolution=args.max_resolution,
        detect_watermarks=args.detect_watermarks,
        use_parallel=not args.disable_parallel,
        use_png=args.png,
        use_gpu=args.use_gpu,
        fast_scene=args.fast_scene,
        resume=args.resume,
        verbose=args.verbose,
        gradfun=args.gradfun,
        deblock=args.deblock,
        deband=args.deband,
        method=args.method
    )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    try:
        if args.source.startswith(('http://', 'https://', 'www.')):
            downloader = VideoDownloader(config)
            video_path = f"downloaded_video_{timestamp}.mp4"
            video_title = downloader.download(args.source, video_path)
            output_folder = args.output or f"screenshots_{video_title}_{timestamp}"
        else:
            video_path = args.source
            video_title = Path(video_path).stem
            output_folder = args.output or f"screenshots_{video_title}_{timestamp}"

        os.makedirs(output_folder, exist_ok=True)
        
        extractor = FrameExtractor(config)
        
        start_time = time.time()
        total_frames, skipped_frames, saved_frames = extractor.extract_frames(
            video_path, output_folder
        )
        execution_time = time.time() - start_time

        if args.thumbnail:
            generate_thumbnail(output_folder)

        logger.info(f"\nExtraction complete:")
        logger.info(f"Execution time: {execution_time:.2f}s")
        logger.info(f"Total frames: {total_frames}")
        logger.info(f"Saved frames: {saved_frames}")
        logger.info(f"Skipped frames: {skipped_frames}")
        logger.info(f"Speed: {total_frames/execution_time:.2f} frames/s")

        if config.gradfun or config.deblock or config.deband:
            logger.info("\nPost-processing filters applied:")
            if config.gradfun:
                logger.info("  - Gradfun filter (reduces color banding)")
            if config.deblock:
                logger.info("  - Deblocking filter (reduces compression artifacts)")
            if config.deband:
                logger.info("  - Debanding filter (reduces color banding)")

    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)
    finally:
        if args.source.startswith(('http://', 'https://', 'www.')):
            try:
                os.remove(video_path)
            except OSError:
                pass

if __name__ == "__main__":
    main()
