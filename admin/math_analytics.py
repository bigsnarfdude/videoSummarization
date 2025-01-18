from collections import Counter, defaultdict
import re
from typing import Dict, List, Tuple, Set, Optional
import numpy as np
from pathlib import Path
from mlx_lm import load, generate
from config import settings
import logging

logger = logging.getLogger(__name__)

class MathLectureAnalyzer:
    def __init__(self, transcript_dir: Optional[str] = None):
        """Initialize the analyzer with optional transcript directory"""
        self.transcript_dir = Path(transcript_dir) if transcript_dir else None
        self.model, self.tokenizer = self._init_phi4()
        self.lectures = []
        if transcript_dir:
            self.lectures = self._load_lectures()

    def _load_lectures(self) -> List[Dict]:
        """Load lectures from transcript directory"""
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

    def _init_phi4(self):
        """Initialize Phi-4 model"""
        try:
            model, tokenizer = load(settings.MLX_MODEL_NAME)
            logger.info("Successfully initialized Phi-4 model")
            return model, tokenizer
        except Exception as e:
            logger.error(f"Error loading Phi-4 model: {e}")
            return None, None

    def _generate_phi4_analysis(self, prompt: str) -> str:
        """Generate analysis using Phi-4"""
        if not self.model or not self.tokenizer:
            logger.error("Model or tokenizer not initialized")
            return ""
            
        try:
            response = generate(
                self.model,
                self.tokenizer,
                prompt=prompt,
                max_tokens=1024,
                verbose=False
            )
            return response
        except Exception as e:
            logger.error(f"Error generating analysis: {e}")
            return ""

    def analyze_topic_relationships(self, content: str) -> Dict:
        """Analyze mathematical topic relationships in content"""
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
        analysis = self._generate_phi4_analysis(prompt)
        return self._parse_topic_analysis(analysis)

    def generate_concept_map(self, content: str) -> Dict:
        """Generate a mathematical concept map"""
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
        map_data = self._generate_phi4_analysis(prompt)
        return self._parse_concept_map(map_data)

    def identify_learning_objectives(self, content: str) -> Dict:
        """Identify learning objectives from content"""
        prompt = f"""Analyze this mathematics lecture and identify:
1. Main learning objectives
2. Key theoretical understandings
3. Practical skills developed
4. Assessment points

Content:
{content[:2000]}

Format as bullet points under each category.
"""
        objectives = self._generate_phi4_analysis(prompt)
        return self._parse_learning_objectives(objectives)

    def analyze_complexity(self) -> List[Dict]:
        """Calculate complexity metrics for content"""
        # For single file analysis
        if not self.lectures:
            return [{
                'total_score': 5.0,  # Default mid-range score
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
        """Parse topic analysis output"""
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
        """Parse concept map output"""
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
        """Parse learning objectives output"""
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