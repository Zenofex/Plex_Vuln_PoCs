# Four-Build Docker Lab

Use separate, empty configuration directories for every build. The tested host
port and container mapping was:

| Build | Container | Host port | Image |
|---|---|---:|---|
| 10828 | `plex-10828` | 32400 | official image digest in `TESTING.md` |
| 10861 | `plex-10861` | 32401 | official image digest in `TESTING.md` |
| 10896 | `plex-10896` | 32402 | official image digest in `TESTING.md` |
| 10903 | `plex-10903` | 32403 | local image built from official DEB |

Place the official 10903 Linux amd64 DEB in `lab/packages/`, verify the SHA-256
listed in `TESTING.md`, and build it without committing the package:

```bash
sha256sum lab/packages/plexmediaserver_1.43.4.10903-e5521bd8c_amd64.deb
docker build -f lab/Dockerfile.local-deb -t plex-audit:10903 \
  --build-arg PMS_PACKAGE=lab/packages/plexmediaserver_1.43.4.10903-e5521bd8c_amd64.deb \
  --build-arg PMS_VERSION=1.43.4.10903-e5521bd8c .
```

Start the four servers from the repository root:

```bash
mkdir -p artifacts/{10828,10861,10896,10903}-config artifacts/media
docker run -d --name plex-10828 -p 127.0.0.1:32400:32400 \
  --add-host=host.docker.internal:host-gateway \
  -v "$PWD/artifacts/10828-config:/config" -v "$PWD/artifacts/media:/media" \
  plexinc/pms-docker@sha256:f6748983db1054b571b57b4a40f07f53af6c4bfb9edd1fa455f5ebb6e16449bc
docker run -d --name plex-10861 -p 127.0.0.1:32401:32400 \
  --add-host=host.docker.internal:host-gateway \
  -v "$PWD/artifacts/10861-config:/config" -v "$PWD/artifacts/media:/media" \
  plexinc/pms-docker@sha256:dd9bcf6494a1f7e817710e75d2ff66beb68485b5ea1b63c7c712adc25983b9bb
docker run -d --name plex-10896 -p 127.0.0.1:32402:32400 \
  -v "$PWD/artifacts/10896-config:/config" -v "$PWD/artifacts/media:/media" \
  plexinc/pms-docker@sha256:c708587e4874617961a1bc24db9cffa2413653ff422f1b05dfec013339e6824d
docker run -d --name plex-10903 -p 127.0.0.1:32403:32400 \
  -v "$PWD/artifacts/10903-config:/config" -v "$PWD/artifacts/media:/media" \
  plex-audit:10903
```

Obtain each claimed or unclaimed lab's local-administrator token as documented
in the root README. Create the same synthetic library in each server. The legacy
RCE chain requires a fresh 10828 configuration for each run because its first
stage creates `/config/.local/lib/python2.7/site-packages`.
