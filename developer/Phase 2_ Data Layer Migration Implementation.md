# Phase 2: Data Layer Migration Implementation
## Overview
Phase 2 migrates the Deal Finder data layer from prototype to production AWS infrastructure. This includes deploying OpenSearch for vector storage (replacing ChromaDB), Aurora PostgreSQL for relational data, and implementing backup/recovery procedures.
## Current State
* Phase 1 complete: VPC, S3, DynamoDB, CloudWatch deployed
* Aurora and OpenSearch Terraform modules exist as empty directories
* Feature flags defined in variables.tf for cost control
* DynamoDB tables already created (deal-state, agent-state, user-sessions)
* S3 buckets already configured (data-lake, models, backups)
## Implementation Tasks
### 1. Aurora PostgreSQL Terraform Module
Create `infrastructure/modules/data/aurora/` with:
* `main.tf`: Aurora PostgreSQL Serverless v2 cluster (cost-optimized)
* `variables.tf`: DB instance settings, credentials, networking
* `outputs.tf`: Cluster endpoint, reader endpoint, security group
* Security group for DB access from private subnets
* Subnet group spanning private subnets
* Parameter group for PostgreSQL tuning
* Automated backups with 7-day retention
### 2. OpenSearch Terraform Module
Create `infrastructure/modules/data/opensearch/` with:
* `main.tf`: OpenSearch domain with k-NN plugin enabled
* `variables.tf`: Instance types, node counts, storage
* `outputs.tf`: Domain endpoint, ARN, security group
* Dev config: Single-node t3.small.search (cost-optimized)
* Prod config: 3 data nodes + 3 master nodes
* VPC deployment in private subnets
* Access policy for Lambda/ECS roles
* Automated snapshots to S3
### 3. Update Dev Environment
Modify `infrastructure/environments/dev/main.tf`:
* Add Aurora module with `enable_aurora` feature flag
* Add OpenSearch module with `enable_opensearch` feature flag
* Pass VPC/subnet outputs to new modules
* Add new outputs for endpoints
### 4. Database Schema and Migrations
Create `src/dealfinder/db/` with:
* `alembic.ini`: Alembic configuration
* `alembic/env.py`: Migration environment setup
* `alembic/versions/001_initial_schema.py`: Initial migration
* `models.py`: SQLAlchemy ORM models (Deal, User, PriceEstimate)
* `connection.py`: Connection pooling with asyncpg
### 5. OpenSearch Client Implementation
Create `src/dealfinder/search/` with:
* `client.py`: OpenSearch client wrapper
* `embeddings.py`: Vector embedding utilities
* `index.py`: Index management (create, delete, bulk ops)
* `migration.py`: ChromaDB to OpenSearch migration script
### 6. Data Access Layer
Create `src/dealfinder/data/` with:
* `repository.py`: Data access patterns (CRUD operations)
* `cache.py`: Redis caching layer (optional for Phase 2)
* `backup.py`: Backup automation utilities
### 7. Tests
Add to `tests/`:
* `tests/infrastructure/test_aurora.py`: Aurora resource validation
* `tests/infrastructure/test_opensearch.py`: OpenSearch resource validation
* `tests/unit/test_db_models.py`: ORM model tests
* `tests/unit/test_search_client.py`: OpenSearch client tests
* `tests/integration/test_data_access.py`: End-to-end data tests
## New Variables Required
```hcl
enable_aurora = false  # ~$50-100/month for Serverless v2
aurora_min_capacity = 0.5  # ACUs (scales to zero when idle)
aurora_max_capacity = 4.0  # ACUs
db_master_username = "dealfinder_admin"
```
## Cost Estimates (Dev Environment)
* Aurora Serverless v2: $50-100/month (scales to ~$0 when idle)
* OpenSearch t3.small: $25-40/month
* Total Phase 2 addition: ~$75-140/month (when active)
## Success Criteria
* Aurora cluster deployed with automated backups
* OpenSearch domain with k-NN enabled
* Alembic migrations run successfully
* Vector search queries < 100ms (p95)
* Zero data loss during ChromaDB migration
* All storage encrypted at rest
* 100% test coverage for new modules
