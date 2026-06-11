"""
Tavily Search API — real-time web research. Better than Perplexity for trends.
Get free key (1,000 searches/month) at: https://app.tavily.com
"""
import os, requests, logging

logger = logging.getLogger("TavilySearch")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")

def tavily_search(query: str, max_results: int = 5,
                  search_depth: str = "basic") -> list:
    """Returns list of {title, url, content, score} dicts."""
    if not TAVILY_API_KEY:
        logger.warning("TAVILY_API_KEY not set — skipping Tavily search")
        return []
    try:
        r = requests.post(
            "https://api.tavily.com/search",
            json={"api_key": TAVILY_API_KEY, "query": query,
                  "search_depth": search_depth, "include_answer": True,
                  "max_results": max_results},
            timeout=15,
        )
        r.raise_for_status()
        return r.json().get("results", [])
    except Exception as e:
        logger.warning(f"Tavily search failed: {e}")
        return []
