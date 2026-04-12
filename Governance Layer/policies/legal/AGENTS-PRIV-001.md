# Data Privacy Policy

| Field | Detail |
|---|---|
| **Document ID** | AGENTS-PRIV-001 |
| **Version** | 1.1.0 |
| **Status** | DRAFT |
| **Classification** | RESTRICTED |
| **Owner** | Legal and Compliance |
| **Authority** | Gatekeeper |
| **Review Cycle** | Annual |

---

## 1. Purpose and Scope

Governs the handling of proprietary client documentation, emails, and internal project logs. Specifically engineered to manage the lifecycle of data passing through training, fine-tuning, and algorithmic inference pipelines.

---

## 2. AI-Specific Privacy Requirements

### 2.1 Classification and Limit
- **Data Stratification:** "Input Data" (user queries) must be walled entirely off from "Training Data" (weights manipulation) and "Metadata" (system logs). 
- Project documentation cannot be utilized to fine-tune commercial models unless explicitly consented to in writing by the data origin client.

### 2.2 De-identification and Scrubbing
- **Automated NER Integration:** Prior to entering any training loop, data must pass a Named Entity Recognition (NER) layer to aggressively redact Personally Identifiable Information (PII).
- **Contextual Anonymization:** Business identifiers capable of triggering "model memorization" (e.g. project budgets, structural contractor IDs) must be scrubbed entirely.

### 2.3 Zero-Data Retention (ZDR)
- **Third-Party APIs:** Integration with external APIs (OpenAI, Anthropic) mandates absolute default configuring to "Opt-Out" or "Zero-Data Retention" (ZDR) endpoints.
- **Local Fallback:** Highly sensitive inference sets (internal emails/codebacks) must be routed automatically to Local Large Language Models (LLMs) executing securely within the agency sandbox.

### 2.4 Model Inversion Protection
- Defensive audits must be conducted quarterly to measure extraction threats (adversarial prompting attempting to unmask internal weights). 
- **Synthetic Data:** The system will prioritize the generation of Synthetic Datasets to shield real-world private data sets from inference leakage. **Ethical Sourcing** is mandatory if borrowing external structures.
- **Differential Privacy:** Statistical noise should be integrated into internal model tuning runs where possible.

---

## 3. Regulatory Alignment
- **Australian Privacy Principles (APPs):** Total alignment with the *Privacy Act 1988* regarding algorithmic automated decision-making. 
- **Right to Deletion:** Clients retain the absolute right to purge their data from future training architectures or request "un-learning" vectors where technically viable.

---

## 4. Records Management and Retention
Implementation of data arrays for new LLM architectures must be preceded by an approved `AGENTS-PRIV-DPIA-001` (Data Privacy Impact Assessment).

---

## Document Control
| Version | Date | Author | Change Description |
|---|---|---|---|
| 1.1.0 | 2026-04-12 | Antigravity | Massive refactor cementing NER scrubbing, ZDR mandates, and Synthetic Data substitution limits. |
