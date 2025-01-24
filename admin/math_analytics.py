from collections import Counter, defaultdict
import re
from typing import Dict, List, Optional
from pathlib import Path
import requests
from config import settings
import logging

logger = logging.getLogger(__name__)

class MathLectureAnalyzer:
    def __init__(self, transcript_dir: Optional[str] = None):
        self.transcript_dir = Path(transcript_dir) if transcript_dir else None
        self.lectures = []
        if transcript_dir:
            self.lectures = self._load_lectures()

    def _load_lectures(self) -> List[Dict]:
        lectures = []
        if not self.transcript_dir or not self.transcript_dir.exists():
            logger.warning(f"Transcript directory not found: {self.transcript_dir}")
            return lectures

        try:
            for file_path in self.transcript_dir.glob("*.txt"):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    lectures.append({
                        'name': file_path.stem,
                        'path': str(file_path),
                        'content': content
                    })
                except Exception as e:
                    logger.error(f"Error loading lecture file {file_path}: {e}")
                    continue

            logger.info(f"Loaded {len(lectures)} lectures from {self.transcript_dir}")
            return lectures

        except Exception as e:
            logger.error(f"Error loading lectures: {e}")
            return []

    def _generate_analysis(self, prompt: str) -> str:
        try:
            response = requests.post(
                f"{settings.OLLAMA_CONFIG['base_url']}/api/generate",
                json={
                    "model": settings.OLLAMA_CONFIG["model"],
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "num_predict": settings.OLLAMA_CONFIG["max_tokens"]
                    }
                },
                timeout=settings.OLLAMA_CONFIG["timeout"]
            )
            response.raise_for_status()
            return response.json().get("response", "")
        except Exception as e:
            logger.error(f"Error generating analysis: {e}")
            return ""

    def analyze_topic_relationships(self, content: str) -> Dict:
        prompt = f"""Analyze the mathematical relationships between topics in this lecture.
Focus on:
1. Core concepts and their dependencies
2. How topics build upon each other
3. Key theoretical connections

Content:
{content[:2000]}

Format your response as:
Core Topics: [list key topics]
Dependencies: [list topic dependencies]
Theoretical Links: [list theoretical connections]
"""
        analysis = self._generate_analysis(prompt)
        return self._parse_topic_analysis(analysis)

    def generate_concept_map(self, content: str) -> Dict:
        prompt = f"""Create a concept map for this mathematical content.
Identify:
1. Key concepts
2. Their relationships
3. Prerequisites
4. Applications

Content:
{content[:2000]}

Format as:
Concepts: [list concepts]
Relationships: [list relationships]
Prerequisites: [list prerequisites]
Applications: [list applications]
"""
        map_data = self._generate_analysis(prompt)
        return self._parse_concept_map(map_data)

    def identify_learning_objectives(self, content: str) -> Dict:
        prompt = f"""Analyze this mathematics lecture and identify:
1. Main learning objectives
2. Key theoretical understandings
3. Practical skills developed
4. Assessment points

Content:
{content[:2000]}

Format as bullet points under each category.
"""
        objectives = self._generate_analysis(prompt)
        return self._parse_learning_objectives(objectives)

    def analyze_complexity(self) -> List[Dict]:
        if not self.lectures:
            return [{
                'total_score': 5.0,
                'metrics': {
                    'term_density': 5.0,
                    'concept_density': 5.0,
                    'abstraction_level': 5.0
                }
            }]

        complexity_scores = []
        for lecture in self.lectures:
            metrics = {
                'term_density': 5.0,
                'concept_density': 5.0,
                'abstraction_level': 5.0
            }
            
            total_score = sum(metrics.values()) / len(metrics)
            
            complexity_scores.append({
                'lecture': lecture['name'],
                'total_score': total_score,
                'metrics': metrics
            })
            
        return complexity_scores

    def _parse_topic_analysis(self, analysis: str) -> Dict:
        sections = {
            'core_topics': [],
            'dependencies': [],
            'theoretical_links': []
        }
        
        current_section = None
        for line in analysis.split('\n'):
            line = line.strip()
            if 'Core Topics:' in line:
                current_section = 'core_topics'
            elif 'Dependencies:' in line:
                current_section = 'dependencies'
            elif 'Theoretical Links:' in line:
                current_section = 'theoretical_links'
            elif current_section and line and not line.endswith(':'):
                sections[current_section].append(line)
                
        return sections

    def _parse_concept_map(self, map_data: str) -> Dict:
        sections = {
            'concepts': [],
            'relationships': [],
            'prerequisites': [],
            'applications': []
        }
        
        current_section = None
        for line in map_data.split('\n'):
            line = line.strip()
            if 'Concepts:' in line:
                current_section = 'concepts'
            elif 'Relationships:' in line:
                current_section = 'relationships'
            elif 'Prerequisites:' in line:
                current_section = 'prerequisites'
            elif 'Applications:' in line:
                current_section = 'applications'
            elif current_section and line and not line.endswith(':'):
                sections[current_section].append(line)
                
        return sections

    def _parse_learning_objectives(self, objectives: str) -> Dict:
        sections = {
            'main_objectives': [],
            'theoretical_understanding': [],
            'practical_skills': [],
            'assessment_points': []
        }
        
        current_section = None
        for line in objectives.split('\n'):
            line = line.strip()
            if 'Main learning objectives:' in line:
                current_section = 'main_objectives'
            elif 'Key theoretical understandings:' in line:
                current_section = 'theoretical_understanding'
            elif 'Practical skills developed:' in line:
                current_section = 'practical_skills'
            elif 'Assessment points:' in line:
                current_section = 'assessment_points'
            elif current_section and line.startswith('- '):
                sections[current_section].append(line[2:])
                
        return sections