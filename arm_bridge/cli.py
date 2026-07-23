from __future__ import annotations

import argparse
import json
import os
import urllib.request


def main():
    parser = argparse.ArgumentParser(description="Send a safe command to the robot arm bridge")
    parser.add_argument("command", choices=["arm", "disarm", "home", "stop", "move"])
    parser.add_argument("--base", type=int)
    parser.add_argument("--shoulder", type=int)
    parser.add_argument("--elbow", type=int)
    parser.add_argument("--gripper", type=int)
    parser.add_argument("--duration-ms", type=int, default=800)
    parser.add_argument("--url", default=os.getenv("ARM_BRIDGE_URL", "http://127.0.0.1:8765"))
    args = parser.parse_args()
    payload = {"command": args.command}
    if args.command == "move":
        payload["joints"] = {k: v for k, v in {
            "base": args.base, "shoulder": args.shoulder,
            "elbow": args.elbow, "gripper": args.gripper,
        }.items() if v is not None}
        payload["duration_ms"] = args.duration_ms
    request = urllib.request.Request(
        args.url.rstrip("/") + "/command",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    token = os.getenv("ARM_BRIDGE_TOKEN")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(request) as response:
        print(response.read().decode())


if __name__ == "__main__":
    main()

