# Security Policy

## Supported versions

zotrm is pre-1.0; security fixes are applied to the latest released version only.

## Reporting a vulnerability

Please **do not open a public issue** for security problems.

Instead, use GitHub's private reporting: go to the repository's **Security** tab →
**Report a vulnerability**. If that is unavailable, contact the maintainer via
<https://roydipta.com>.

Please include:

- a description of the issue and its impact,
- steps to reproduce, and
- any relevant logs or configuration (with secrets such as your Zotero API key removed).

You can expect an initial response within a week. Thank you for helping keep zotrm and its
users safe.

## A note on secrets

zotrm stores your Zotero API key in a local config file (`~/.config/zotrm/config.ini`) and
sends it only to Zotero's official API. Never paste your API key into an issue or PR;
`zotrm config --show` masks it for exactly this reason.
