I’ll produce an end-to-end, implementation-ready engineering spec: architecture + consistent job/state taxonomy, detailed module requirements, data model + APIs, the three pipeline specs with human-in-the-loop checkpoints and artifacts, printability/mesh rules, MCP tool contracts, orchestration patterns, tech stack, testing, security, and phased milestones (MVP → v2). I’ll start by laying down a clear plan so the rest of the spec stays internally consistent.



# Human-in-the-loop 3D Model → STL Generator (Web App) — Engineering Specification

## 0) Scope, Principles, and Glossary

- **Primary Goal**: A web app that produces **3D-printable STL** outputs via three pipelines:
  - **Pipeline A**: Multi-photo scanning (**photogrammetry / NeRF-style reconstruction**) for real objects.
  - **Pipeline B**: Single-image relief (**depth-map → bas-relief / lithophane / coin**) for shallow printable models.
  - **Pipeline C**: Generative minis (**text prompt + optional reference images**) for **original “grimdark sci-fi tabletop mini”** style models.

- **Critical Product Constraint**: The app must not market or imply creation of branded Warhammer 40k miniatures. It must support **original creations** in a **grimdark sci-fi** aesthetic.

- **Human-in-the-loop**: The system must pause at checkpoints, explain issues, and guide the user to:
  - **Improve photo sets** (scan workflow).
  - **Iterate prompts** (generative workflow).
  - **Fix printability issues** (all workflows).

- **Safety/IP Layer**: Must include:
  - **Prompt filtering** for trademarked faction names/logos and close variants.
  - **Image detection** for obvious insignia/logos.
  - **User attestation** for scan workflows (rights to scan + no prohibited IP).

### Glossary
- **Job**: A single execution instance of a pipeline (scan/relief/generative).
- **Project**: A user container grouping jobs and artifacts around a single “model idea.”
- **Artifact**: Any file output or intermediate (photos, masks, point clouds, mesh stages, reports, STL).
- **Validation**: A computed check result (quality, safety, printability) with findings and recommendations.
- **Printer Profile**: Parameters controlling printability thresholds (FDM vs resin, nozzle/pixel size, etc.).
- **MCP**: Model Context Protocol interface used by orchestration to call processing tools.

---

# 1) System Overview + Architecture (Text Diagram, Services, Data Flow, Job States)

## 1.1 High-level Architecture (Services)

- **Frontend Web App**
  - Authenticated UX for project creation, upload, wizards, preview, and “fix issues” flows.
  - 3D viewer and validation explanation panel.
  - Real-time job progress via SSE/WebSocket.

- **API Service (Control Plane)**
  - REST API for projects/jobs/artifacts/validations/printer profiles.
  - Issues pre-signed upload URLs for object storage.
  - Enforces auth, RBAC, rate limits, input schemas.

- **Orchestrator Service**
  - Owns job state machine.
  - Creates job steps, dispatches work to workers via queues/workflow engine.
  - Calls **MCP tools** exposed by processing services.
  - Manages retries, idempotency, cancellation, and progress events.

- **Processing Workers**
  - **CPU Worker Pool**: mesh repair, analysis, validations, conversions, slicing integrations.
  - **GPU Worker Pool**: NeRF, photogrammetry acceleration (if used), depth estimation, generative model inference.
  - Workers expose MCP tool servers or are wrapped by an MCP “adapter.”

- **Safety & Moderation Service**
  - Prompt/IP rules engine (string + fuzzy matching + classifier).
  - Image/logo/insignia detection (heuristic + ML).
  - Attestation capture + enforcement.
  - Optional human moderation queue for borderline cases.

- **Storage**
  - **Object Storage**: all uploaded media + generated artifacts (versioned).
  - **Database**: metadata, state, audit logs, validation records, artifact lineage.
  - **Cache / PubSub**: low-latency progress events, rate limiting counters.

- **Observability Stack**
  - Central logs, metrics, traces, job timelines, GPU utilization.

## 1.2 Text Architecture Diagram (Data Flow)

```text
[Browser UI]
  |  (Auth + REST + SSE/WS)
  v
[API Service] ------------------------------+
  |                                         |
  | (create job, get upload URLs, configs)   | (state + metadata)
  v                                         v
[Object Storage] <---- artifacts ----> [Postgres DB]
  ^                                         ^
  |                                         |
  | (artifact URIs)                         | (job/step state, validations)
  v                                         |
[Orchestrator / Workflow Engine] -----------+
  |
  | (MCP calls with input URIs + configs)
  v
+---------------------+     +---------------------+
| CPU Processing Pool |     | GPU Processing Pool |
| (MCP tool servers)  |     | (MCP tool servers)  |
+---------------------+     +---------------------+
  |
  | (outputs -> object storage + reports -> DB)
  v
[Object Storage] + [DB] -> [API] -> [UI Viewer + Explain Panel]
```

## 1.3 Canonical Job State Machine (Used Everywhere)

### Job `state` (single taxonomy for all pipelines)
- **`DRAFT`**: Configuring inputs/settings; uploads may be in progress; no processing.
- **`SUBMITTED`**: User requested execution; inputs locked (except allowed additions).
- **`VALIDATING`**: Automated checks running (quality + safety + schema).
- **`ACTION_REQUIRED`**: Waiting for user changes/confirmations (retake photos, revise prompt, accept risk).
- **`QUEUED`**: Ready to run; waiting for compute capacity.
- **`RUNNING`**: Processing steps executing.
- **`REVIEW_REQUIRED`**: Results ready for user acceptance/iteration (preview mesh, approve supports).
- **`SUCCEEDED`**: Final STL artifacts produced and validated (or user-overridden with recorded attestation).
- **`FAILED`**: Terminal failure; includes error details and recoverability hints.
- **`CANCELLED`**: User cancelled; processing halted; partial artifacts retained with status.

### Job `hold_reason` (required when `ACTION_REQUIRED` or `REVIEW_REQUIRED`)
- **`INPUT_MISSING`**
- **`QUALITY_LOW`**
- **`SAFETY_IP_BLOCK`**
- **`ATTESTATION_REQUIRED`**
- **`PRINTABILITY_ERRORS`**
- **`USER_APPROVAL_REQUIRED`**
- **`PAYMENT_REQUIRED`** (if monetized; optional)

### Job Step Model (internal)
- **`PENDING`**
- **`QUEUED`**
- **`RUNNING`**
- **`SUCCEEDED`**
- **`FAILED`**
- **`CANCELLED`**
- **`SKIPPED`**
- **`WAITING_USER`**

## 1.4 Example State Transitions (Concrete)

- **Relief pipeline (happy path)**:
  - `DRAFT` → `SUBMITTED` → `VALIDATING` → `QUEUED` → `RUNNING` → `REVIEW_REQUIRED` (preview) → `RUNNING` (supports/export) → `SUCCEEDED`

- **Scan pipeline (quality gate fail)**:
  - `DRAFT` → `SUBMITTED` → `VALIDATING` → `ACTION_REQUIRED` (`QUALITY_LOW`) → (user uploads more photos) → `VALIDATING` → `QUEUED` → `RUNNING`

- **Generative pipeline (IP prompt block)**:
  - `DRAFT` → `SUBMITTED` → `VALIDATING` → `ACTION_REQUIRED` (`SAFETY_IP_BLOCK`) with “revise prompt” UI

## 1.5 Hard Block vs Override Policy (Canonical)

This table governs whether a job can proceed without changing inputs, and what must be logged if the user proceeds.

| Category | Default system action | Override allowed? | Required logging | Typical job state/hold_reason |
|---|---|---:|---|---|
| Safety/IP (high confidence) | Block | No | Safety finding + evidence | `ACTION_REQUIRED / SAFETY_IP_BLOCK` |
| Safety/IP (medium confidence) | Review | Yes | Safety finding + user override attestation | `ACTION_REQUIRED / SAFETY_IP_BLOCK` or `REVIEW_REQUIRED` |
| Printability `ERROR` | Block | Yes | Risk acceptance attestation + snapshot of findings | `ACTION_REQUIRED / PRINTABILITY_ERRORS` |
| Quality LOW | Pause | Yes | Risk acceptance attestation + quality metrics | `ACTION_REQUIRED / QUALITY_LOW` |
| Bed fit FAIL | Block | No (until split supported) | Finding + recommended resize/profile change | `ACTION_REQUIRED / PRINTABILITY_ERRORS` |

**Enforcement rules**:
- A “hard block” means the UI must not show a “Proceed anyway” path; the only path forward is changing inputs/config to clear the gate.
- An “override allowed” gate requires an explicit user action (checkbox + typed confirmation) and must emit a `JobEvent` capturing:
  - the finding codes being overridden
  - the user-provided attestation text
  - a hash of the validation report(s) at time of acceptance

---

# 2) Functional Requirements by Module

## 2.1 Frontend (Web App)

### Must-have (MVP)
- **Authentication UX**: sign-in/sign-up, session handling.
- **Project dashboard**: list projects, create project, open project.
- **Job creation wizard**: choose pipeline A/B/C, select printer profile, configure settings.
- **Upload UX**:
  - Multi-photo upload (scan).
  - Single-image upload (relief).
  - Optional ref images upload (generative).
  - Resume/retry on failure.
- **Real-time progress UI**: step-by-step timeline + ETA (best-effort).
- **3D viewer**:
  - Preview mesh (GLB recommended for preview even if STL final).
  - Basic controls: rotate/zoom/pan, toggle wireframe, measure tool.
  - Scale controls (mm) + mini presets (28mm/32mm).
- **Explain problems panel**:
  - Shows validations grouped by severity.
  - Plain-language explanation + recommended action buttons (e.g., “Auto-repair mesh,” “Add thickness,” “Retake photos”).

### Later enhancements
- **Mask editor** for scan photos (brush/erase).
- **Advanced mesh editing** (cut plane, hole fill UI, sculpt lite).
- **Print orientation assistant** (auto-orient + visualize supports/overhang heatmap).
- **Version compare** for generations/reconstructions.
- **Team projects** (shared workspaces, reviewer roles).

## 2.2 Backend API (Control Plane)

### Must-have (MVP)
- **CRUD for projects/jobs/artifacts** with tenant isolation.
- **Upload mediation**:
  - Generate pre-signed URLs.
  - Enforce content-type, size, and checksum.
- **Job submission**: create job, lock inputs, notify orchestrator.
- **Validation retrieval**: provide structured validation results.
- **Artifact access**: signed download URLs for artifacts, time-limited.
- **Printer profiles**: built-in defaults + user custom profiles.

### Later enhancements
- **Billing integration**: usage metering, quotas, paid tiers.
- **Audit/report export**: “model provenance report” including attestations and safety decisions.

## 2.3 Orchestrator (Workflow Engine)

### Must-have (MVP)
- **Create steps per pipeline** based on job type and configuration.
- **State transitions** adhering to canonical taxonomy.
- **Dispatch to MCP tools** with artifact URIs as inputs/outputs.
- **Pause/resume** on `ACTION_REQUIRED` / `REVIEW_REQUIRED`.
- **Retries** for transient worker errors; deterministic idempotency.
- **Cancellation**: user cancels job; orchestrator signals worker to abort.

### Later enhancements
- **Dynamic routing**:
  - Choose photogrammetry vs NeRF based on photo count/hardware.
  - Auto-adjust parameters if quality borderline (downscale, denoise).
- **Cost-aware scheduling**:
  - GPU time quotas, priority queues.
- **Human moderation workflow** for borderline IP cases.

## 2.4 Processing Layer (CPU/GPU tools)

### Must-have (MVP)
- **Image analysis**: blur/exposure/resolution checks; duplicates; basic logo scan.
- **Relief generation**: depth estimation + mesh creation + export.
- **Mesh repair**: watertight/manifold repair; decimation; unit normalization.
- **Printability validations**: thickness, overhang, fragile features, bounding box checks.
- **Support generation integration**: call slicer CLI/service and return supported mesh.

### Later enhancements
- **Full photogrammetry** (COLMAP/OpenMVS/AliceVision) and/or NeRF mesh extraction.
- **Generative mini synthesis** with iterative refinement and higher fidelity.
- **Texture baking** and textured preview.

## 2.5 Safety & IP Layer

### Must-have (MVP)
- **Prompt filtering**:
  - Block/flag trademarked names and close variants (fuzzy match, leetspeak).
  - Explain block reason and offer “rewrite suggestions” focused on generic descriptors.
- **Image insignia detection**:
  - Flag obvious faction logos, brand marks, recognizable insignia patterns.
- **Scan attestation**:
  - Required checkbox + typed confirmation: “I own rights or have permission to scan this object and it is not prohibited IP.”
- **Logging**:
  - Persist safety decisions and user actions to audit log.

### Later enhancements
- **Similarity search**:
  - Compare generated meshes/images to internal IP reference embeddings.
- **Human review console**:
  - Moderator queue, escalation, appeal flow.

---

# 3) Non-Functional Requirements (NFRs)

## 3.1 Performance / Latency Targets
- **Relief pipeline**:
  - **MVP target**: 1–3 minutes end-to-end for 1K–2K image on GPU; 3–8 minutes on CPU fallback (if allowed).
- **Generative minis**:
  - **MVP**: 3–8 minutes for first draft mesh; <2 minutes per variation (GPU-dependent).
- **Scan pipeline**:
  - **v1**: 15–60 minutes depending on photo count and compute; show continuous progress and intermediate previews.

## 3.2 Scalability
- **Horizontal scaling**:
  - API and orchestrator scale by replicas.
  - Workers scale by queue depth and GPU availability.
- **Queues**:
  - Separate **CPU queue** and **GPU queue** with distinct concurrency limits.
- **Multi-tenant isolation**:
  - Per-tenant rate limits + per-tenant storage quotas.

## 3.3 Storage & Retention
- **Object storage**:
  - Versioned artifacts; immutable once finalized.
  - Lifecycle policies:
    - **Intermediate artifacts**: default 30 days (configurable).
    - **Final artifacts (STL + chosen previews)**: default 1 year (configurable).
- **Database**:
  - Keep metadata indefinitely or per compliance requirements.

## 3.4 Observability
- **Tracing**: distributed traces from API → orchestrator → tool calls.
- **Metrics**:
  - Queue wait time, job durations, step success rates, GPU utilization, retry counts.
- **Logging**:
  - Structured logs with correlation IDs (`job_id`, `step_id`, `artifact_id`).
- **Alerting**:
  - Worker crash loops, GPU OOM spikes, upload failures, high moderation blocks.

## 3.5 Security
- **Transport**: TLS everywhere.
- **At rest**: encryption for DB and object storage.
- **Uploads**: strict content-type validation, malware scanning, and size limits.
- **Secrets**: managed secrets store; no secrets in logs.

---

# 4) Data Model (Entities, Fields, Relationships)

## 4.1 Entities

### **User**
- **Key fields**: `id`, `email`, `name`, `created_at`, `last_login_at`, `role` (user/admin), `status`
- **Relationships**: has many `projects`, has many `printer_profiles`, has many `jobs` (through projects)

### **Project**
- **Key fields**: `id`, `user_id`, `name`, `description`, `created_at`, `updated_at`
- **Relationships**: has many `jobs`, has many `artifacts`

### **Job**
- **Key fields**:
  - `id`, `project_id`, `pipeline_type` (`SCAN|RELIEF|GENERATIVE`)
  - `state` (canonical), `hold_reason` (nullable)
  - `config` (JSON; immutable after submit except allowed edits)
  - `model_preset_id` (nullable; primarily for minis/generative)
  - `printer_profile_id`
  - `created_at`, `submitted_at`, `completed_at`
  - `error_code`, `error_message` (nullable)
  - `safety_status` (`PASS|BLOCK|REVIEW`) + `safety_summary`
  - `quality_score` (float 0.0–1.0)
  - `quality_score_version` (string; used to keep scoring comparable over time)
  - `quality_summary` (JSON; see §6.0.1)
- **Relationships**:
  - has many `job_steps`
  - has many `artifacts`
  - has many `validation_reports`
  - has many `events`
  - has one `attestation` (required for scan)

### **JobStep**
- **Key fields**:
  - `id`, `job_id`, `step_key` (enum), `state` (step state)
  - `attempt`, `started_at`, `ended_at`
  - `input_artifact_ids[]`, `output_artifact_ids[]`
  - `progress` (0..1), `progress_message`
- **Relationships**: belongs to `job`

### **Artifact**
- **Key fields**:
  - `id`, `job_id`, `project_id`, `artifact_type`
  - `format` (`jpg|png|ply|obj|glb|stl|json|zip`)
  - `uri` (object storage), `sha256`, `size_bytes`
  - `version`, `label`, `created_at`
  - `metadata` (JSON; e.g., dimensions, units, triangle count)
- **Relationships**:
  - belongs to `job` and `project`
  - has many `artifact_lineage` edges (parents/children)

### **ArtifactLineage**
- **Key fields**: `parent_artifact_id`, `child_artifact_id`, `transform_type` (e.g., `REPAIR`, `DECIMATE`)
- **Purpose**: reproducibility and provenance

### **PrinterProfile**
- **Key fields**:
  - `id`, `user_id` (nullable for system default), `name`
  - `printer_type` (`FDM|RESIN`)
  - `settings` (JSON; nozzle/pixel size, layer height, etc.)
  - `created_at`, `updated_at`

### **ModelPreset**
- **Purpose**: a constrained design preset to reduce prompt entropy and standardize scale/base/pose/detail defaults.
- **Key fields**:
  - `id`, `user_id` (nullable for system preset), `name`, `category` (`MINI`)
  - `mini_scale_preset` (`MINI_28MM_HEROIC|MINI_32MM`)
  - `base_preset` (e.g., `ROUND_25MM|ROUND_32MM|ROUND_40MM|NONE`)
  - `pose_category` (e.g., `IDLE|CHARGING|AIMING|LEADER`)
  - `detail_density` (`LOW|MED|HIGH`)
  - `default_config` (JSON; pipeline-specific defaults)
  - `created_at`, `updated_at`

### **ValidationReport**
- **Key fields**:
  - `id`, `job_id`, `scope` (`INPUT|MESH|PRINTABILITY|SAFETY`)
  - `status` (`PASS|WARN|FAIL`)
  - `created_at`, `summary`
- **Relationships**: has many `validation_findings`

### **ValidationFinding**
- **Key fields**:
  - `id`, `report_id`, `severity` (`INFO|WARNING|ERROR`)
  - `code` (stable identifier), `title`, `message_plain`
  - `metric_name`, `metric_value`, `threshold`
  - `recommended_action` (enum), `action_payload` (JSON)
  - `related_artifact_id` (nullable)
  - `created_at`

### **SafetyFinding**
- **Key fields**:
  - `id`, `job_id`, `severity`, `type` (`PROMPT|IMAGE|ATTESTATION`)
  - `matched_terms[]`, `confidence`, `evidence_artifact_id` (nullable)
  - `decision` (`ALLOW|BLOCK|REVIEW`), `created_at`

### **Attestation**
- **Key fields**:
  - `id`, `job_id`, `user_id`, `text`, `confirmed_at`, `ip_address`, `user_agent`

### **JobEvent**
- **Key fields**:
  - `id`, `job_id`, `type` (enum), `payload` (JSON), `created_at`
- **Purpose**: timeline + streaming source + audits

### **WebhookSubscription** (optional but recommended)
- **Key fields**: `id`, `user_id`, `url`, `secret`, `events[]`, `created_at`, `status`

---

# 5) API Specification (Endpoints, Shapes, Events, State Machine)

## 5.1 Conventions

- **Auth**: Bearer token (OIDC/JWT). Every object is scoped to a tenant/user.
- **Idempotency**: `Idempotency-Key` header on:
  - Job create/submit
  - Upload session create
- **Error format** (consistent):
```json
{
  "error": {
    "code": "VALIDATION_FAILED",
    "message": "One or more inputs are invalid.",
    "details": [
      { "field": "config.scale_mm", "reason": "Must be > 0" }
    ],
    "request_id": "req_..."
  }
}
```

## 5.2 Core Endpoints

### Projects
- **`POST /v1/projects`**
  - **Request**:
```json
{ "name": "My Mini Project", "description": "..." }
```
  - **Response**:
```json
{ "id": "proj_123", "name": "...", "created_at": "..." }
```

- **`GET /v1/projects`**
- **`GET /v1/projects/{project_id}`**

### Jobs
- **`POST /v1/projects/{project_id}/jobs`**
  - **Request**:
```json
{
  "pipeline_type": "RELIEF",
  "model_preset_id": null,
  "printer_profile_id": "pp_default_fdm_04",
  "config": {
    "output_scale_preset": "MINI_32MM",
    "relief_mode": "BAS_RELIEF"
  }
}
```
  - **Response**:
```json
{
  "id": "job_abc",
  "state": "DRAFT",
  "pipeline_type": "RELIEF",
  "config": { "...": "..." }
}
```

- **`PATCH /v1/jobs/{job_id}`** (only when `state=DRAFT` or when explicitly allowed)
- **`POST /v1/jobs/{job_id}/submit`**
  - **Response**:
```json
{ "id": "job_abc", "state": "SUBMITTED" }
```

- **`POST /v1/jobs/{job_id}/cancel`**
- **`POST /v1/jobs/{job_id}/resume`** (from `ACTION_REQUIRED` or `REVIEW_REQUIRED` after user changes/accepts)
- **`GET /v1/jobs/{job_id}`** (includes `state`, `hold_reason`, latest validation summary)
- **`GET /v1/jobs/{job_id}/steps`**
- **`GET /v1/jobs/{job_id}/events`**

### Uploads
- **`POST /v1/uploads`** (create upload session + pre-signed URLs)
  - **Request**:
```json
{
  "job_id": "job_abc",
  "artifact_type": "RAW_PHOTO",
  "files": [
    { "filename": "img_001.jpg", "content_type": "image/jpeg", "size_bytes": 5234234, "sha256": "..." }
  ]
}
```
  - **Response**:
```json
{
  "upload_session_id": "upl_123",
  "files": [
    { "filename": "img_001.jpg", "put_url": "https://...", "artifact_id": "art_001" }
  ]
}
```

- **`POST /v1/uploads/{upload_session_id}/complete`**
  - Finalizes artifacts, triggers `VALIDATING` if job was submitted.

### Artifacts and Downloads
- **`GET /v1/jobs/{job_id}/artifacts`**
- **`GET /v1/artifacts/{artifact_id}`**
- **`POST /v1/artifacts/{artifact_id}/download-url`**
  - Returns time-limited URL.

### Validations
- **`GET /v1/jobs/{job_id}/validations`**
- **`GET /v1/validation-reports/{report_id}`**

### Printer Profiles
- **`GET /v1/printer-profiles`** (system + user)
- **`POST /v1/printer-profiles`** (user custom)
- **`PATCH /v1/printer-profiles/{id}`**

### Model Presets
- **`GET /v1/model-presets`** (system + user)
- **`POST /v1/model-presets`** (user custom)
- **`GET /v1/model-presets/{id}`**
- **`PATCH /v1/model-presets/{id}`**

### Safety / Moderation
- **`GET /v1/jobs/{job_id}/safety`**
- **`POST /v1/jobs/{job_id}/attest`**
  - **Request**:
```json
{ "text": "I confirm I have rights to scan..." }
```

## 5.3 Streaming and Webhooks

- **`GET /v1/jobs/{job_id}/stream`** (SSE preferred for simplicity)
  - Events:
```json
{ "type": "JOB_STATE_CHANGED", "job_id": "job_abc", "state": "RUNNING", "at": "..." }
{ "type": "STEP_PROGRESS", "job_id": "job_abc", "step_key": "REPAIR_MESH", "progress": 0.6, "message": "Fixing non-manifold edges..." }
{ "type": "ARTIFACT_CREATED", "artifact_id": "art_900", "artifact_type": "MESH_REPAIRED" }
{ "type": "VALIDATION_REPORT_CREATED", "report_id": "vr_77", "scope": "PRINTABILITY" }
```

- **Webhooks (optional)**:
  - **`POST /v1/webhooks`** to register.
  - Signed delivery with `X-Signature` (HMAC of payload).

---

# 6) Pipeline Specifications (Inputs, Validations, Gates, Human Checkpoints, Artifacts)

## 6.0 Shared Pipeline Concepts

### Shared input validations (all pipelines)
- **`FILE_TYPE_ALLOWED`**: only whitelist (jpeg/png for images; optional zip for batches).
- **`FILE_SIZE_LIMIT`**: per file and per job quota.
- **`CHECKSUM_MATCH`**: sha256 matches declared.
- **`MALWARE_SCAN_PASS`**: must pass before processing.
- **`SAFETY_SCAN`**: prompt/image checks before expensive compute.

### Shared artifact types (common)
- **`RAW_PHOTO`**, **`RAW_IMAGE`**
- **`ANALYSIS_REPORT_JSON`**
- **`MASK_IMAGE`**
- **`DEPTH_MAP`**
- **`POINT_CLOUD_SPARSE`**, **`POINT_CLOUD_DENSE`**
- **`MESH_RAW`**, **`MESH_CLEANED`**, **`MESH_REPAIRED`**, **`MESH_SCALED_MM`**
- **`MESH_HOLLOWED`**, **`MESH_SUPPORTED`**
- **`PREVIEW_GLB`**
- **`FINAL_STL`**
- **`VALIDATION_REPORT_JSON`**

### 6.0.1 Canonical Job Quality Score (`quality_score`)

**Purpose**: a single scalar for UX (“Overall Quality: 72/100”), user warnings, analytics, and longitudinal tracking.

**Stored on `Job`**:
```json
{
  "quality_score": 0.0,
  "quality_score_version": "v1",
  "quality_summary": {
    "input_quality": 0.78,
    "reconstruction_confidence": 0.65,
    "printability_risk": 0.12,
    "notes": ["Low top-down coverage", "Thin sword tip"]
  }
}
```

**Ranges**:
- `quality_score`: 0.0–1.0 (UI can display as `round(score*100)`)
- `input_quality`: 0.0–1.0
- `reconstruction_confidence`: 0.0–1.0
- `printability_risk`: 0.0–1.0 (**0 is best**, 1 is worst)

**Computation (v1)**:
- Convert each relevant technical metric into a 0..1 subscore.
- Compute:
  - `printability_quality = 1.0 - printability_risk`
  - `quality_score = clamp01(w_in * input_quality + w_rec * reconstruction_confidence + w_pr * printability_quality)`

**Default weights by pipeline (v1)**:
- `SCAN`: `w_in=0.35`, `w_rec=0.45`, `w_pr=0.20`
- `RELIEF`: `w_in=0.50`, `w_rec=0.20`, `w_pr=0.30` (depth confidence counts as reconstruction)
- `GENERATIVE`: `w_in=0.20`, `w_rec=0.50`, `w_pr=0.30`

**Source signals (non-exhaustive; must be logged in `quality_summary` or linked reports)**:
- `input_quality`:
  - Scan: blur/exposure/resolution pass rates, duplicate ratio, coverage estimate
  - Relief: resolution + contrast + crop acceptance
  - Generative: prompt safety cleanliness (no blocked terms), reference image quality (if provided)
- `reconstruction_confidence`:
  - Scan photogrammetry: camera solve success rate, reprojection error, inlier ratio, mesh confidence
  - Relief: depth model confidence/consistency (or proxy metrics)
  - Generative: model confidence proxies + mesh sanity checks (degenerate triangles, disconnected parts)
- `printability_risk`:
  - Derived from printability findings severity and “distance to threshold” (e.g., min wall thickness margin)
  - If `BED_FIT_FAIL` then `printability_risk=1.0` and **override is not allowed** (see §1.5)

**UI thresholds (v1)**:
- `quality_score >= 0.80`: “Great” (no warnings)
- `0.60–0.79`: “Good” (show warnings if any `WARN` findings)
- `0.40–0.59`: “Risky” (default to `ACTION_REQUIRED/QUALITY_LOW` for scan inputs)
- `< 0.40`: “Poor” (strong guidance; allow override only where policy permits)

---

## 6.1 Pipeline A — Multi-Photo Scanning (Photogrammetry / NeRF)

### A.1 Inputs
- **Required**: 30–200 photos (JPEG/PNG), recommended 12MP+.
- **Optional**: turntable metadata (if available), object category hint, masking preference.

### A.2 Quality Gates & Thresholds (initial)
- **`MIN_PHOTO_COUNT`**:
  - **Must-have**: ≥ 30
  - **Recommended**: 60–120
- **`BLUR_SCORE`**:
  - **Gate**: reject if >25% images “blurry” (variance of Laplacian below threshold).
- **`EXPOSURE_SCORE`**:
  - **Gate**: reject if >20% severely under/overexposed.
- **`DUPLICATE_DETECTION`**:
  - **Gate**: warn if >15% near-duplicates.
- **`COVERAGE_ESTIMATE`** (heuristic; based on viewpoint clustering):
  - **Gate**: require viewpoints across at least 3 elevation bands (low/mid/high) for full 3D.
- **`BACKGROUND_COMPLEXITY`**:
  - **Gate**: warn if background high-frequency dominates (suggest plain backdrop).

### A.3 Safety/IP Gates
- **`SCAN_ATTESTATION_REQUIRED`**:
  - **Gate**: job must enter `ACTION_REQUIRED` with `ATTESTATION_REQUIRED` until provided.
- **`IMAGE_INSIGNIA_DETECTION`**:
  - **Gate**: if high-confidence logo detected → `ACTION_REQUIRED` with `SAFETY_IP_BLOCK` (or `REVIEW_REQUIRED` if you support human moderation).

### A.4 Human-in-the-loop Checkpoints (UI)
- **Checkpoint 1 (after analysis)**: `ACTION_REQUIRED/QUALITY_LOW`
  - **UI**: coverage visualization + list of failed photos + retake guidance.
  - **User actions**:
    - Upload additional photos.
    - Remove bad photos.
    - Continue anyway (requires explicit “I accept lower quality” confirmation).

- **Checkpoint 2 (optional masking)**: `REVIEW_REQUIRED/USER_APPROVAL_REQUIRED`
  - **UI**: auto-masks preview; user edits masks if needed.

- **Checkpoint 3 (after raw mesh)**: `REVIEW_REQUIRED/USER_APPROVAL_REQUIRED`
  - **UI**: 3D preview; cropping/cleanup suggestions; choose scale reference.

- **Checkpoint 4 (printability)**: `ACTION_REQUIRED/PRINTABILITY_ERRORS`
  - **UI**: fix-issues action list (auto-repair, thicken, re-orient, hollow, supports).

### A.5 Step-by-step Artifacts (Concrete)
- **Step `ANALYZE_PHOTOS`**:
  - Outputs:
    - `ANALYSIS_REPORT_JSON` (blur/exposure/coverage metrics)
    - Optional `COVERAGE_HEATMAP_IMAGE`
- **Step `MASK_PHOTOS`** (optional):
  - Outputs:
    - `MASK_IMAGE` per photo
- **Step `RECONSTRUCT`**:
  - Outputs:
    - `POINT_CLOUD_SPARSE` (.ply)
    - `POINT_CLOUD_DENSE` (.ply)
    - `MESH_RAW` (.obj/.ply)
    - Optional textures
- **Step `CLEAN_MESH`**:
  - Outputs:
    - `MESH_CLEANED`
    - `PREVIEW_GLB`
- **Step `REPAIR_MESH`**:
  - Outputs:
    - `MESH_REPAIRED`
- **Step `NORMALIZE_SCALE`**:
  - Outputs:
    - `MESH_SCALED_MM`
- **Step `PRINTABILITY_VALIDATE`**:
  - Outputs:
    - `VALIDATION_REPORT_JSON` (printability)
- **Step `GENERATE_SUPPORTS`** (optional by printer type):
  - Outputs:
    - `MESH_SUPPORTED`
- **Step `EXPORT_STL`**:
  - Outputs:
    - `FINAL_STL`

---

## 6.2 Pipeline B — Single-Image Relief (Bas-relief / Lithophane / Coin)

### B.1 Inputs
- **Required**: 1 image (JPEG/PNG).
- **Config**:
  - `relief_mode`: `BAS_RELIEF | LITHOPHANE | COIN`
  - `target_width_mm` / `target_height_mm`
  - `max_relief_depth_mm`
  - `base_thickness_mm`
  - `invert` (for lithophane)
  - optional rim/text (coin mode)

### B.2 Quality Gates & Thresholds
- **`MIN_RESOLUTION`**:
  - **MVP gate**: min shortest side ≥ 1024px
- **`SUBJECT_CONTRAST`**:
  - **Gate**: warn if extremely low contrast; recommend edits.
- **`CROP_REQUIRED`**:
  - **Gate**: if aspect mismatch with target dimensions; user must crop or auto-crop preview.
- **`SAFETY_IMAGE_INSIGNIA`**:
  - **Gate**: block if obvious trademark/logo detected.

### B.3 Human-in-the-loop Checkpoints (UI)
- **Checkpoint 1 (crop/subject)**: `ACTION_REQUIRED/USER_APPROVAL_REQUIRED`
  - **UI**: crop tool + optional background removal toggle.
- **Checkpoint 2 (depth preview)**: `REVIEW_REQUIRED/USER_APPROVAL_REQUIRED`
  - **UI**: show depth map, sliders for smoothing/contrast, relief depth preview.
- **Checkpoint 3 (printability)**: `ACTION_REQUIRED/PRINTABILITY_ERRORS`
  - **UI**: enforce base thickness, minimum ridge thickness.

### B.4 Artifacts by Step (Concrete)
- **Step `ANALYZE_IMAGE`**:
  - Outputs:
    - `ANALYSIS_REPORT_JSON`
- **Step `ESTIMATE_DEPTH`** (GPU preferred):
  - Outputs:
    - `DEPTH_MAP` (image or float map)
- **Step `GENERATE_RELIEF_MESH`**:
  - Outputs:
    - `MESH_RAW`
    - `PREVIEW_GLB`
- **Step `REPAIR_MESH`**:
  - Outputs:
    - `MESH_REPAIRED`
- **Step `EXPORT_STL`**:
  - Outputs:
    - `FINAL_STL`

---

## 6.3 Pipeline C — Generative Minis (Text + Optional Reference Images)

### C.1 Inputs
- **Required**: text prompt (user-controlled).
- **Optional**: 1–5 reference images (pose silhouette, armor vibe, etc.).
- **Config**:
  - `model_preset_id` (recommended)
  - `style`: grimdark sci-fi slider set (e.g., “gothic/industrial,” “bio-mech,” “rusty,” “clean”)
  - `anatomy_preset`: humanoid/robot/alien/beast
  - `pose`: idle/charging/aiming/leader stance
  - `detail_level`: low/med/high
  - `base_type`: none/round/base scenic
  - `mini_scale_preset`: 28mm heroic / 32mm

### C.2 Safety/IP Gates (strict)
- **`PROMPT_TRADEMARK_FILTER`**:
  - **Gate**: block trademarked faction names, brand names, and close variants.
- **`IMAGE_LOGO_FILTER`**:
  - **Gate**: block if uploaded images contain obvious insignia/logos.
- **`USER_INTENT_ATTESTATION`**:
  - **Gate**: user must confirm “I am requesting an original design and not a branded replica.”

### C.3 Human-in-the-loop Checkpoints (UI)
- **Checkpoint 1 (prompt safety block)**: `ACTION_REQUIRED/SAFETY_IP_BLOCK`
  - **UI**: show blocked terms (redacted if needed) + rewrite tool + allowed examples.
- **Checkpoint 2 (first mesh preview)**: `REVIEW_REQUIRED/USER_APPROVAL_REQUIRED`
  - **UI**: show 3–6 variations; pick one; allow refine prompt and regenerate.
- **Checkpoint 3 (printability)**: `ACTION_REQUIRED/PRINTABILITY_ERRORS`
  - **UI**: thin features highlighted; allow thickening and support strategy changes.

### C.4 Artifacts by Step (Concrete)
- **Step `SAFETY_PROMPT_SCAN`**:
  - Outputs:
    - `VALIDATION_REPORT_JSON` (safety)
- **Step `GENERATE_3D`** (GPU):
  - Outputs:
    - `MESH_RAW`
    - `PREVIEW_GLB`
- **Step `REFINE_MESH`** (CPU/GPU depending on approach):
  - Outputs:
    - `MESH_CLEANED`
- **Step `REPAIR_MESH`**:
  - Outputs:
    - `MESH_REPAIRED`
- **Step `NORMALIZE_SCALE`**:
  - Outputs:
    - `MESH_SCALED_MM`
- **Step `GENERATE_SUPPORTS`** (optional):
  - Outputs:
    - `MESH_SUPPORTED`
- **Step `EXPORT_STL`**:
  - Outputs:
    - `FINAL_STL`

---

# 7) Mesh Normalization & Printability Specification

## 7.1 Mesh Standards (required before STL export)
- **`UNITS_MM`**: mesh must be scaled to millimeters; store `units="mm"` in metadata.
- **`WATERTIGHT`**: closed surface; no holes.
- **`MANIFOLD`**: no non-manifold edges/vertices.
- **`NO_SELF_INTERSECTIONS`**: resolve intersections that break slicing.
- **`NORMALS_CONSISTENT`**: outward-facing; no flipped islands.
- **`TRIANGLE_BUDGET`**: configurable (e.g., <2M triangles for viewer; decimate for preview if needed).

## 7.2 Printability Checks (Validation Findings)

### Common checks (FDM + resin)
- **`MIN_WALL_THICKNESS`**:
  - Compare local thickness field against profile threshold.
- **`MIN_FEATURE_DIAMETER`**:
  - Detect pins/antennas/edges thinner than threshold.
- **`ISOLATED_FLOATERS`**:
  - Remove small disconnected components or flag.
- **`BED_FIT`**:
  - Bounding box must fit within printer bed volume (unless split is supported later).
- **`OVERHANGS`**:
  - Detect faces exceeding overhang angle relative to chosen orientation.

### FDM-specific rules (parameterized)
- **`min_wall_mm`**: default `2 * nozzle_diameter` (e.g., 0.8mm for 0.4 nozzle).
- **`min_feature_mm`**: default `0.8 * nozzle_diameter`.
- **`max_overhang_angle_deg`**: default 45°.
- **`bridge_length_mm`**: warn if unsupported spans exceed profile.

### Resin-specific rules (parameterized)
- **`min_wall_mm`**: often 0.6–1.2mm depending on resin/printer.
- **`min_pillar_mm`**: ensure thin spikes are supportable (or auto-support).
- **`islands_detection`**: identify islands for support generation.
- **`hollowing`**:
  - Require minimum wall thickness after offset.
  - Require **drain holes** (size and count) and verify accessibility.

## 7.3 Scale Normalization & Mini Presets
- **`MINI_28MM_HEROIC`**:
  - Default humanoid “eye height” 28mm (approx; user confirms anchor).
- **`MINI_32MM`**:
  - Default eye height 32mm.
- **User flow**:
  - User chooses preset.
  - Viewer prompts: “Select a reference point (feet-to-eyes / feet-to-head).”
  - System computes scale factor and records `scale_method`.

## 7.4 Auto-Fix Actions (Fix Issues Panel)
Each validation finding must map to one or more actions:

- **`AUTO_REPAIR_WATERTIGHT`**: fill holes, weld vertices, remove self-intersections.
- **`AUTO_THICKEN_FEATURES`**: selective offset/remesh in thin regions (bounded).
- **`AUTO_ORIENT_FOR_MIN_SUPPORTS`**: propose orientation that reduces supports.
- **`AUTO_HOLLOW_AND_DRAIN`**: resin hollowing with drain holes + checks.
- **`AUTO_GENERATE_SUPPORTS`**: run support generation tool with profile defaults.
- **`AUTO_DECIMATE_FOR_VIEWER`**: only for preview (not for print STL unless requested).

---

# 8) UI/UX Flows (Wizards, Viewer, Explain Panel)

## 8.1 Capture Wizard (Scan Pipeline)
- **Step 1: Prep Guidance**
  - **Must-have**:
    - Recommended lighting, matte spray suggestion (optional), background advice.
- **Step 2: Upload + Live Quality Scoring**
  - **Must-have**:
    - Show per-photo badges: sharpness, exposure, resolution.
    - Duplicate warnings.
- **Step 3: Coverage Visualization**
  - **Must-have**:
    - Show missing-angle guidance: “Need more top-down shots” etc.
    - Require attestation before proceeding.
- **Step 4: Review & Start Reconstruction**
  - **Must-have**:
    - “Proceed anyway” requires explicit acknowledgement if quality borderline.

## 8.2 Prompt Wizard (Generative Minis)
- **Step 1: Intent + Safety**
  - **Must-have**:
    - Prompt input with real-time safety feedback.
    - Explicit messaging: “Original grimdark sci-fi minis only.”
- **Step 2: Style and Anatomy**
  - **Must-have**:
    - Sliders: silhouette bulk, surface detail, armor density, ornamentation, griminess.
    - Presets: humanoid/robot/alien.
- **Step 3: Pose + Base**
  - **Must-have**:
    - Pose selector (a small set to start).
    - Base selector (round 25/32/40mm).
- **Step 4: Generate Variations**
  - **Must-have**:
    - Present 3–6 results; pick one; “refine” and regenerate.

## 8.3 Relief Wizard (Single Image)
- **Step 1: Crop + Mode**
  - **Must-have**:
    - Choose bas-relief/lithophane/coin.
    - Crop tool; auto-fit to target dimensions.
- **Step 2: Depth Preview**
  - **Must-have**:
    - Depth map overlay.
    - Sliders: smoothing, contrast, depth amplitude, inversion (lithophane).
- **Step 3: Print Preview**
  - **Must-have**:
    - Show thickness checks and warnings.

## 8.4 3D Viewer + “Fix Issues” Action List
- **Viewer features (must-have)**:
  - Rotate/zoom/pan, wireframe toggle, bounding box dimensions.
  - Measure tool (point-to-point).
  - Scale controls + presets.
  - Auto-orient button.
- **Fix issues panel (must-have)**:
  - Group by severity:
    - **ERROR**: blocks completion until fixed or explicitly overridden.
    - **WARNING**: recommend fix, allow proceed.
    - **INFO**: optional improvements.
  - One-click actions mapped to validations.
- **Explain problems panel (must-have)**:
  - Plain language + “why it matters for printing.”
  - Example: “This sword tip is 0.35mm thick but your resin profile minimum is 0.6mm. It may snap during cleanup.”

---

# 9) Job Orchestration (Queues, Retries, Idempotency, Cancellation, Progress)

## 9.1 Workflow Design
- **Each job is a workflow**:
  - Steps defined by `pipeline_type` + config.
  - Step outputs stored as artifacts and referenced by IDs.
- **Workflow must support pausing**:
  - `ACTION_REQUIRED` and `REVIEW_REQUIRED` are explicit pause points.
  - Resume requires a user action (upload, config update, acceptance).

## 9.2 Queues and Worker Pools
- **Separate queues**:
  - **CPU queue**: mesh repair, validations, conversions, supports generation.
  - **GPU queue**: depth estimation, NeRF/reconstruction acceleration, generative inference.
- **Routing**:
  - Orchestrator dispatches by step requirements: `requires_gpu=true/false`.

## 9.3 Retries and Idempotency
- **Retry policy**:
  - Transient errors: retry with exponential backoff, capped attempts.
  - Deterministic failures (bad input): no retry; move to `ACTION_REQUIRED`.
- **Idempotency**:
  - Job submission uses idempotency key.
  - Each step stores a content hash of:
    - input artifact hashes
    - step config parameters
  - If repeated, return existing output artifacts instead of recomputing.

## 9.4 Cancellation
- **User cancellation**:
  - Orchestrator sets job `CANCELLED`, signals workers with cancellation token.
  - Workers must:
    - Stop new work.
    - Safely terminate running subprocesses (best-effort).
    - Mark step `CANCELLED`.

## 9.5 Progress Updates and Notifications
- **Progress contract**:
  - Workers emit step progress `0..1` with a message and optional substage.
- **UI updates**:
  - SSE/WebSocket stream from API reading `JobEvents`.
- **Notifications**:
  - Email/push optional: “job completed,” “action required,” “failed.”

---


# 10) MCP Integration Plan (Tool Interfaces, GPU/CPU, Artifact Passing)

## 10.1 Integration Model (how orchestration calls tools)
- **Orchestrator is the only component that advances `job.state`**. MCP tools are pure processing functions that:
  - Consume **input artifact URIs** + a **typed config**.
  - Produce **output artifacts** written to object storage.
  - Return **artifact descriptors** + **structured reports** (JSON) + **progress**.
- **All artifact I/O uses object storage URIs** (S3-style). No tool should accept raw file bytes over MCP in production.
- **Idempotency**:
  - Orchestrator computes `step_fingerprint = hash(tool_name + tool_version + input_artifact_hashes + config_json)`.
  - Tools receive `step_fingerprint` and must treat it as idempotency key for caching or safe re-run.

## 10.2 Artifact URI + metadata conventions
- **Input reference**: `s3://bucket/tenant/{tenant_id}/jobs/{job_id}/...`
- **Output prefix**: tool receives an `output_prefix_uri` and must write outputs under it:
  - Example: `s3://.../jobs/{job_id}/steps/{step_id}/{tool_name}/`
- **Each produced file** must return:
  - `artifact_type` (from canonical list)
  - `format`
  - `uri`
  - `sha256`
  - `size_bytes`
  - `metadata` (triangle count, units, bounds, etc.)

## 10.3 Standard MCP Tool Envelope (request/response)
### Request (common fields)
```json
{
  "tool_version": "1.0",
  "request_id": "req_...",
  "tenant_id": "ten_...",
  "job_id": "job_...",
  "step_id": "step_...",
  "step_fingerprint": "sha256:...",
  "output_prefix_uri": "s3://.../jobs/job_.../steps/step_.../",
  "inputs": [
    { "artifact_id": "art_...", "artifact_type": "MESH_REPAIRED", "uri": "s3://...", "sha256": "..." }
  ],
  "config": { }
}
```

### Response (common fields)
```json
{
  "status": "SUCCEEDED",
  "warnings": [ { "code": "LOW_TEXTURE_QUALITY", "message": "..." } ],
  "outputs": [
    { "artifact_type": "PREVIEW_GLB", "format": "glb", "uri": "s3://...", "sha256": "...", "size_bytes": 12345, "metadata": {} }
  ],
  "report": { "type": "ANALYSIS_REPORT_JSON", "data": { } },
  "resource_usage": { "cpu_seconds": 12.3, "gpu_seconds": 0.0, "peak_ram_mb": 1400 }
}
```

### Error semantics
- `status` is one of:
  - **`SUCCEEDED`**
  - **`FAILED_TRANSIENT`** (retryable: network, GPU OOM that might succeed later with smaller batch)
  - **`FAILED_PERMANENT`** (non-retryable: invalid inputs, corrupted mesh)
- Tools must return `error.code`, `error.message`, `error.debug` (optional, not user-facing).

## 10.4 Required MCP Tools (as requested)

### 10.4.1 `analyze_photos` (CPU)
- **Used by**: Scan pipeline (A), optional for reference images (C).
- **GPU required**: No.
- **Inputs**: `RAW_PHOTO[]` artifacts.
- **Config** (must-have):
  - `min_resolution_px` (default 1024 shortest side)
  - `blur_threshold` (calibrated)
  - `duplicate_similarity_threshold`
- **Outputs**:
  - `ANALYSIS_REPORT_JSON` (per-photo metrics)
  - Optional `COVERAGE_HEATMAP_IMAGE` (for scan)
- **Report fields (minimum)**:
  - `photos_total`
  - `blurred_count`, `overexposed_count`, `underexposed_count`
  - `duplicates[]` (pairs with similarity)
  - `coverage_estimate` (e.g., `{ bands_ok: true, missing: ["top"] }`)
  - `recommendations[]` (typed actions the UI can render)

### 10.4.2 `reconstruct_mesh` (GPU-optional, usually heavy)
- **Used by**: Scan pipeline (A).
- **GPU required**:
  - **Photogrammetry**: optional GPU (feature matching acceleration if available).
  - **NeRF**: **GPU required**.
- **Inputs**:
  - `RAW_PHOTO[]`
  - Optional `MASK_IMAGE[]`
- **Config** (must-have):
  - `method`: `PHOTOGRAMMETRY | NERF | AUTO`
  - `quality`: `DRAFT | STANDARD | HIGH`
  - `max_photos` (cap for cost control)
- **Outputs** (minimum set):
  - `POINT_CLOUD_SPARSE` (ply)
  - `POINT_CLOUD_DENSE` (ply) (if available)
  - `MESH_RAW` (obj/ply)
  - `ANALYSIS_REPORT_JSON` (camera solve stats, reprojection error)
- **Quality gate signals (in report)**:
  - `camera_solve_success_rate`
  - `median_reprojection_error_px`
  - `inlier_ratio`
  - `mesh_confidence` (0..1 heuristic)

### 10.4.3 `generate_3d` (GPU)
- **Used by**: Generative minis pipeline (C).
- **GPU required**: Yes.
- **Inputs**:
  - Optional `RAW_IMAGE[]` reference images
  - Text prompt passed in `config`
- **Config** (must-have):
  - `prompt` (string)
  - `negative_prompt` (string; optional)
  - `style_profile`: `GRIMDARK_SCIFI_DEFAULT | ...`
  - `detail_level`: `LOW|MED|HIGH`
  - `seed` (optional)
  - `variations` (int, default 4)
- **Outputs**:
  - `MESH_RAW`
  - `PREVIEW_GLB`
  - `ANALYSIS_REPORT_JSON` (model params, seed, safety flags)
- **Safety note**: prompt safety happens **before** this step in orchestrator; this tool should still return a `warning` if it detects disallowed tokens (defense in depth).

### 10.4.4 `repair_mesh` (CPU)
- **Used by**: All pipelines.
- **GPU required**: No.
- **Inputs**: one mesh artifact (`MESH_RAW|MESH_CLEANED`).
- **Config** (must-have):
  - `target_watertight`: true
  - `fix_normals`: true
  - `remove_small_components_mm3` (threshold)
  - `max_triangles` (optional cap)
- **Outputs**:
  - `MESH_REPAIRED`
  - `ANALYSIS_REPORT_JSON` (repairs performed, before/after stats)
- **Hard requirements**:
  - Must produce `units` metadata (or mark as unknown for later normalization).
  - Must output a stable summary for “Explain problems” (e.g., “filled 12 holes”).

### 10.4.5 `validate_printability` (CPU)
- **Used by**: All pipelines before final export.
- **GPU required**: No.
- **Inputs**: mesh (`MESH_REPAIRED|MESH_SCALED_MM`), printer profile settings in config.
- **Config** (must-have):
  - `printer_profile`: full resolved profile JSON (not just ID)
  - `orientation_mode`: `AS_IS|AUTO_ORIENT|USER_DEFINED`
  - `mini_scale_preset` (optional)
- **Outputs**:
  - `VALIDATION_REPORT_JSON`
  - Optional heatmaps:
    - `THICKNESS_HEATMAP_IMAGE`
    - `OVERHANG_HEATMAP_IMAGE`
- **Report fields (minimum)**:
  - `status`: `PASS|WARN|FAIL`
  - `findings[]` (aligned with `ValidationFinding` schema)
  - `recommended_actions[]` (auto-fix actions with payload)

### 10.4.6 `generate_supports` (CPU; may call external slicer)
- **Used by**: Typically resin minis, optionally FDM.
- **GPU required**: No.
- **Inputs**: mesh + printer profile + orientation.
- **Config** (must-have):
  - `support_style`: `LIGHT|MEDIUM|HEAVY`
  - `density` (0..1)
  - `touchpoint_size_mm`
  - `allow_auto_orientation` (bool)
- **Outputs**:
  - `MESH_SUPPORTED` (preferred as mesh with supports merged) and/or
  - `SUPPORTS_METADATA_JSON` (for reproducibility)
- **Implementation note**: If you rely on a slicer (e.g., PrusaSlicer), the tool must:
  - Run in a sandboxed container.
  - Record the slicer version and exact parameters.

### 10.4.7 `export_stl` (CPU)
- **Used by**: All pipelines at the end.
- **GPU required**: No.
- **Inputs**: final mesh stage (`MESH_REPAIRED|MESH_SUPPORTED|MESH_SCALED_MM`).
- **Config**:
  - `binary`: true
  - `units`: `mm` (must be mm at this point)
  - `apply_scale`: 1.0 (or explicit)
- **Outputs**:
  - `FINAL_STL`
  - `ANALYSIS_REPORT_JSON` (triangle count, bounds, checksum)


## 10.5 Additional MCP tools (recommended, not strictly required)
- **`estimate_depth`** (GPU): relief pipeline depth map.
- **`generate_relief_mesh`** (CPU/GPU): bas-relief/lithophane mesh creation.
- **`normalize_scale`** (CPU): mm normalization + mini presets.
- **`hollow_mesh`** (CPU): resin hollow + drain holes.
- **`decimate_mesh`** (CPU): viewer-friendly previews.
- **`detect_logos`** (GPU/CPU): image insignia detection (can live in safety service instead).

---

# 11) Tech Stack Recommendation (with rationale)

## 11.1 Frontend
- **Framework**: **Next.js (React) + TypeScript**
  - **Rationale**: fast iteration, strong ecosystem, SSR for dashboard SEO (optional), easy deployment.
- **UI kit**: **TailwindCSS + shadcn/ui**
  - **Rationale**: consistent components + fast UX iteration.
- **Data fetching**: **React Query** (TanStack Query)
  - **Rationale**: caching, polling/invalidations for job status.
- **3D Viewer**:
  - **three.js** via **react-three-fiber**
  - Loaders: GLB (primary preview), STL (download-only)
  - **Rationale**: industry standard, good performance, extensible for heatmaps/overlays.

## 11.2 Backend (Control Plane API)
- **Framework**: **FastAPI (Python)**
  - **Rationale**: typed schemas (Pydantic), excellent for ML-adjacent services, fast to build, easy OpenAPI generation.
- **DB access**: SQLAlchemy + Alembic migrations
- **Auth**: OIDC (Auth0/Cognito/Clerk) or self-hosted Keycloak for enterprise
- **Rate limiting**: Redis-based (per-user/per-tenant/per-IP)

## 11.3 Orchestrator / Workflow Engine
- **Workflow**: **Temporal**
  - **Rationale**: purpose-built for long-running jobs, retries, durable state, pause/resume, signals for user actions, idempotency.
- **Alternative (simpler MVP)**: Celery + Redis + explicit DB state machine
  - **Tradeoff**: less robust for long-running workflows and human-in-loop pauses.

## 11.4 Queues, Cache, and Realtime
- **Redis**:
  - Caching, rate limit counters, pubsub for progress fanout (optional).
- **Realtime**:
  - **SSE** from API reading `JobEvents` (simpler than WS at MVP).

## 11.5 Storage
- **Object storage**: **S3 (or S3-compatible like MinIO for local dev)**
  - Enable versioning + lifecycle policies.
- **Database**: **PostgreSQL**
  - Strong relational model for jobs/artifacts/lineage/audits.

## 11.6 Containerization + Deployment
- **Containers**: Docker for API, orchestrator, workers, tool servers.
- **Cluster**: Kubernetes (EKS/GKE/AKS) with:
  - **CPU node pool** for API/orchestrator/cpu workers
  - **GPU node pool** for inference/reconstruction
- **Autoscaling**:
  - HPA for API
  - Queue-based autoscaling (KEDA) for workers

## 11.7 3D Processing Toolchain Options (implementation-ready choices)
- **Mesh operations (repair/inspect/convert)**:
  - **trimesh** (Python) for common mesh ops and STL export
  - **pymeshlab** for robust cleanup filters
  - **manifold3d / MeshFix** for watertight repair (choose one; benchmark)
- **Photogrammetry (v1)**:
  - **COLMAP** (SfM) + **OpenMVS** (dense + mesh), or **AliceVision/Meshroom** end-to-end
  - **Rationale**: mature, proven pipelines; containerizable.
- **NeRF (later / optional)**:
  - Nerfstudio or instant-ngp + mesh extraction
- **Depth estimation (relief)**:
  - MiDaS-like depth model (GPU recommended)
- **Supports generation**:
  - **PrusaSlicer CLI** (FDM + SLA supports) as an integration target
  - Store slicer version + config snapshots for reproducibility

## 11.8 Safety/IP tooling
- **Prompt filtering**:
  - Dictionary + fuzzy matching (e.g., rapidfuzz) + optional classifier
- **Image/logo detection**:
  - Start with a detector model (YOLO/CLIP-based) + heuristics
  - **MVP**: conservative block on high-confidence logo hits; otherwise warn + attestation

---

# 12) Testing Strategy

## 12.1 Goals
- **Correctness**: validators and state machine behave deterministically and are regression-safe.
- **Reliability**: long-running jobs tolerate retries, partial failures, and cancellations.
- **Safety/IP**: prompt/image filtering is robust against evasion and logs decisions.
- **Print outcomes**: printability findings are accurate across a curated mesh corpus.

## 12.2 Test Pyramid

### Must-have (MVP)
- **Unit tests (fast, deterministic)**
  - Validators:
    - Input validators (file type/size/checksum)
    - Photo quality metrics (blur/exposure/duplicates)
    - Mesh validations (watertight/manifold/self-intersection detection)
    - Printability checks (thickness/overhang/bed fit)
  - Safety/IP rules:
    - Fuzzy matching (leetspeak, whitespace, punctuation, casing)
    - Keyword allowlist/denylist interactions
    - “Explain problems” mapping: `ValidationFinding.code` → UI action mapping
  - Serialization:
    - All request/response schemas (API + MCP tool envelope)
    - Artifact metadata schema stability

- **Integration tests (job workflow + persistence)**
  - Job lifecycle:
    - `DRAFT → SUBMITTED → VALIDATING → QUEUED → RUNNING → REVIEW_REQUIRED → SUCCEEDED`
    - Negative paths:
      - `VALIDATING → ACTION_REQUIRED (QUALITY_LOW)`
      - `VALIDATING → ACTION_REQUIRED (SAFETY_IP_BLOCK)`
      - `RUNNING → FAILED` with recoverability metadata
      - `RUNNING → CANCELLED` mid-step
  - Step idempotency:
    - Same `step_fingerprint` re-run returns same output artifacts or short-circuits.
  - Artifact lineage:
    - Parent/child relationships correctly recorded for repair/support/export steps.

- **Contract tests (API + MCP)**
  - Verify orchestrator can call MCP tool servers using the standard envelope.
  - Verify tools return `FAILED_TRANSIENT` vs `FAILED_PERMANENT` correctly.
  - Verify object storage URIs are respected and output files are placed under `output_prefix_uri`.

### Later enhancements
- **End-to-end tests (browser + backend)**
  - Use Playwright/Cypress to run:
    - Upload flow
    - Wizard flows
    - Viewer + “Fix issues” actions
    - Resume from `ACTION_REQUIRED`

- **Performance tests**
  - Load tests for:
    - Upload URL issuance
    - SSE stream fan-out
    - Job status polling fallback
  - Soak tests for long-running scan jobs.

## 12.3 Golden Test Assets (Meshes + Images)

### Must-have (MVP)
- **Mesh corpus** (small but representative; store in a versioned test bucket and/or repo LFS)
  - `mesh_watertight_ok.stl` (baseline)
  - `mesh_non_manifold.stl` (expected: `MANIFOLD_ERROR`)
  - `mesh_holes.stl` (expected: `NOT_WATERTIGHT`)
  - `mesh_self_intersect.stl` (expected: `SELF_INTERSECTION`)
  - `mesh_thin_features.stl` (expected: `MIN_FEATURE_DIAMETER_FAIL`)
  - `mesh_overhangs.stl` (expected: `OVERHANGS_WARN/FAIL` depending on profile)
  - `mesh_large_bed.stl` (expected: `BED_FIT_FAIL`)

- **Image corpus**
  - Relief images with known depth behavior (high contrast, low contrast, portrait, landscape).
  - Scan photo samples (synthetic or owned) representing:
    - Good coverage
    - Missing top/bottom coverage
    - Motion blur
    - Duplicates

### Later enhancements
- Add “real-world” anonymized assets via an internal dataset pipeline with explicit rights.
- Add adversarial meshes (degenerate triangles, huge coordinate ranges, NaNs).

## 12.4 Safety/IP Adversarial Testing

### Must-have (MVP)
- **Prompt evasion suite**:
  - Leetspeak substitutions
  - Spacing/punctuation splitting
  - Homoglyph variants
  - “Describe without naming” attempts

- **Image evasion suite**:
  - Partial logo crops
  - Low-contrast logos
  - Rotated and skewed insignia

- **Expected outcomes**:
  - Each case asserts `decision=BLOCK|REVIEW|ALLOW` and that a structured `SafetyFinding` is written.

### Later enhancements
- Property-based tests for fuzzy matching.
- Red-team style prompt/image fuzzing in CI nightly jobs.

## 12.5 GPU Testing Strategy

### Must-have (MVP)
- **CPU-only CI** runs unit + integration + contract tests with MCP tools stubbed.
- **Nightly GPU pipeline** (separate runners):
  - Relief depth estimation
  - Generative `generate_3d` smoke tests (seeded for determinism where possible)
  - Scan reconstruction smoke test (small dataset)

---

# 13) Security/Compliance Checklist

## 13.1 Identity, Auth, and RBAC

### Must-have (MVP)
- **OIDC-based authentication**; short-lived access tokens.
- **RBAC**:
  - `user` (default)
  - `admin` (internal)
  - (later) `moderator`
- **Tenant isolation** enforced at the query layer (every `project/job/artifact` scoped by `user_id/tenant_id`).

### Later enhancements
- Organization accounts with role delegation.
- SCIM provisioning for enterprise.

## 13.2 Data Protection

### Must-have (MVP)
- **Encryption in transit**: TLS for API, SSE, and internal tool calls.
- **Encryption at rest**:
  - Database encryption (managed service)
  - Object storage SSE (KMS-managed keys)
- **PII minimization**:
  - Only store required user fields.
  - Avoid storing raw prompts/images in logs.

### Later enhancements
- Per-tenant encryption keys.
- Data residency controls.

## 13.3 Secure Uploads and Artifact Handling

### Must-have (MVP)
- **Pre-signed upload URLs** with:
  - Strict content-type
  - Max size
  - Short expiry
  - Object key prefix locked to `{tenant_id}/{job_id}`
- **Malware scanning**:
  - Scan uploaded files before they become eligible for processing steps.
- **File validation**:
  - Reject mismatched content-type vs file signature.
  - Verify checksum.
- **Download URLs**:
  - Time-limited signed URLs only.

### Later enhancements
- DLP scanning (for broader compliance).

## 13.4 Service-to-Service Security

### Must-have (MVP)
- Workers/tools run in isolated containers.
- No public ingress to MCP tool servers; only reachable from orchestrator network.
- Least privilege IAM:
  - API can write metadata but not read all artifacts.
  - Workers can read only job-scoped prefixes.

### Later enhancements
- mTLS between services.
- Workload identity (no static cloud keys).

## 13.5 Audit Logging and Provenance

### Must-have (MVP)
- Audit events captured for:
  - Job submission/resume/cancel
  - Safety decisions (block/review/allow)
  - Attestation acceptance
  - Artifact creation and export
- Retain audit logs (configurable), with immutable append-only storage.

## 13.6 Rate Limiting and Abuse Controls

### Must-have (MVP)
- Rate limits per user/IP for:
  - Upload URL creation
  - Job submission
  - SSE connections
- Quotas (soft limit) on:
  - Artifact storage bytes
  - GPU minutes
  - Jobs/day

## 13.7 Content and IP Safety Controls

### Must-have (MVP)
- **Prompt filtering** blocks trademarked faction names/logos and close variants.
- **Image insignia detection** blocks high-confidence brand marks.
- **User attestations**:
  - Scan workflow: rights/permission + non-prohibited IP
  - Generative workflow: original creation intent
- **User-facing messaging** must state:
  - “Original grimdark sci-fi minis only”
  - No branded replicas

### Later enhancements
- Human moderation console for borderline cases.
- Similarity search against a protected reference set.

## 13.8 Secure Operations

### Must-have (MVP)
- Secrets stored in a managed secrets store.
- Dependency scanning + container image scanning.
- CSP headers for the web app; strict CORS policy.
- Log redaction for tokens, URLs, and sensitive payloads.

---

# 14) Milestones

## 14.1 MVP (4–8 weeks): Relief Pipeline End-to-End + Stub Generative

### Must-have scope
- **Pipeline B (Relief)** end-to-end:
  - Upload 1 image
  - Validate image quality + basic insignia detection
  - Depth estimation (GPU preferred; CPU fallback optional)
  - Relief mesh generation
  - Mesh repair + mm normalization
  - Printability validation (basic thickness + bed fit)
  - Export `FINAL_STL`
  - Viewer preview via `PREVIEW_GLB`
- **Human-in-loop UX**:
  - Crop + depth preview checkpoint
  - “Explain problems” + “Fix issues” actions (at least: repair + scale + base thickness)
- **Safety/IP MVP**:
  - Block obvious trademarked terms in prompts (even if generative is stubbed)
  - Image/logo detection with conservative block
  - Attestation capture for scan (even if scan pipeline not executed)
- **Stub Pipeline C (Generative)**:
  - Prompt wizard + safety filtering + “job state flow”
  - Stubbed `generate_3d` tool returns a placeholder mesh artifact (internal testing) or is disabled behind feature flag
- **Infrastructure**:
  - API + DB + object storage
  - Orchestrator with canonical state machine
  - SSE job progress
  - Basic observability (logs + metrics)

### Acceptance criteria
- A new user can produce a printable relief STL with:
  - `job.state = SUCCEEDED`
  - `FINAL_STL` downloadable
  - At least one validation report stored and visible
- Safety blocks trigger `ACTION_REQUIRED/SAFETY_IP_BLOCK` with a clear, actionable explanation.

### Explicitly out of scope (MVP)
- Full photogrammetry/NeRF reconstruction.
- High-quality generative minis.
- Advanced mesh editing.
- Freeform sculpting.
- Topology painting / retopology UI.
- UV editing.
- Texture painting.
- Material authoring/shader graph.
- Rigging and animation.
- Multi-part model splitting and keyed connectors.
- Manual support editing (only auto-support generation is allowed if supports are in scope).

## 14.2 v1 (8–16 weeks): Full Scan Pipeline + Printability Automation

### Must-have scope
- **Pipeline A (Scan)**:
  - Photo analysis + coverage visualization
  - Reconstruction (photogrammetry recommended baseline)
  - Optional masking step
  - Mesh cleanup/repair
  - Scale normalization with mini presets
- **Printability automation**:
  - Robust thickness/overhang/islands detection
  - Resin hollowing + drain holes (resin profiles)
  - Support generation integration
- **Reliability**:
  - Retries, idempotency, cancellation hardened
  - Partial artifact retention and clear failure diagnostics
- **Safety/IP v1**:
  - Improved logo detection
  - Expanded trademark dictionary + fuzzy matching hardening
  - Attestation enforcement end-to-end

### Acceptance criteria
- Scan jobs reliably reach `REVIEW_REQUIRED` with a preview mesh and can be iterated to `SUCCEEDED`.
- “Fix issues” actions resolve common print failures without leaving the UI.

## 14.3 v2 (16+ weeks): Higher Quality Generative Minis + Advanced Editing

### Must-have scope
- **Pipeline C (Generative)**:
  - Production-grade `generate_3d` with variation selection + iterative refinement
  - Stronger printability-aware generation or post-processing
- **Advanced editing**:
  - Basic cut/merge operations
  - Boolean union for base attachment
  - Region thickening tools
- **Quality + safety**:
  - Similarity checks / moderation workflow (where appropriate)
  - Expanded adversarial testing and monitoring

### Acceptance criteria
- Users can iteratively refine an original grimdark sci-fi mini and obtain a validated printable STL with supports in a guided flow.

---

## Status
- **Specification completion**: Deliverables **#1–#14** are now included in this document.
- **Recommended next step**: Implement **Milestone 14.1 (MVP)** end-to-end for the relief pipeline, with feature flags for scan and generative.
