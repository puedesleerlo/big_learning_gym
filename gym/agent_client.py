"""Small HTTP client for every Gym API action: ``python -m gym.agent_client``."""

import argparse
import json
import os
import sys
from contextlib import ExitStack
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from dotenv import load_dotenv


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("method", help="GET, POST, PUT, PATCH, DELETE, or capabilities/schema")
    result.add_argument("path", nargs="?", help="API path, for example /api/overview")
    result.add_argument("--base-url", default=os.getenv("GYM_BASE_URL", "http://127.0.0.1:8787"))
    result.add_argument("--json", dest="json_file", metavar="FILE", help="JSON request file; '-' reads stdin")
    result.add_argument(
        "--field", action="append", default=[], metavar="KEY=VALUE", help="Multipart form field"
    )
    result.add_argument("--file", action="append", default=[], metavar="FIELD=PATH", help="Upload a file")
    result.add_argument(
        "--output", metavar="PATH", help="Save response bytes, e.g. schedule.ics or schema.json"
    )
    result.add_argument("--timeout", type=float, default=60)
    return result


def _pair(value):
    key, sep, content = value.partition("=")
    if not sep or not key:
        raise ValueError("Form fields and uploads use KEY=VALUE")
    return key, content


def main(argv=None):
    load_dotenv()
    args = parser().parse_args(argv)
    method = args.method.upper()
    path = args.path
    if method in {"CAPABILITIES", "SCHEMA"}:
        path, method = "/api/agent/" + method.lower(), "GET"
    token = os.getenv("GYM_ACCESS_TOKEN", "")
    try:
        if method not in {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}:
            raise ValueError("Unsupported HTTP method")
        if not path or not path.startswith("/api/") or path.startswith("//"):
            raise ValueError("Supply a relative /api/ path")
        base = urlsplit(args.base_url)
        if base.scheme not in {"http", "https"} or not base.hostname or base.username or base.password:
            raise ValueError("Base URL must be http(s), with no credentials")
        if base.query or base.fragment or base.path not in {"", "/"}:
            raise ValueError("Base URL must contain only the server origin")
        if args.json_file and (args.file or args.field):
            raise ValueError("Choose JSON or multipart fields/files, not both")
        headers = {"Authorization": "Bearer " + token} if token else {}
        kwargs = {}
        if args.json_file:
            raw = sys.stdin.read() if args.json_file == "-" else Path(args.json_file).read_text()
            kwargs["json"] = json.loads(raw)
        with ExitStack() as stack:
            if args.field:
                kwargs["data"] = dict(_pair(field) for field in args.field)
            if args.file:
                kwargs["files"] = [
                    (key, (Path(filename).name, stack.enter_context(Path(filename).open("rb"))))
                    for key, filename in (_pair(value) for value in args.file)
                ]
            client = stack.enter_context(
                httpx.Client(
                    base_url=args.base_url.rstrip("/"),
                    timeout=args.timeout,
                    headers=headers,
                    follow_redirects=False,
                )
            )
            response = client.request(method, path, **kwargs)
        # Never log headers or credentials, including when reporting transport failures.
        if response.is_error or response.is_redirect:
            detail = response.text
            if token:
                detail = detail.replace(token, "[redacted]")
            print(f"HTTP {response.status_code}: {detail}", file=sys.stderr)
            return 1
        response_text = response.text.replace(token, "[redacted]") if token else response.text
        if args.output:
            Path(args.output).write_bytes(response_text.encode() if token else response.content)
        else:
            try:
                print(json.dumps(json.loads(response_text), indent=2, ensure_ascii=False))
            except ValueError:
                print(response_text)
        return 0
    except (ValueError, OSError, httpx.HTTPError) as error:
        message = str(error)
        if token:
            message = message.replace(token, "[redacted]")
        print(message, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
