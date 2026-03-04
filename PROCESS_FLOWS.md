# Deal Finder - Process Flow Diagrams

**Project**: AI-Powered Deal Hunting System — Production Architecture  
**Updated**: March 2026

Color palette: `#1B2845`, `#274060`, `#335C81`, `#65AFFF`

---

## 1. High-Level System Architecture

```mermaid
flowchart TD
    classDef primary fill:#1B2845,stroke:#1B2845,color:#ffffff
    classDef secondary fill:#274060,stroke:#274060,color:#ffffff
    classDef accent fill:#335C81,stroke:#335C81,color:#ffffff
    classDef link fill:#65AFFF,stroke:#274060,color:#ffffff

    subgraph Input["Deal Sources"]
        RSS[RSS Feeds]:::primary
        Vendors[Vendor APIs<br/>(Phase 5)]:::secondary
    end

    subgraph Orchestration["Serverless Orchestration"]
        EventBridge[EventBridge Schedule]:::accent
        StepFn[AWS Step Functions<br/>Core Pipeline]:::primary
    end

    subgraph Agents["Lambda Agents"]
        Scanner[ScannerAgent Lambda<br/>RSS → Aurora]:::secondary
        Evaluator[EvaluatorAgent Lambda<br/>Bedrock Price Estimation]:::secondary
        Messenger[MessengerAgent Lambda<br/>Personalized Notifications<br/>(Phase 4)]:::secondary
    end

    subgraph Data["Persistent Storage & Search"]
        Aurora[Aurora PostgreSQL<br/>Deal Store]:::accent
        OpenSearch[OpenSearch Serverless<br/>Vector + Text Search]:::accent
        S3Archive[S3 Buckets<br/>(Raw + Processed)]:::accent
        DynamoDB[DynamoDB State Cache]:::accent
    end

    subgraph Notifications["Notification Fan-out"]
        SNS[SNS Topic]:::primary
        Pushover[Pushover API]:::link
        Email[SES Email]:::link
        Webhook[Partner Webhooks]:::link
    end

    subgraph API["Consumer Interfaces"]
        APIG[API Gateway + Lambda<br/>FastAPI (Phase 4)]:::primary
        Clients[Clients<br/>(CLI, Web, Mobile)]:::link
    end

    RSS --> Scanner
    Vendors -. Future .-> Scanner
    EventBridge --> StepFn
    StepFn --> Scanner
    StepFn --> Evaluator
    StepFn --> Messenger
    Scanner --> Aurora
    Evaluator --> Aurora
    Evaluator --> OpenSearch
    Evaluator --> DynamoDB
    Scanner --> S3Archive
    Messenger --> SNS
    SNS --> Pushover
    SNS --> Email
    SNS --> Webhook
    APIG --> Clients
    Aurora --> APIG
    OpenSearch --> APIG
    DynamoDB --> APIG
```

---

## 2. Core Pipeline (Step Functions Workflow)

```mermaid
flowchart TD
    classDef primary fill:#1B2845,stroke:#1B2845,color:#ffffff
    classDef secondary fill:#274060,stroke:#274060,color:#ffffff
    classDef accent fill:#335C81,stroke:#335C81,color:#ffffff
    classDef warn fill:#65AFFF,stroke:#1B2845,color:#ffffff

    Start([Start]):::primary --> Trigger[EventBridge Trigger<br/>(Cron Schedule)]:::accent
    Trigger --> Scan[ScannerAgent Lambda<br/>Fetch & Deduplicate Deals]:::secondary
    Scan -->|new_deal_ids| MapState{Deals Found?}:::accent

    MapState -->|No| Complete([Success<br/>No Deals]):::primary
    MapState -->|Yes| MapBlock[Map State<br/>Iterate Deals]:::accent

    subgraph Evaluation["Evaluation Path"]
        MapBlock --> Eval[EvaluatorAgent Lambda<br/>Bedrock Price Estimation]:::secondary
        Eval --> Discount[Calculate Discount & Confidence]:::secondary
        Discount --> Check{Discount ≥ Threshold?}:::accent
        Check -->|No| Skip[Log & Store Evaluation<br/>Status = Evaluated]:::secondary
        Check -->|Yes| Queue[Send to Notification Queue<br/>(SQS Phase 4)]:::secondary
        Queue --> Metrics[Update Metrics + State<br/>Aurora & DynamoDB]:::secondary
        Skip --> Metrics
        Metrics --> Continue([Deal Complete]):::primary
    end

    MapBlock --> Eval
    Continue --> PipelineDone([Pipeline Succeeded]):::primary
    Complete --> PipelineDone

    Scan -.error.-> ScanFail[[Fail<br/>DealFinder.ScanError]]:::warn
    Eval -.error.-> EvalFail[[Fail<br/>DealFinder.EvaluationError]]:::warn
    Queue -.error.-> NotifyFail[[Fail<br/>DealFinder.NotificationError]]:::warn
```

---

## 3. Data Flow & Persistence

```mermaid
flowchart LR
    classDef primary fill:#1B2845,stroke:#1B2845,color:#ffffff
    classDef secondary fill:#274060,stroke:#274060,color:#ffffff
    classDef accent fill:#335C81,stroke:#335C81,color:#ffffff
    classDef link fill:#65AFFF,stroke:#274060,color:#ffffff

    RSS[RSS Feed Items]:::link --> Scanner[ScannerAgent Lambda]:::secondary
    Scanner --> Clean[Normalize & Deduplicate]:::secondary
    Clean --> Aurora[Aurora PostgreSQL<br/>Deals, Sources, Estimates]:::primary
    Clean --> RawS3[S3 Raw Archive]:::accent

    Aurora --> Eval[EvaluatorAgent Lambda]:::secondary
    Eval --> Estimates[PriceEstimates Table]:::primary
    Eval --> Embeddings[Generate Embeddings<br/>(Phase 4)]:::secondary
    Embeddings --> OpenSearch[OpenSearch Serverless]:::primary

    Eval --> State[DynamoDB Deal State<br/>TTL Cache]:::accent
    Eval --> Metrics[CloudWatch Metrics + Logs]:::accent

    subgraph Notifications["Notification Fan-out"]
        Eval -->|High-Value Deals| SQSQueue[SQS Notification Queue<br/>(Phase 4)]:::accent
        SQSQueue --> Messenger[MessengerAgent Lambda]:::secondary
        Messenger --> SNS[SNS Topic]:::primary
        SNS --> Channels[Email / Pushover / Webhooks]:::link
    end
```

---

## 4. User API Request Flow (Phase 4 Preview)

```mermaid
sequenceDiagram
    autonumber
    participant User as User / Client
    participant APIG as API Gateway
    participant Auth as Cognito Authorizer
    participant Lambda as FastAPI Lambda
    participant Aurora as Aurora PostgreSQL
    participant OpenSearch as OpenSearch Serverless
    participant DynamoDB as DynamoDB Cache

    User->>APIG: HTTPS GET /deals (JWT)
    APIG->>Auth: Validate JWT / scopes
    Auth-->>APIG: Auth OK
    APIG->>Lambda: Invoke with request context
    Lambda->>DynamoDB: Fetch cached filters (optional)
    alt Cache hit
        DynamoDB-->>Lambda: Cached result
    else Cache miss
        Lambda->>Aurora: Query deals & estimates
        Aurora-->>Lambda: Result set
        Lambda->>OpenSearch: Similar deals / embeddings (optional)
        OpenSearch-->>Lambda: Search hits
        Lambda->>DynamoDB: Store cache entry
    end
    Lambda-->>APIG: HTTP 200 JSON payload
    APIG-->>User: Response
    note right of User: Latency target<br/>&lt; 1s P95
```

---