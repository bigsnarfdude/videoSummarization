from flask import jsonify, render_template, abort
from pathlib import Path
import json
from . import admin_bp
from config import settings

@admin_bp.route('/api/lecture/<lecture_name>')
def get_lecture_stats(lecture_name):
    """Get stats for a specific lecture"""
    try:
        stats_file = settings.OUTPUT_DIRS["stats"] / f"{lecture_name}_stats.json"
        if not stats_file.exists():
            return jsonify({'error': 'Stats not found'}), 404
            
        with open(stats_file, 'r', encoding='utf-8') as f:
            stats = json.load(f)
        return jsonify(stats)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def get_stats_data():
    """Get statistics from all stats files"""
    stats_dir = settings.OUTPUT_DIRS["stats"]
    word_counts = {"total": 0, "by_document": []}
    all_stats = []
    
    try:
        for stats_file in stats_dir.glob("*_stats.json"):
            try:
                with open(stats_file, 'r', encoding='utf-8') as f:
                    stats = json.load(f)
                    all_stats.append(stats)
                    
                    # Add word count stats
                    doc_word_count = stats['analysis'].get('word_count', 0)
                    word_counts["total"] += doc_word_count
                    word_counts["by_document"].append({
                        "name": stats['metadata']['title'],
                        "words": doc_word_count
                    })
            except (json.JSONDecodeError, KeyError) as e:
                print(f"Error processing {stats_file}: {e}")
                continue
                
        # Calculate average word count
        doc_count = len(word_counts["by_document"])
        word_counts["average"] = word_counts["total"] // doc_count if doc_count > 0 else 0
        
        return {
            "word_counts": word_counts,
            "total_documents": doc_count,
            "processing_stats": {
                "total_chunks": sum(s['analysis'].get('chunk_count', 0) for s in all_stats),
                "total_summaries": sum(s['analysis'].get('summary_count', 0) for s in all_stats)
            }
        }
        
    except Exception as e:
        print(f"Error reading stats directory: {e}")
        return None

@admin_bp.route('/')
def admin_dashboard():
    """Render the admin dashboard template"""
    return render_template('admin/dashboard.html')

@admin_bp.route('/api/stats')
def get_stats():
    """API endpoint for dashboard statistics"""
    try:
        stats_data = get_stats_data()
        if stats_data is None:
            return jsonify({'error': 'Error processing stats data'}), 500
            
        return jsonify(stats_data)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500