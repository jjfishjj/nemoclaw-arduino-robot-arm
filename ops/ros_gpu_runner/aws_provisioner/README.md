# AWS ephemeral provisioner adapter

This adapter receives GitHub's `workflow_job` webhook and launches exactly one
EC2 instance when a queued job contains every trusted GPU runner label. It
validates `X-Hub-Signature-256` before parsing the request, obtains a short-lived
registration token, stores it in a job-scoped one-use secret, and starts the
sealed-image systemd service. EC2 user-data contains only that secret's ARN.

The EC2 launch template must pin a reviewed GPU AMI, subnet, security group and
instance profile. Its root EBS mapping must set `DeleteOnTermination=true`.
The Lambda call additionally sets `InstanceInitiatedShutdownBehavior=terminate`,
so the guest service poweroff destroys the instance. Use no inbound security
group rules; the runner needs outbound HTTPS only. The instance profile must
allow `GetSecretValue` and `DeleteSecret` only for
`rover/ephemeral-runner/*`; the boot script fetches the value to `/run` tmpfs
and immediately force-deletes the cloud secret.

Store this JSON in Secrets Manager, not in CloudFormation or the AMI:

```json
{"webhook_secret":"random-webhook-secret","github_token":"fine-grained-token"}
```

The GitHub token requires repository Administration write permission solely to
create runner registration tokens. Prefer a GitHub App installation token in a
production adapter and rotate any stored fallback token. Package `handler.py`
as a zip, upload it to a versioned S3 bucket, and deploy `template.yaml`. Use its
`GitHubWebhookUrl` output as a GitHub `workflow_job` webhook with the same
webhook secret. The Function URL is public by necessity, but every request fails
closed unless its raw body passes GitHub HMAC validation.

CloudWatch alarms should cover Lambda errors, EC2 launch failures, and instances
tagged `Ephemeral=true` older than four hours. The latter is the provider-side
dead-man switch when boot or systemd fails before guest teardown can run.
