"""
CLI Helper to automatically configure TigerGraph Cloud credentials and generate REST++ secret.
Usage:
    python -m tools.setup_tg_env --host <HOST_URL> --password <PASSWORD> [--username <USER>]
"""

import os
import sys
import argparse
from pathlib import Path
from dotenv import dotenv_values


def update_env_file(updates: dict):
    env_path = Path(".env")
    current = {}
    if env_path.is_file():
        current = dotenv_values(env_path)

    current.update(updates)

    lines = []
    for k, v in current.items():
        lines.append(f"{k}={v if v is not None else ''}")

    with open(env_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"[SUCCESS] Updated {env_path.resolve()} with {list(updates.keys())}")


def main():
    parser = argparse.ArgumentParser(description="Configure TigerGraph Cloud credentials into .env")
    parser.add_argument("--host", required=True, help="TigerGraph Host URL (e.g. https://xxx.i.tgcloud.io or http://127.0.0.1:14240)")
    parser.add_argument("--password", required=True, help="TigerGraph password")
    parser.add_argument("--username", default="tigergraph", help="TigerGraph username (default: tigergraph)")
    parser.add_argument("--graph", default="FraudGraph", help="Graph name (default: FraudGraph)")
    parser.add_argument("--alias", default="fraud_secret", help="Secret alias to create (default: fraud_secret)")

    args = parser.parse_args()

    host = args.host.strip().rstrip("/")
    if not host.startswith("http://") and not host.startswith("https://"):
        host = f"https://{host}"

    print(f"Connecting to TigerGraph host: {host} as user '{args.username}'...")

    try:
        import pyTigerGraph as tg
        conn = tg.TigerGraphConnection(
            host=host,
            graphname=args.graph,
            username=args.username,
            password=args.password
        )

        # Attempt to auto-generate secret
        print(f"Generating REST++ secret with alias '{args.alias}'...")
        try:
            secret = conn.createSecret(args.alias)
            print(f"[SUCCESS] Generated REST++ Secret: {secret}")
        except Exception as sec_err:
            print(f"[NOTE] Secret generation note: {sec_err}")
            # Try to get token directly with password
            try:
                token = conn.getToken(conn.createSecret())
                secret = token[0] if isinstance(token, tuple) else ""
            except Exception:
                secret = ""

        # Update .env
        updates = {
            "TG_HOST": host,
            "TG_GRAPHNAME": args.graph,
            "TG_USERNAME": args.username,
            "TG_PASSWORD": args.password,
        }
        if secret:
            updates["TG_SECRET"] = secret

        update_env_file(updates)
        print("\nTigerGraph connection successfully configured in .env!")

    except Exception as e:
        print(f"[ERROR] Failed to configure TigerGraph: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
