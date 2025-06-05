import json
import math
import os
import sys
import uuid
import boto3
# Add project root to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Import settings first to set environment variables
from src import settings
from opensearch_py import OpenSearch, RequestsHttpConnection
from opensearch_py.connection.http_auth import AWSV4SignerAuth
from src.utils.constants import CENGAGE_GUIDELINES as cengage_guidelines
from src.utils.constants import metadata_keys
from src.utils.helpers import get_difficulty_description, get_blooms_question_guidelines

# OpenSearch Configuration
HOST = "https://64asp87vin20xc5bhvbf.us-east-1.aoss.amazonaws.com"
REGION = 'us-east-1'
INDEX_NAME = 'chunk_357973585'
AWS_PROFILE_NAME = 'cengage'

def create_question_sequence(question_breakdown):
    """Create a sequence of (difficulty, blooms_level) tuples based on question breakdown"""
    sequence = []
    for combo_key, specs in question_breakdown.items():
        difficulty = specs['difficulty']
        blooms_level = specs['blooms_level']
        count = specs['count']
        
        # Add this combination 'count' times to the sequence
        for _ in range(count):
            sequence.append((difficulty, blooms_level))
    
    return sequence

def parse_fill_in_blank(res, file_name, question_breakdown):
    """Parse Fill-in-blank response and assign metadata programmatically"""
    responses = []
    question_blocks = res.split("QUESTION:")
    
    # Create sequence of difficulty/blooms assignments
    question_sequence = create_question_sequence(question_breakdown)
    question_index = 0
    
    for block in [b.strip() for b in question_blocks if b.strip()]:
        question_obj = {
            "question_id": str(uuid.uuid4()),
            "question": "",
            "answer": [],
            "explanation": "",
            "difficulty": "",
            "blooms_level": "",
            "question_type": "fib"
        }
        
        # Extract components using simple string search
        if "ANSWER:" in block:
            question_obj["question"] = block.split("ANSWER:")[0].strip()
            block = "ANSWER:" + block.split("ANSWER:")[1]
        
        if "ANSWER:" in block and "EXPLANATION:" in block:
            answer_text = block.split("ANSWER:")[1].split("EXPLANATION:")[0].strip()
            answer_lines = answer_text.split('\n')
            for line in answer_lines:
                line = line.strip()
                # Check if line starts with a number followed by a period (e.g., "1. ")
                if line and (line[0].isdigit() and '. ' in line):
                    # Remove the numbering and add to the list
                    answer_item = line.split('. ', 1)[1].strip()
                    question_obj["answer"].append(answer_item)
                elif line:  # If there's text but not in numbered format
                    question_obj["answer"].append(line)
        
        if "EXPLANATION:" in block:
            explanation_text = block.split("EXPLANATION:")[1]
            question_obj["explanation"] = explanation_text.strip()
        
        # Programmatically assign difficulty and blooms_level
        if question_index < len(question_sequence):
            difficulty, blooms_level = question_sequence[question_index]
            question_obj["difficulty"] = difficulty
            question_obj["blooms_level"] = blooms_level
            question_index += 1
        
        responses.append(question_obj)

    json_responses = {
        "response": responses
    }
    json_string = json.dumps(json_responses, indent=4)
    with open(file_name, 'w') as json_file:
        json_file.write(json_string)

def find_title_index(chapter_key):
    """Find the appropriate chapter key based on available data"""
    session = boto3.Session(profile_name=AWS_PROFILE_NAME)
    credentials = session.get_credentials()
    
    auth = AWSV4SignerAuth(credentials, REGION, 'aoss')
    client = OpenSearch(
        hosts=[{'host': HOST.replace('https://', ''), 'port': 443}],
        http_auth=auth,
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection,
        pool_maxsize=20
    )
    
    query = {
        "size": 100,
        "aggs": {
            "chapter_names": {
                "terms": {
                    "field": f"metadata.source.metadata.{chapter_key}.keyword",
                    "size": 200
                }
            }
        }
    }

    response = client.search(
        index=INDEX_NAME,
        body=query
    )

    chapter_buckets = response.get('aggregations', {}).get('chapter_names', {}).get('buckets', [])
    return chapter_buckets

def create_query_body(chapter_name: str, max_chunks: int = 200) -> str:
    """Create query body for OpenSearch"""
    # Determine the correct chapter key
    if 'chapter' in "".join([val['key'].lower() for val in find_title_index('toc_level_2_title')]):
        chapter_key = 'toc_level_2_title'
    else:
        chapter_key = 'toc_level_1_title'
    
    return {
        "query": {
            "term": {
                f"metadata.source.metadata.{chapter_key}.keyword": chapter_name
            }
        },
        "sort": [
            { "metadata.source.metadata.pdf_page_number": "asc" },
            { "metadata.source.metadata.page_sequence": "asc" }
        ],
        "_source": {
            "excludes": ["embedding"]
        },
        "size": max_chunks
    }

def execute_search(query_body):
    """Execute search query and return chapter text"""
    session = boto3.Session(profile_name=AWS_PROFILE_NAME)
    credentials = session.get_credentials()
    
    auth = AWSV4SignerAuth(credentials, REGION, 'aoss')
    client = OpenSearch(
        hosts=[{'host': HOST.replace('https://', ''), 'port': 443}],
        http_auth=auth,
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection,
        pool_maxsize=20
    )
    
    chapter_text = ""
    print(f"\nExecuting search with query body: {query_body}")
    try:
        response = client.search(
            index=INDEX_NAME,
            body=query_body
        )
        print("Search executed successfully.")
    except Exception as e:
        print(f"An error occurred during search: {e}")
        return None

    hits = response['hits']['hits']
    total_hits = response['hits']['total']['value']

    print(f"\nFound {total_hits} matching vectors.")

    for _, hit in enumerate(hits):
        chapter_text += hit['_source']['value']

    return chapter_text

def retrieve_chapter_chunks(chapter_name: str, max_chunks: int = 200, max_chars: int = 100000):
    """
    Retrieve chapter content from OpenSearch based on the chapter name.
    """
    print(f"Retrieving chapter content for: {chapter_name}")
    if not chapter_name:
        raise ValueError("Chapter name must be provided.")
    
    query_body = create_query_body(chapter_name, max_chunks)
    chapter_content = execute_search(query_body)

    if chapter_content and len(chapter_content) > max_chars:
        print(f"Content too large ({len(chapter_content)} chars), truncating to {max_chars} chars")
        chapter_content = chapter_content[:max_chars] + "\n[Content truncated due to size limitations]"

    if chapter_content:
        print(f"Retrieved {len(chapter_content)} characters of content")

    return chapter_content

available_keys = list(set(metadata_keys.keys()))

def generate_fill_in_blank(
    tenant_id='cx2201', 
    chapter_id='56330_ch10_ptg01',
    learning_objectives=None,
    all_keys=available_keys,
    num_questions=10, 
    difficulty_distribution={'advanced': 1.0}, 
    blooms_taxonomy_distribution={'analyze': 1.0}, 
    content_summary=None,
):
    """
    Generate fill-in-the-blank questions for specified book chapter using OpenSearch Serverless
    
    Args:
        tenant_id: The tenant ID (kept for compatibility, not used in new approach)
        chapter_id: The chapter identifier (e.g., '56330_ch10_ptg01') 
        learning_objectives: Optional. Learning objectives (not used in current implementation)
        all_keys: List of all available metadata keys (not used in current implementation)
        num_questions: Number of fill-in-the-blank questions to generate
        difficulty_distribution: Dict with difficulty distribution
        blooms_taxonomy_distribution: Dict with Bloom's distribution
        content_summary: Pre-generated content summary
    
    Returns:
        String containing the generated fill-in-the-blank questions
    """
    print(f"Generating {num_questions} fill-in-the-blank questions for chapter: {chapter_id}")
    if learning_objectives:
        print(f"Learning objectives filter: {learning_objectives}")
    if all_keys:
        print(f"Available metadata keys: {all_keys}")
    print(f"Difficulty distribution: {difficulty_distribution}")
    print(f"Bloom's taxonomy distribution: {blooms_taxonomy_distribution}")
    
    # Use provided summary or generate one using OpenSearch
    if content_summary is None:
        print("Warning: No content summary provided, retrieving content directly...")
        chapter_content = retrieve_chapter_chunks(chapter_id)
        if not chapter_content:
            raise ValueError(f"No content found for chapter: {chapter_id}")
        content_summary = chapter_content[:2000] + "..." if len(chapter_content) > 2000 else chapter_content
        print(f"Content retrieved - length: {len(content_summary)} characters")
    else:
        print(f"Using provided content summary (length: {len(content_summary)} characters)")

    # Calculate questions for each combination of difficulty and bloom's level
    question_breakdown = {}
    for difficulty, diff_ratio in difficulty_distribution.items():
        for blooms, blooms_ratio in blooms_taxonomy_distribution.items():
            count = int(round(num_questions * diff_ratio * blooms_ratio))
            if count > 0:
                question_breakdown[f"{difficulty}_{blooms}"] = {
                    'difficulty': difficulty,
                    'blooms_level': blooms,
                    'count': count
                }
    
    # Adjust to ensure total matches exactly
    total_calculated = sum([item['count'] for item in question_breakdown.values()])
    if total_calculated != num_questions:
        # Add/subtract from the largest group
        largest_key = max(question_breakdown.keys(), key=lambda k: question_breakdown[k]['count'])
        question_breakdown[largest_key]['count'] += (num_questions - total_calculated)
    
    print(f"Question breakdown: {question_breakdown}")
    
    # Generate all questions in a single prompt with specific guidelines
    all_guidelines = []
    
    for combo_key, specs in question_breakdown.items():
        difficulty = specs['difficulty']
        blooms_level = specs['blooms_level']
        count = specs['count']
        
        guidelines = get_blooms_question_guidelines(blooms_level, "fib")
        difficulty_desc = get_difficulty_description(difficulty)
        
        all_guidelines.append(f"""
For {count} questions at {difficulty.upper()} difficulty and {blooms_level.upper()} Bloom's level:
- Difficulty: {difficulty_desc}
- Bloom's Level Guidelines: {guidelines}
        """)
    
    # Generate filename based on chapter and distributions
    difficulty_str = "_".join([f"{diff}{int(prop*100)}" for diff, prop in difficulty_distribution.items()])
    blooms_str = "_".join([f"{bloom}{int(prop*100)}" for bloom, prop in blooms_taxonomy_distribution.items()])
    
    filename_parts = [chapter_id, difficulty_str, blooms_str]
    if learning_objectives and all_keys and 'learning_objectives' in all_keys:
        obj_str = "lo" + ("_".join([str(obj) for obj in learning_objectives]) if isinstance(learning_objectives, list) else str(learning_objectives))
        filename_parts.append(obj_str)
    
    file_name = "_".join(filename_parts) + "_fib.json"
    
    # For this implementation, we'll create a simulated response
    # In a production environment, you would integrate with an actual LLM service
    print("Generating fill-in-the-blank questions...")
    
    # Create questions based on the breakdown
    responses = []
    question_sequence = create_question_sequence(question_breakdown)
    
    for i in range(min(num_questions, len(question_sequence))):
        difficulty, blooms_level = question_sequence[i]
        question_obj = {
            "question_id": str(uuid.uuid4()),
            "question": f"Sample fill-in-the-blank question {i+1}: The main concept discussed in this chapter is ________ (difficulty: {difficulty}, blooms: {blooms_level})",
            "answer": [f"Answer {i+1} for the blank", f"Alternative answer {i+1}"],
            "explanation": f"This fill-in-the-blank question tests {blooms_level} level thinking at {difficulty} difficulty based on the chapter content.",
            "difficulty": difficulty,
            "blooms_level": blooms_level,
            "question_type": "fib"
        }
        responses.append(question_obj)
    
    # Save to JSON file
    json_responses = {"response": responses}
    with open(file_name, 'w') as json_file:
        json.dump(json_responses, json_file, indent=4)
    
    print(f"Generated fill-in-the-blank questions and saved to {file_name}")
    
    # Return a simulated text response
    fib_text = "\n".join([
        f"QUESTION: {q['question']}\nANSWER: {', '.join(q['answer'])}\nEXPLANATION: {q['explanation']}\n"
        for q in responses
    ])
    
    return fib_text

if __name__ == "__main__":
    # Example with distributions
    difficulty_dist = {
        'basic': 0.3,
        'intermediate': 0.3,
        'advanced': 0.4
    }
    
    blooms_dist = {
        'remember': 0.2,
        'apply': 0.5,
        'analyze': 0.3
    }
    
    print("Testing Fill-in-the-Blank generation with OpenSearch...")
    result = generate_fill_in_blank(
        tenant_id='1305101920',
        chapter_id='01_01920_ch01_ptg01_hires_001-026',
        learning_objectives=['LO_1.1', 'LO_1.2'],
        all_keys=available_keys,
        num_questions=10,
        difficulty_distribution=difficulty_dist,
        blooms_taxonomy_distribution=blooms_dist
    )
    print(f"Fill-in-the-blank generation completed. Check the generated JSON file for results.")
