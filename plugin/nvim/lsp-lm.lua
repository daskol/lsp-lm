--[[
-- Experimental configuration of built-in Neovim LSP client.
--]]

--[[
-- Use built-in Neovim LSP client (without neovim/lspconfig).
--]]

local lspconfig = require('lspconfig')
lspconfig.configs = require('lspconfig/configs')
lspconfig.util = require('lspconfig/util')

function on_attach(client, bufnr)
  -- Enable completion triggered by <c-x><c-o>
  vim.api.nvim_buf_set_option(bufnr, 'omnifunc', 'v:lua.vim.lsp.omnifunc')
end

lspconfig.configs['txt'] = {
  default_config = {
    cmd = {'python3', '-m', 'lsp', 'serve'},
    filetypes = { 'txt' },
    root_dir = function(fname)
      return (lspconfig.util.find_git_ancestor(fname) or
              lspconfig.util.path.dirname(fname))
    end,
    log_level = vim.lsp.protocol.MessageType.Warning,
  },
}

lspconfig['txt'].setup {
    on_attach = on_attach,
}

--[[
-- If we want autocompletion support then we should use some autocompletion
-- plugin, for example, hrsh7th/nvim-cmp.
--]]

local cmp = require('cmp')

cmp.setup({
  mapping = {
    ['<C-d>'] = cmp.mapping.scroll_docs(-4),
    ['<C-f>'] = cmp.mapping.scroll_docs(4),
    ['<C-Space>'] = cmp.mapping.complete(),
    ['<C-e>'] = cmp.mapping.close(),
    ['<CR>'] = cmp.mapping.confirm({ select = true }),
  },
  sources = {
    { name = 'nvim_lsp' },
    { name = 'buffer' },
  }
})

require('lspconfig')['txt'].setup {
  capabilities = require('cmp_nvim_lsp').update_capabilities(vim.lsp.protocol.make_client_capabilities())
}
