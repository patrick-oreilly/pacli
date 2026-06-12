---
name: run-loop
description: >-
  Continuously resolve the oldest open GitHub issue: delegate fix to a
  subagent, track PR URLs, loop until no issues remain.
  Use when user types `/run-loop`.
---

# Run Loop

Triggered by `/run-loop`. Loops in the current context: fetch issue → delegate to subagent → log PR → repeat. The main context stays small — subagents do the heavy editing/testing for each issue and are ephemeral.

## Loop protocol

1. **Fetch** the oldest open issue:
   ```
   gh issue list --limit 1 --state open --json number,title
   ```
   If empty → print "All clear!" and stop.

2. **Read** the issue title and body:
   ```
   gh issue view <number>
   ```

3. **Delegate** to a subagent via the `task` tool. Use `subagent_type: "build"` with a prompt containing:
   - The full issue content (number, title, body)
   - Instructions to: understand the issue → find relevant code → apply the fix → run `gh issue view <number>` to check test command → run tests until green → create branch `fix/issue-<number>` → commit with message `"fix: <title>"` → `gh pr create --fill` → return the PR URL
   - Tell the subagent: "Do not use the task tool. Do not loop. Fix this one issue and return."

4. **Log** the returned PR URL into `progress.md` (update the issue row to 🟢 Closed).

5. **Repeat** from step 1.

## Context management

- Each issue is handled by an ephemeral subagent — the main context barely grows.
- Update `progress.md` after each PR with the PR URL.
- If `task` tool is unavailable, fall back to handling issues directly but only do **one** per `/run-loop` invocation and instruct the user to run `/run-loop` again.

## Safety

- Stop if `gh` auth fails.
- Stop if no test runner detected (ask user).
- Subagent must not create a PR if tests fail (instruct it to keep iterating).
- Subagent must not force-push.
