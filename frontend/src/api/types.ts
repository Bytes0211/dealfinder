/** Mirrors backend DealResponse Pydantic schema. */
export interface DealResponse {
  id: string;
  title: string;
  url: string;
  sale_price: string | null;
  original_price: string | null;
  estimated_value: string | null;
  discount_percentage: string | null;
  is_high_value: boolean;
  brand: string | null;
  status: string;
  source_name: string | null;
  // Availability — only present on WatchlistAgent-discovered deals.
  in_stock: boolean | null;
  // Trend analysis — only present on WatchlistAgent-discovered deals.
  trend: 'upward' | 'downward' | 'stable' | null;
  trend_confidence: number | null;
  price_trend: 'increasing' | 'decreasing' | 'stable' | null;
  discount_frequency: 'low' | 'medium' | 'high' | null;
  stockouts_last_30_days: number | null;
  review_velocity: 'low' | 'medium' | 'high' | null;
  competitor_activity: 'stable' | 'increasing' | 'decreasing' | null;
  trend_summary: string | null;
}

/** Mirrors backend DealListResponse Pydantic schema. */
export interface DealListResponse {
  items: DealResponse[];
  total: number;
  limit: number;
  offset: number;
  /** ISO timestamp of the most recent pipeline scan, or null if never run. */
  last_scan_at: string | null;
  /** Number of active RSS feed sources checked in the last scan. */
  sources_scanned: number | null;
}

/** A single entry in the user's watchlist (saved search turned into a feed). */
export interface SavedFeed {
  id: string;
  query: string;
  title: string;
  url: string;
  current_price: string | null;
  quality_score: number | null;
  quality_reason: string | null;
  saved_at: string;
}

/** Mirrors backend UserResponse Pydantic schema. */
export interface UserResponse {
  id: string;
  email: string;
  username: string;
  full_name: string | null;
  is_active: boolean;
  phone_number: string | null;
  notification_preferences: Record<string, unknown> | null;
}

/** Mirrors backend UserPreferencesUpdate Pydantic schema. */
export interface UserPreferencesUpdate {
  notification_preferences?: Record<string, unknown> | null;
  saved_feeds?: SavedFeed[] | null;
  phone_number?: string | null;
}

/** Query parameters for GET /deals. */
export interface DealFilters {
  status?: string;
  limit?: number;
  offset?: number;
}

/** Search request body — mirrors backend SearchRequest schema. */
export interface SearchRequest {
  query: string;
}

/** A single search result with Bedrock-extracted quality scoring. */
export interface SearchResult {
  title: string;
  url: string;
  current_price: string | null;
  quality_score: number;
  quality_reason: string;
}

/** Search response — mirrors backend SearchResponse schema. */
export interface SearchResponse {
  query: string;
  results: SearchResult[];
}
