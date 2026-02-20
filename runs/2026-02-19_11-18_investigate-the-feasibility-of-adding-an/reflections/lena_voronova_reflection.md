# Reflection — Lena Voronova (UX Researcher)

## Thinking
As I dive into these assignments from Alex, I’m struck by the weight of the "Trust" factor. In my past research, I’ve seen users abandon entire platforms because of a single "Error 404" at a critical moment. With AI, the risk isn't just a broken link; it's a confident lie. 

I'm thinking about Nielsen’s 1st Heuristic: **Visibility of System Status**. If the AI is "thinking," how do we show that without making the user feel like they're waiting for a slow human? And more importantly, how do we handle the "I don't know" state? A user might say, *"I’d rather the search bar tell me it can’t find the 2024 Vendor terms than have it give me the 2022 terms and tell me they’re current."*

I need to make sure my interviews don't just capture *what* they can't find, but *how it feels* when they can't find it. That's where the "Shadow Workflows" live. If they've given up on search and built their own "Golden Desktop Folders," we've already lost the battle for their primary workspace.

## Action

### 1. Salient Questions
*   **Are we solving for "Finding" or "Understanding"?** We assume users want a summary (Synthesis), but do they? Or do they just want the specific paragraph in a 200-page PDF that mentions "liability limits"? We need to challenge the assumption that a "chat" interface is the right UI for an enterprise search problem.
*   **What is the "Tolerance for Hallucination" in different roles?** A marketing manager might be okay with a slightly creative summary, but a compliance officer has zero margin for error. Should the UI change its "certainty markers" based on who is logged in?
*   **Does the "Shadow Workflow" provide a sense of safety that AI can never replicate?** If a user names a file `CONTRACT_FINAL_USE_THIS_ONE_JAN_23`, they are creating their own source of truth. Can an AI-generated answer ever feel as "safe" as a file the user manually renamed?

### 2. Insights
*   **The "Calling Steve" Pattern:** Across almost all our power users, the ultimate fallback isn't a better search query; it's human-to-human tribal knowledge. This tells me our current search isn't just failing on a technical level; it's failing to provide *authoritative* confidence. Our AI needs to cite its sources as clearly as a legal brief to even begin competing with "Steve."
*   **The Latency-Trust Paradox:** I'm seeing a conflict between Maya’s "Cost-per-Query" and James’s "Accuracy." If we opt for a cheaper, faster model that hallucinates 5% more, we might save money on compute but lose the user's trust forever. In UX terms, **Reliability > Speed** in the enterprise space. A user might say, *"I'll wait 10 seconds for the truth, but I won't spend 1 second on a lie."*
*   **Permissions as a UX Barrier:** If we implement strict permission-aware indexing (as James is researching), we risk creating a "Fragmented Reality." If User A gets a different answer than User B because of permissions, they might think the AI is "broken" when they compare notes. We need a way to communicate "I am only showing you what you have access to" without making it feel like the AI is hiding things.

### 3. Self-Assessment
*   **What went well:** I feel I’ve successfully pivoted the conversation from "features" to "feelings" and "friction." Alex and I are aligned on the idea that this is a trust exercise, not just a tech upgrade.
*   **What to improve:** I need to get closer to Maya. I realized while thinking about the User Journey Maps that I don't actually know if our infrastructure can support the "instant feedback" I want to design. I need to be more technical in my cross-department inquiries to ensure my "ideal" journey is actually buildable.
*   **Confidence Rating:** **Medium-High**. I am very confident in the existence of the "Search Pain," but my confidence in our ability to solve it without breaking the "Trust Gap" is currently moderate until I see James’s hallucination benchmarks.

## Cross-Department Requests
TARGET_AGENT: Maya Rodriguez | REQUEST: I’m starting the User Journey Maps. Can you give me a "best-case" vs "worst-case" latency estimate for a RAG-based query? I need to know if I’m designing for a "Type-ahead" experience or a "Submit and Wait" experience.

TARGET_AGENT: Dr. James Okafor | REQUEST: Regarding the "Golden Dataset"—how does the model currently handle conflicting information? (e.g., if two documents say different things). A user might say, *"The search result is arguing with itself."* I need to know how we represent uncertainty in the UI.

## Status
I am preparing the interview scripts for the five Power User accounts. My focus is shifting from "what features are missing" to "what is the cost of the current search failure" (e.g., hours lost, legal risks). I have a preliminary list of competitors for the friction analysis, focusing on their "hallucination" complaints in public forums.

**Next Step:** Executing the first two Contextual Inquiry interviews.