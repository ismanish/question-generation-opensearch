# This file is maintained for backward compatibility
# Additional environment-specific settings for OpenSearch integration

import os

# Explicitly set environment variables
os.environ["AWS_PROFILE"] = "cengage"
os.environ["AWS_REGION"] = "us-east-1"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"

# OpenSearch Configuration (updated for new approach)
OPENSEARCH_HOST = "https://64asp87vin20xc5bhvbf.us-east-1.aoss.amazonaws.com"
OPENSEARCH_REGION = "us-east-1"
OPENSEARCH_INDEX = "chunk_357973585"
OPENSEARCH_PROFILE = "cengage"

# Legacy endpoints (kept for reference but not used in new OpenSearch approach)
NeptuneEndpoint = "neptune-db://contentai-neptune-01-instance-1.crgki0ug6nab.us-east-1.neptune.amazonaws.com:8182"
VectorStoreEndpoint = "aoss://https://1tsv2alzp27po3fu3rmk.us-east-1.aoss.amazonaws.com"
