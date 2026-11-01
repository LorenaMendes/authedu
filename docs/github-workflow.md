# GitHub Work Organization

## Publication status

The private GitHub repository [LorenaMendes/authedu](https://github.com/LorenaMendes/authedu) has a `main` baseline containing the local planning and AI guidance files. Starter issues [#1](https://github.com/LorenaMendes/authedu/issues/1), [#2](https://github.com/LorenaMendes/authedu/issues/2), and [#3](https://github.com/LorenaMendes/authedu/issues/3) are closed; implementation PRs #4 and #5 were merged. The remaining roadmap is tracked by epics [#6–#9](https://github.com/LorenaMendes/authedu/issues/6) and foundation tasks [#10–#14](https://github.com/LorenaMendes/authedu/issues/10). The release milestone, custom labels, and Project board have not yet been created.

Continue with the GitHub organization steps below. Do not recreate the existing issues. Do not paste tokens or passwords into chat.

## Initial GitHub Setup

1. Confirm the repository's visibility and default branch are appropriate for the project.
2. Publish the project plan, these templates, and the contribution guide to its default branch.
3. Create milestone **v0.1 — Sessions, JWT, and Authorization**. Leave its due date unset until delivery estimates are meaningful.
4. Create the labels listed below.
5. Create a user-owned GitHub Project named **AuthEdu Development**, with private visibility initially unless the board is deliberately intended to be public.
6. Link the repository to the Project, and configure automatic addition of its open issues where supported. Add initial issues manually if automation is unavailable.
7. Add epics #6–#9 and foundation tasks #10–#14 to the v0.1 milestone and Project after creating them.
8. Attach #10–#14 as child issues of epic #6 using GitHub sub-issues. Record prerequisites using dependency relationships where available, otherwise issue links. Issues #2 and #3 are completed foundation slices and should not be duplicated.
9. Keep later modules as unmilestoned backlog epics when they become useful; do not expand them into detailed tasks yet.

Issue templates intentionally do not auto-apply labels or assignees: labels do not yet exist, and ownership should be chosen deliberately.

## Project Fields

| Field | Type | Values or usage |
| --- | --- | --- |
| Status | Single select | Backlog, Ready, In Progress, In Review, Done |
| Priority | Single select | P0 — Essential, P1 — Important, P2 — Later |
| Size | Single select | S, M, L; split large implementation tasks before starting |
| Milestone | Built-in issue field | Release target |
| Assignees | Built-in issue field | Person responsible |

P0 means essential for the selected milestone, not an emergency. An epic can remain In Progress across multiple child tasks; the solo work-in-progress limit applies to implementation tasks.

## Status Definitions

- **Backlog:** valuable work that is not yet actionable.
- **Ready:** scope, acceptance criteria, and verification are clear; prerequisites are complete.
- **In Progress:** actively being implemented.
- **In Review:** a linked pull request is ready for checks/review, including self-review when working solo.
- **Done:** merged and acceptance criteria verified. For an epic, its overall completion gate must also pass.

Use a `blocked` label and name the blocking issue; retain the item's actual workflow status. Do not duplicate statuses in labels.

## Labels

| Category | Labels |
| --- | --- |
| Work type | `type:epic`, `type:feature`, `type:bug`, `type:docs`, `type:chore` |
| Area | `area:backend`, `area:frontend`, `area:docs`, `area:infra` |
| Module | `module:sessions`, `module:authorization`, `module:jwt` |
| Dependency | `blocked` |

Use `type:epic` to identify parent issues without requiring custom issue types. Use sub-issues for work needing independent tracking and checklists for small steps within an issue.

## Project Views

- **Current work:** board grouped by Status; focus on implementation tasks.
- **First release:** table filtered to the v0.1 milestone, showing priority, size, assignee, and status.
- **Roadmap:** table filtered to `type:epic`, displaying sub-issue progress where supported.
- **Backlog:** table filtered to Backlog, sorted by Priority.

## Automation

- Enable the Project's issue-closed workflow to set Status to Done.
- Enable its issue-reopened workflow to return work to Backlog, if available; re-evaluate whether it is Ready.
- Move issues to In Review manually when their pull requests are ready. Automatically mapping a pull request's state to a separate linked issue requires additional automation; it is not assumed here.
- Include `Closes #NUMBER` in a pull request targeting the default branch so merging closes the implementation issue.
- Do not close epics automatically from individual pull requests.

## Regular Planning

At each planning pass:

1. Verify the current milestone's scope against the project plan.
2. Close work whose acceptance criteria are actually satisfied.
3. Resolve or document blockers.
4. Refine only the next few implementation tasks.
5. Move newly actionable tasks to Ready.
6. Keep one implementation task active at a time when working solo.

The [project plan](../project-plan.md) owns goals and release boundaries. GitHub Issues own task scope, dependencies, and execution progress. This local backlog is a publication seed, not a second live issue tracker.