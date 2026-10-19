--[[
Hide draw.io's "Text is not SVG - cannot display" line in PDF output.

When draw.io saves a .drawio.svg, it writes each label as HTML inside a
<foreignObject> with a plain <text> fallback, and appends one extra fallback
line linking to its "SVG export text problems" FAQ. rsvg-convert, which turns
the SVG into PDF, cannot draw <foreignObject>, so it uses every fallback: the
labels come out right, but the warning line shows under the figure.

This filter points each .drawio.svg image at a copy in .quarto/drawio/ with
that one warning removed. The file in figures/ stays exactly as draw.io saved
it, so it can still be edited in draw.io.

  filters:
    - path: ../../templates/writeup/drawio-svg.lua
      at: pre-quarto
]]

local OUT_DIR = ".quarto/drawio"
local WARNING = "svg-export-text-problems"

-- Remove the <switch> ... </switch> block that holds draw.io's warning link.
local function strip_warning(svg)
  local hit = svg:find(WARNING, 1, true)
  if not hit then
    return svg
  end
  local start, pos = nil, 1
  while true do
    local s = svg:find("<switch", pos, true)
    if not s or s > hit then
      break
    end
    start, pos = s, s + 1
  end
  local _, finish = svg:find("</switch>", hit, true)
  if not start or not finish then
    return svg
  end
  return svg:sub(1, start - 1) .. svg:sub(finish + 1)
end

function Image(img)
  if not FORMAT:match("latex") or not img.src:match("%.drawio%.svg$") then
    return nil
  end
  local f = io.open(img.src, "r")
  if not f then
    return nil
  end
  local svg = f:read("a")
  f:close()
  local cleaned = strip_warning(svg)
  if cleaned == svg then
    return nil
  end
  pandoc.system.make_directory(OUT_DIR, true)
  local out = OUT_DIR .. "/" .. img.src:gsub("[/\\]", "_")
  local o = assert(io.open(out, "w"))
  o:write(cleaned)
  o:close()
  img.src = out
  return img
end
