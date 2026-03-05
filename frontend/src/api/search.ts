import { apiClient } from './client';
import type { SearchRequest, SearchResponse } from './types';

/**
 * POST /api/v1/search — run a Tavily + Bedrock web search.
 *
 * Sends a free-text query; the API fetches live web results via Tavily and
 * runs them through Bedrock (Claude) to extract title, URL, current price,
 * and deal-quality scoring.
 */
export async function postSearch(body: SearchRequest): Promise<SearchResponse> {
  const { data } = await apiClient.post<SearchResponse>('/search', body);
  return data;
}
