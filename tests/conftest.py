import json
from pathlib import Path

import pytest
from mcp import types


@pytest.fixture
def anyio_backend():
    return "asyncio"


def read_audit(directory: Path) -> list[dict]:
    lines = []
    for path in sorted(directory.glob("audit-*.jsonl")):
        lines += [json.loads(line) for line in path.read_text().splitlines()]
    return lines


def elicitation(answer: str, confirm: bool = True):
    """Callback client : l'humain accepte (oui/non) ou refuse la fenetre de confirmation."""
    asked: list[str] = []

    async def callback(context, params):
        asked.append(params.message)
        if answer == "accept":
            return types.ElicitResult(action="accept", content={"confirm": confirm})
        return types.ElicitResult(action=answer)

    callback.asked = asked
    return callback


def text_of(result) -> str:
    return " ".join(getattr(c, "text", "") for c in result.content)
