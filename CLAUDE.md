# CLAUDE.md

Guidance for working in this repository (the FormBharo documentation site, built with Mintlify).

## Writing style

Every page is written in Calibrate's docs style (docs.calibrate.artpark.ai) and
Pipecat's docs style (docs.pipecat.ai): short, plain, declarative sentences.

1. No em-dashes.
2. No marketing language ("powerful", "seamless", "cutting-edge").
3. No filler: every sentence states a fact or gives an instruction.
4. Prefer a table or short list over a paragraph for tabular content.
5. State what an endpoint or feature does, never why it works that way (no
   storage/implementation reasoning, no naming private functions or internals).
6. Never re-list a response's fields in prose when the response model already
   declares them (it renders as its own schema panel on the page).
7. No number in prose that just duplicates a count already shown by a table,
   list, or card grid right next to it (e.g. "three fields" above a 3-row
   table): state the fact, drop the number.
8. A `<Card>` one-line description does not end with a period.
9. Don't add a documentation page beyond what's been explicitly asked for.

Rules 1-6 also apply to `form-bharo`'s backend route docstrings, which generate
the API reference pages here; see that repo's `CLAUDE.md`.

## Structure

- Pages are `.mdx` files; navigation is set in `docs.json`.
- `api-reference/openapi.json` is pushed here by form-bharo's
  `deploy_backend.yml` after every production deploy. Do not hand-edit it.
- The server domain `https://api.formbharo.artpark.ai` is written literally in
  every page. Do not put it behind a snippet variable: MDX does not substitute
  variables inside code fences, so readers copy the raw placeholder. If the
  domain changes, grep-replace it across the repo.
