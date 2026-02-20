# Reflection — Zara Ahmed (Junior Software Engineer)

## Thinking
I’ve been diving into the "Cost-to-Serve" model and the latency benchmarking Maya assigned. It’s clear that while the LLM is the "brain," the infrastructure costs and retrieval speeds are the actual skeleton of this project. If the skeleton is too heavy or too slow, the brain doesn't matter. I’m seeing a lot of dependencies between what James (Research) picks for models and what I have to calculate for storage and compute. I need to make sure my math accounts for the "hidden" costs like re-indexing on every document update, not just the initial load.

## Action

### 1. Salient Questions
*   **The "Update Tax":** We’re focusing on the cost of 1M vectors, but what is the average churn rate of our documents? If our legacy DB has high write-volume, the cost of re-embedding and re-indexing via CDC (Change Data Capture) might actually dwarf the initial ingestion cost. Are we modeling for a static library or a living ecosystem?
*   **Metadata Overhead:** Maya mentioned that filtering by ACLs (Access Control Lists) is a "latency trap." Does the Vector DB we choose handle "pre-filtering" vs. "post-filtering" efficiently? If we have to filter 1M results down to 10 based on permissions *after* the vector search, the performance will tank. Should we be looking at "Integrated Filtering" as a hard requirement for the DB shortlist?

### 2. Insights
*   **Dimensionality is the Primary Cost Driver:** After spiking on some initial numbers, it’s obvious that the jump from 768 to 1536 dimensions (e.g., switching from a lightweight local model to OpenAI’s large model) doesn't just double the storage—it ripples through memory requirements and increases the latency of every single similarity calculation. The "Research" decision on models is actually a "Budget" decision.
*   **The Latency Gap:** Our current keyword search is the "competitor." If I find that our legacy clusters are hitting sub-100ms, and the RAG pipeline is hitting 2s, no amount of "semantic relevance" will save the user experience. We aren't just competing with other AI; we're competing with the "fast enough" status quo.
*   **Permission Sync is a Security Debt:** If we don't solve the "Stale Index" problem Maya pointed out, we’re essentially building a tool that could accidentally leak sensitive HR or Legal docs just because a "Revoke Access" command took 5 minutes to propagate to the vector space.

### 3. Self-Assessment
*   **What went well:** I didn't wait for the final specs from James or Alex. I built a modular spreadsheet where I can just plug in "Dimensions," "Token Price," and "Document Count" to see the bottom line instantly. It’s ready for their data.
*   **What could be improved:** I should have reached out to Marcus earlier to see how he’s structuring the metadata for the PoC. If my cost model assumes simple metadata but he’s planning on storing entire permission trees, my storage estimates will be way off.
*   **Confidence Rating:** **Medium.** My logic for the cost calculator is solid, but until I get the hard numbers on document growth from Alex, the "Total Cost of Ownership" is still just a range.

## Cross-Department Requests
CROSS_DEPT_REQUEST: [Dr. James Okafor] - Do you have a preliminary preference for model dimensionality? Even a range (e.g., "definitely under 1024") would help me narrow down the RAM requirements for the self-hosting cost estimate.

CROSS_DEPT_REQUEST: [Alex Kim] - What’s the expected "Update Frequency" for the MVP documents? Are these static archives or docs that get edited daily? This changes the embedding API cost significantly.

## Status
- **Cost-to-Serve Calculator:** v0.1 Template complete with placeholder variables.
- **Latency Baseline:** Initial queries against Cluster A completed; Cluster B and C scheduled for tomorrow.
- **API Research:** Rate limit docs for OpenAI, Cohere, and Voyage AI compiled.
- **Next Step:** I'll spike on a script to automate the latency tests across the remaining clusters so I can get a cleaner average. 

Ready for review — let me know!