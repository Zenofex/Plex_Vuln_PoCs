# Framework Route Injection into Private Plug-in RPC

## Summary

Plex Framework in `1.43.3.10828-00f62d37d` allows a query parameter to replace
an identically named route variable. The System agent service calls its agent
validation function but continues when validation returns an error. A crafted
`identifier` therefore replaces the intended agent name with a complete internal
messaging path, and a fragment marker truncates the route's appended suffix.

The PoC invokes LocalMedia's private `MessageKit:ReadTags` function with a
client-selected absolute file path. Build `1.43.3.10861-07dfddaeb` returns the
agent-validation result and prevents query parameters from overwriting route
variables.

## Classification

- CVE: not assigned as of 2026-09-10
- Primary weakness: CWE-863, Incorrect Authorization
- Related weakness: CWE-20, Improper Input Validation
- Affected build confirmed: `1.43.3.10828-00f62d37d`
- Fixed build confirmed: `1.43.3.10861-07dfddaeb`
- Authentication observed: no token required in the unclaimed local lab

## Technical Details

The injected identifier has this decoded structure:

```text
com.plexapp.agents.localmedia/messaging/function/
<base64 MessageKit:ReadTags>/<Cerealizer argument list>/<empty kwargs>#
```

The request reaches:

```text
POST /system/agents/tv.plex.agents.movie/searchOne
```

On the vulnerable build, a tagged MP3 fixture produced:

```json
{"artist": ["lab-only"], "title": ["PLEX_RPC_PYTHON_91A7"]}
```

The fixed build returned `Agent not found`. This establishes unauthorized
private function invocation and file metadata access. It does not establish
arbitrary file-content disclosure for files that LocalMedia cannot parse.

## Impact

An unauthenticated local-network client can invoke the private LocalMedia tag
reader with a server-side absolute path. The demonstrated result is metadata
disclosure from a supported media file, not arbitrary byte-for-byte file read.

Implementation references:

- Cerealizer argument construction: [`poc.py`](poc.py#L18)
- injected messaging target: [`poc.py`](poc.py#L48)
- agent-service request: [`poc.py`](poc.py#L61)
- result validation: [`poc.py`](poc.py#L71)

## Patch evidence and requirements

The packaged 10861 Framework prevents query parameters from replacing route
variables and returns the failed agent-validation result. Python 3 and the same
tagged fixture inside both servers are required. Fixed mode requires the exact
documented XML error; vulnerable mode requires the marker in the selected tag
field. Package hashes and results are in [`TESTING.md`](../TESTING.md).

## Usage

Create a tagged fixture and copy it into each disposable server:

```bash
ffmpeg -y -f lavfi -i sine=frequency=880:duration=1 \
  -metadata title=PLEX_RPC_PYTHON_91A7 -metadata artist=lab-only \
  /tmp/rpc-secret.mp3
docker cp /tmp/rpc-secret.mp3 plex-10828:/tmp/rpc-secret.mp3
docker cp /tmp/rpc-secret.mp3 plex-10861:/tmp/rpc-secret.mp3
```

Then run:

```bash
python3 poc.py --url http://127.0.0.1:32400 \
  --file /tmp/rpc-secret.mp3 --marker PLEX_RPC_PYTHON_91A7 \
  --expect vulnerable

python3 poc.py --url http://127.0.0.1:32401 \
  --file /tmp/rpc-secret.mp3 --expect fixed
```

The Python PoC creates the Plex Cerealizer argument encoding from `--file`; it
does not use a hardcoded serialized path.

## Remediation

Upgrade to `1.43.3.10861-07dfddaeb` or later.
