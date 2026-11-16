# HydraStream Image Tagging Convention

## Overview

HydraStream CI tags the proxy image with an immutable git-SHA-based tag on every push to `main`/`master`. This ensures deployments are fully reproducible and cannot silently pick up unintended changes.

## Tag Formats

| Event | Tags pushed | Example |
|---|---|---|
| Push to `main`/`master` | `proxy-<7-char-sha>` | `proxy-a1b2c3d` |
| Push of a release tag `v*.*.*` | `proxy-<7-char-sha>`, `proxy-<semver>` | `proxy-a1b2c3d`, `proxy-v1.2.0` |
| Pull request | _(no push)_ | — |

**`proxy-latest` is not published.** It was removed in BLUAA-291 — mutable tags prevent reproducible deployments and were flagged as a P0 security issue.

## Finding the Right Tag

After a CI run, the workflow summary shows the exact SHA tag that was published. You can also look up the short SHA for any commit:

```bash
git rev-parse --short HEAD
# e.g. a1b2c3d
# → image tag: proxy-a1b2c3d
```

## Deploying with a SHA Tag

### Helm (recommended)

```bash
helm upgrade --install <release> ./streaming_infra/charts/hydrastream-tenant \
  --set proxy.image.tag=proxy-<sha>
```

### deploy-tenant.sh

```bash
./streaming_infra/deploy-tenant.sh tenant-1 tenant-1 proxy-a1b2c3d
```

The `proxy.image.tag` value in `charts/hydrastream-tenant/values.yaml` defaults to `""` (empty), which is intentional — it **must** be set at deploy time. A missing or empty tag will cause the chart to fail fast rather than silently pull an unintended image.

## Engine and dbt Worker

The Flink engine image is pinned by Flink version (`engine-flink1.19.1`) and does not use `latest`. The dbt worker still uses a `dbt-latest` convenience tag but is not on the production-critical proxy path.
