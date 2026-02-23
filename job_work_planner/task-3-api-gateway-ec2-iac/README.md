
# Task-3: API Gateway → EC2 Backend (AWS CDK | Production Ready)
 
## 1. Purpose of This Task
 
This task implements a **production-grade backend entry point** for the Job Work Planner system.
 
The goal is to:
- Run the backend on **EC2**
- Expose it securely via **Amazon API Gateway**
- Control access using **JWT (Cognito)**
- Apply **throttling, logging, and security best practices**
- Build everything using **Infrastructure as Code (AWS CDK)**
 
This task is **fully completed, deployed, verified, and tested end-to-end**.
 
---
 
## 2. High-Level Architecture (Easy Explanation)
 
Think of this setup like a secure office building:
 
- **API Gateway** → Security gate + traffic controller  
- **Cognito JWT** → ID card verification  
- **EC2** → Actual office where work happens  
- **SSM** → Secure remote access (no keys needed)
User / Client | | HTTPS Request v API Gateway (HTTP API) | | JWT Verified + Throttled v EC2 Instance (Amazon Linux 2) | | Apache HTTP Server v Backend Response
Copy code
 
---
 
## 3. What Is Implemented (Clear Checklist)
 
### Infrastructure
- EC2 instance (Amazon Linux 2)
- Apache HTTP server installed and running
- IAM Instance Profile attached
- AWS Systems Manager (SSM) enabled
 
### API Gateway
- HTTP API (low cost, low latency)
- Routes mapped to EC2 backend
- CloudWatch access logs enabled
- Auto-deployment enabled
 
### Security
- Cognito JWT Authorizer attached
- Protected business routes
- Public health endpoint only
- IAM least-privilege followed
 
### Reliability
- Throttling configured
- Burst protection enabled
- End-to-end tested using `curl`
 
---
 
## 4. API Routes
 
### Public (No Authentication)
| Method | Endpoint |
|------|----------|
| GET | `/health` |
 
### Protected (JWT Required)
| Endpoint |
|---------|
| `/auth/{proxy+}` |
| `/masters/{proxy+}` |
| `/jobs/{proxy+}` |
| `/attachments/{proxy+}` |
| `/reports/{proxy+}` |
 
---
 
## 5. Throttling Configuration
 
Configured at API Gateway stage level:
 
- **Rate limit:** 100 requests/second  
- **Burst limit:** 200 requests  
 
This protects the EC2 backend from overload or misuse.
 
---
 
## 6. Technology Stack
 
- AWS CDK (Python)
- Amazon EC2 (Amazon Linux 2)
- Amazon API Gateway (HTTP API v2)
- Amazon Cognito (JWT)
- AWS CloudWatch Logs
- AWS Systems Manager (SSM)
- Apache HTTP Server
 
---
 
## 7. Folder Structure
task-3-api-gateway-ec2-iac/ │ ├── api_gateway_stack.py   # API Gateway, JWT, throttling, logging ├── ec2_stack.py           # EC2 instance, IAM, security group ├── app.py                 # CDK app entry point ├── cdk.json               # CDK configuration ├── requirements.txt       # Python dependencies ├── README.md              # Documentation └── tests/                 # Reserved for future tests
Copy code
 
---
 
## 8. Deployment Commands
 
### Activate virtual environment
```bash
.venv\Scripts\activate
Synthesize CloudFormation templates
Copy code
Bash
cdk synth
Deploy all stacks
Copy code
Bash
cdk deploy --all --require-approval never
9. Deployment Outputs
After deployment, CDK provides:
EC2 Public IP
API Gateway Base URL
Example:
Copy code
 
https://xxxxxxxx.execute-api.ap-south-1.amazonaws.com
10. Verification Performed
✔ EC2 instance reachable internally
✔ Apache server running and responding
✔ API Gateway routes forwarding correctly
✔ JWT authorizer attached successfully
✔ Throttling enforced
✔ CloudWatch logs generated
✔ SSM session access working
✔ No SSH keys required
✔ No manual AWS console steps needed
 