from flask import jsonify, render_template
from pathlib import Path
from . import admin_bp  # This import will now work
from .math_analytics import MathLectureAnalyzer

@admin_bp.route('/')
def admin_dashboard():
    """Render the admin dashboard template"""
    return render_template('admin/dashboard.html')

@admin_bp.route('/api/stats')
def get_stats():
    """API endpoint for dashboard statistics with Phi-4 enhanced analysis"""
    try:
        # Initialize analyzer
        analyzer = MathLectureAnalyzer("files/transcripts")
        
        # Get complexity analysis
        complexity_scores = analyzer.analyze_complexity()
        
        # Get topic progression
        topic_progression = analyzer.analyze_topic_progression()
        
        # Get prerequisites
        prerequisites = analyzer.identify_prerequisites()
        
        # Get educational metrics
        educational_metrics = analyzer.calculate_educational_metrics()
        
        # Get topic overlap
        topic_overlap = analyzer.analyze_topic_overlap()

        # Get advanced analyses using Phi-4
        lecture_content = analyzer.lectures[0]['content'] if analyzer.lectures else ""
        topic_relationships = analyzer.analyze_topic_relationships(lecture_content)
        concept_map = analyzer.generate_concept_map(lecture_content)
        learning_objectives = analyzer.identify_learning_objectives(lecture_content)
        
        return jsonify({
            'complexity_analysis': {
                'scores': complexity_scores,
                'average': sum(s['total_score'] for s in complexity_scores) / len(complexity_scores) if complexity_scores else 0,
                'phi4_insights': {
                    'topic_relationships': topic_relationships,
                    'concept_map': concept_map,
                    'learning_objectives': learning_objectives
                }
            },
            'topic_analysis': {
                'progression': topic_progression,
                'prerequisites': prerequisites,
                'overlap': {f"{k[0]}-{k[1]}": v for k, v in topic_overlap.items()}
            },
            'educational_metrics': educational_metrics
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500