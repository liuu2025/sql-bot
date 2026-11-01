"""Extract visible text from OpenAI/LangChain probe chunks without SDK coupling."""

from typing import Any


def chunk_text(chunk: Any) -> str:
    if isinstance(chunk, str):
        return chunk
    content = (
        chunk.get("content")
        if isinstance(chunk, dict)
        else getattr(chunk, "content", None)
    )
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            item.get("text", "")
            for item in content
            if isinstance(item, dict) and isinstance(item.get("text"), str)
        )
    return ""
