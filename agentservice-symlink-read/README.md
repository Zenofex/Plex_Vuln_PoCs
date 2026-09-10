# AgentService File Read through an Escaping Metadata Symlink

## Summary

The `media_get` route in Plex Media Server `1.43.3.10896-cb3ebc72d` resolves a
legacy metadata-bundle path and reads it without verifying the final target
after symbolic-link resolution. A valid metadata entry whose media file is an
absolute symlink can therefore return a file outside the bundle.

Build `1.43.4.10903-e5521bd8c` adds path-segment validation, an allowed-category
list, XPath variable binding, and `realpath` containment checks.

## Classification

- CVE: not assigned as of 2026-09-10
- Primary weakness: CWE-59, Improper Link Resolution Before File Access
- Related weakness: CWE-22, Improper Limitation of a Pathname to a Restricted Directory
- Affected build confirmed: `1.43.3.10896-cb3ebc72d`
- Fixed build confirmed: `1.43.4.10903-e5521bd8c`
- Authentication: confirmed with a local-administrator token
- Required condition: an escaping symlink already exists in the selected legacy metadata bundle

## Scope

The PoC uses local Docker control to create a unique temporary bundle containing
an `Info.xml` entry and a symlink to `--target`. It then exercises the network
route and removes the bundle. This isolates and tests the behavior changed by
the patch. It does not demonstrate a remote method for creating the symlink,
and no such method is claimed.

This is a conditional file-read primitive, not a standalone remotely
attacker-reproducible chain. Its security impact depends on a separate method
of placing an escaping symlink in a legacy metadata bundle.

Observed results for `/etc/hostname`:

| Build | Result |
|---|---|
| `1.43.3.10896-cb3ebc72d` | HTTP 200; response matched the 13-byte target |
| `1.43.4.10903-e5521bd8c` | HTTP 404; no target bytes returned |

The fixed System bundle logs that the resolved path escapes the bundle
directory.

Implementation references:

- unique bundle path generation: [`poc.py`](poc.py#L55)
- fixture and symlink creation: [`poc.py`](poc.py#L69)
- authenticated AgentService request: [`poc.py`](poc.py#L94)
- response comparison and bundle cleanup: [`poc.py`](poc.py#L107)

## Usage

```bash
python3 poc.py --url http://127.0.0.1:32400 \
  --token TOKEN --container plex-10896 \
  --target /etc/hostname --expect vulnerable

python3 poc.py --url http://127.0.0.1:32401 \
  --token TOKEN --container plex-10903 \
  --target /etc/hostname --expect fixed
```

Use only a disposable server. The PoC creates and deletes a uniquely named
metadata bundle under `/config`.

## Remediation

Upgrade to `1.43.4.10903-e5521bd8c` or later.
