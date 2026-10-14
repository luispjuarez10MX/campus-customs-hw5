"""Paths, model, and run limits shared by the backend."""

import os
from pathlib import Path

from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic_ai.models.openai import OpenAIResponsesModel, OpenAIResponsesModelSettings
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.usage import UsageLimits

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Use the nearest .env: the project's own (for clones of the repo, copied from
# .env.example) or, in the course workspace, the shared course-root .env.
for folder in (PROJECT_ROOT, *PROJECT_ROOT.parents[:3]):
    if (folder / ".env").is_file():
        load_dotenv(folder / ".env")
        break

ORIGINAL_DB = PROJECT_ROOT / "data" / "campus_customs.db"
DB_PATH = Path(os.environ.get("CAMPUS_CUSTOMS_DB", PROJECT_ROOT / "data" / "campus_customs_new.db"))
AUDIT_TRAIL_PATH = Path(os.environ.get("AUDIT_TRAIL_PATH", PROJECT_ROOT / "output" / "audit_trail.json"))
MCP_SERVER_SCRIPT = PROJECT_ROOT / "mcp_server" / "server.py"
PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"

MODEL_NAME = "gpt-6-luna"

# Token guardrails. One budget is shared by the whole team for a run, because
# every delegated run reuses the caller's usage counter.
MODEL_SETTINGS = OpenAIResponsesModelSettings(
    max_tokens=2_000,
    openai_reasoning_effort="low",
)
USAGE_LIMITS = UsageLimits(
    request_limit=60,
    tool_calls_limit=80,
    total_tokens_limit=250_000,
)
MAX_DELEGATION_DEPTH = 3
MAX_DELEGATIONS_PER_RUN = 12
AUDIT_TEXT_LIMIT = 4_000


def build_model() -> OpenAIResponsesModel:
    """gpt-6-luna through Portkey. Uses the Responses API, because this model
    rejects function tools on /chat/completions."""
    key = os.environ["PORTKEY_API_KEY"]
    client = AsyncOpenAI(
        api_key=key,
        base_url="https://api.portkey.ai/v1",
        default_headers={"x-portkey-api-key": key},
    )
    return OpenAIResponsesModel(MODEL_NAME, provider=OpenAIProvider(openai_client=client))
