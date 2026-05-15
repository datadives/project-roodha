# Roodha Frontend

React/Vite frontend for the Roodha manufacturing job planner.

## Local Setup

```powershell
cd job_work_planner\task-5-react-frontend
npm install
npm run dev
```

Required `.env.local` values:

```text
VITE_API_BASE_URL=http://roodha-backend-env.eba-52xsapkh.ap-south-1.elasticbeanstalk.com/api
VITE_COGNITO_REGION=ap-south-1
VITE_COGNITO_USER_POOL_ID=ap-south-1_U3JeTevgw
VITE_COGNITO_CLIENT_ID=3ab798pg0k2p8hp7v6bbtlh4mj
VITE_ENABLE_SELF_SIGNUP=true
VITE_ALLOW_DEV_PASS=true
VITE_DEV_PASS_TOKEN=roodha-dev-test-123
VITE_DEV_TENANT_ID=lalafactory
```

For production builds, set `VITE_ALLOW_DEV_PASS=false` and keep demo login hidden.

## App Flow

1. Owner signs up or logs in through Cognito.
2. Owner provisions workspace and master data.
3. Owner invites Supervisor and Operator users.
4. Supervisor creates/reviews jobs and plans operations.
5. Operator views assigned work and updates progress.
6. Dashboard, kanban, analytics, costing, and CSV exports reflect real backend data.

## Verification

```powershell
npm test -- --run src/pages/LoginPage.test.js src/lib/auth.test.js src/config.test.js
npm run build
```

Browser checks:

- Login/create/recover screens fit on mobile and desktop.
- Jobs can be created without `Section Offline`.
- Analytics shows WIP and costing after real jobs exist.
- Jobs CSV and machine-load CSV export download.
- Operator navigation does not expose owner-only actions.

## UI Notes

Keep labels short inside cards, buttons, and mobile nav. Use tooltips or helper text for details instead of long headings. Error panels should name the failed module and give a direct recovery action.
