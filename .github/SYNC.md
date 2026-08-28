# Keeping the pages current

The written pages describe the FormBharo API: its endpoints, the fields you send,
the values that are allowed. That moves without anyone here noticing.
[`sync-from-spec.yml`](workflows/sync-from-spec.yml) watches for it.

The pages are prose, not generated, so they cannot be rebuilt from the API
description. Instead Claude reads what changed, reads the pages, and makes the
edits the change calls for. The result opens as a pull request. Nothing is merged
automatically.

The API reference pages are not part of this. They are drawn from
`api-reference/openapi.json` and follow the API on their own.

## Where the change comes from

`form-fill-agent` deploys to production, then commits the API schema into this
repo. The history of `api-reference/openapi.json` here is the record of what the
API looked like after every deploy, and that commit is what starts a run.

```
form-fill-agent ──(deploy)──► formbharo-docs   commits api-reference/openapi.json
                                               │
                                               └─► that push starts this run,
                                                   which diffs the last two
                                                   versions, Claude edits → PR
```

Nothing is cloned and no token is needed to read the schema, because it is
already here. The commit starts a run because `form-fill-agent` makes it with a
personal token; a push made with GitHub's own token would not start anything.

## What a run does

1. Takes the two most recent commits that touched `api-reference/openapi.json`.
   Both copies are rewritten with sorted keys first, so the difference shows real
   API changes rather than however the schema happened to be written that day.
2. If they match, or there is only one, the run stops there and costs nothing.
3. Otherwise Claude gets the difference, reads the pages, and edits what the
   change makes wrong or incomplete. Most API changes touch nothing here.
4. If Claude changed nothing, no pull request opens.
5. If Claude did change something, `check_docs_rules.py` runs, one pull request
   opens on `automated/spec-sync`, and an email goes out with the link if the
   mail secrets below are set.

It can also be started by hand from the Actions tab, which is the way to catch a
deploy whose push did not start a run.

## Reruns are safe

The branch is fixed, so a second run over the same API change updates that pull
request instead of opening another one. And once it is merged, a rerun reads the
same difference, finds the pages already correct, and opens nothing.

## Config on this repo

- **Secret `CLAUDE_CODE_OAUTH_TOKEN`** — required, and already set for the style
  rules check. Without it the step that works out what the pages need cannot run.
- **Secret `DOCS_SYNC_TOKEN`** — optional. A token so the pull request starts the
  style rules check; one opened by GitHub's own token does not start further
  checks. Without it the pull request still opens, just unchecked.
- **Secrets `MAIL_SERVER`, `MAIL_PORT`, `MAIL_USERNAME`, `MAIL_PASSWORD`** —
  optional. Without them the pull request still opens and GitHub still emails the
  assignee; only the extra email is skipped.

## When the pull request is wrong

Claude wrote it, so read it as a draft by a colleague rather than a fact. The
body says which files changed and why, and whether the mechanical rules pass.
Edit the branch and merge it, or close it. Closing loses nothing: the next deploy
that changes the API opens a fresh one.
