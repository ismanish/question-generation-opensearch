"""
Application constants.
"""
# Question types
QUESTION_TYPE_MCQ = "mcq"
QUESTION_TYPE_FIB = "fib"
QUESTION_TYPE_TF = "tf"

# Difficulty levels
DIFFICULTY_BASIC = "basic"
DIFFICULTY_INTERMEDIATE = "intermediate"
DIFFICULTY_ADVANCED = "advanced"

# Default values
DEFAULT_TENANT_ID = "1305101920"
DEFAULT_FILTER_KEY = "toc_level_1_title"
DEFAULT_FILTER_VALUE = "01_01920_ch01_ptg01_hires_001-026"
DEFAULT_NUM_QUESTIONS = 10
DEFAULT_DIFFICULTY = {DIFFICULTY_ADVANCED: 1.0}

# DynamoDB table name
DYNAMODB_TABLE_NAME = "question_generation_history"

# Prompt templates
CENGAGE_GUIDELINES = """
You are an educational assessment expert creating questions and quizzes for Cengage digital products. Follow these guidelines:

OBJECTIVES AND QUALITY:
- Each question must directly support at least one measurable learning objective
- Match question difficulty to the objective's Bloom's Taxonomy level
- Ensure content is error-free: correct answers, terminology, factual accuracy
- Use standard American English following Merriam-Webster's Collegiate Dictionary (11th Ed) and Chicago Manual of Style (16th Ed)

QUESTION STEMS:
- Make stems meaningful standalone, presenting a definite problem
- Ensure readability outside the section context
- Remove irrelevant material from stems
- Use negative statements only when learning objectives require it
- Format as questions or partial sentences (avoid initial/interior blanks)
- Match the core text's terminology and tone

ANSWER OPTIONS:
- Create strong distractors reflecting common misconceptions
- All options must be of same type/category and similar length
- NEVER use "all/none of the above" or "both a and b" options
- Ensure grammatical consistency with the stem
- Avoid repeating key words from the stem in the correct answer
- Avoid absolute determiners (All, Always, Never) in incorrect options
- Ensure distractors are unequivocally wrong with no debate possibility

HIGHER-ORDER THINKING:
- Analysis questions: inference, cause/effect, conclusions, comparisons
- Evaluation questions: judgment, advantages/limitations, hypothesizing
- Provide sufficient context or scenarios for complex questions

INCLUSIVITY AND ACCESSIBILITY:
- Use diverse names reflecting student diversity
- Avoid content reinforcing stereotypes or revealing biases
- Consider varied social/cultural experiences of students
- Ensure equivalent experience for students with disabilities

CRITICAL REQUIREMENTS:
- Never create subjective questions without definitive correct answers
- Each question must stand independently (no references to other questions)
- Questions must be answerable based solely on provided content
- Include feedback explaining why correct/incorrect answers are right/wrong
- Review for grammar, spelling, factual accuracy before submission

For each question, tag all applicable learning objectives and ensure the question provides valuable assessment that genuinely measures student understanding.
"""

# Metadata keys for OpenSearch (updated for new approach)
metadata_keys = {
    "source": None,
    "source.metadata": None,
    "source.metadata.file_title": None,
    "source.metadata.pdf_page_number": None,
    "source.metadata.toc_level_1_title": "chapter",
    "source.metadata.toc_level_2_title": "section",
    "source.metadata.toc_level_3_title": "subsection",
    "source.metadata.toc_level_4_title": "paragraph",
    "source.metadata.toc_level_5_title": "subparagraph",
    "source.metadata.toc_page_number": None,    
    "source.metadata.toc_section_hierarchy": None,
    "source.metadata.total_pages": None,
    "source.sourceId": None,
    "topics": None,
    "topics.statements": None,
    "topics.statements.chunkId": None,
    "topics.statements.details": None,
    "topics.statements.facts": None,
    "topics.statements.score": None,
    "topics.statements.statement": None,
    "topics.statements.statementId": None,
    "topics.statements.statement_str": None,
    "topics.topic": "topic",
}

# Content to tenant mapping (kept for compatibility)
content_tenant_mapping = {
    "9781305101920_p10_lores.pdf": "1305101920",
}

# OpenSearch Configuration
OPENSEARCH_CONFIG = {
    "HOST": "https://64asp87vin20xc5bhvbf.us-east-1.aoss.amazonaws.com",
    "REGION": "us-east-1",
    "INDEX_NAME": "chunk_357973585",
    "AWS_PROFILE_NAME": "cengage"
}

# Chapter key detection
CHAPTER_KEYS = ["toc_level_1_title", "toc_level_2_title"]
