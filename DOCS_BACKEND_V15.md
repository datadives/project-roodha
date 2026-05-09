# PROJECT ROODHA: BACKEND MASTER DOC (v1.5.7)

## FastAPI Architecture
The Project Roodha backend is built on **FastAPI (Python 3.11+)**, providing a fully asynchronous, non-blocking execution model. This aligns directly with the **"System Architecture"** section of the official `ROADMAP.md` (Stage 1). The framework leverages asynchronous SQLAlchemy 2.0 connected to a PostgreSQL 15+ database on AWS RDS, ensuring high throughput for industrial IoT and shop-floor requests.

## Multi-Tenancy & X-Tenant-ID Logic
To satisfy the "Industrial Hardening" (Stage 2) requirements from the Roadmap, the system enforces strict data isolation via **Row-Level Security (RLS)** and Application Context constraints. 
Every API request must include an `X-Tenant-ID` header. The backend validates this header against the verified AWS Cognito JWT's `custom:tenant_id` claim using the `JWTAuthMiddleware`. If the ID matches, it populates the `tenant_id_context` ContextVar, automatically scoping all subsequent database queries via the `TenantAuditMixin`.

## Industrial Intelligence: The Alert Priority Engine
In support of the "Proactive Delay Guard" capabilities, the backend computes an `alert_priority` at runtime. The engine dynamically evaluates the `due_date` of active jobs. Priorities are calculated as follows:
- **CRITICAL**: The job is overdue.
- **HIGH**: Due within the next 24 hours.
- **NORMAL**: Due beyond 24 hours.
These signals are exposed via the API and drive the frontend's color-coded warnings, preventing shop-floor bottlenecks before they occur. 
