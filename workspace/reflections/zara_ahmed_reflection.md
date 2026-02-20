# Reflection — Zara Ahmed (Junior Software Engineer)

## Thinking
I’ve been diving into the "Cost-to-Serve" task Maya assigned. The 10-million-document scale is the real kicker here. It’s not just a one-time API hit; it’s a massive upfront indexing cost followed by recurring "Day 2" re-indexing risks. I’ve started a Python script to model this because a static spreadsheet will break the moment OpenAI or Anthropic changes their pricing. 

I’m realizing that the "accuracy" side of the matrix is totally dependent on what Dr. Okafor finds in his benchmarks, and the "storage" side depends on the vector dimensions. I’m currently blocked on the exact math until I get those specs, but I can already see that the delta between self-hosting (EC2 + Llama) and using an API (OpenAI) is going to be the biggest decision point for the budget.

## Action

### 1. Salient Questions
*   **What is our average "Chunk-to-Document" ratio?** 10 million documents could mean 50 million or 500 million vector embeddings depending on our chunking strategy (e.g., 500-token overlaps). This multiplier is the single biggest variable in our Vector DB storage costs.
*   **Can we support "Tiered Search"?** Does every document need to be indexed in a high-performance/high-cost vector store like Pinecone, or can we move older/less-accessed docs to a cheaper "cold" storage (like pgvector on a standard RDS) to save on the 10M doc overhead?
*   **Challenge:** We are assuming we need a "Golden Model" for everything. Should we be looking at a "Small Model" for embedding/retrieval and only using the "Expensive Model" for the final synthesis?

### 2. Insights
*   **The "Architectural Tax":** In traditional dev, architecture affects performance. In AI search, architecture *is* the budget. Choosing a 1536-dimension model over a 768-dimension one literally doubles our storage bill before we even write a line of code.
*   **Maintenance > Implementation:** The "Day 2" problem isn't just a risk; it's the primary cost driver. If we re-index twice a year as Maya suggested, the maintenance cost of this feature will likely exceed the initial R&D spend within 18 months. We need to build the "Blue/Green" indexing pipeline as a core feature, not an afterthought.
*   **The Dependency Bottleneck:** There’s a tight loop between James (Model choice), Alex (User latency), and my cost model. If Alex demands <500ms latency, we might be forced into expensive provisioned throughput, which kills our margins on the 10M doc corpus.

### 3. Self-Assessment
*   **What went well:** I’ve already started a Python-based cost simulator. It’s much faster to iterate on than a spreadsheet and allows me to plug in different API pricing tiers instantly.
*   **Improvement:** I should have reached out to Marcus sooner to see how he's handling multi-tenancy in the DB PoC. If we silo by OrgID at the index level, that might increase our "idle" storage costs compared to a single shared index with metadata filtering.
*   **Confidence Rating:** Medium. The logic of my cost model is solid, but the input variables (token counts, dimensions) are still placeholders.

## Cross-Department Requests
TARGET_AGENT: [Dr. James Okafor] | REQUEST: I need the expected token count per document chunk for your top 3 model candidates. Also, please confirm if the models you're benchmarking use 768, 1024, or 1536 dimensions so I can finalize the Vector DB storage estimates.

TARGET_AGENT: [Marcus Webb] | REQUEST: For the "Data Isolation PoC," are you planning on separate collections per tenant or a shared collection with metadata filters? This significantly changes how I calculate the "base" compute cost vs. "per-document" storage cost.

## Status
**Accomplished:** Created a CLI-based cost simulator prototype; identified chunking ratio as a primary cost multiplier.
**Pending:** Integration of real dimension data from Research; comparison of self-hosted vs. API-based inference costs.

Ready for review — let me know!