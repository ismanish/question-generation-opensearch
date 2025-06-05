"""
Shared summary generation helper for question generators using OpenSearch Serverless.
This module centralizes the summary generation logic to avoid duplication.
"""
import os
import sys
import boto3
# Add project root to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Import settings first to set environment variables
from src import settings
from opensearch_py import OpenSearch, RequestsHttpConnection
from opensearch_py.connection.http_auth import AWSV4SignerAuth
from llama_index.core.vector_stores.types import (
    MetadataFilter,
    FilterOperator
)
from src.utils.constants import CENGAGE_GUIDELINES as cengage_guidelines

# OpenSearch Configuration
HOST = "https://64asp87vin20xc5bhvbf.us-east-1.aoss.amazonaws.com"
REGION = 'us-east-1'
INDEX_NAME = 'chunk_357973585'
AWS_PROFILE_NAME = 'cengage'

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
    Args:
        chapter_name (str): The name of the chapter to retrieve.
        max_chunks (int): Maximum number of chunks to retrieve.
        max_chars (int): Maximum total characters to include in content.
    Returns:
        str: The content of the chapter, limited to max_chars.
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

def generate_content_summary_sync(
    tenant_id: str, 
    chapter_id: str,
    learning_objectives=None,
    all_keys=None
) -> str:
    """
    Synchronous version of content summary generation using OpenSearch Serverless.
    
    Args:
        tenant_id: The tenant ID (kept for compatibility, not used in new approach)
        chapter_id: The chapter identifier (e.g., '56330_ch10_ptg01') 
        learning_objectives: Optional. Learning objectives (not used in current implementation)
        all_keys: List of all available metadata keys (not used in current implementation)
        
    Returns:
        str: Content summary
    """
    print(f"Generating shared content summary (sync) for chapter: {chapter_id}")
    if learning_objectives:
        print(f"Learning objectives filter: {learning_objectives}")
    
    # Use new retrieval method
    try:
        chapter_content = retrieve_chapter_chunks(chapter_id)
        
        if not chapter_content:
            print("No content retrieved for the chapter")
            return "No content available for the specified chapter."
        
        # Generate a simple summary from the retrieved content
        # For now, we'll return the first part of the content as summary
        # In a production environment, you might want to use an LLM to generate a proper summary
        summary_length = min(2000, len(chapter_content))
        content_summary = chapter_content[:summary_length]
        
        if len(chapter_content) > summary_length:
            content_summary += "\n[Summary truncated - full content available for question generation]"
        
        print(f"Summary generated - length: {len(content_summary)} characters")
        return content_summary
        
    except Exception as e:
        print(f"Error generating summary: {str(e)}")
        return f"Error retrieving content for chapter {chapter_id}: {str(e)}"
