"""
antigravity_launch.py
---------------------
Project Roodha V1.0 Launch Automation Script.

This script:
1. Loads DATABASE_URL and AWS_REGION from the backend .env file.
2. Applies the 'quoted_price' column schema update via psycopg2.
3. Builds the production bundle for the React frontend.
4. Syncs the build to the 'roodha-staging' S3 bucket.
5. Invalidates the CloudFront cache automatically.
6. Presents the Live Dashboard link.
"""

import os
import subprocess
import sys
import json

# Define exact local paths to avoid workspace context errors
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(ROOT_DIR, "task-4-backend-skeleton")
FRONTEND_DIR = os.path.join(ROOT_DIR, "task-5-react-frontend")
ENV_PATH = os.path.join(BACKEND_DIR, ".env")

S3_BUCKET = "roodha-staging"
CLOUDFRONT_DOMAIN = "d1k4eogtw67m2o.cloudfront.net" # Placeholder, we will fetch the live HTTPS link

def print_step(title):
    print(f"\n" + "="*50)
    print(f"🚀 {title}")
    print("="*50)

def load_env_vars():
    print_step("Loading Environment")
    if not os.path.exists(ENV_PATH):
        print(f"[ERROR] Environment file not found at: {ENV_PATH}")
        sys.exit(1)
        
    env_data = {}
    with open(ENV_PATH, "r") as file:
        for line in file:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                env_data[key.strip()] = value.strip()
                
    db_url = env_data.get("DATABASE_URL")
    region = env_data.get("AWS_REGION", "ap-south-1")
    
    if not db_url:
        print("[ERROR] DATABASE_URL missing from .env")
        sys.exit(1)
        
    print(f"[OK] Database URL: {db_url.split('@')[-1]}")
    print(f"[OK] AWS Region: {region}")
    return db_url, region

def update_database(db_url):
    print_step("Database Upgrade (SQL)")
    try:
        import psycopg2
        # Connect strictly to perform the DDL
        conn = psycopg2.connect(db_url)
        conn.autocommit = True
        cur = conn.cursor()
        
        # Add column if it doesn't already exist
        query = """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name='jobs' AND column_name='quoted_price'
            ) THEN
                ALTER TABLE jobs ADD COLUMN quoted_price NUMERIC(10, 2);
            END IF;
        END
        $$;
        """
        cur.execute(query)
        print("[OK] Executed: ALTER TABLE jobs ADD COLUMN quoted_price NUMERIC(10, 2);")
        cur.close()
        conn.close()
    except ImportError:
        print("[ERROR] psycopg2 is not installed in the current environment.")
        print("Please run: pip install psycopg2-binary")
        sys.exit(1)
    except Exception as e:
        print(f"[ERROR] Database upgrade failed: {e}")
        sys.exit(1)

def build_frontend():
    print_step("Building Production React Frontend")
    if not os.path.exists(FRONTEND_DIR):
        print(f"[ERROR] Frontend directory not found at: {FRONTEND_DIR}")
        sys.exit(1)
        
    print(f"[INFO] Running 'npm run build' in {FRONTEND_DIR}...")
    try:
        # Use shell=True for npm on Windows
        result = subprocess.run(
            ["npm", "run", "build"], 
            cwd=FRONTEND_DIR, 
            shell=True, 
            check=True,
            stdout=sys.stdout,
            stderr=sys.stderr
        )
        print("[OK] Frontend built successfully.")
    except subprocess.CalledProcessError:
        print("[ERROR] npm build failed.")
        sys.exit(1)

def deploy_to_aws(region):
    print_step("AWS Deployment: S3 Sync & CloudFront Invalidation")
    dist_dir = os.path.join(FRONTEND_DIR, "dist")
    
    if not os.path.exists(dist_dir):
        print(f"[ERROR] Distribution output not found at: {dist_dir}")
        sys.exit(1)
        
    print(f"[INFO] Syncing {dist_dir} to s3://{S3_BUCKET}...")
    try:
        subprocess.run(
            ["aws", "s3", "sync", str(dist_dir), f"s3://{S3_BUCKET}", "--delete", "--region", region],
            shell=True,
            check=True,
            stdout=subprocess.DEVNULL
        )
        print(f"[OK] Synced content to s3://{S3_BUCKET}")
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] AWS S3 Sync failed. Are AWS credentials configured? {e}")
        sys.exit(1)

    print("[INFO] Fetching CloudFront Distribution ID...")
    try:
        # Fetch distributions JSON
        cf_raw = subprocess.check_output(
            ["aws", "cloudfront", "list-distributions", "--query", "DistributionList.Items[*].{Id:Id,Origins:Origins.Items[*].DomainName,Domain:DomainName}", "--output", "json"],
            shell=True,
            text=True
        )
        distributions = json.loads(cf_raw)
        
        target_dist_id = None
        target_domain = None
        
        for dist in distributions:
            # Check if any origin matches our S3 bucket string
            origins = dist.get("Origins", [])
            for origin in origins:
                if S3_BUCKET in origin:
                    target_dist_id = dist.get("Id")
                    target_domain = dist.get("Domain")
                    break
            if target_dist_id:
                break
                
        if not target_dist_id:
            print(f"[WARNING] Could not automatically find an active CloudFront distribution for '{S3_BUCKET}'. Skipping invalidation.")
            return f"http://{S3_BUCKET}.s3-website-{region}.amazonaws.com"
            
        print(f"[INFO] Found CloudFront Distribution: {target_dist_id} ({target_domain})")
        print("[INFO] Creating Invalidation for /* ...")
        
        subprocess.run(
            ["aws", "cloudfront", "create-invalidation", "--distribution-id", target_dist_id, "--paths", "/*"],
            shell=True,
            check=True,
            stdout=subprocess.DEVNULL
        )
        print("[OK] Cache invalidation requested successfully.")
        return f"https://{target_domain}"
        
    except Exception as e:
        print(f"[WARNING] CloudFront cache invalidation failed: {e}")
        return f"http://{S3_BUCKET}.s3-website-{region}.amazonaws.com"

def __main__():
    db_url, region = load_env_vars()
    update_database(db_url)
    build_frontend()
    live_url = deploy_to_aws(region)
    
    print_step("LAUNCH DASHBOARD")
    print("Project Roodha V1.0 is live and fully synchronized.")
    print(f"👉 Live URL: {live_url}")
    print("="*50 + "\n")

if __name__ == "__main__":
    __main__()
