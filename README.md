# Question Generation API - OpenSearch Serverless

This is an updated version of the question generation API that uses **OpenSearch Serverless** instead of the GraphRAG toolkit for content retrieval and processing.

## 🚀 Key Changes from Original

### Architecture Migration
- **FROM**: GraphRAG toolkit with Neptune + Vector Store
- **TO**: Direct OpenSearch Serverless integration
- **Benefits**: Simplified architecture, improved performance, reduced dependencies

### Core Updates

1. **Content Retrieval**: 
   - Replaced GraphRAG's complex retrieval system with direct OpenSearch queries
   - Simplified chapter-based content filtering
   - Maintained compatibility with existing chapter ID structure

2. **Dependencies**:
   - Removed GraphRAG toolkit dependency
   - Added `opensearch-py` for direct OpenSearch integration
   - Significantly reduced package size and complexity

3. **Configuration**:
   - New OpenSearch Serverless configuration
   - Updated AWS authentication using AWSV4SignerAuth
   - Simplified connection management

## 📋 Prerequisites

- Python 3.10+
- AWS Account with OpenSearch Serverless access
- AWS CLI configured with appropriate credentials
- AWS Profile named 'cengage' (or update configuration)

## 🛠 Installation

```bash
# Clone the repository
git clone https://github.com/ismanish/question-generation-opensearch.git
cd question-generation-opensearch

# Install dependencies
pip install -r requirements.txt

# Or using virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## ⚙️ Configuration

### OpenSearch Serverless Setup

Update the configuration in `src/utils/constants.py`:

```python
OPENSEARCH_CONFIG = {
    "HOST": "https://your-opensearch-endpoint.region.aoss.amazonaws.com",
    "REGION": "us-east-1",
    "INDEX_NAME": "your_index_name",
    "AWS_PROFILE_NAME": "your_profile"
}
```

### AWS Configuration

Ensure your AWS credentials are configured:

```bash
aws configure --profile cengage
# or
export AWS_PROFILE=cengage
export AWS_REGION=us-east-1
```

## 🚀 Running the API

### Development Mode

```bash
# From the main directory
cd main
python app.py

# Or using uvicorn directly
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

### Docker (Optional)

```bash
# Build the Docker image
docker build -t question-generation-opensearch .

# Run the container
docker run -p 8000:8000 \
  -v ~/.aws:/root/.aws \
  -e AWS_PROFILE=cengage \
  -e AWS_REGION=us-east-1 \
  question-generation-opensearch
```

## 📡 API Usage

### Generate Questions Endpoint

```http
POST /questionBankService/source/{sourceId}/questions/generate
```

### Example Request

```json
{
  "contentId": "9781305101920_p10_lores.pdf",
  "chapter_id": "01_01920_ch01_ptg01_hires_001-026",
  "learning_objectives": ["LO_1.1", "LO_1.2"],
  "total_questions": 15,
  "question_type_distribution": {
    "mcq": 0.4,
    "fib": 0.3,
    "tf": 0.3
  },
  "difficulty_distribution": {
    "basic": 0.3,
    "intermediate": 0.3,
    "advanced": 0.4
  },
  "blooms_taxonomy_distribution": {
    "remember": 0.3,
    "apply": 0.4,
    "analyze": 0.3
  }
}
```

### Example Response

```json
{
  "status": "success",
  "message": "✅ Generated 15 questions across 3 question types...",
  "session_id": "uuid-here",
  "contentId": "9781305101920_p10_lores.pdf",
  "chapter_id": "01_01920_ch01_ptg01_hires_001-026",
  "total_questions": 15,
  "files_generated": ["chapter_basic30_intermediate30_advanced40_mcqs.json"],
  "data": {
    "mcq": {
      "response": [...]
    }
  }
}
```

## 🏗 Architecture Overview

### New OpenSearch Integration

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   FastAPI App   │───▶│  OpenSearch     │───▶│   Question      │
│                 │    │  Serverless     │    │   Generators    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   DynamoDB      │    │   Chapter       │    │   JSON Files    │
│   Logging       │    │   Content       │    │   Output        │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### Key Components

1. **OpenSearch Client**: Direct integration with AWS OpenSearch Serverless
2. **Content Retrieval**: Chapter-based content fetching using metadata filters
3. **Question Generation**: Parallel processing of different question types
4. **Summary Generation**: Shared content summarization across question types

## 🔧 Key Functions

### Content Retrieval
- `retrieve_chapter_chunks()`: Fetches content from OpenSearch
- `create_query_body()`: Builds OpenSearch queries
- `execute_search()`: Executes queries and processes results

### Question Generation
- `generate_mcqs()`: Multiple choice questions
- `generate_true_false()`: True/false questions  
- `generate_fill_in_blank()`: Fill-in-the-blank questions

### Processing
- `generate_content_summary_sync()`: Generates content summaries
- `calculate_question_distribution()`: Distributes questions across types/difficulties

## ⚡ Performance Optimizations

1. **Shared Summary Generation**: Summary created once and reused across question types
2. **Parallel Processing**: True parallel execution using ThreadPoolExecutor
3. **Direct OpenSearch Access**: Eliminates GraphRAG overhead
4. **Efficient Filtering**: Optimized metadata-based content filtering

## 🔒 Security Considerations

- AWS credentials managed through AWS SDK
- DynamoDB access for logging and session management
- CORS configuration for web access
- Input validation and error handling

## 🐛 Troubleshooting

### Common Issues

1. **OpenSearch Connection Issues**:
   ```bash
   # Check AWS credentials
   aws sts get-caller-identity --profile cengage
   ```

2. **Missing Index**:
   - Verify the index name in constants.py
   - Ensure the index exists in your OpenSearch cluster

3. **Authentication Errors**:
   - Verify AWS profile configuration
   - Check IAM permissions for OpenSearch access

## 📝 Development Notes

### Current Limitations

1. **LLM Integration**: The current implementation includes placeholder LLM responses. In production, integrate with your preferred LLM service (Claude, GPT, etc.)

2. **Question Quality**: The sample questions are for demonstration. Real implementation should generate contextually relevant questions based on content.

3. **Error Handling**: Additional error handling may be needed for production environments.

### Future Enhancements

1. **LLM Integration**: Add real LLM service integration for question generation
2. **Caching**: Implement content caching for improved performance
3. **Batch Processing**: Support for batch question generation
4. **Question Validation**: Add automated question quality validation

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project maintains the same license as the original codebase.

## 🆘 Support

For issues and questions:
1. Check the troubleshooting section
2. Review the configuration settings
3. Create an issue in the GitHub repository

---

**Migration Summary**: This version successfully migrates from GraphRAG to OpenSearch Serverless while maintaining API compatibility and improving performance through simplified architecture and direct OpenSearch integration.
