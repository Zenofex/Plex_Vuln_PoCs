# Plex Media Server Patch-Diff Vulnerability PoCs

This repository contains reproducible proof-of-concept code for security issues
identified by comparing patched Plex Media Server builds from
`1.43.3.10828-00f62d37d` through `1.43.4.10903-e5521bd8c`.

The PoCs are organized by vulnerability and use only Python's standard library.
Each directory contains a technical writeup, affected/fixed version evidence,
command-line usage, and expected results.

## Finding summary

Severity ratings are provisional researcher assessments, not vendor scores or
CVSS calculations. They reflect the demonstrated impact and tested
preconditions. The legacy RCE entry is an impact chain composed from two listed
primitives and is not counted as a separate root cause.

| Severity | Finding | Primitive to impact | Access and boundary |
|---|---|---|---|
| **Critical** | [Unauthenticated Framework and x264 preference chain to command execution](legacy-pth-rce/)<br><sub>CWE-862, CWE-94, CWE-22</sub> | Framework path placement + protected-preference modification → executable `.pth` placement → command execution as the Plex account | No token in the tested local lab<br>10828 affected; 10861 blocked |
| **High** | [CompanionProxy callback injection enabling server-side request forgery](companion-proxy-ssrf/)<br><sub>CWE-918</sub> | Callback authority and path injection → server-side timeline POST to a selected HTTP destination | No token in the tested local lab<br>10828 affected; 10861 fixed |
| **High** | [Framework route injection enabling private LocalMedia RPC invocation](framework-rpc-injection/)<br><sub>CWE-863, CWE-20</sub> | Route-variable clobbering → private `ReadTags` call against a selected server-side media path | No token in the tested local lab<br>10828 affected; 10861 fixed |
| **High** | [Unauthenticated modification of protected x264 transcoder preferences](network-transcoder-preference/)<br><sub>CWE-862</sub> | Missing preference authorization → persistent control of x264 options used by software transcoding | No token in the tested local lab<br>10828 affected; 10861 fixed |
| **High** | [Client-profile augmentation enabling transcoder argument injection and command execution](profile-extra-rce/)<br><sub>CWE-88, CWE-94, CWE-73</sub> | Profile augmentation injection → transcoder-controlled `.pth` placement → command execution as the Plex account | Local-administrator token<br>10861 affected; 10896 fixed |
| **High** | [Metadata `file://` reference injection enabling arbitrary server-side file read](metadata-file-read/)<br><sub>CWE-36, CWE-73</sub> | External path control → arbitrary file read within Plex account permissions | Local-administrator token<br>10861 affected; 10896 fixed |
| **Medium** | [AgentService symlink resolution without bundle containment enabling conditional file read](agentservice-symlink-read/)<br><sub>CWE-59, CWE-22</sub> | Escaping bundle symlink → conditional file read within Plex account permissions | Token + pre-existing symlink<br>10896 affected; 10903 fixed |

Build numbers are shorthand for the complete versions below. Authentication
observations apply only to the tested local lab. Managed-user, shared-user, and
WAN behavior were not established.

## Version differences

| Build | Significant observed behavior |
|---|---|
| `1.43.3.10828-00f62d37d` | Companion callback injection, private RPC injection, network-modifiable x264 preferences, and the legacy `.pth` RCE chain are reproducible |
| `1.43.3.10861-07dfddaeb` | Earlier issues are fixed; profile `VideoEncodeFlags` RCE and metadata `file://` read remain reproducible |
| `1.43.3.10896-cb3ebc72d` | Profile RCE and metadata `file://` read are fixed; AgentService follows an escaping bundle symlink |
| `1.43.4.10903-e5521bd8c` | AgentService validates path segments and resolved bundle containment |

Relevant strings added across the fixed PMS binaries include:

```text
ClientProfileExtra: ignoring transcode target setting %s, which may not be set from a profile augmentation
[Library] Rejecting metadata file request for unsupported media reference: %s
[Library] Rejecting metadata file request that escapes the bundle directory: %s
[Library] Ignoring media reference that escapes its bundle directory: %s
wanted to subscribe with an unsupported protocol '%s'
wanted to subscribe with an out of range port %d
```

The 10861-to-10896 patch strings were also confirmed in the official macOS and
Windows packages. Dynamic PoC testing was performed on Linux x86-64 Docker
images. See [TESTING.md](TESTING.md) for the test record.

## Lab setup

For the complete four-version environment, including the locally packaged
10903 build and a consistent port map, see [`lab/README.md`](lab/README.md).

Use a disposable server containing no sensitive data. The following example
publishes Plex only on the local loopback interface:

```bash
mkdir -p "$PWD/artifacts/plex-config" "$PWD/artifacts/media"
ffmpeg -y -f lavfi -i testsrc=size=640x360:rate=24 \
  -f lavfi -i sine=frequency=1000 -t 5 \
  -c:v libx264 -pix_fmt yuv420p -c:a aac \
  "$PWD/artifacts/media/test.mp4"
docker run -d --name plex-10861 \
  -p 127.0.0.1:32401:32400 \
  -v "$PWD/artifacts/plex-config:/config" \
  -v "$PWD/artifacts/media:/data" \
  plexinc/pms-docker@sha256:dd9bcf6494a1f7e817710e75d2ff66beb68485b5ea1b63c7c712adc25983b9bb
```

Create a movie library for `/data` through the Plex web interface and note the
test video's numeric rating key. On an unclaimed local test server, the
generated local-administrator token can be obtained with:

```bash
docker exec plex-10861 sh -c \
  'cat "/config/Library/Application Support/Plex Media Server/.LocalAdminToken"'
```

Run the file-read PoC:

```bash
python3 metadata-file-read/poc.py \
  --url http://127.0.0.1:32401 \
  --rating-key 1 \
  --token TOKEN \
  --file /etc/hostname
```

Run the complete profile-to-command-execution chain and have the PoC restart
the disposable container to trigger Plex Script Host:

```bash
python3 profile-extra-rce/poc.py \
  --url http://127.0.0.1:32401 \
  --rating-key 1 \
  --token TOKEN \
  --command 'touch /config/PROFILE_RCE_MARKER' \
  --container plex-10861 \
  --verify-path /config/PROFILE_RCE_MARKER
```

For negative testing, create a second lab with a fresh configuration directory
and the fixed amd64 image:

```bash
mkdir -p "$PWD/artifacts/fixed-config" "$PWD/artifacts/fixed-media"
cp "$PWD/artifacts/media/test.mp4" "$PWD/artifacts/fixed-media/test.mp4"
docker run -d --name plex-10896 \
  -p 127.0.0.1:32402:32400 \
  -v "$PWD/artifacts/fixed-config:/config" \
  -v "$PWD/artifacts/fixed-media:/data" \
  plexinc/pms-docker@sha256:c708587e4874617961a1bc24db9cffa2413653ff422f1b05dfec013339e6824d
```

Add the test video as a new library, obtain that server's token and rating key,
and run both PoCs against `http://127.0.0.1:32402`. The file-read request must
not return the selected server-side file. The RCE PoC must fail to find its
per-run `.pth` payload.

Stop and remove the lab containers when testing is complete:

```bash
docker stop plex-10861 plex-10896
docker rm plex-10861 plex-10896
```

## Safety and scope

These PoCs perform real server-side file access and command execution. Run them
only against systems you own or are explicitly authorized to test. The Docker
instructions bind PMS to `127.0.0.1` and are intended for an isolated lab.

Token scope for the authenticated findings was tested with local-administrator
tokens. Managed and shared-user tokens were not tested, and no claim is made
about those token classes. The unauthenticated findings were tested from the
local Docker network against unclaimed lab servers; WAN behavior was not tested.

## Methodology and disclosure status

Findings were derived from static comparison of official packages and dynamic
regression testing at the build boundaries recorded in [TESTING.md](TESTING.md).
Binary strings were extracted with printable-string scanning and correlated
with changed behavior; package hashes identify the reviewed inputs.

Unless a Plex advisory or CVE is linked for a specific finding, classifications
and impact statements are researcher assessments, not vendor confirmation.
Research credit: Zenofex. CVSS scores are omitted because final CVE scope and
deployment assumptions were not available at publication time.

## References

- [Plex security update announcement](https://forums.plex.tv/t/important-security-update-for-plex-media-server-v1-43-2-and-earlier/942319)
- [Plex Media Server downloads](https://www.plex.tv/media-server-downloads/)

## License

This repository is released under the [MIT License](LICENSE).
