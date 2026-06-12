---
name: review-loop
description: >-
  Continuously review and merge the oldest open PR: delegate code review to a
  fresh subagent per PR, merge on approval, loop until no PRs remain.
  Use when user types `/review-loop` or asks to review-and-merge all open PRs.
---

# Review Loop

Triggered by `/review-loop`. Loops: fetch oldest open PR → delegate thorough review to a fresh subagent → merge if approved → repeat. The main context stays small — each PR is handled by an ephemeral subagent.

## Loop protocol

1. **Fetch** the oldest open PR:
   ```
   gh pr list --state open --limit 1 --json number,title,headRefName,baseRefName
   ```
   If empty → print "No open PRs — all clear!" and stop.

2. **Get PR diff and details** in the main context:
   ```
   gh pr view <number> --json number,title,body,state,mergeable,reviews
   gh pr diff <number>
   ```

3. **Delegate** review to a subagent via the `task` tool. Use `subagent_type: "general"` with a prompt containing:
   - The full PR diff, title, body, branch names, and existing reviews
   - Instructions to perform a thorough code review covering:
     * **Correctness** — does the change do what it claims? Edge cases handled?
     * **Security** — any injection, auth bypass, secret leaks, unsafe deps?
     * **Style/conventions** — matches the codebase's patterns and idioms?
     * **Test quality** — are there tests? Do they actually test the right thing?
     * **Performance** — any obvious regressions or N+1 problems?
     * **Dependencies** — new packages vetted? Lockfile updated?
   - Tell the subagent: "Return exactly one of: 'VERDICT: APPROVE' with optional improvement suggestions, or 'VERDICT: BLOCK' with a clear list of blocking issues. Be decisive — do not hedge."
   - Tell the subagent: "Do not use the task tool. Review this one PR and return your verdict."

4. **Act on the verdict**:
   - If APPROVE → merge the PR:
     ```
     gh pr merge <number> --squash
     ```
     Print the merged PR URL and the verdict summary.
   - If BLOCK → print the blocking issues in the main output. Ask the user whether to:
     * Skip and move to next PR
     * Add a review comment with the blocking issues via `gh pr comment <number> --body "..."` then skip
     * Stop the loop

5. **Log** the outcome into `review-loop-progress.md` (PR number, title, verdict, action).

6. **Repeat** from step 1.

## Context management

- Each PR is handled by a fresh ephemeral subagent — the main context barely grows.
- Update `review-loop-progress.md` after each PR.
- If `task` tool is unavailable, handle PRs directly but only **one** per invocation and instruct the user to run `/review-loop` again.

## Safety

- Stop if `gh` auth fails.
- Blocked PRs pause the loop — the main agent asks the user what to do.
- Never merge a PR with blocking issues unless the user explicitly overrides.
- Subagent must return a clear, unambiguous verdict (APPROVE or BLOCK).
- Do not push, commit, or force-push to the PR branch.
