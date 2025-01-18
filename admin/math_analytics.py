from collections import Counter, defaultdict
import re
from typing import Dict, List, Tuple, Set
import numpy as np
from pathlib import Path
from mlx_lm import load, generate
from config import settings

class MathLectureAnalyzer:
    def __init__(self, transcript_dir: str):
        self.transcript_dir = Path(transcript_dir)
        self.lectures = self._load_lectures()
        self.model, self.tokenizer = self._init_phi4()

    def _init_phi4(self):
        """Initialize Phi-4 model"""
        try:
            model, tokenizer = load(settings.MLX_MODEL_NAME)
            return model, tokenizer
        except Exception as e:
            print(f"Error loading Phi-4 model: {e}")
            return None, None

    def _generate_phi4_analysis(self, prompt: str) -> str:
        """Generate analysis using Phi-4"""
        if not self.model or not self.tokenizer:
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
            print(f"Error generating analysis: {e}")
            return ""

    def analyze_topic_relationships(self, content: str) -> Dict:
        """Use Phi-4 to analyze relationships between mathematical topics"""
        prompt = f"""Analyze the mathematical relationships and dependencies between topics in this lecture.
Focus on:
1. Core concepts and their dependencies
2. How topics build upon each other
3. Key theoretical connections

Lecture content:
{content[:2000]}  # Limit content length for prompt

Format your response as:
Core Topics: [list key topics]
Dependencies: [list topic dependencies]
Theoretical Links: [list theoretical connections]
"""
        analysis = self._generate_phi4_analysis(prompt)
        return self._parse_topic_analysis(analysis)

    def generate_concept_map(self, content: str) -> Dict:
        """Generate a concept map using Phi-4"""
        prompt = f"""Create a mathematical concept map for this lecture content.
Identify:
1. Key mathematical concepts
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
        """Use Phi-4 to identify learning objectives"""
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

    def _parse_topic_analysis(self, analysis: str) -> Dict:
        """Parse the Phi-4 generated topic analysis"""
        sections = {
            'core_topics': [],
            'dependencies': [],
            'theoretical_links': []
        }
        
        current_section = None
        for line in analysis.split('\n'):
            if 'Core Topics:' in line:
                current_section = 'core_topics'
            elif 'Dependencies:' in line:
                current_section = 'dependencies'
            elif 'Theoretical Links:' in line:
                current_section = 'theoretical_links'
            elif current_section and line.strip():
                sections[current_section].append(line.strip())
                
        return sections

    def _parse_concept_map(self, map_data: str) -> Dict:
        """Parse the Phi-4 generated concept map"""
        sections = {
            'concepts': [],
            'relationships': [],
            'prerequisites': [],
            'applications': []
        }
        
        current_section = None
        for line in map_data.split('\n'):
            if 'Concepts:' in line:
                current_section = 'concepts'
            elif 'Relationships:' in line:
                current_section = 'relationships'
            elif 'Prerequisites:' in line:
                current_section = 'prerequisites'
            elif 'Applications:' in line:
                current_section = 'applications'
            elif current_section and line.strip():
                sections[current_section].append(line.strip())
                
        return sections

    def _parse_learning_objectives(self, objectives: str) -> Dict:
        """Parse the Phi-4 generated learning objectives"""
        sections = {
            'main_objectives': [],
            'theoretical_understanding': [],
            'practical_skills': [],
            'assessment_points': []
        }
        
        current_section = None
        for line in objectives.split('\n'):
            if 'Main learning objectives:' in line:
                current_section = 'main_objectives'
            elif 'Key theoretical understandings:' in line:
                current_section = 'theoretical_understanding'
            elif 'Practical skills developed:' in line:
                current_section = 'practical_skills'
            elif 'Assessment points:' in line:
                current_section = 'assessment_points'
            elif current_section and line.strip().startswith('- '):
                sections[current_section].append(line.strip()[2:])
                
        return sections

    # Add to analyze_complexity method
    def analyze_complexity(self) -> List[Dict]:
        """Calculate complexity scores and generate detailed analysis"""
        complexity_scores = []
        
        for lecture in self.lectures:
            # Get basic complexity metrics
            basic_metrics = self._calculate_basic_complexity(lecture['content'])
            
            # Get Phi-4 analysis of complexity
            prompt = f"""Analyze the mathematical complexity of this lecture.
Consider:
1. Conceptual depth
2. Mathematical sophistication
3. Abstract reasoning required
4. Technical prerequisites

Content:
{lecture['content'][:2000]}

Provide a detailed analysis and a complexity score (1-10).
"""
            phi4_analysis = self._generate_phi4_analysis(prompt)
            
            complexity_scores.append({
                'lecture': lecture['name'],
                'basic_metrics': basic_metrics,
                'phi4_analysis': phi4_analysis,
                'total_score': round((basic_metrics['total_score'] + 
                                    self._extract_phi4_score(phi4_analysis)) / 2, 2)
            })
            
        return complexity_scores

    def _calculate_basic_complexity(self, text: str) -> Dict:
        """Calculate basic complexity metrics"""
        term_density = self._calculate_term_density(text)
        concept_density = self._calculate_concept_density(text)
        abstraction_level = self._calculate_abstraction_level(text)
        
        return {
            'term_density': round(term_density, 2),
            'concept_density': round(concept_density, 2),
            'abstraction': round(abstraction_level, 2),
            'total_score': round((term_density + concept_density + abstraction_level) / 3, 2)
        }

    def _extract_phi4_score(self, analysis: str) -> float:
        """Extract numerical complexity score from Phi-4 analysis"""
        try:
            # Look for numbers between 1-10 in the analysis
            scores = re.findall(r'(?:score:?\s*)(\d+(?:\.\d+)?)', analysis.lower())
            if scores:
                score = float(scores[0])
                return min(max(score, 1), 10)  # Ensure score is between 1-10
            return 5.0  # Default score if none found
        except Exception:
            return 5.0  # Default score if parsing fails
