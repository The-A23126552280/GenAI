import os
from tavily import TavilyClient


def search_research(topic: str, max_results: int = 5) -> str:
    """Search the web via Tavily and return a formatted research string.

    Falls back to a placeholder message if the API key is missing or the
    request fails, so the pipeline can still run (LLM will then generate
    research instead).
    """
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        return "Tavily API key not configured. Using placeholder research data."

    client = TavilyClient(api_key=api_key)
    try:
        response = client.search(
            query=topic,
            max_results=max_results,
            search_depth="advanced",
        )
        results = [
            f"**{item.get('title', 'No title')}**\n"
            f"{item.get('content', 'No content')}\n"
            f"Source: {item.get('url', '')}\n"
            for item in response.get("results", [])
        ]
        return "\n---\n".join(results) if results else "No research data found."
    except Exception as e:
        return f"Search error: {str(e)}. Using placeholder data."
