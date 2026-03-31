# Change Loop — Workflow Diagram

```mermaid
flowchart TD
    A([Request\nnatural language]) --> B

    B[LLM: find affected facts\nsemantic search over corpus]
    B --> C

    C[LLM: propose bundle\nfact edits · topic tags · template changes]
    C --> D

    D{Coherence gate}
    D -- inconsistency detected --> E[LLM: extend bundle\nwith resolution]
    E --> D
    D -- coherent --> F

    F[Human reviews bundle]
    F -- iterate --> C
    F -- confirm --> G

    G[Approval routing\ndriven by approval scope of facts in bundle]
    G --> H

    H{Approvers review}
    H -- rejected with notes --> F
    H -- approved --> I

    I[Scheduled for publication date]
    I --> J

    J([Publication date reached])
    J --> K

    subgraph pub [Publication — runs per channel]
        K[LLM: channel transform\ntone · style · narrative fit]
        K --> L[Human override window]
        L --> M[Deterministic render\nmarkdown → HTML / PDF\nor chatbot KB pre-processing]
        M --> N[Deliver to channel]
    end

    N --> O{Engagement configured\nfor this change?}
    O -- no --> Z([Done])
    O -- yes --> P

    subgraph eng [Engagement]
        P[Notify audience\nper audience scope]
        P --> Q[Collect responses\nack or feedback]
        Q --> R[Remind non-respondents]
        R --> S[Surface completion\nto administrator]
    end

    S --> Z
```

## Notes

**Coherence gate loop**: the gate does not block — it feeds back into the proposal. The human always sees a coherent bundle. They never resolve inconsistencies manually.

**Iteration vs. rejection**: human iteration (during review) re-enters at the proposal step, keeping the LLM in the loop. Approver rejection re-enters at the human review step, keeping the approver's notes visible.

**Publication is per-channel**: the same approved bundle triggers a separate publication sub-flow for each channel in the facts' channel scope. Each channel has its own LLM transform config and its own human override window.

**Engagement is optional per change**: configured at change time, not as a fixed fact attribute. The same fact might require acknowledgment when a legal clause changes but not when a typo is fixed.
