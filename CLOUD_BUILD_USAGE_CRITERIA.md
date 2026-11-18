# Criteria for Using GCP Cloud Build on Minisky

## Overview
Minisky provides a local emulator for GCP Cloud Build, allowing developers to test Cloud Build configurations without incurring costs or affecting real GCP resources. This document establishes clear criteria for when to use Minisky Cloud Build versus real GCP Cloud Build, considering factors like development vs production, testing environments, cost, and integration with the existing GCP migration plan.

## When to Use Minisky Cloud Build

### 1. Local Development and Testing
- Developers can validate their `cloudbuild.yaml` configurations locally before committing.
- Run unit tests and integration tests that depend on Cloud Build in a safe, isolated environment.
- Ideal for iterative development and debugging of Cloud Build steps.

### 2. Feature Branch Validation
- Use Minisky Cloud Build in CI for pull requests to provide fast feedback on build and test steps.
- Avoids using real GCP resources for every PR, reducing costs and quota usage.
- Particularly useful for early-stage feedback where production-equivalent performance is not required.

### 3. Configuration Drift Testing
- Test changes to Cloud Build triggers, substitutions, and workflows without affecting the real GCP project.
- Validate that Cloud Build configurations work correctly before promoting to real GCP.
- Safe environment to experiment with new Cloud Build features or machine types.

### 4. Learning and Experimentation
- New team members can experiment with Cloud Build syntax and features in a risk-free environment.
- Ideal for training sessions and workshops on GCP Cloud Build.
- Allows testing of complex build scenarios without impacting shared resources.

### 5. Non-Production Builds
- Building Docker images for development or staging environments that don't require production-grade guarantees.
- Running tests that don't require access to production services or secrets.
- Internal tooling or utility builds that are not customer-facing.

## When to Use Real GCP Cloud Build

### 1. Production Deployments
- For builds that are intended for release (e.g., pushing to main/master, creating tags).
- When building Docker images that will be deployed to production environments.
- Any build that produces artifacts used in customer-facing systems.

### 2. Performance and Scale Requirements
- When builds require more powerful machines or specific machine types not available or accurately emulated in Minisky.
- When needing to leverage GCP-specific integrations (e.g., with Artifact Registry, Secret Manager) that may have different behavior or performance characteristics in Minisky.
- Builds requiring high concurrency or specialized compute options (e.g., GPU, high-memory instances).

### 3. Final Validation Before Release
- Run a final build in real GCP Cloud Build to ensure compatibility with production GCP services.
- Validate that IAM permissions, service account configurations, and secret access work correctly in the real environment.
- Perform smoke tests on built artifacts using production-like configurations.

### 4. Compliance and Auditing
- For builds that require audit trails in real GCP for compliance reasons (e.g., SOC 2, ISO 27001).
- When regulatory requirements mandate that certain builds occur in the actual production GCP project.
- Builds that generate artifacts subject to legal or contractual obligations requiring GCP provenance.

### 5. Integration Testing with Real GCP Services
- End-to-end tests that require interaction with real GCP services beyond what Minisky emulates.
- Testing integration with services that may have limited or different emulation in Minisky (e.g., specific BigQuery features, specialized AI/ML APIs).
- Validating network policies, VPC configurations, or other infrastructure-specific behaviors.

## Decision Matrix

| Scenario                                  | Minisky Cloud Build | Real GCP Cloud Build |
|-------------------------------------------|---------------------|----------------------|
| Local development (developer machine)     | ✅ Preferred        | ❌ Not applicable    |
| Pull request CI                           | ✅ Recommended      | ⚠️ Optional (for final validation) |
| Feature branch builds (non-production)    | ✅ Recommended      | ⚠️ Optional          |
| Release candidate builds (main/master)    | ⚠️ For testing only | ✅ Required          |
| Production image builds                   | ❌ Not recommended  | ✅ Required          |
| Testing Cloud Build configuration changes | ✅ Preferred        | ❌ Avoid (risky)     |
| Performance/scale testing                 | ❌ Limited          | ✅ Preferred         |
| Compliance/auditing requirements          | ❌ Not sufficient   | ✅ Required          |
| Integration with non-emulated GCP services| ❌ Limited          | ✅ Required          |

## Implementation Recommendations

### 1. Feature Flag Mechanism
Introduce a feature flag to dynamically choose between Minisky and real GCP Cloud Build:

- **Environment Variable**: `USE_MINISKY_CLOUD_BUILD=true/false`
- **Configuration File**: `.cloudbuild-config` with settings for endpoint selection
- **CI Pipeline Logic**: 
  - For PRs from forks or feature branches: default to Minisky
  - For PRs targeting main/master: optionally run dual validation (Minisky first, then real GCP)
  - For merges to main/master: require real GCP Cloud Build
  - For release/tag builds: always use real GCP Cloud Build

### 2. Minisky Configuration Guidelines
When using Minisky, ensure proper configuration:

```bash
# Environment variables (from MINISKY_TESTING.md)
export MINISKY_ENABLED=true
export MINISKY_API_URL=http://localhost:8080
export MINISKY_PROJECT_ID=local-dev
export CLOUDSDK_API_ENDPOINT_OVERRIDES_CLOUDBUILD=http://localhost:8080/
export GOOGLE_CLOUD_PROJECT=local-dev
```

In `cloudbuild.yaml`, use substitutions that can be overridden for Minisky:
```yaml
substitutions:
  _REGION: 'us-central1'  # Can be overridden
  _PROJECT_ID: '${PROJECT_ID}'  # Will be 'local-dev' in Minisky
  _ARTIFACT_REGISTRY: '${REGION}-docker.pkg.dev/${PROJECT_ID}/hydrastream-images'
```

### 3. Integration with GCP Migration Plan
Align criteria with the existing migration strategy:

**Phase 1 (Preparation)**:
- Use Minisky to validate required GCP APIs are properly emulated
- Test Secret Manager and Artifact Registry access patterns locally

**Phase 2 (Implementation)**:
- Develop and test `cloudbuild.yml` using Minisky
- Validate build steps work identically in Minisky and real GCP (where emulation is accurate)
- Test trigger configurations using Minisky's Cloud Build API emulation

**Phase 3 (Cutover)**:
- Run parallel validation: build same commit in both Minisky and real GCP
- Compare outputs, timing, and artifact consistency
- Promote to real GCP only after Minisky validation passes

### 4. Cost Optimization Strategy
Leverage Minisky to minimize real GCP Cloud Build expenses:

- **Development Builds**: 100% Minisky (free)
- **CI for PRs**: 80% Minisky, 20% real GCP (for random sampling or critical paths)
- **Main/Master Branches**: 50% Minisky (pre-validation), 50% real GCP (final validation)
- **Release Builds**: 100% real GCP Cloud Build
- **Emergency Hotfixes**: Minisky for rapid validation, then real GCP for deployment

### 5. Monitoring and Feedback
Implement observability to track usage patterns:

- Log which environment (Minisky/real GCP) was used for each build
- Track build durations and success rates in both environments
- Monitor cost savings from Minisky usage
- Collect developer feedback on Minisky fidelity and pain points

## Transition Guidelines

### From GitHub Actions to Minisky Cloud Build (Intermediate Step)
1. Develop `cloudbuild.yml` mirroring GitHub Actions workflows
2. Test locally using Minisky with `curl -H "Host: cloudbuild.googleapis.com" http://localhost:8080/...`
3. Validate using existing test suites via `make test-minisky`
4. Once stable, use Minisky for PR CI while keeping GitHub Actions for main
5. Gradually shift more workloads to Minisky as confidence increases

### From Minisky to Real GCP Cloud Build
1. Promote changes that pass Minisky validation to a staging branch
2. Run dual validation: build in both Minisky and real GCP
3. Compare artifact digests, test results, and build logs
4. After N consecutive successful validations, enable real GCP for that branch type
5. Monitor for drift and re-validate periodically

## Success Metrics

Track these indicators to evaluate the effectiveness of the criteria:

1. **Cost Savings**: Percentage reduction in real GCP Cloud Build usage
2. **Developer Velocity**: Average time from commit to build feedback
3. **Build Success Rate**: Comparison of success rates between Minisky and real GCP
4. **Issue Detection Rate**: Percentage of issues caught in Minisky vs. escaping to real GCP
5. **Adoption Rate**: Percentage of builds using Minisky vs. real GCP by branch type
6. **Mean Time to Recovery (MTTR)**: How quickly build failures are resolved using Minisky for reproduction

## Review and Evolution

These criteria should be reviewed quarterly or when:
- Significant changes occur in Minisky's GCP service emulation fidelity
- New GCP features are released that affect build processes
- Company production workloads or compliance requirements change
- Feedback from development teams indicates needed adjustments

The CTO and DevOps team should own periodic reviews and updates to this document.

---

*Document created as part of Issue BLUAA-233: criteria to use GCP cloud build on Minisky*
*Last updated: 2026-05-22*