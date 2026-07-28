# YuanQi Agent engineering context

## Architecture and trust boundaries

- Java uses JDK 17 and Spring Boot 3.x. It is the only business-data trust root and owns CRUD for medical entities (patients, prescriptions, medical records), transactions, authentication, authorization, and row-level data filtering.
- Python uses FastAPI, LangGraph, and Pydantic v2. It performs nondeterministic reasoning, medical knowledge graph retrieval (Neo4j), and orchestration. It connects to Neo4j for disease/symptom/drug queries and to Java for patient data CRUD.
- The frontend uses React 18, TypeScript, and Ant Design X. It renders server-described UI for medical knowledge exploration and patient management.
- Browser requests enter through Java with the user's JWT. Python-to-Java tool callbacks must forward that JWT. Prefer a Java-authenticated SSE proxy rather than exposing Python as a trusted public entry point.

## Domain model

### Medical knowledge graph (Neo4j)
- Node types: 疾病 (Disease), 症状 (Symptom), 药物 (Drug), 科室 (Department), 检查 (Exam); catalog-only browse types 食物 (Food), 治疗方式 (Therapy)
- Relationships: HAS_SYMPTOM, TREATED_BY, BELONGS_TO, COMPLICATION, REQUIRES_EXAM; catalog-only HAS_THERAPY, RECOMMENDED_EAT, AVOID_EAT, RECOMMENDED_RECIPE
- Import the full disease catalog via `agent/scripts/import_disease_kb.py --file data/medical.json`, then `standardize_medical_catalog.py` and `publish_trusted_medical_subset.py` (or run `scripts/run_medical_pipeline.ps1` end to end)

### Business entities (Java/MySQL)
- Patient: patient_no, name, gender, birth_date, phone, blood_type, allergy_history, medical_history
- MedicalRecord: record_no, patient_id, visit_date, diagnosis, treatment_plan
- Prescription: prescription_no, patient_id, drugs_json, diagnosis, status

## Mandatory safety rules

- Every Python tool has a strongly typed Pydantic schema.
- Every write tool must call LangGraph `interrupt()` before execution, persist the proposed tool and arguments in a Checkpointer, and run only after an explicit resume decision.
- Generated Python code must pass an AST allowlist/denylist check and execute in Pyodide/WASM or a no-network, resource-limited container.
- Never expose private chain-of-thought. Stream short user-facing progress summaries under `reasoning`.
- Java must not build SQL strings manually or call an LLM. Long-running Agent calls use a dedicated executor or reactive I/O, never request-processing threads.
- Row-level authorization is derived from verified JWT claims and is applied again on every read and write in Java. Client-supplied tenant/user scope is never trusted.
- Python data analysis consumes only data exported by an authorized Java endpoint. A schema-only response can guide code generation but cannot supply calculation data.

## Protocol

SSE events use one of these logical payloads:

- `reasoning`: a public progress summary.
- `text`: an incremental Markdown fragment.
- `uiData`: structured JSON for a supported component such as `chart` or `approval_card`.

SSE clients must buffer partial network chunks and parse complete event frames. Unknown UI component types must fail closed to a text fallback.

## Delivery order

1. Java business foundation, OpenAPI, JWT, and row-level authorization.
2. LangGraph state machine, AST policy, sandbox, interrupt/resume.
3. Neo4j plus vector retrieval and RRF fusion.
4. Ant Design X conversation UI, buffered SSE, and generative UI registry.
5. End-to-end integration and adversarial security tests.
