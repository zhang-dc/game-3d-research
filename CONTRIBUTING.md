# Contributing

This repository is a research log, not a maintained library. Useful contributions:

- **Reproductions and counter-results.** If you tried one of the rejected approaches and it worked for you (or a "working"
  one failed), open an issue with the setup, numbers and side-by-side renders. Negative results are welcome.
- **Bug fixes** in the tools, especially hard-coded assumptions that block reuse.
- **Clarifications** of the docs.

Guidelines:

- Keep the evaluation rules in [docs/methodology.md](docs/methodology.md): report measurements, not impressions; one change per PR where possible.
- No model weights, generated images or meshes, or third-party assets in PRs. Small figures for docs go in `docs/img/`, each under 500 KB.
- No secrets, tokens, personal paths or internal URLs. Paths go through arguments or environment variables.
- Python: standard library + numpy/scipy/pillow/trimesh for plain scripts; Blender scripts must run with `blender -b --factory-startup`.
- By contributing you agree that code is licensed under MIT and documentation under CC BY 4.0.

Docs are mostly written in Chinese; English contributions are fine.
