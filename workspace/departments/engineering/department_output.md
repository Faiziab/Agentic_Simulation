# Engineering Department Output

**Lead:** Maya Rodriguez

## Thinking
The team has done a solid job identifying the "Day 2" problem, which is where most AI projects at this scale go to die. Marcus is thinking correctly about the data pipeline—using Kafka for CDC (Change Data Capture) is the only way to keep this from becoming a manual maintenance nightmare. Zara’s cost analysis is the real wake-up call; a $400,000 re-indexing bill for a $5,000 query load is a catastrophic architectural failure. We are not doing that.

**Review of Marcus’s Deliverable:**
*   **Strong:** The decoupling of the Vector DB as a "Search Index" rather than a primary store is the right move. His focus on the "Zero-leakage test" is exactly the kind of engineering rigor we need.
*   **Improvement:** I’m skeptical of Milvus for the PoC. It’s powerful, but the operational overhead (K8s, monitoring, specialized knowledge) is high. I want to see a "pgvector-first" mindset unless the performance benchmarks prove it's a bottleneck at 10M docs. We build for the 1x scenario first, then scale to 10x.

**Review of Zara’s Deliverable:**
*   **Strong:** Excellent catch on the re-indexing cost disparity. The 20x cost difference between API and self-hosted embeddings makes the decision for us.
*   **Improvement:** The "Self-Hosted" cost of <$500 is just the electricity and silicon. She needs to factor in the "Engineering Tax"—the cost of Marcus and her spending time managing that infrastructure.

**Synthesis:**
We are moving toward a hybrid architecture: Self-hosted embeddings (to save $400k/year) and API-based LLMs (to keep accuracy high). The biggest hurdle is the Vector DB selection and ensuring multi-tenancy doesn't leak data.

## Action

### TO: Dr. Sarah Chen (VP of R&D)
### FROM: Maya Rodriguez (Engineering Lead)
### SUBJECT: Engineering Assessment: AI-Powered Search Feasibility

**Executive Summary:** It depends on the requirements, but at 10M documents, a pure API-based embedding strategy is financially irresponsible. We are pivoting to a "Self-Hosted Embedding + API-LLM" hybrid model.

---

### 1. Proposed System Architecture (The MVP)
We will treat the Vector DB as a volatile search index. If we need to change models, we re-run the pipeline.

```text
[ Primary Data ] -> [ Kafka ] -> [ Embedding Worker (Self-Hosted) ]
                                      |
                                      v
[ Query Orchestrator ] <------- [ Vector DB (Milvus/pgvector) ]
      |                               |
      +--> [ OrgID Filter Applied ] --+
      |
      v
[ LLM API (GPT-4o-mini/Haiku) ] -> [ User ]
```

### 2. Key Findings
*   **The Re-indexing Trap:** Using OpenAI for embeddings at 10M documents costs ~$200k per re-index. Doing this twice a year wipes out the project’s ROI. Self-hosting the embedding model (e.g., BGE-Base) reduces this to negligible compute costs.
*   **Multi-tenancy:** We will implement **Logical Isolation** (Metadata filtering) as our MVP. Hard isolation (separate collections) will be our fallback if the 200ms latency target isn't met or if Legal mandates it.
*   **Data Pipeline:** We must leverage the existing Kafka backbone. Adding a new "sync" service is scope creep we can't afford.

### 3. Recommendations
*   **Database:** Start PoC with **Milvus** (distributed) but keep a **pgvector** branch for comparison. If Milvus takes more than 3 days to stabilize in dev, we drop it.
*   **Embedding Model:** Self-host the embedding model on EC2/G5 instances. The "Day 2" savings are too large to ignore.
*   **Search Strategy:** Hybrid search (Keyword + Vector) is mandatory. Vector search alone is often "vibes-based" and fails on specific technical terms.

### 4. Risks & Concerns
*   **I/O Bottleneck:** Re-indexing 10M docs will saturate our Kafka bus if not throttled.
*   **Accuracy vs. Dimensions:** If Research pushes for 1536-dimension vectors, our storage and memory costs double instantly.
*   **The "Hallucination" Liability:** Engineering can build the pipes, but we need Research to guarantee a "Grounding" mechanism to prevent the LLM from making up facts from our docs.

---

## Cross-Department Requests
TARGET_AGENT: [Dr. James Okafor] | REQUEST: I need a final decision on the embedding model dimensions (768 vs 1536) and the distance metric (Cosine/L2/Inner Product) by EOD Friday. I cannot finalize the DB schema without this.

TARGET_AGENT: [Alex Kim] | REQUEST: Confirm the maximum allowable latency for a "Search" result. If you need <100ms, we may have to sacrifice the LLM summarization and just provide the links.

## Status
**Accomplished:**
*   Identified $400k/year cost saving by moving to self-hosted embeddings.
*   Defined Kafka-based CDC architecture for document indexing.
*   Established PoC success criteria (200ms latency, zero data leakage).

**Pending:**
*   Final model specs from Research.
*   Actual query volume projections from Product to size the Vector DB cluster.
*   Decision on pgvector vs. Milvus based on initial ingestion benchmarks.