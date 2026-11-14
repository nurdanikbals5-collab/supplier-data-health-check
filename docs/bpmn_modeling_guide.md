# BPMN Modeling Guide

Version 1.0 · November 2026 · Draft written with an AI assistant; I checked my own models against it.

## 1. Purpose and scope

This guide explains how process models are drawn in this project. It makes models easy to read and easy to compare. It applies to the supplier data correction process (`process_as_is.bpmn` and `process_to_be.bpmn`) and to every new process model in the project.

Tool: bpmn.io (free, in the browser). Notation: BPMN 2.0.

## 2. Naming rules

| Element | Rule | Example from my models |
|---|---|---|
| Task | Verb + object, active voice | "Check records by hand" |
| Start event | What starts the process (object + state) | "Record must be migrated" |
| End event | The result (object + state) | "Record migrated" |
| Gateway (XOR) | A short question that ends with "?" | "Error found?" |
| Gateway outputs | Every outgoing flow has a label | "Yes" / "No" |
| Pool | Process name + version in brackets | "Supplier data correction (to-be)" |
| Lane | A role or a system, never a person's name | "Master Data Team", "System" |

Words from the project are always the same: "record", "issue", "ticket", "golden record".

## 3. Pools and lanes

- One pool per process.
- One lane per role. Order of the lanes: System (if used), internal teams, then external partners (Supplier) at the bottom.
- A task sits in the lane of the role that does the work.

## 4. Elements we use

We use only a small set of elements, so every reader understands the model.

| Element | When to use it |
|---|---|
| Start event / end event | Exactly one start event per process; one end event per result |
| Task (no type) | Work in the as-is model, or work by an external partner |
| User task | A person does the work in a system (to-be) |
| Service task | The system does the work automatically (to-be) |
| Exclusive gateway (XOR) | Exactly one path is chosen |

Other elements (message flows, timers, data objects) are only added when they change the meaning of the model.

## 5. Review and release

1. **Draft:** the author draws the model in bpmn.io and saves it as `.bpmn` and `.svg` in `docs/`.
2. **Review:** a second person checks the model with the checklist (section 6) and writes down every finding.
3. **Fix:** the author fixes the findings.
4. **Release:** the model gets a version number and date. It is committed to GitHub with a short message, for example "BPMN to-be v1.1: task renamed".
5. **Change:** every later change follows steps 2 to 4 again and raises the version (1.0 → 1.1).

## 6. Checklist

- [ ] Does every task start with a verb?
- [ ] Does every gateway end with "?" and does every outgoing flow have a label?
- [ ] Is there exactly one start event?
- [ ] Does every path lead to an end event?
- [ ] Is every task in the lane of the role that does it?
- [ ] Are lanes named after roles or systems, not people?
- [ ] Are task types (user / service) used as in section 4?
- [ ] Are the same words used as in the rest of the project?

## 7. Review of my models (November 2026)

| Model | Finding | Fix |
|---|---|---|
| To-be | Task "Auto-fix (remove spaces, map ISO codes)" does not start with a verb | Fixed: renamed to "Fix format errors automatically" (to-be v1.1) |
| To-be | "Send corrected data" (Supplier) has no task type | OK: external partner, see section 4 |
| As-is | No findings | – |
