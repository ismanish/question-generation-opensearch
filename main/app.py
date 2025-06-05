import sys
import os
import uuid
import json
import datetime
import boto3
import math
import asyncio
import concurrent.futures
from typing import Optional, Dict, List, Union
from fastapi import FastAPI, Query, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from enum import Enum
from fastapi.responses import JSONResponse

# Add the project root directory to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import settings to configure environment variables first
from src import settings

# Import question generation functions - UPDATED VERSION
from src.utils.helpers import get_difficulty_description

# Import the NEW shared summary helper
from src.utils.summary_helper import generate_content_summary_sync

# Import metadata keys for available_keys
from src.utils.constants import metadata_keys, content_tenant_mapping

# Initialize DynamoDB client
dynamodb = boto3.resource(
    'dynamodb',
    region_name=os.environ.get('AWS_REGION', 'us-east-1'),
    aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY')
)

# Get the DynamoDB tables
table_names = {
    'history': 'question_generation_history',
    'conversation': 'conversation',
    'events': 'events'
}

tables = {}
try:
    for key, table_name in table_names.items():
        tables[key] = dynamodb.Table(table_name)
        # Test if table exists by performing a small operation
        tables[key].scan(Limit=1)
        print(f"Successfully connected to DynamoDB table: {table_name}")
except Exception as e:
    print(f"Warning: DynamoDB table access error - {str(e)}")
    print("Will log to console instead of DynamoDB")
    tables = {key: None for key in table_names.keys()}

app = FastAPI(
    title="Question Generation API - OpenSearch",
    description="API for generating different types of questions using OpenSearch Serverless with async processing and shared summary generation",
    version="3.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

class QuestionType(str, Enum):
    mcq = "mcq"
    tf = "tf"
    fib = "fib"

class BloomsTaxonomy(str, Enum):
    remember = "remember"
    apply = "apply"
    analyze = "analyze"

class DifficultyLevel(str, Enum):
    basic = "basic"
    intermediate = "intermediate"
    advanced = "advanced"

class QuestionRequest(BaseModel):
    contentId: str = "9781305101920_p10_lores.pdf"
    chapter_id: str = "01_01920_ch01_ptg01_hires_001-026"
    learning_objectives: Optional[Union[str, List[str]]] = None
    total_questions: int = 10
    question_type_distribution: Dict[str, float] = {"mcq": 0.4, "fib": 0.3, "tf": 0.3}
    difficulty_distribution: Dict[str, float] = {"basic": 0.3, "intermediate": 0.3, "advanced": 0.4}
    blooms_taxonomy_distribution: Dict[str, float] = {"remember": 0.3, "apply": 0.4, "analyze": 0.3}
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique session identifier")

class QuestionResponse(BaseModel):
    status: str
    message: str
    session_id: str             
    contentId: str                   
    chapter_id: str                    
    learning_objectives: Optional[Union[str, List[str]]]
    total_questions: int              
    question_type_distribution: Dict[str, float]  
    difficulty_distribution: Dict[str, float]     
    blooms_taxonomy_distribution: Dict[str, float]  
    files_generated: list
    data: dict

def calculate_question_distribution(total_questions: int, question_type_dist: Dict[str, float], 
                                  difficulty_dist: Dict[str, float], blooms_dist: Dict[str, float]):
    """
    Calculate the exact number of questions for each combination of question type, difficulty, and bloom's level
    """
    # First, calculate exact fractional counts for all combinations
    fractional_distribution = {}
    
    for q_type, q_ratio in question_type_dist.items():
        for difficulty, d_ratio in difficulty_dist.items():
            for blooms, b_ratio in blooms_dist.items():
                exact_count = total_questions * q_ratio * d_ratio * b_ratio
                key = f"{q_type}_{difficulty}_{blooms}"
                fractional_distribution[key] = {
                    'question_type': q_type,
                    'difficulty': difficulty,
                    'blooms_level': blooms,
                    'exact_count': exact_count,
                    'count': int(exact_count)  # Floor value
                }
    
    # Calculate remainder needed to reach total_questions
    current_total = sum([item['count'] for item in fractional_distribution.values()])
    remainder = total_questions - current_total
    
    # Sort by fractional part (descending) to allocate remainder
    sorted_keys = sorted(
        fractional_distribution.keys(),
        key=lambda k: fractional_distribution[k]['exact_count'] - fractional_distribution[k]['count'],
        reverse=True
    )
    
    # Distribute remainder to items with highest fractional parts
    for i in range(remainder):
        if i < len(sorted_keys):
            fractional_distribution[sorted_keys[i]]['count'] += 1
    
    # Remove items with zero count and clean up the structure
    distribution = {}
    for key, item in fractional_distribution.items():
        if item['count'] > 0:
            distribution[key] = {
                'question_type': item['question_type'],
                'difficulty': item['difficulty'],
                'blooms_level': item['blooms_level'],
                'count': item['count']
            }
    
    return distribution

def generate_single_question_type_sync(question_type: str, configs: list, content_summary: str, 
                                      tenant_id: str, chapter_id: str, learning_objectives: Optional[Union[str, List[str]]],
                                      difficulty_distribution: Dict[str, float], 
                                      blooms_distribution: Dict[str, float]) -> tuple:
    """
    Synchronous function for generating a single question type using shared summary.
    This function will be run in parallel using ThreadPoolExecutor.
    """
    try:
        # Import functions inside the function to avoid import issues
        from src.utils.utils_mcq import generate_mcqs
        from src.utils.utils_fib import generate_fill_in_blank  
        from src.utils.utils_tf import generate_true_false
        
        # Get available keys
        available_keys = list(set(metadata_keys.keys()))
        
        # Aggregate counts for this question type
        total_for_type = sum([config['count'] for config in configs])
        
        print(f"[THREAD] Generating {question_type} questions (count: {total_for_type})...")
        
        # Generate questions based on type using the UPDATED functions with shared summary
        if question_type == "mcq":
            question_text = generate_mcqs(
                tenant_id=tenant_id,
                chapter_id=chapter_id,
                learning_objectives=learning_objectives,
                all_keys=available_keys,
                num_questions=total_for_type,
                difficulty_distribution=difficulty_distribution,
                blooms_taxonomy_distribution=blooms_distribution,
                content_summary=content_summary
            )
        elif question_type == "fib":
            question_text = generate_fill_in_blank(
                tenant_id=tenant_id,
                chapter_id=chapter_id,
                learning_objectives=learning_objectives,
                all_keys=available_keys,
                num_questions=total_for_type,
                difficulty_distribution=difficulty_distribution,
                blooms_taxonomy_distribution=blooms_distribution,
                content_summary=content_summary
            )
        elif question_type == "tf":
            question_text = generate_true_false(
                tenant_id=tenant_id,
                chapter_id=chapter_id,
                learning_objectives=learning_objectives,
                all_keys=available_keys,
                num_questions=total_for_type,
                difficulty_distribution=difficulty_distribution,
                blooms_taxonomy_distribution=blooms_distribution,
                content_summary=content_summary
            )
        
        # Generate filename exactly as the utility functions do
        difficulty_str = "_".join([f"{diff}{int(prop*100)}" for diff, prop in difficulty_distribution.items()])
        blooms_str = "_".join([f"{bloom}{int(prop*100)}" for bloom, prop in blooms_distribution.items()])
        
        filename_parts = [chapter_id, difficulty_str, blooms_str]
        if learning_objectives and available_keys and 'learning_objectives' in available_keys:
            obj_str = "lo" + ("_".join([str(obj) for obj in learning_objectives]) if isinstance(learning_objectives, list) else str(learning_objectives))
            filename_parts.append(obj_str)
        
        if question_type == "mcq":
            file_name = "_".join(filename_parts) + "_mcqs.json"
        elif question_type == "fib":
            file_name = "_".join(filename_parts) + "_fib.json"
        elif question_type == "tf":
            file_name = "_".join(filename_parts) + "_tf.json"
        
        # Read the generated JSON file
        with open(file_name, 'r') as json_file:
            question_data = json.load(json_file)
        
        print(f"[THREAD] Completed generating {question_type} questions")
        return question_type, file_name, question_data, None
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"[THREAD] Error generating {question_type} questions: {str(e)}")
        print(f"[THREAD] Full error details: {error_details}")
        return question_type, None, None, str(e)

@app.get("/")
def read_root():
    return {"message": "Question Generation API v3.0 - OpenSearch. Use /questionBankService/source/{sourceId}/questions/generate endpoint to create questions with OpenSearch Serverless."}

def generate_session_id():
    """Generate a unique session ID"""
    return str(uuid.uuid4())

@app.post("/questionBankService/source/{sourceId}/questions/generate", response_model=QuestionResponse)
async def generate_questions(sourceId: str, request: QuestionRequest, req: Request):
    """
    Generate questions based on the specified parameters using OpenSearch Serverless.
    
    Key Features:
    1. Summary generated only ONCE and shared across all question types
    2. Question generators run in TRUE PARALLEL using ThreadPoolExecutor
    3. Uses OpenSearch Serverless instead of GraphRAG
    4. Enhanced filtering with learning objectives support
    
    - **sourceId**: Source identifier (e.g., 'dev_app')
    - **contentId**: Content ID to map to tenant (kept for compatibility)
    - **chapter_id**: The chapter identifier (e.g., '01_01920_ch01_ptg01_hires_001-026')
    - **learning_objectives**: Optional learning objectives to filter on (single string or list of strings)
    - **total_questions**: Total number of questions to generate
    - **question_type_distribution**: Distribution of question types (mcq, fib, tf)
    - **difficulty_distribution**: Distribution of difficulty levels (basic, intermediate, advanced)
    - **blooms_taxonomy_distribution**: Distribution of Bloom's levels (remember, apply, analyze)
    - **session_id**: Unique session identifier for tracking this request
    """
    # Generate timestamp for the request
    request_timestamp = datetime.datetime.utcnow().isoformat()
    status = "success"
    error_message = ""
    all_question_data = {}
    files_generated = []
    
    # Handle session_id - use from request if provided, otherwise generate a new one
    session_id = request.session_id if request.session_id else generate_session_id()
    
    # For OpenSearch approach, tenant_id is less relevant but kept for compatibility
    tenant_id = content_tenant_mapping.get(request.contentId, "default")
    
    # Log the conversation in DynamoDB
    try:
        log_conversation(sourceId, session_id, request, request_timestamp, request.contentId, tenant_id)
    except Exception as e:
        print(f"Error logging conversation: {str(e)}")
    
    print(f"Processing OpenSearch request for sourceId: {sourceId}")
    print(f"Request parameters: {request.dict()}")
    available_keys = list(set(metadata_keys.keys()))
    
    try:
        # OPTIMIZATION 1: Generate shared summary ONCE using OpenSearch
        print("🚀 OPTIMIZATION: Generating shared content summary once using OpenSearch...")
        start_time = datetime.datetime.utcnow()
        
        # Generate the summary once using the shared helper with OpenSearch
        content_summary = generate_content_summary_sync(
            tenant_id=tenant_id,
            chapter_id=request.chapter_id,
            learning_objectives=request.learning_objectives,
            all_keys=available_keys
        )   
        
        summary_time = (datetime.datetime.utcnow() - start_time).total_seconds()
        print(f"✅ Shared summary generated in {summary_time:.2f} seconds (length: {len(content_summary)} characters)")
        
        # Calculate question distribution
        question_dist = calculate_question_distribution(
            request.total_questions,
            request.question_type_distribution,
            request.difficulty_distribution,
            request.blooms_taxonomy_distribution
        )
        
        print(f"Question distribution: {question_dist}")
        
        # Group by question type for generation
        type_groups = {}
        for key, config in question_dist.items():
            q_type = config['question_type']
            if q_type not in type_groups:
                type_groups[q_type] = []
            type_groups[q_type].append(config)
        
        # OPTIMIZATION 2: Run question generators in TRUE PARALLEL using ThreadPoolExecutor
        print("🚀 OPTIMIZATION: Running question generators in TRUE PARALLEL using threads...")
        parallel_start_time = datetime.datetime.utcnow()
        
        # Create thread pool and submit tasks
        loop = asyncio.get_event_loop()
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            # Create futures for each question type
            futures = []
            
            for question_type, configs in type_groups.items():
                # Create combined distributions for this question type
                total_for_type = sum([config['count'] for config in configs])
                difficulty_dist_for_type = {}
                blooms_dist_for_type = {}
                
                for config in configs:
                    diff = config['difficulty']
                    blooms = config['blooms_level']
                    count = config['count']
                    
                    if diff not in difficulty_dist_for_type:
                        difficulty_dist_for_type[diff] = 0
                    if blooms not in blooms_dist_for_type:
                        blooms_dist_for_type[blooms] = 0
                        
                    difficulty_dist_for_type[diff] += count / total_for_type
                    blooms_dist_for_type[blooms] += count / total_for_type
                
                # Submit task to thread pool
                future = loop.run_in_executor(
                    executor,
                    generate_single_question_type_sync,
                    question_type,
                    configs,
                    content_summary,  # Pass shared summary
                    tenant_id,
                    request.chapter_id,
                    request.learning_objectives,
                    difficulty_dist_for_type,
                    blooms_dist_for_type
                )
                futures.append(future)
            
            # Wait for all futures to complete - THIS IS TRUE PARALLEL EXECUTION
            print(f"⚡ Running {len(futures)} question generators in parallel threads...")
            results = await asyncio.gather(*futures, return_exceptions=True)
        
        parallel_time = (datetime.datetime.utcnow() - parallel_start_time).total_seconds()
        print(f"✅ TRUE parallel question generation completed in {parallel_time:.2f} seconds")
        
        # Process results
        for result in results:
            if isinstance(result, Exception):
                raise result
            
            question_type, file_name, question_data, error = result
            
            if error:
                raise Exception(f"Error in {question_type}: {error}")
            
            files_generated.append(file_name)
            all_question_data[question_type] = question_data
        
        total_time = (datetime.datetime.utcnow() - start_time).total_seconds()
        
        learning_obj_str = f" with learning objectives: {request.learning_objectives}" if request.learning_objectives else ""
        
        response = QuestionResponse(
            status=status,
            message=f"✅ Generated {request.total_questions} questions across {len(type_groups)} question types for sourceId: {sourceId}, chapter: {request.chapter_id}{learning_obj_str} in {total_time:.2f} seconds using OpenSearch (Summary: {summary_time:.2f}s, TRUE Parallel Generation: {parallel_time:.2f}s)",
            session_id=session_id,
            files_generated=files_generated,
            contentId=request.contentId,
            chapter_id=request.chapter_id,
            learning_objectives=request.learning_objectives,
            total_questions=request.total_questions,
            question_type_distribution=request.question_type_distribution,
            difficulty_distribution=request.difficulty_distribution,
            blooms_taxonomy_distribution=request.blooms_taxonomy_distribution,
            data=all_question_data
        )
        
    except Exception as e:
        import traceback
        error_message = str(e)
        error_details = traceback.format_exc()
        print(f"Full error details: {error_details}")
        status = "error"
        response = QuestionResponse(
            status=status,
            message=f"❌ Error generating questions for sourceId {sourceId}: {error_message}",
            session_id=session_id,
            contentId=request.contentId,
            chapter_id=request.chapter_id,
            learning_objectives=request.learning_objectives,
            total_questions=request.total_questions,
            question_type_distribution=request.question_type_distribution,
            difficulty_distribution=request.difficulty_distribution,
            blooms_taxonomy_distribution=request.blooms_taxonomy_distribution,
            files_generated=[],
            data={}
        )
        raise HTTPException(status_code=500, detail=f"Error generating questions: {error_message}")
    finally:
        # Store the request and response data in DynamoDB
        try:
            if tables['history'] is not None:
                # Create item to store in DynamoDB
                dynamo_item = {
                    'session_id': session_id,
                    'source_id': sourceId,
                    'request_timestamp': request_timestamp,
                    'contentId': request.contentId,
                    'chapter_id': request.chapter_id,
                    'learning_objectives': json.dumps(request.learning_objectives) if request.learning_objectives else None,
                    'total_questions': request.total_questions,
                    'question_type_distribution': json.dumps(request.question_type_distribution),
                    'difficulty_distribution': json.dumps(request.difficulty_distribution),
                    'blooms_taxonomy_distribution': json.dumps(request.blooms_taxonomy_distribution),
                    'files_generated': json.dumps(files_generated),
                    'status': status,
                    'error_message': error_message,
                    'response_data': json.dumps(all_question_data) if all_question_data else ""
                }
                
                # Put item in DynamoDB
                tables['history'].put_item(Item=dynamo_item)
                print(f"Request data saved to DynamoDB for session: {session_id}, sourceId: {sourceId}")
            else:
                # Log to console if DynamoDB is not available
                print(f"Request data (not saved to DynamoDB): sourceId={sourceId}, {request.dict()}")
        except Exception as db_error:
            print(f"Error saving to DynamoDB: {str(db_error)}")
    
    # If we got here without raising an exception, return the response
    if status == "success":
        # Log event for successful response and individual questions
        try:
            # Log overall response event
            response_timestamp = datetime.datetime.utcnow().isoformat()
            
            # Log main response event
            log_event(
                event_type="RESPONSE", 
                session_id=session_id, 
                source_id=sourceId, 
                status="success", 
                timestamp=response_timestamp,
                tenant_id=tenant_id,
                metadata={
                    'totalQuestions': request.total_questions,
                    'questionTypes': list(request.question_type_distribution.keys()),
                    'filesGenerated': files_generated
                }
            )
            
            # Log each question as a separate event in the events table
            for question_type, question_data in all_question_data.items():
                log_question_events(
                    session_id=session_id,
                    source_id=sourceId,
                    question_type=question_type,
                    question_data=question_data,
                    timestamp_base=response_timestamp,
                    tenant_id=tenant_id
                )
        except Exception as e:
            print(f"Error logging events: {str(e)}")
            
        return response

def log_conversation(source_id, session_id, request_data, timestamp, contentId, tenant_id):
    """Log conversation data to DynamoDB"""
    if tables['conversation'] is None:
        print(f"Conversation logging skipped - DynamoDB table not available")
        return
    
    try:
        # Create conversation item based on schema
        conversation_item = {
            'PK': session_id,  # Partition key
            'SK': timestamp,   # Sort key
            'contentId': contentId,
            'tenantId': tenant_id,
            'timeStamp': timestamp,
            'convSummary': json.dumps(request_data.dict()),
            'conversationName': f"Question Generation - {request_data.chapter_id}",
            'sourceId': source_id,
            'conversationID': session_id,
            'conversationType': "QUESTION_GENERATION",
            'status': "PROCESSING",
            'conversationInput': json.dumps(request_data.dict())
        }
        
        # Put item in DynamoDB
        tables['conversation'].put_item(Item=conversation_item)
        print(f"Conversation logged to DynamoDB for session: {session_id}")
    except Exception as e:
        print(f"Error logging conversation to DynamoDB: {str(e)}")

def log_event(event_type, session_id, source_id, status, timestamp, tenant_id, data=None, metadata=None):
    """Log event data to DynamoDB"""
    if tables['events'] is None:
        print(f"Event logging skipped - DynamoDB table not available")
        return
    
    try:
        # Create event item based on schema
        event_item = {
            'PK': session_id,  # Partition key
            'SK': timestamp,   # Sort key
            'event': event_type,
            'id': str(uuid.uuid4()),
            'sender': "SYSTEM",
            'tenantId': tenant_id,
            'timestamp': timestamp,
            'sourceID': source_id,
            'status': status,
            'conversationID': session_id
        }
        
        # Add optional data if provided
        if data:
            event_item['data'] = json.dumps(data)
            
        # Add any additional metadata if provided
        if metadata and isinstance(metadata, dict):
            for key, value in metadata.items():
                if key not in event_item:  # Don't overwrite existing fields
                    event_item[key] = value
        
        # Put item in DynamoDB
        tables['events'].put_item(Item=event_item)
        print(f"Event logged to DynamoDB for session: {session_id}, event: {event_type}")
    except Exception as e:
        print(f"Error logging event to DynamoDB: {str(e)}")

def log_question_events(session_id, source_id, question_type, question_data, timestamp_base, tenant_id):
    """Log each question as a separate event in the events table"""
    if not question_data or tables['events'] is None:
        return
    
    try:
        # Get questions from the correct path in the response structure
        questions = []
        if 'response' in question_data:
            questions = question_data['response']
        
        print(f"Logging {len(questions)} individual questions for {question_type}")
        
        for i, question in enumerate(questions):
            # Create a unique sort key for each question
            question_timestamp = f"{timestamp_base}_{question_type}_{i}"
            
            # Extract metadata from the question
            question_metadata = {
                'questionType': question_type,
                'questionIndex': i,
                'questionId': question.get('question_id', 'unknown'),
                'difficulty': question.get('difficulty', 'unknown'),
                'bloomsLevel': question.get('blooms_level', 'unknown')
            }
            
            # Log each question as a separate event
            log_event(
                event_type="QUESTION_GENERATED",
                session_id=session_id,
                source_id=source_id,
                status="success",
                timestamp=question_timestamp,
                tenant_id=tenant_id,
                data=question,
                metadata=question_metadata
            )
        
        print(f"Successfully logged {len(questions)} question events for {question_type}")
    except Exception as e:
        print(f"Error logging question events: {str(e)}")

@app.get("/health")
def health_check():
    return {"status": "healthy", "version": "3.0.0 - OpenSearch", "features": ["opensearch_serverless", "true_parallel_processing", "learning_objectives_support", "session_management"]}

# Run the FastAPI app with uvicorn if executed directly
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
