#!/usr/bin/env python3
import argparse
import pathlib
import sys
import urllib.error
import urllib.parse
import urllib.request


class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def parse_args():
    parser = argparse.ArgumentParser(
        description="Read a server-side file through Plex's metadata endpoint"
    )
    parser.add_argument("--url", required=True, help="Plex server origin")
    parser.add_argument("--rating-key", required=True, type=int)
    parser.add_argument("--file", required=True, help="Absolute server-side path")
    parser.add_argument("--token", required=True, help="Plex authentication token")
    parser.add_argument("--output", help="Write response bytes to this local path")
    args = parser.parse_args()

    parsed = urllib.parse.urlsplit(args.url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        parser.error("--url must be an HTTP(S) origin")
    if parsed.path not in ("", "/") or parsed.query or parsed.fragment:
        parser.error("--url must not contain a path, query, or fragment")
    if args.rating_key <= 0:
        parser.error("--rating-key must be greater than zero")
    if not pathlib.PurePosixPath(args.file).is_absolute():
        parser.error("--file must be an absolute POSIX path")
    args.url = args.url.rstrip("/")
    return args


def main():
    args = parse_args()
    file_url = "file://" + urllib.parse.quote(args.file)
    query = urllib.parse.urlencode({"url": file_url})
    endpoint = f"{args.url}/library/metadata/{args.rating_key}/file?{query}"
    request = urllib.request.Request(
        endpoint,
        headers={"X-Plex-Token": args.token},
    )

    try:
        opener = urllib.request.build_opener(NoRedirectHandler)
        with opener.open(request, timeout=15) as response:
            data = response.read()
            print(
                f"HTTP {response.status}: received {len(data)} bytes",
                file=sys.stderr,
            )
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        raise RuntimeError(f"HTTP {exc.code}: {body}") from exc

    if args.output:
        pathlib.Path(args.output).write_bytes(data)
        print(f"wrote {len(data)} bytes to {args.output}", file=sys.stderr)
    else:
        sys.stdout.buffer.write(data)


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
