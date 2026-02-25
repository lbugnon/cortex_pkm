# Nvim Integration

Cortex uses `[Title](stem.md)` for internal link targets, which enables
native editor navigation without any plugins.

## Link navigation (`gf`)

With `.md` in link targets, `gf` in nvim jumps directly to the linked file.
No configuration needed — it works out of the box. VSCode also navigates
`.md` links natively.

## Link insertion (Telescope)

Save the following to `~/.config/nvim/lua/plugins/cortex.lua`:

```lua
---@diagnostic disable: lowercase-global

local function insert_cortex_link(include_archive)
  return function()
    local vault = vim.env.COR_VAULT or vim.fn.expand("~/vault")
    
    -- Build find command based on archive preference
    local find_cmd = { "fd", "--extension", "md" }
    if not include_archive then
      table.insert(find_cmd, "--exclude")
      table.insert(find_cmd, "archive")
    end
    
    require("telescope.builtin").find_files({
      cwd = vault,
      prompt_title = include_archive and "Insert Link (with archive)" or "Insert Note Link",
      find_command = find_cmd,
      attach_mappings = function(prompt_bufnr)
        local actions = require("telescope.actions")
        local state = require("telescope.actions.state")
        actions.select_default:replace(function()
          actions.close(prompt_bufnr)
          local entry = state.get_selected_entry()
          if not entry then
            return
          end
          
          -- Get path relative to vault (preserves subfolders like ref/paper.md)
          local relpath = vim.fn.fnamemodify(entry.value, ":.")
          local stem = vim.fn.fnamemodify(entry.value, ":t:r")
          
          vim.api.nvim_put({"[" .. stem .. "](" .. relpath .. ")"}, "c", true, true)
        end)
        return true
      end,
    })
  end
end

local function show_backlinks()
  local vault = vim.env.COR_VAULT or vim.fn.expand("~/vault")
  local current_file = vim.fn.fnamemodify(vim.fn.expand("%"), ":t:r")
  
  require("telescope.builtin").grep_string({
    cwd = vault,
    search = "](" .. current_file .. ".md)",
    prompt_title = "Backlinks to " .. current_file,
    -- Exclude the current file itself
    additional_args = function()
      return { "--glob", "!" .. vim.fn.expand("%:t") }
    end,
  })
end

return {
  {
    "nvim-telescope/telescope.nvim",
    keys = {
      -- Insert link to active notes (default)
      {
        "<C-l>",
        insert_cortex_link(false),
        mode = "i",
        desc = "Cor: insert note link",
        ft = "markdown",
      },
      -- Insert link including archive
      {
        "<C-S-l>",
        insert_cortex_link(true),
        mode = "i",
        desc = "Cor: insert note link (with archive)",
        ft = "markdown",
      },
      -- Show backlinks
      {
        "<leader>bl",
        show_backlinks,
        mode = "n",
        desc = "Cor: show backlinks",
        ft = "markdown",
      },
    },
  },
}
```

### Keymaps

| Key | Mode | Action |
|-----|------|--------|
| `<C-l>` | Insert | Insert link to note (excludes archive) |
| `<C-S-l>` | Insert | Insert link to note (includes archive) |
| `<leader>bl` | Normal | Show files that link to current file |

### Environment Variable

Set `COR_VAULT` in your shell environment:

```sh
export COR_VAULT=~/notes
```

Add to your `~/.bashrc` or `~/.zshrc` to make it permanent.

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

## Alternative: Vanilla nvim (no Telescope)

If you prefer not to use Telescope, use this simpler version:

```lua
-- ~/.config/nvim/after/ftplugin/markdown.lua
vim.keymap.set("i", "<C-l>", function()
  local vault = vim.env.COR_VAULT or vim.fn.expand("~/vault")
  local files = vim.fn.globpath(vault, "**/*.md", false, true)
  
  -- Filter out archive by default
  files = vim.tbl_filter(function(f)
    return not f:match("/archive/")
  end, files)
  
  vim.ui.select(files, {
    prompt = "Insert Note Link",
    format_item = function(item)
      return vim.fn.fnamemodify(item, ":.")
    end,
  }, function(choice)
    if choice then
      local relpath = vim.fn.fnamemodify(choice, ":.")
      local stem = vim.fn.fnamemodify(choice, ":t:r")
      vim.api.nvim_put({"[" .. stem .. "](" .. relpath .. ")"}, "c", true, true)
    end
  end)
end, { desc = "Cor: insert note link" })
```