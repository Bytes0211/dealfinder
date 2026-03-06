## Problem Statement
Replace the category-based deal discovery model with a Tavily-powered free-text search flow. Simplify preferences (remove global discount threshold and preferred categories). Add phone number field for SNS SMS notifications and account deletion.
## Current State
* **Feed page** (`FeedPage.tsx`): Filters deals by `category` + `status` via `CategoryPicker`; saved feeds are `{category, status}` pairs stored in `notification_preferences.saved_feeds`
* **Preferences page** (`PreferencesPage.tsx`): Has `discount_threshold` input and `CategoryTagInput` multi-select
* **User model** (`db/models.py`): Has `discount_threshold (Numeric)` and `preferred_categories (JSONB)` columns
* **API schemas** (`schemas.py`): `UserPreferencesUpdate` and `UserResponse` include both removed fields
* **No search/Tavily capability** exists anywhere in the stack
## Proposed Changes
### 1. New Search Page + API (Tavily + Bedrock)
Add a `POST /api/v1/search` endpoint:
* Request: `SearchRequest(query: str, max_results: int = 10)`
* **Step 1 — Tavily**: Backend calls Tavily API (`httpx` async client, key in `DEALFINDER_TAVILY_API_KEY`) — returns raw results: `title, url, content` snippet per result
* **Step 2 — Bedrock (Claude)**: Raw Tavily results passed to `BedrockSearchExtractor` (new class in `agents/bedrock.py`). Claude extracts structured data from the snippets in a single prompt: `title` (cleaned), `url`, `current_price` (as string e.g. `"$279.99"`, or `null`), **`quality_score` (0–10 float)** and **`quality_reason`** (max 20-word explanation). Quality scoring considers price relative to typical market value, brand, and snippet context — the first agentic layer, extensible to price comparison and deeper reasoning in future phases.
* Response: `SearchResponse(results: list[SearchResult])` where `SearchResult` has `title: str`, `url: str`, `current_price: str | None`, `quality_score: float | None`, `quality_reason: str | None`
* No DB persistence — transient
New frontend `SearchPage.tsx` (`/search` route):
* Free-text input + "Search" button; loading state while Tavily + Bedrock run
* Results list: each row shows title (linked), extracted price, quality badge (🟢/🟡/🔴 + score), and a checkbox; `quality_reason` shown as tooltip on the badge
* After selecting items: single "Minimum Discount (%)" input + "Save as feed" / "Dismiss" buttons
* "Save as feed" → each selected item appended to `notification_preferences.saved_feeds` and user navigated to Feed page
* "Dismiss" → clears results, stays on page
### 2. Feed Page — Watchlist + Matched Deals
The Feed page (`/`) has two sections:
**Section A — My Watchlist** (top): the user's saved feed items
* Each entry: title (linked to URL), current price, editable discount % input (debounced `PUT /preferences` on change), remove button
* Empty state: prompt to go to `/search`
**Section B — Matched Deals** (below watchlist, paginated): RSS-pipeline deals that match the user's watchlist items
* New API endpoint `GET /api/v1/users/{id}/watchlist/matches?limit=20&offset=0`
* For each saved feed item, queries the `deals` table: `title ILIKE '%<term>%'` using keywords from the saved feed's `query` field, filtered by `deal.discount_percentage >= feed.min_discount`
* Results deduplicated and sorted by `discovered_at DESC`; returns `DealListResponse` shape with pagination
* Frontend renders paginated deal cards below the watchlist
* Unauthenticated users see a login prompt
**Notification pipeline** (EvaluatorAgent enhancement):
* After evaluating a deal, `EvaluatorAgent` queries the DB for all users whose `notification_preferences.saved_feeds` contain a query that matches the deal's title (`ILIKE` keyword check) AND whose `min_discount ≤ deal.discount_percentage`
* For each matched user, enqueues a per-user notification message to the existing SQS notification dispatch queue
* `MessengerAgent` dispatches as usual (SNS fan-out / SMS to phone number if set)
* Each `SavedFeed` entry shape: `{id: string, query: string, title: string, url: string, current_price: string | null, min_discount: number, quality_score: number | null, quality_reason: string | null, saved_at: string}`
* **Section A quality display**: Each watchlist item shows a colored quality badge (🟢 8–10 = Great Deal / 🟡 5–7 = Fair / 🔴 0–4 = Weak) using the `quality_score` stored at save time, with `quality_reason` shown as a tooltip
* Remove `categories.ts`, `CategoryPicker.tsx`, `CategoryTagInput.tsx`, `FilterBar.tsx` — no longer used
### 3. Preferences Page Overhaul
* **Remove**: `discount_threshold` input, `CategoryTagInput` / preferred categories
* **Add phone number**: E.164 validated input (`^\+[1-9]\d{1,14}$`). Backend validates format (422 on failure) and stores in `User.phone_number`. SNS SMS `subscribe` called on save. Dev-only: SNS sandbox requires number verification — backend handles the subscribe call and the user receives a confirmation text.
* **Add account deletion**: "Request Account Deletion" button with a confirm dialog. Calls `DELETE /api/v1/users/{id}`. Backend sets `user.is_active = False`. Frontend logs user out.
### 4. Backend / DB Changes
**`db/models.py`**:
* `User`: remove `discount_threshold`, remove `preferred_categories`, add `phone_number: Mapped[Optional[str]] = mapped_column(String(20))`
**`api/schemas.py`**:
* `UserPreferencesUpdate`: remove `discount_threshold`, `preferred_categories`; add `phone_number: Optional[str] = None`
* `UserResponse`: same field changes; add `phone_number: Optional[str] = None`
* `SavedFeed`: replace `category: str` with `{id, query, title, url, current_price, min_discount, quality_score, quality_reason, saved_at}` — stored as JSONB in `notification_preferences.saved_feeds`
* Add `SearchRequest(query: str, max_results: int = 10)`, `SearchResult(title, url, current_price, quality_score, quality_reason)`, `SearchResponse(results: list[SearchResult])`
**`api/routes/users.py`**:
* Remove `discount_threshold` / `preferred_categories` update logic
* Add phone number update: E.164 regex validation → `sns.subscribe()` → store in `user.phone_number`
* Add `DELETE /users/{user_id}` (sets `is_active = False`, returns 204)
**`api/routes/search.py`** (new):
* `POST /search` — calls Tavily → passes results to `BedrockSearchExtractor` → returns `SearchResponse`
* Auth not required (public endpoint)
**`agents/bedrock.py`**: add `BedrockSearchExtractor` class with `extract(results: list[dict]) -> list[SearchResult]`; uses Claude with a single JSON prompt that returns `title`, `url`, `current_price`, `quality_score` (0–10), and `quality_reason`
**`api/main.py`**: register `search` router
**`agents/config.py`**: add `tavily_api_key: str = ""`
**Alembic migration `003_add_phone_drop_categories`**:
* `ALTER TABLE users DROP COLUMN discount_threshold`
* `ALTER TABLE users DROP COLUMN preferred_categories`
* `ALTER TABLE users ADD COLUMN phone_number VARCHAR(20)`
### 5. Terraform Changes (dev only)
**`modules/api/main.tf`**: add `DEALFINDER_TAVILY_API_KEY` Lambda env var; add `sns:Subscribe` IAM permission for API Lambda role on the `deal_notifications` topic
**`modules/api/variables.tf`**: add `tavily_api_key` var (plain string, sourced from Secrets Manager at deploy time)
**`environments/dev/`**: wire new var
### 6. Frontend Changes Summary
* `App.tsx`: add `/search` route
* `NavBar.tsx`: add "Search" nav link
* `api/types.ts`: update `UserResponse`, `UserPreferencesUpdate`, `SavedFeed`; add `SearchRequest`, `SearchResult`, `SearchResponse`
* `api/search.ts` (new): `postSearch(query, max_results?) → SearchResponse`
* `api/users.ts`: add `deleteUser(userId: string)`
* `hooks/index.ts`: add `useSearch()` mutation, `useDeleteUser()` mutation
* `pages/SearchPage.tsx` (new): search UI with results, checkbox selection, discount input, save/dismiss
* `pages/FeedPage.tsx`: rewritten as watchlist (remove all category/filter/deals-query logic)
* `pages/PreferencesPage.tsx`: remove discount/categories, add phone number + account deletion
* Delete: `components/FilterBar.tsx`, `components/CategoryPicker.tsx`, `components/CategoryTagInput.tsx`, `api/categories.ts`
### 7. Tests
* Add `tests/unit/api/test_search.py`
* Update `tests/unit/api/test_users.py`: remove discount/category refs, add phone validation, delete-user tests
* Update `tests/unit/db/test_models.py` and `tests/unit/data/test_repository.py`: remove old User fields, add `phone_number`
* Update `tests/unit/agents/conftest.py` if needed
### 8. GitHub Issue
Create `github/ISSUES/issue-phase6-redesign-tavily-search.m`