# Session Security and Access Policy

- Document ID: DOC-SEC-002
- Owner: Security Engineering
- Classification: Internal
- Version: 2.1

## Session lifetime
Access tokens have a 15 minute lifetime.

## Role claims
A role change takes effect on the next authenticated request after session claims are refreshed.

## Confidential sources
Confidential source files are available only to the Employee and authorised Manager roles.

## Operational requirements
- Never place real credentials in source control or demo fixtures.
- Use the configured secret store for signing keys.
- Record sign-in and access-denied events in the audit trail.
