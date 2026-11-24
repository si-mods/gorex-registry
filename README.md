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
