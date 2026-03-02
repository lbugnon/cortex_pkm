# Nvim Integration

Cortex uses `[Title](stem.md)` for internal link targets, which enables
native editor navigation without any plugins. Lazy.nvim plugin is recommended.

  git clone https://github.com/LazyVim/starter ~/.config/nvim

The plugin uses `vim.ui.select`, so it works with any LazyVim picker
(snacks.picker, fzf-lua, or telescope) without installing anything extra.

**Requirements:** `fd` (file listing) and `rg` (backlinks search).

## Link navigation (`gf`)

With `.md` in link targets, `gf` in nvim jumps directly to the linked file.
No configuration needed — it works out of the box. VSCode also navigates
`.md` links natively.

### Link insertion Keymaps

| Key | Mode | Action |
|-----|------|--------|
| `<C-l>` | Insert | Insert link to note (excludes archive) |
| `<C-S-l>` | Insert | Insert link to note (includes archive) |
| `<leader>bl` | Normal | Show files that link to current file |


## How it works

### Link format

Links are inserted with the **relative path** from vault root:

```markdown
- [paper](ref/paper.md)      ← references in subfolders keep their path
- [ideas](project.ideas.md)  ← flat notes work too
```

### Backlinks

The `<leader>bl` command searches for all files containing links to the current
file. It uses `rg` (ripgrep) under the hood, so it's fast even in large vaults.

This is a **read-only** operation — unlike some note-taking tools, Cortex does
not auto-modify files to add backlink sections. This keeps your files clean and
avoids git noise.

## Plugin source

The plugin is installed by `cor init` to `~/.config/nvim/lua/plugins/cortex.lua`.
