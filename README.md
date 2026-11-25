# GoRex Community Pack Registry

Static index of community packs for GoRex: program icon packs (`docs/MOD-012-program-icon-packs.md`) and theme packs (`docs/DSK-008-theme.md`).

## Adding a Pack

1. Create a pack repository (or add a directory under `packs/` for official starter packs) with a valid `pack.json` (`schema: 1`) and SVG/PNG assets (`<= 32 KiB`).
2. Add an entry to `packs.json` and open a pull request.
3. GitHub Actions validates every pack and rebuilds `index.json` on `main`.

## Adding a Theme

A theme pack is a directory with one `theme.json`: a manifest of colors for GoRex's own window, as data only (`docs/DSK-008-theme.md`).

```json
{
  "name": "Slate",
  "seeds": { "light": { "accent": "#3b6ea8" }, "dark": { "accent": "#7fa7d9" } },
  "roles": { "sideBar.tabActiveBackground": { "light": "#ffffffee", "dark": "#2c3542" } },
  "terminal": { "light": "Ayu Light", "dark": "Ayu" }
}
```

- Seed keys are GoRex's seed names (`bgTop`, `text`, `panel`, `accent`, ...); a seed you leave out keeps GoRex's own. Role keys are `sideBar.*` role names. Values are `#rgb`, `#rgba`, `#rrggbb` or `#rrggbbaa`; a role may take `{"light", "dark"}`.
- `terminal` is optional. It names a Ghostty theme for each appearance, as GoRex's terminal theme picker lists them (a theme Ghostty ships). It applies only when the user has not set `terminal.theme`. GoRex builds before the `terminal` key drop it with a warning and keep the terminal's colors.
- A theme ported from another project carries that project's license in a `NOTICE` file in its folder.
- Add an entry with `"kind": "theme"` to the `themes` list of `packs.json` and of `index.json`, not to `packs`: GoRex builds before theme packs read only `packs`.
- `gorex pack install <id>` installs it as `<config>/themes/<id>.json`; `"appearance.theme": "<id>"` in `settings.json` selects it.

### A theme with images and shaders, in its own repo

A theme can carry images and `.kage` shader sources: its shaders draw the window's background and the faces of roles, and read up to four image assets each (`docs/DSK-012-theme-shaders.md` of si-mods/gorex). Such a pack lives in a public repo of its own, not in this registry: its root holds `theme.json`, an `assets/` folder, a `NOTICE` and each license text the `NOTICE` names.

- List it with `repo` (an https clone URL ending in `.git`), no `subdir`, and `ref`: the full 40-character commit SHA to install. A branch or a tag is refused, as its owner can move it. GoRex installs that commit and nothing else, so a later push to the pack's repo changes nothing until a registry PR moves `ref`.
- CI clones the repo at `ref` and checks the files users get: the caps GoRex enforces (24 assets, a `.kage` source of 16 KiB, PNG, GIF and APNG images of 1 MiB and 1024 px — or 2 MiB and 2048 px for an image only shaders read — animated images of 512 px, 64 frames and 16 MiB decoded, 8 MiB a pack), the asset names the manifest uses, a `NOTICE` for a pack with assets, and each `LICENSE*` file the `NOTICE` names. `scripts/theme_assets.py` holds the checks.
- List a pack only when the license of each asset allows redistribution.
