from pathlib import Path
from typing import Dict, List, TypedDict
from pydantic_settings import BaseSettings, SettingsConfigDict
import os 

class TranscriptionConfig(TypedDict):
    model_size: str
    device: str
    compute_type: str
    beam_size: int
    language: str

class OllamaConfig(TypedDict):
    base_url: str
    model: str
    timeout: int
    max_tokens: int

class Settings(BaseSettings):
    """Application settings with validation using Pydantic"""
    
    APP_NAME: str = "Video Processing Service"
    APP_ENV: str = "development" 
    DEBUG: bool = False
    API_PREFIX: str = "/api/v1"
    SECRET_KEY: str = "your-secret-key-here"
    
    HOST: str = "0.0.0.0"
    PORT: int = 5000
    WORKERS: int = 4
    
    MAX_FILE_SIZE: int = 500 * 1024 * 1024  # 500MB
    ALLOWED_EXTENSIONS: List[str] = ["mp4", "avi", "mov", "mkv", "mp3"]
    MAX_FILENAME_LENGTH: int = 100
    
    WINDOW_SIZE: int = 4096
    
    BASE_DIR: Path = Path(__file__).resolve().parent
    
    OUTPUT_DIRS: Dict[str, Path] = {
        "uploads": BASE_DIR / "files/uploads",
        "audio": BASE_DIR / "files/audio",
        "transcripts": BASE_DIR / "files/transcripts",
        "summaries": BASE_DIR / "files/summaries",
        "logseq": BASE_DIR / "files/logseq",
        "stats": BASE_DIR / "files/stats"
    }
    
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    LOG_FILE: Path = BASE_DIR / "logs/app.log"
    
    RATE_LIMIT_REQUESTS: int = 10
    RATE_LIMIT_WINDOW: int = 60
    
    TRANSCRIPTION_CONFIG: TranscriptionConfig = {
        "model_size": "large-v3",
        "device": "cuda", 
        "compute_type": "float16",
        "beam_size": 5,
        "language": "en"
    }

    OLLAMA_CONFIG: OllamaConfig = {
        "base_url": "http://localhost:11434",
        "model": "phi4:latest",
        "timeout": 120,
        "max_tokens": 1024
    }
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True
    )

settings = Settings()
