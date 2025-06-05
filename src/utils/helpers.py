"""
Helper functions for the application.
"""
import json
from typing import Dict, Any, List

def format_distribution_string(difficulty_distribution: Dict[str, float]) -> str:
    """
    Format a difficulty distribution dictionary into a string for file naming.
    
    Args:
        difficulty_distribution: Dictionary mapping difficulty levels to proportions
        
    Returns:
        str: Formatted string (e.g., "basic30_intermediate40_advanced30")
    """
    return "_".join([f"{diff}{int(prop*100)}" for diff, prop in difficulty_distribution.items()])

def save_to_json_file(data: Any, file_path: str) -> None:
    """
    Save data to a JSON file.
    
    Args:
        data: Data to save
        file_path: Path to save the file
    """
    with open(file_path, 'w') as json_file:
        json.dump(data, json_file, indent=2)

def load_from_json_file(file_path: str) -> Any:
    """
    Load data from a JSON file.
    
    Args:
        file_path: Path to the JSON file
        
    Returns:
        The loaded data
    """
    with open(file_path, 'r') as json_file:
        return json.load(json_file)

def generate_file_name(filter_value: str, distribution_str: str, question_type: str) -> str:
    """
    Generate a standardized file name for question output.
    
    Args:
        filter_value: The filter value used (often a chapter ID)
        distribution_str: Formatted string of difficulty distribution
        question_type: Type of questions (mcq, tf, fib)
        
    Returns:
        str: Generated file name
    """
    suffix = ""
    if question_type == "mcq":
        suffix = "mcqs"
    elif question_type == "fib":
        suffix = "fib"
    elif question_type == "tf":
        suffix = "tf"
    
    return f"{filter_value}_{distribution_str}_{suffix}.json"

def get_difficulty_description(difficulty):
    """Return a description of what each difficulty level means for question generation."""
    if difficulty == "basic":
        return "recall of facts and basic understanding of concepts"
    elif difficulty == "intermediate":
        return "application of concepts and analysis of relationships"
    elif difficulty == "advanced":
        return "synthesis of multiple concepts and evaluation of complex scenarios"
    else:
        return "appropriate college-level understanding"

def get_blooms_question_guidelines(blooms_level, question_type):
    """Return specific guidelines for creating questions at a given Bloom's level and question type."""
    
    if question_type == "mcq":
        if blooms_level == "remember":
            return "Focus on direct recall of facts, definitions, and basic concepts. Stem should ask for specific information covered in the material."
        elif blooms_level == "apply":
            return "Present a scenario or problem that requires applying learned concepts. Stem should describe a situation where students must use their knowledge."
        elif blooms_level == "analyze":
            return "Present complex scenarios requiring analysis of multiple variables. Stem should require students to examine, compare, or evaluate information."
    
    elif question_type == "tf":
        if blooms_level == "remember":
            return "State facts, definitions, or basic concepts clearly. Focus on information directly covered in the material."
        elif blooms_level == "apply":
            return "Present statements about applying concepts to situations. Focus on whether procedures or principles are correctly applied."
        elif blooms_level == "analyze":
            return "Present statements requiring analysis of complex relationships. Focus on evaluations, comparisons, or synthesis of information."
    
    elif question_type == "fib":
        if blooms_level == "remember":
            return "Remove key terms, definitions, or factual information. Focus on vocabulary, names, dates, and basic concepts."
        elif blooms_level == "apply":
            return "Remove answers that require applying formulas or procedures. Focus on results of calculations or applications."
        elif blooms_level == "analyze":
            return "Remove conclusions, evaluations, or synthesis results. Focus on analytical outcomes or judgments."
    
    return "appropriate cognitive level thinking"

def get_blooms_description(blooms_level):
    """Return a description of what each Bloom's taxonomy level means for question generation."""
    if blooms_level == "remember":
        return """Remember/Understand level - Assessment items that ask students to show they can recall basic information or understand basic concepts. Questions should focus on:
        - Recalling definitions, facts, and basic information
        - Understanding fundamental concepts
        - Identifying key terms and their meanings
        - Listing components or steps
        - Outlining basic structures or processes
        
        Examples: "What is the definition of...?", "List the components of...", "In what year was...", "What is the first stage of...?"
        """
    elif blooms_level == "apply":
        return """Apply level - Assessment items that ask students to apply their knowledge of a concept to a situation or problem. Questions should focus on:
        - Using knowledge to solve problems
        - Applying concepts to new situations
        - Calculating using formulas or procedures
        - Implementing procedures in given contexts
        - Using information to complete tasks
        
        Examples: "Solve for x in...", "Use the information in the table to calculate...", "Apply the concept of... to determine..."
        """
    elif blooms_level == "analyze":
        return """Analyze/Evaluate/Create level - Assessment items that require students to examine information by parts, make decisions, or create new solutions. Questions should focus on:
        - Examining information to identify causes and effects
        - Making decisions based on provided variables
        - Comparing and contrasting different approaches
        - Evaluating effectiveness of strategies
        - Creating new solutions or ideas
        - Analyzing scenarios to determine best outcomes
        - Synthesizing information from multiple sources
        
        Examples: "Based on the scenario, which strategy would maximize...", "Given the situation, rank the following actions...", "Which combination of factors would be most effective...", "Analyze the data to determine..."
        """
    else:
        return "appropriate cognitive level thinking"

def validate_distributions(question_type_dist: Dict[str, float], difficulty_dist: Dict[str, float], blooms_dist: Dict[str, float]) -> bool:
    """
    Validate that all distributions sum to approximately 1.0.
    
    Args:
        question_type_dist: Question type distribution
        difficulty_dist: Difficulty distribution  
        blooms_dist: Bloom's taxonomy distribution
        
    Returns:
        bool: True if all distributions are valid
    """
    tolerance = 0.01  # Allow small floating point errors
    
    distributions = [question_type_dist, difficulty_dist, blooms_dist]
    names = ["question_type", "difficulty", "blooms_taxonomy"]
    
    for dist, name in zip(distributions, names):
        total = sum(dist.values())
        if abs(total - 1.0) > tolerance:
            print(f"Warning: {name} distribution sums to {total:.3f}, not 1.0")
            return False
    
    return True

def normalize_distribution(distribution: Dict[str, float]) -> Dict[str, float]:
    """
    Normalize a distribution so it sums to 1.0.
    
    Args:
        distribution: Distribution to normalize
        
    Returns:
        Dict: Normalized distribution
    """
    total = sum(distribution.values())
    if total == 0:
        # If all values are 0, distribute equally
        num_items = len(distribution)
        return {k: 1.0/num_items for k in distribution.keys()}
    
    return {k: v/total for k, v in distribution.items()}

def calculate_question_counts(total_questions: int, distributions: List[Dict[str, float]]) -> Dict[str, int]:
    """
    Calculate exact question counts for all combinations of distributions.
    
    Args:
        total_questions: Total number of questions
        distributions: List of distributions (question_type, difficulty, blooms)
        
    Returns:
        Dict: Mapping of combination keys to question counts
    """
    question_type_dist, difficulty_dist, blooms_dist = distributions
    
    # Validate distributions
    if not validate_distributions(question_type_dist, difficulty_dist, blooms_dist):
        # Normalize if needed
        question_type_dist = normalize_distribution(question_type_dist)
        difficulty_dist = normalize_distribution(difficulty_dist)
        blooms_dist = normalize_distribution(blooms_dist)
    
    # Calculate fractional counts
    fractional_counts = {}
    for q_type, q_ratio in question_type_dist.items():
        for difficulty, d_ratio in difficulty_dist.items():
            for blooms, b_ratio in blooms_dist.items():
                key = f"{q_type}_{difficulty}_{blooms}"
                exact_count = total_questions * q_ratio * d_ratio * b_ratio
                fractional_counts[key] = exact_count
    
    # Round to integers using largest remainder method
    integer_counts = {k: int(v) for k, v in fractional_counts.items()}
    remainder = total_questions - sum(integer_counts.values())
    
    # Distribute remainder based on largest fractional parts
    if remainder > 0:
        remainders = [(k, fractional_counts[k] - integer_counts[k]) for k in fractional_counts.keys()]
        remainders.sort(key=lambda x: x[1], reverse=True)
        
        for i in range(remainder):
            if i < len(remainders):
                key = remainders[i][0]
                integer_counts[key] += 1
    
    # Remove zero counts
    return {k: v for k, v in integer_counts.items() if v > 0}
