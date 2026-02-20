# Reflection — Lena Voronova (UX Researcher)

## Thinking
As I look over the tasks Alex has set for me, I’m vibrating with a mix of excitement and a healthy dose of "researcher's skepticism." Alex’s phrase, **"Instant Answers with Zero Doubt,"** is a beautiful North Star, but as a researcher, I know that "Zero Doubt" is an incredibly high bar to clear when you're dealing with LLMs. 

I’m thinking about the junior analyst Alex mentioned. If that analyst asks about a liability cap and the AI gives a number, the very next thing that analyst will do—if they are good at their job—is ask, *"Where did this come from?"* If we don't provide the "why" and the "where," we haven't actually saved them time; we've just given them a new thing to worry about. I need to make sure our "Day 1" designs aren't just a flashy chat box, but a tool that respects the user's need for verification. I'm also worried about the "Chat-first" assumption. Does a lawyer actually want to *talk* to their documents, or do they just want the relevant paragraph highlighted in the context of the full PDF?

## Action

### 1. Salient Questions
*   **The Verification Tax:** If the AI provides an answer but the user feels they must manually open the source document to "double-check" it every single time, have we actually reduced their cognitive load, or just shifted it? A user might say, *"The AI told me the cap is $5M, but I don't trust it enough to put that in my report without seeing the signature on page 182."* How do we design for "Verifiable Trust" rather than just "Accuracy"?
*   **The Interface Assumption:** Are we assuming a "Chat" interface because it’s the current industry trend (Nielsen’s heuristic #4: Consistency and Standards), or is it truly the best way to handle complex document queries? Would a "Supercharged Sidebar" or an "Augmented Results List" better match the user's existing mental model of document management?
*   **The "I Don't Know" Threshold:** What is the UX for a "Low-Confidence" answer? If the AI is only 60% sure, should it guess, or should it revert to a standard keyword search? We need to define what "graceful failure" looks like here.

### 2. Insights
*   **The "Trust Gap" is the Real Competitor:** Looking at the notes from Sarah and Alex, the technical challenge is RAG and latency, but the product challenge is *confidence*. If we have 100% accuracy but 0% transparency, the user will still feel "search pain." Our unique advantage isn't just the model; it's how we visualize the connection between the answer and the source.
*   **Mental Model Friction:** Our users are trained on "Keyword Search." They know how to "control-F." Moving to "Natural Language" is a shift from *giving the system instructions* to *having a conversation*. We need to bridge this. I suspect we’ll find that users want a "Hybrid" experience—the precision of keywords with the synthesis of AI.
*   **The "Day 2" UX is about Freshness:** Sarah mentioned re-indexing. From a user's perspective, this is a "System Status" issue (Nielsen’s heuristic #1). If the search results don't show *when* the document was last indexed, the user will always doubt if they are seeing the latest version. "Instant" is useless if it's "Outdated."

### 3. Self-Assessment
*   **What went well:** I’ve successfully pushed the conversation toward "empathy" and "trust" rather than just "latency" and "features." I think Alex and I are well-aligned on the "Value North Star."
*   **Areas for improvement:** I need to make sure I don't let my own bias against "Chatbots" color the initial mockups. I need to stay objective during the five enterprise interviews and let the users' actual workflows dictate the UI, not my desire for a "cleaner" sidebar.
*   **Confidence Rating:** **High** on identifying the core user problem (Trust/Verification), but **Medium** on our current ability to solve it without cluttering the UI with too much metadata.

## Cross-Department Requests
TARGET_AGENT: alex_kim | REQUEST: Alex, for the five enterprise interviews, can we ensure at least two of them are "Power Users" (those who currently use complex boolean queries) and two are "Casual Searchers"? I want to see if the AI-augmented journey needs to look different for these two distinct personas.
TARGET_AGENT: james_okafor | REQUEST: James, regarding the "Golden Dataset"—could you let me know if your benchmarking includes "Citation Accuracy"? I need to know how often the model points to the *wrong* page for a *correct* answer. This will heavily influence how I design the source-linking UI.

## Status
**Accomplished:** Initial synthesis of the "Trust vs. Accuracy" problem; identified key UX risks in the "Chat-first" assumption; drafted the focus for upcoming user interviews.
**Pending:** Scheduling and conducting the five enterprise interviews; drafting the "Day 1" low-fi wireframes; collaborating with Maya on how to visualize latency (loading states) for longer RAG queries.