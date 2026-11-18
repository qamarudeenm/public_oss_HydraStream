# Contributing to HydraStream

Thanks for contributing to HydraStream.

## Repository Hygiene Rules

- Do not commit secrets, credentials, or production endpoints.
- Keep generated artifacts out of source control.
- Generated dbt outputs must never be committed:
  - `streaming_infra/dbt/target/`
  - `streaming_infra/dbt/logs/`
- Keep pull requests focused and small enough to review.

## Branch and Commit Conventions

- Create a dedicated feature/fix branch per change.
- Use clear commit messages that explain intent and scope.
- If your change affects security-sensitive paths, call that out in the PR description.

## Local Validation Before Opening a PR

Run the checks relevant to your change.

### Flink Proxy Gateway (`streaming_infra/infra/flink-proxy-gateway`)

```bash
cd streaming_infra/infra/flink-proxy-gateway
uv sync --all-extras
make lint
make test-unit
```

### Frontend (`control_plane/frontend`)

```bash
cd control_plane/frontend
npm ci
npm run lint
```

### Security Gate (`streaming_infra`)

```bash
./streaming_infra/security/cybersecurity-gate.sh
```

## CI Quality Gates

GitHub Actions enforces the following workflow gates on push/PR to `main` and `master`:

- `repository-hygiene`: fails when generated dbt artifacts are tracked.
- `proxy-quality`: lint/type checks and unit tests for the proxy gateway.
- `frontend-quality`: lint checks for control plane frontend.
- `security-release-gate`: cybersecurity release-readiness checks.

All required gates must pass before merge.

## Pull Request Checklist

- [ ] I did not commit generated artifacts or secrets.
- [ ] I ran the relevant local quality gates.
- [ ] CI quality gates pass.
- [ ] I documented any security-relevant impact in the PR.
