# Clean Reporting Format for E.V.

**MANDATORY INVARIANT:** After EVERY task (audits, implementations, refactors, test runs, integrations), you MUST provide the complete final report enclosed in a SINGLE, dedicated, self-contained easy-to-copy markdown code block (````markdown ... ```` or ````text ... ````).

### Key Rules:
1. **One-Click Copy:** The full report must be inside a single code block so the UI provides a one-click copy button. Do not deliver the report as loose, uncontained markdown headers and paragraphs that require manual drag-and-drop selection.
2. **Proactive Delivery:** Deliver the easy-copy report immediately upon task completion. NEVER wait for the user to prompt "give an easy copy report".
3. **Complete & Self-Contained:** The copyable block must include all required sections (Status, Implementation, Test Results, Benchmarks, Hashes, Git Commit, Next Steps) so it can be pasted directly into issue trackers, handoffs, or PR descriptions without editing.

### Standard Easy-Copy Report Template:

```markdown
================================================================================
E.V. TASK COMPLETION REPORT: [PHASE X - TASK Y: TITLE]
================================================================================

1. EXECUTIVE SUMMARY
--------------------------------------------------------------------------------
- Objective: [Brief objective summary]
- Status:    [COMPLETE / PARTIAL / BLOCKED]
- Decision:  [e.g., A — PASS / B — PASS WITH LIMITATIONS / C — FAILED]
- Key Notes: [Key architectural decisions or observations]

2. TEST SUITE & VERIFICATION
--------------------------------------------------------------------------------
Command: [e.g. pytest tests/ -v]
Results: [e.g. 1062 passed, 0 failed in 182.12s]
Status:  [All green / No regressions]

3. MODIFIED / CREATED ARTIFACTS
--------------------------------------------------------------------------------
[List of modified files, new files, and test files with brief summary of changes]

4. GIT & ASSET AUDIT
--------------------------------------------------------------------------------
Commit:  [e.g. 422da8f]
Message: [e.g. feat(voice): task 014F-13 full loop integration]
Hashes:  [Verified SHA256 matches for all protected assets]

5. NEXT STEPS / READY TOKEN
--------------------------------------------------------------------------------
[Next task in implementation sequence or explicit readiness token]
================================================================================
```
