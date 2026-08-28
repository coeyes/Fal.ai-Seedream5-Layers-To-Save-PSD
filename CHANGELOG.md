# Changelog

All notable changes to this project will be documented in this file.

## [1.0.0] - 2026-08-28

First release.

### Added
- `make_psd.py`: converts a fal.ai Seedream 5 Pro Layerize result JSON into a PSD with **Embedded Smart Objects** — pure Python (psd-tools low-level assembly), no Photoshop required
- Each layer embedded at its original high resolution and transform-placed by its bounding box; `z_index 0` becomes the `background` layer and defines the canvas size
- Workaround for a psd-tools bug (missing `LinkedLayer` v8 `contentID` descriptor) that made Photoshop reject generated files — see [TECH.md](TECH.md)
- Filename sanitization and case-insensitive duplicate suffixes for layer names
- `--gen-layers-folder` (default on): also saves each layer PNG to `<output>.psd_layers/<zindex>_<layername>.png`
- `gui.py`: tkinter GUI — paste JSON, pick output folder/name, Run; non-blocking worker with status log; English / Korean / Japanese UI (auto-detected); link to the fal.ai model page
- `build.bat`: PyInstaller one-file windowed build with `icon.png` → `.ico` conversion
- Standalone Windows exe published on GitHub Releases

[1.0.0]: https://github.com/coeyes/Fal.ai-Seedream5-Layers-To-Save-PSD/releases/tag/v1.0.0
