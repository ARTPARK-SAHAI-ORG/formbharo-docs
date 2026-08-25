# FormBharo documentation

The source of the FormBharo documentation site, built with [Mintlify](https://mintlify.com).
Pages are `.mdx` files, and the navigation is set in `docs.json`.
`api-reference/openapi.json` is synced automatically from the live FormBharo server
by `.github/workflows/sync-api-spec.yml`, on every production deploy and weekly as a
backup. Do not hand-edit it.
