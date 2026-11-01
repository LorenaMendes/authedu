---
name: secure-feature-delivery
description: 'Deliver one AuthEdu feature from an issue or acceptance criteria through implementation, tests, security review, and a learner-friendly explanation. Use for feature work, bug fixes, authentication, authorization, API/UI changes, and backlog tasks.'
argument-hint: 'Issue number, backlog ID, or feature and acceptance criteria'
user-invocable: true
---

# Secure Feature Delivery

Use this repeatable workflow when implementing or refining a single AuthEdu feature. It teaches the reasoning as well as completing the code.

## Procedure

1. **Orient:** Read `.github/copilot-instructions.md`, the relevant product-plan and backlog sections (and GitHub issue #1 for foundation work), then inspect current files, dependencies, and tests. Existing code/config is authoritative for what's implemented; the approved target is FastAPI, PostgreSQL 18, SQLAlchemy/migrations, React/Vite, CPython 3.14.10, Node.js 26.13, `uv`, and `npm`.
2. **Scope:** Translate the request into observable acceptance criteria. Identify prerequisites, trust boundaries, and what's explicitly out of scope. Ask only for decisions that materially affect the design or security; otherwise state reasonable assumptions.
3. **Plan:** Propose a short file-level plan and a smallest useful vertical slice. Avoid unrelated refactors and unnecessary dependencies.
4. **Implement:** Change the code while preserving clear separation between credential validation, trusted identity, authorization policy, and UI presentation. Never rely on frontend hiding as access control.
5. **Test:** Add/update success and rejection tests. Run focused tests first, then relevant lint/type/build/integration checks that the repository supports. Report unavailable services and failures honestly.
6. **Review:** Inspect the diff and docs for scope, secret leakage, and alignment with the plan. For security-sensitive changes, ask the **AuthEdu Security Reviewer** subagent for a read-only review, then resolve or disclose material findings.
7. **Teach:** Explain in the final response: (a) what changed, (b) why the key design is safe/appropriate, (c) how to run or verify it, and (d) one question or small exercise that helps the learner check their understanding.

## AuthEdu guardrails

- Treat `.github/project-plan.md` as the product/security source of truth; do not add exploit labs, insecure modes, or production-readiness claims.
- Before scaffolding the approved stack, verify requested runtimes and tools against official support and ecosystem compatibility information. Pin exact compatible versions (including Node's patch version and PostgreSQL image tag), commit `uv.lock` and `package-lock.json`, and record package-manager versions and evidence. If a requested target is unsupported or incompatible, pause and report the evidence instead of silently changing it.
- Use maintained libraries for cryptographic operations; never invent cryptography.
- Derive principals from validated credentials and trusted server-side state. Enforce authorization on every protected backend operation and deny by default.
- Keep credentials and secrets out of responses, logs, browser persistent storage where prohibited by the plan, fixtures, screenshots, and artifacts.
- Do not commit, push, publish, or perform destructive operations unless the user explicitly requests them.
