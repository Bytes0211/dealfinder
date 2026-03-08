# Deal Finder — User Process Flows

**Last Updated:** March 7, 2026

This document describes the complete user journey through the Deal Finder application — from first visit through deal discovery, watchlist management, notification setup, and receiving alerts.

---

## 1. User Journey Overview

```mermaid
flowchart TD
    classDef page fill:#274060,stroke:#274060,color:#ffffff
    classDef action fill:#335C81,stroke:#335C81,color:#ffffff
    classDef outcome fill:#65AFFF,stroke:#274060,color:#1B2845
    classDef system fill:#1B2845,stroke:#1B2845,color:#ffffff

    Visit["User visits app\n(CloudFront)"]:::page

    Visit --> Unauth

    subgraph Unauth["Without Login"]
        TopDeals["Browse Top Deals\n🔥 highest-discount deals\nsorted by % off"]:::page
    end

    Visit --> Login

    subgraph Login["Sign In (Cognito)"]
        LoginBtn["Click 'Sign in with Cognito'"]:::action
        Cognito["Cognito Hosted UI\noAuth2 PKCE redirect"]:::system
        Callback["Callback — JWT stored\nuser auto-provisioned in DB"]:::system
        LoginBtn --> Cognito --> Callback
    end

    Callback --> LoggedIn

    subgraph LoggedIn["Authenticated User Flows"]
        Search["Search for Deals\nPOST /search\nTavily + Bedrock"]:::page
        Feed["Matched Deals Feed\nGET /watchlist/matches"]:::page
        Prefs["Preferences\nSMS + email settings"]:::page
    end

    Search -->|"Save to watchlist"| Feed
    Feed -->|"System runs every 30 min"| Notify
    Prefs -->|"Enable email / SMS"| Notify

    Notify["Receive Notifications\n📧 Email via SES\n📱 SMS via SNS"]:::outcome
```

---

## 2. Authentication Flow

The app uses Cognito Hosted UI with an oAuth2 PKCE flow. No passwords are stored in the application database — all authentication is delegated to Cognito.

```mermaid
sequenceDiagram
    actor User
    participant SPA as React SPA
    participant Cognito as Cognito Hosted UI
    participant API as API Gateway + Lambda
    participant DB as Aurora PostgreSQL

    User->>SPA: Visit app (unauthenticated)
    Note over SPA: Top Deals page accessible<br/>without login

    User->>SPA: Click "Sign in with Cognito"
    SPA->>Cognito: Redirect (PKCE auth request)
    User->>Cognito: Enter email + password
    Cognito-->>SPA: Redirect to /auth/callback + code

    SPA->>Cognito: Exchange code for JWT access token
    Cognito-->>SPA: JWT (contains user sub UUID + email)
    Note over SPA: Token stored in localStorage<br/>getUserId() reads sub UUID

    User->>API: GET /users/{id} (Bearer JWT)
    API->>DB: Look up user by Cognito sub UUID
    alt First login — no DB record yet
        DB-->>API: Not found
        API->>DB: Auto-provision User row<br/>(id=sub, email from JWT username claim)
        DB-->>API: New user created
    end
    API-->>SPA: UserResponse (id, email, preferences)
```

**Key points:**
- Unauthenticated users can browse the **Top Deals** page without signing in.
- On first login, the API auto-provisions a `User` row using the Cognito `sub` UUID as the primary key and the sign-in email from the JWT `username` claim.
- Subsequent logins reuse the existing DB record — no duplicate provisioning.
- Logging out clears the JWT from localStorage. The Cognito session is separately managed.

---

## 3. Searching for Deals

The Search page lets users find products using natural language. Results are enriched by Bedrock (Claude) in real time and are **not persisted** — they are transient until the user explicitly saves them to their watchlist.

```mermaid
flowchart TD
    classDef page fill:#274060,stroke:#274060,color:#ffffff
    classDef action fill:#335C81,stroke:#335C81,color:#ffffff
    classDef system fill:#1B2845,stroke:#1B2845,color:#ffffff
    classDef outcome fill:#65AFFF,stroke:#274060,color:#1B2845
    classDef decision fill:#4a7c9e,stroke:#274060,color:#ffffff

    Start["User navigates to Search page"]:::page
    Start --> TypeQuery

    TypeQuery["Type a product query\ne.g. 'Sony noise-cancelling headphones'"]:::action
    TypeQuery --> Submit

    Submit["Click Search"]:::action
    Submit --> Tavily

    Tavily["POST /search\n→ Tavily API (up to 10 web results)\n→ BedrockSearchExtractor\n  · clean product title\n  · extract current price\n  · quality score 0–10\n  · quality reason"]:::system

    Tavily --> Results

    Results["Results displayed in table\n🟢 Great Deal (score ≥ 8)\n🟡 Fair (score ≥ 5)\n🔴 Weak (score < 5)\nCurrent price · reason shown"]:::page

    Results --> SelectAction

    SelectAction{{"User action"}}:::decision

    SelectAction -->|"Check boxes + click\n'Save selected to watchlist'"| CheckAuth

    CheckAuth{{"Authenticated?"}}:::decision
    CheckAuth -->|"No"| LoginPrompt["'Log in to save feeds.' message\n→ user must sign in first"]:::outcome
    CheckAuth -->|"Yes"| SaveFeed

    SaveFeed["PUT /users/{id}/preferences\n↳ new SavedFeed entries appended\n  · id (UUID)\n  · query (search term)\n  · title, url, current_price\n  · quality_score, quality_reason\n  · saved_at timestamp"]:::system

    SaveFeed --> Confirmation["'N feeds saved ✔' shown\nRow marked Saved"]:::outcome
    Confirmation --> NavigateFeed["Click 'View my watchlist'\n→ navigates to Feed page"]:::action

    SelectAction -->|"Click result link"| OpenURL["Opens product URL\nin new tab"]:::outcome
```

---

## 4. Watchlist & Matched Deals Flow

The Feed page (named "Matched Deals") is the user's home base. It shows their saved watchlist entries and all deals the system has discovered that match those entries.

```mermaid
flowchart TD
    classDef page fill:#274060,stroke:#274060,color:#ffffff
    classDef action fill:#335C81,stroke:#335C81,color:#ffffff
    classDef system fill:#1B2845,stroke:#1B2845,color:#ffffff
    classDef outcome fill:#65AFFF,stroke:#274060,color:#1B2845
    classDef decision fill:#4a7c9e,stroke:#274060,color:#ffffff

    FeedPage["Feed Page\n(requires login)"]:::page

    FeedPage --> LoadData

    LoadData["Load data in parallel\n→ GET /users/{id} (saved feeds)\n→ GET /users/{id}/watchlist/matches\n  (paginated, 20 per page)"]:::system

    LoadData --> SectionA

    subgraph SectionA["Section A — My Watchlist"]
        WatchlistCards["One card per saved feed\n· Title (links to product URL)\n· Current price (at save time)\n· Quality badge"]:::page

        WatchlistCards --> FeedActions

        FeedActions{{"Per-card actions"}}:::decision

        FeedActions -->|"⊕ Filter"| FilterDeals["Client-side filter\nMatchs deals by feed's query keywords\nShows count e.g. '3 of 47'"]:::outcome

        FeedActions -->|"Remove"| RemoveFeed["PUT /users/{id}/preferences\nSaved feed removed\nList refreshes"]:::system

        FeedActions -->|"+ New Search"| SearchPage["Navigate to\nSearch page"]:::page
    end

    LoadData --> SectionB

    subgraph SectionB["Section B — Matched Deals Grid"]
        DealsGrid["Scrollable deal grid\n20 per page with pagination\n→ DealCard per deal"]:::page

        DealsGrid --> TrendData

        TrendData{{"WatchlistAgent deal?"}}:::decision

        TrendData -->|"Yes — has trend data"| TrendDisplay["Trend signals row\n↑/↓/→ trend + confidence %\nPrice · Discounts · Reviews · Competitors\nTrend summary text"]:::outcome

        TrendData -->|"No — RSS pipeline deal"| BasicCard["DealCard only\nTitle · price · discount\nSource name"]:::outcome

        DealsGrid --> Pagination["Pagination controls\nPrev / Next"]:::action
    end

    SectionB --> NoDeals

    NoDeals{{"No matches yet?"}}:::decision
    NoDeals -->|"Yes"| WaitMsg["'No matched deals yet.\nLast scan: [timestamp]\nN sources scanned'"]:::outcome
    NoDeals -->|"No"| DealsGrid
```

### What populates the Matched Deals grid

Deals arrive from two sources, both visible in the same grid:

| Source | How it gets there | Has trend data? |
|--------|------------------|-----------------|
| **RSS Pipeline** | Scanner finds deal in RSS feed → Evaluator prices it → `is_high_value=true` → notified via SQS | No |
| **WatchlistAgent** | Every 30 min: Tavily search per watchlist query → Bedrock enrichment → persisted as `EVALUATED` deal | Yes — 8 trend fields |

The `last_scan_at` and `sources_scanned` values shown in the "no matches" state come from the most recent `DealSource.last_checked_at` across all active sources.

---

## 5. Notification Setup Flow

Users configure how they receive deal alerts on the Preferences page. Both channels can be enabled simultaneously.

```mermaid
flowchart TD
    classDef page fill:#274060,stroke:#274060,color:#ffffff
    classDef action fill:#335C81,stroke:#335C81,color:#ffffff
    classDef system fill:#1B2845,stroke:#1B2845,color:#ffffff
    classDef outcome fill:#65AFFF,stroke:#274060,color:#1B2845
    classDef decision fill:#4a7c9e,stroke:#274060,color:#ffffff

    PrefsPage["Preferences Page\n(requires login)"]:::page
    PrefsPage --> Load

    Load["GET /users/{id}\nLoads current phone + email pref"]:::system

    Load --> EmailSection

    subgraph EmailSection["Email Notifications"]
        EmailToggle["Check 'Enable email notifications'\nEmail address shown (from Cognito account)"]:::action
        EmailToggle --> SaveEmail["PUT /users/{id}/preferences\n{email: true/false}"]:::system
        SaveEmail --> EmailActive["Deal alerts sent to account email\nvia SES when deals qualify\n+ 'no deals found' feed updates"]:::outcome
    end

    Load --> SMSSection

    subgraph SMSSection["SMS Notifications"]
        PhoneInput["Enter E.164 phone number\ne.g. +12125551234"]:::action
        PhoneInput --> Validate{{"Valid E.164 format?"}}:::decision
        Validate -->|"No"| PhoneError["'Enter a valid E.164 number'\nerror shown inline"]:::outcome
        Validate -->|"Yes"| SavePhone["PUT /users/{id}/preferences\n{phone_number: '+1...'}"]:::system
        SavePhone --> SNSSub["API calls SNS Subscribe\nProtocol: SMS\n→ phone added to deal-notifications topic"]:::system
        SNSSub --> SMSActive["Deal alerts sent via SNS SMS\nto confirmed phone number"]:::outcome
    end

    Load --> DangerSection

    subgraph DangerSection["Account — Deactivate"]
        DeleteBtn["Click 'Deactivate Account'"]:::action
        DeleteBtn --> Confirm{{"Confirm?"}}:::decision
        Confirm -->|"Cancel"| PrefsPage
        Confirm -->|"Yes, deactivate"| SoftDelete["DELETE /users/{id}\nis_active = false\nAccount record retained"]:::system
        SoftDelete --> Logout["JWT cleared\nRedirect to /login\nAll alerts stop"]:::outcome
    end
```

**Notification channel summary:**

| Channel | Setup required | Delivery trigger | Dedup |
|---------|---------------|-----------------|-------|
| Email (SES) | Enable toggle on Preferences page | High-value deal OR no-deals-feed update | 24h per deal |
| SMS (SNS) | Enter E.164 phone number | High-value deal broadcast to SNS topic | 24h per deal |

---

## 6. End-to-End: From Saved Feed to Notification

This sequence shows the complete path from a user saving a watchlist item to receiving a deal notification.

```mermaid
sequenceDiagram
    actor User
    participant SPA as React SPA
    participant API as API Lambda
    participant WA as WatchlistAgent (30 min)
    participant Tavily as Tavily API
    participant Bedrock as AWS Bedrock
    participant DB as Aurora
    participant SQS as SQS
    participant Messenger as MessengerAgent
    participant SNS as SNS / SES

    User->>SPA: Search "Sony headphones"
    SPA->>API: POST /search
    API->>Tavily: Search query
    Tavily-->>API: Raw results
    API->>Bedrock: Enrich results (quality scores)
    Bedrock-->>API: Scored results
    API-->>SPA: SearchResponse

    User->>SPA: Select result + "Save to watchlist"
    SPA->>API: PUT /users/{id}/preferences (saved_feeds)
    API->>DB: Update user.notification_preferences
    DB-->>API: OK
    API-->>SPA: "1 feed saved ✔"

    Note over WA: EventBridge fires every 30 min
    WA->>DB: Load active users + saved_feeds
    DB-->>WA: Users + queries
    WA->>Tavily: Search "Sony headphones"
    Tavily-->>WA: Raw results
    WA->>Bedrock: Extract + score + trends (include_trends=True)
    Bedrock-->>WA: Enriched results with 8 trend fields
    WA->>DB: Persist new Deals (status=EVALUATED, raw_data=trends)

    Note over SPA: User opens Feed page
    SPA->>API: GET /users/{id}/watchlist/matches
    API->>DB: ILIKE keyword match on deal titles
    DB-->>API: Matched deals with trend data
    API-->>SPA: DealListResponse (incl. trend fields)
    SPA->>User: Deal grid with trend signals

    Note over Messenger: High-value deal → SQS enqueued
    Messenger->>Bedrock: Craft notification message
    Bedrock-->>Messenger: {title, message}
    Messenger->>SNS: Publish (broadcast to all subscribers)
    SNS-->>User: 📱 SMS alert
    Messenger->>SES: Send per-user email (if enabled)
    SES-->>User: 📧 Email alert
```

---

## 7. Page Reference

| Page | URL | Auth required | Purpose |
|------|-----|---------------|---------|
| Login | `/login` | No | Sign in via Cognito Hosted UI |
| Top Deals | `/top` | No | Browse high-value deals sorted by discount |
| Search | `/search` | No (save requires login) | Search + score deals, save to watchlist |
| Feed (Matched Deals) | `/` | Yes | View watchlist + matched deals with trend data |
| Preferences | `/preferences` | Yes | Enable email/SMS notifications, deactivate account |
| Deal Detail | `/deals/:id` | No | Single deal detail view |

### What unauthenticated users can do
- Browse **Top Deals** (RSS pipeline high-value deals, sorted by discount %)
- Run searches on the **Search** page and view quality scores
- Open any product URL directly from search results

### What requires login
- Saving search results to a watchlist
- Viewing the personalized **Matched Deals** feed
- Configuring email or SMS notification preferences
- Removing items from the watchlist
