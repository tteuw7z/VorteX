# VorteX Motion UI

Original Python-driven, dependency-free native HTML/CSS interface inspired by the interaction design approach of [Sakuga VFX](https://github.com/finktheartist/sakuga-vfx), reference commit c3dabb173928a3ad2372183103caf2e6f50953d0 (MIT). No upstream code, sprites, lettering, private videos or assets are copied. The core is Python; generated CSS provides finite spring-like reactions. No JavaScript or network is required. 

`vortex design motion CANDIDATE --mode menu --locale pt-BR` generates a private offline menu candidate. `--mode gallery` creates a native-control lab; `--still` disables motion. The directory must not exist. The command intentionally reports REVIEW_REQUIRED (exit 1) until independent publication evidence is provided. Open index.html locally to inspect the candidate, not as a released product.

The menu reads existing Conversation navigation and capabilities; it does not activate or mutate the supplied host session. The standalone preview cannot execute tasks, invoke tools, save text or change host permissions. Existing host chat activation and text fallback remain unchanged. Two planning profiles specialize in motion design and interaction testing.

Motion rules: ordinary controls at rest; direct state updates; bounded spring transforms; one decorative ring/shard motif; no flashes, looping animation or audio; native keyboard, focus and reduced-motion behavior. The local checkbox disables all visual motion without affecting state. CSS and HTML are generated from fixed templates and escaped text, with hash-based CSP and no scripts or form submission. Declared palette contrast is checked using the existing design audit. Static checks do not prove complete accessibility or security.

Test at 390px and desktop, keyboard and pointer/touch, reduced motion and final settled frames. Do not equate static or headless tests with real-device or screen-reader tests. Browser behavior and independent gate validation must be reported separately. 

## Browser evidence

CI runs a test-only Node 22+ DevTools harness against installed Chromium. It generates actual Python candidates, uses native CDP keyboard and emulated touch events, checks CSS CSP, motion preferences and no page network traffic, and captures screenshots. Node is not a runtime dependency. Evidence is synthetic and does not authorize publication.

## Reusable controls

`Controls` owns a page-local ID registry and exposes toggle, radio (regular, segmented, rating), slider, text, select, progress, disclosure and notice builders. Every user label is escaped, numeric bounds are checked, and duplicate or unsafe IDs fail before rendering. The gallery contains ten examples; the progress is explicitly a sample, the notice is a user-triggered disclosure, and no controls submit a form or alter the host. Native radio semantics are retained for segmented/rating presentations; no false ARIA tab semantics.
