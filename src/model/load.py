import os

from strands.models import BedrockModel

MODEL_ID = os.environ.get("MODEL_ID", "us.amazon.nova-pro-v1:0")


def load_model() -> BedrockModel:
    """
    Get Bedrock model client.
    Uses IAM authentication via the execution role.
    """
    return BedrockModel(model_id=MODEL_ID)


def load_model_id() -> str:
    return MODEL_ID
