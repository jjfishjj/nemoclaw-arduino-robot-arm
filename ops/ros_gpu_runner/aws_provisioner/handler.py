"""AWS Lambda adapter for one-job GitHub Actions GPU runners.

API Gateway must pass the unmodified request body. Secrets Manager stores a
JSON object with ``webhook_secret`` and ``github_token``. The token needs only
repository Administration write permission to mint runner registration tokens.
"""
import base64
import hashlib
import hmac
import json
import os
import urllib.error
import urllib.request

import boto3


REQUIRED_LABELS = {"self-hosted", "linux", "x64", "ros2-jazzy", "gpu", "gazebo", "ephemeral"}


def _secret():
    value = boto3.client("secretsmanager").get_secret_value(
        SecretId=os.environ["GITHUB_SECRET_ARN"]
    )["SecretString"]
    return json.loads(value)


def _body(event):
    value = event.get("body") or ""
    return base64.b64decode(value) if event.get("isBase64Encoded") else value.encode()


def _authorized(headers, body, secret):
    signature = next(
        (value for key, value in headers.items() if key.lower() == "x-hub-signature-256"), ""
    )
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature, expected)


def _registration_token(owner, repo, github_token):
    request = urllib.request.Request(
        f"https://api.github.com/repos/{owner}/{repo}/actions/runners/registration-token",
        data=b"{}",
        method="POST",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {github_token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "rover-ephemeral-runner-provisioner",
        },
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read())["token"]


def _boot_secret(repository_url, runner_name, token, job_id):
    value = "\n".join(
        (f"GITHUB_URL={repository_url}", f"RUNNER_TOKEN={token}", f"RUNNER_NAME={runner_name}",
         "EPHEMERAL_RUNNER=1", f"RUNNER_VERSION={os.environ['RUNNER_VERSION']}",
         f"RUNNER_SHA256={os.environ['RUNNER_SHA256']}",
         "EPHEMERAL_LOG_DIR=/mnt/runner-diagnostics")
    )
    return boto3.client("secretsmanager").create_secret(
        Name=f"rover/ephemeral-runner/{job_id}", SecretString=value,
        Description="Single-use GitHub runner boot credentials",
    )["ARN"]


def _user_data(secret_arn):
    # User-data contains only an ARN. The instance role reads the value once,
    # stores it on tmpfs, and force-deletes the single-use secret.
    return f"""#!/bin/bash
set -euo pipefail
install -d -m 0700 /run/secrets
aws secretsmanager get-secret-value --secret-id '{secret_arn}' --query SecretString --output text >/run/secrets/ephemeral-runner.env
chmod 0600 /run/secrets/ephemeral-runner.env
aws secretsmanager delete-secret --secret-id '{secret_arn}' --force-delete-without-recovery
systemctl start ephemeral-gpu-runner.service
"""


def _launch(payload, token):
    repository = payload["repository"]
    job = payload["workflow_job"]
    runner_name = f"rover-gpu-{payload['installation']['id']}-{job['id']}"
    secret_arn = _boot_secret(repository["html_url"], runner_name, token, job["id"])
    response = boto3.client("ec2").run_instances(
        LaunchTemplate={"LaunchTemplateId": os.environ["LAUNCH_TEMPLATE_ID"]},
        ClientToken=f"github-workflow-job-{job['id']}",
        MinCount=1,
        MaxCount=1,
        InstanceInitiatedShutdownBehavior="terminate",
        UserData=_user_data(secret_arn),
        TagSpecifications=[{
            "ResourceType": "instance",
            "Tags": [
                {"Key": "Name", "Value": runner_name},
                {"Key": "GitHubRepository", "Value": repository["full_name"]},
                {"Key": "GitHubWorkflowJobId", "Value": str(job["id"])},
                {"Key": "Ephemeral", "Value": "true"},
            ],
        }],
    )
    return response["Instances"][0]["InstanceId"]


def lambda_handler(event, _context):
    body = _body(event)
    secret = _secret()
    if not _authorized(event.get("headers") or {}, body, secret["webhook_secret"]):
        return {"statusCode": 401, "body": "invalid signature"}
    event_name = next(
        (value for key, value in (event.get("headers") or {}).items()
         if key.lower() == "x-github-event"), None
    )
    if event_name not in (None, "workflow_job"):
        return {"statusCode": 202, "body": "ignored event"}
    payload = json.loads(body)
    job = payload.get("workflow_job") or {}
    labels = set(job.get("labels") or [])
    if payload.get("action") != "queued" or not REQUIRED_LABELS.issubset(labels):
        return {"statusCode": 202, "body": "ignored job"}
    repository = payload["repository"]
    token = _registration_token(
        repository["owner"]["login"], repository["name"], secret["github_token"]
    )
    instance_id = _launch(payload, token)
    return {"statusCode": 202, "body": json.dumps({"instance_id": instance_id})}
