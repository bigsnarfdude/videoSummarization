from pathlib import Path
import json
from datetime import datetime
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class LectureStatsTracker:
    """Track and manage statistics for processed lectures"""
    
    def __init__(self, stats_dir: str = "files/stats"):
        self.stats_dir = Path(stats_dir)
        self.stats_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Initialized LectureStatsTracker with directory: {self.stats_dir}")
        
    def save_lecture_stats(self, lecture_id: str, stats: Dict[str, Any]):
        """Save statistics for a specific lecture"""
        try:
            stats_file = self.stats_dir / f"{lecture_id}_stats.json"
            logger.info(f"Attempting to save stats to: {stats_file}")
            
            # Add timestamp
            stats['timestamp'] = datetime.now().isoformat()
            
            # Create the file with pretty formatting
            with open(stats_file, 'w', encoding='utf-8') as f:
                json.dump(stats, f, indent=2, ensure_ascii=False)
                
            logger.info(f"Successfully saved stats to {stats_file}")
            
            # Verify the file was created
            if stats_file.exists():
                logger.info(f"Verified file exists: {stats_file}")
                logger.info(f"File size: {stats_file.stat().st_size} bytes")
            else:
                logger.error(f"File was not created: {stats_file}")
                
        except Exception as e:
            logger.error(f"Error saving stats for lecture {lecture_id}: {e}")
            raise
        
    def get_lecture_stats(self, lecture_id: str) -> Dict[str, Any]:
        """Retrieve statistics for a specific lecture"""
        stats_file = self.stats_dir / f"{lecture_id}_stats.json"
        if stats_file.exists():
            try:
                with open(stats_file, encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error reading stats for lecture {lecture_id}: {e}")
                return {}
        return {}
        
    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """Retrieve statistics for all lectures"""
        all_stats = {}
        for stats_file in self.stats_dir.glob("*_stats.json"):
            lecture_id = stats_file.stem.replace('_stats', '')
            try:
                with open(stats_file, encoding='utf-8') as f:
                    all_stats[lecture_id] = json.load(f)
            except Exception as e:
                logger.error(f"Error reading stats file {stats_file}: {e}")
        return all_stats
        
    def delete_lecture_stats(self, lecture_id: str) -> bool:
        """Delete statistics for a specific lecture"""
        stats_file = self.stats_dir / f"{lecture_id}_stats.json"
        if stats_file.exists():
            try:
                stats_file.unlink()
                logger.info(f"Deleted stats file: {stats_file}")
                return True
            except Exception as e:
                logger.error(f"Error deleting stats file {stats_file}: {e}")
        return False
        
    def update_lecture_stats(self, lecture_id: str, stats_update: Dict[str, Any]) -> bool:
        """Update specific fields in a lecture's statistics"""
        current_stats = self.get_lecture_stats(lecture_id)
        if current_stats:
            # Recursively update nested dictionaries
            def update_dict(d, u):
                for k, v in u.items():
                    if isinstance(v, dict) and k in d:
                        d[k] = update_dict(d[k], v)
                    else:
                        d[k] = v
                return d
                
            try:
                updated_stats = update_dict(current_stats, stats_update)
                self.save_lecture_stats(lecture_id, updated_stats)
                logger.info(f"Updated stats for lecture {lecture_id}")
                return True
            except Exception as e:
                logger.error(f"Error updating stats for lecture {lecture_id}: {e}")
        return False