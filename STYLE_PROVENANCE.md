# Scientific visualisation provenance

The visual style is Nature-inspired; the article target remains Waste Management
& Research. Style resemblance is not a Nature publication, endorsement or a
claim of journal acceptance.

Configuration sources read on 2026-10-05:

- [SciencePlots](https://github.com/garrettj403/SciencePlots), commit
  `b9b16959570bd2fbc9ff5118bacc423c3bddd592`, MIT. `science` and `nature`
  styles inform sans-serif fonts, panel labels, restrained lines and dimensions.
- [K-Dense scientific-visualization skill](https://github.com/k-dense-ai/scientific-agent-skills/tree/154988403bb5a18e9d3c0ce4e6d5e2e4b184a298/scientific-visualization),
  commit `154988403bb5a18e9d3c0ce4e6d5e2e4b184a298`, MIT. Its Nature stylesheet
  is combined with the local configuration. The skill influenced final-size,
  vector/editable-text, truthful-error-bar and overlap checks. Third-party code
  was not executed; only reviewed visualisation configuration was applied.
- [Official Nature figure guide](https://research-figure-guide.nature.com/figures/building-and-exporting-figure-panels/)
  and [final-submission guidance](https://www.nature.com/nature/for-authors/final-submission),
  read 2026-10-05. Standalone figures are 183 mm wide; panel lettering is 8 pt,
  labels generally 6–7 pt. The publisher guide is a reference, not this target's
  licence or a requirement to rasterise vector graphics.

Relevant software/skill citation (not an added magnet-recovery scientific source):
Kassis, T., Agarwal, V., He, Y., Patel, D. and Brueckner, A. M. (2026).
*Scientific Agent Skills: A Library of Procedural Knowledge for Research Agents*.
arXiv:2609.00065. https://doi.org/10.48550/arXiv.2609.00065.

Exports: native PDF/SVG vectors, embedded PDF fonts, editable SVG text,
native 1200 dpi PNG/RGB LZW-TIFF. No interpolated resolution or generative-AI
result images. DPI describes only raster exports; vectors do not have a DPI.
Arial is used where installed; Helvetica/Liberation Sans/DejaVu Sans are fallback
fonts. Font changes can alter bounds, so reruns must pass overlap checks and be
visually reviewed at final size. Source ± intervals are not labelled as invented
confidence intervals. Hydrogen has an explicitly labelled logarithmic scale.
