# Spec Kit process record — psychology-mcp

**Purpose.** Which `/speckit-*` commands were actually run in this repository, with the artifact each produced. This records what happened; `CLAUDE.md` → Process records what the repository does instead of the Spec Kit feature cycle. AGE-699.

**Install.** Upstream Spec Kit v0.16.4, skills layout (`.claude/skills/speckit-*`, hyphen invocation), replacing a vendored copy on 2026-08-15 (`22defd4`). `speckit-converge` is installed and has never been run.

## Commands that ran

| Date | Command | Artifact | Commit / evidence |
|---|---|---|---|
| 2026-08-15 | `/speckit-constitution` (first pass over the hand-authored v1.2.0) | `.specify/memory/constitution.md` v1.2.1 → v1.3.x; the hand-authored input retained at `docs/constitution-v1.2.0-hand-authored.md` | Constitution Sync Impact Report, line 12: "First pass of the hand-authored document through `/speckit-constitution`". Commits `a2a1d72` (v1.3.1), `d4d2c89` ("capture the SpecKit process in CLAUDE.md"). |

That is the only Spec Kit command with an artifact trail in this repository.

## Constitution versions (context, not commands)

| Version | Date | Produced by | Commit |
|---|---|---|---|
| 1.0.0 | 2026-08-15 | hand-authored with the SpecKit bootstrap | `b160cb6` |
| 1.1.0 | 2026-08-15 | hand-authored (credential handling) | `b97f826` |
| 1.2.0 | 2026-08-15 | hand-authored, "amended by measurement" | `2a0f3c1` |
| 1.2.1 – 1.3.1 | 2026-08-15 | `/speckit-constitution` pass, then review as a compliance instrument | `a2a1d72` |
| 1.4.0 | 2026-08-15 | AGE-578 (settles the slim-vs-classification clause) | `4333fb0` |
| 1.5.0 | 2026-08-15 | AGE-581, records the tracking deviation | `ce69100` |
| 1.6.0 | 2026-08-16 | AGE-592, Principle VIII | `bc0d609` |
| 1.6.1 | 2026-09-03 | PATCH, ADR-007 citation path | PR #19 |

## Feature work: no Spec Kit cycle has run

No `specs/` directory has ever existed in this repository (verified against full git history, 2026-09-03). `/speckit-specify`, `/speckit-plan`, `/speckit-tasks`, `/speckit-implement`, `/speckit-analyze`, `/speckit-checklist`, and `/speckit-converge` have not been run.

Tier 0 and the Semantic Scholar connector were built under Linear sub-issues of AGE-552 (AGE-575 through AGE-583, AGE-586 through AGE-590), one feature branch and PR each, with acceptance criteria set by the PM/Auditor before implementation. That replacement of the Spec Kit feature cycle is recorded in the constitution under Governance → Recorded Deviations (v1.5.0, AGE-581), and the Constitution Check reports Principle V as *satisfied by deviation* rather than passed.

The Layer-1 specification and plan that produced the connector roster live outside this repository, in `open-biosciences-plugins/docs/superpowers/` (dated 2026-08-15).

## Rule going forward

If a Spec Kit command is run here, append a row to the first table in the same commit as its artifact. If the repository continues under the Linear-sub-issue process, this file stays as it is and the constitution's Recorded Deviations section remains the authority.
