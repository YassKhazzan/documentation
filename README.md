# LiveHQ documentation

The user documentation of [LiveHQ](https://www.livehq.dev), published with
[Mintlify](https://mintlify.com). Pages are MDX files; `docs.json` holds the navigation and
the site settings.

## What is where

| Path | What it holds |
| --- | --- |
| `docs.json` | Navigation (three tabs: Documentation, Help, AI agents), colors, fonts, footer, redirects, and the instructions Mintlify adds to every Markdown page for AI agents (`markdown.instructions`). |
| `index.mdx`, `quickstart.mdx`, `start/` | Welcome, the one-page quickstart, the four-step path for people who have never rented a server, and the concept pages. |
| `servers/`, `apps/`, `databases/`, `network/`, `account/` | One page per job in the console. |
| `help/` | Troubleshooting by symptom, emails, outages, export, known limits, FAQ, glossary. |
| `agents/` | The compact reference for AI agents: model, order of operations, status words, limits. |
| `skill.md` | The skill file AI agents can install. Written by hand. |
| `images/console/` | Console screenshots (`.webp`), all taken with the example workspace "Acme Studio". |
| `logo/`, `favicon.svg` | The LiveHQ mark and wordmark. |
| `style.css` | A few rules for the serif headings. Mintlify loads it by itself. |
| `AGENTS.md` | The style guide. Read it before you write or let an agent write. |
| `scripts/check.py` | The link, image and configuration check. |

## Before you commit

```bash
python3 scripts/check.py
```

It needs only Python 3. It fails when a page in the navigation is missing, a link, anchor
or image does not resolve, a page has no title or description, a component tag is left
open, or placeholder text, a credential-looking value or an unexpected email address is
left in a page.

To also check `docs.json` against Mintlify's published schema:

```bash
curl -sL https://mintlify.com/docs.json -o /tmp/mintlify-docs.schema.json
python3 scripts/check.py --schema /tmp/mintlify-docs.schema.json
```

## Preview locally

Mintlify's command-line tool renders the site on your computer. It is not needed to
publish.

```bash
npm i -g mint
mint dev
```

The preview opens at `http://localhost:3000`. `mint broken-links` and `mint validate` are
Mintlify's own checks.

## Publish

Mintlify deploys the default branch when its GitHub App is installed on this repository.
A pull request gets a preview address.

## Keeping the docs true

- **The console's words.** Every label in bold is the text of a button, a tab or a status
  in the console. When the console changes a label, change it here.
- **Numbers live in two places.** A plan limit or a time limit appears on its task page and
  on `agents/limits.mdx`; a status word on its task page and on `agents/status-words.mdx`.
  Change both.
- **Dated facts.** The hosting companies and prices on `start/rent-a-server.mdx` were read
  on 23 November 2026, the same day as the console's own setup guide. Refresh them together.
- **Screenshots.** They were taken on 6 November 2026 with made-up data. Never capture a
  real workspace. Name new files for what they show and store them at 2000 px wide.
- **Limits are said plainly.** `help/known-limits.mdx` is the single list of what LiveHQ
  does not do. Add to it when a page has to say "not yet".
