# BLUAA-36 Cybersecurity Release Readiness Report

Generated: 2026-04-12T19:03:36Z (UTC)
Scope: `streaming_infra`

## Verdict

PASS - Release readiness criteria are satisfied.

## Security Checks Executed

Command:

```bash
./streaming_infra/security/cybersecurity-gate.sh
```

Result summary:
- Passed controls: 7
- Warnings: 1
- Failed controls: 0

## Passed Controls

- Kubernetes proxy ConfigMap enforces `PROXY_AUTH_MODE=oidc_jwt`
- Helm tenant chart injects `PROXY_AUTH_MODE` into proxy container env
- Helm tenant values default proxy auth mode to `oidc_jwt`
- Helm tenant chart applies container security context for proxy pod
- Kubernetes proxy deployment enforces non-root, no privilege escalation, and read-only filesystem
- Helm values no longer ship with a default ClickHouse password
- `streaming_infra/example.env` no longer uses weak sample passwords

## Warning and Remediation Recommendation

- Warning: proxy image tag is mutable (`proxy-latest`).
- Recommendation: pin proxy image to an immutable tag or digest before production release.

## Validation Evidence

- Integration test suite: `uv run pytest tests/integration/test_proxy_endpoints.py -q`
- Outcome: `7 passed`
- Added attack-surface regression test covering native endpoints:
  - `/v1/sessions`
  - `/v1/sessions/{session_id}/statements`
  - `/v1/sessions/{session_id}/statements/{operation_id}/status`

