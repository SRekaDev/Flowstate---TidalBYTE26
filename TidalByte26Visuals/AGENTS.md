# Repository guidance

These instructions apply throughout the repository. Follow any more specific `AGENTS.md` in the directory you are editing.

# Goal
- Create a productivity tracker using data imported from a face tracker and keystroke tracker to measure focus and fatigue scores 

## Making changes

- Inspect the relevant files and `git status --short` before editing. Preserve existing user changes.
- Keep changes focused on the requested outcome. Follow existing code patterns, naming, and formatting as they emerge.
- Reuse existing code where it fits. Preserve behavior that callers rely on unless the task calls for a change.
- Use PowerShell for local shell commands and `rg` for searching when available.
- Keep secrets and credentials out of source files, logs, and commits. Ask before potentially destructive changes or publishing externally unless the user has already authorized the action.
- Keep the interface usable for windows

## Verification

- Use the build, lint, and test commands defined by the project once they exist. Start with the checks closest to the change.
- Review the diff for unintended changes. In the handoff, summarize what changed, which checks ran, and any verification gaps.
- Update this file when project structure or verification commands become established. Keep task-specific notes in the relevant issue, pull request, or documentation.

