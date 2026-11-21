# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability (such as SSRF bypass, authentication flaw, prompt-injection escalation, or secret leakage), please **do not** open a public GitHub issue with exploit details.

Instead, report it privately to the maintainers with:
1. A description of the vulnerability and affected component.
2. Steps to reproduce safely.
3. Any suggested remediation.

## Security Design Principles

- All retrieved web content is untrusted data.
- SSRF protections validate public DNS/IPs on initial URLs and all redirect hops.
- All API keys remain strictly server-side in environment variables.
- Ownership checks are enforced on every database query and API endpoint.
