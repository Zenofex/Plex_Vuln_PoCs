# Authenticated command execution through client profile augmentation

## Summary

Plex Media Server accepts `X-Plex-Client-Profile-Extra` from a client and, in
vulnerable builds, permits `add-transcode-target-settings` to set
`VideoEncodeFlags`. Plex tokenizes this value into additional Plex Transcoder
arguments. The complete chain uses FFmpeg HLS recursive directory creation,
libx264's two-pass statistics output, and Python 2 `.pth` startup processing to
execute an arbitrary command as the Plex service account.

Execution is delayed until Plex Script Host next starts. The PoC can restart a
named disposable Docker container to exercise that trigger end to end.

## Classification

- Product: Plex Media Server
- Affected build confirmed: `1.43.3.10861-07dfddaeb`
- Fixed build confirmed: `1.43.3.10896-cb3ebc72d`
- CVE: not assigned as of 2026-09-10
- Primary weakness: CWE-88, Improper Neutralization of Argument Delimiters in a Command
- Related weaknesses: CWE-94, Improper Control of Generation of Code; CWE-73, External Control of File Name or Path
- Authentication: confirmed with a local-administrator token; managed and shared-user tokens were not tested
- Execution context: operating-system account running Plex Media Server

## Full chain

1. The client supplies an `add-transcode-target-settings` profile augmentation
   containing `VideoEncodeFlags`.
2. PMS appends those flags to the Plex Transcoder argument vector.
3. HLS options `-strftime 1 -strftime_mkdir 1` create the Python 2 user-site
   directory beneath `/config/.local`.
4. `-x264opts pass=1:stats=...:zones=...` directs x264 to write a `.pth` file.
5. Carriage returns remain inside one transcoder argument but become Python line
   boundaries. A tab after `import` is accepted as Python whitespace.
6. On the next Plex Script Host startup, Python processes the `.pth` import line
   and executes the supplied command.

The chain does not require a server-preference change.

Implementation references:

- per-run payload construction: [`poc.py`](poc.py#L109)
- profile augmentation header: [`poc.py`](poc.py#L133)
- transcode requests: [`poc.py`](poc.py#L157)
- Docker trigger and verification: [`poc.py`](poc.py#L180)

After URL decoding, the generated profile augmentation has the following
abridged structure:

```text
add-transcode-target-settings(
  type=videoProfile&context=streaming&protocol=hls&
  VideoEncodeFlags=
    -f hls -strftime 1 -strftime_mkdir 1 ...
    -x264opts pass=1:stats=/config/.local/lib/python2.7/site-packages/plex_profile_rce_<timestamp>.pth:
    zones=<CR>0,0,q=20,stats=x<CR>import<TAB>os;os.system(...)
)
```

## Patch difference

Dynamic testing showed that the fixed build blocks security-sensitive settings
supplied by client profile augmentation. The supplied arguments did not appear
in the transcoder command line. Its PMS binary contains:

```text
ClientProfileExtra: ignoring setting %s, which may not be set from a profile augmentation
ClientProfileExtra: ignoring transcode target setting %s, which may not be set from a profile augmentation
```

On `1.43.3.10861-07dfddaeb`, the client-provided `-x264opts` appears in the
actual transcoder command line and the `.pth` is written. On
`1.43.3.10896-cb3ebc72d`, `VideoEncodeFlags` is logged as ignored and those
arguments do not reach the transcoder.

## Proof of concept

Requirements:

- Python 3.8 or later
- a local-administrator Plex token
- a rating key for a software-transcodable video
- Plex's bundled Python 2 Script Host
- local Docker control over the disposable server for automated verification

Complete lab chain:

```bash
python3 poc.py \
  --url http://127.0.0.1:32400 \
  --rating-key 1 \
  --token TOKEN \
  --command 'touch /config/PROFILE_RCE_MARKER' \
  --container plex-10861 \
  --verify-path /config/PROFILE_RCE_MARKER
```

Without Docker control, omit `--container` and `--verify-path`. The PoC starts
the transcode and reports the requested `.pth` location, but it does not claim
that placement or execution was verified.

Example successful output from `1.43.3.10861-07dfddaeb`:

```text
[1/4] Create transcode decision
[2/4] Start transcode
[3/4] Verified payload: /config/.local/lib/python2.7/site-packages/plex_profile_rce_<timestamp>.pth
[4/4] Restart container and verify execution
PASS: /config/PROFILE_RCE_MARKER was created by the supplied command
Removed generated artifacts for run <timestamp>
```

The marker path must not exist before the test. By default, the PoC removes its
per-run `.pth`, x264 companion file, and HLS bootstrap files after placement,
including when command verification fails. Remove the marker separately after
recording the result. Use `--keep-payload` only when the generated files are
needed for analysis.

## Impact

An authenticated client able to initiate the selected transcode can persist a
Python startup payload and execute arbitrary commands with the filesystem and
network privileges of the Plex service account. The payload survives until the
written `.pth` is removed.

## Remediation

Upgrade to Plex Media Server `1.43.3.10896-cb3ebc72d` or later. Raw encoder and
FFmpeg options should not be accepted from client-controlled profiles.
