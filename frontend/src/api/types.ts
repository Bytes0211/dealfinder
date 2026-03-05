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
  category: string | null;
  brand: string | null;
  status: string;
  source_name: string | null;
}

/** Mirrors backend DealListResponse Pydantic schema. */
export interface DealListResponse {
  items: DealResponse[];
  total: number;
  limit: number;
  offset: number;
}

/** Mirrors backend UserResponse Pydantic schema. */
export interface UserResponse {
  id: string;
  email: string;
  username: string;
  full_name: string | null;
  is_active: boolean;
  discount_threshold: string;
  preferred_categories: string[] | null;
}

/** Mirrors backend UserPreferencesUpdate Pydantic schema. */
export interface UserPreferencesUpdate {
  notification_preferences?: Record<string, boolean> | null;
  discount_threshold?: string | null;
  preferred_categories?: string[] | null;
  pushover_user_key?: string | null;
}

/** Query parameters for GET /deals. */
export interface DealFilters {
  category?: string;
  status?: string;
  limit?: number;
  offset?: number;
}
