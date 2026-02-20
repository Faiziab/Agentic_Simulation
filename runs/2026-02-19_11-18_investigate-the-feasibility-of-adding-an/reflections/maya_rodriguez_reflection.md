# Reflection — Maya Rodriguez (Engineering Lead)

## Thinking
The discovery phase has moved from "Can we do this?" to "How much will this hurt?" The data from Marcus and Zara, combined with Alex’s confirmation of our mess of a permission structure (2,500 ACL entries per doc), confirms that the AI part is a commodity—the engineering of the data pipeline and the security layer is the actual product.

We are currently at a p90 of 615ms for keyword search. Moving to a RAG (Retrieval-Augmented Generation) model shifts us into a 4-12 second window. That’s not an "improvement" in the traditional sense; it’s a different product category. I need to make sure Dr. Chen and the Board understand that "better" search here comes at a 10x-20x latency penalty.

I'm pushing back on Tier 3 (Multi-doc synthesis) for the MVP. We need to nail the "Trusted Librarian" (Tier 1: Semantic Search) first. If we can't surface the right document securely and quickly, summarizing five wrong documents is just a faster way to be wrong.

## Action: Engineering Department Consolidated Output
**TO:** Dr. Sarah Chen, VP of R&D  
**FROM:** Maya Rodriguez, Engineering Lead  
**SUBJECT:** Technical Feasibility & Discovery Synthesis: Project AI-Search

### 1. Key Findings
*   **The Permission Bottleneck:** Our legacy ACL structure is the primary technical risk. With up to 2,500 individual access entries per document, standard vector database "pre-filtering" will likely degrade performance to unacceptable levels.
*   **Latency Reality Check:** 
    *   Current Baseline: **615ms** (p90).
    *   Projected AI Search (Tier 1): **2-4 seconds**.
    *   Projected AI Synthesis (Tier 3): **8-12 seconds**.
*   **Cost-to-Serve:** Preliminary SaaS-based infrastructure (Pinecone + Embedding APIs) is estimated at **~$211/mo per 1M documents** (excluding LLM generation costs). Self-hosting Milvus would increase operational overhead but stabilize long-term costs.
*   **Infrastructure Strategy:** A CDC (Change Data Capture) pipeline is required to keep the vector index fresh. Manual indexing is a non-starter for production.

### 2. Recommendations
*   **MVP Scope:** Focus exclusively on **Tier 1 (Semantic Search)**. It is the "smallest thing" we can build to validate if users actually value intent-matching over keyword-matching.
*   **Architecture:** 
    *   Use **Pinecone (SaaS)** for the PoC to maximize velocity.
    *   Implement an **Abstraction Wrapper** around the vector DB to allow a "lift and shift" to Milvus if costs scale linearly.
    *   Adopt **Late-Binding Permissions**: Fetch top candidates from the vector DB, then filter against a hot-cache of ACLs in the application layer to prevent "leakage."
*   **UI/UX:** Must support **streaming responses**. A "waiting" spinner for 8 seconds will kill adoption.

### 3. System Architecture (MVP Flow)
```text
[User Query]
    |
    v
[API Gateway] --> [Auth Cache (Redis)] -- (Fetch User ACLs)
    |
    +--> [Embedding API] -- (Convert Query to Vector)
    |
    +--> [Vector DB (Pinecone)] -- (Filtered Query: Find top 50 matches)
    |
    v
[Post-Filter Service] -- (Cross-ref matches with User ACLs)
    |
    v
[LLM (Optional for Tier 1)] -- (Re-rank results)
    |
    v
[User Interface] -- (Streamed results)
```

### 4. Risks & Concerns
*   **The "Legacy Tax":** If our SQL DB/Auth service is slow, the search is slow. We cannot fix search latency without fixing auth latency.
*   **Stale Indexing:** The 2-second CDC lag means a user might briefly see a document they just lost access to. This requires a "Tombstone" cache for high-security docs.
*   **Hallucination Floor:** As Alex noted, we need to define the "I don't know" threshold.

---

## Salient Questions
1. **The "Why" vs. "How":** Are we building "AI Search" because users can't find documents, or because "AI" is a Board requirement? If it's the former, would improving our Elasticsearch indices be 10x cheaper and 2x faster?
2. **The Latency Threshold:** What is the absolute "drop-off" point for our users? If we hit 5 seconds, do they go back to Slack/Teams to ask a human?
3. **Data Residency:** If we use Pinecone/OpenAI, data leaves our VPC. Does this immediately disqualify us for 50% of our Tier 1 enterprise clients?

## Insights
*   **The Permission-Latency Paradox:** The more secure we make the search (by checking complex ACLs), the more we degrade the "magical" speed of AI. We are trading performance for compliance.
*   **The Iceberg Connection:** Marcus (Infra), Zara (Cost), and Alex (Product) are all hitting the same wall: **Permissions.** This is the single most important thread. Our 15 years of legacy data management is our biggest hurdle to modernizing.
*   **MVP Misalignment:** Research is looking at "Multi-doc synthesis" (Tier 3), but Engineering is still trying to figure out how to sync a document (Tier 0). We need to align on the MVP immediately to avoid wasted effort.

## Self-Assessment
*   **What went well:** I’ve successfully steered the team toward "back-of-the-envelope" math and concrete prototypes rather than theoretical whitepapers. Zara and Marcus are focused on the right metrics (p90 latency and cost-per-query).
*   **Improvements:** I need to be more aggressive in telling Product (Alex) "No" on Tier 3 features until we have a working Tier 1 prototype. I've let the discussion drift into synthesis when we haven't even solved retrieval.
*   **Confidence Rating:** **High** on technical feasibility; **Medium** on the cost-to-value ratio for the end user.

---

## Cross-Department Requests
TARGET_AGENT: alex_kim | REQUEST: I need a definitive "No-Go" latency number. If Engineering says we can't get under 3 seconds for a secure query, is the project dead?

TARGET_AGENT: dr_james_okafor | REQUEST: Confirm the minimum dimensionality required for "acceptable" accuracy. If we can drop from 1536 to 768 dims, I can cut our memory footprint in half.

## Status
*   **Consolidated Engineering Report:** Completed (see above).
*   **Team Deliverables:** Reviewed and integrated.
*   **Pending:** Hard latency requirements from Product and dimensionality specs from Research.
*   **Next Step:** Marcus starts the "Smallest Thing" PoC (Local Embeddings -> Dockerized Milvus) to test ACL filtering speeds.