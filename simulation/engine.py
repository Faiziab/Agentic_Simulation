"""
Simulation Engine — Main Orchestrator.
Manages the 7-round simulation lifecycle, agent coordination,
task delegation, and communication routing.
Supports any number of departments and agents (fully dynamic).
"""

import os
import yaml
from concurrent.futures import ThreadPoolExecutor, as_completed

from simulation.agents import Agent, load_agents
from simulation.communication import MessageBoard
from simulation.reflection import ReflectionEngine
from simulation.shared_knowledge import KnowledgeManager
from simulation.logger import SimulationLogger
from simulation.chat_chains import ChatChainRunner
from simulation.traits.voting import VotingBallot
from simulation.dashboard import DashboardState, LiveDashboard, Status
try:
    from simulation.ui_dashboard import NiceGUIDashboard
except ImportError:
    NiceGUIDashboard = None  # NiceGUI not installed — fall back to old dashboard


class SimulationEngine:
    """
    Orchestrates the full R&D department simulation.
    Manages rounds, agent activation, task delegation,
    communication routing, and reflection cycles.
    """

    def __init__(
        self,
        config_dir: str,
        workspace_dir: str,
        model_name: str = "gemini-3-flash-preview",
        model_map: dict[int, str] | None = None,
        verbose: bool = False,
        live: bool = False,
    ):
        self.config_dir = config_dir
        self.workspace_dir = workspace_dir
        self.model_name = model_name
        self.verbose = verbose
        self.live = live

        # Load config
        with open(os.path.join(config_dir, "org_structure.yaml"), "r", encoding="utf-8") as f:
            self.org_structure = yaml.safe_load(f)

        # Load pipeline config (data-driven round sequence)
        pipeline_path = os.path.join(config_dir, "pipeline.yaml")
        if os.path.exists(pipeline_path):
            with open(pipeline_path, "r", encoding="utf-8") as f:
                self.pipeline = yaml.safe_load(f).get("pipeline", [])
        else:
            self.pipeline = []  # Falls back to hardcoded if no pipeline.yaml

        # Initialize components
        agents_and_registry = load_agents(config_dir, workspace_dir, model_name, model_map=model_map)
        self.agents: dict[str, Agent] = agents_and_registry[0]
        self.trait_registry = agents_and_registry[1]
        self.message_board = MessageBoard(workspace_dir)
        self.reflection_engine = ReflectionEngine()
        self.logger = SimulationLogger(workspace_dir, verbose=verbose)
        self.chat_chain_runner = ChatChainRunner(max_turns=4)
        self.knowledge_manager = KnowledgeManager(workspace_dir)

        # ── Dynamic Agent Discovery ──────────────────
        self.vp_id = next(
            (aid for aid, a in self.agents.items() if a.level == 1), None
        )
        self.lead_ids = [aid for aid, a in self.agents.items() if a.level == 2]
        self.ic_ids = [aid for aid, a in self.agents.items() if a.level >= 3]

        # Discover all departments dynamically
        self.departments = set()
        for agent in self.agents.values():
            if agent.department:
                self.departments.add(agent.department)

        # Create workspace directories (dynamic per department)
        self._setup_workspace()

        # Wire shared knowledge pools to agents
        for agent in self.agents.values():
            if agent.department:
                agent.shared_knowledge = self.knowledge_manager.get_pool(agent.department)

        # State tracking
        self.current_round = 0
        self.round_outputs: dict[int, list[dict]] = {}
        self.quality_gate_iterations = 0

        # ── Dashboard (optional, --live mode) ────────
        self.dashboard = None
        self.dashboard_state: DashboardState | None = None
        if self.live:
            self.dashboard_state = DashboardState(self.agents)
            self.dashboard_state.set_agents_ref(self.agents)
            # Prefer NiceGUI dashboard, fall back to old HTML dashboard
            if NiceGUIDashboard is not None:
                self.dashboard = NiceGUIDashboard(self.dashboard_state)
            else:
                self.dashboard = LiveDashboard(self.dashboard_state)

    def _setup_workspace(self):
        """Create the workspace directory structure — dynamic per department."""
        dirs = [
            os.path.join(self.workspace_dir, "shared"),
            os.path.join(self.workspace_dir, "memory"),
            os.path.join(self.workspace_dir, "reflections"),
            os.path.join(self.workspace_dir, "logs"),
            os.path.join(self.workspace_dir, "reports"),
            os.path.join(self.workspace_dir, "knowledge"),
        ]
        # Create a directory for each discovered department
        for dept in self.departments:
            dirs.append(os.path.join(self.workspace_dir, "departments", dept))
        for d in dirs:
            os.makedirs(d, exist_ok=True)

    def run(self, prompt: str):
        """Run the full 7-round simulation."""
        self.logger.log_simulation_start(prompt, len(self.agents))

        # Start dashboard if in live mode
        if self.dashboard:
            self.dashboard.start()

        self._run_all_rounds(prompt)
        self.logger.log_simulation_end()

    def _run_all_rounds(self, prompt: str):
        """Execute simulation rounds using data-driven pipeline or fallback."""
        if self.pipeline:
            self._run_pipeline(prompt)
        else:
            self._run_fallback_rounds(prompt)

        # Generate trait reports
        self._save_trait_reports()

        # Simulation end hooks
        for agent_id, agent in self.agents.items():
            self.trait_registry.call_on_simulation_end(agent_id, agent)

    def _run_pipeline(self, prompt: str):
        """Data-driven pipeline executor — reads steps from pipeline.yaml.

        Supports:
          - Standard rounds (call engine methods)
          - Auto-skip (skip steps with no applicable work)
          - Quality gates (VP evaluates and can trigger re-iteration)
        """
        i = 0
        self.quality_gate_iterations = 0

        while i < len(self.pipeline):
            # ── Kill switch check ─────────────────────
            if self.dashboard_state and self.dashboard_state.kill_requested.is_set():
                self._log_pipeline("⛔ Simulation killed via dashboard")
                if self.dashboard_state:
                    self.dashboard_state.add_message(
                        "System", "All", "skip", "Simulation killed by user"
                    )
                break

            step = self.pipeline[i]
            step_type = step.get("type", "round")
            step_name = step.get("name", f"Step {i+1}")

            # ── Quality Gate ──────────────────────────
            if step_type == "quality_gate":
                max_iter = step.get("max_iterations", 2)
                if self.quality_gate_iterations < max_iter:
                    should_proceed = self._quality_gate_evaluation(prompt)
                    if should_proceed:
                        self._log_pipeline("✅ Quality Gate: VP approved — proceeding")
                        if self.dashboard_state:
                            self.dashboard_state.add_message(
                                "VP", "All", "quality_gate", "Quality approved — proceeding"
                            )
                        self.quality_gate_iterations = 0
                        i += 1
                    else:
                        self.quality_gate_iterations += 1
                        self._log_pipeline(
                            f"🔄 Quality Gate: VP requests iteration "
                            f"({self.quality_gate_iterations}/{max_iter})"
                        )
                        if self.dashboard_state:
                            self.dashboard_state.add_message(
                                "VP", "All", "quality_gate",
                                f"Iteration {self.quality_gate_iterations}/{max_iter} — needs more work"
                            )
                        target = step.get("iterate_from", "")
                        target_idx = self._find_step_index(target)
                        if target_idx is not None:
                            i = target_idx
                        else:
                            i += 1
                else:
                    self._log_pipeline("⚠️ Quality Gate: Max iterations reached — proceeding")
                    self.quality_gate_iterations = 0
                    i += 1
                continue

            # ── Auto-skip check ───────────────────────
            if step.get("auto_skip") and self._should_skip_step(step):
                self._log_pipeline(f"⏩ Skipping {step_name} (no applicable work)")
                if self.dashboard_state:
                    self.dashboard_state.add_message(
                        "Pipeline", step_name, "skip", "No applicable work — skipped"
                    )
                i += 1
                continue

            # ── Execute the step ──────────────────────
            method_name = step.get("method")
            if method_name and hasattr(self, method_name):
                method = getattr(self, method_name)
                round_num = step.get("round_number")

                # Dashboard notification for rounds
                if step_type == "round" and round_num:
                    self._notify_dashboard_round(round_num, step_name)

                # Call the method with appropriate arguments
                if step.get("pass_prompt"):
                    method(prompt)
                elif step.get("pass_round"):
                    method(step["pass_round"])
                else:
                    method()

                # Round-end hooks for standard rounds
                if step_type == "round" and round_num:
                    self._call_round_end_hooks(round_num)

            i += 1

    def _find_step_index(self, step_name: str) -> int | None:
        """Find the index of a pipeline step by name."""
        for idx, step in enumerate(self.pipeline):
            if step.get("name") == step_name:
                return idx
        return None

    def _should_skip_step(self, step: dict) -> bool:
        """Determine if a step should be auto-skipped.

        Returns True if there's no applicable work for this step.
        """
        method_name = step.get("method", "")

        if method_name == "_round_4_collaboration":
            # Skip collaboration if no cross-department messages exist
            cross_dept = self.message_board.get_cross_department()
            return len(cross_dept) == 0

        if method_name == "_run_fact_checks":
            # Skip fact-check if no agents have the fact_check trait
            if not self.trait_registry:
                return True
            has_fact_check = any(
                self.trait_registry.has_trait(aid, "fact_check")
                for aid in self.agents
            )
            return not has_fact_check

        if method_name == "_run_voting_session":
            # Skip voting if no agents have the voting trait
            if not self.trait_registry:
                return True
            has_voting = any(
                self.trait_registry.has_trait(aid, "voting")
                for aid in self.agents
            )
            return not has_voting

        return False  # Don't skip by default

    def _quality_gate_evaluation(self, prompt: str) -> bool:
        """VP evaluates current output quality and decides: proceed or iterate.

        Returns:
            True if quality is sufficient (proceed to next step).
            False if another iteration is needed.
        """
        if not self.vp_id:
            return True  # No VP, just proceed

        vp = self.agents[self.vp_id]

        # Gather current deliverables for the VP to review
        deliverables = self.message_board.get_for_agent(self.vp_id, msg_type="deliverable")
        if not deliverables:
            return True  # No deliverables to review — proceed

        deliverable_summary = "\n\n".join(
            f"**{d.from_agent} (Round {d.round_number}):**\n{d.content[:500]}"
            for d in deliverables[-6:]  # Last 6 deliverables
        )

        evaluation_prompt = f"""You are evaluating the quality of your team's work so far.

ORIGINAL INITIATIVE: "{prompt}"

CURRENT DELIVERABLES:
{deliverable_summary}

Evaluate whether the work is of sufficient quality to proceed to the final synthesis.
Consider:
- Are the analyses thorough enough?
- Are there major gaps or missing perspectives?
- Is the evidence strong enough for a strategic recommendation?

Respond with EXACTLY one word on the first line: PROCEED or ITERATE
Then briefly explain your reasoning (2-3 sentences)."""

        self._notify_dashboard_thinking(self.vp_id, "Evaluating quality...")
        result = vp.think(evaluation_prompt, round_number=self.current_round)
        self._notify_dashboard_done(self.vp_id, result,
                                     task_text=evaluation_prompt, action="quality_gate",
                                     round_number=self.current_round)

        # Parse the decision
        first_line = result.strip().split("\n")[0].strip().upper()
        should_proceed = "PROCEED" in first_line

        self.logger.log_agent_action(
            agent_id=self.vp_id,
            agent_name=vp.name,
            agent_role=vp.title,
            action="quality_gate",
            task="Evaluate team output quality",
            output_summary=f"Decision: {'PROCEED' if should_proceed else 'ITERATE'} — {result[:200]}",
            full_output=result,
            round_number=self.current_round,
        )

        return should_proceed

    def _run_fallback_rounds(self, prompt: str):
        """Fallback: hardcoded round sequence if no pipeline.yaml exists."""
        self._notify_dashboard_round(1, "Strategic Decomposition")
        self._round_1_strategic_decomposition(prompt)
        self._call_round_end_hooks(1)

        self._notify_dashboard_round(2, "Department Planning")
        self._round_2_department_planning()
        self._call_round_end_hooks(2)

        self._notify_dashboard_round(3, "Execution")
        self._round_3_execution()
        self._call_round_end_hooks(3)

        self._run_fact_checks(3)

        self._notify_dashboard_round(4, "Cross-Department Collaboration")
        self._round_4_collaboration()
        self._call_round_end_hooks(4)

        self._notify_dashboard_round(5, "Refinement")
        self._round_5_refinement()
        self._call_round_end_hooks(5)

        self._run_voting_session(prompt)

        self._notify_dashboard_round(6, "Reflection & Synthesis")
        self._round_6_reflection()
        self._call_round_end_hooks(6)

        self._notify_dashboard_round(7, "Final Report")
        self._round_7_final_report(prompt)
        self._call_round_end_hooks(7)

    # ── Dashboard Helpers ──────────────────────────

    def _log_pipeline(self, message: str):
        """Log a pipeline event — prints to console unless live dashboard is active."""
        if not self.dashboard:
            self.logger.console.print(f"  {message}")


    def _notify_dashboard_round(self, round_number: int, round_name: str):
        """Update dashboard with current round info and reset agent statuses."""
        if self.dashboard_state:
            self.dashboard_state.set_round(round_number, round_name)
            self.dashboard_state.reset_all()

    def _notify_dashboard_thinking(self, agent_id: str, task_preview: str = ""):
        """Mark an agent as thinking on the dashboard."""
        if self.dashboard_state:
            self.dashboard_state.set_thinking(agent_id, task_preview)
            self.dashboard_state.increment_api_calls()

    def _notify_dashboard_done(self, agent_id: str, output_preview: str = "",
                                task_text: str = "", action: str = "", round_number: int = 0):
        """Mark an agent as done on the dashboard and log the conversation."""
        if self.dashboard_state:
            self.dashboard_state.set_done(agent_id, output_preview)
            agent = self.agents.get(agent_id)
            if agent:
                # Stream the full conversation to the dashboard
                if task_text or output_preview:
                    self.dashboard_state.add_conversation(
                        agent_id=agent_id,
                        agent_name=agent.name,
                        department=agent.department or "executive",
                        action=action or "response",
                        task=task_text,
                        response=output_preview,
                        round_number=round_number,
                        tools_used=list(getattr(agent, 'last_tools_used', [])),
                    )

                # ── Track confidence for heatmap ──
                confidence = getattr(agent, 'confidence', None)
                if confidence is not None:
                    self.dashboard_state.add_confidence_entry(
                        agent_id=agent_id,
                        agent_name=agent.name,
                        score=confidence,
                        round_number=round_number or self.current_round,
                    )

                # ── Track token usage ──
                token_usage = getattr(agent, 'last_token_usage', None)
                if token_usage:
                    self.dashboard_state.update_token_stats(
                        agent_id=agent_id,
                        input_tokens=token_usage.get('input', 0),
                        output_tokens=token_usage.get('output', 0),
                        model=agent.model_name if hasattr(agent, 'model_name') else self.model_name,
                    )

    # ── Trait Integration Methods ───────────────────

    def _call_round_end_hooks(self, round_number: int):
        """Call on_round_end for all agents' traits."""
        for agent_id, agent in self.agents.items():
            self.trait_registry.call_on_round_end(agent_id, agent, round_number)

    def _run_fact_checks(self, after_round: int):
        """Run fact-check pass: leads review ICs' work from the previous round."""
        fact_trait = self.trait_registry.get_trait(self.vp_id, "fact_check")
        if not fact_trait:
            return

        self.logger.console.print(
            "\n  🔍 [bold yellow]Fact-Check Pass[/bold yellow] — Leads reviewing IC deliverables..."
        )

        outputs = self.round_outputs.get(after_round, [])
        if not outputs:
            return

        # Group outputs by department, have each lead check their ICs' work
        for lead_id, lead in self.agents.items():
            if lead.level != 2:  # Only leads
                continue

            ic_outputs = [
                o for o in outputs
                if o.get("department") == lead.department and o.get("agent_id") != lead_id
            ]

            for output in ic_outputs[:2]:  # Check up to 2 per lead to limit API calls
                content = output.get("response", "")
                if len(content) < 50:
                    continue

                check_prompt = fact_trait.build_fact_check_prompt(
                    checker_name=lead.name,
                    checker_role=lead.title,
                    source_name=output.get("agent_name", "Unknown"),
                    source_role=output.get("agent_role", ""),
                    content=content,
                )

                try:
                    response = lead.think(check_prompt, round_number=after_round)
                    verified, flagged, rating, notes = fact_trait.parse_fact_check(response)
                    fact_trait.record_result(
                        source_agent=output.get("agent_id", ""),
                        checker_agent=lead_id,
                        content_preview=content[:100],
                        verified=verified,
                        flagged=flagged,
                        rating=rating,
                        notes=notes,
                        round_number=after_round,
                    )

                    rating_emoji = {"reliable": "✅", "mostly_reliable": "⚠️", "needs_review": "🔴"}.get(
                        rating, "❓"
                    )
                    self.logger.console.print(
                        f"    {rating_emoji} {lead.name} reviewed {output.get('agent_name', '?')}: {rating}"
                    )
                except Exception as e:
                    self.logger.console.print(f"    ⚠️ Fact-check error: {e}")

    def _run_voting_session(self, prompt: str):
        """Run a voting session after refinement — leads vote on the recommendation."""
        voting_trait = self.trait_registry.get_trait(self.vp_id, "voting")
        if not voting_trait:
            return

        self.logger.console.print(
            "\n  🗳️ [bold magenta]Voting Session[/bold magenta] — Department leads voting on recommendation..."
        )

        # Build context from Round 5 outputs
        context_parts = []
        for output in self.round_outputs.get(5, []):
            context_parts.append(f"{output.get('agent_name', '?')}: {output.get('response', '')[:300]}")
        context = "\n\n".join(context_parts)

        topic = f"Should we proceed with the proposed approach for: {prompt[:100]}?"
        session = voting_trait.create_session(topic=topic, round_number=5)

        # Each lead + VP votes
        for agent_id, agent in self.agents.items():
            if agent.level > 2:  # Only leads and VP
                continue

            vote_prompt = voting_trait.build_vote_prompt(
                agent_name=agent.name,
                agent_role=agent.title,
                topic=topic,
                context=context[:2000],
            )

            try:
                response = agent.think(vote_prompt, round_number=5)
                vote, reasoning = voting_trait.parse_vote(response)
                weight = voting_trait.get_weight(agent.level)

                session.cast_vote(
                    VotingBallot(
                        agent_id=agent_id,
                        agent_name=agent.name,
                        vote=vote,
                        reasoning=reasoning,
                        weight=weight,
                    )
                )

                vote_emoji = {"support": "👍", "oppose": "👎", "abstain": "🤷"}.get(vote, "❓")
                self.logger.console.print(
                    f"    {vote_emoji} {agent.name}: {vote} (weight: {weight})"
                )
            except Exception as e:
                self.logger.console.print(f"    ⚠️ Voting error for {agent.name}: {e}")

        # Tally results
        result = session.tally()
        self.logger.console.print(
            f"\n    📊 [bold]Result:[/bold] {result['winner'].upper()} "
            f"(margin: {result['margin']:.0%}, unanimous: {result['unanimous']})"
        )

    def _save_trait_reports(self):
        """Save all trait reports to workspace."""
        reports_dir = os.path.join(self.workspace_dir, "reports")
        os.makedirs(reports_dir, exist_ok=True)

        sections = []

        # Confidence report
        for agent_id in self.agents:
            conf_trait = self.trait_registry.get_trait(agent_id, "confidence")
            if conf_trait:
                summary = conf_trait.get_summary()
                if summary.get("avg") is not None:
                    sections.append(
                        f"**{agent_id}** — Avg: {summary['avg']:.1f}/10, "
                        f"Min: {summary['min']}, Max: {summary['max']}, "
                        f"Low-confidence outputs: {summary['low_count']}"
                    )
                break  # Shared instance, only need one

        # Voting report
        voting_trait = self.trait_registry.get_trait(self.vp_id, "voting")
        if voting_trait:
            voting_md = voting_trait.format_results()
            if voting_md:
                sections.append(voting_md)

        # Knowledge graph report
        kg_trait = self.trait_registry.get_trait(self.vp_id, "knowledge_graph")
        if kg_trait:
            kg_md = kg_trait.get_report()
            if kg_md:
                sections.append(kg_md)

        # Skill growth report
        sg_trait = self.trait_registry.get_trait(self.vp_id, "skill_growth")
        if sg_trait:
            sg_md = sg_trait.format_all_skills()
            if sg_md:
                sections.append(sg_md)

        # Fact-check report
        fc_trait = self.trait_registry.get_trait(self.vp_id, "fact_check")
        if fc_trait:
            fc_md = fc_trait.format_report()
            if fc_md:
                sections.append(fc_md)

        # Devil's advocate report
        da_trait = self.trait_registry.get_trait(self.vp_id, "devil_advocate")
        if da_trait:
            da_md = da_trait.format_report()
            if da_md:
                sections.append(da_md)

        # Emotional state / morale report
        es_trait = self.trait_registry.get_trait(self.vp_id, "emotional_state")
        if es_trait:
            es_md = es_trait.format_report()
            if es_md:
                sections.append(es_md)

        # Decision log report
        dl_trait = self.trait_registry.get_trait(self.vp_id, "decision_log")
        if dl_trait:
            dl_md = dl_trait.format_report()
            if dl_md:
                sections.append(dl_md)

        # Stakeholder pressure report
        sp_trait = self.trait_registry.get_trait(self.vp_id, "stakeholder_pressure")
        if sp_trait:
            sp_md = sp_trait.format_report()
            if sp_md:
                sections.append(sp_md)

        if sections:
            report_path = os.path.join(reports_dir, "trait_reports.md")
            with open(report_path, "w", encoding="utf-8") as f:
                f.write("# Trait System Reports\n\n")
                f.write("\n\n---\n\n".join(sections))
            self.logger.console.print(
                f"\n  📊 Trait reports saved to: [bold]{report_path}[/bold]"
            )

    # ═══════════════════════════════════════════════
    # ROUND 1: VP STRATEGIC DECOMPOSITION
    # ═══════════════════════════════════════════════

    def _round_1_strategic_decomposition(self, prompt: str):
        """VP receives the prompt and decomposes it into department objectives."""
        self.current_round = 1
        self.logger.log_round_start(1)

        vp = self.agents[self.vp_id]

        # Build dynamic department list from actual leads
        dept_descriptions = []
        for i, lead_id in enumerate(self.lead_ids, 1):
            lead = self.agents[lead_id]
            dept_name = (lead.department or "General").title()
            dept_descriptions.append(
                f"{i}. **{dept_name} Department** ({lead.name}): "
                f"What should they investigate, analyze, or work on?"
            )
        dept_list = "\n".join(dept_descriptions)

        task = f"""You have received the following strategic initiative from the board:

"{prompt}"

As VP of R&D, decompose this into specific objectives for your {len(self.lead_ids)} department leads:

{dept_list}

For EACH department, provide:
- A clear objective statement
- 2-3 specific tasks they should accomplish
- What deliverables you expect from them
- Any cross-department dependencies they should be aware of

Be strategic and ensure all departments' work will come together into a comprehensive analysis."""

        self._notify_dashboard_thinking(self.vp_id, "Strategic decomposition...")
        result = vp.act(task, round_number=1)
        self._notify_dashboard_done(self.vp_id, result["response"],
                                     task_text=task, action="strategic_decomposition",
                                     round_number=1)
        self.round_outputs[1] = [result]

        self.logger.log_agent_action(
            agent_id=self.vp_id,
            agent_name=vp.name,
            agent_role=vp.title,
            action="strategic_decomposition",
            task="Decompose initiative into department objectives",
            output_summary=result["response"][:200],
            full_output=result["response"],
            round_number=1,
        )

        # Store VP's decomposition for leads to access
        self._save_shared_document(
            "task_board.md",
            f"# Task Board — R&D Initiative\n\n"
            f"## Original Prompt\n{prompt}\n\n"
            f"## VP's Strategic Decomposition\n{result['response']}\n",
        )

        # ── Dashboard: comm flow VP → all leads ──
        if self.dashboard_state:
            for lead_id in self.lead_ids:
                lead = self.agents[lead_id]
                self.dashboard_state.add_comm_flow(
                    from_name=vp.name, to_name=lead.name,
                    msg_type="delegation", preview="Strategic objectives",
                    round_number=1,
                )

        self.logger.log_round_end(1)

    # ═══════════════════════════════════════════════
    # ROUND 2: DEPARTMENT PLANNING
    # ═══════════════════════════════════════════════

    def _round_2_department_planning(self):
        """Department leads receive objectives and plan tasks for their teams."""
        self.current_round = 2
        self.logger.log_round_start(2)

        vp_output = self.round_outputs[1][0]["response"]
        vp_name = self.agents[self.vp_id].name if self.vp_id else "VP"
        round_outputs = []

        def _plan_for_lead(lead_id):
            lead = self.agents[lead_id]
            dept_name = lead.department

            # Get direct reports
            reporting = self.org_structure["reporting_lines"].get(lead_id, {})
            reports = reporting.get("direct_reports", [])
            report_names = []
            for r_id in reports:
                if r_id in self.agents:
                    r_agent = self.agents[r_id]
                    report_names.append(f"{r_agent.name} ({r_agent.title})")

            team_info = ", ".join(report_names) if report_names else "No direct reports"

            task = f"""The VP of R&D ({vp_name}) has set the following strategic direction:

{vp_output}

As the {lead.title}, review the objectives assigned to your department and create a detailed plan:

1. **Your interpretation** of the department's objectives (in your own words)
2. **Task assignments** for your team members ({team_info}):
   - What specific tasks should each person work on?
   - What deliverables should they produce?
   - Any guidance or constraints you want to set
3. **Your own tasks** — what will you personally focus on?
4. **Dependencies** — what do you need from other departments?
5. **Risks & concerns** you see with this initiative

Delegate effectively — leverage each team member's strengths."""

            self._notify_dashboard_thinking(lead_id, f"Planning {dept_name} dept...")
            result = lead.act(task, round_number=2)
            self._notify_dashboard_done(lead_id, result["response"],
                                         task_text=task, action="department_planning",
                                         round_number=2)

            self.logger.log_agent_action(
                agent_id=lead_id,
                agent_name=lead.name,
                agent_role=lead.title,
                action="department_planning",
                task=f"Plan tasks for {dept_name} department",
                assigned_by=self.vp_id or "",
                output_summary=result["response"][:200],
                full_output=result["response"],
                round_number=2,
                department=dept_name,
            )

            # Post task assignments to message board for team members
            for r_id in reports:
                self.message_board.post_task_assignment(
                    from_agent=lead_id,
                    to_agent=r_id,
                    task_description=f"Tasks from {lead.name}:\n{result['response']}",
                    round_number=2,
                )
                self.logger.log_communication(
                    from_agent=lead_id,
                    to_agent=r_id,
                    msg_type="task_assignment",
                    content_preview=f"Task delegation from {lead.name}",
                    round_number=2,
                )
                if self.dashboard_state:
                    r_agent = self.agents.get(r_id)
                    self.dashboard_state.add_message(
                        from_name=lead.name,
                        to_name=r_agent.name if r_agent else r_id,
                        msg_type="task_assignment",
                        preview=f"Assigned tasks for {dept_name}",
                        department=dept_name,
                    )

            # Handle cross-department requests
            for req in result.get("cross_dept_requests", []):
                target = req["target"]
                self.message_board.post_question(
                    from_agent=lead_id,
                    to_agent=target,
                    question=req["request"],
                    round_number=2,
                )

            return result

        # Run leads concurrently
        if self.live and len(self.lead_ids) > 1:
            with ThreadPoolExecutor(max_workers=len(self.lead_ids)) as executor:
                futures = {executor.submit(_plan_for_lead, lid): lid for lid in self.lead_ids}
                for future in as_completed(futures):
                    try:
                        round_outputs.append(future.result())
                    except Exception as e:
                        self.logger.console.print(f"  ⚠️ Error in lead planning: {e}")
        else:
            for lead_id in self.lead_ids:
                round_outputs.append(_plan_for_lead(lead_id))

        self.round_outputs[2] = round_outputs
        self.logger.log_round_end(2)

    # ═══════════════════════════════════════════════
    # ROUND 3: EXECUTION (INDIVIDUAL WORK)
    # ═══════════════════════════════════════════════

    def _round_3_execution(self):
        """ICs work on their assigned tasks (concurrently when in live mode)."""
        self.current_round = 3
        self.logger.log_round_start(3)

        round_outputs = []

        def _execute_ic(ic_id):
            ic = self.agents[ic_id]

            # Get task assignments from message board
            assignments = self.message_board.get_for_agent(ic_id, msg_type="task_assignment")
            if not assignments:
                return None

            # Build context from assignments
            assignment_text = "\n\n".join(
                [f"From {a.from_agent}: {a.content}" for a in assignments]
            )

            # Also include the VP's original decomposition for full context
            vp_context = self.round_outputs[1][0]["response"]

            task = f"""You have received the following task assignments:

{assignment_text}

ORIGINAL INITIATIVE CONTEXT (from VP):
{vp_context}

Work on your assigned tasks and produce your deliverables. Be thorough and true to your expertise.

If you need information from someone in another department, state it clearly in the Cross-Department Requests section."""

            self._notify_dashboard_thinking(ic_id, f"Working on tasks...")
            result = ic.act(task, round_number=3)
            self._notify_dashboard_done(ic_id, result["response"],
                                         task_text=task, action="execution",
                                         round_number=3)

            # Find who assigned the task
            assigned_by = assignments[0].from_agent if assignments else ""

            self.logger.log_agent_action(
                agent_id=ic_id,
                agent_name=ic.name,
                agent_role=ic.title,
                action="task_execution",
                task=f"Execute assigned tasks",
                assigned_by=assigned_by,
                output_summary=result["response"][:200],
                full_output=result["response"],
                round_number=3,
                department=ic.department,
            )

            # Submit deliverable to lead
            reporting = self.org_structure["reporting_lines"].get(ic_id, {})
            lead_id = reporting.get("reports_to", "")
            if lead_id:
                self.message_board.post_deliverable(
                    from_agent=ic_id,
                    to_agent=lead_id,
                    deliverable=result["response"],
                    round_number=3,
                )
                if self.dashboard_state:
                    lead = self.agents.get(lead_id)
                    self.dashboard_state.add_message(
                        from_name=ic.name,
                        to_name=lead.name if lead else lead_id,
                        msg_type="deliverable",
                        preview=f"Submitted deliverable",
                        department=ic.department,
                    )

            # Handle cross-department requests
            for req in result.get("cross_dept_requests", []):
                target = req["target"]
                self.message_board.post_question(
                    from_agent=ic_id,
                    to_agent=target,
                    question=req["request"],
                    round_number=3,
                )
                self.logger.log_communication(
                    from_agent=ic_id,
                    to_agent=target,
                    msg_type="question",
                    content_preview=req["request"][:120],
                    round_number=3,
                )

            self.message_board.mark_read(ic_id)
            return result

        # Run ICs concurrently
        if self.live and len(self.ic_ids) > 1:
            with ThreadPoolExecutor(max_workers=len(self.ic_ids)) as executor:
                futures = {executor.submit(_execute_ic, iid): iid for iid in self.ic_ids}
                for future in as_completed(futures):
                    try:
                        r = future.result()
                        if r:
                            round_outputs.append(r)
                    except Exception as e:
                        self.logger.console.print(f"  ⚠️ Error in IC execution: {e}")
        else:
            for ic_id in self.ic_ids:
                r = _execute_ic(ic_id)
                if r:
                    round_outputs.append(r)

        self.round_outputs[3] = round_outputs
        self.logger.log_round_end(3)

    # ═══════════════════════════════════════════════
    # ROUND 4: CROSS-DEPARTMENT COLLABORATION
    # ═══════════════════════════════════════════════

    def _round_4_collaboration(self):
        """Agents engage in multi-turn chat chains for cross-department collaboration."""
        self.current_round = 4
        self.logger.log_round_start(4)

        round_outputs = []
        chat_chain_summaries = []

        # Find all unanswered questions
        pending_questions = [
            m for m in self.message_board.get_all()
            if m.msg_type == "question" and not m.read
        ]

        if not pending_questions:
            self.logger.console.print("  [dim]No cross-department requests to process.[/dim]")
            self.logger.log_round_end(4)
            return

        for question in pending_questions:
            target_agent_id = question.to_agent

            # Try to find the agent by ID or partial match
            responding_agent = None
            for aid, agent in self.agents.items():
                if aid == target_agent_id or target_agent_id in aid:
                    responding_agent = agent
                    target_agent_id = aid
                    break

            if not responding_agent:
                continue

            # Get the initiating agent
            initiating_agent = None
            for aid, agent in self.agents.items():
                if aid == question.from_agent or question.from_agent in aid:
                    initiating_agent = agent
                    break

            if not initiating_agent:
                continue

            # Build context from prior work
            context = ""
            for ro in self.round_outputs.get(3, []):
                if ro.get("agent_id") in [initiating_agent.agent_id, target_agent_id]:
                    context += f"\n{ro.get('agent_id')}'s prior work: {ro.get('response', '')[:300]}\n"

            # Run a multi-turn chat chain instead of single-shot
            topic = f"{initiating_agent.name} asks {responding_agent.name}: {question.content[:100]}"

            self.logger.console.print(
                f"  💬 [bold cyan]Chat Chain:[/bold cyan] {initiating_agent.name} ↔ {responding_agent.name}"
            )

            chain = self.chat_chain_runner.run_chain(
                initiator=initiating_agent,
                responder=responding_agent,
                topic=topic,
                initial_message=question.content,
                context=context,
                round_number=4,
                message_board=self.message_board,
                logger=self.logger,
            )

            question.read = True

            round_outputs.append({
                "agent_id": target_agent_id,
                "agent_name": responding_agent.name,
                "response": chain.conclusion,
                "in_reply_to": question.from_agent,
                "chat_chain": chain.to_dict(),
                "total_turns": len(chain.turns),
            })

            chat_chain_summaries.append(
                self.chat_chain_runner.get_chain_summary(chain)
            )

            # ── Dashboard: comm flow + cross-dept tracking ──
            if self.dashboard_state:
                self.dashboard_state.add_comm_flow(
                    from_name=initiating_agent.name,
                    to_name=responding_agent.name,
                    msg_type="collaboration",
                    preview=question.content[:80],
                    round_number=4,
                )
                self.dashboard_state.add_cross_dept_request(
                    from_agent=initiating_agent.name,
                    from_dept=initiating_agent.department or "executive",
                    to_dept=responding_agent.department or "executive",
                    request=question.content[:200],
                    round_number=4,
                )
                self.dashboard_state.fulfill_cross_dept_request(
                    from_dept=initiating_agent.department or "executive",
                    to_dept=responding_agent.department or "executive",
                    response=chain.conclusion[:200],
                )

            self.logger.log_agent_action(
                agent_id=target_agent_id,
                agent_name=responding_agent.name,
                agent_role=responding_agent.title,
                action="chat_chain_collaboration",
                task=f"Multi-turn discussion with {initiating_agent.name} ({len(chain.turns)} turns)",
                assigned_by=question.from_agent,
                output_summary=f"Chat chain ({len(chain.turns)} turns): {chain.conclusion[:150]}",
                full_output=chain.conclusion,
                round_number=4,
                department=responding_agent.department or "",
            )

        # Save all chat chain transcripts
        if chat_chain_summaries:
            chains_path = os.path.join(self.workspace_dir, "reports", "chat_chains.md")
            with open(chains_path, "w", encoding="utf-8") as f:
                f.write("# Chat Chain Transcripts — Cross-Department Collaboration\n\n")
                f.write(f"Total chains: {len(chat_chain_summaries)}\n\n")
                f.write("---\n\n".join(chat_chain_summaries))
            self.logger.console.print(
                f"  📝 Chat chain transcripts saved to: [bold]{chains_path}[/bold]"
            )

        self.round_outputs[4] = round_outputs
        self.logger.log_round_end(4)

    # ═══════════════════════════════════════════════
    # ROUND 5: REFINEMENT
    # ═══════════════════════════════════════════════

    def _round_5_refinement(self):
        """Leads review deliverables and ICs refine based on feedback (concurrent in live mode)."""
        self.current_round = 5
        self.logger.log_round_start(5)

        round_outputs = []

        def _refine_lead(lead_id):
            lead = self.agents[lead_id]

            # Gather all deliverables submitted to this lead
            deliverables = self.message_board.get_for_agent(lead_id, msg_type="deliverable")

            # Also gather any cross-dept responses relevant to the department
            reporting = self.org_structure["reporting_lines"].get(lead_id, {})
            direct_reports = reporting.get("direct_reports", [])
            responses = [
                m for m in self.message_board.get_by_round(4)
                if m.msg_type == "response" and (
                    m.to_agent == lead_id or m.from_agent == lead_id
                    or any(
                        m.to_agent == r or m.from_agent == r
                        for r in direct_reports
                    )
                )
            ]

            deliverable_text = "\n\n---\n\n".join(
                [f"**From {d.from_agent}:**\n{d.content}" for d in deliverables]
            ) if deliverables else "No deliverables received yet."

            response_text = "\n\n".join(
                [f"**{r.from_agent} → {r.to_agent}:** {r.content}" for r in responses]
            ) if responses else "No cross-department responses."

            task = f"""As {lead.title}, review the work from your team and cross-department collaborations:

TEAM DELIVERABLES:
{deliverable_text}

CROSS-DEPARTMENT COLLABORATION RESPONSES:
{response_text}

Please:
1. **Review** each team member's deliverable — what's strong, what needs improvement?
2. **Integrate** cross-department insights into your department's position
3. **Synthesize** your department's overall findings and recommendations
4. **Produce your department's consolidated output** — this will go to the VP

Format your department's output as a clear, structured document that covers:
- Key Findings
- Recommendations
- Risks & Concerns
- Dependencies on other departments"""

            self._notify_dashboard_thinking(lead_id, f"Reviewing {lead.department} deliverables...")
            result = lead.act(task, round_number=5)
            self._notify_dashboard_done(lead_id, result["response"],
                                         task_text=task, action="review_refinement",
                                         round_number=5)

            self.logger.log_agent_action(
                agent_id=lead_id,
                agent_name=lead.name,
                agent_role=lead.title,
                action="review_and_synthesize",
                task=f"Review team deliverables and synthesize department output",
                output_summary=result["response"][:200],
                full_output=result["response"],
                round_number=5,
                department=lead.department,
            )

            # Submit department synthesis to VP
            self.message_board.post_deliverable(
                from_agent=lead_id,
                to_agent=self.vp_id,
                deliverable=result["response"],
                context=f"Department synthesis from {lead.department}",
                round_number=5,
            )

            # Save department output
            if lead.department:
                dept_dir = os.path.join(self.workspace_dir, "departments", lead.department)
                os.makedirs(dept_dir, exist_ok=True)
                with open(os.path.join(dept_dir, "department_output.md"), "w", encoding="utf-8") as f:
                    f.write(f"# {lead.department.title()} Department Output\n\n")
                    f.write(f"**Lead:** {lead.name}\n\n")
                    f.write(result["response"])

            self.message_board.mark_read(lead_id)
            return result

        # Run leads concurrently
        if self.live and len(self.lead_ids) > 1:
            with ThreadPoolExecutor(max_workers=len(self.lead_ids)) as executor:
                futures = {executor.submit(_refine_lead, lid): lid for lid in self.lead_ids}
                for future in as_completed(futures):
                    try:
                        round_outputs.append(future.result())
                    except Exception as e:
                        self.logger.console.print(f"  ⚠️ Error in lead refinement: {e}")
        else:
            for lead_id in self.lead_ids:
                round_outputs.append(_refine_lead(lead_id))

        self.round_outputs[5] = round_outputs
        self.logger.log_round_end(5)

    # ═══════════════════════════════════════════════
    # ROUND 6: REFLECTION & SYNTHESIS
    # ═══════════════════════════════════════════════

    def _round_6_reflection(self):
        """All agents reflect on their work and generate insights (concurrent in live mode)."""
        self.current_round = 6
        self.logger.log_round_start(6)

        round_outputs = []

        def _reflect_agent(agent_id, agent):
            recent_memories = agent.memory_stream.get_recent(n=15)
            if not recent_memories:
                return None

            reflection_prompt = self.reflection_engine.build_reflection_prompt(
                agent_name=agent.name,
                agent_role=agent.title,
                recent_memories=recent_memories,
            )

            self._notify_dashboard_thinking(agent_id, "Reflecting...")
            reflection = agent.think(reflection_prompt, round_number=6)
            self._notify_dashboard_done(agent_id, reflection,
                                         task_text=reflection_prompt, action="reflection",
                                         round_number=6)

            # Store reflection in memory
            self.reflection_engine.record_reflection(
                agent_id=agent_id,
                memory_stream=agent.memory_stream,
                reflection_content=reflection,
                round_number=6,
            )

            # Save reflection to file
            ref_dir = os.path.join(self.workspace_dir, "reflections")
            with open(os.path.join(ref_dir, f"{agent_id}_reflection.md"), "w", encoding="utf-8") as f:
                f.write(f"# Reflection — {agent.name} ({agent.title})\n\n")
                f.write(reflection)

            self.logger.log_reflection(
                agent_id=agent_id,
                agent_name=agent.name,
                reflection_preview=reflection[:150],
                round_number=6,
            )

            return {
                "agent_id": agent_id,
                "agent_name": agent.name,
                "agent_role": agent.title,
                "reflection": reflection,
            }

        # Run all agent reflections (concurrently in live mode)
        agent_items = list(self.agents.items())
        if self.live and len(agent_items) > 1:
            with ThreadPoolExecutor(max_workers=len(agent_items)) as executor:
                futures = {executor.submit(_reflect_agent, aid, a): aid for aid, a in agent_items}
                for future in as_completed(futures):
                    try:
                        r = future.result()
                        if r:
                            round_outputs.append(r)
                    except Exception as e:
                        self.logger.console.print(f"  ⚠️ Error in reflection: {e}")
        else:
            for agent_id, agent in agent_items:
                r = _reflect_agent(agent_id, agent)
                if r:
                    round_outputs.append(r)

        # Leads perform higher-level synthesis (dynamically discovered)
        for lead_id in self.lead_ids:
            lead = self.agents[lead_id]
            reporting = self.org_structure["reporting_lines"].get(lead_id, {})
            reports = reporting.get("direct_reports", [])

            team_reflections = [
                r for r in round_outputs if r["agent_id"] in reports
            ]
            own_reflection = next(
                (r["reflection"] for r in round_outputs if r["agent_id"] == lead_id), ""
            )

            if team_reflections:
                synthesis_prompt = self.reflection_engine.build_synthesis_prompt(
                    agent_name=lead.name,
                    agent_role=lead.title,
                    team_reflections=team_reflections,
                    own_reflection=own_reflection,
                )
                synthesis = lead.think(synthesis_prompt, round_number=6) or ""

                self.reflection_engine.record_insight(
                    agent_id=lead_id,
                    memory_stream=lead.memory_stream,
                    insight_content=synthesis,
                    round_number=6,
                )

                self.logger.log_agent_action(
                    agent_id=lead_id,
                    agent_name=lead.name,
                    agent_role=lead.title,
                    action="team_synthesis",
                    task="Synthesize team reflections into higher-level insights",
                    output_summary=synthesis[:200],
                    full_output=synthesis,
                    round_number=6,
                    department=lead.department,
                )

        # ── Memory Consolidation & Knowledge Publishing ──
        self.logger.console.print("\n  📦 Consolidating agent memories...")
        for agent_id, agent in self.agents.items():
            try:
                agent.memory_stream.consolidate(
                    current_round=6,
                    llm_client=agent.client,
                    model_name=agent.model_name,
                )
            except Exception:
                pass  # Non-critical

            # Auto-publish high-importance reflections to team knowledge pool
            if agent.department and agent.shared_knowledge:
                reflections = agent.memory_stream.get_by_type("reflection", n=3)
                for mem in reflections:
                    if mem.importance >= 7:
                        try:
                            agent.shared_knowledge.publish(
                                agent_id=agent_id,
                                content=mem.content[:500],
                                tags=[agent.department, agent.title.lower().replace(' ', '_')],
                                importance=mem.importance,
                                round_number=6,
                            )
                        except Exception:
                            pass

        self.round_outputs[6] = round_outputs
        self.logger.log_round_end(6)

    # ═══════════════════════════════════════════════
    # ROUND 7: VP FINAL REPORT
    # ═══════════════════════════════════════════════

    def _round_7_final_report(self, original_prompt: str):
        """VP reviews everything and produces the final synthesis."""
        self.current_round = 7
        self.logger.log_round_start(7)

        vp = self.agents[self.vp_id]

        # Gather all department outputs
        dept_outputs = self.message_board.get_for_agent(self.vp_id, msg_type="deliverable")
        dept_text = "\n\n" + "=" * 60 + "\n\n".join(
            [f"**From {d.from_agent} (Round {d.round_number}):**\n{d.content}" for d in dept_outputs]
        )

        # Gather reflections from all leads (dynamic)
        lead_reflections = ""
        for lead_id in self.lead_ids:
            lead = self.agents[lead_id]
            insights = lead.memory_stream.get_by_type("insight")
            if insights:
                lead_reflections += f"\n**{lead.name}'s Insights:**\n"
                for ins in insights:
                    lead_reflections += f"{ins.content}\n\n"

        # Build dynamic department findings list
        dept_findings = []
        for lead_id in self.lead_ids:
            lead = self.agents[lead_id]
            dept_name = (lead.department or "General").title()
            dept_findings.append(f"   - {dept_name}: What were their key findings?")
        dept_findings_text = "\n".join(dept_findings)

        task = f"""As VP of R&D, you have received all department outputs and team reflections for this initiative.

ORIGINAL INITIATIVE:
"{original_prompt}"

DEPARTMENT OUTPUTS:
{dept_text}

TEAM REFLECTIONS & INSIGHTS:
{lead_reflections}

Produce a FINAL EXECUTIVE SYNTHESIS that includes:

1. **Executive Summary** — 2-3 paragraph overview of findings and recommendation
2. **Key Findings by Department**
{dept_findings_text}
3. **Cross-Department Insights** — What emerged from the collaboration between teams?
4. **Strategic Recommendation** — Your recommended path forward (with confidence level)
5. **Risk Assessment** — Key risks and mitigation strategies
6. **Next Steps** — Concrete action items with owners and timelines
7. **Resource Requirements** — What's needed to move forward
8. **Open Questions** — What still needs to be answered

This should be a polished, executive-ready document. Be decisive but acknowledge uncertainties."""

        self._notify_dashboard_thinking(self.vp_id, "Writing final synthesis...")
        result = vp.act(task, round_number=7)
        self._notify_dashboard_done(self.vp_id, result["response"],
                                     task_text=task, action="final_synthesis",
                                     round_number=7)
        self.round_outputs[7] = [result]

        self.logger.log_agent_action(
            agent_id=self.vp_id,
            agent_name=vp.name,
            agent_role=vp.title,
            action="final_synthesis",
            task="Produce final executive synthesis",
            output_summary=result["response"][:200],
            full_output=result["response"],
            round_number=7,
        )

        # Save final report
        report_path = os.path.join(self.workspace_dir, "reports", "final_synthesis.md")
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(f"# Final Executive Synthesis\n\n")
            f.write(f"**Initiative:** {original_prompt}\n\n")
            f.write(f"**Prepared by:** {vp.name}, {vp.title}\n\n")
            f.write("---\n\n")
            f.write(result["response"])

        self.logger.console.print(
            f"\n  📄 Final report saved to: [bold]{report_path}[/bold]"
        )

        self.logger.log_round_end(7)

    # ═══════════════════════════════════════════════
    # UTILITY METHODS
    # ═══════════════════════════════════════════════

    def _save_shared_document(self, filename: str, content: str):
        """Save a document to the shared workspace."""
        filepath = os.path.join(self.workspace_dir, "shared", filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

    def get_simulation_summary(self) -> dict:
        """Get a summary of the simulation state."""
        return {
            "rounds_completed": self.current_round,
            "total_messages": len(self.message_board),
            "agents": {
                aid: agent.get_memory_summary()
                for aid, agent in self.agents.items()
            },
        }
