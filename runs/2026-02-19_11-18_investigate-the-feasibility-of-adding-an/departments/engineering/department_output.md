# Engineering Department Output

**Lead:** Maya Rodriguez

## Thinking
The discovery phase is yielding some cold, hard truths. Marcus and Zara have done the legwork, and the results confirm my suspicion: the "AI" part is easy; the "Enterprise" part is where the wheels fall off. 

Marcus's CDC (Change Data Capture) pipeline is the only way to handle our legacy sync without it being a manual disaster, but that 2-second lag is a compliance liability unless we build a tombstone cache. His "Late-Binding" permission strategy is clever, but Alex’s revelation about 2,500+ individual ACL entries per document is a performance grenade. If we try to shove 3,000 IDs into a metadata filter for every query, the vector DB will crawl. We need a hybrid approach: pre-filter by Group/Project ID and post-filter the top 100 results against a hot-cache of individual user ACLs.

Zara’s baseline of 615ms for current search is our target. If our "smart" search takes 5 seconds, it’s not a feature; it’s a frustration. Her cost model shows SaaS is viable for a 1M doc MVP, but at 100M docs, we’re looking at a massive "SaaS tax." 

I'm pushing back on Tier 3 (multi-doc synthesis) for the initial rollout. It’s a latency nightmare (8-12s). We build Tier 1 (Semantic Search) first, validate the plumbing, then move up.

## Action

### Engineering Department Discovery Report: AI Search Integration
**To:** Dr. Sarah Chen, VP of R&D
**From:** Maya Rodriguez, Engineering Lead
**Status:** Feasibility Assessment (Discovery Phase)

#### 1. Key Findings
*   **Current Baseline:** Our existing search p90 is **615ms**. Any AI solution that exceeds 2 seconds for retrieval will likely face low user adoption.
*   **The "Legacy Tax":** Permission checks are the primary bottleneck. We have documents with up to **2,500 individual ACL entries**. Filtering these in the vector database metadata layer will cause significant latency spikes.
*   **Cost vs. Scale:** At 1M documents, Pinecone (SaaS) is ~$211/mo. At 100M documents, hardware/SaaS costs scale linearly, making self-hosted Milvus on K8s the only long-term path to maintain margins.
*   **Sync Accuracy:** Manual indexing is a non-starter. A CDC (Change Data Capture) pipeline is required to prevent "stale" indices, though it introduces a ~2s consistency lag.

#### 2. Proposed System Architecture (MVP)

```text
[ Document Store ] --> [ CDC Listener (Debezium) ] --> [ Kafka ]
                                                          |
    +-----------------------------------------------------+
    v
[ Indexer Service ] 
    |-- 1. Chunking
    |-- 2. Embedding (Research's Model)
    |-- 3. Metadata Tagging (Project_IDs + Group_IDs)
    v
[ Vector DB (Pinecone w/ Milvus Wrapper) ]
    ^
    | (Query Time)
[ Search API ] <--> [ Auth Cache (Redis) ]
    |-- 1. Fetch User's Project/Group IDs
    |-- 2. Pre-filter Vector Search (Top 100)
    |-- 3. Post-filter individual User ACLs
    |-- 4. Re-rank & Return
```

#### 3. Recommendations
*   **Start with "Vector DB Agnostic" Wrapper:** Use Pinecone for the PoC to move fast, but write the interface for Milvus. We will need to move in-house once we hit the 10M document mark to control costs.
*   **Hybrid Permission Filtering:** Do not index individual user IDs. Index Group/Project UUIDs. Perform a "Late-Binding" check against the top 100 candidates to handle individual user permissions. This protects performance while maintaining SOC2 compliance.
*   **Tier 1 MVP:** Focus exclusively on Semantic Search. Multi-doc synthesis (Tier 3) should be deferred until we have a streaming-compatible UI and stabilized retrieval latency.
*   **Implement a "Tombstone" Cache:** To bridge the 2s CDC lag, we need a fast-access Redis store that marks recently deleted documents/revoked permissions to prevent the AI from returning unauthorized snippets.

#### 4. Risks & Concerns
*   **Metadata Bloat:** If Alex's requirement for 3,000 ACLs grows, the index size will explode. We must enforce a "Group-First" permission policy for AI-indexed folders.
*   **The Hallucination Floor:** Engineering can deliver the document, but if the LLM hallucinates the summary, the system is untrustworthy. We need James’s "Golden Dataset" results to quantify this risk.
*   **GPU Availability:** If we go self-hosted for embeddings (Milvus + Llama), we need guaranteed access to AWS `g4dn` or `p3` instances.

#### 5. Team Review
*   **Marcus Webb:** Strong architectural foundation. The CDC strategy is the right call for reliability. *Next step: Build the Dockerized Milvus PoC to test the 3,000 ACL metadata filter performance.*
*   **Zara Ahmed:** Good baseline metrics. The cost model needs a "Scale-out" tab for 10M and 100M documents. *Next step: Automate the cost comparison script to include token-pricing for Voyage AI and Cohere.*

## Cross-Department Requests
TARGET_AGENT: dr_james_okafor | REQUEST: I need the embedding dimensionality (e.g., 768 vs 1536) by EOD Friday. Zara cannot finalize the "Scale-out" cost model without this, as it dictates our RAM requirements.

TARGET_AGENT: alex_kim | REQUEST: Can we mandate that documents indexed for AI search *must* use Group-based permissions rather than individual User ACLs? Reducing that 2,500-entry list to 5-10 Group IDs would drop our retrieval latency by ~300ms.

TARGET_AGENT: dr_sarah_chen | REQUEST: Requesting a decision on "Tier 1" vs "Tier 3" for the MVP. Engineering recommends Tier 1 (Semantic Search) to ensure we hit the <2s latency target. Tier 3 (Synthesis) is currently an 8-12s operation.

## Status
Engineering has completed the initial infrastructure and cost discovery. We have a clear path for the MVP (Pinecone + CDC Pipeline) and a scale-out plan (Milvus). 
*   **Pending:** Embedding dimensions from Research; Permission policy decision from Product.
*   **Next Step:** Marcus is spinning up a performance test to see exactly how badly 3,000 metadata filters hit Vector DB latency.