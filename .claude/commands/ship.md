---
name: ship
description: Update docs if needed, add comments to changed code, stage all changes, commit with a conventional message, push, and create a PR to main. Use when you're done with a session and want to ship your work.
argument-hint: "[optional commit message override]"
disable-model-invocation: true
allowed-tools: Bash, Read, Edit, Glob, Grep
---

# Ship: Comment, Commit, Push & PR

Ship all work from this session — update docs, add comments, commit, push, and open a PR to `main`.

## Step 1: Update Documentation (if necessary)

1. Run `git diff` and `git diff --cached` to see all modified files, and `git ls-files --others --exclude-standard` for untracked files
2. Read `CLAUDE.md` and the Development Roadmap (Section 5) in `docs/design-doc.md`
3. Determine if updates are needed:
   - **CLAUDE.md** — update if changes affect: project structure, key files, environment variables, coding conventions, architecture boundaries, or any section that no longer reflects reality
   - **Design doc roadmap** — update task status (mark tasks complete with `- [x]`, update partial progress) if the session's work completed or advanced a roadmap task
4. If updates are needed, make them. If nothing is out of date, skip silently — do not ask the user or add noise
5. Keep updates minimal and accurate — only change what the session's work invalidates

## Step 2: Review and Comment Changed Code

1. Run `git diff` and `git diff --cached` to see all modified files
2. Run `git ls-files --others --exclude-standard` to see untracked files
3. Read each changed/new file
4. Add brief clarifying comments ONLY where the logic is not self-evident. Do NOT over-comment — skip obvious code. Follow the project's existing comment style.
5. For Python files: use `#` comments.

## Step 3: Safety Check

Before staging, scan for sensitive files that should NEVER be committed:
- `.env`, `.env.*` files
- Private keys, API keys, tokens
- `credentials.json`, `secrets.*`, `*.pem`, `*.key`

If any are found, **STOP and warn the user**. Do NOT proceed until they confirm.

## Step 4: Stage All Changes

Run `git add .` to stage everything.

Then run `git status` to show the user what will be committed.

## Step 5: Commit

Analyze the staged diff (`git diff --cached`) and create a commit message:

- Use conventional commit format: `feat:`, `fix:`, `refactor:`, `chore:`, `docs:`, `test:`, etc.
- First line: concise summary under 72 characters
- If the changes are substantial, add a blank line followed by bullet points explaining the key changes
- Check if the changes implement (partially or fully) a task from the Development Roadmap in `docs/design-doc.md`. If so, include the task label in the first line (e.g., `feat(P1-T1): implement model upload endpoint`). If the changes are not related to a roadmap task, omit the label.

If the user provided `$ARGUMENTS`, use that as the commit message instead of auto-generating one.

**Before committing, present the draft commit message to the user and ask them to approve or edit it.** Do NOT run `git commit` until the user confirms. If the user provides edits, incorporate them.

Once approved, create the commit using a HEREDOC format:
```
git commit -m "$(cat <<'EOF'
<commit message here>

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

## Step 6: Push and Create PR

1. Get the current branch name: `git branch --show-current`
2. If on `main` or `master`, **STOP and warn the user** — they should be on a feature branch
3. Push to remote: `git push -u origin <branch-name>`
4. Create a PR targeting `main` using:

```
gh pr create --title "<short PR title>" --body "$(cat <<'EOF'
## Summary
<bullet points summarizing the changes>

## Test plan
<how to verify the changes work>

🤖 Generated with [Claude Code](https://claude.ai/code)
EOF
)"
```

5. Display the PR URL to the user

## Important Rules

- NEVER commit sensitive data (keys, tokens, passwords, .env files)
- NEVER force push
- NEVER push directly to main/master
- If any step fails, stop and report the error — do not continue blindly
