import re
import hashlib
from typing import Dict, Any

def optimize_prompt(prompt: str) -> str:
    """
    Token Optimization:
    - Remove duplicate context
    - Remove repeated instructions
    - Trim excessive history
    """
    # 1. Remove multiple spaces and empty lines
    prompt = re.sub(r'\n{3,}', '\n\n', prompt)
    prompt = re.sub(r' +', ' ', prompt)

    # 2. Heuristic: If there's repeated instructions like "IMPORTANT: Return JSON", keep only one
    if "IMPORTANT:" in prompt:
        parts = prompt.split("IMPORTANT:")
        # Keep the first occurrence and the last, if they differ
        prompt = parts[0] + "IMPORTANT:" + parts[-1]

    # Add more token optimization strategies here if needed.
    return prompt.strip()
