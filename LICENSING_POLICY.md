# VorteX licensing policy — proposed transition

The existing public framework remains licensed under Apache-2.0. This policy does not revoke, narrow or replace rights already granted, including rights in previously released versions and third-party contributions.

## Future proprietary components

New, independently authored components that the rights holder elects to keep proprietary should preferably be developed in a separate private repository. With explicit owner authorization, a separately identified source-available directory may instead be published publicly with its own license notice. Such publication permits viewing and forking through GitHub under its terms and cannot provide technical secrecy. The studio/ directory is the first such exception. Before distribution, each such component must carry an explicit license notice and a documented ownership and dependency review. Proposed default notice for wholly owned, separately identified material:

> Copyright (c) 2026 the respective VorteX copyright holder(s). All rights reserved.
> Except as expressly authorized in writing by the copyright holder or permitted by applicable law, no permission is granted to reproduce, modify, redistribute, sublicense or commercially exploit this proprietary material.

This notice is a template, not a retroactive relicensing of this repository, and does not itself grant end-user usage rights. An appropriate end-user or service agreement must be adopted before proprietary distribution.

## Third-party materials and contributions

- Verify provenance and license compatibility before importing any code, assets, designs or dependencies.
- Preserve required copyright, license and attribution notices. Do not claim exclusive rights over third-party material or previously licensed code.
- Use independently authored implementations of permitted functionality when reuse is not licensed. Do not bypass access controls or copy proprietary assets or source without permission.
- Review contributor ownership and obtain the necessary permissions before relicensing any contribution.
- Keep a component-level license inventory and audit distribution obligations before release.

## Public/private boundary

Public catalogs and integration clients should expose only explicitly approved information. Keep proprietary implementation private by default except for expressly authorized source-available components; credentials, personal context and confidential logs remain excluded from public repositories. A public repository may be viewed and forked under GitHub's terms; a proprietary notice is not a technical copy-prevention mechanism. Private hosting cannot recall existing copies.

This proposal requires owner and legal review before adoption; it does not change the existing LICENSE or package metadata.
