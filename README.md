# FormBharo documentation

The source of the FormBharo documentation site, built with [Mintlify](https://mintlify.com).
Pages are `.mdx` files, and the navigation is set in `docs.json`.
`api-reference/openapi.json` is pushed here by form-bharo's `deploy_backend.yml`
after every production deploy, so it always matches the code that is live. Do not
hand-edit it: change the API in form-bharo and it is copied over on the next deploy.
