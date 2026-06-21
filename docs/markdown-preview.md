# Markdown Preview

Markdown files (`.md`, `.markdown`, `text/markdown`) render as GitHub-style HTML by default.

A **Rendered / Source** toggle in the sidebar switches between the rich view and syntax-highlighted raw source.

## Query parameter

`?md_view=source` — open the file in source view.  
`?md_view=rendered` — open the file in rendered view (overrides a saved `source` session preference).

Any other value is ignored and falls back to the session preference or the default (rendered). The parameter is not reflected back into the URL when the user toggles the view.
