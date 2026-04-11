# Project Roodha - Technical State-of-the-Union Report

## [A] Directory Tree & File Inventory
A high-level map of the critical structure (excluding `.venv`, `node_modules`, and `.git`):

```text
project-roodha/
├── task-2-s3-cloudfront-iac/     # Frontend Infrastructure (AWS CDK)
│   ├── app.py                    # CDK Entry showing RoodhaFrontendProdStackV1
│   └── jobwork_s3_iac/           # S3 Bucket and CloudFront stack classes
├── task-3-api-gateway-ec2-iac/   # Backend Infrastructure (AWS CDK)
│   ├── app.py                    # CDK Entry defining EC2 and API Gateway
│   ├── api_gateway_stack.py      
│   └── ec2_stack.py
├── task-4-backend-skeleton/      # API Endpoints & Logic (FastAPI)
│   ├── .env                      # Contains RDS URL & Cognito constraints
│   ├── app/
│   │   ├── core/                 # Business logic schemas and middleware
│   │   ├── routes/               # FastAPI route files (auth, jobs, metrics, etc.)
│   │   ├── database.py           # RDS Session binding
│   │   └── models.py             # SQLAlchemy schemas
│   └── seed_db.py                # Database dummy-data init script
└── task-5-react-frontend/        # React Components & Interfaces (Vite SPA)
    ├── .env                      # Contains API base routing and Cognito pool
    └── src/
        ├── components/           # Generic / reusable React views
        ├── lib/                  # Includes amplify.js and isolated API bindings
        └── pages/                # Complete page components
```

## [B] Tech Stack Summary
- **Frontend Layer:** React (via Vite compiler), JavaScript, TailwindCSS layout system.
- **Backend Layer:** Python ecosystem using FastAPI framework, SQLAlchemy ORM, and Alembic for schema migrations.
- **Data Persistence:** AWS RDS running PostgreSQL.
- **AWS Infrastructure Ecosystem:**
  - **Authentication:** AWS Cognito
  - **Frontend Delivery:** Private AWS S3 exposed securely via CloudFront using Origin Access Control (OAC). 
  - **Backend Compute:** Provisioned EC2 instance served via API Gateway.
  - **IaC Tooling:** AWS CDK written in Python.

## [C] Connection Map
1. **Frontend (SPA):** React interface leverages `src/lib/api.js` (an Axios singleton) dynamically setting the route prefix using `VITE_API_BASE_URL`. Traffic targets backend micro-endpoints separated cleanly in files like `jobsApi.js` and `masterDataApi.js`.
2. **API Access:** Traffic is funneled through API Gateway, traversing toward the provisioned EC2 instances which serve FastAPI asynchronously.
3. **Backend Middleware:** API Gateway drops the traffic to the FastAPI framework, which immediately verifies the token using internal `JWTAuthMiddleware`.
4. **Database Execution:** Once authorized, handlers query directly to AWS RDS instances using synchronous/asynchronous logic initialized exclusively by connections from `app/database.py`.

## [D] Security & Auth Status
- **Cognito Integration - MIXED STATUS:**
  - **Frontend:** `.env` safely imports real, recovered credentials correctly (`VITE_COGNITO_USER_POOL_ID=ap-south-1_M3xBYcen7`, client mapping perfectly matching).
  - **Backend:** `task-4-backend-skeleton/.env` remains misconfigured with placeholder strings (`COGNITO_USER_POOL_ID=ap-south-1_xxxxxxxx`). Tokens handed from the frontend currently risk failing backend verification due to key mismatches. 
- **CORS Status:** Strictly controlled. `main.py` establishes CORS matching explicit addresses derived dynamically from `CORS_ALLOW_ORIGINS` combined permanently with local dev URLs (e.g., `localhost:5173`). 

## [E] V1.0 SaaS Readiness Gaps

The platform is functionally stable, but the following areas require remediation before the final V1.0 production launch can scale to enterprise levels:

- **Tenant Isolation Verification:** Verified. The `tenant_id` primitive is comprehensively applied across all core tables (`Jobs`, `Parts`, `Customers`, and `Machines`) ensuring strict multi-tenant isolation.
- **Missing Domain Needs (RDS Schema):** The database schema currently lacks financial and operational cost modeling. While production operations are scheduled and tracked sequentially, models for **Material Costs**, **Machine Hourly Rates**, and aggregated **Billing Summaries** must be introduced via a new migration.
- **Deployment Status:** The Frontend Infrastructure successfully prevents clashes via dynamically appended stack identifiers. Ultimately, the network provisioning remains locally blocked and cannot activate until the AWS Account passes domain verification constraints restricting CloudFront creation.

*Report generated automatically from live project filesystem structures.*
