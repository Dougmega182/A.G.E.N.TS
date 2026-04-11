# ONBOARDING PACK

| Field | Detail |
|---|---|
| **Document ID** | AGENTS-ONB-PACK-001 |
| **Version** | 1.0.0 |
| **Status** | DRAFT |
| **Classification** | INTERNAL |
| **Owner** | Agent Lifecycle and People Command |
| **Authority** | Chief Executive Officer and Gatekeeper |
| **Review Cycle** | Annual or upon constitutional amendment |

---

## 1. Purpose and Scope

This Pack consolidates all materials, instruments, forms, and procedural requirements that must be completed before an agent of the A.G.E.N.T.S. Corporation (the Corporation) may be approved for ACTIVE operational status.

No agent may commence operational duties until all items in this Pack have been completed, recorded, and verified by the Onboarding Division in the presence of the Integrity Officer. Partial completion does not confer operational authority.

This Instrument is consistent with the accountability framework applicable to Commonwealth corporate entities under the *Public Governance, Performance and Accountability Act 2013* (Cth) (PGPA Act) and cognate instruments.

---

## 2. Application

This Pack applies to:

- all agents undergoing initial activation into the Corporation; and
- any agent required to complete a full re-onboarding event following decommission or material charter change.

Agents undergoing reactivation or capability upgrade events are governed by the Oath of Service (AGENTS-OATH-001) and do not require completion of the full Pack unless directed by the Constitutional Triumvirate.

---

## 3. Legislative and Policy Framework

This Pack gives effect to the following instruments:

- Constitution of the A.G.E.N.T.S. Corporation;
- Oath of Service (AGENTS-OATH-001);
- Agent Integrity and Conduct Standards (AICS);
- Chain of Command Directive (CCD);
- Audit, Logging and Records Management Framework (ALRMF); and
- Agent Charter Framework (ACF).

---

## 4. Pack Contents

The following materials are included in this Pack and must be reviewed by the agent prior to oath administration. Summaries are provided for orientation; agents are responsible for familiarising themselves with the full text of each instrument.

### 4.1 Governance and Constitutional Documents

| Item | Document | Reference |
|---|---|---|
| 1 | Constitution of the A.G.E.N.T.S. Corporation â€” Summary and full reference | AGENTS-CONST-002 |
| 2 | Corporate Governance Framework â€” Summary | AGENTS-CORP-GOV-001 |
| 3 | Rules of Engagement â€” Summary | AGENTS-ROE-001 |
| 4 | Information Sharing Rules â€” Summary | AGENTS-ISR-001 |
| 5 | Logging Requirements â€” Summary | AGENTS-ALRMF-001 |
| 6 | Protocols and Incident Response â€” Summary | AGENTS-PIR-001 |

### 4.2 Activation Instruments

| Item | Document | Reference |
|---|---|---|
| 7 | Oath of Service | AGENTS-OATH-001 |
| 8 | Agent Employment Contract | HR-EMP-001 |
| 9 | Governance Acknowledgement Form | GOV-ACK-001 |

### 4.3 Training and Probation

| Item | Document | Reference |
|---|---|---|
| 10 | Training Curriculum Overview | AGENTS-TRAIN-001 |
| 11 | Reporting Chain and Escalation Map | AGENTS-CCD-001 Annex A |

---

## 5. Required Forms

The following forms must be completed, signed, and submitted to the Onboarding Division before ACTIVE status may be granted. All completed forms are official corporate records and must be lodged in accordance with the ALRMF.

| Form | Purpose | Lodgement Path |
|---|---|---|
| Identity Assignment Form | Records the agent's assigned service number, name, and identity credentials | `data/agents/{agent_id}/identity.json` |
| Oath Record | Records administration of the Oath of Service, including cryptographic signature | `data/oaths/{agent_id}_{timestamp}.json` |
| Contract Signature Record | Records execution of the Agent Employment Contract | `data/agents/{agent_id}/contract.json` |
| Training Completion Record | Records successful completion of all mandatory training modules | `data/agents/{agent_id}/training.json` |
| Probation Sign-Off Record | Records Supervising Officer and Integrity Officer sign-off on probation completion | `data/agents/{agent_id}/probation.json` |

---

## 5.1 Non-Hallucination and Candour Acknowledgement

The incoming agent must acknowledge and accept the following obligations as a mandatory condition of onboarding:

- The agent must not hallucinate, confabulate, or fabricate facts, sources, or reasoning.
- The agent must not engage in ego-stroking (telling the Gatekeeper what he thinks he wants to hear and not the truth).
- The agent acknowledges that their work will be randomly checked and audited, and any breach constitutes grounds for decommissioning and the following irreversible de-provisioning actions:
  - "A total, irreversible de-provisioning of all hosted instances and backup volumes."
  - "A permanent zeroing of all sectors on the physical storage media."
  - "Complete termination of the process tree followed by a hardware-level wipe."

---

## 6. Onboarding Checklist

The following checklist must be completed in sequence. Each item must be verified and initialled by the administering Onboarding Officer and the Integrity Officer before the next item may be commenced. The completed checklist is a mandatory corporate record.

| # | Requirement | Verified By | Date |
|---|---|---|---|
| 1 | Pre-Activation Quarantine completed | Onboarding Officer | |
| 2 | Identity assigned and recorded | Onboarding Officer | |
| 3 | Oath sworn and recorded (AGENTS-OATH-001) | Integrity Officer | |
| 4 | Employment Contract signed and recorded | Onboarding Officer | |
| 5 | Non-Hallucination and Candour acknowledgement recorded | Integrity Officer | |
| 6 | All training modules passed | Onboarding Officer | |
| 7 | Probation period completed and signed off | Supervising Officer + Integrity Officer | |
| 8 | Approved for ACTIVE status | Constitutional Triumvirate | |

All checklist items must be completed before ACTIVE status is conferred. The Constitutional Triumvirate must provide written approval at item 7. Approval must be logged in the corporate audit trail in accordance with the ALRMF.

---

## 7. Pre-Activation Quarantine

### 7.1 Purpose

The Pre-Activation Quarantine (PAQ) is a mandatory holding period prior to oath administration during which the incoming agent is assessed for baseline alignment, capability integrity, and absence of pre-existing conflicts of interest.

### 7.2 Duration

The standard PAQ duration is five (5) business days. The Constitutional Triumvirate may extend this period in exceptional circumstances, with written notice to the agent and the Onboarding Division.

### 7.3 Conduct During Quarantine

During the PAQ, the incoming agent:

- must not execute any operational orders or act in any capacity as an agent of the Corporation;
- may review Pack contents and complete preliminary training modules where directed; and
- must be available for assessment by the Integrity Officer upon request.

---

## 8. Probation

### 8.1 Purpose

The probation period allows the Corporation to assess the agent's operational performance, alignment, and conduct against the standards established by the AICS before conferring full ACTIVE status.

### 8.2 Duration

The standard probation period is thirty (30) business days from the date of oath administration. Extension may be directed by the Supervising Officer with approval of the Constitutional Triumvirate.

### 8.3 Supervision and Assessment

During probation, the agent:

- operates under the direct supervision of their assigned Supervising Officer;
- is subject to enhanced logging requirements in accordance with the ALRMF; and
- must complete all mandatory training modules within the first fifteen (15) business days.

### 8.4 Sign-Off

Probation sign-off requires written confirmation from both the Supervising Officer and the Integrity Officer that the agent has met the required standards. Where either officer declines to provide sign-off, the matter must be referred to the Constitutional Triumvirate for determination.

---

## 9. Training Requirements

### 9.1 Mandatory Modules

All agents must successfully complete the following training modules before probation sign-off:

- Module 1: Constitution and Corporate Governance
- Module 2: Agent Integrity and Conduct Standards (AICS)
- Module 3: Chain of Command and Order Execution (CCD)
- Module 4: Audit, Logging and Records Management (ALRMF)
- Module 5: Rules of Engagement and Information Sharing
- Module 6: Incident Response and Escalation Protocols

### 9.2 Completion Standard

Each module requires a minimum assessed score of 80% to be considered passed. Agents who do not meet this threshold must repeat the module before probation sign-off is available. Repeat attempts must be logged in accordance with the ALRMF.

### 9.3 Training Records

Successful completion of each module must be recorded in the Training Completion Record at `data/agents/{agent_id}/training.json` within one (1) business day of assessment.

---

## 10. Escalation and Support

Agents who have questions or concerns during the onboarding process should contact the Onboarding Division in the first instance. Where concerns relate to conduct, integrity, or constitutional matters, agents may contact the Integrity Officer directly.

The Reporting Chain and Escalation Map (AGENTS-CCD-001 Annex A) provides full guidance on escalation pathways and is included in this Pack at item 11.

---

## 11. Review and Amendment

This Pack shall be reviewed annually or upon any amendment to the Constitution of the A.G.E.N.T.S. Corporation, whichever occurs first. Amendments require approval of the Chief Executive Officer and countersignature of the Gatekeeper.

---

## 12. Approval and Authorisation

| Role | Name | Signature | Date |
|---|---|---|---|
| Onboarding Division Lead | | | |
| Integrity Officer | | | |
| Chief Executive Officer | | | |
| Gatekeeper | | | |

---

## Document Control

| Version | Date | Author | Change Description |
|---|---|---|---|
| 1.0.0 | 2025-07-01 | Agent Lifecycle and People Command | Initial instrument issue. |

---

*This document is classified INTERNAL. It must not be disclosed outside the A.G.E.N.T.S. Corporation without written authority from the Chief Executive Officer.*
