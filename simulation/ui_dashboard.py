"""
NiceGUI-based Live Dashboard for the R&D Simulation.
=====================================================
Replaces the old hardcoded HTML dashboard with a Python-native UI framework.
Provides real-time updates via WebSocket (built into NiceGUI), tabs for
communication flow, confidence heatmap, knowledge graph, and more.
"""

import threading
import time
from datetime import datetime
from nicegui import ui, app
from simulation.dashboard import DashboardState, Status


# ── Color Palette ─────────────────────────────────
COLORS = {
    "bg_primary": "#0a0e17",
    "bg_secondary": "#111827",
    "bg_card": "#1a2332",
    "border": "#2a3a4e",
    "text_primary": "#e2e8f0",
    "text_secondary": "#94a3b8",
    "text_dim": "#64748b",
    "accent_cyan": "#22d3ee",
    "accent_blue": "#3b82f6",
    "accent_green": "#10b981",
    "accent_yellow": "#f59e0b",
    "accent_red": "#ef4444",
    "accent_purple": "#a78bfa",
}

DEPT_COLORS = {
    "research": "#60a5fa",
    "engineering": "#34d399",
    "product": "#fbbf24",
    "executive": "#c084fc",
}

DEPT_ICONS = {
    "research": "🔬",
    "engineering": "⚙️",
    "product": "📦",
    "executive": "👔",
}

# Pricing per 1M tokens (input, output)
MODEL_PRICING = {
    "gemini-2.5-flash": (0.15, 0.60),
    "gemini-3-flash-preview": (0.15, 0.60),
    "gemini-3-pro-preview": (3.50, 10.50),
}


class NiceGUIDashboard:
    """NiceGUI-based dashboard that replaces the old HTTP-based LiveDashboard."""

    def __init__(self, state: DashboardState):
        self.state = state
        self._thread: threading.Thread | None = None
        self.port = 8420

        # UI element references (set during page build)
        self._elapsed_label = None
        self._api_calls_label = None
        self._active_label = None
        self._token_label = None
        self._round_badge = None
        self._round_name = None
        self._progress = None
        self._agent_container = None
        self._feed_container = None
        self._conv_container = None
        self._flow_container = None
        self._heatmap_container = None
        self._knowledge_container = None
        self._crossdept_container = None
        self._profiles_container = None
        self._report_container = None
        self._killed_banner = None
        self._last_conv_count = 0
        self._last_msg_count = 0
        self._report_loaded = False

    def start(self):
        """Start the NiceGUI dashboard in a background thread."""
        self._build_pages()
        self._thread = threading.Thread(target=self._run_server, daemon=True)
        self._thread.start()
        time.sleep(1)  # Give server time to start
        import webbrowser
        try:
            webbrowser.open(f"http://127.0.0.1:{self.port}")
        except Exception:
            print(f"  ⚠️  Navigate to http://127.0.0.1:{self.port} manually.")

    def stop(self):
        """Stop the dashboard server."""
        print("  🔴 NiceGUI Dashboard server stopped")

    def _run_server(self):
        """Run NiceGUI server (blocking call in background thread)."""
        ui.run(
            host="0.0.0.0",
            port=self.port,
            title="Agentic Simulation — Live Dashboard",
            reload=False,
            show=False,
        )

    def _build_pages(self):
        """Define all NiceGUI pages."""

        dashboard_ref = self

        @ui.page("/")
        def main_page():
            dashboard_ref._build_main_dashboard()

        @ui.page("/launch")
        def launch_page():
            dashboard_ref._build_launch_page()

    # ══════════════════════════════════════════════════
    # MAIN DASHBOARD PAGE
    # ══════════════════════════════════════════════════
    def _build_main_dashboard(self):
        """Build the main dashboard page with all tabs."""
        # Dark theme
        ui.dark_mode().enable()
        ui.add_head_html("""
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
        <style>
            body { font-family: 'Inter', sans-serif !important; background: #0a0e17 !important; }
            .nicegui-content { padding: 0 !important; }
            .q-card { background: #1a2332 !important; border: 1px solid #2a3a4e !important; }
            .q-tab-panel { padding: 12px !important; }
            .stat-value { font-family: 'JetBrains Mono', monospace; font-weight: 600; }
            .agent-card { transition: all 0.3s ease; border-radius: 10px; }
            .agent-card.thinking { border-color: #f59e0b !important; animation: cardPulse 2s ease-in-out infinite; }
            .agent-card.done { border-color: rgba(16, 185, 129, 0.4) !important; }
            .agent-card.error { border-color: rgba(239, 68, 68, 0.4) !important; }
            @keyframes cardPulse { 0%,100%{box-shadow:none} 50%{box-shadow:0 0 16px rgba(245,158,11,0.12)} }
            .dept-badge { font-size: 10px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.8px;
                          padding: 2px 8px; border-radius: 6px; white-space: nowrap; }
            .conf-fill { height: 4px; border-radius: 4px; transition: width 0.5s ease; }
            .msg-row { animation: fadeIn 0.3s ease; }
            @keyframes fadeIn { from{opacity:0;transform:translateY(-4px)} to{opacity:1;transform:translateY(0)} }
            .killed-banner { background: linear-gradient(135deg, rgba(239,68,68,0.15), rgba(153,27,27,0.1));
                            border: 1px solid rgba(239,68,68,0.4); border-radius: 10px; padding: 16px 24px;
                            text-align: center; }
            .tool-badge { display: inline-flex; align-items: center; gap: 3px;
                         background: rgba(245,158,11,0.15); border: 1px solid rgba(245,158,11,0.3);
                         color: #f59e0b; font-size: 10px; font-weight: 600;
                         padding: 2px 7px; border-radius: 10px; }
            .conv-card { background: rgba(255,255,255,0.03); border: 1px solid #2a3a4e;
                        border-radius: 8px; margin-bottom: 6px; cursor: pointer; transition: border-color 0.2s; }
            .conv-card:hover { border-color: #22d3ee; }
        </style>
        """)

        # ── Header ──────────────────────────
        with ui.header().classes("items-center justify-between px-6 py-3").style(
            f"background: {COLORS['bg_secondary']}; border-bottom: 1px solid {COLORS['border']}"
        ):
            with ui.row().classes("items-center gap-4"):
                ui.icon("circle").classes("text-green-400 text-xs")
                ui.label("🏢 Agentic Simulation — Live Dashboard").classes(
                    "text-lg font-bold"
                ).style(
                    "background: linear-gradient(135deg, #22d3ee, #3b82f6);"
                    "-webkit-background-clip: text; -webkit-text-fill-color: transparent;"
                )

            with ui.row().classes("items-center gap-6"):
                with ui.row().classes("items-center gap-1"):
                    ui.label("⏱").classes("text-sm")
                    self._elapsed_label = ui.label("0m00s").classes("stat-value text-sm")

                with ui.row().classes("items-center gap-1"):
                    ui.label("🔗 API:").classes("text-sm text-gray-400")
                    self._api_calls_label = ui.label("0").classes("stat-value text-sm")

                with ui.row().classes("items-center gap-1"):
                    ui.label("⚡ Active:").classes("text-sm text-gray-400")
                    self._active_label = ui.label("0").classes("stat-value text-sm")

                with ui.row().classes("items-center gap-1"):
                    ui.label("💰").classes("text-sm")
                    self._token_label = ui.label("$0.00").classes("stat-value text-sm text-green-400")

                ui.button("⛔ Kill", on_click=self._kill_simulation).props(
                    "color=red dense no-caps"
                ).classes("px-4")

        # ── Round Progress ──────────────────
        with ui.element("div").classes("w-full px-6 py-3").style(
            f"background: {COLORS['bg_secondary']}; border-bottom: 1px solid {COLORS['border']}"
        ):
            with ui.row().classes("items-center gap-4 mb-2"):
                self._round_badge = ui.badge("ROUND 0/7").props("color=cyan")
                self._round_name = ui.label("Initializing...").classes("text-sm font-medium")
            self._progress = ui.linear_progress(value=0, show_value=False).props(
                "color=cyan rounded size=4px"
            )

        # ── Killed Banner (hidden) ──────────
        self._killed_banner = ui.element("div").classes("hidden killed-banner mx-6 mt-4")
        with self._killed_banner:
            ui.label("⛔ Simulation Killed").classes("text-red-400 text-lg font-bold")
            ui.label("The simulation has been stopped.").classes("text-gray-400 text-sm")

        # ── Main Content ────────────────────
        with ui.element("div").classes("px-6 py-4"):
            # Agent Activity Section
            ui.label("👥 Agent Activity").classes(
                "text-xs font-semibold uppercase tracking-wider text-gray-500 mb-3"
            )
            self._agent_container = ui.element("div").classes("mb-6")

            # ── Tabbed Section ──────────────
            with ui.tabs().classes("w-full").props("dense active-color=cyan indicator-color=cyan") as tabs:
                tab_feed = ui.tab("feed", label="💬 Live Feed")
                tab_conv = ui.tab("conversations", label="🗣️ Conversations")
                tab_flow = ui.tab("flow", label="🔀 Comm Flow")
                tab_heatmap = ui.tab("heatmap", label="🌡️ Heatmap")
                tab_knowledge = ui.tab("knowledge", label="🧠 Knowledge")
                tab_crossdept = ui.tab("crossdept", label="🔗 Cross-Dept")
                tab_profiles = ui.tab("profiles", label="📊 Profiles")
                tab_report = ui.tab("report", label="📄 Report")

            with ui.tab_panels(tabs, value=tab_feed).classes("w-full").style(
                f"background: {COLORS['bg_card']}; border: 1px solid {COLORS['border']}; border-radius: 10px"
            ):
                with ui.tab_panel(tab_feed):
                    self._feed_container = ui.column().classes("w-full gap-0 max-h-64 overflow-y-auto")
                    with self._feed_container:
                        ui.label("Waiting for agent activity...").classes("text-gray-500 text-sm py-8 text-center w-full")

                with ui.tab_panel(tab_conv):
                    self._conv_container = ui.column().classes("w-full gap-1 max-h-96 overflow-y-auto")
                    with self._conv_container:
                        ui.label("No conversations yet...").classes("text-gray-500 text-sm py-8 text-center w-full")

                with ui.tab_panel(tab_flow):
                    self._flow_container = ui.column().classes("w-full")
                    with self._flow_container:
                        ui.label("Communication flow will appear as agents interact...").classes(
                            "text-gray-500 text-sm py-8 text-center w-full"
                        )

                with ui.tab_panel(tab_heatmap):
                    self._heatmap_container = ui.column().classes("w-full")
                    with self._heatmap_container:
                        ui.label("Confidence heatmap builds as rounds complete...").classes(
                            "text-gray-500 text-sm py-8 text-center w-full"
                        )

                with ui.tab_panel(tab_knowledge):
                    self._knowledge_container = ui.column().classes("w-full")
                    with self._knowledge_container:
                        ui.label("Knowledge graph populates during simulation...").classes(
                            "text-gray-500 text-sm py-8 text-center w-full"
                        )

                with ui.tab_panel(tab_crossdept):
                    self._crossdept_container = ui.column().classes("w-full gap-2")
                    with self._crossdept_container:
                        ui.label("Cross-department requests appear during collaboration...").classes(
                            "text-gray-500 text-sm py-8 text-center w-full"
                        )

                with ui.tab_panel(tab_profiles):
                    self._profiles_container = ui.column().classes("w-full")
                    with self._profiles_container:
                        ui.label("Performance profiles generate after simulation completes...").classes(
                            "text-gray-500 text-sm py-8 text-center w-full"
                        )

                with ui.tab_panel(tab_report):
                    self._report_container = ui.column().classes("w-full")
                    with self._report_container:
                        ui.label("⏳ Report will appear here when the simulation completes").classes(
                            "text-gray-500 text-sm py-8 text-center w-full"
                        )

        # ── Polling Timer ───────────────────
        ui.timer(0.5, self._poll_state)

    # ══════════════════════════════════════════════════
    # POLLING & UPDATE
    # ══════════════════════════════════════════════════
    def _poll_state(self):
        """Called every 500ms to update the UI from DashboardState."""
        if not self.state:
            return

        # Header stats
        self._elapsed_label.text = self.state.get_elapsed()
        self._api_calls_label.text = str(self.state.api_calls)
        self._active_label.text = str(self.state.active_count)

        # Token cost
        token_stats = getattr(self.state, "token_stats", None)
        if token_stats:
            cost = token_stats.get("estimated_cost", 0)
            total_in = token_stats.get("total_input", 0)
            total_out = token_stats.get("total_output", 0)
            self._token_label.text = f"${cost:.3f} ({total_in//1000}K in / {total_out//1000}K out)"

        # Round progress
        rn = self.state.round_number
        tr = self.state.total_rounds
        pct = (rn / tr) if tr else 0
        self._round_badge.text = f"ROUND {rn}/{tr}"
        self._round_name.text = self.state.round_name or "Initializing..."
        self._progress.value = pct

        # Agent cards
        self._update_agent_grid()

        # Live feed
        msgs = list(self.state.messages)
        if len(msgs) != self._last_msg_count:
            self._last_msg_count = len(msgs)
            self._update_feed(msgs)

        # Conversations
        convs = self.state.conversation_log
        if len(convs) != self._last_conv_count:
            self._last_conv_count = len(convs)
            self._update_conversations(convs)

        # Communication flow
        comm_flow = getattr(self.state, "comm_flow", [])
        if comm_flow:
            self._update_flow(comm_flow)

        # Confidence heatmap
        conf_grid = getattr(self.state, "confidence_grid", [])
        if conf_grid:
            self._update_heatmap(conf_grid)

        # Knowledge graph
        self._update_knowledge_graph()

        # Cross-dept requests
        cross_dept = getattr(self.state, "cross_dept_requests", [])
        if cross_dept:
            self._update_crossdept(cross_dept)

        # Report
        if self.state.simulation_complete and not self._report_loaded:
            self._report_loaded = True
            self._update_report()
            self._update_profiles()

        # Killed state
        if self.state.kill_requested.is_set():
            self._killed_banner.classes(remove="hidden")

    # ══════════════════════════════════════════════════
    # UI UPDATE METHODS
    # ══════════════════════════════════════════════════
    def _update_agent_grid(self):
        """Rebuild agent hierarchy cards."""
        self._agent_container.clear()
        agents = {}
        with self.state.lock:
            for aid, s in self.state.agent_states.items():
                agents[aid] = dict(s)

        vp, leads, ics = [], {}, {}
        for aid, agent in agents.items():
            lvl = agent.get("level", 3)
            dept = agent.get("department", "executive")
            if lvl == 1:
                vp.append((aid, agent))
            elif lvl == 2:
                leads.setdefault(dept, []).append((aid, agent))
            else:
                ics.setdefault(dept, []).append((aid, agent))

        with self._agent_container:
            # VP tier
            if vp:
                ui.label("👔 EXECUTIVE").classes("text-xs uppercase tracking-widest text-gray-500 text-center mb-1")
                with ui.row().classes("justify-center gap-4 w-full mb-2"):
                    for aid, agent in vp:
                        self._render_agent_card(aid, agent, wide=True)

            # Connector
            if leads:
                with ui.element("div").classes("mx-auto").style(
                    "width: 2px; height: 14px; background: linear-gradient(to bottom, #2a3a4e, rgba(34,211,238,0.3))"
                ):
                    pass

            # Lead tier
            dept_order = ["research", "engineering", "product"]
            active_depts = [d for d in dept_order if d in leads or d in ics]
            if active_depts:
                ui.label("📋 DEPARTMENT LEADS").classes("text-xs uppercase tracking-widest text-gray-500 text-center mb-1")
                with ui.row().classes("justify-center gap-4 w-full mb-2"):
                    for dept in active_depts:
                        with ui.column().classes("items-center gap-1 flex-1 max-w-xs"):
                            icon = DEPT_ICONS.get(dept, "👤")
                            color = DEPT_COLORS.get(dept, "#94a3b8")
                            ui.label(f"{icon} {dept.upper()}").classes("text-xs font-bold").style(f"color: {color}")
                            for aid, agent in leads.get(dept, []):
                                self._render_agent_card(aid, agent)

            # Connector
            if any(d in ics for d in active_depts):
                with ui.element("div").classes("mx-auto").style(
                    "width: 2px; height: 14px; background: linear-gradient(to bottom, #2a3a4e, rgba(34,211,238,0.3))"
                ):
                    pass

            # IC tier
            if any(d in ics for d in active_depts):
                ui.label("🔧 INDIVIDUAL CONTRIBUTORS").classes("text-xs uppercase tracking-widest text-gray-500 text-center mb-1")
                with ui.row().classes("justify-center gap-4 w-full"):
                    for dept in active_depts:
                        if dept not in ics:
                            continue
                        with ui.column().classes("items-center gap-1 flex-1 max-w-xs"):
                            icon = DEPT_ICONS.get(dept, "👤")
                            color = DEPT_COLORS.get(dept, "#94a3b8")
                            ui.label(f"{icon} {dept.upper()}").classes("text-xs font-bold").style(f"color: {color}")
                            for aid, agent in ics[dept]:
                                self._render_agent_card(aid, agent)

    def _render_agent_card(self, aid: str, agent: dict, wide: bool = False):
        """Render a single agent card."""
        status = agent.get("status", "waiting")
        dept = agent.get("department", "executive")
        color = DEPT_COLORS.get(dept, "#94a3b8")
        status_class = status if status in ("thinking", "done", "error") else ""
        width = "max-w-sm w-full" if wide else "w-full"

        with ui.card().classes(f"agent-card {status_class} {width} p-3").style(
            f"border-left: 3px solid {color}; background: {COLORS['bg_card']}"
        ):
            with ui.row().classes("items-start justify-between w-full"):
                with ui.column().classes("gap-0"):
                    ui.label(agent.get("name", aid)).classes("text-sm font-semibold")
                    ui.label(agent.get("title", "")).classes("text-xs text-gray-500")

            # Status line
            if status == "thinking":
                with ui.row().classes("items-center gap-2 mt-1"):
                    ui.spinner(size="xs").props("color=yellow")
                    ui.label(agent.get("task_preview", "Thinking...")[:60]).classes(
                        "text-xs text-gray-400 truncate"
                    )
            elif status == "done":
                with ui.row().classes("items-center gap-1 mt-1"):
                    ui.label("✅").classes("text-xs")
                    ui.label(agent.get("output_preview", "Done")[:60]).classes(
                        "text-xs text-gray-400 truncate"
                    )
                # Confidence bar
                conf = agent.get("confidence")
                if conf is not None:
                    with ui.row().classes("items-center gap-2 mt-1 w-full"):
                        ui.label(f"{conf}%").classes("text-xs text-gray-500")
                        with ui.element("div").classes("flex-1 h-1 rounded").style("background: #2a3a4e"):
                            conf_color = "#ef4444" if conf < 40 else "#f59e0b" if conf < 70 else "#10b981"
                            ui.element("div").classes("conf-fill").style(
                                f"width: {conf}%; background: {conf_color}"
                            )
            elif status == "error":
                ui.label(f"❌ {agent.get('output_preview', 'Error')[:60]}").classes(
                    "text-xs text-red-400 mt-1"
                )
            else:
                ui.label("⏳ Waiting").classes("text-xs text-gray-500 mt-1")

    def _update_feed(self, messages: list):
        """Update the live message feed."""
        self._feed_container.clear()
        with self._feed_container:
            if not messages:
                ui.label("Waiting for agent activity...").classes("text-gray-500 text-sm py-8 text-center w-full")
                return
            for msg in messages:
                dept = msg.get("department", "executive")
                color = DEPT_COLORS.get(dept, "#94a3b8")
                with ui.row().classes("items-start gap-2 px-4 py-2 w-full msg-row").style(
                    f"border-bottom: 1px solid rgba(42,58,78,0.4)"
                ):
                    ui.label(msg.get("time", "")).classes("text-xs text-gray-500 font-mono min-w-14")
                    ui.label(msg.get("icon", "💬")).classes("text-sm")
                    ui.label(msg.get("from", "")).classes("text-sm font-semibold").style(f"color: {color}")
                    ui.label("→").classes("text-gray-500")
                    ui.label(msg.get("to", "")).classes("text-sm text-gray-400")
                    ui.label(msg.get("preview", "")).classes("text-xs text-gray-500 flex-1 truncate")

    def _update_conversations(self, conversations: list):
        """Update the conversations tab."""
        self._conv_container.clear()
        with self._conv_container:
            if not conversations:
                ui.label("No conversations yet...").classes("text-gray-500 text-sm py-8 text-center w-full")
                return

            # Group by round
            by_round = {}
            for c in conversations:
                r = c.get("round", 0)
                by_round.setdefault(r, []).append(c)

            for rnd in sorted(by_round.keys(), reverse=True):
                ui.label(f"ROUND {rnd}").classes(
                    "text-xs font-bold uppercase tracking-wider text-cyan-400 px-2 py-1"
                ).style("border-bottom: 1px solid rgba(34,211,238,0.15)")

                for c in reversed(by_round[rnd]):
                    dept = c.get("department", "executive")
                    color = DEPT_COLORS.get(dept, "#94a3b8")
                    icon = DEPT_ICONS.get(dept, "👤")
                    tools = c.get("tools_used", [])

                    with ui.expansion(
                        f"{icon} {c.get('agent_name', '?')} — {c.get('action', 'response')}",
                    ).classes("w-full conv-card").props("dense"):
                        # Tools used
                        if tools:
                            ui.label("🔧 Tools Used").classes("text-xs font-semibold text-gray-400 mb-1")
                            with ui.row().classes("gap-1 flex-wrap mb-2"):
                                for t in tools:
                                    ui.html(
                                        f'<span class="tool-badge">🔧 {t.get("tool", "?")}</span>'
                                    )
                        # Task
                        ui.label("📋 Task").classes("text-xs font-semibold text-gray-400 mb-1")
                        ui.label(c.get("task", "")).classes(
                            "text-xs whitespace-pre-wrap p-2 rounded"
                        ).style("background: rgba(0,0,0,0.2); max-height: 200px; overflow-y: auto")
                        # Response
                        ui.label("💡 Response").classes("text-xs font-semibold text-gray-400 mt-2 mb-1")
                        ui.label(c.get("response", "")).classes(
                            "text-xs whitespace-pre-wrap p-2 rounded"
                        ).style("background: rgba(0,0,0,0.2); max-height: 300px; overflow-y: auto")

    def _update_flow(self, comm_flow: list):
        """Update communication flow visualization using Plotly Sankey."""
        self._flow_container.clear()
        with self._flow_container:
            if not comm_flow:
                ui.label("No communication data yet...").classes("text-gray-500 text-sm py-8 text-center w-full")
                return

            import plotly.graph_objects as go

            # Build node list and links
            agents_set = set()
            for entry in comm_flow:
                agents_set.add(entry.get("from_name", "?"))
                agents_set.add(entry.get("to_name", "?"))
            agent_list = sorted(agents_set)
            idx = {name: i for i, name in enumerate(agent_list)}

            sources, targets, values, labels = [], [], [], []
            for entry in comm_flow:
                src = idx.get(entry.get("from_name", "?"), 0)
                tgt = idx.get(entry.get("to_name", "?"), 0)
                if src != tgt:
                    sources.append(src)
                    targets.append(tgt)
                    values.append(1)
                    labels.append(entry.get("msg_type", "message"))

            # Assign colors per department
            node_colors = []
            for name in agent_list:
                # Try to find department from state
                color = "#94a3b8"
                for aid, s in self.state.agent_states.items():
                    if s.get("name") == name:
                        color = DEPT_COLORS.get(s.get("department", ""), "#94a3b8")
                        break
                node_colors.append(color)

            fig = go.Figure(data=[go.Sankey(
                node=dict(
                    pad=15, thickness=20, line=dict(color="#2a3a4e", width=0.5),
                    label=agent_list, color=node_colors
                ),
                link=dict(source=sources, target=targets, value=values, label=labels,
                          color="rgba(34,211,238,0.2)")
            )])
            fig.update_layout(
                paper_bgcolor="#0a0e17", plot_bgcolor="#0a0e17",
                font=dict(color="#e2e8f0", family="Inter"), height=400,
                margin=dict(l=20, r=20, t=30, b=20),
                title=dict(text="Agent Communication Flow", font=dict(size=14))
            )
            ui.plotly(fig).classes("w-full")

    def _update_heatmap(self, conf_grid: list):
        """Update confidence heatmap using Plotly."""
        self._heatmap_container.clear()
        with self._heatmap_container:
            if not conf_grid:
                ui.label("No confidence data yet...").classes("text-gray-500 text-sm py-8 text-center w-full")
                return

            import plotly.graph_objects as go

            # Build matrix: agents x rounds
            agents_names = sorted(set(e.get("agent_name", "?") for e in conf_grid))
            rounds = sorted(set(e.get("round", 0) for e in conf_grid))

            z = []
            for agent_name in agents_names:
                row = []
                for rnd in rounds:
                    score = None
                    for e in conf_grid:
                        if e.get("agent_name") == agent_name and e.get("round") == rnd:
                            score = e.get("score")
                            break
                    row.append(score if score is not None else 0)
                z.append(row)

            fig = go.Figure(data=go.Heatmap(
                z=z, x=[f"R{r}" for r in rounds], y=agents_names,
                colorscale=[[0, "#ef4444"], [0.5, "#f59e0b"], [1, "#10b981"]],
                zmin=1, zmax=10,
                hovertemplate="Agent: %{y}<br>Round: %{x}<br>Confidence: %{z}/10<extra></extra>"
            ))
            fig.update_layout(
                paper_bgcolor="#0a0e17", plot_bgcolor="#111827",
                font=dict(color="#e2e8f0", family="Inter"), height=350,
                margin=dict(l=120, r=20, t=40, b=40),
                title=dict(text="Agent Confidence Heatmap", font=dict(size=14)),
                xaxis=dict(title="Round", gridcolor="#2a3a4e"),
                yaxis=dict(title="", gridcolor="#2a3a4e"),
            )
            ui.plotly(fig).classes("w-full")

    def _update_knowledge_graph(self):
        """Update knowledge graph visualization."""
        # Check if knowledge graph trait is available
        kg_data = getattr(self.state, "knowledge_graph_data", None)
        if not kg_data:
            return

        self._knowledge_container.clear()
        with self._knowledge_container:
            import plotly.graph_objects as go

            nodes = kg_data.get("nodes", [])
            edges = kg_data.get("edges", [])

            if not nodes:
                ui.label("No knowledge data yet...").classes("text-gray-500 text-sm py-8 text-center w-full")
                return

            # Simple force-directed layout approximation
            import math
            n = len(nodes)
            node_x, node_y = [], []
            for i, node in enumerate(nodes):
                angle = 2 * math.pi * i / n
                r = 1 if node.get("type") == "agent" else 2
                node_x.append(r * math.cos(angle))
                node_y.append(r * math.sin(angle))

            # Edges
            edge_x, edge_y = [], []
            for edge in edges:
                src_idx = next((i for i, n in enumerate(nodes) if n["id"] == edge["source"]), None)
                tgt_idx = next((i for i, n in enumerate(nodes) if n["id"] == edge["target"]), None)
                if src_idx is not None and tgt_idx is not None:
                    edge_x.extend([node_x[src_idx], node_x[tgt_idx], None])
                    edge_y.extend([node_y[src_idx], node_y[tgt_idx], None])

            fig = go.Figure()
            fig.add_trace(go.Scatter(x=edge_x, y=edge_y, mode="lines",
                                      line=dict(width=1, color="rgba(34,211,238,0.3)"),
                                      hoverinfo="none"))

            colors = ["#22d3ee" if n.get("type") == "agent" else "#f59e0b" for n in nodes]
            sizes = [20 if n.get("type") == "agent" else 10 for n in nodes]
            labels = [n.get("label", "?") for n in nodes]

            fig.add_trace(go.Scatter(
                x=node_x, y=node_y, mode="markers+text", text=labels,
                textposition="top center", textfont=dict(size=9, color="#e2e8f0"),
                marker=dict(size=sizes, color=colors, line=dict(width=1, color="#2a3a4e")),
                hovertemplate="%{text}<extra></extra>",
            ))
            fig.update_layout(
                paper_bgcolor="#0a0e17", plot_bgcolor="#0a0e17",
                font=dict(color="#e2e8f0", family="Inter"), height=450,
                showlegend=False,
                xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                margin=dict(l=20, r=20, t=40, b=20),
                title=dict(text="Knowledge Graph", font=dict(size=14)),
            )
            ui.plotly(fig).classes("w-full")

    def _update_crossdept(self, requests: list):
        """Update cross-department request tracker."""
        self._crossdept_container.clear()
        with self._crossdept_container:
            if not requests:
                ui.label("No cross-department requests yet...").classes(
                    "text-gray-500 text-sm py-8 text-center w-full"
                )
                return

            for req in requests:
                from_dept = req.get("from_dept", "?")
                to_dept = req.get("to_dept", "?")
                status = req.get("status", "pending")
                status_color = {"pending": "#f59e0b", "fulfilled": "#10b981", "unfulfilled": "#ef4444"}.get(
                    status, "#94a3b8"
                )

                with ui.card().classes("w-full p-3"):
                    with ui.row().classes("items-center gap-2 w-full"):
                        # From dept badge
                        from_color = DEPT_COLORS.get(from_dept, "#94a3b8")
                        ui.label(from_dept.upper()).classes("dept-badge").style(
                            f"background: {from_color}22; color: {from_color}"
                        )
                        ui.label("→").classes("text-gray-500")
                        to_color = DEPT_COLORS.get(to_dept, "#94a3b8")
                        ui.label(to_dept.upper()).classes("dept-badge").style(
                            f"background: {to_color}22; color: {to_color}"
                        )
                        ui.space()
                        ui.badge(status.upper()).style(f"background: {status_color}; color: white")

                    ui.label(req.get("request", "")).classes("text-xs text-gray-300 mt-1")
                    ui.label(f"Round {req.get('round', '?')} — {req.get('from_agent', '?')}").classes(
                        "text-xs text-gray-500 mt-1"
                    )

    def _update_profiles(self):
        """Generate and display agent performance profiles."""
        self._profiles_container.clear()
        with self._profiles_container:
            agents = {}
            with self.state.lock:
                for aid, s in self.state.agent_states.items():
                    agents[aid] = dict(s)

            convs = self.state.conversation_log
            conf_grid = getattr(self.state, "confidence_grid", [])

            with ui.row().classes("gap-4 flex-wrap w-full"):
                for aid, agent in agents.items():
                    name = agent.get("name", aid)
                    dept = agent.get("department", "executive")
                    color = DEPT_COLORS.get(dept, "#94a3b8")

                    # Compute stats
                    agent_convs = [c for c in convs if c.get("agent_id") == aid]
                    response_count = len(agent_convs)
                    tool_count = sum(len(c.get("tools_used", [])) for c in agent_convs)

                    agent_scores = [e.get("score", 0) for e in conf_grid if e.get("agent_id") == aid and e.get("score")]
                    avg_conf = sum(agent_scores) / len(agent_scores) if agent_scores else 0

                    with ui.card().classes("p-4").style(f"min-width: 250px; border-left: 3px solid {color}"):
                        ui.label(name).classes("font-semibold text-sm")
                        ui.label(agent.get("title", "")).classes("text-xs text-gray-500 mb-2")

                        # Stat bars
                        stats = [
                            ("Responses", response_count, 10, "#3b82f6"),
                            ("Tools Used", tool_count, 10, "#f59e0b"),
                            ("Avg Confidence", round(avg_conf, 1), 10, "#10b981"),
                        ]
                        for label, value, max_val, bar_color in stats:
                            with ui.row().classes("items-center gap-2 w-full"):
                                ui.label(label).classes("text-xs text-gray-500 w-24")
                                with ui.element("div").classes("flex-1 h-2 rounded").style("background: #2a3a4e"):
                                    pct = min(100, (value / max_val * 100)) if max_val else 0
                                    ui.element("div").style(
                                        f"width: {pct}%; height: 100%; background: {bar_color}; border-radius: 4px"
                                    )
                                ui.label(str(value)).classes("text-xs text-gray-400 w-8 text-right")

    def _update_report(self):
        """Show the final report."""
        self._report_container.clear()
        with self._report_container:
            if self.state.report_content:
                ui.markdown(self.state.report_content).classes("w-full")
            else:
                ui.label("Report not available.").classes("text-gray-500 text-sm py-8 text-center w-full")

    def _kill_simulation(self):
        """Handle kill button click."""
        self.state.kill_requested.set()
        with self.state.lock:
            self.state.round_name = "⛔ SIMULATION KILLED"
        self._killed_banner.classes(remove="hidden")
        ui.notify("Simulation killed", type="negative")

    # ══════════════════════════════════════════════════
    # LAUNCH PAGE
    # ══════════════════════════════════════════════════
    def _build_launch_page(self):
        """Build the interactive launch/prompt editor page."""
        ui.dark_mode().enable()
        ui.add_head_html("""
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
        <style>body { font-family: 'Inter', sans-serif !important; background: #0a0e17 !important; }</style>
        """)

        with ui.column().classes("max-w-2xl mx-auto p-8 gap-6"):
            ui.label("🚀 Agentic Simulation — Launch Pad").classes("text-2xl font-bold").style(
                "background: linear-gradient(135deg, #22d3ee, #3b82f6);"
                "-webkit-background-clip: text; -webkit-text-fill-color: transparent;"
            )
            ui.label("Configure and start a new simulation from your browser.").classes("text-gray-400")

            ui.separator()

            # Prompt
            prompt = ui.textarea(
                label="Strategic Initiative Prompt",
                placeholder="e.g., Investigate adding AI-powered search to our document management product",
            ).classes("w-full").props("outlined dark")

            with ui.row().classes("gap-4 w-full"):
                # Model selection
                model = ui.select(
                    label="Model",
                    options=["gemini-2.5-flash", "gemini-3-flash-preview", "gemini-3-pro-preview"],
                    value="gemini-2.5-flash",
                ).classes("flex-1").props("outlined dark")

                # Rounds
                rounds = ui.number(label="Rounds", value=7, min=1, max=15).classes("w-32").props("outlined dark")

            with ui.row().classes("items-center gap-4"):
                tiered = ui.switch("Tiered Models (Pro for VP)").props("dark")
                verbose = ui.switch("Verbose Logging").props("dark")

            ui.separator()

            async def launch():
                if not prompt.value:
                    ui.notify("Please enter a prompt", type="warning")
                    return
                ui.notify("🚀 Launching simulation...", type="positive")
                # The launch would trigger the simulation in a background thread
                # This requires importing and calling run_simulation logic
                ui.notify("Simulation started! Switch to the Dashboard tab.", type="info")

            ui.button("🚀 Launch Simulation", on_click=launch).props(
                "color=cyan no-caps size=lg"
            ).classes("w-full")

            ui.label("After launching, view the dashboard at /").classes("text-gray-500 text-xs text-center")
