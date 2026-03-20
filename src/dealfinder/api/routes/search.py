"""Search endpoint for the Deal Finder REST API.

Endpoints:
    POST /search — Tavily web search + Bedrock enrichment → structured results
"""

import asyncio
import logging
import os

import httpx
from fastapi import APIRouter, HTTPException, status

from dealfinder.agents.bedrock import BedrockSearchExtractor
from dealfinder.agents.config import AgentConfig
from dealfinder.api.schemas import SearchRequest, SearchResponse, SearchResult

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/search", tags=["search"])

_TAVILY_API_URL = "https://api.tavily.com/search"


async def _call_tavily(
    query: str, max_results: int, api_key: str, exclude_domains: list[str]
) -> list[dict]:
    """Call the Tavily Search API and return raw results.

    Args:
        query: Search query string.
        max_results: Maximum number of results to return.
        api_key: Tavily API key.
        exclude_domains: List of domains to exclude from results.

    Returns:
        List of raw Tavily result dicts (title, url, content, score).

    Raises:
        HTTPException 502: If Tavily returns a non-2xx response.
        HTTPException 504: If Tavily times out.
    """
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                _TAVILY_API_URL,
                json={
                    "api_key": api_key,
                    "query": f"{query} buy price",
                    "search_depth": "basic",
                    "max_results": max_results,
                    "include_answer": False,
                    "include_raw_content": False,
                    "exclude_domains": exclude_domains,
                },
            )
            response.raise_for_status()
            data = response.json()
            return data.get("results", [])
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Tavily search timed out — please try again",
        )
    except httpx.HTTPStatusError as e:
        logger.error(f"Tavily API error {e.response.status_code}: {e.response.text[:200]}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Search service unavailable — please try again",
        )


@router.post("", response_model=SearchResponse, summary="Search for deals via Tavily + Bedrock")
async def search_deals(body: SearchRequest) -> SearchResponse:
    """Search for product deals using Tavily web search enriched by Bedrock (Claude).

    Step 1 — Tavily: Fetches web results for the query (title, URL, content snippet).
    Step 2 — Bedrock: Claude extracts clean title, current price, and assigns a
    deal quality score (0–10) with a brief reasoning explanation.

    Results are transient — they are not persisted. The caller saves selected
    items as feed entries via PUT /users/{id}/preferences.

    Args:
        body: Search request with query and optional max_results.

    Returns:
        SearchResponse with query echo and enriched results list.

    Raises:
        HTTPException 400: If Tavily API key is not configured.
        HTTPException 502: If Tavily returns an error.
        HTTPException 504: If Tavily times out.
    """
    config = AgentConfig()
    api_key = config.tavily_api_key or os.getenv("DEALFINDER_TAVILY_API_KEY", "")

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Search is not configured — Tavily API key missing",
        )

    # Step 1: Tavily search
    raw_results = await _call_tavily(body.query, body.max_results, api_key, config.exclude_domains)

    if not raw_results:
        return SearchResponse(query=body.query, results=[])

    # Step 2: Bedrock enrichment (blocking boto3 call, run in executor)
    extractor = BedrockSearchExtractor(config)
    loop = asyncio.get_running_loop()
    try:
        enriched = await loop.run_in_executor(None, extractor.extract, raw_results)
    except Exception as exc:
        logger.warning(f"Bedrock enrichment failed, returning raw Tavily results: {exc}")
        # Graceful fallback: return title/url without quality scoring
        enriched = [
            {"title": r.get("title", ""), "url": r.get("url", ""),
             "current_price": None, "quality_score": None, "quality_reason": None}
            for r in raw_results
        ]

    results = [
        SearchResult(
            title=str(r.get("title") or ""),
            url=str(r.get("url") or ""),
            current_price=r.get("current_price") or None,
            quality_score=float(r["quality_score"]) if r.get("quality_score") is not None else None,
            quality_reason=r.get("quality_reason") or None,
        )
        for r in enriched
        if r.get("url")
    ]

    logger.info(f"Search '{body.query}': {len(results)} results enriched by Bedrock")
    return SearchResponse(query=body.query, results=results)
