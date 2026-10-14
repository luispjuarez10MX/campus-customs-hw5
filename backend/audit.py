"""Append-only audit trail of every agent-loop step, in output/audit_trail.json."""

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic_ai import Agent
from pydantic_ai.messages import (
    RetryPromptPart,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)

from backend.config import AUDIT_TEXT_LIMIT

_lock = threading.Lock()


def _clip(value: Any) -> Any:
    text = value if isinstance(value, str) else json.dumps(value, default=str)
    if len(text) <= AUDIT_TEXT_LIMIT:
        return value
    return text[:AUDIT_TEXT_LIMIT] + f"... [clipped {len(text) - AUDIT_TEXT_LIMIT} chars]"


class AuditTrail:
    """The file is a JSON list. Each append re-reads it, so earlier runs are kept."""

    def __init__(self, path: Path):
        self.path = path

    def append(self, entry: dict[str, Any]) -> None:
        entry = {"logged_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), **entry}
        with _lock:
            steps = json.loads(self.path.read_text()) if self.path.exists() else []
            steps.append(entry)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(steps, indent=2, default=str))
            os.replace(tmp, self.path)


def describe_node(node: Any) -> dict[str, Any]:
    """Turn one agent-graph node into a readable audit record."""
    if Agent.is_user_prompt_node(node):
        return {"step_type": "user_prompt", "prompt": _clip(node.user_prompt)}

    if Agent.is_model_request_node(node):
        # What is sent to the model: the task, tool results, or retry notices.
        parts = []
        for part in node.request.parts:
            if isinstance(part, UserPromptPart):
                parts.append({"user_prompt": _clip(part.content)})
            elif isinstance(part, ToolReturnPart):
                parts.append({"tool_result": part.tool_name, "call_id": part.tool_call_id, "content": _clip(part.content)})
            elif isinstance(part, RetryPromptPart):
                parts.append({"retry": part.tool_name, "content": _clip(part.content)})
        return {"step_type": "model_request", "sent_to_model": parts}

    if Agent.is_call_tools_node(node):
        # What the model answered: text and the tool calls it wants to make.
        response = node.model_response
        parts = []
        for part in response.parts:
            if isinstance(part, TextPart) and part.content.strip():
                parts.append({"text": _clip(part.content)})
            elif isinstance(part, ToolCallPart):
                parts.append({"tool_call": part.tool_name, "call_id": part.tool_call_id, "args": _clip(part.args_as_dict())})
        return {
            "step_type": "model_response",
            "model": response.model_name,
            "model_output": parts,
            "usage": {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            },
        }

    if Agent.is_end_node(node):
        output = node.data.output
        return {"step_type": "end", "output": _clip(output.model_dump() if hasattr(output, "model_dump") else output)}

    return {"step_type": type(node).__name__}
