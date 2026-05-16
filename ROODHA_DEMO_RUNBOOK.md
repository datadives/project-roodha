# Roodha Demo Runbook

Use this file during the meeting. Keep the tone simple: Roodha is a practical factory job tracker, not a heavy ERP.

## 1. Open These Before The Meeting

Live app:

```text
http://roodha-v1-live-918172959197.s3-website.ap-south-1.amazonaws.com
```

Backend health:

```text
http://roodha-backend-env.eba-52xsapkh.ap-south-1.elasticbeanstalk.com/api/ready
```

GitHub branch:

```text
https://github.com/roshandatadive/project-roodha/tree/codex/saas-stabilization-live
```

Pull request page:

```text
https://github.com/roshandatadive/project-roodha/pull/new/codex/saas-stabilization-live
```

## 2. One-Minute Opening

Say:

```text
Roodha is a lightweight SaaS manufacturing job planner for small and mid-sized factories.

Many factories still track production jobs using Excel, WhatsApp, paper registers, or memory. That creates missed due dates, unclear responsibility, poor machine visibility, and weak costing control.

Roodha gives the factory a live job board, master data, machine load visibility, role-based access, analytics, and CSV exports.
```

Short version:

```text
Roodha helps a factory know what job is running, where it is stuck, who owns it, and what value is currently sitting on the shopfloor.
```

## 3. Architecture Talk Track

Say:

```text
The frontend is a React app deployed on AWS S3.
The backend is FastAPI deployed on AWS Elastic Beanstalk.
The production database is PostgreSQL on AWS RDS.
Authentication and OTP are handled by AWS Cognito.

The product has three roles:
Owner manages the workspace, users, master data, jobs, costing, and analytics.
Supervisor plans jobs and reviews shopfloor work.
Operator updates assigned operations and progress.
```

Important line:

```text
The backend enforces role and tenant security. The UI is not the only security layer.
```

## 4. Demo Flow

### Step 1: Login Screen

Show:

- Login
- New account
- Reset password
- Cognito Guard text

Say:

```text
This is the secure entry point. Users can log in, create a workspace, or recover access. Authentication is connected to AWS Cognito.
```

If OTP does not arrive:

```text
Cognito OTP is configured. For fully reliable production email, SES sender/domain verification and production access approval are still required. For today, I can use a prepared account to show the product flow.
```

### Step 2: Dashboard

Show:

- Job board / Kanban
- Machine load
- Notifications
- Navigation

Say:

```text
The dashboard is the daily production control screen. The owner or supervisor can see active jobs, machine pressure, and operational alerts without chasing updates manually.
```

### Step 3: Master Data

Show:

- Customers
- Parts
- Machines
- Shifts
- Workers

Say:

```text
Before a factory creates production jobs, it defines reusable master data. This avoids repeated manual entry and keeps jobs consistent.
```

### Step 4: Create A Job

Explain:

```text
A job connects customer, part, quantity, due date, priority, and operations. Once created, the job becomes visible in planning, dashboard, and analytics.
```

If job creation works:

```text
The job is now stored in the live RDS database and can be tracked through its production stages.
```

If job creation fails:

```text
This usually means either a required master-data field is missing or the backend returned a validation error. The important thing is the app now fails visibly instead of silently. We can inspect the exact API error and fix the data or config.
```

### Step 5: Jobs / Kanban

Say:

```text
This replaces manual WhatsApp follow-ups. Jobs move through statuses, and supervisors can quickly see what is waiting, running, or completed.
```

### Step 6: Analytics

Show:

- Total WIP
- Late jobs
- Bottleneck machines
- Costing summary

Say:

```text
Analytics is based on database-backed jobs. It helps management understand WIP pressure, overdue work, bottlenecks, and estimated value on the shopfloor.
```

If analytics is empty:

```text
Analytics becomes meaningful after jobs have quantity, operations, machine assignment, and status movement. Empty state is expected when there is no active production data for that tenant.
```

### Step 7: CSV Export

Say:

```text
Factories still need reports for Excel, accounts, or management reviews. CSV export keeps the product practical for real-world factory operations.
```

## 5. What Was Stabilized

Say:

```text
Recently we stabilized the live AWS environment and made the system demo-ready.
```

Mention:

- Backend deployed on Elastic Beanstalk
- Frontend deployed on S3
- PostgreSQL RDS connected
- Cognito signup, OTP, recovery, and role setup repaired
- CORS fixed between frontend and backend
- Database readiness endpoint added
- Role source of truth hardened on backend
- Supervisor/operator invite flow improved
- OTP resend cooldown added
- CSV exports verified
- Mobile login UI cleaned up
- Backend and frontend tests added
- GitHub branch pushed for review

## 6. If Something Breaks During Demo

### If OTP does not arrive

Say:

```text
The Cognito configuration is fixed, but production-grade email reliability needs SES production access and a verified sender/domain. This is an AWS email-deliverability step, not core app logic. For the demo, I will use a prepared account.
```

### If backend says unable to connect

Say:

```text
Let me check the health endpoint. The backend has a readiness endpoint that verifies the RDS database and required tables.
```

Open:

```text
http://roodha-backend-env.eba-52xsapkh.ap-south-1.elasticbeanstalk.com/api/ready
```

If it shows ready:

```text
Backend and database are healthy. This is likely a frontend session/auth state issue, so I will clear the session and sign in again.
```

### If Section Offline appears

Say:

```text
This is the app's graceful failure screen. Instead of crashing the whole product, one module is isolated and the rest of the workspace remains usable.
```

Then click:

- Reset section
- If needed, Reload Workspace

### If analytics shows zero

Say:

```text
Analytics depends on live job data. WIP and costing update when jobs have operations, quantities, machine assignment, and active statuses.
```

### If invite fails

Say:

```text
Invites depend on Cognito admin permissions and email delivery. The backend now handles duplicate emails and role mapping more safely. If an email already belongs to another workspace, the system blocks it to prevent cross-tenant confusion.
```

### If manager asks whether this is production-ready

Say:

```text
This is V1 demo-ready and live on AWS. The core flow is working. For full production readiness, the remaining items are SES production email approval, custom domain with HTTPS, deeper E2E role tests, and monitoring.
```

## 7. Common Questions And Answers

Question:

```text
Is this multi-tenant?
```

Answer:

```text
Yes. Each workspace has a tenant ID. Backend and database logic enforce tenant scoping so one factory does not read another factory's data.
```

Question:

```text
Can operators access owner features?
```

Answer:

```text
No. The product uses role-based access. Owner, Supervisor, and Operator have different permissions, and backend checks enforce those roles.
```

Question:

```text
Why not build a full ERP?
```

Answer:

```text
Roodha starts with the highest pain area: daily job tracking. The goal is to be lightweight, fast, and usable by factories that are not ready for a heavy ERP.
```

Question:

```text
Is the data real?
```

Answer:

```text
Yes. The live backend is connected to AWS RDS PostgreSQL. Jobs, master data, analytics, and exports are database-backed.
```

Question:

```text
What is the next milestone?
```

Answer:

```text
Pilot with one real factory, add SES production email, attach a custom domain, monitor usage, and improve scheduling automation after user feedback.
```

## 8. Closing Statement

Say:

```text
Roodha is designed to be practical first. It helps a factory digitize the daily production board, reduce manual follow-ups, track work-in-progress, and understand bottlenecks and costing.

For V1, the focus is reliability, simple workflows, and clear factory value. After pilot validation, we can expand into scheduling automation, deeper costing, and machine-level optimization.
```

## 9. Final Checklist Before Presenting

- Open live app.
- Open backend `/api/ready`.
- Keep GitHub branch link ready.
- Use a prepared account if OTP is slow.
- Do not over-explain technical problems.
- Keep returning to business value: job visibility, WIP, bottlenecks, costing, exports.

