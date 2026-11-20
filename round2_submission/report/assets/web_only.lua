-- Drops blocks marked ::: web-only from the PDF (the PDF has its own title page).
function Div(el)
  if el.classes:includes('web-only') and FORMAT:match('latex') then return {} end
end
