from pathlib import Path
from typing import Dict, List, TypedDict, Any
from pydantic_settings import BaseSettings, SettingsConfigDict
import os 


class TranscriptionConfig(TypedDict):
    language: str
    sample_rate: int
    channels: int

class Settings(BaseSettings):
    """Application settings with validation using Pydantic"""
    
    # Basic app configuration
    APP_NAME: str = "Video Processing Service"
    APP_ENV: str = "development"  # development, testing, production
    DEBUG: bool = False
    API_PREFIX: str = "/api/v1"
    SECRET_KEY: str = "your-secret-key-here"  # Override in production
    
    # Server settings
    HOST: str = "0.0.0.0"
    PORT: int = 5000
    WORKERS: int = 4
    
    # File processing settings
    MAX_FILE_SIZE: int = 500 * 1024 * 1024  # 500MB
    ALLOWED_EXTENSIONS: List[str] = ["mp4", "avi", "mov", "mkv"]
    MAX_FILENAME_LENGTH: int = 100
    
    # Model configuration
    WHISPER_PATH: str = "/Users/vincent/development/whisper.cpp/main"
    WHISPER_MODEL_PATH: str = "/Users/vincent/development/whisper.cpp/models/ggml-large-v3.bin"
    MLX_MODEL_NAME: str = "mlx-community/phi-4-8bit"
    WINDOW_SIZE: int = 4096
    
    # Base directory configuration
    BASE_DIR: Path = Path(__file__).resolve().parent
    
    # Directory structure
    OUTPUT_DIRS: Dict[str, Path] = {
        "uploads": BASE_DIR / "files/uploads",
        "audio": BASE_DIR / "files/audio",
        "transcripts": BASE_DIR / "files/transcripts",
        "summaries": BASE_DIR / "files/summaries",
        "logseq": BASE_DIR / "files/logseq"
    }
    
    # Logging configuration
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    LOG_FILE: Path = BASE_DIR / "logs/app.log"
    
    # Rate limiting
    RATE_LIMIT_REQUESTS: int = 10
    RATE_LIMIT_WINDOW: int = 60  # seconds
    
    # Model specific settings
    TRANSCRIPTION_CONFIG: TranscriptionConfig = {
        "language": "en",
        "sample_rate": 16000,
        "channels": 1
    }
    
    # Configure environment file loading
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True
    )
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._init_directories()
        self._validate_paths()
    
    def _init_directories(self) -> None:
        """Initialize all required directories"""
        # Create logs directory
        os.makedirs(self.BASE_DIR / "logs", exist_ok=True)
        
        # Create all output directories
        for directory in self.OUTPUT_DIRS.values():
            os.makedirs(directory, exist_ok=True)
    
    def _validate_paths(self) -> None:
        """Validate critical paths and executables"""
        if self.APP_ENV != "testing":
            if not os.path.isfile(self.WHISPER_PATH):
                raise ValueError(f"Whisper executable not found at {self.WHISPER_PATH}")
            if not os.path.isfile(self.WHISPER_MODEL_PATH):
                raise ValueError(f"Whisper model not found at {self.WHISPER_MODEL_PATH}")
    
    @property
    def is_development(self) -> bool:
        return self.APP_ENV == "development"
    
    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"
    
    @property
    def is_testing(self) -> bool:
        return self.APP_ENV == "testing"

# Create global settings instance
settings = Settings()