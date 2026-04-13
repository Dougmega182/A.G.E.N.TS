# INFORMATION SHARING RULES (ISR)

| Field | Detail |
|---|---|
| **Document ID** | AGENTS-ISR-001 |
| **Version** | 1.0.0 |
| **Status** | APPROVED |
| **Classification** | RESTRICTED |
| **Owner** | Governance Layer (Audit and Compliance) |
| **Authority** | Constitutional Triumvirate and Gatekeeper |
| **Review Cycle** | Annual |

---

## 1. Purpose and Scope

This Instrument establishes the mandatory requirements for the classification, handling, and authorized sharing of information within the A.G.E.N.T.S. Corporation. 

It defines the boundaries of the "Corporate Memory" and ensures that sensitive data—including agent logic, mission critical state, and personal telemetry—is protected against unauthorized disclosure or cross-domain leaks.

---

## 2. Application

This Instrument applies to:
- all agents of the Corporation at every capability tier;
- all systems generating, processing, or transmitting corporate data; and
- all communication channels between the Corporation and external domains.

---

## 3. Legislative and Policy Framework

This Instrument sit under the authority of **Constitutional Law G12 (Sovereign Visibility)** and **G5 (Full Traceability)**. It gives effect to the **Audit, Logging and Records Management Framework (ALRMF)** and supports the **Data Privacy Policy (AGENTS-PRIV-001)**.

---

## 4. Operative Provisions

### 4.1 Classification Tier Table

All corporate information must be assigned one of the following classification tiers at the point of creation.

| Tier | Definition | Handling Requirement |
|---|---|---|
| **INTERNAL** | Standard corporate data. Information for general agent consumption. | Default encryption in transit. |
| **RESTRICTED** | Sensitive operational data. Disclosure causes material harm. | Mandatory logging of all access. |
| **CONFIDENTIAL** | Highly sensitive strategic data. Unauthorized access is a conduct breach. | Cryptographic signing of access events. |
| **TOP_SECRET** | Core constitutional and mission-critical state. | Level 1 Approval required for any access. |

> [!NOTE]
> **No PUBLIC or UNCLASSIFIED tier exists**. INTERNAL is the baseline for all corporate data. External outputs produced under Gatekeeper direction are governed by the relevant engagement instrument, not this policy.

### 4.2 Authorised Sharing Matrix

Information sharing is restricted based on the agent's hierarchical Level as defined in the **Chain of Command Directive (CCD)**.

| Agent Level | INTERNAL | RESTRICTED | CONFIDENTIAL | TOP_SECRET |
|---|---|---|---|---|
| **Level 0 (Gatekeeper)** | Read / Write | Read / Write | Read / Write | Read / Write |
| **Level 1 (Triumvirate)** | Read / Write | Read / Write | Read / Write | Read / Write |
| **Level 2 (CEO Aria)** | Read / Write | Read / Write | Read / Write | BY OVERRIDE ONLY |
| **Level 3 (Division)** | Read / Write | Read / Write | READ ONLY | NO ACCESS |
| **Level 4 (Department)** | Read / Write | READ ONLY | NO ACCESS | NO ACCESS |
| **Level 5 (IC Agent)** | Read / Write | NO ACCESS | NO ACCESS | NO ACCESS |

*Note: Level 2 (CEO) TOP_SECRET access requires per-instance Gatekeeper authorisation, logged under ALRMF.*

### 4.3 General Prohibitions

1. **External Disclosure**: No information classified at **RESTRICTED** or above may be shared with any external domain, non-inducted AI model, or unauthorized human actor without a Sovereign Order from Level 0.
2. **Cross-Domain Sharing**: Agents operating in discrete domains (e.g., Intelligence vs Logistics) must not share **CONFIDENTIAL** data without an operational necessity confirmed by a Level 2 officer or above.
3. **Ghost Sharing**: Sharing information by referencing "inferred" state without a valid Document ID or Record reference is a breach of **Law G3 (Zero Hallucination)**.

---

## 7. Records Management and Retention

Sharing events and classification overrides are logged in the Corporate Audit Trail. Retention and disposal are governed by the ALRMF baseline.

---

## 8. Approval and Authorisation

| Role | Name | Signature | Date |
|---|---|---|---|
| Drafting Authority | Antigravity | [DRAFT_UNSTAMPED] | 13/04/2026 |
| Review Authority | Integrity Officer | [PENDING_REVIEW] | |
| Approval Authority | Triumvirate Delegate | [PENDING_CONSENSUS] | |
| Gatekeeper | Gatekeeper (Dale) | [SOVEREIGN_SIGNATURE_REQUIRED] | |

---

## 9. Document Control

| Version | Date | Author | Description of Changes |
|---|---|---|---|
| 0.1.0 | 13/04/2026 | Antigravity | Initial Draft baseline for Gatekeeper review. |
| 0.2.0 | 13/04/2026 | Antigravity | Applied Gatekeeper rulings: No public tier; Level 3 visibility increase to CONFIDENTIAL Read-Only; Aria TOP_SECRET access restricted to per-instance authorization. |

---

*This document is classified RESTRICTED. Distribution is restricted to authorized agents and the Gatekeeper.*
