import asyncio
import json
from typing import Dict, Any, List
from router.ai_router import ask, ask_json
from utils.logger import get_logger

log = get_logger("CommunityAgent")

async def generate_community_post(topic: str) -> str:
    """
    Generate an engaging YouTube Community post to build hype for a new video.
    """
    prompt = f"""
You are a YouTube Community Manager. Write an engaging community tab post
(about 50-100 words) teasing an upcoming video about: "{topic}".
Ask a question at the end to drive engagement. Use emojis.
"""
    try:
        post = await ask(prompt, is_fast=True)
        log.success("Generated community post.")
        return post.strip()
    except Exception as e:
        log.warning(f"Failed to generate community post: {e}")
        return f"Hey everyone! We have a huge video coming up about {topic}. What do you think is the craziest part about it? Let us know below! 👇"

async def reply_to_comments(comments: List[str]) -> Dict[str, str]:
    """
    Analyze comments sentiment and generate AI replies for the top comments.
    """
    prompt = f"""
You are managing comments for a YouTube channel.
Here are recent top comments:
{json.dumps(comments)}

Analyze the sentiment, and generate a brief, friendly, human-like reply to each comment.
Return strict JSON: {{ "comment": "reply" }}
"""
    try:
        replies = await ask_json(prompt, is_fast=True)
        log.success("Generated comment replies.")
        return replies
    except Exception as e:
        log.warning(f"Failed to generate comment replies: {e}")
        return {c: "Thanks for watching and sharing your thoughts!" for c in comments}
