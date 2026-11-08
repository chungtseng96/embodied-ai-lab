---
name: factory-packet
description: Factory packet for a PR at merge-ready, or any PR a human will review from evidence: the proof-of-done packet with linked evidence per criterion, impact, self-review and the agent's own weakest point.
user-invocable: true
---

# Packet

The packet is what a human reviews instead of the diff. Every claim links to
the artifact that proves it; a claim without a link is a bounce. Read the
[factory](../factory/SKILL.md) shared rules first. Inputs: the state record
(or, standalone, the PR and its ticket), `N`, `SHA`.

## Steps

1. **Gather at `SHA` only.** The acceptance criteria and **Operator-run**
   list from the record (or the ticket's acceptance list), the Verify
   ledger, the CI result and run link, the **Goldens** result on an `R`
   ticket, every reviewer finding and its outcome, the dismissal lines, the
   needs-human list. A line from an earlier head counts only when babysit
   marked it `patch-id unchanged @SHA`; anything marked `stale` does not.

2. **Write the packet** as a Linear comment whose first line starts with
   `**Proof of done**`, editing it if one exists
   (`factory_linear.py upsert-comment $T --marker "**Proof of done**" --body-file <file>`):
   ```markdown
   **Proof of done** · <ticket> · PR #<n> · head `<full SHA>` · <ISO time>

   **1. Done criteria**
   | Criterion | Status | Evidence |
   |---|---|---|
   | <verbatim criterion> | done (mock) / not done / operator-run | <test command and output line, CI run link, diff range; or "needs an operator: <what to run>"> |

   **2. Impact**
   - Current: <what happens today>
   - New: <what happens after this merges>
   - Could break: <blast radius, dependent paths, the profile's **Impact** risk surface accounted for>
   - Rollout / rollback: <order, config, revert range; what a physical run must confirm first>

   **3. Self-review**
   - Fixed: <finding · commit>
   - Dismissed: <finding · disproof>
   - Open: <finding · why it is a human's call>

   **4. Weakest point**
   <one paragraph, named by this run: the part a reviewer should stress first,
   or what to test next if nothing is weak>
   ```
   Every criterion row carries a link or a command with its output line.
   "Tests pass" with no command is not evidence. A row is `done (mock)`
   only; a factory run never writes a physical status. Impact accounts for
   the profile's **Impact** risk surface, in Could break or in Current.

3. **Mirror into the PR.** The **Factory run** note in the PR body (the
   profile's **PR body**) gets the **Weakest point** sentence and a
   **Packet** link to the comment. The packet is the long form; the PR body
   stays short.

4. **Record.** Add a **Packet** row to the state record's phase table with
   `SHA` and the comment link.

## Done when

A **Proof of done** comment exists at `SHA` with every criterion linked to
evidence or marked operator-run, an impact section, a self-review that
lists fixed, dismissed and open findings, and a weakest point written by
this run; the PR body links it.
