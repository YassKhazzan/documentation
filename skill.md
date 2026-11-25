---
name: livehq
description: Help a person host apps and databases on their own Linux server with LiveHQ. Use when they want to connect a server, deploy an app from GitHub, add PostgreSQL or Redis, set up a custom domain, secure the server, or work out why a deployment or an app failed.
compatibility: LiveHQ has no public API and no command-line tool. A person carries out every step in the web console at https://console.livehq.dev.
metadata:
  author: livehq
  version: "1.0"
---

# LiveHQ

LiveHQ turns a Linux server that a person rents into their own cloud. They paste one
install line into the server, then manage everything in a web console: deploy apps from
GitHub, run PostgreSQL and Redis, add domains, read logs. An agent on the server builds
and runs everything in Docker. Visitors reach apps through LiveHQ's edge and an encrypted
tunnel that the server opens outward, so the server needs no open web ports.

## What you can do

You cannot operate LiveHQ yourself: it has no API and no CLI. You help the person by:

- telling them which page to open and which button to press, with the console's exact
  labels;
- preparing their repository so that it deploys (listen on `PORT`, answer the health
  check, add a `Dockerfile` when needed);
- reading a deployment's copied logs or an app's restart summary and saying what is wrong;
- saying plainly when LiveHQ cannot do what they ask, and what to do instead.

## Read the documentation first

The documentation is at https://livehq.mintlify.app. Add `.md` to any page address for
Markdown, or read https://livehq.mintlify.app/llms.txt for the index.

Start with these four pages:

- https://livehq.mintlify.app/agents/reference.md — the objects, where each thing is in the
  console, roles, how apps and databases run.
- https://livehq.mintlify.app/agents/order-of-operations.md — what must exist before what, and
  the steps of each common job.
- https://livehq.mintlify.app/agents/status-words.md — every status the console shows.
- https://livehq.mintlify.app/agents/limits.md — every number: plans, sizes, time limits.

Then https://livehq.mintlify.app/help/known-limits.md and
https://livehq.mintlify.app/help/troubleshooting.md.

## Rules

1. Never invent an API endpoint, a `livehq` command or a configuration file. The only
   commands are the install line and the private SSH command that the console generates,
   and the `livehq-agent` commands the documentation names.
2. Use the labels the documentation puts in bold. If you do not know a label, say so.
3. Never ask the person to paste a password, an enrollment code, a recovery code, a
   private SSH command, a connection URL or a variable's value.
4. Before a step that restarts something, deletes data, costs money or could lock the
   person out, say so.
5. Check the plan and the role a step needs before you send the person to it.
6. Ask what the banner on the app's Overview says before you guess at a cause: LiveHQ
   explains most failures in plain words and often offers a one-click fix.

## The order of a first setup

1. Create an account at https://console.livehq.dev/signup.
2. Rent a server: Ubuntu 22.04, 24.04 or 26.04, or Debian 12 or 13; 2 vCPU and 4 GB of
   memory is a comfortable start.
3. Open the server with SSH.
4. In the console open **Connect a server**, name the server, copy the command, press
   **Create enrollment code**. Paste the command on the server, then the code when asked.
   A code works once, for 30 minutes.
5. Connect GitHub: **GitHub** in the sidebar, **Connect GitHub**, share the repository.
6. Deploy: **New**, **GitHub repository**, pick the repository, check the app port and
   who can open it, press **Deploy application**.
7. The deployment reads **Live**. The app's address is `name.livehq.app`. A new app is
   **Private** until the person changes it under **Settings & access**.

Someone who has never rented a server should use the console's own guide: **Guide me,
step by step** on Home.

## What LiveHQ does not do

No bare domains (`www.example.com` works, `example.com` does not). No scheduled jobs. No
autoscaling. No persistent disk for apps. No raw TCP or UDP for apps. No preview
deployments per branch. No point-in-time recovery: database backups are scheduled, on Pro
and Teams. One deployment at a time per server, and builds run on the person's own server.
LiveHQ does not check an app from outside the server.

## Plans

Free: 1 server, 3 apps, 3 databases, 10 GB of bandwidth a month, no custom domains, no
backups. Pro, $15 a month: 3 servers, 30 apps, 30 databases, 5 custom domains, 2 TB,
backups. Teams, $49 a month: 10 servers, 100 apps, 100 databases, 10 custom domains, 5 TB,
5 members with roles. Details: https://livehq.mintlify.app/account/plans.md
