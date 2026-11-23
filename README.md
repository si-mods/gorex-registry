# GoRex Community Icon Pack Registry

Static index of community program icon packs for GoRex (`docs/MOD-012-program-icon-packs.md`).

## Adding a Pack

1. Create a pack repository (or add a directory under `packs/` for official starter packs) with a valid `pack.json` (`schema: 1`) and SVG/PNG assets (`<= 32 KiB`).
2. Add an entry to `packs.json` and open a pull request.
3. GitHub Actions validates every pack and rebuilds `index.json` on `main`.
