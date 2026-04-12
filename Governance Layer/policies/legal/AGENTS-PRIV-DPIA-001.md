# Data Privacy Impact Assessment (DPIA) Template

| Field | Detail |
|---|---|
| **Document ID** | AGENTS-PRIV-DPIA-001 |
| **Version** | 1.0.0 |
| **Status** | DRAFT |
| **Classification** | INTERNAL |
| **Owner** | Legal and Compliance |
| **Authority** | Gatekeeper |
| **Review Cycle** | Annual |

---

## 1. Project Overview
* **Project Name:** ______________________________
* **Description:** [Brief summary of the AI’s function]
* **Key Stakeholders:** Project Lead, Data Privacy Officer, External Clients.

---

## 2. Data Flow & Source Mapping

| Data Category | Data Source | Sensitivity Level | Storage Location |
| :--- | :--- | :--- | :--- |
| **Communication** | Project Emails, Slack/Teams | High | Cloud / Local Server |
| **Technical Docs** | Site Plans, Specs, CAD | Medium | Local Server |
| **Financials** | Contract Variations, Invoices | High | Encrypted Database |
| **Personal Info** | Contact Details, Contractor IDs | High | PII-Scrubbed DB |

---

## 3. AI Processing & Risk Assessment

### 3.1 Model Architecture
* **Inference Method:** Third-party API vs Local Processing (Ollama/Llama).
* **Training/Fine-Tuning:** Will data update model weights? How is it sanitized?

### 3.2 Privacy Risks
* **Data Leakage:** Unintended revelation of confidential variables?
* **Model Memorization:** Is there a risk the model will repeat PII when prompted?
* **Third-Party Access:** Do ToS allow external models to train on inputs?

---

## 4. Mitigation & Control Measures

| Risk Identified | Mitigation Strategy | Status |
| :--- | :--- | :--- |
| **Unintended PII Exposure** | Automated NER (Named Entity Recognition) scrubbing layer. | [Planned/Active] |
| **Unauthorized Access** | Role-Based Access Control (RBAC) restrictions. | [Planned/Active] |
| **Data Retention** | "Zero-Data Retention" (ZDR) enabled on third-party endpoints. | [Planned/Active] |
| **Inaccurate Outputs** | "Human-in-the-loop" (HITL) review for high-stakes execution. | [Planned/Active] |

---

## 5. Ongoing Compliance & Monitoring
* **Drift Monitoring:** Frequency of checking AI privacy filter efficacy.
* **Deletion Requests:** Protocol for "Right to be Forgotten" enactments.
* **Audit Trail:** Standard logging mechanism for accessing targeted sensitive context boundaries.

---

## 6. Sign-Off
* **Completed By:** ____________________ **Date:** ___________
* **Approved By:** ____________________ **Date:** ___________

---

## Document Control
| Version | Date | Author | Change Description |
|---|---|---|---|
| 1.0.0 | 2026-04-12 | Antigravity | Foundational DPIA Template mapped. |
