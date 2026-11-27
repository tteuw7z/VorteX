# Third-party provenance and licensing inventory

This is a preliminary inventory, not a clearance certificate. The public baseline remains Apache-2.0 (see LICENSE and pyproject.toml). Existing grants are preserved. No new external source or asset is incorporated by this inventory.

Studio separately uses Pillow (HPND; check exact installed release and notices) and invokes system FFmpeg/FFprobe. Neither dependency is vendored.

| Component | Role | License evidence / obligations | Status |
| --- | --- | --- | --- |
| VorteX public baseline | Existing framework | Apache-2.0, LICENSES/Apache-2.0.txt and root scope notice; review contributor ownership before any relicensing | Preserve |
| Craft Anything | Architecture reference only | [Upstream README](https://github.com/storytold/craft-anything/blob/main/README.md), [MIT](https://github.com/storytold/craft-anything/blob/main/LICENSE-MIT), [Apache](https://github.com/storytold/craft-anything/blob/main/LICENSE-APACHE); verify exact file and revision before import | No import |
| agency-agents | Historical catalog reference | DECISIONS.md records MIT upstream and prior publication of categories/counts only; verify actual file provenance before reuse | Historical record, not re-audited |
| setuptools | Build dependency | Version/build distribution license to be checked at release | External |
| FFmpeg / FFprobe | Media executables | https://ffmpeg.org/legal.html ; build-dependent LGPL/GPL and other terms; inspect exact binary before redistribution | External, not bundled |
| Android SDK / Gradle / JDK | Android build tools | Review each installed version, SDK terms and redistribution rights | External, not bundled |
| Whisper CLI / weights / Tesseract | Local media adapters | Review exact code versions, model/data licenses and transitive dependencies separately | External, not bundled |

## Gate for new components

Record each imported file or asset, original URL, immutable upstream revision, SHA-256, copyright notice, applicable license, modifications, and required distribution notices. Preserve the exact upstream license text for imported material. Block unknown licenses and unresolved redistribution obligations. A reference entry is not permission to copy. Do not claim proprietary rights over third-party code. Require explicit authorization to publish; do not place private source, personal context, private evidence, or secrets in this public repository. Studio's original source is an explicitly authorized source-available exception.

For a future proprietary package: verify ownership, identify covered original files, include a separate proprietary license and third-party notices where applicable, and review distribution terms before release. No changes to existing Apache-2.0 files are authorized by this inventory.
