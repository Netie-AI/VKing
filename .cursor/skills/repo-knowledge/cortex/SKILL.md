---
name: cortex-repo-knowledge
description: Load-bearing capability card for Cortex — populated by repo-surveyor subagent. What Vking's frozen interfaces (§4.4) need from Cortex.
---

# Cortex — capability card

## 1. What it is

**Netie Cortex OS** (`netie` / `CortexOS` on PyPI metadata) — governed agentic runtime: hybrid retrieval (BM25 + dense + RRF + rerank), tiered LLM routing with cost gating, and DAG execution for multi-step synthesis.

| Field | Value |
|-------|-------|
| **Pinned commit** | `0d41c08423ea7bcca69f2de218ac1e5e176b3840` |
| **Package version** | `0.1.0` (`pyproject.toml`) |
| **License** | Apache-2.0 (`LICENSE`) |

Cortex does **not** implement HDL ingestion, protocol detection, RTL/TB template codegen, sim backends, or Vking gates. Vking uses it for **memory retrieval** (v0.4) and **gated LLM orchestration** (v0.5 cocotb path).

## 2. Entry points → frozen interfaces

| Entry point | Interface | What Vking needs |
|-------------|-----------|------------------|
| `CortexOS.fabrication.skillmesh.SkillMesh.retrieve(intent, top_k=8)` | **IMemoryStore** | In-process two-stage hybrid retrieval (BM25 → `DenseReranker` cosine rerank). Primary v0.4 "SkillMesh reuse" path over verified artifacts wrapped as `SkillCard`s. Returns `Result[list[SkillCard]]`; may set `detail["warning"] = "near_boundary"` and truncate to top 3. |
| `CortexOS.rag.retriever_dense.DenseRetriever.retrieve_dense_query` + `CortexOS.rag.retriever_sparse.SparseRetriever.retrieve_sparse` + `CortexOS.rag.fuser_rrf.fuse_dense_sparse` | **IMemoryStore** | Scaled hybrid retrieval when facts are indexed externally: Qdrant cosine (`BGE-M3` vectors) fused with Postgres FTS via reciprocal rank fusion. Vking must supply its own collection/table schema and provenance payload fields. |
| `CortexOS.rag.reranker.BGEReranker` (`rerank` / cross-encoder scoring) | **IMemoryStore** | Optional third stage after RRF — `BAAI/bge-reranker-v2-m3` cross-encoder rerank with asyncio semaphore serialization. |
| `CortexOS.execution.executor.invoke_routed_completion` | **ITBGenerator** | Pre-call cost-ceiling gate + tier-routed LLM adapter invocation + post-call ledger write. Pattern for v0.5 cocotb-Python generation: retrieve verified context → prompt → validate output → bounded repair. Cost accounting in MYR via `CostLedger`. |
| `CortexOS.execution.dag_runner` (+ `fabrication.dsl_parser.parse_dsl`, `fabrication.hls_compiler.HLSCompiler.synthesize` as reference flow) | **ITBGenerator** | Multi-step LLM workflow execution: DAG nodes with `{upstream}` prompt templating, tier bounds, and schema-validated JSON output with ≤2 retry on parse failure. Mirrors v0.5 self-consistency / repair loop without owning Vking's cocotb schema. |

## 3. Quirks / flags / gotchas

- **Import alias:** `netie.*` resolves to `CortexOS.*` via a `sys.meta_path` finder (`netie/__init__.py`). Either name works; pick one convention in Vking adapters and stick to it.
- **Two retrieval stacks, different embedders:** `SkillMesh` defaults to `all-MiniLM-L6-v2` (in-process); the RAG pipeline uses `BAAI/bge-m3` (Qdrant) + Postgres FTS + `bge-reranker-v2-m3`. Do not mix indices or embedders without full reindex.
- **No SQLite storage in CortexOS:** Cortex supplies retrieval *algorithms*, not Vking's `facts`/`runs` SQLite schema. Vking owns `IMemoryStore.write_fact()` and single-write-path enforcement; Cortex code must not bypass it.
- **No provenance-level filtering built in:** `SkillMesh` and RAG retrievers rank by relevance only. Vking §8 requires L3+ filtering at query time — wrap retrieval calls and filter on `provenance_level` in payload before few-shot slots.
- **SparseRetriever is Postgres-locked:** SQL targets a `listings` table with `fts_doc`/`plainto_tsquery('simple', …)`. Vking must fork SQL or parameterize table/column names; cannot drop in as-is.
- **Optional extras are hard deps for full RAG:** `qdrant-client` (`[rag]` extra), `sqlalchemy[asyncio]` + `asyncpg` (`[postgres]` extra), `tiktoken` (`[tokens]` extra for `HLSCompiler` token budgeting). Missing extras fail at import/runtime, not gracefully degrade.
- **Async-only hot paths:** `DenseRetriever`, `SparseRetriever`, `invoke_routed_completion`, and `dag_runner` are `async`. Vking CLI/UI bridge needs an asyncio runner or a thin sync wrapper.
- **Config surface:** `~/.netie/config.toml` overridden by `NETIE_*` env vars (`NETIE_DATABASE_URL`, `NETIE_QDRANT_URL`, `NETIE_EMBEDDER_MODEL`, `NETIE_API_KEY`, `PACK`, etc.). No `vking.toml` integration — adapter must translate.
- **SkillMesh input model:** BM25 corpus is `SkillCard` name + description + `example_intents`, not arbitrary text chunks. Vking must project verified TB/RTL artifacts into cards or build a parallel BM25 corpus adapter.
- **Bounded retry, not open-loop repair:** `HLSCompiler.synthesize` retries once on DSL parse failure; `SkillMesh` near-boundary truncates to 3 cards. Vking's ≤3 repair loop must be implemented above Cortex, feeding specific gate failures back as prompts.
- **Cost ledger expects Postgres:** `CostLedger` persists `NodeExecutionRecord` to Postgres when `database_url` is set; raises `CostCeilingExceeded` before the LLM call. Headless CI must either stub the ledger or provide a DSN.
- **Vertical-pack baggage:** Default `pack=ruma`; DMS routes (`packs.dms.plug_in`) are warehouse/chat-specific. Vking should import `CortexOS.fabrication` / `CortexOS.rag` / `CortexOS.execution` directly — not mount DMS FastAPI routes for IUIRenderer.
- **WASM sandbox (F8) not production-ready:** `execution.wasm_isolate` exists but STATUS.md marks F8 tool-call execution as "packet on rail" — do not depend on sandboxed code execution yet.
