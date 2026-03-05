# Deal Finder Cost Management & Optimization

**Last Updated:** March 5, 2026 (Pre-Production Deploy)
**Environment:** Development (feature flags disabled)
**Deployment Status:** 96% Complete (Phase 5 — production deploy pending)
**Current Monthly Cost:** ~$4-10/month (feature flags off)
**Full-Stack Production Cost:** ~$156-435/month (all services enabled)
**Cost Target:** <$500/month

---

## Monthly Cost Breakdown

### Current Costs (Development — Feature Flags Disabled)

**VPC & Networking**
- VPC, subnets, route tables, internet gateway: $0/month
  - NAT Gateway disabled (`enable_nat_gateway = false`) — saves ~$100/month
- VPC Endpoints (S3, DynamoDB): $0/month (included in free tier)

**Storage — S3**
- 3 buckets (data-lake, models, backups): $1-5/month
  - RSS archives: ~1-2 GB ($0.023/GB)
  - Model artifacts: ~0.5 GB ($0.012/GB)
  - Lifecycle policies: transition to Glacier after 90 days
- **Optimization:** Lifecycle policies already configured

**NoSQL — DynamoDB**
- 3 tables (deal-state, agent-state, user-sessions): $0-2/month
  - On-demand pricing (no provisioned capacity)
  - TTL enabled on deal-state and agent-state (auto-expiry reduces storage)
- **Optimization:** TTL already configured

**Monitoring — CloudWatch**
- Logs: $3.20/month
  - $0.50/GB ingested
  - 3 log groups (scanner, evaluator, messenger)
- 8 alarms: $0.80/month ($0.10/alarm)
- 1 dashboard: Free (first 3 dashboards free)
- Cost Anomaly Monitor: Free
- **Optimization:** Set retention policies to 30 days for dev (reduces storage cost)

**IAM & Secrets Manager**
- Secrets Manager: $2-5/month
  - Pushover API key, Aurora credentials, OpenSearch credentials
  - ~4-5 secrets @ $0.40/secret
- IAM: Free

**Development Subtotal:** ~$4-10/month

---

### Projected Costs (Production — All Feature Flags Enabled)

**Compute — AWS Lambda**
- 3 agent functions (Scanner, Evaluator, Messenger) + API handler: $10-30/month
  - $0.20/1M requests
  - ~50K-500K invocations/month (5-15 min schedule)
  - Compute: $0.0000166667/GB-second
  - Scanner: 512 MB, 5s avg; Evaluator: 512 MB, 10s avg; Messenger: 256 MB, 3s avg
  - API handler: 512 MB, 1s avg
- **Optimization:** Enable ARM Graviton2 (20% cheaper); use Lambda Power Tuning

**Orchestration — Step Functions**
- Pipeline executions: $5-15/month
  - $0.025/1K state transitions
  - ~100-500 pipeline runs/day × ~10 transitions each
  - Monthly: 30K-150K transitions
- **Optimization:** Already using Standard Workflows (most cost-effective for duration)

**API — API Gateway HTTP API v2**
- REST API calls: $5-15/month
  - $1.00/1M requests (HTTP API v2, cheaper than REST API)
  - ~5K-15K requests/day = 150K-450K/month
- Data transfer: Minimal for deal data payloads
- **Optimization:** HTTP API v2 already selected over REST API ($1/1M vs $3.50/1M)

**Database — Aurora PostgreSQL Serverless v2**
- ACU hours: $50-100/month
  - $0.06/ACU-hour (us-east-1)
  - Minimum: 0.5 ACU; Maximum: 4 ACU
  - Scales to zero when idle (no connections)
  - Storage: $0.10/GB-month (~2-5 GB initial)
- **Optimization:** Scales to zero between pipeline runs; feature flag disables in dev

**Vector Search — OpenSearch**
- Single-node (dev): $25-75/month
  - t3.small.search: ~$25/month
  - Multi-AZ (prod): t3.medium.search × 2: ~$75/month
  - Storage: $0.10/GB-month (~5-10 GB embeddings)
- **Optimization:** Feature flag disabled in dev; snapshot to S3 before teardown

**LLM — AWS Bedrock (Claude)**
- Price estimation + notification crafting: $50-150/month
  - Claude 3 Haiku (price estimation — high volume): $0.25/1M input, $1.25/1M output
  - Claude 3 Sonnet (notification crafting — lower volume): $3/1M input, $15/1M output
  - Estimated: 500K-2M tokens/month across both use cases
- **Optimization:** Already using tiered models (Haiku for estimation, Sonnet for messaging)

**NoSQL — DynamoDB**
- Agent state, rate limits, deal cache: $1-5/month
  - On-demand pricing
  - TTL reduces storage cost; cache entries expire in 24-48 hours

**Messaging — SQS/SNS**
- 4 SQS queues + 2 DLQs + 1 SNS topic: $1-5/month
  - SQS: $0.40/1M requests (first 1M free)
  - SNS: $0.50/1M requests
  - Estimated: 500K-5M messages/month

**Email — SES**
- Deal alert emails: $1-5/month
  - $0.10/1K emails
  - Estimated: 100-5K emails/month

**Auth — Cognito**
- User pool + JWT auth: $0-10/month
  - Free tier: 50K MAUs
  - API auth tokens: free (covered by Lambda authorizer or built-in)

**Networking**
- NAT Gateway (required for Lambda in VPC → internet): $30-50/month
  - $0.045/hour × 730 hours = $32.85/month
  - Data processing: $0.045/GB
  - **Note:** Largest surprise cost; disabled in dev via feature flag

**Full-Stack Production Subtotal:** $156-435/month

---

### Revised Monthly Estimate

| Environment | Cost | Feature Flags |
|-------------|------|---------------|
| Development (current) | $4-10/month | All off |
| Development (full stack) | $156-435/month | All on |
| Production (optimized) | $200-400/month | All on + optimizations |

**Cost Target:** <$500/month (well within range)

---

## Feature Flags

Three Terraform feature flags control the most expensive resources:

| Flag | Savings | Default | When to Enable |
|------|---------|---------|----------------|
| `enable_nat_gateway` | ~$100/month | `false` | Production deploy |
| `enable_aurora` | $50-100/month | `false` | Production deploy |
| `enable_opensearch` | $25-75/month | `false` | Production deploy |

**Enabling for production:**
```bash
# infrastructure/environments/prod/terraform.tfvars
enable_nat_gateway = true
enable_aurora      = true
enable_opensearch  = true
```

---

## Cost Optimization Strategies

### Immediate Actions (0-1 week implementation)

#### 1. CloudWatch Log Retention Policies
**Current:** Logs retained indefinitely → storage grows unbounded
**Optimized:** 30 days dev, 90 days prod

**Actions:**
- Set retention to 30 days on all dev log groups
- Set retention to 90 days on prod log groups
- Export to S3 Glacier for long-term archival if needed

**Savings:** $1-3/month

#### 2. Lambda ARM Graviton2
**Current:** x86 Lambda functions
**Optimized:** ARM-based Graviton2

**Actions:**
```bash
# In Terraform Lambda resource
architectures = ["arm64"]
```
- 20% cheaper per GB-second
- Often faster for Python workloads

**Savings:** $2-6/month (in production)

#### 3. S3 Intelligent-Tiering for RSS Archives
**Current:** Standard storage class for all S3 objects
**Optimized:** Intelligent-Tiering for data-lake bucket

**Actions:**
- Enable Intelligent-Tiering on data-lake bucket (lifecycle already partially configured)
- Auto-transition infrequent archives to cheaper tiers

**Savings:** $0.50-2/month

**Total Immediate Savings:** $3.50-11/month

---

### Short-term Actions (1-4 weeks implementation)

#### 4. Bedrock Model Tiering
**Current:** All LLM calls may use higher-tier models
**Optimized:** Route by complexity

**Actions:**
- Price estimation (high volume): Claude 3 Haiku (already low-cost)
- Notification crafting (low volume): Claude 3 Sonnet
- Add prompt result caching for repeated product categories
- Implement token usage CloudWatch metrics

**Savings:** $10-30/month

#### 5. Aurora Serverless v2 Minimum ACU Tuning
**Current:** Minimum 0.5 ACU (default)
**Optimized:** Monitor and adjust based on actual baseline

**Actions:**
- Monitor `ServerlessDatabaseCapacity` metric for 2 weeks post-deploy
- Tune `min_capacity` based on observed idle baseline
- Confirm scales to zero between pipeline runs (no persistent connections)

**Savings:** $5-20/month

#### 6. EventBridge Schedule Optimization
**Current:** Pipeline designed for every 5-15 minutes
**Optimized:** Start at 15 minutes, adjust based on deal freshness needs

**Actions:**
- Start with 15-minute intervals (reduces Lambda + Step Functions invocations by 3×)
- Monitor deal discovery rate; shorten interval only if needed
- Disable schedule during off-peak hours (11 PM - 6 AM) if discovery rate allows

**Savings:** $5-15/month (Lambda + Step Functions)

**Total Short-term Savings:** $20-65/month

---

### Long-term Actions (1-3 months in production)

#### 7. OpenSearch Right-Sizing
**Current (planned):** t3.small.search (dev) / t3.medium.search × 2 (prod)
**Optimized:** Monitor actual index size and query load

**Actions:**
- After 4 weeks of production data, evaluate actual vector index size
- If < 1M embeddings and query latency is acceptable: stay on t3.small.search
- If throughput demands: evaluate Reserved Instance (30-60% savings)
- 1-year Reserved: ~$18/month vs ~$25/month on-demand (t3.small)

**Savings:** $7-15/month with Reserved Instances

#### 8. DynamoDB Capacity Review
**Current:** On-demand pricing (pay per request)
**Optimized:** Provisioned with auto-scaling (if patterns are predictable)

**Actions:**
- After 4 weeks, review CloudWatch `ConsumedReadCapacityUnits` and `ConsumedWriteCapacityUnits`
- If usage is predictable: switch to provisioned with auto-scaling (20-50% cheaper)

**Savings:** $0.50-2/month

#### 9. Multi-Account Strategy (Future)
**Current:** Single AWS account (dev + prod co-mingled eventually)
**Optimized:** Separate dev/prod accounts

**Benefits:**
- Isolate prod costs from dev experimentation
- Granular budget controls per environment
- Easier IAM boundary enforcement

**Total Long-term Savings:** $7-17/month

---

## Cost Monitoring & Alerts

### Current Alarms Configured (8 total)

1. **DLQ Depth Alert:** Triggers when `deal-processing-dlq` or `notification-dispatch-dlq` > 0
   - Action: SNS → CloudWatch alarm
   - Prevents: Repeated retries driving up SQS costs

2. **Step Functions Failures:** Monitors failed pipeline executions
   - Action: SNS notification
   - Prevents: Silent failures that would require reprocessing

3. **API 5xx Errors:** Monitors API Gateway error rate
   - Action: SNS notification
   - Cost impact: Indicates Lambda errors burning compute

4. **Cost Anomaly Monitor:** AWS-managed ML-based spending anomaly detection
   - Configured in Phase 1 monitoring module
   - Alerts on unusual spending patterns (e.g., runaway pipeline)

### Recommended Additional Alerts

**Budget Alerts (set in AWS Budgets):**
- 50% of $500 budget: $250/month (early warning)
- 75% of $500 budget: $375/month (action required)
- 100% of $500 budget: $500/month (critical — disable feature flags)

**Service-Specific Alerts:**
- Bedrock token usage > 5M tokens/month
- Lambda invocations > 1M/month
- Step Functions state transitions > 500K/month
- DynamoDB read/write capacity > 1M units/month
- OpenSearch FreeStorageSpace < 5 GB

---

## Cost Allocation Tags

### Tagging Strategy

**Required Tags (all Terraform resources):**
- `Project`: dealfinder
- `Environment`: dev | prod
- `ManagedBy`: terraform
- `Persistent`: true | false

**Optional Tags:**
- `Owner`: scotton
- `Phase`: phase1 | phase2 | phase3 | phase4 | phase5
- `Component`: pipeline | api | notifications | data | monitoring

### Cost Allocation by Component

**Monthly Cost by Component (production):**
```
Pipeline (Lambda + Step Functions + EventBridge):  $15-45/month
API (Lambda + API Gateway + Cognito):              $10-30/month
Data (Aurora + DynamoDB + S3):                     $52-110/month
Search (OpenSearch):                               $25-75/month
LLM (Bedrock):                                     $50-150/month
Notifications (SQS/SNS + SES):                     $2-10/month
Networking (NAT Gateway + VPC):                    $30-50/month
Monitoring (CloudWatch + Secrets Manager):         $7-20/month
```

**Cost by Service (Top 5, production):**
1. Bedrock (Claude): $50-150/month (35%)
2. Aurora Serverless v2: $50-100/month (25%)
3. NAT Gateway: $30-50/month (12%)
4. OpenSearch: $25-75/month (10%)
5. Lambda: $10-30/month (8%)

---

## Budget Recommendations

### Development Environment (Current)
- **Current (flags off):** $4-10/month
- **Recommended Budget:** $15/month (buffer for testing)

### Development Environment (Full Stack)
- **Estimated:** $156-435/month
- **Recommendation:** Only enable all flags when needed for integration testing; disable after

### Production Environment
- **Estimated:** $156-435/month
- **Optimized Target:** $200-350/month (with immediate + short-term optimizations)
- **Recommended Budget:** $500/month (buffer for spikes)
- **Hard Limit:** Set AWS Budget alert at $500 — disable non-critical feature flags if exceeded

---

## Cost-Benefit Analysis

### AI Deal Discovery ROI

**Monthly Investment:** $200-350/month (production, optimized)

**Benefits:**
- Automated deal discovery (100-1000 deals/hour, 24/7)
- AI-powered price estimation (no manual research)
- Instant push notifications (<2 minutes from discovery)
- Scalable serverless architecture (cost scales with usage, not idle)

**Cost per Notification (production):**
- Assume: 50 high-value deals/day × 30 days = 1,500 notifications/month
- Monthly cost: $200-350/month
- **Cost per notification: $0.13-0.23**
- Target: <$0.10 (achievable with optimizations)

**Comparison:**
- Manual deal hunting: 1-2 hours/day at $25/hour = $750-1,500/month in time
- Commercial deal alert service: $20-100/month (limited customization, no AI pricing)
- **This system:** $200-350/month (fully customized, AI-powered, scalable)

**Break-even vs manual hunting:** Immediate — automation saves 1-2 hrs/day

---

## Cost Optimization Checklist

### Weekly Tasks
- [ ] Review CloudWatch cost anomaly alerts
- [ ] Check DLQ message counts (failed processing = wasted compute)
- [ ] Monitor Lambda duration metrics (long-running = expensive)
- [ ] Check Bedrock token usage trends

### Monthly Tasks
- [ ] Review AWS Cost Explorer breakdown by service
- [ ] Validate budget alerts are triggering correctly
- [ ] Check Aurora ACU usage vs min/max capacity settings
- [ ] Review EventBridge schedule — is 15-minute interval optimal?
- [ ] Audit unused Lambda versions (delete to reduce storage)
- [ ] Update cost forecasts

### Quarterly Tasks
- [ ] Evaluate OpenSearch Reserved Instance options
- [ ] Review DynamoDB on-demand vs provisioned pricing
- [ ] Assess Bedrock model tiering (new Claude models may be cheaper)
- [ ] Review NAT Gateway data transfer costs (consider VPC endpoints for services)
- [ ] Consider adding VPC endpoints for Bedrock, SQS, SNS (reduces NAT Gateway traffic)

---

## Cost Saving Quick Wins

**Immediate (< 1 hour):**
1. Set CloudWatch log retention to 30 days (dev): $1-3/month savings
2. Enable Graviton2 (arm64) on Lambda functions: $2-6/month savings
3. Delete old Lambda function versions: $0-1/month savings

**Total quick wins:** $3-10/month

**Short-term (1-2 days):**
1. Add Bedrock token usage CloudWatch metrics + alert: visibility into #1 cost driver
2. Tune EventBridge to 15-minute intervals: $5-15/month savings
3. Add VPC endpoints for Bedrock/SQS/SNS: $5-20/month NAT Gateway savings

**Total short-term wins:** $10-35/month

**Combined savings potential:** $13-45/month (5-15% reduction on production)

---

## Summary & Recommendations

### Current State
- **Monthly Cost:** $4-10/month (dev, feature flags off)
- **Full Production Cost:** $156-435/month (all services enabled)
- **Largest Cost Driver:** Bedrock (35%) → Aurora (25%) → NAT Gateway (12%)
- **Optimization Applied:** Feature flags, Graviton2 pending, TTL on DynamoDB, lifecycle on S3

### Recommended Actions (Priority Order)

**Priority 1 (Before Production Deploy):**
1. Set CloudWatch log retention policies → $1-3/month savings
2. Enable arm64 (Graviton2) on all Lambda functions → $2-6/month savings
3. Set EventBridge to 15-minute interval → $5-15/month savings
4. Configure AWS Budgets alert at $500/month
5. **Total:** $8-24/month savings (pre-optimized production cost: $132-411/month)

**Priority 2 (First Month in Production):**
1. Add VPC endpoints for Bedrock, SQS, SNS → $5-20/month NAT savings
2. Implement Bedrock prompt result caching → $10-30/month savings
3. Monitor Aurora ACU baseline and tune min_capacity → $5-20/month savings
4. **Total:** $20-70/month additional savings

**Priority 3 (After 3 Months in Production):**
1. Evaluate OpenSearch Reserved Instances → $7-15/month savings
2. Review DynamoDB on-demand vs provisioned → $0.50-2/month savings
3. Consider disabling NAT Gateway + using VPC endpoints exclusively → $30-50/month savings

### Target Monthly Costs

**Development (flags off):** $4-10/month
**Production (initial):** $156-435/month
**Production (optimized — 3 months):** $100-280/month

---

## Appendix: Cost Tracking Tools

### AWS Native Tools
- AWS Cost Explorer
- AWS Budgets (set at $500/month)
- AWS Cost Anomaly Detection (configured in monitoring module)
- AWS Cost and Usage Reports (CUR)

### Infrastructure Cost Estimation
- Infracost CLI (`infracost breakdown --path infrastructure/environments/prod/`)
- Terraform plan cost estimation

### Custom Monitoring
- CloudWatch dashboard with Lambda invocation + duration metrics
- CloudWatch Bedrock token usage metrics (custom namespace)
- Monthly cost summary via Lambda + SES (future enhancement)

---

**Last Review Date:** March 5, 2026
**Next Review Date:** April 5, 2026 (1 month post-production deploy)
**Reviewed By:** scotton
