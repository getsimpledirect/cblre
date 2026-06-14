# Security Policy

## Supported versions

CBLRE is a research-stage benchmark harness. The current development line (`main`) is the only supported version. No backport patches are issued for older tags.

## Scope

This policy covers:

- The scoring harness (`harness/`) and its dependencies
- The CI/release pipeline (`.github/workflows/`)
- The item schema (`schema/eval_item.schema.json`)

It does **not** cover:

- The gated item bank (distributed separately under a restricted licence — report data concerns directly to the maintainers)
- Third-party model endpoints or APIs that you point the harness at

## Reporting a vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

Report vulnerabilities privately through [GitHub's private vulnerability reporting](https://github.com/getsimpledirect/cblre/security/advisories/new). We aim to acknowledge reports within **3 business days** and provide a resolution timeline within **10 business days**.

Please include:

- A description of the vulnerability and its potential impact
- Steps to reproduce or a minimal proof-of-concept
- Which version / commit you tested against

## Responsible disclosure

We ask that you:

- Give us reasonable time to address the issue before public disclosure
- Avoid accessing, modifying, or deleting data that does not belong to you
- Limit testing to your own evaluation runs and items

We commit to:

- Acknowledging your report promptly
- Keeping you informed of remediation progress
- Crediting reporters in the release notes (unless you prefer to remain anonymous)

## Security design notes

- API keys are never stored in the repository; they are read exclusively from environment variables at runtime
- The harness makes outbound HTTP requests only to endpoints you explicitly configure via `--model` and `--judge` specs
- No data is sent to SimpleDirect® servers during an evaluation run
- The gated item bank is distributed through authenticated channels, not this repository
