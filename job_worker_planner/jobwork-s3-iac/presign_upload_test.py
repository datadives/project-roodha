# presign_upload_test.py
# Fixed: Generates a presigned PUT URL using signature v4 and regional endpoint, then uploads a test object.

import boto3
from botocore.client import Config
import requests
from datetime import datetime, timezone

# Configuration
BUCKET = "jobwork-app-files-dev"   # from your stack outputs
TENANT = "T001"
MODULE = "uploads"
REGION = "ap-south-1"

def main():
    # Create S3 client with explicit signature version and regional endpoint
    s3 = boto3.client(
        "s3",
        region_name=REGION,
        config=Config(signature_version="s3v4", s3={'addressing_style': 'virtual'}),
        endpoint_url=f"https://s3.{REGION}.amazonaws.com"
    )

    # build object key: tenant/module/yyyy/mm/dd/filename (use UTC date)
    today = datetime.now(timezone.utc)
    key = f"{TENANT}/{MODULE}/{today.year}/{today.month:02d}/{today.day:02d}/test-presign.txt"

    print("Generating presigned PUT URL for:", key)
    put_url = s3.generate_presigned_url(
        "put_object",
        Params={"Bucket": BUCKET, "Key": key, "ContentType": "text/plain"},
        ExpiresIn=3600
    )
    print("Presigned URL (first 200 chars):", put_url[:200] + ("..." if len(put_url) > 200 else ""))

    # Upload small text
    data = b"Hello from presign test\n"
    headers = {"Content-Type": "text/plain"}
    print("Uploading test data via requests.put() ...")
    resp = requests.put(put_url, data=data, headers=headers, timeout=30)
    print("Upload HTTP status code:", resp.status_code)
    if resp.status_code not in (200, 201):
        print("Upload response headers:", resp.headers)
        print("Upload response text:", resp.text)
        raise SystemExit("Upload failed")

    # Verify upload by calling head_object
    print("Verifying object exists via S3 HeadObject ...")
    try:
        meta = s3.head_object(Bucket=BUCKET, Key=key)
        print("HeadObject successful. ContentLength:", meta.get("ContentLength"), "LastModified:", meta.get("LastModified"))
    except Exception as e:
        print("HeadObject failed:", e)
        raise

    print("Test completed successfully. Object key:", key)

if __name__ == "__main__":
    main()
