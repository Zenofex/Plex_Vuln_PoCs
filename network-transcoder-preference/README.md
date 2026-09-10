# Network Modification of Protected Transcoder Preferences

## Summary

Plex Media Server `1.43.3.10828-00f62d37d` permits a local-network request to
modify `TranscoderH264Options` and `TranscoderH264OptionsOverride` through
`PUT /:/prefs` without a token. These values are consumed as x264 configuration
during software transcoding. Build `1.43.3.10861-07dfddaeb` adds both names to
the preference handler's protected-setting list and returns HTTP 403.

## Classification

- CVE: not assigned as of 2026-09-10
- Primary weakness: CWE-862, Missing Authorization
- Affected build confirmed: `1.43.3.10828-00f62d37d`
- Fixed build confirmed: `1.43.3.10861-07dfddaeb`
- Access tested: unauthenticated request from the server's local Docker network

## Technical Details

The PoC sends an x264 value and reads the preference list back to verify whether
it was persisted. It records the prior value and restores it after a successful
vulnerable-build test. It does not infer vulnerability from the PUT status alone.

```http
PUT /:/prefs?TranscoderH264OptionsOverride=ref%3D2 HTTP/1.1
```

Observed behavior:

| Build | PUT status | Stored value |
|---|---:|---|
| `1.43.3.10828-00f62d37d` | 200 | `ref=2` |
| `1.43.3.10861-07dfddaeb` | 403 | empty |

The broader consequences are demonstrated separately in
[`legacy-pth-rce`](../legacy-pth-rce/). This folder covers only the missing
preference protection.

Implementation references:

- preference update: [`poc.py`](poc.py#L59)
- stored-value parsing: [`poc.py`](poc.py#L46)
- vulnerable and fixed assertions: [`poc.py`](poc.py#L68)

## Impact, patch evidence, and requirements

A local-network client can change x264 configuration consumed by later software
transcodes. The 10861 protected-setting list adds both documented preference
names. Python 3 and an unclaimed disposable server are required; `--value` must
differ from the stored value. Exact results are in
[`TESTING.md`](../TESTING.md).

## Usage

```bash
python3 poc.py --url http://127.0.0.1:32400 \
  --value ref=2 --expect vulnerable

python3 poc.py --url http://127.0.0.1:32401 \
  --value ref=2 --expect fixed
```

The PoC verifies that the fixed build preserves the pre-test value.

## Remediation

Upgrade to `1.43.3.10861-07dfddaeb` or later.
