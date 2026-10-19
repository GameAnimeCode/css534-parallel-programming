--[[
Make the whole "Table 8" or "Figure 3" a link in PDF output.

Quarto renders a cross-reference such as @tbl-phases as three inlines:
  Str "Table", Str " " (non-breaking space), RawInline latex "\ref{tbl-phases}"
so only the number becomes a link. This filter swaps that sequence for
  \hyperref[tbl-phases]{Table~\ref*{tbl-phases}}
which links the word and the number together. The .qmd keeps the plain
@tbl-/@fig- syntax, so editor completion and link checking still work.

It must run after Quarto resolves cross-references:
  filters:
    - path: ../../templates/writeup/whole-ref-links.lua
      at: post-quarto
]]

local NBSP = "\u{00A0}"

function Inlines(inlines)
  if not FORMAT:match("latex") then
    return nil
  end
  local out = pandoc.Inlines({})
  local i = 1
  while i <= #inlines do
    local name, gap, ref = inlines[i], inlines[i + 1], inlines[i + 2]
    local label = ref and ref.t == "RawInline" and ref.format:match("tex")
      and ref.text:match("^\\ref{(.-)}$")
    if label and name.t == "Str" and gap and gap.t == "Str" and gap.text == NBSP then
      out:insert(pandoc.RawInline("latex",
        "\\hyperref[" .. label .. "]{" .. name.text .. "~\\ref*{" .. label .. "}}"))
      i = i + 3
    else
      out:insert(inlines[i])
      i = i + 1
    end
  end
  return out
end
