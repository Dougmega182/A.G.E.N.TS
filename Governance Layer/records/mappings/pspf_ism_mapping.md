# PSPF and ISM Mapping Matrix

Status: Draft
Owner: Security Command + Legal and Compliance
Approval: Audit Agent + Gatekeeper

Purpose
Map A.G.E.N.T.S. governance documents to PSPF requirements and ISM controls for audit readiness.

Authoritative Sources
- PSPF Release 2025 - List of Requirements (PDF): Governance Layer/records/mappings/source/pspf-release-2025-list-requirements.pdf
- ISM OSCAL Catalog (March 2026): Governance Layer/records/mappings/source/ISM_catalog_2026-03-24.json

Generated Mapping Artifacts
- PSPF parsed requirements: Governance Layer/records/mappings/pspf_requirements_parsed.csv
- PSPF requirements mapping: Governance Layer/records/mappings/pspf_requirements_mapping.csv
- ISM parsed controls: Governance Layer/records/mappings/ism_controls_parsed.csv
- ISM controls mapping: Governance Layer/records/mappings/ism_controls_mapping.csv

Summary
- PSPF requirements parsed: 172
- ISM controls parsed: 1130

PSPF Mapping
| PSPF Domain | Control Area | A.G.E.N.T.S. Document | Evidence Location |
|---|---|---|---|
| Governance | Security governance | Governance Layer/corporate_governance.json | Governance Layer/registers/document_register.md |
| Personnel | Personnel security | Onboarding/onboarding_pack.md | Onboarding records |
| Information | Information security | Governance Layer/security_policy.md | Governance Layer/records |

ISM Mapping
| ISM Control Area | A.G.E.N.T.S. Document | Evidence Location |
|---|---|---|
| Access Control | Governance Layer/security_policy.md | Governance Layer/records |
| Logging and Monitoring | config/logging_requirements.json | Governance Layer/memory/checkpoints.jsonl |
| Incident Response | config/protocols.json | Incident reports |
| Data Protection | Governance Layer/security_policy.md | Governance Layer/records |

Gaps and Evidence
- Coverage is marked Partial by default until evidence is attached per requirement/control.
- Physical security requirements are marked Gap until a physical security policy is drafted.
- Evidence artifacts must be linked in the mapping CSVs prior to approvals.

