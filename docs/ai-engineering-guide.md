# Using AI to build AuthEdu

This repository includes a small, project-specific Copilot setup. It is intentionally not a large collection of personas: one delivery agent can implement and test a feature, and a separate read-only reviewer provides an independent security perspective.

## The pieces

| File | What it does | When it is used |
| --- | --- | --- |
| [.github/copilot-instructions.md](../.github/copilot-instructions.md) | Shared project context and security guardrails. It tells Copilot what AuthEdu is, which documents are authoritative, and what must never be exposed. | Automatically for workspace Copilot conversations. Keep it short and broadly relevant. |
| [.github/agents/authedu-feature-engineer.agent.md](../.github/agents/authedu-feature-engineer.agent.md) | User-selectable implementation agent. It inspects the task and code, plans a small slice, implements it, tests it, checks the diff, and reports what you learned. It may delegate security review. | Choose **AuthEdu Feature Engineer** in VS Code's agent picker for a feature, issue, or bug. |
| [.github/agents/authedu-security-reviewer.agent.md](../.github/agents/authedu-security-reviewer.agent.md) | Independent, read-only security reviewer with read, search, and web research tools. It reports actionable findings; it cannot change the implementation. | Use after security-sensitive work, or let the feature engineer invoke it. |
| [.github/skills/secure-feature-delivery/SKILL.md](../.github/skills/secure-feature-delivery/SKILL.md) | Reusable checklist for the complete feature lifecycle, including tests, review, and a teaching explanation. | Invoke `/secure-feature-delivery` when you want that workflow while using your usual agent. |

A **custom agent** changes who is doing the work and what tools/role they have. A **skill** is reusable, on-demand know-how loaded into the current agent. **Instructions** are standing context—not a task queue and not a substitute for tests.

## A good first workflow

1. The project owner approved the initial stack targets in GitHub issue #1: FastAPI, PostgreSQL 18 with SQLAlchemy/migrations, React/Vite, CPython 3.14.10, Node.js 26.13, `uv`, and `npm`. The compatibility review and decision record are complete; the application is not yet scaffolded. The plan's pytest/httpx, Playwright, and Docker Compose recommendations should be checked against each task rather than assumed implemented.
2. Choose **AuthEdu Feature Engineer** in the agent picker and start with issue #2: “Implement the minimal Python API health service. Follow the completed stack decision in `docs/technology-decisions.md`; verify current pins before scaffolding, then show me your plan and explain the health check and tests.”
3. Review the plan before the implementation progresses. Correct assumptions early; AI is most useful when you give it acceptance criteria and constraints, not just a feature name.
4. Inspect the diff and test results. Ask the security reviewer to review authentication, authorization, credential storage, cookies, CSRF, token validation, or security configuration changes.
5. Ask follow-up questions about tradeoffs and request a small learning exercise. Don't accept “tests pass” as proof that security is correct; understand which threat each test rejects.

You can also select **AuthEdu Security Reviewer** directly for a read-only review. It reports risks and suggestions but does not fix them; ask the implementation agent to address findings, then review the resulting diff yourself.

## Prompting pattern

State **goal + context + acceptance criteria + boundaries + learning request**. For example:

> Implement [issue/feature]. Follow the project plan and existing conventions. Acceptance criteria: [observable outcomes]. Keep the change scoped; do not weaken security controls. Before editing, tell me the plan and assumptions. Run the relevant tests and explain what each important test proves. Finish with a plain-language explanation and one question I can use to check my understanding.

If a request is broad, ask the agent to split it into small independently verifiable tasks rather than implementing the entire roadmap at once. If a stack choice or security tradeoff is unresolved, decide it explicitly with the agent before scaffolding.

## What still needs human judgment

- The owner has approved the initial target stack and the decision record documents current compatibility evidence; the agent should still re-check exact pins and compatibility at scaffold time and report any changed support status.
- Check whether proposed dependencies are maintained and appropriate, and review security-sensitive code and findings.
- Verify acceptance criteria and run the app yourself when feasible. Agents can miss context, tests can be incomplete, and a security review is not an audit.
- Keep secrets out of chat and source control. Never paste passwords, API keys, or tokens into prompts.

## Why there are no hooks or separate test agent yet

Hooks can enforce deterministic local commands, but this repository has no implementation scripts or stable test commands yet. Add them only after the project has those commands and their effects are understood. Testing is already part of feature delivery; a separate test persona would duplicate responsibilities at this stage. Revisit these choices when the codebase grows or a real bottleneck appears.
