# Deal Finder - Process Flow Diagrams

**Project**: AI-Powered Deal Hunting System - Production Architecture  
**Date**: January 19, 2026

---

## 1. High-Level System Architecture Flow

```
┌────────────────────────────────────────────────────────────────────┐
│                           USER INTERFACES                          │
├─────────────┬──────────────┬──────────────┬────────────────────────┤
│   Web App   │  Mobile App  │   Browser    │    Email Digest        │
│  (React)    │ (iOS/Android)│  Extension   │    (Future)            │
└─────┬───────┴──────┬───────┴──────┬───────┴────────────────────────┘
      │              │              │
      └──────────────┼──────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────────────────┐
│                        CDN / API GATEWAY                         │
│  ┌──────────────────┐        ┌──────────────────────┐            │
│  │ CloudFront (CDN) │        │  API Gateway + WAF   │            │
│  │   Static Assets  │        │  Rate Limiting, Auth │            │
│  └──────────────────┘        └──────────────────────┘            │
└─────────────────┬──────────────────────┬─────────────────────────┘
                  │                      │
         ┌────────┘                      └────────┐
         ▼                                        ▼
┌──────────────────┐                  ┌──────────────────────┐
│  Static Content  │                  │   Apache APISIX      │
│  (S3)            │                  │   Service Mesh       │
└──────────────────┘                  └──────┬───────────────┘
                                              │
                                              ▼
         ┌────────────────────────────────────────────────────┐
         │           APPLICATION LAYER (ECS Fargate)          │
         │  ┌──────────────┐  ┌──────────────┐              │
         │  │  FastAPI     │  │  FastAPI     │ (Auto-scale) │
         │  │  Backend 1   │  │  Backend 2   │              │
         │  └──────┬───────┘  └──────┬───────┘              │
         └─────────┼──────────────────┼──────────────────────┘
                   │                  │
         ┌─────────┴──────────────────┴─────────┐
         │                                       │
         ▼                                       ▼
┌─────────────────┐                    ┌─────────────────────┐
│   WebSocket     │                    │   ElastiCache       │
│   Connections   │                    │   (Redis)           │
│   (API GW WS)   │                    │   Session Store     │
└─────────────────┘                    └─────────────────────┘
         │
         ▼
┌────────────────────────────────────────────────────────────────────┐
│                     ORCHESTRATION LAYER                             │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │              AWS Step Functions State Machine                 │ │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐    │ │
│  │  │ Scanner  │→ │ Ensemble │→ │Evaluator │→ │Messenger │    │ │
│  │  │  Agent   │  │  Agent   │  │          │  │  Agent   │    │ │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘    │ │
│  └──────────────────────────────────────────────────────────────┘ │
└─────────┬─────────────────────┬────────────────────┬──────────────┘
          │                     │                    │
          ▼                     ▼                    ▼
┌──────────────────┐   ┌─────────────────┐  ┌─────────────────┐
│  Lambda          │   │  Lambda         │  │  Lambda         │
│  Functions       │   │  Functions      │  │  Functions      │
│  (Agent Logic)   │   │  (ML Models)    │  │  (Messaging)    │
└────────┬─────────┘   └────────┬────────┘  └────────┬────────┘
         │                      │                     │
         ├──────────────────────┼─────────────────────┤
         │                      │                     │
         ▼                      ▼                     ▼
┌────────────────────────────────────────────────────────────────────┐
│                        DATA STREAMING LAYER                        │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │              Apache Kafka (AWS MSK)                           │ │
│  │  [deals.raw] → [deals.parsed] → [deals.evaluated] →           │ │
│  │  [deals.opportunities] → [notifications.outbound]             │ │
│  └───────────────────────────────────────────────────────────────┘ │
└─────────┬──────────────────────┬────────────────────┬──────────────┘
          │                      │                    │
          ▼                      ▼                    ▼
┌─────────────────┐    ┌─────────────────┐   ┌──────────────────┐
│  Stream         │    │  Batch          │   │  Model Training  │
│  Processing     │    │  Processing     │   │  Pipeline        │
│  (Kafka/Flink)  │    │ (Spark on EMR)  │   │  (SageMaker)     │
└────────┬────────┘    └────────┬────────┘   └─────────┬────────┘
         │                      │                       │
         └──────────────────────┼───────────────────────┘
                                │
                                ▼
┌────────────────────────────────────────────────────────────────┐
│                          STORAGE LAYER                         │
│  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐           │
│  │  OpenSearch  │  │  RDS Aurora  │  │  DynamoDB   │           │
│  │  (Vector DB) │  │ (PostgreSQL) │  │  (NoSQL)    │           │
│  └──────────────┘  └──────────────┘  └─────────────┘           │
│  ┌──────────────────────────────────────────────────┐          │
│  │           S3 Data Lake (Raw + Processed)         │          │
│  └──────────────────────────────────────────────────┘          │
└────────────────────────────────────────────────────────────────┘
         │
         ▼
┌────────────────────────────────────────────────────────────────┐
│                   MONITORING & OBSERVABILITY                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │  CloudWatch  │  │  Prometheus  │  │   X-Ray      │          │
│  │    Logs      │  │   Metrics    │  │  Tracing     │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│  ┌──────────────────────────────────────────────────┐          │
│  │           Grafana Dashboards + Alerts            │          │
│  └──────────────────────────────────────────────────┘          │
└────────────────────────────────────────────────────────────────┘
```

---

## 2. Deal Discovery Pipeline (Step Functions Workflow)

┌─────────────────────────────────────────────────────────────────────┐
│                      STEP FUNCTIONS STATE MACHINE                    │
└─────────────────────────────────────────────────────────────────────┘

START
  │
  ▼
┌──────────────────────────────┐
│  1. EventBridge Trigger      │
│     (Every 5 minutes)         │
└───────────────┬──────────────┘
                │
                ▼
┌──────────────────────────────┐
│  2. Initialize Context       │
│     - Load memory (DynamoDB) │
│     - Get last scan time     │
│     - Check rate limits      │
└───────────────┬──────────────┘
                │
                ▼
┌──────────────────────────────┐
│  3. Scanner Agent (Lambda)   │
│     - Fetch RSS feeds        │
│     - Parse HTML/XML         │
│     - Filter new deals       │
│     Output: 5-30 deals       │
└───────────────┬──────────────┘
                │
                ▼
┌──────────────────────────────┐
│  4. Check Deal Count         │◄─────────┐
└───────────────┬──────────────┘          │
                │                          │
         ┌──────┴──────┐                  │
         │             │                  │
    [Empty]      [Has Deals]              │
         │             │                  │
         ▼             ▼                  │
    ┌────────┐  ┌──────────────────────────────┐
    │  END   │  │  5. Publish to Kafka          │
    └────────┘  │     Topic: deals.parsed       │
                └───────────────┬───────────────┘
                                │
                                ▼
                ┌──────────────────────────────┐
                │  6. Map State (Parallel)     │
                │     Process each deal        │
                └───────────────┬───────────────┘
                                │
                ▼───────────────▼───────────────▼
      ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
      │ Specialist  │  │  Frontier   │  │   Neural    │
      │   Model     │  │   Model     │  │   Network   │
      │  (Lambda)   │  │  (Lambda)   │  │  (Lambda)   │
      │             │  │             │  │             │
      │ Returns:    │  │ Returns:    │  │ Returns:    │
      │ $124.50     │  │ $189.99     │  │ $156.23     │
      └─────┬───────┘  └─────┬───────┘  └─────┬───────┘
            │                │                │
            └────────────────┼────────────────┘
                             │
                             ▼
                ┌──────────────────────────────┐
                │  7. Ensemble Calculation     │
                │     weight_frontier = 0.8    │
                │     weight_specialist = 0.1  │
                │     weight_neural = 0.1      │
                │     Final: $180.47           │
                └───────────────┬───────────────┘
                                │
                                ▼
                ┌──────────────────────────────┐
                │  8. Calculate Discount       │
                │     discount = estimate -    │
                │                deal_price    │
                │     threshold = $50          │
                └───────────────┬───────────────┘
                                │
                                ▼
                ┌──────────────────────────────┐
                │  9. Evaluate Opportunity     │
                │     Is discount > threshold? │
                └───────────────┬───────────────┘
                                │
                    ┌───────────┴───────────┐
                    │                       │
                [NO]│                       │[YES]
                    │                       │
                    ▼                       ▼
        ┌──────────────────┐    ┌──────────────────────────┐
        │ 10a. Log & Skip  │    │ 10b. Create Opportunity  │
        │   - Write to     │    │   - Build notification   │
        │     CloudWatch   │    │   - Add to memory        │
        └────────┬─────────┘    └────────┬─────────────────┘
                 │                       │
                 │                       ▼
                 │            ┌──────────────────────────┐
                 │            │ 11. Messaging Agent      │
                 │            │   - Use Claude to craft  │
                 │            │   - Send via SNS/SQS     │
                 │            │   - Update DynamoDB      │
                 │            └────────┬─────────────────┘
                 │                     │
                 │                     ▼
                 │            ┌──────────────────────────┐
                 │            │ 12. Multi-Channel Send   │
                 │            │   - Pushover API         │
                 │            │   - Email (SES)          │
                 │            │   - SMS (optional)       │
                 │            │   - WebSocket push       │
                 │            └────────┬─────────────────┘
                 │                     │
                 └─────────────────────┼──────────────────────┘
                                       │
                                       ▼
                          ┌──────────────────────────┐
                          │ 13. Update State         │
                          │   - Write to DynamoDB    │
                          │   - Publish to Kafka     │
                          │   - Increment metrics    │
                          └────────┬─────────────────┘
                                   │
                                   ▼
                                  END

┌──────────────────────────────────────────────────────────────────┐
│  ERROR HANDLING (at any step)                                    │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  Retry Strategy: 3 attempts with exponential backoff       │  │
│  │  Catch: All errors → Send to DLQ → Alert on-call engineer  │  │
│  │  Compensations: Rollback state changes, log error context  │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

---

## 3. Data Flow Through Kafka Topics

```
┌─────────────────────────────────────────────────────────────────────┐
│                       KAFKA DATA PIPELINE                           │
└─────────────────────────────────────────────────────────────────────┘

RSS FEEDS (External)
  │
  ▼
┌──────────────────────────────┐
│  Scanner Agent Producer      │
└───────────────┬──────────────┘
                │
                ▼
     ╔═════════════════════════╗
     ║   Topic: deals.raw      ║
     ║   Partitions: 6         ║
     ║   Retention: 7 days     ║
     ║   Schema: JSON          ║
     ╚═════════════════════════╝
                │
                ▼
┌──────────────────────────────┐
│  Stream Processor (Flink)    │
│  - Parse HTML                │
│  - Extract structured data   │
│  - Validate schema           │
│  - Deduplicate (24hr window) │
└───────────────┬──────────────┘
                │
                ▼
     ╔═════════════════════════╗
     ║  Topic: deals.parsed    ║
     ║  Partitions: 6          ║
     ║  Retention: 30 days     ║
     ║  Schema: Avro           ║
     ╚═══════════════════════════╝
                │
        ┌───────┴────────┐
        │                │
        ▼                ▼
┌──────────────┐  ┌──────────────────┐
│  Ensemble    │  │  S3 Sink         │
│  Agent       │  │  (Archive)       │
│  Consumer    │  └──────────────────┘
└──────┬───────┘
       │
       ▼
     ╔═════════════════════════╗
     ║ Topic: deals.evaluated  ║
     ║ Partitions: 6           ║
     ║ Retention: 30 days      ║
     ║ Contains: price + est.  ║
     ╚═══════════════════════════╝
                │
                ▼
┌──────────────────────────────┐
│  Opportunity Evaluator       │
│  - Calculate discount        │
│  - Apply business rules      │
│  - Filter by threshold       │
└───────────────┬──────────────┘
                │
        ┌───────┴────────┐
        │                │
        ▼                ▼
     ╔══════════════╗  ╔═════════════════════╗
     ║ Topic:       ║  ║ Topic:              ║
     ║ opportunities║  ║ analytics.events    ║
     ╚══════════════╝  ╚═════════════════════╝
        │                      │
        ▼                      ▼
┌──────────────┐      ┌───────────────────┐
│ Notification │      │  Spark Analytics  │
│ Service      │      │  (EMR)            │
└──────┬───────┘      └───────────────────┘
       │
       ▼
     ╔═════════════════════════╗
     ║ Topic:                  ║
     ║ notifications.outbound  ║
     ║ Partitions: 3           ║
     ║ Retention: 3 days       ║
     ╚═══════════════════════════╝
                │
        ┌───────┴────────────┬──────────────┐
        │                    │              │
        ▼                    ▼              ▼
┌──────────────┐   ┌──────────────┐  ┌──────────────┐
│  Pushover    │   │   SES        │  │  WebSocket   │
│  Consumer    │   │   Consumer   │  │  Publisher   │
└──────────────┘   └──────────────┘  └──────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│  CONSUMER GROUPS                                                    │
│  - ensemble-pricing-group (3 consumers)                             │
│  - opportunity-evaluation-group (2 consumers)                       │
│  - notification-dispatch-group (5 consumers)                        │
│  - analytics-group (1 consumer)                                     │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│  MONITORING                                                         │
│  - Kafka lag per consumer group                                     │
│  - Message throughput (msg/sec)                                     │
│  - Processing latency (E2E)                                         │
│  - Error rates by topic                                             │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 4. User Request Flow (API)

```
┌─────────────────────────────────────────────────────────────────────┐
│                         USER REQUEST FLOW                           │
└─────────────────────────────────────────────────────────────────────┘

USER (Browser)
  │
  │ HTTPS Request: GET /api/v1/deals
  │ Authorization: Bearer <JWT_TOKEN>
  │
  ▼
┌──────────────────────────────┐
│  CloudFront CDN              │
│  - SSL/TLS Termination       │
│  - Cache check (miss)        │
└───────────────┬──────────────┘
                │
                ▼
┌──────────────────────────────┐
│  AWS WAF                     │
│  - SQL injection check       │
│  - Rate limiting (IP-based)  │
│  - Geo-blocking              │
└───────────────┬──────────────┘
                │
                ▼
┌──────────────────────────────┐
│  API Gateway                 │
│  - Validate JWT token        │
│  - Check quota (per user)    │
│  - Request logging           │
└───────────────┬──────────────┘
                │
                ▼
┌──────────────────────────────┐
│  Apache APISIX               │
│  - Route to backend          │
│  - Load balancing            │
│  - Circuit breaker check     │
└───────────────┬──────────────┘
                │
                ▼
┌──────────────────────────────┐
│  Application Load Balancer   │
│  - Health check              │
│  - Target group selection    │
└───────────────┬──────────────┘
                │
        ┌───────┴────────┐
        │                │
        ▼                ▼
┌──────────────┐  ┌──────────────┐
│  FastAPI     │  │  FastAPI     │
│  Instance 1  │  │  Instance 2  │
│  (ECS Task)  │  │  (ECS Task)  │
└──────┬───────┘  └──────┬───────┘
       │                 │
       └────────┬────────┘
                │
                ▼
┌──────────────────────────────┐
│  1. Check Redis Cache        │
│     Key: deals:user123:v1    │
└───────────────┬──────────────┘
                │
        ┌───────┴────────┐
        │                │
    [Cache Hit]      [Cache Miss]
        │                │
        │                ▼
        │      ┌──────────────────────────────┐
        │      │  2. Query DynamoDB           │
        │      │     Table: active_deals      │
        │      │     Index: user_preferences  │
        │      └───────────────┬──────────────┘
        │                      │
        │                      ▼
        │      ┌──────────────────────────────┐
        │      │  3. Enrich from OpenSearch   │
        │      │     - Vector similarity      │
        │      │     - User preferences       │
        │      └───────────────┬──────────────┘
        │                      │
        │                      ▼
        │      ┌──────────────────────────────┐
        │      │  4. Format Response          │
        │      │     - Apply filters          │
        │      │     - Sort by discount       │
        │      │     - Paginate (20 items)    │
        │      └───────────────┬──────────────┘
        │                      │
        │                      ▼
        │      ┌──────────────────────────────┐
        │      │  5. Store in Redis           │
        │      │     TTL: 60 seconds          │
        │      └───────────────┬──────────────┘
        │                      │
        └──────────────────────┘
                │
                ▼
┌──────────────────────────────┐
│  6. Add Response Headers     │
│     - X-Request-ID           │
│     - X-RateLimit-Remaining  │
│     - Cache-Control          │
└───────────────┬──────────────┘
                │
                ▼
┌──────────────────────────────┐
│  7. Log Metrics              │
│     - CloudWatch metric      │
│     - X-Ray trace            │
│     - Prometheus counter     │
└───────────────┬──────────────┘
                │
                ▼
      200 OK (JSON Response)
                │
                ▼
            USER (Browser)

┌─────────────────────────────────────────────────────────────────────┐
│  RESPONSE TIME BREAKDOWN (Target: < 500ms P95)                      │
│  - CDN/WAF: 10-20ms                                                 │
│  - API Gateway: 5-10ms                                              │
│  - APISIX: 5-10ms                                                   │
│  - ALB: 5-10ms                                                      │
│  - Application: 100-200ms (cache hit: 20-50ms)                     │
│  - DynamoDB: 10-20ms                                                │
│  - OpenSearch: 50-100ms                                             │
│  Total: 185-370ms (avg), < 500ms (P95)                             │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 5. Real-Time Notification Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                    REAL-TIME NOTIFICATION FLOW                       │
└─────────────────────────────────────────────────────────────────────┘

OPPORTUNITY DETECTED (from Step Functions)
  │
  ▼
┌──────────────────────────────┐
│  Messaging Agent (Lambda)    │
│  - Receive opportunity data  │
│  - Check user preferences    │
└───────────────┬──────────────┘
                │
                ▼
┌──────────────────────────────┐
│  Claude API (AWS Bedrock)    │
│  - Generate engaging message │
│  - Personalize for user      │
│  - Keep under 200 chars      │
└───────────────┬──────────────┘
                │
                ▼
┌──────────────────────────────┐
│  Publish to SNS Topic        │
│  Topic: deal-notifications   │
└───────────────┬──────────────┘
                │
        ┌───────┴────────────────────────┐
        │                                 │
        ▼                                 ▼
┌─────────────────┐           ┌─────────────────────┐
│  SQS Queue:     │           │  SNS Subscription:  │
│  push-notif     │           │  email-notif        │
└────────┬────────┘           └────────┬────────────┘
         │                              │
         ▼                              ▼
┌─────────────────┐           ┌─────────────────────┐
│  Lambda:        │           │  SES Email Service  │
│  PushDispatcher │           │  - Template render  │
│  - Check rate   │           │  - Send email       │
│    limit        │           └─────────────────────┘
│  - Deduplicate  │
└────────┬────────┘
         │
    ┌────┴────┬──────────────┬──────────────┐
    │         │              │              │
    ▼         ▼              ▼              ▼
┌────────┐ ┌──────┐  ┌──────────┐  ┌────────────┐
│Pushover│ │  SMS │  │WebSocket │  │   Slack    │
│  API   │ │(SNS) │  │(API GW)  │  │  Webhook   │
└────┬───┘ └───┬──┘  └─────┬────┘  └─────┬──────┘
     │         │            │             │
     └─────────┴────────────┴─────────────┘
                     │
                     ▼
        ┌──────────────────────────┐
        │  User Receives           │
        │  Notification            │
        └──────────┬───────────────┘
                   │
           ┌───────┴────────┐
           │                │
       [Ignore]        [Click/View]
           │                │
           │                ▼
           │    ┌──────────────────────────┐
           │    │  Track Engagement        │
           │    │  - DynamoDB write        │
           │    │  - Analytics event       │
           │    │  - Update preferences    │
           │    └──────────┬───────────────┘
           │               │
           │               ▼
           │    ┌──────────────────────────┐
           │    │  ML Model Feedback       │
           │    │  - Adjust ranking        │
           │    │  - Update user profile   │
           │    └──────────────────────────┘
           │
           ▼
    ┌──────────────────────────┐
    │  Clean up (24 hrs later) │
    │  - DynamoDB TTL          │
    │  - Archive to S3         │
    └──────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│  NOTIFICATION DELIVERY SLA                                           │
│  - Time from detection to delivery: < 30 seconds (P95)              │
│  - Delivery success rate: > 99.5%                                   │
│  - Duplicate prevention: 100% (24-hour window)                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 6. CI/CD Deployment Pipeline

```
┌─────────────────────────────────────────────────────────────────────┐
│                        CI/CD PIPELINE FLOW                           │
└─────────────────────────────────────────────────────────────────────┘

DEVELOPER
  │
  │ git push origin feature/new-agent
  │
  ▼
┌──────────────────────────────┐
│  GitHub Repository           │
│  - Branch protection active  │
│  - Required: 2 approvals     │
└───────────────┬──────────────┘
                │
                ▼
┌──────────────────────────────┐
│  GitHub Actions (PR Checks)  │
│  ┌──────────────────────────┐│
│  │ 1. Lint (black, pylint)  ││
│  │ 2. Type check (mypy)     ││
│  │ 3. Security scan (bandit)││
│  │ 4. Dependency check      ││
│  │ 5. Unit tests (pytest)   ││
│  └──────────┬───────────────┘│
└─────────────┼────────────────┘
              │
      [Tests Pass]
              │
              ▼
┌──────────────────────────────┐
│  Code Review & Approval      │
│  - 2 reviewers required      │
│  - All checks passed         │
└───────────────┬──────────────┘
                │
                ▼
┌──────────────────────────────┐
│  Merge to main branch        │
└───────────────┬──────────────┘
                │
                ▼
┌──────────────────────────────┐
│  AWS CodeBuild (or GH Actions)│
│  ┌──────────────────────────┐│
│  │ BUILD STAGE              ││
│  │ 1. Install dependencies  ││
│  │ 2. Run full test suite   ││
│  │ 3. Build Docker images   ││
│  │ 4. Security scan images  ││
│  │ 5. Push to ECR           ││
│  └──────────┬───────────────┘│
└─────────────┼────────────────┘
              │
              ▼
┌──────────────────────────────┐
│  Tag: latest, v1.2.3         │
└───────────────┬──────────────┘
                │
                ▼
┌──────────────────────────────┐
│  AWS CodePipeline            │
│  ┌──────────────────────────┐│
│  │ DEPLOY TO DEV            ││
│  │ 1. Update ECS task def   ││
│  │ 2. Deploy to dev cluster ││
│  │ 3. Run smoke tests       ││
│  │ 4. Health check          ││
│  └──────────┬───────────────┘│
└─────────────┼────────────────┘
              │
      [Dev Tests Pass]
              │
              ▼
┌──────────────────────────────┐
│  Integration Tests (Dev)     │
│  - API endpoint tests        │
│  - Agent workflow tests      │
│  - Load tests (locust)       │
└───────────────┬──────────────┘
                │
      [Tests Pass]
              │
              ▼
┌──────────────────────────────┐
│  DEPLOY TO STAGING           │
│  - Blue-green deployment     │
│  - Traffic gradually shifted │
│  - Monitor for 10 minutes    │
└───────────────┬──────────────┘
                │
      [Staging Healthy]
              │
              ▼
┌──────────────────────────────┐
│  Manual Approval Gate        │
│  - Product Manager review    │
│  - Check staging metrics     │
│  - Approve for production    │
└───────────────┬──────────────┘
                │
      [APPROVED]
              │
              ▼
┌──────────────────────────────┐
│  Pre-Production Checks       │
│  - Backup current state      │
│  - Check alarm status        │
│  - Verify rollback plan      │
└───────────────┬──────────────┘
                │
                ▼
┌──────────────────────────────┐
│  DEPLOY TO PRODUCTION        │
│  ┌──────────────────────────┐│
│  │ CANARY DEPLOYMENT        ││
│  │ 1. Deploy to 10% traffic ││
│  │ 2. Monitor for 5 min     ││
│  │ 3. Check error rates     ││
│  │ 4. Scale to 50%          ││
│  │ 5. Monitor for 10 min    ││
│  │ 6. Scale to 100%         ││
│  └──────────┬───────────────┘│
└─────────────┼────────────────┘
              │
      ┌───────┴────────┐
      │                │
  [Success]       [High Error Rate]
      │                │
      │                ▼
      │     ┌──────────────────────────┐
      │     │  AUTOMATIC ROLLBACK      │
      │     │  1. Shift traffic back   │
      │     │  2. Alert on-call        │
      │     │  3. Create incident      │
      │     └──────────────────────────┘
      │
      ▼
┌──────────────────────────────┐
│  Post-Deployment             │
│  - Update documentation      │
│  - Tag release in GitHub     │
│  - Notify team (Slack)       │
│  - Monitor metrics (1 hour)  │
└──────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│  ROLLBACK TRIGGERS (Automatic)                                       │
│  - Error rate > 1% for 2 minutes                                    │
│  - P95 latency > 1000ms for 3 minutes                               │
│  - Health check failures > 20%                                      │
│  - CPU usage > 90% sustained                                        │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 7. Data Migration Flow (ChromaDB to OpenSearch)

```
┌─────────────────────────────────────────────────────────────────────┐
│                    DATA MIGRATION WORKFLOW                           │
└─────────────────────────────────────────────────────────────────────┘

EXISTING SYSTEM (ChromaDB)
  │
  ▼
┌──────────────────────────────┐
│  Phase 1: Assessment         │
│  - Count documents: 50,000   │
│  - Measure size: 2.5 GB      │
│  - Identify vector dims: 384 │
└───────────────┬──────────────┘
                │
                ▼
┌──────────────────────────────┐
│  Phase 2: Setup Target       │
│  - Provision OpenSearch      │
│  - Create index mapping      │
│  - Configure k-NN settings   │
└───────────────┬──────────────┘
                │
                ▼
┌──────────────────────────────┐
│  Phase 3: Export from Chroma │
│  - Extract all documents     │
│  - Save to S3 (JSON format)  │
│  - Batch size: 1000 docs     │
└───────────────┬──────────────┘
                │
                ▼
┌──────────────────────────────┐
│  Phase 4: Transform Data     │
│  - Apache Spark job (EMR)    │
│  - Map fields to new schema  │
│  - Validate data quality     │
│  - Output to S3 (parquet)    │
└───────────────┬──────────────┘
                │
                ▼
┌──────────────────────────────┐
│  Phase 5: Bulk Load          │
│  - Use OpenSearch bulk API   │
│  - Lambda function           │
│  - Process 100K docs/hour    │
│  - Monitor progress          │
└───────────────┬──────────────┘
                │
                ▼
┌──────────────────────────────┐
│  Phase 6: Verification       │
│  - Count documents           │
│  - Random sample validation  │
│  - Run test queries          │
│  - Compare results           │
└───────────────┬──────────────┘
                │
      ┌─────────┴──────────┐
      │                    │
  [Mismatch]          [Validated]
      │                    │
      ▼                    ▼
┌──────────┐     ┌──────────────────────┐
│  Debug   │     │  Phase 7: Parallel   │
│  & Retry │     │  Running (2 weeks)   │
└──────────┘     │  - Old: ChromaDB     │
                 │  - New: OpenSearch   │
                 │  - Compare responses │
                 └──────────┬───────────┘
                            │
                            ▼
                 ┌──────────────────────┐
                 │  Phase 8: Cutover    │
                 │  - Update configs    │
                 │  - Switch endpoints  │
                 │  - Monitor closely   │
                 └──────────┬───────────┘
                            │
                            ▼
                 ┌──────────────────────┐
                 │  Phase 9: Cleanup    │
                 │  - Keep ChromaDB for │
                 │    1 week (backup)   │
                 │  - Decomission old   │
                 └──────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│  ROLLBACK PLAN                                                      │
│  - Keep ChromaDB running in parallel for 2 weeks                    │
│  - Config flag to switch back instantly                             │
│  - Monitor error rates during migration                             │
│  - No deletion of old data until full validation                    │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 8. Monitoring & Alerting Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                   MONITORING & ALERTING ARCHITECTURE                │
└─────────────────────────────────────────────────────────────────────┘

APPLICATION METRICS
  │
  ├─► CloudWatch Metrics ─────────┐
  │   - Custom metrics            │
  │   - AWS service metrics       │
  │                               │
  ├─► Prometheus Exporters ───────┤
  │   - Application metrics       │
  │   - JVM/Python metrics        │         ┌──────────────────┐
  │                               ├────────►│   Grafana        │
  ├─► X-Ray Traces ───────────────┤         │   Dashboards     │
  │   - Distributed traces        │         └────────┬─────────┘
  │   - Service map               │                  │
  │                               │                  │
  └─► CloudWatch Logs ────────────┘         ┌────────▼─────────┐
      - Application logs                    │  Visualization   │
      - Access logs                         │  - System health │
                                            │  - Business KPIs │
                                            │  - Cost tracking │
                                            └──────────────────┘

ALERTING RULES
  │
  ├─► CloudWatch Alarms
  │   - Threshold: Error rate > 1%
  │   - Threshold: Latency P95 > 500ms
  │   - Threshold: CPU > 80%
  │
  ├─► Prometheus Alert Manager
  │   - Rate of change alerts
  │   - Prediction alerts
  │   - Composite conditions
  │
  └─► Custom Lambda Monitors
      - Business rule violations
      - Data quality issues

         │
         ▼
┌─────────────────────────────────────────┐
│         ALERT ROUTING                   │
│                                         │
│   Severity: CRITICAL                    │
│   ├─► PagerDuty ─► On-call Engineer     │
│   └─► Slack #incidents                  │
│                                         │
│   Severity: WARNING                     │
│   ├─► Slack #alerts                     │
│   └─► Email to team                     │
│                                         │
│   Severity: INFO                        │
│   └─► CloudWatch dashboard only         │
└─────────────────────────────────────────┘

INCIDENT RESPONSE
  │
  ▼
┌──────────────────────────────┐
│  1. Alert Received           │
│     - Context loaded         │
│     - Runbook retrieved      │
└───────────────┬──────────────┘
                │
                ▼
┌──────────────────────────────┐
│  2. Initial Assessment       │
│     - Check dashboards       │
│     - Review recent deploys  │
│     - Check dependencies     │
└───────────────┬──────────────┘
                │
                ▼
┌──────────────────────────────┐
│  3. Mitigation               │
│     - Apply fixes            │
│     - Rollback if needed     │
│     - Scale resources        │
└───────────────┬──────────────┘
                │
                ▼
┌──────────────────────────────┐
│  4. Verification             │
│     - Confirm metrics normal │
│     - Test functionality     │
└───────────────┬──────────────┘
                │
                ▼
┌──────────────────────────────┐
│  5. Post-Incident            │
│     - Update incident ticket │
│     - Write postmortem       │
│     - Create follow-up tasks │
└──────────────────────────────┘
```

---

## Summary

These process flows provide a comprehensive view of how the production system will operate across multiple dimensions:

1. **Architecture** : Multi-tier cloud-native design with AWS services
2. **Data Pipeline**: Event-driven architecture with Kafka streaming
3. **Orchestration**: Step Functions for reliable agent coordination
4. **API Layer**: High-performance request handling with caching
5. **Notifications**: Multi-channel real-time delivery
6. **CI/CD**: Automated, safe deployment with rollback capabilities
7. **Migration**: Systematic approach to data platform changes
8. **Monitoring**: Comprehensive observability and incident response

Each flow is designed for scalability, reliability, and operational excellence in a production environment.
