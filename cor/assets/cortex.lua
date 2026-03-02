---@diagnostic disable: lowercase-global

local function get_vault()
  if vim.env.COR_VAULT then return vim.env.COR_VAULT end
  local cfg = vim.fn.expand("~/.config/cor/config.yaml")
  if vim.fn.filereadable(cfg) == 1 then
    for _, line in ipairs(vim.fn.readfile(cfg)) do
      local vault = line:match("^vault:%s*(.+)")
      if vault then return vim.fn.expand(vim.trim(vault)) end
    end
  end
  return vim.fn.expand("~/vault")
end

local function insert_cor_link(include_archive)
  return function()
    local vault = get_vault()
    local files

    if vim.fn.executable("fd") == 1 then
      local excl = include_archive and "" or " --exclude archive"
      files = vim.fn.systemlist("cd " .. vim.fn.shellescape(vault) .. " && fd --extension md" .. excl)
    else
      files = vim.fn.globpath(vault, "**/*.md", false, true)
      files = vim.tbl_map(function(f) return vim.fn.fnamemodify(f, ":.") end, files)
      if not include_archive then
        files = vim.tbl_filter(function(f) return not f:match("/archive/") end, files)
      end
    end

    table.sort(files, function(a, b)
      return vim.fn.getftime(vault .. "/" .. a) > vim.fn.getftime(vault .. "/" .. b)
    end)

    vim.ui.select(files, {
      prompt = include_archive and "Insert Link (with archive)" or "Insert Note Link",
    }, function(choice)
      if not choice then return end
      local stem = vim.fn.fnamemodify(choice, ":t:r")
      vim.api.nvim_put({ "[" .. stem .. "](" .. choice .. ")" }, "c", true, true)
    end)
  end
end

local function show_backlinks()
  local vault = get_vault()
  local stem = vim.fn.fnamemodify(vim.fn.expand("%"), ":t:r")
  local search = vim.fn.shellescape("](" .. stem .. ".md)")
  local current_file = vim.fn.expand("%:t")

  local results = vim.fn.systemlist(
    "cd " .. vim.fn.shellescape(vault) .. " && rg --with-filename --line-number " .. search
    .. " --glob '!" .. current_file .. "'"
  )

  if #results == 0 then
    vim.notify("No backlinks to " .. stem, vim.log.levels.INFO)
    return
  end

  vim.ui.select(results, {
    prompt = "Backlinks to " .. stem,
  }, function(choice)
    if not choice then return end
    local file, line = choice:match("^([^:]+):(%d+):")
    if file then
      vim.cmd("edit " .. vim.fn.fnameescape(vault .. "/" .. file))
      vim.api.nvim_win_set_cursor(0, { tonumber(line), 0 })
    end
  end)
end

-- Buffer-local keymaps for markdown files only
vim.api.nvim_create_autocmd("FileType", {
  pattern = "markdown",
  callback = function()
    vim.keymap.set("i", "<C-l>", insert_cor_link(false), { buffer = true, desc = "Cor: insert note link" })
    vim.keymap.set("i", "<C-S-l>", insert_cor_link(true), { buffer = true, desc = "Cor: insert note link (with archive)" })
    vim.keymap.set("n", "<leader>bl", show_backlinks, { buffer = true, desc = "Cor: show backlinks" })
  end,
})

return {}
