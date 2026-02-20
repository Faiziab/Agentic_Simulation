# Research Department Output

**Lead:** Dr. James Okafor

## Thinking

The preliminary work submitted by Dr. Sharma and Mr. Park is quite rigorous and aligns well with the methodological standards I expect within this division. Dr. Sharma’s focus on "noisy" data—specifically simulated OCR degradation and semantic collisions—is particularly commendable. The literature on RAG systems, notably recent benchmarks like the RGB (Retrieval-Augmented Generation Benchmark), suggests that model performance often degrades significantly when faced with irrelevant or "distractor" documents. Her plan to use bootstrap sampling to provide 95% confidence intervals for RAGAS metrics is a necessary step to ensure our findings are statistically significant and not merely stochastic noise.

Mr. Park has correctly identified the "flattening" risk inherent in vector databases. His analysis of permission-aware search strategies is thorough for a junior analyst. I agree with his preliminary recommendation of Metadata Pre-Filtering. The "Empty Result" risk he identified in Post-Retrieval Filtering is a known phenomenon in high-security environments where the intersection of "relevant" and "authorized" documents may be a null set at low $K$ values. I will advise him to proceed with "Hard Enforcement" exclusively; in an enterprise context, "Soft Enforcement" (relying on the LLM to filter) introduces an unacceptable risk of prompt injection or latent space leakage.

One area that requires further scrutiny is the trade-off between Dr. Sharma's "Configuration C" (Domain-Adapted LoRA) and the latency constraints likely to be imposed by Engineering. While a fine-tuned model and a Cross-Encoder re-ranker will undoubtedly improve Precision@K, they introduce significant computational overhead. We must determine if the marginal gain in "Faithfulness" justifies the increased cost-to-serve.

## Action

### Memorandum: Consolidated Research Findings on AI-Powered Enterprise Search (Discovery Phase)

**To:** Dr. Sarah Chen, VP of Research & Development  
**From:** Dr. James Okafor, Research Lead  
**Date:** October 27, 2023  
**Subject:** Technical Evaluation of RAG Architectures and Security-Aware Retrieval

#### 1. Executive Summary
The Research Division has completed its initial assessment of Retrieval-Augmented Generation (RAG) frameworks and permission-aware indexing strategies. The evidence suggests that while semantic search offers a transformative leap over keyword-based systems, its implementation in an enterprise environment is constrained by two primary factors: document "noise" (OCR errors/contradictions) and the preservation of complex Access Control Lists (ACLs). We have developed a benchmarking protocol to evaluate these variables and identified Metadata Pre-Filtering as the most viable path for secure retrieval.

#### 2. Key Findings & Analysis

**A. Benchmarking Framework and Robustness (Lead: Dr. Priya Sharma)**  
The literature suggests that "laboratory" accuracy of LLMs rarely translates to enterprise environments due to suboptimal document quality. Our proposed framework (v1.0) will evaluate three configurations—ranging from proprietary (GPT-4o) to domain-adapted open-source (Llama-3-70B with LoRA)—against a "Noisy" dataset. We are prioritizing metrics such as "Faithfulness" and "Context Precision" via the RAGAS framework. It is worth noting that we are introducing "Contradiction Injection" into our tests to evaluate the model's ability to prioritize temporal metadata (e.g., a 2023 policy vs. a 2019 policy).  
*Confidence Level: High (Methodology is robust).*

**B. Permission-Aware Vector Search (Lead: Tom Park)**  
The integration of AI search must not bypass existing security hierarchies. Our review of retrieval strategies indicates that **Metadata Pre-Filtering** is the most effective method for "Hard Enforcement." This approach utilizes bitmasking during the Approximate Nearest Neighbor (ANN) search to ensure that unauthorized document vectors are never even considered for retrieval. This mitigates the "inference-based leakage" risks associated with post-retrieval filtering.  
*Confidence Level: Medium-High (Pending confirmation of TechNova's ACL cardinality).*

#### 3. Formal Recommendations

1.  **Standardize on Hard Enforcement:** We should formally reject "Soft Enforcement" or LLM-based filtering for security. All document permissions must be enforced at the database level before data reaches the LLM.
2.  **Hybrid Search Evaluation:** I recommend we investigate a "Hybrid" approach (BM25 keyword search + Vector embeddings). The literature frequently indicates that for technical documentation with specific nomenclature, hybrid systems outperform pure semantic search in "Hit Rate @ 1" metrics.
3.  **Cross-Encoder Implementation:** For the first iteration, we should include a Cross-Encoder re-ranking step. Although it increases latency, it is the most reliable way to mitigate the "Empty Result" risk in filtered searches by ensuring the most relevant authorized documents are prioritized.

#### 4. Risks & Caveats

*   **The "Golden Dataset" Dependency:** Our benchmarks are only as good as the ground truth provided by Product. If the dataset lacks high-cardinality edge cases, our findings may be overly optimistic.
*   **Index Sprawl:** While Metadata Pre-Filtering is scalable, extremely high-cardinality metadata (e.g., unique permissions for thousands of users on a single document) can lead to performance degradation in the vector DB.
*   **Hallucination in "Noise":** There is a low-to-medium risk that high OCR error rates will cause the embedding models to cluster documents incorrectly, leading to "semantic drift."

***

### Guidance to Team Members

**To Dr. Priya Sharma:** 
Interesting—the inclusion of "Formatting Entropy" as a treatment is an excellent addition. I would like you to specifically monitor the delta between Configuration A and B when processing the "Contradiction Injection" samples. I suspect the proprietary model may have better inherent reasoning for temporal metadata, but I would prefer to see the data. Please ensure the bootstrap sampling accounts for the variance in the "LLM-as-a-judge" evaluator.

**To Tom Park:** 
Your technical brief is well-structured. Regarding your question on "Hard" vs "Soft" enforcement: We will proceed exclusively with **Hard Enforcement**. TechNova’s "Triad of Trust" cannot rely on the probabilistic nature of an LLM for security. Please dive deeper into the bitmasking performance of Milvus vs. Weaviate, specifically looking for benchmarks involving "High Cardinality" metadata (e.g., thousands of distinct ACL tags).

## Cross-Department Requests

**CROSS_DEPT_REQUEST: [alex_kim]** - We require the "Golden Dataset" (50-100 triplets) by EOW to begin benchmarking. This must include metadata for "document date" and "security clearance" to test our temporal reasoning and ACL filtering. Also, will the dataset include "negative permissions" (specifically excluded users)?

**CROSS_DEPT_REQUEST: [maya_rodriguez]** - I need clarity on the existing ACL structure. Is it primarily RBAC (Role-Based) or ABAC (Attribute-Based)? The metadata overhead for our "Pre-Filtering" strategy is highly dependent on whether we are indexing "Roles" or "Individual User IDs." Additionally, what is our "p99" latency budget for the retrieval step?

## Status

The Research Division has finalized the experimental design and the security architecture brief. We have moved from the "Interpretation" phase to "Initial Benchmarking Setup." 
**Pending:** Acquisition of the Golden Dataset from Alex Kim and ACL schema details from Maya Rodriguez to initiate the first simulation run.

**Current Confidence in Project Feasibility:** Medium-High. The technical path is clear, but the performance-to-security trade-off remains the primary variable to solve.