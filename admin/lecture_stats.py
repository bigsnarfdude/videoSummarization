from pathlib import Path
import json
from datetime import datetime
from typing import Dict, Any

class LectureStatsTracker:
    """Track and manage statistics for processed lectures"""
    
    def __init__(self, stats_dir: str = "files/stats"):
        self.stats_dir = Path(stats_dir)
        self.stats_dir.mkdir(parents=True, exist_ok=True)
        
    def save_lecture_stats(self, lecture_id: str, stats: Dict[str, Any]):
        """Save statistics for a specific lecture"""
        stats_file = self.stats_dir / f"{lecture_id}_stats.json"
        stats['timestamp'] = datetime.now().isoformat()
        
        with open(stats_file, 'w') as f:
            json.dump(stats, f, indent=2)
            
    def get_lecture_stats(self, lecture_id: str) -> Dict[str, Any]:
        """Retrieve statistics for a specific lecture"""
        stats_file = self.stats_dir / f"{lecture_id}_stats.json"
        if stats_file.exists():
            with open(stats_file) as f:
                return json.load(f)
        return {}
        
    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """Retrieve statistics for all lectures"""
        all_stats = {}
        for stats_file in self.stats_dir.glob("*_stats.json"):
            lecture_id = stats_file.stem.replace('_stats', '')
            with open(stats_file) as f:
                all_stats[lecture_id] = json.load(f)
        return all_stats
        
    def delete_lecture_stats(self, lecture_id: str) -> bool:
        """Delete statistics for a specific lecture"""
        stats_file = self.stats_dir / f"{lecture_id}_stats.json"
        if stats_file.exists():
            stats_file.unlink()
            return True
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
                
            updated_stats = update_dict(current_stats, stats_update)
            self.save_lecture_stats(lecture_id, updated_stats)
            return True
        return False
        
    def clear_all_stats(self):
        """Delete all lecture statistics"""
        for stats_file in self.stats_dir.glob("*_stats.json"):
            stats_file.unlink()
