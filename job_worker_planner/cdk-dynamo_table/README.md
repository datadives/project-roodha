# Task 1 – DynamoDB Multi-Tenant Tables (IaC)

## Overview
This task provisions the **initial DynamoDB tables** required for the JobWork Planner application using **Infrastructure as Code (AWS CDK – Python)**.

The objective is to ensure:
- Consistent infrastructure across environments
- A clean **multi-tenant SaaS design**
- Production-ready, scalable database setup

---

## Why DynamoDB?
DynamoDB was chosen because:
- The application is **multi-tenant**
- Data access is key-based (tenant → users)
- It scales automatically
- PAY_PER_REQUEST billing removes capacity planning

---

## Tables Created

### 1. Tenant Table (`tenant`)
Stores factory / company level information.

**Primary Key**
- `tenant_id` (STRING, UUID)

**Attributes**
- `name` – tenant name
- `code` – short readable code (e.g. `DD-DEMO`)
- `created_at` – creation timestamp

**Purpose**
- Root entity for multi-tenancy
- Every factory/company is represented as one tenant

---

### 2. Users Table (`users`)
Stores users belonging to a tenant.

**Primary Key**
- Partition Key: `tenant_id` (STRING)
- Sort Key: `user_id` (STRING, UUID)

**Attributes**
- `cognito_sub` – maps user to AWS Cognito
- `name`
- `email`
- `role` – OWNER / SUPERVISOR / OPERATOR
- `created_at`
- `updated_at`

**Purpose**
- Groups users under a tenant
- Enables efficient queries like:
  - “Get all users for a tenant”
- Ensures strict tenant isolation

---

## Multi-Tenancy Design
- Every record is scoped by `tenant_id`
- Application logic ensures users can only access their tenant’s data
- Design supports future scaling without schema changes

---

## Infrastructure Details
- **IaC Tool:** AWS CDK (Python)
- **Billing Mode:** PAY_PER_REQUEST
- **Removal Policy:** DESTROY (development only)

⚠️ In production, removal policy will be changed to `RETAIN`.

---

## Project Structure
# Task 1 – DynamoDB Multi-Tenant Tables (IaC)

## Overview
This task provisions the **initial DynamoDB tables** required for the JobWork Planner application using **Infrastructure as Code (AWS CDK – Python)**.

The objective is to ensure:
- Consistent infrastructure across environments
- A clean **multi-tenant SaaS design**
- Production-ready, scalable database setup

---

## Why DynamoDB?
DynamoDB was chosen because:
- The application is **multi-tenant**
- Data access is key-based (tenant → users)
- It scales automatically
- PAY_PER_REQUEST billing removes capacity planning

---

## Tables Created

### 1. Tenant Table (`tenant`)
Stores factory / company level information.

**Primary Key**
- `tenant_id` (STRING, UUID)

**Attributes**
- `name` – tenant name
- `code` – short readable code (e.g. `DD-DEMO`)
- `created_at` – creation timestamp

**Purpose**
- Root entity for multi-tenancy
- Every factory/company is represented as one tenant

---

### 2. Users Table (`users`)
Stores users belonging to a tenant.

**Primary Key**
- Partition Key: `tenant_id` (STRING)
- Sort Key: `user_id` (STRING, UUID)

**Attributes**
- `cognito_sub` – maps user to AWS Cognito
- `name`
- `email`
- `role` – OWNER / SUPERVISOR / OPERATOR
- `created_at`
- `updated_at`

**Purpose**
- Groups users under a tenant
- Enables efficient queries like:
  - “Get all users for a tenant”
- Ensures strict tenant isolation

---

## Multi-Tenancy Design
- Every record is scoped by `tenant_id`
- Application logic ensures users can only access their tenant’s data
- Design supports future scaling without schema changes

---

## Infrastructure Details
- **IaC Tool:** AWS CDK (Python)
- **Billing Mode:** PAY_PER_REQUEST
- **Removal Policy:** DESTROY (development only)

⚠️ In production, removal policy will be changed to `RETAIN`.

---

## Project Structure
cdk-demo/
├── app.py
├── dynamodb_stack.py
├── cdk.json
├── requirements.txt
└── README.md





---

## Deployment Commands
```bash
cdk bootstrap
cdk synth
cdk deploy


---

Verification

Tables verified using AWS CLI

Key schema validated

Sample items inserted and scanned successfully

Status

✅ DynamoDB tables created using IaC
✅ Multi-tenant design verified
✅ Ready for application integration

Author

Roshan Sah
Software / Cloud Engineering Intern
2025
