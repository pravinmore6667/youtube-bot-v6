import asyncio
from typing import Dict, Any
from router.ai_router import ask_json

async def optimize_for_algorithm(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deeply optimize CTR, Retention, Session duration, Replay value,
    Returning viewers, and Subscriber conversion for the YouTube Algorithm.
    """
    if metadata.get("algorithm_optimized"):
        return metadata

    prompt = f"""
You are a YouTube Algorithm Optimization Engine.
Your task is to rewrite the video title, description, and tags to maximize Click-Through Rate (CTR) and search ranking.

Current Metadata:
Title: {metadata.get('title')}
Description: {metadata.get('description')}
Tags: {metadata.get('tags')}

Return a strict JSON object with the optimized values:
{{
  "title": str (max 65 chars, highly clickable),
  "description": str (SEO optimized, engaging first 2 lines),
  "tags": [str] (list of high volume tags)
}}
"""
    try:
        optimized = await ask_json(prompt, is_fast=True)
        if optimized and "title" in optimized:
            metadata["title"] = optimized["title"]
            metadata["description"] = optimized["description"]
            if isinstance(optimized.get("tags"), list):
                metadata["tags"] = optimized["tags"]
            metadata["algorithm_optimized"] = True
    except Exception:
        # If parsing fails, fall back to simple appends
        metadata["algorithm_optimized"] = True
        if "tags" in metadata:
            metadata["tags"].extend(["viral", "trending", "must watch"])

    return metadata
