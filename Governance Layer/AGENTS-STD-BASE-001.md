# Australian Standards Baseline

| Field | Detail |
|---|---|
| **Document ID** | AGENTS-STD-BASE-001 |
| **Version** | 1.0.0 |
| **Status** | DRAFT |
| **Classification** | INTERNAL |
| **Owner** | Governance Layer (AI Oversight Board) |
| **Authority** | Constitutional Triumvirate and Gatekeeper |
| **Review Cycle** | Quarterly or on regulatory change |

---

## 1. Purpose
This baseline defines the minimum Australian government standards and legal frameworks that A.G.E.N.T.S. must meet before any agent activation or fine-tuning. If there is any conflict between internal policy and an applicable Australian standard, the stricter requirement applies until Gatekeeper decision.

Applicable Australian Standards and Frameworks (Minimum Set)
1. Protective Security Policy Framework (PSPF) - Australian Government security policy baseline
2. Australian Government Information Security Manual (ISM) - ASD controls and guidance
3. ASD Essential Eight - baseline cyber security maturity expectations
4. Privacy Act 1988 (Cth) and Australian Privacy Principles (APPs)
5. Archives Act 1983 (Cth) and National Archives of Australia digital records guidance
6. Public Governance, Performance and Accountability Act 2013 (PGPA Act)
7. Work Health and Safety Act 2011 (Cth)
8. Australian AI Ethics Principles (Commonwealth policy baseline)

Scope Mapping to Internal Documents
- Governance and accountability: config/corporate_governance.json, config/AGENTS-DELEG-001.md
- Security controls: config/security_layers.json, config/information_sharing.json
- Logging and audit: config/logging_requirements.json
- Incident response: config/protocols.json
- Rules of engagement: config/rules_of_engagement.json
- Onboarding, oath, contract: config/onboarding_sop.json, config/oath_and_contract.json

Compliance Gating
- No agent activation until all baseline documents are in Approved status and signed.
- No fine-tuning or model modification until data governance, privacy, and security controls are approved.
- Any exception requires Gatekeeper approval and audit logging.

Evidence and Audit
- All compliance evidence is stored in Governance Layer records.
- Audit Agent verifies evidence quarterly against PSPF and ISM control coverage.

