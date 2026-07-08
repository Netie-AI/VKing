---
name: lightma-repo-knowledge
description: Load-bearing capability card for lightma — populated by repo-surveyor subagent. What Vking's frozen interfaces (§4.4) need from lightma.
---

# lightma — capability card

## What it is

**LightMa** (Light Manifold Architecture) is a Python research prototype for **sparse knowledge-graph retrieval** via spreading activation (PPR / heat-kernel / one-hop), not a trained LLM. It replaces transformer attention with a 4D manifold stack (`TrifoldStack`) plus a **Visual Core** graph (`VisualCoreGraph`) where concepts are hash-embedded nodes with `truth_score`, typed edges, and graph propagation.

Vking references it at **v0.6 / S6**: a LightMa-style graph may replace YAML signature tables for `IProtocolDetector` **only when** Vking's own confirmed-module corpus is ≥ ~50 and the graph beats tables on a held-out split (§5, §13 S6). Until then, Vking uses SQLite + signature tables; LightMa is not on the critical path for v0.1–v0.5.

**Package version:** `0.1.0` (`lightma/__init__.py`).

**Pinned commit:** **Unknown** — `repos/lightma/` is not a git checkout (no `.git`, no remote). Record a commit hash when the repo is properly vendored or submoduled.

**License:** **None found** — no `LICENSE`, `README`, `pyproject.toml`, or copyright headers in the tree. Treat redistribution terms as unset until upstream metadata is added.

**Dependencies (observed):** `numpy` required everywhere; optional `onnxruntime-directml`, `openvino` for GPU/NPU paths (`runtime/device.py`). No requirements file in tree.

---

## Load-bearing entry points (§4.4)

Only what Vking's frozen interfaces need. Ignore web UI (`web/`), evolution (`evolve/`), lottery (`lottery/`), and text generation unless explicitly extending beyond protocol detection.

### 1. `LightMaModel.absorb()` — ingest verified facts (`IMemoryStore` / graph build)

**Path:** `repos/lightma/model.py` → delegates to `VisualCoreGraph.absorb()`.

**Contract:** `absorb(entries: list[dict], min_truth: float = 0.7) -> int`

Each entry:

```python
{
    "label": str,           # stable concept id (e.g. "axi4_lite_aw_channel")
    "text": str,            # free-text description / signal names
    "truth": float,         # 0–1; entries below min_truth are skipped
    "core": bool,           # default True; core_only graph down-weights non-core
    "links": [              # optional typed edges
        {"to": "<label>", "weight": float, "type": "bridge|causes|domain|..."}
    ],
}
```

**Vking mapping:** After human confirmation + conformance gate, map `L4+` protocol facts from `IMemoryStore` into absorb entries. `truth` should reflect provenance (not raw detection confidence). Vking's single write path still applies — LightMa is a **read/retrieve backend**, not a bypass for provenance rules.

### 2. `LightMaModel.retrieve_bridges()` — graded concept retrieval (`IProtocolDetector` v0.6)

**Path:** `repos/lightma/model.py` → `VisualCoreGraph.activate_subgraph()`.

**Contract:** `retrieve_bridges(query: str, top_k: int = 12) -> list[dict]`

Returns activated concept labels with scores — **gradeable set output**, not prose. Each hit includes `label`, `score`, `ppr`, `direct_sim`, `bridge_gain`, `novel` (whether label tokens overlap query).

**Vking mapping:** Given module port/signal context as `query`, surface top protocol concept labels; compare against signature-table candidates. Ship only if held-out F1 beats the table baseline (§5 KG upgrade criteria).

**Tunable via `LightMaConfig`:** `kernel` (`cosine|onehop|ppr|heat`), `spread_hops`, `ppr_restart`, `hub_penalty`, `graph_nodes`, `hidden_dim`.

### 3. `run_bridge_benchmark()` + `bridge_fitness()` — ship gate for graph vs baseline

**Path:** `repos/lightma/bench/bridge_rigorous.py`; exported from `lightma.bench`.

**Contract:**

- `run_bridge_benchmark(domain="semiconductor", top_k=5, config=None, query_subset="all|train|test") -> BridgeBenchReport`
- `bridge_fitness(report, precision_floor=0.20) -> float` — F1-primary, precision floor anti-recall-spam, latency penalty, bonus if `beats_dense_on_f1`.

Compares LightMa propagation vs **dense hash-cosine** on held-out bridge queries. Win condition: higher mean F1 than dense baseline.

**Vking mapping:** Adapt the benchmark pattern for a Vking-specific domain (`bench/domains/semiconductor.py` is the only domain today): absorb corpus + held-out queries where expected labels are never in the query text. Use train/test split discipline from `lottery/engine.py` (select on train, report on test).

### 4. `VisualCoreGraph.save()` / `load()` — graph persistence (`IMemoryStore` backing store)

**Path:** `repos/lightma/memory/visual_core.py` (also `LightMaModel.save()`/`load()` bundles graph + manifold stack).

**Contract:** NPZ + sidecar JSON for edges/metadata. Only nodes with `truth_score > 0` participate in propagation (`_build_transition` builds matrix over active subgraph only).

**Vking mapping:** Optional serialized KG snapshot alongside SQLite facts; SQLite remains source of truth for provenance levels — graph is derived/index materialization.

### 5. Absorb corpus + held-out query schema — Vking training data shape

**Path:** `repos/lightma/bench/domains/semiconductor.py` (`SEMICONDUCTOR_ABSORB`, `SEMICONDUCTOR_HELD_OUT`).

**Contract:** `BridgeQuery(id, query, expected_bridges: list[str], notes)` — queries deliberately avoid naming expected bridge labels.

**Vking mapping:** Template for how to structure Vking's labeled protocol-module corpus (~50+ confirmed modules) for evaluation. Replace semiconductor concepts with protocol/signal-group labels derived from verified manifests.

---

## Quirks / gotchas

1. **Not an LLM.** Embeddings are deterministic bag-of-words over `stable_hash(token) % hidden_dim` — no external embedding model. Retrieval quality depends on label/text token overlap and explicit `links`, not semantic similarity. Do not expect ChatGPT-class ambiguity resolution.

2. **`kernel="cosine"` equals flat dense retrieval.** Graph propagation advantage requires `ppr`, `heat`, or `onehop` with meaningful typed `bridge` edges. Default config uses `kernel="ppr"`.

3. **Truth gating is load-bearing.** Nodes with `truth_score == 0` are excluded from the active subgraph. Absorb must set truth from Vking provenance; unverified facts must not enter the graph as high-truth nodes.

4. **Tiny benchmark today.** Semiconductor held-out set is **8 queries**; `bridge_rigorous.py` and `lottery/engine.py` explicitly warn to interpret summaries cautiously. Vking needs its own held-out set at ≥50 modules before S6.

5. **Single domain only.** `run_bridge_benchmark()` raises on unknown `domain`. Vking must add a `domains/vking_protocol.py` (or similar) — do not assume semiconductor transfers.

6. **No packaging metadata.** No README, LICENSE, requirements, or git pin in `repos/lightma/`. Import as a path dependency or install manually; pin commit + license before production reuse.

7. **Reproducibility:** Use `stable_hash()` (BLAKE2b), not Python `hash()` — built-in hash is salted per process (`visual_core.py`).

8. **Out of scope for Vking interfaces:** `web/server.py` (Deep Sea forum UI), `evolve/`, `lottery/`, `generate()`, SEA-LION API benchmarks — interesting for LightMa research, not load-bearing for `IProtocolDetector` / `IMemoryStore` integration.

9. **`KnowledgeGraph` vs `VisualCoreGraph`:** Legacy `memory/knowledge_graph.py` lacks truth scores, PPR kernels, and bridge grading. Vking should use **`VisualCoreGraph` only** via `LightMaModel`.

10. **CLI fragility:** `cli.py` references `run_intelligence_benchmark` / `save_benchmark_baseline` in `cmd_bench_intelligence` without importing them — `bench-intelligence` subcommand will fail; use `bench-bridge` for the rigorous path.

---

## Vking interface map (quick reference)

| Vking interface | LightMa surface | Vking version |
|-----------------|-----------------|---------------|
| `IProtocolDetector` | `retrieve_bridges()` + custom domain benchmark | v0.6 (S6), fallback to YAML tables |
| `IMemoryStore` | `absorb()` ingest + graph `save`/`load` as derived index; SQLite stays canonical | v0.4+ hybrid retrieval; graph optional until S6 |
| `IGateRunner` | Adapt `run_bridge_benchmark()` pattern as offline eval gate | S6 entry criterion |

**Do not wire LightMa into:** `IHdlFrontend`, `ITBGenerator`, `IRtlGenerator`, `ISimBackend`, `IUIRenderer` — no load-bearing hooks exist.
