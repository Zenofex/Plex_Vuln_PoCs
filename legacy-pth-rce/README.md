# Delayed RCE Chain through Framework Routing and Transcoder Preferences

## Summary

This chain combines two issues present in Plex Media Server
`1.43.3.10828-00f62d37d`:

1. Framework route-variable injection creates Plex's Python 2 user-site
   directory outside the intended plug-in configuration path.
2. The unprotected `TranscoderH264OptionsOverride` preference supplies x264
   options that write a client-controlled `.pth` file to that directory.

Plex Script Host processes the `.pth` import line when it starts, executing the
supplied command as the Plex service account. Build
`1.43.3.10861-07dfddaeb` protects the transcoder preference used by the chain.
This directory documents the combined impact and does not count the chain as a
third root cause.

## Classification

- CVE: not assigned as of 2026-09-10
- Primary weakness: CWE-862, Missing Authorization
- Related weaknesses: CWE-94, Improper Control of Generation of Code; CWE-22, Improper Limitation of a Pathname to a Restricted Directory
- Affected build confirmed: `1.43.3.10828-00f62d37d`
- Fixed build confirmed: `1.43.3.10861-07dfddaeb`
- Authentication observed: no token required in the unclaimed local lab
- Trigger: later Plex Script Host startup; the PoC restarts a disposable container

## Full Chain

1. Send the traversal value as the agent configuration `identifier`.
2. Set `TranscoderH264OptionsOverride` to an x264 two-pass value.
3. Start an HLS transcode for the selected rating key.
4. x264 writes a per-run `.pth` containing the injected Python import line.
5. Clear the persistent transcoder preference.
6. Restart the disposable container and verify the command's marker path.
7. Remove the per-run `.pth` and companion x264 file.

The vulnerable test refuses to run if the Python site directory already exists.
It verifies that the Framework request creates that directory before proceeding.
The fixed-build mode is a boundary check for the protected-preference fix; it
does not claim to exercise every earlier stage.

Implementation references:

- per-run x264 and `.pth` payload: [`poc.py`](poc.py#L93)
- Framework directory-creation request: [`poc.py`](poc.py#L104)
- preference update: [`poc.py`](poc.py#L119)
- transcode, restart, and cleanup: [`poc.py`](poc.py#L164)

## Usage

```bash
python3 poc.py --url http://127.0.0.1:32400 \
  --rating-key 3 --command 'touch /config/LEGACY_RCE_MARKER' \
  --container plex-10828 --verify-path /config/LEGACY_RCE_MARKER \
  --expect vulnerable

python3 poc.py --url http://127.0.0.1:32401 \
  --rating-key 1 --command 'touch /config/LEGACY_RCE_FIXED_MARKER' \
  --container plex-10861 --verify-path /config/LEGACY_RCE_FIXED_MARKER \
  --expect fixed
```

The marker must not exist before testing. Unless `--keep-payload` is supplied,
the PoC clears the preference and removes the per-run `.pth` and x264 companion
file. Remove the command-created marker after recording the result.

## Remediation

Upgrade to `1.43.3.10861-07dfddaeb` or later.
