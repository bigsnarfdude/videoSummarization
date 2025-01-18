from flask import Blueprint, jsonify, request
from pathlib import Path
from .math_analytics import MathLectureAnalyzer
from .lecture_stats import LectureStatsTracker

api_bp = Blueprint('api', __name__, url_prefix='/api/v1/lectures')
stats_tracker = LectureStatsTracker()

@api_bp.route('/', methods=['GET'])
def get_all_lectures():
    """Get a list of all lectures with basic info"""
    try:
        all_stats = stats_tracker.get_all_stats()
        lectures = []
        
        for lecture_id, stats in all_stats.items():
            lectures.append({
                'id': lecture_id,
                'title': stats['basic_info']['title'],
                'duration': stats['basic_info']['duration'],
                'word_count': stats['basic_info']['word_count'],
                'complexity_score': stats['complexity']['total_score']
            })
            
        return jsonify({
            'count': len(lectures),
            'lectures': lectures
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_bp.route('/<lecture_id>', methods=['GET'])
def get_lecture_details(lecture_id: str):
    """Get detailed stats for a specific lecture"""
    try:
        stats = stats_tracker.get_lecture_stats(lecture_id)
        if not stats:
            return jsonify({'error': 'Lecture not found'}), 404
            
        return jsonify(stats)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_bp.route('/<lecture_id>/complexity', methods=['GET'])
def get_lecture_complexity(lecture_id: str):
    """Get complexity analysis for a specific lecture"""
    try:
        stats = stats_tracker.get_lecture_stats(lecture_id)
        if not stats:
            return jsonify({'error': 'Lecture not found'}), 404
            
        return jsonify(stats['complexity'])
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_bp.route('/<lecture_id>/topics', methods=['GET'])
def get_lecture_topics(lecture_id: str):
    """Get topic analysis for a specific lecture"""
    try:
        stats = stats_tracker.get_lecture_stats(lecture_id)
        if not stats:
            return jsonify({'error': 'Lecture not found'}), 404
            
        return jsonify(stats['topics'])
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_bp.route('/search', methods=['GET'])
def search_lectures():
    """Search lectures by topic or concept"""
    query = request.args.get('q', '').lower()
    if not query:
        return jsonify({'error': 'No search query provided'}), 400
        
    try:
        results = []
        all_stats = stats_tracker.get_all_stats()
        
        for lecture_id, stats in all_stats.items():
            # Search in topics
            topics = stats.get('topics', {}).get('core_topics', [])
            # Search in concepts
            concepts = stats.get('concept_map', {}).get('concepts', [])
            
            if any(query in topic.lower() for topic in topics) or \
               any(query in concept.lower() for concept in concepts):
                results.append({
                    'id': lecture_id,
                    'title': stats['basic_info']['title'],
                    'matching_topics': [t for t in topics if query in t.lower()],
                    'matching_concepts': [c for c in concepts if query in c.lower()]
                })
                
        return jsonify({
            'count': len(results),
            'results': results
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_bp.route('/analytics', methods=['GET'])
def get_global_analytics():
    """Get analytics across all lectures"""
    try:
        all_stats = stats_tracker.get_all_stats()
        
        analytics = {
            'total_lectures': len(all_stats),
            'average_complexity': 0,
            'total_duration': 0,
            'total_words': 0,
            'topic_frequency': {},
            'concept_frequency': {}
        }
        
        if all_stats:
            for stats in all_stats.values():
                analytics['average_complexity'] += stats.get('complexity', {}).get('total_score', 0)
                analytics['total_duration'] += stats.get('basic_info', {}).get('duration', 0)
                analytics['total_words'] += stats.get('basic_info', {}).get('word_count', 0)
                
                # Aggregate topics
                for topic in stats.get('topics', {}).get('core_topics', []):
                    analytics['topic_frequency'][topic] = \
                        analytics['topic_frequency'].get(topic, 0) + 1
                        
                # Aggregate concepts
                for concept in stats.get('concept_map', {}).get('concepts', []):
                    analytics['concept_frequency'][concept] = \
                        analytics['concept_frequency'].get(concept, 0) + 1
            
            analytics['average_complexity'] /= len(all_stats)
            
        return jsonify(analytics)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500