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
