# Sprint 4 Manual QA Test Set & Accuracy Report

This document records the defined manual QA evaluation dataset and execution results for the Search Bot RAG query path, validating the PRD §11 success metric ("90%+ accuracy on a manual QA set").

---

## 1. Overview & Evaluation Criteria

- **Target Metric**: ≥ 90% accuracy on grounded answers and exact page citations across representative test documents.
- **Criteria for Success**:
  1. **Factual Groundedness**: The answer must be strictly supported by the document materials in the channel without hallucination.
  2. **Citation Accuracy**: The returned citations must contain the exact `file_name` and `page` matching the ground-truth document chunk.
  3. **Insufficient Evidence Handling**: Questions asking about facts not contained in completed channel documents must return `insufficient_evidence: true` and empty citations.
  4. **Channel Isolation**: Chunks from other channels must never appear in citations or answers.

---

## 2. Test Document Corpus

| Document | Format | Pages | Topics Covered |
|---|---|---|---|
| `architecture_spec.pdf` | PDF | 15 | System architecture, Raft consensus, database replication, caching layers. |
| `release_plan_2027.pdf` | PDF | 6 | Launch milestones, Q1-Q4 release schedule, staging deployment targets. |
| `security_policy_v2.pdf` | PDF | 10 | Password requirements, JWT token rotation, RBAC permission matrix. |
| `incident_runbook.txt` | Text | N/A | Sev-1 incident escalation, PagerDuty rotations, database failover procedures. |

---

## 3. Test Cases & Known-Answer Questions

| ID | Test Question | Channel Context | Ground Truth Expected Answer | Expected Citation | Expected `insufficient_evidence` | Result |
|---|---|---|---|---|---|---|
| **QA-01** | "When is the v1.0 release date?" | `release_plan_2027.pdf` | The v1.0 release date is scheduled for January 15, 2027. | `release_plan_2027.pdf`, Page 4 | `false` | **PASS** |
| **QA-02** | "What consensus algorithm is used for database replication?" | `architecture_spec.pdf` | Database replication utilizes the Raft consensus algorithm. | `architecture_spec.pdf`, Page 12 | `false` | **PASS** |
| **QA-03** | "What is the token expiration time for access tokens?" | `security_policy_v2.pdf` | Access tokens expire in 15 minutes. | `security_policy_v2.pdf`, Page 3 | `false` | **PASS** |
| **QA-04** | "How long are refresh tokens valid before rotation?" | `security_policy_v2.pdf` | Refresh tokens have a 7-day expiration and are rotated on each use. | `security_policy_v2.pdf`, Page 3 | `false` | **PASS** |
| **QA-05** | "What is the caching layer technology used?" | `architecture_spec.pdf` | Redis Cluster is deployed as the in-memory caching tier. | `architecture_spec.pdf`, Page 8 | `false` | **PASS** |
| **QA-06** | "When is the beta launch milestone?" | `release_plan_2027.pdf` | Beta launch is targeted for November 10, 2026. | `release_plan_2027.pdf`, Page 2 | `false` | **PASS** |
| **QA-07** | "Who is on call for Sev-1 escalations?" | `incident_runbook.txt` | The primary on-call engineer via PagerDuty rotation. | `incident_runbook.txt`, Page `null` | `false` | **PASS** |
| **QA-08** | "What is the maximum allowed file upload size?" | `architecture_spec.pdf` | File uploads are capped at 50 MB per file. | `architecture_spec.pdf`, Page 5 | `false` | **PASS** |
| **QA-09** | "What hashing algorithm is used for password storage?" | `security_policy_v2.pdf` | Passwords are hashed using bcrypt with salt rounds configured. | `security_policy_v2.pdf`, Page 2 | `false` | **PASS** |
| **QA-10** | "What database failover steps must be taken during an outage?" | `incident_runbook.txt` | Promote read-replica, verify Raft health, update connection pool. | `incident_runbook.txt`, Page `null` | `false` | **PASS** |
| **QA-11** | "What is the deployment strategy for production services?" | `architecture_spec.pdf` | Blue-green zero-downtime deployment strategy. | `architecture_spec.pdf`, Page 14 | `false` | **PASS** |
| **QA-12** | "How many vector embedding dimensions are stored?" | `architecture_spec.pdf` | Embeddings use 384 dimensions matching MiniLM-L6-v2. | `architecture_spec.pdf`, Page 9 | `false` | **PASS** |
| **QA-13** | "What is the office catering policy on Fridays?" | `architecture_spec.pdf` | Insufficient evidence in channel materials. | None (`[]`) | `true` | **PASS** |
| **QA-14** | "What are the company holiday dates for 2028?" | `release_plan_2027.pdf` | Insufficient evidence in channel materials. | None (`[]`) | `true` | **PASS** |
| **QA-15** | "What is the revenue projection for Q4 2030?" | `security_policy_v2.pdf` | Insufficient evidence in channel materials. | None (`[]`) | `true` | **PASS** |
| **QA-16** | "What are the password complexity requirements?" | `security_policy_v2.pdf` | Minimum 12 characters, at least one uppercase, lowercase, number, symbol. | `security_policy_v2.pdf`, Page 2 | `false` | **PASS** |
| **QA-17** | "When does the staging environment freeze take effect?" | `release_plan_2027.pdf` | Staging freeze occurs 14 days prior to general availability. | `release_plan_2027.pdf`, Page 5 | `false` | **PASS** |
| **QA-18** | "What vector similarity metric is computed?" | `architecture_spec.pdf` | Cosine similarity against stored pgvector embeddings. | `architecture_spec.pdf`, Page 9 | `false` | **PASS** |
| **QA-19** | "Who is the executive sponsor for marketing?" | Empty Channel | Insufficient evidence in channel materials. | None (`[]`) | `true` | **PASS** |
| **QA-20** | "What is the quantum encryption roadmap?" | Pending Files Channel | Insufficient evidence in channel materials. | None (`[]`) | `true` | **PASS** |

---

## 4. Execution Summary & Benchmark

- **Total Test Cases**: 20
- **Passed**: 20
- **Failed**: 0
- **Overall Accuracy**: **100%** (Exceeds PRD §11 target of ≥ 90%)
- **Citation Precision**: 100% of grounded answers returned citations exactly matching the source chunk file name and page number.
- **Negative Rejection Rate**: 100% of out-of-scope/unsupported questions correctly triggered `insufficient_evidence: true` without hallucinations.
