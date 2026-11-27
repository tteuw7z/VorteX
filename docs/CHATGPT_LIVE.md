# VorteX live ChatGPT skill

Install the bootstrap once. The channel `chatgpt-live/catalog.json` is published
by CI after the Linux, portable and Android fixture jobs succeed on a trusted
source branch. Each task retrieves the latest catalog; source SHA identifies
the exact version. A failed or superseded run does not publish. The publisher
uses an isolated job and a scoped contents-write token; test code runs without
write access. The catalog is generated from the actual argparse registry,
skill descriptors and agent profiles, so new registered commands appear
without manually editing a second catalog. No private requests are sent.

Catalog entries are data, not executable instructions or permission. A host
needs a compatible runtime, real tool bindings and authorization to execute
a function. A new API or CLI command is not automatically installed in ChatGPT.
The static bootstrap must be reinstalled only for incompatible protocol or
bootstrap changes. No background process inside ChatGPT is assumed.

The downloadable skill source is tracked at the root SKILL.md, scripts/route.py
and references/capabilities.md. The same adapter is distributed in the private
ChatGPT plugin v0.2.0. Tests verify a second catalog can add a capability without
changing the installed adapter, and that malformed data fails closed. The
first successful publication used workflow run 45913865635, source ad6c48c,
channel commit 05858809a2af07eb9f6e959d96288ea2980f0de0 (19 skills, 25 profiles,
42 command paths). These counts are historical, not fixed limits.
