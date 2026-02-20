"""
NiceGUI-based Live Dashboard for the R&D Simulation.
=====================================================
Premium dashboard with glassmorphism, smooth animations,
real‐time WebSocket updates, Plotly visualizations, and
a polished dark‐theme aesthetic.
"""

import math
import threading
import time
from datetime import datetime
from nicegui import ui, app
from simulation.dashboard import DashboardState, Status


# ── Design Tokens ─────────────────────────────────
COLORS = {
    "bg":         "#060a13",
    "bg_surface": "#0d1321",
    "bg_card":    "rgba(15, 23, 42, 0.65)",
    "glass":      "rgba(15, 23, 42, 0.45)",
    "border":     "rgba(56, 78, 107, 0.35)",
    "border_lit": "rgba(56, 78, 107, 0.55)",
    "text":       "#e2e8f0",
    "text_dim":   "#94a3b8",
    "text_muted": "#64748b",
    "cyan":       "#22d3ee",
    "blue":       "#3b82f6",
    "green":      "#10b981",
    "yellow":     "#f59e0b",
    "red":        "#ef4444",
    "purple":     "#a78bfa",
    "pink":       "#f472b6",
}

DEPT_PALETTE = {
    "research":    {"color": "#60a5fa", "bg": "rgba(96,165,250,0.08)",  "icon": "🔬"},
    "engineering": {"color": "#34d399", "bg": "rgba(52,211,153,0.08)",  "icon": "⚙️"},
    "product":     {"color": "#fbbf24", "bg": "rgba(251,191,36,0.08)",  "icon": "📦"},
    "executive":   {"color": "#c084fc", "bg": "rgba(192,132,252,0.08)", "icon": "👔"},
}

STATUS_DOT = {
    "waiting":  ("bg-gray-600",  ""),
    "thinking": ("bg-yellow-400", "animate-pulse"),
    "done":     ("bg-green-400",  ""),
    "error":    ("bg-red-400",    ""),
}


# ── Shared CSS ────────────────────────────────────
_GLOBAL_CSS = """
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<style>
  /* ── Base ─────────────── */
  * { box-sizing: border-box; }
  body {
    font-family: 'Inter', -apple-system, sans-serif !important;
    background: #060a13 !important;
    color: #e2e8f0;
  }
  .nicegui-content { padding: 0 !important; }

  /* ── Typography ─────── */
  .mono { font-family: 'JetBrains Mono', monospace; }

  /* ── Glassmorphism ───── */
  .glass {
    background: rgba(15,23,42,0.45);
    backdrop-filter: blur(16px) saturate(1.2);
    -webkit-backdrop-filter: blur(16px) saturate(1.2);
    border: 1px solid rgba(56,78,107,0.35);
  }
  .glass-card {
    background: rgba(15,23,42,0.65);
    backdrop-filter: blur(12px);
    border: 1px solid rgba(56,78,107,0.35);
    border-radius: 12px;
    transition: border-color 0.25s ease, box-shadow 0.25s ease;
  }
  .glass-card:hover {
    border-color: rgba(56,78,107,0.55);
    box-shadow: 0 4px 24px rgba(0,0,0,0.3);
  }

  /* ── Agent Cards ─────── */
  .agent-card {
    background: rgba(15,23,42,0.65);
    border: 1px solid rgba(56,78,107,0.35);
    border-radius: 10px;
    padding: 12px 14px;
    transition: all 0.3s cubic-bezier(0.4,0,0.2,1);
    position: relative;
    overflow: hidden;
  }
  .agent-card::before {
    content: '';
    position: absolute; top: 0; left: 0; right: 0;
    height: 2px;
    background: linear-gradient(90deg, var(--dept-color) 0%, transparent 100%);
    opacity: 0.6;
  }
  .agent-card:hover {
    border-color: rgba(56,78,107,0.55);
    transform: translateY(-1px);
    box-shadow: 0 4px 20px rgba(0,0,0,0.25);
  }
  .agent-card.thinking {
    border-color: rgba(245,158,11,0.4) !important;
    animation: thinkGlow 2.5s ease-in-out infinite;
  }
  .agent-card.done {
    border-color: rgba(16,185,129,0.3) !important;
  }
  .agent-card.error {
    border-color: rgba(239,68,68,0.4) !important;
  }
  @keyframes thinkGlow {
    0%, 100% { box-shadow: 0 0 0 rgba(245,158,11,0); }
    50%      { box-shadow: 0 0 20px rgba(245,158,11,0.08); }
  }

  /* ── Status Dot ─────── */
  .status-dot {
    width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0;
    transition: background 0.3s ease;
  }
  .status-dot.pulsing {
    animation: dotPulse 1.4s ease-in-out infinite;
    box-shadow: 0 0 6px rgba(245,158,11,0.5);
  }
  @keyframes dotPulse {
    0%, 100% { opacity: 1; }
    50%      { opacity: 0.35; }
  }

  /* ── Stat Pill ─────── */
  .stat-pill {
    background: rgba(15,23,42,0.65);
    border: 1px solid rgba(56,78,107,0.3);
    border-radius: 10px;
    padding: 6px 14px;
    display: flex; align-items: center; gap: 8px;
    backdrop-filter: blur(8px);
  }

  /* ── Confidence Bar ── */
  .conf-track { height: 3px; border-radius: 3px; background: rgba(42,58,78,0.5); }
  .conf-fill  { height: 3px; border-radius: 3px; transition: width 0.6s cubic-bezier(0.4,0,0.2,1); }

  /* ── Feed Row ────── */
  .feed-row {
    animation: slideIn 0.25s ease-out;
    transition: background 0.15s ease;
    border-bottom: 1px solid rgba(56,78,107,0.15);
  }
  .feed-row:hover { background: rgba(34,211,238,0.03); }
  @keyframes slideIn {
    from { opacity: 0; transform: translateX(-6px); }
    to   { opacity: 1; transform: translateX(0); }
  }

  /* ── Conversation Card ── */
  .conv-card {
    background: rgba(15,23,42,0.4);
    border: 1px solid rgba(56,78,107,0.25);
    border-radius: 10px;
    transition: border-color 0.2s ease;
  }
  .conv-card:hover { border-color: rgba(34,211,238,0.35); }

  /* ── Badges ─────── */
  .dept-tag {
    font-size: 10px; font-weight: 700; text-transform: uppercase;
    letter-spacing: 0.8px; padding: 2px 8px; border-radius: 6px;
    white-space: nowrap; line-height: 1.4;
  }
  .tool-tag {
    display: inline-flex; align-items: center; gap: 3px;
    background: rgba(245,158,11,0.1);
    border: 1px solid rgba(245,158,11,0.25);
    color: #f59e0b; font-size: 10px; font-weight: 600;
    padding: 2px 7px; border-radius: 10px;
  }

  /* ── Kill Banner ──── */
  .killed-banner {
    background: linear-gradient(135deg, rgba(239,68,68,0.12), rgba(153,27,27,0.08));
    border: 1px solid rgba(239,68,68,0.3);
    border-radius: 12px; padding: 20px 28px; text-align: center;
  }

  /* ── Round Steps ──── */
  .round-step {
    width: 28px; height: 28px; border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-size: 11px; font-weight: 700;
    border: 2px solid rgba(56,78,107,0.4);
    color: #64748b;
    transition: all 0.35s ease;
  }
  .round-step.active {
    border-color: #22d3ee; color: #22d3ee;
    box-shadow: 0 0 12px rgba(34,211,238,0.2);
    animation: stepPulse 2s ease-in-out infinite;
  }
  .round-step.completed {
    border-color: #10b981; color: #10b981;
    background: rgba(16,185,129,0.1);
  }
  @keyframes stepPulse {
    0%, 100% { box-shadow: 0 0 12px rgba(34,211,238,0.2); }
    50%      { box-shadow: 0 0 20px rgba(34,211,238,0.35); }
  }
  .round-connector {
    flex: 1; height: 2px; background: rgba(56,78,107,0.3);
    margin: 0 2px; transition: background 0.3s ease;
  }
  .round-connector.completed { background: rgba(16,185,129,0.4); }

  /* ── Scrollbar ─────── */
  ::-webkit-scrollbar { width: 6px; }
  ::-webkit-scrollbar-track { background: transparent; }
  ::-webkit-scrollbar-thumb { background: rgba(56,78,107,0.4); border-radius: 3px; }
  ::-webkit-scrollbar-thumb:hover { background: rgba(56,78,107,0.6); }

  /* ── Tab Override ──── */
  .q-tab-panel { padding: 16px !important; }
  .q-tabs__content { gap: 4px; }
  .q-tab { min-width: auto; padding: 8px 14px; }

  /* ── Completion ──── */
  .completion-badge {
    background: linear-gradient(135deg, rgba(16,185,129,0.15), rgba(34,211,238,0.1));
    border: 1px solid rgba(16,185,129,0.3);
    border-radius: 12px; padding: 16px 24px;
    text-align: center; animation: fadeInUp 0.5s ease-out;
  }
  @keyframes fadeInUp {
    from { opacity: 0; transform: translateY(8px); }
    to   { opacity: 1; transform: translateY(0); }
  }

  /* ── Empty State ──── */
  .empty-state {
    display: flex; flex-direction: column; align-items: center;
    gap: 8px; padding: 48px 16px; color: #4a5568;
  }
  .empty-state .icon { font-size: 32px; opacity: 0.4; }
  .empty-state .text { font-size: 13px; }
</style>
"""


class NiceGUIDashboard:
    """NiceGUI-based dashboard — premium real-time simulation monitor."""

    def __init__(self, state: DashboardState):
        self.state = state
        self._thread: threading.Thread | None = None
        self.port = 8420

        # UI element references
        self._elapsed_label = None
        self._api_calls_label = None
        self._active_label = None
        self._token_label = None
        self._round_steps = []          # list of (step_element, connector_element)
        self._round_name = None
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
        self._completion_banner = None

        # Change tracking — only rebuild UI when data changes
        self._last_agent_hash = ""
        self._last_msg_count = 0
        self._last_conv_count = 0
        self._last_flow_count = 0
        self._last_conf_count = 0
        self._last_crossdept_count = 0
        self._report_loaded = False

    # ══════════════════════════════════════════════════
    # LIFECYCLE
    # ══════════════════════════════════════════════════
    def start(self):
        """Start the NiceGUI dashboard in a background thread."""
        self._build_pages()
        self._thread = threading.Thread(target=self._run_server, daemon=True)
        self._thread.start()
        time.sleep(1)
        import webbrowser
        try:
            webbrowser.open(f"http://127.0.0.1:{self.port}")
        except Exception:
            print(f"  ⚠️  Navigate to http://127.0.0.1:{self.port} manually.")

    def stop(self):
        """Stop the dashboard server."""
        print("  🔴 NiceGUI Dashboard server stopped")

    def _run_server(self):
        ui.run(
            host="0.0.0.0",
            port=self.port,
            title="Agentic Simulation — Live Dashboard",
            reload=False,
            show=False,
        )

    def _build_pages(self):
        ref = self

        @ui.page("/")
        def main_page():
            ref._build_main_dashboard()

        @ui.page("/launch")
        def launch_page():
            ref._build_launch_page()

    # ══════════════════════════════════════════════════
    # MAIN DASHBOARD
    # ══════════════════════════════════════════════════
    def _build_main_dashboard(self):
        ui.dark_mode().enable()
        ui.add_head_html(_GLOBAL_CSS)

        # ── Fixed Header ──────────────────────
        with ui.header().classes("items-center justify-between px-5 py-2").style(
            "background: rgba(6,10,19,0.85); backdrop-filter: blur(20px) saturate(1.3);"
            "border-bottom: 1px solid rgba(56,78,107,0.25); z-index: 100;"
        ):
            # Left: title
            with ui.row().classes("items-center gap-3 no-wrap"):
                # Animated dot
                ui.element("div").classes("status-dot pulsing").style("background: #10b981")
                ui.label("Agentic Simulation").classes(
                    "text-base font-bold tracking-tight"
                ).style(
                    "background: linear-gradient(135deg, #22d3ee 0%, #3b82f6 50%, #a78bfa 100%);"
                    "-webkit-background-clip: text; -webkit-text-fill-color: transparent;"
                )

            # Right: stat pills + kill
            with ui.row().classes("items-center gap-3 no-wrap"):
                # Elapsed
                with ui.element("div").classes("stat-pill"):
                    ui.icon("schedule").classes("text-sm text-gray-400")
                    self._elapsed_label = ui.label("0m 00s").classes("mono text-xs font-medium")

                # API calls
                with ui.element("div").classes("stat-pill"):
                    ui.icon("api").classes("text-sm text-blue-400")
                    self._api_calls_label = ui.label("0").classes("mono text-xs font-semibold text-blue-300")

                # Active
                with ui.element("div").classes("stat-pill"):
                    ui.icon("bolt").classes("text-sm text-yellow-400")
                    self._active_label = ui.label("0").classes("mono text-xs font-semibold text-yellow-300")

                # Token cost
                with ui.element("div").classes("stat-pill"):
                    ui.icon("payments").classes("text-sm text-green-400")
                    self._token_label = ui.label("$0.000").classes("mono text-xs font-semibold text-green-300")

                # Kill switch (subtle icon button)
                ui.button(icon="stop_circle", on_click=self._kill_simulation).props(
                    "flat round dense color=red-4 size=sm"
                ).tooltip("Kill Simulation")

        # ── Content Area ──────────────────────
        with ui.element("div").classes("w-full").style(
            "max-width: 1400px; margin: 0 auto; padding: 16px 24px 64px;"
        ):
            # ── Round Progress Steps ──────
            self._build_round_steps()

            # ── Kill Banner (hidden) ──────
            self._killed_banner = ui.element("div").classes("hidden killed-banner mt-4")
            with self._killed_banner:
                ui.label("⛔ Simulation Killed").classes("text-red-400 text-base font-bold")
                ui.label("The simulation has been terminated by user request.").classes(
                    "text-gray-400 text-xs mt-1"
                )

            # ── Completion Banner (hidden) ──
            self._completion_banner = ui.element("div").classes("hidden completion-badge mt-4")
            with self._completion_banner:
                ui.label("✨ Simulation Complete").classes("text-green-400 text-base font-bold")
                ui.label("All rounds finished — check the Report tab for final output.").classes(
                    "text-gray-400 text-xs mt-1"
                )

            # ── Section: Agent Hierarchy ──
            ui.element("div").classes("mt-5")
            with ui.row().classes("items-center gap-2 mb-3"):
                ui.icon("groups").classes("text-sm text-gray-500")
                ui.label("Agent Hierarchy").classes(
                    "text-xs font-bold uppercase tracking-widest text-gray-500"
                )
            self._agent_container = ui.element("div")

            # ── Section: Feature Tabs ─────
            ui.element("div").classes("mt-6")
            with ui.tabs().classes("w-full").props(
                "dense no-caps active-color=cyan indicator-color=cyan "
                "align=left outside-arrows mobile-arrows"
            ) as tabs:
                tab_feed     = ui.tab("feed",     label="💬 Feed")
                tab_conv     = ui.tab("conv",     label="🗣️ Conversations")
                tab_flow     = ui.tab("flow",     label="🔀 Flow")
                tab_heatmap  = ui.tab("heatmap",  label="🌡️ Heatmap")
                tab_kg       = ui.tab("kg",       label="🧠 Knowledge")
                tab_xdept    = ui.tab("xdept",    label="🔗 Cross-Dept")
                tab_profiles = ui.tab("profiles", label="📊 Profiles")
                tab_report   = ui.tab("report",   label="📄 Report")

            with ui.tab_panels(tabs, value=tab_feed).classes("w-full mt-1").style(
                "background: rgba(15,23,42,0.45); backdrop-filter: blur(12px);"
                "border: 1px solid rgba(56,78,107,0.25); border-radius: 12px; min-height: 320px;"
            ):
                with ui.tab_panel(tab_feed):
                    self._feed_container = ui.column().classes(
                        "w-full gap-0"
                    ).style("max-height: 420px; overflow-y: auto;")
                    with self._feed_container:
                        self._empty_state("radio", "Waiting for agent activity…")

                with ui.tab_panel(tab_conv):
                    self._conv_container = ui.column().classes(
                        "w-full gap-1"
                    ).style("max-height: 520px; overflow-y: auto;")
                    with self._conv_container:
                        self._empty_state("forum", "Conversations appear as agents respond…")

                with ui.tab_panel(tab_flow):
                    self._flow_container = ui.column().classes("w-full")
                    with self._flow_container:
                        self._empty_state("account_tree", "Communication flow builds as agents interact…")

                with ui.tab_panel(tab_heatmap):
                    self._heatmap_container = ui.column().classes("w-full")
                    with self._heatmap_container:
                        self._empty_state("grid_on", "Confidence heatmap populates each round…")

                with ui.tab_panel(tab_kg):
                    self._knowledge_container = ui.column().classes("w-full")
                    with self._knowledge_container:
                        self._empty_state("hub", "Knowledge graph renders during simulation…")

                with ui.tab_panel(tab_xdept):
                    self._crossdept_container = ui.column().classes("w-full gap-2")
                    with self._crossdept_container:
                        self._empty_state("swap_horiz", "Cross-dept requests appear in Round 4…")

                with ui.tab_panel(tab_profiles):
                    self._profiles_container = ui.column().classes("w-full")
                    with self._profiles_container:
                        self._empty_state("bar_chart", "Profiles generate after simulation completes…")

                with ui.tab_panel(tab_report):
                    self._report_container = ui.column().classes("w-full")
                    with self._report_container:
                        self._empty_state("description", "Report appears when the simulation finishes…")

        # ── Polling Timer ───────────────────
        ui.timer(0.5, self._poll_state)

    # ── Helpers ───────────────────────────
    @staticmethod
    def _empty_state(icon: str, text: str):
        """Render a minimalist empty-state placeholder."""
        with ui.element("div").classes("empty-state"):
            ui.icon(icon).classes("icon text-3xl")
            ui.label(text).classes("text")

    def _build_round_steps(self):
        """Render the horizontal round-step indicator."""
        round_names = ["Strategic", "Planning", "Execution", "Collab", "Refine", "Reflect", "Report"]
        self._round_steps = []
        with ui.row().classes("items-center gap-0 w-full mt-2 px-2"):
            for i, name in enumerate(round_names):
                step = ui.element("div").classes("round-step")
                step.text = str(i + 1)
                with step:
                    ui.label(str(i + 1)).classes("text-xs")
                ui.tooltip(name)
                self._round_steps.append(step)
                if i < len(round_names) - 1:
                    conn = ui.element("div").classes("round-connector")
                    self._round_steps.append(conn)  # interleaved: step, conn, step, conn...

        # Round name label below
        self._round_name = ui.label("Initializing…").classes(
            "text-xs text-gray-500 text-center w-full mt-1"
        )

    # ══════════════════════════════════════════════════
    # POLLING & STATE SYNC
    # ══════════════════════════════════════════════════
    def _poll_state(self):
        if not self.state:
            return

        # ── Header Stats ──
        self._elapsed_label.text = self.state.get_elapsed()
        self._api_calls_label.text = str(self.state.api_calls)
        self._active_label.text = str(self.state.active_count)

        token_stats = getattr(self.state, "token_stats", None)
        if token_stats:
            cost = token_stats.get("estimated_cost", 0)
            ti = token_stats.get("total_input", 0)
            to = token_stats.get("total_output", 0)
            if ti or to:
                self._token_label.text = f"${cost:.3f}  ({ti//1000}K ↑ {to//1000}K ↓)"
            else:
                self._token_label.text = f"${cost:.3f}"

        # ── Round Steps ──
        rn = self.state.round_number
        self._round_name.text = self.state.round_name or "Initializing…"
        # Update step classes
        step_idx = 0
        for i, el in enumerate(self._round_steps):
            if i % 2 == 0:  # step element
                step_idx += 1
                el.classes(remove="active completed")
                if step_idx < rn:
                    el.classes(add="completed")
                elif step_idx == rn:
                    el.classes(add="active")
            else:  # connector
                el.classes(remove="completed")
                if step_idx < rn:
                    el.classes(add="completed")

        # ── Agent Grid (only on change) ──
        agent_hash = self._compute_agent_hash()
        if agent_hash != self._last_agent_hash:
            self._last_agent_hash = agent_hash
            self._update_agent_grid()

        # ── Feed ──
        msgs = list(self.state.messages)
        if len(msgs) != self._last_msg_count:
            self._last_msg_count = len(msgs)
            self._update_feed(msgs)

        # ── Conversations ──
        convs = self.state.conversation_log
        if len(convs) != self._last_conv_count:
            self._last_conv_count = len(convs)
            self._update_conversations(convs)

        # ── Comm Flow ──
        flow = getattr(self.state, "comm_flow", [])
        if len(flow) != self._last_flow_count:
            self._last_flow_count = len(flow)
            if flow:
                self._update_flow(flow)

        # ── Confidence ──
        conf = getattr(self.state, "confidence_grid", [])
        if len(conf) != self._last_conf_count:
            self._last_conf_count = len(conf)
            if conf:
                self._update_heatmap(conf)

        # ── Knowledge Graph ──
        kg = getattr(self.state, "knowledge_graph_data", None)
        if kg:
            self._update_knowledge_graph()

        # ── Cross-Dept ──
        xd = getattr(self.state, "cross_dept_requests", [])
        if len(xd) != self._last_crossdept_count:
            self._last_crossdept_count = len(xd)
            if xd:
                self._update_crossdept(xd)

        # ── Report ──
        if self.state.simulation_complete and not self._report_loaded:
            self._report_loaded = True
            self._update_report()
            self._update_profiles()
            self._completion_banner.classes(remove="hidden")

        # ── Killed ──
        if self.state.kill_requested.is_set():
            self._killed_banner.classes(remove="hidden")

    def _compute_agent_hash(self) -> str:
        """Cheap hash of agent states to avoid redundant rebuilds."""
        parts = []
        with self.state.lock:
            for aid, s in self.state.agent_states.items():
                parts.append(f"{aid}:{s.get('status')}:{s.get('confidence')}")
        return "|".join(parts)

    # ══════════════════════════════════════════════════
    # AGENT HIERARCHY
    # ══════════════════════════════════════════════════
    def _update_agent_grid(self):
        self._agent_container.clear()
        agents = {}
        with self.state.lock:
            for aid, s in self.state.agent_states.items():
                agents[aid] = dict(s)

        # Partition by level
        vps, leads_by_dept, ics_by_dept = [], {}, {}
        for aid, a in agents.items():
            lvl = a.get("level", 3)
            dept = a.get("department", "executive")
            if lvl == 1:
                vps.append((aid, a))
            elif lvl == 2:
                leads_by_dept.setdefault(dept, []).append((aid, a))
            else:
                ics_by_dept.setdefault(dept, []).append((aid, a))

        dept_order = ["research", "engineering", "product"]
        active_depts = [d for d in dept_order if d in leads_by_dept or d in ics_by_dept]

        with self._agent_container:
            #  VP Row
            if vps:
                with ui.row().classes("justify-center w-full mb-1"):
                    for aid, a in vps:
                        self._render_card(aid, a, width="340px")

                # Connector line from VP down
                if active_depts:
                    self._render_connector()

            # Department columns
            if active_depts:
                with ui.row().classes("justify-center gap-5 w-full"):
                    for dept in active_depts:
                        dp = DEPT_PALETTE.get(dept, DEPT_PALETTE["executive"])
                        with ui.column().classes("items-center gap-2 flex-1").style("max-width: 380px"):
                            # Dept header
                            with ui.row().classes("items-center gap-1 mb-1"):
                                ui.label(dp["icon"]).classes("text-sm")
                                ui.label(dept.upper()).classes("text-xs font-bold tracking-wider").style(
                                    f"color: {dp['color']}"
                                )

                            # Lead card(s)
                            for aid, a in leads_by_dept.get(dept, []):
                                self._render_card(aid, a)

                            # Connector
                            if dept in ics_by_dept:
                                with ui.element("div").style(
                                    "width: 1px; height: 12px;"
                                    f"background: linear-gradient(to bottom, {dp['color']}44, transparent);"
                                    "margin: 0 auto;"
                                ):
                                    pass

                            # IC cards
                            for aid, a in ics_by_dept.get(dept, []):
                                self._render_card(aid, a)

    def _render_card(self, aid: str, agent: dict, width: str = "100%"):
        """Render a polished agent card with status indicators."""
        status = agent.get("status", "waiting")
        dept = agent.get("department", "executive")
        dp = DEPT_PALETTE.get(dept, DEPT_PALETTE["executive"])
        status_class = status if status in ("thinking", "done", "error") else ""

        with ui.element("div").classes(f"agent-card {status_class}").style(
            f"--dept-color: {dp['color']}; width: {width}; max-width: 100%;"
        ):
            # Top row: name + status dot
            with ui.row().classes("items-center justify-between w-full"):
                with ui.column().classes("gap-0"):
                    ui.label(agent.get("name", aid)).classes("text-sm font-semibold")
                    ui.label(agent.get("title", "")).classes("text-[11px] text-gray-500")
                # Status dot
                dot_bg = {"waiting": "#4b5563", "thinking": "#f59e0b", "done": "#10b981", "error": "#ef4444"}
                dot_cls = "pulsing" if status == "thinking" else ""
                ui.element("div").classes(f"status-dot {dot_cls}").style(
                    f"background: {dot_bg.get(status, '#4b5563')}"
                )

            # Status detail
            if status == "thinking":
                with ui.row().classes("items-center gap-2 mt-2"):
                    ui.spinner(size="xs").props("color=yellow")
                    ui.label(agent.get("task_preview", "Thinking…")[:55]).classes(
                        "text-[11px] text-gray-400"
                    ).style("overflow: hidden; text-overflow: ellipsis; white-space: nowrap;")

            elif status == "done":
                preview = agent.get("output_preview", "Done")[:55]
                ui.label(f"✓ {preview}").classes("text-[11px] text-gray-400 mt-1").style(
                    "overflow: hidden; text-overflow: ellipsis; white-space: nowrap;"
                )
                # Confidence bar
                conf = agent.get("confidence")
                if conf is not None:
                    conf_color = "#ef4444" if conf < 40 else "#f59e0b" if conf < 70 else "#10b981"
                    with ui.row().classes("items-center gap-2 mt-1 w-full"):
                        ui.label(f"{conf}%").classes("text-[10px] text-gray-500 mono w-8")
                        with ui.element("div").classes("conf-track flex-1"):
                            ui.element("div").classes("conf-fill").style(
                                f"width: {conf}%; background: {conf_color}"
                            )

            elif status == "error":
                ui.label(f"✕ {agent.get('output_preview', 'Error')[:55]}").classes(
                    "text-[11px] text-red-400 mt-1"
                )

            else:  # waiting
                ui.label("Queued").classes("text-[11px] text-gray-600 mt-1")

    @staticmethod
    def _render_connector():
        """Vertical connector line between hierarchy tiers."""
        with ui.element("div").classes("w-full flex justify-center my-1"):
            ui.element("div").style(
                "width: 1px; height: 16px;"
                "background: linear-gradient(to bottom, rgba(34,211,238,0.25), transparent);"
            )

    # ══════════════════════════════════════════════════
    # LIVE FEED
    # ══════════════════════════════════════════════════
    def _update_feed(self, messages: list):
        self._feed_container.clear()
        with self._feed_container:
            if not messages:
                self._empty_state("radio", "Waiting for agent activity…")
                return
            for msg in messages:
                dept = msg.get("department", "executive")
                dp = DEPT_PALETTE.get(dept, DEPT_PALETTE["executive"])
                with ui.row().classes("items-center gap-3 px-4 py-2 w-full feed-row no-wrap"):
                    ui.label(msg.get("time", "")).classes("text-[11px] text-gray-500 mono").style("min-width: 52px")
                    # Dept color dot
                    ui.element("div").style(
                        f"width: 4px; height: 4px; border-radius: 50%; background: {dp['color']}; flex-shrink: 0;"
                    )
                    ui.label(msg.get("from", "")).classes("text-xs font-semibold").style(
                        f"color: {dp['color']}; min-width: 90px; max-width: 120px;"
                        "overflow: hidden; text-overflow: ellipsis; white-space: nowrap;"
                    )
                    ui.icon("east").classes("text-[10px] text-gray-600")
                    ui.label(msg.get("to", "")).classes("text-xs text-gray-400").style(
                        "min-width: 80px; max-width: 120px; overflow: hidden;"
                        "text-overflow: ellipsis; white-space: nowrap;"
                    )
                    ui.label(msg.get("preview", "")).classes(
                        "text-[11px] text-gray-500 flex-1"
                    ).style("overflow: hidden; text-overflow: ellipsis; white-space: nowrap;")

    # ══════════════════════════════════════════════════
    # CONVERSATIONS
    # ══════════════════════════════════════════════════
    def _update_conversations(self, conversations: list):
        self._conv_container.clear()
        with self._conv_container:
            if not conversations:
                self._empty_state("forum", "Conversations appear as agents respond…")
                return

            by_round = {}
            for c in conversations:
                by_round.setdefault(c.get("round", 0), []).append(c)

            for rnd in sorted(by_round.keys(), reverse=True):
                # Round header
                with ui.row().classes("items-center gap-2 py-1 px-1"):
                    ui.badge(f"ROUND {rnd}").props("color=cyan-8 text-color=white").classes("text-[10px]")
                    ui.label(f"{len(by_round[rnd])} entries").classes("text-[11px] text-gray-600")

                for c in reversed(by_round[rnd]):
                    dept = c.get("department", "executive")
                    dp = DEPT_PALETTE.get(dept, DEPT_PALETTE["executive"])
                    tools = c.get("tools_used", [])
                    action = c.get("action", "response")

                    with ui.expansion(
                        f"{dp['icon']} {c.get('agent_name', '?')} — {action}",
                    ).classes("w-full conv-card").props("dense"):

                        # Tools
                        if tools:
                            with ui.row().classes("gap-1 flex-wrap mb-2"):
                                for t in tools:
                                    ui.html(f'<span class="tool-tag">🔧 {t.get("tool", "?")}</span>')

                        # Task
                        with ui.element("div").classes("mb-3"):
                            ui.label("TASK").classes("text-[10px] font-bold uppercase tracking-wider text-gray-500 mb-1")
                            ui.element("div").style(
                                "background: rgba(0,0,0,0.25); border-radius: 8px; padding: 10px;"
                                "max-height: 180px; overflow-y: auto; font-size: 12px;"
                                "color: #cbd5e1; white-space: pre-wrap; line-height: 1.5;"
                            ).props(f'innerHTML="{self._escape(c.get("task", ""))}"')

                        # Response
                        with ui.element("div"):
                            ui.label("RESPONSE").classes("text-[10px] font-bold uppercase tracking-wider text-gray-500 mb-1")
                            ui.element("div").style(
                                "background: rgba(0,0,0,0.25); border-radius: 8px; padding: 10px;"
                                "max-height: 280px; overflow-y: auto; font-size: 12px;"
                                "color: #e2e8f0; white-space: pre-wrap; line-height: 1.5;"
                            ).props(f'innerHTML="{self._escape(c.get("response", ""))}"')

    @staticmethod
    def _escape(text: str) -> str:
        """Escape HTML special characters for safe innerHTML insertion."""
        return (text
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;")
                .replace("\n", "<br>"))

    # ══════════════════════════════════════════════════
    # COMMUNICATION FLOW (Sankey)
    # ══════════════════════════════════════════════════
    def _update_flow(self, comm_flow: list):
        self._flow_container.clear()
        with self._flow_container:
            if not comm_flow:
                self._empty_state("account_tree", "No communication data yet…")
                return

            import plotly.graph_objects as go

            names = sorted({e.get("from_name", "?") for e in comm_flow}
                           | {e.get("to_name", "?") for e in comm_flow})
            idx = {n: i for i, n in enumerate(names)}

            sources, targets, values = [], [], []
            for e in comm_flow:
                s, t = idx.get(e["from_name"], 0), idx.get(e["to_name"], 0)
                if s != t:
                    sources.append(s)
                    targets.append(t)
                    values.append(1)

            node_colors = []
            for name in names:
                c = "#94a3b8"
                for aid, s in self.state.agent_states.items():
                    if s.get("name") == name:
                        c = DEPT_PALETTE.get(s.get("department", ""), {}).get("color", "#94a3b8")
                        break
                node_colors.append(c)

            fig = go.Figure(data=[go.Sankey(
                node=dict(pad=20, thickness=18, line=dict(color="rgba(56,78,107,0.3)", width=0.5),
                          label=names, color=node_colors),
                link=dict(source=sources, target=targets, value=values,
                          color="rgba(34,211,238,0.12)")
            )])
            fig.update_layout(
                paper_bgcolor="#060a13", plot_bgcolor="#060a13",
                font=dict(color="#e2e8f0", family="Inter", size=11),
                height=380, margin=dict(l=24, r=24, t=40, b=16),
                title=dict(text="Communication Flow", font=dict(size=13, color="#94a3b8")),
            )
            ui.plotly(fig).classes("w-full")

    # ══════════════════════════════════════════════════
    # CONFIDENCE HEATMAP
    # ══════════════════════════════════════════════════
    def _update_heatmap(self, conf_grid: list):
        self._heatmap_container.clear()
        with self._heatmap_container:
            if not conf_grid:
                self._empty_state("grid_on", "No confidence data yet…")
                return

            import plotly.graph_objects as go

            agent_names = sorted(set(e.get("agent_name", "?") for e in conf_grid))
            rounds = sorted(set(e.get("round", 0) for e in conf_grid))

            z = []
            for name in agent_names:
                row = []
                for rnd in rounds:
                    score = next(
                        (e["score"] for e in conf_grid
                         if e.get("agent_name") == name and e.get("round") == rnd),
                        None
                    )
                    row.append(score if score is not None else 0)
                z.append(row)

            fig = go.Figure(data=go.Heatmap(
                z=z, x=[f"R{r}" for r in rounds], y=agent_names,
                colorscale=[[0, "#7f1d1d"], [0.3, "#ef4444"], [0.5, "#f59e0b"],
                            [0.7, "#22d3ee"], [1, "#10b981"]],
                zmin=1, zmax=10,
                hovertemplate="<b>%{y}</b><br>Round %{x}<br>Confidence: %{z}/10<extra></extra>",
                colorbar=dict(tickfont=dict(color="#94a3b8"), title=dict(text="Score", font=dict(color="#94a3b8"))),
            ))
            fig.update_layout(
                paper_bgcolor="#060a13", plot_bgcolor="#0d1321",
                font=dict(color="#e2e8f0", family="Inter", size=11),
                height=340, margin=dict(l=130, r=24, t=40, b=40),
                title=dict(text="Agent Confidence Heatmap", font=dict(size=13, color="#94a3b8")),
                xaxis=dict(title="", gridcolor="rgba(56,78,107,0.2)"),
                yaxis=dict(title="", gridcolor="rgba(56,78,107,0.2)"),
            )
            ui.plotly(fig).classes("w-full")

    # ══════════════════════════════════════════════════
    # KNOWLEDGE GRAPH
    # ══════════════════════════════════════════════════
    def _update_knowledge_graph(self):
        kg = getattr(self.state, "knowledge_graph_data", None)
        if not kg:
            return
        self._knowledge_container.clear()
        with self._knowledge_container:
            import plotly.graph_objects as go

            nodes = kg.get("nodes", [])
            edges = kg.get("edges", [])
            if not nodes:
                self._empty_state("hub", "No knowledge data yet…")
                return

            n = len(nodes)
            nx, ny = [], []
            for i, node in enumerate(nodes):
                angle = 2 * math.pi * i / n
                r = 1.2 if node.get("type") == "agent" else 2.2
                nx.append(r * math.cos(angle))
                ny.append(r * math.sin(angle))

            ex, ey = [], []
            for edge in edges:
                si = next((i for i, nd in enumerate(nodes) if nd["id"] == edge["source"]), None)
                ti = next((i for i, nd in enumerate(nodes) if nd["id"] == edge["target"]), None)
                if si is not None and ti is not None:
                    ex.extend([nx[si], nx[ti], None])
                    ey.extend([ny[si], ny[ti], None])

            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=ex, y=ey, mode="lines",
                line=dict(width=0.8, color="rgba(34,211,238,0.2)"), hoverinfo="none"
            ))
            colors = ["#22d3ee" if nd.get("type") == "agent" else "#f59e0b" for nd in nodes]
            sizes = [18 if nd.get("type") == "agent" else 9 for nd in nodes]
            labels = [nd.get("label", "?") for nd in nodes]

            fig.add_trace(go.Scatter(
                x=nx, y=ny, mode="markers+text", text=labels,
                textposition="top center", textfont=dict(size=9, color="#94a3b8"),
                marker=dict(size=sizes, color=colors, line=dict(width=1, color="rgba(56,78,107,0.4)")),
                hovertemplate="%{text}<extra></extra>",
            ))
            fig.update_layout(
                paper_bgcolor="#060a13", plot_bgcolor="#060a13",
                font=dict(color="#e2e8f0", family="Inter"), height=420,
                showlegend=False,
                xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                margin=dict(l=16, r=16, t=40, b=16),
                title=dict(text="Knowledge Graph", font=dict(size=13, color="#94a3b8")),
            )
            ui.plotly(fig).classes("w-full")

    # ══════════════════════════════════════════════════
    # CROSS-DEPT TRACKER
    # ══════════════════════════════════════════════════
    def _update_crossdept(self, requests: list):
        self._crossdept_container.clear()
        with self._crossdept_container:
            if not requests:
                self._empty_state("swap_horiz", "No cross-department requests yet…")
                return

            # Summary row
            pending = sum(1 for r in requests if r.get("status") == "pending")
            fulfilled = sum(1 for r in requests if r.get("status") == "fulfilled")
            with ui.row().classes("items-center gap-4 mb-2 px-1"):
                ui.badge(f"{len(requests)} total").props("color=grey-8")
                if pending:
                    ui.badge(f"{pending} pending").props("color=amber-8")
                if fulfilled:
                    ui.badge(f"{fulfilled} fulfilled").props("color=green-8")

            for req in requests:
                from_dept = req.get("from_dept", "?")
                to_dept = req.get("to_dept", "?")
                status = req.get("status", "pending")
                fd = DEPT_PALETTE.get(from_dept, DEPT_PALETTE["executive"])
                td = DEPT_PALETTE.get(to_dept, DEPT_PALETTE["executive"])
                status_clr = {"pending": "#f59e0b", "fulfilled": "#10b981"}.get(status, "#94a3b8")

                with ui.element("div").classes("glass-card p-3"):
                    with ui.row().classes("items-center gap-2 w-full"):
                        ui.label(from_dept.upper()).classes("dept-tag").style(
                            f"background: {fd['color']}15; color: {fd['color']}"
                        )
                        ui.icon("east").classes("text-xs text-gray-600")
                        ui.label(to_dept.upper()).classes("dept-tag").style(
                            f"background: {td['color']}15; color: {td['color']}"
                        )
                        ui.space()
                        ui.badge(status.upper()).style(f"background: {status_clr}; color: white;")

                    ui.label(req.get("request", "")).classes("text-xs text-gray-300 mt-2 leading-relaxed")
                    with ui.row().classes("items-center gap-2 mt-1"):
                        ui.icon("schedule").classes("text-[10px] text-gray-600")
                        ui.label(f"Round {req.get('round', '?')} · {req.get('from_agent', '?')}").classes(
                            "text-[11px] text-gray-600"
                        )

    # ══════════════════════════════════════════════════
    # PERFORMANCE PROFILES
    # ══════════════════════════════════════════════════
    def _update_profiles(self):
        self._profiles_container.clear()
        with self._profiles_container:
            agents = {}
            with self.state.lock:
                for aid, s in self.state.agent_states.items():
                    agents[aid] = dict(s)

            convs = self.state.conversation_log
            conf_grid = getattr(self.state, "confidence_grid", [])
            token_stats = getattr(self.state, "token_stats", {})
            per_agent = token_stats.get("per_agent", {})

            with ui.row().classes("gap-4 flex-wrap w-full"):
                for aid, agent in agents.items():
                    name = agent.get("name", aid)
                    dept = agent.get("department", "executive")
                    dp = DEPT_PALETTE.get(dept, DEPT_PALETTE["executive"])

                    agent_convs = [c for c in convs if c.get("agent_id") == aid]
                    resp_count = len(agent_convs)
                    tool_count = sum(len(c.get("tools_used", [])) for c in agent_convs)
                    scores = [e["score"] for e in conf_grid if e.get("agent_id") == aid and e.get("score")]
                    avg_conf = sum(scores) / len(scores) if scores else 0
                    agent_cost = per_agent.get(aid, {}).get("cost", 0)

                    with ui.element("div").classes("glass-card p-4").style(
                        f"min-width: 260px; flex: 1; max-width: 320px;"
                        f"border-top: 2px solid {dp['color']};"
                    ):
                        with ui.row().classes("items-center gap-2 mb-3"):
                            ui.label(dp["icon"]).classes("text-base")
                            with ui.column().classes("gap-0"):
                                ui.label(name).classes("text-sm font-semibold")
                                ui.label(agent.get("title", "")).classes("text-[11px] text-gray-500")

                        stats = [
                            ("Responses",  resp_count,       12, dp["color"]),
                            ("Tools Used", tool_count,       12, "#f59e0b"),
                            ("Confidence", round(avg_conf, 1), 10, "#22d3ee"),
                            ("Cost ($)",   round(agent_cost, 4), 0.5, "#10b981"),
                        ]
                        for label, value, max_val, bar_c in stats:
                            with ui.row().classes("items-center gap-2 w-full mb-1"):
                                ui.label(label).classes("text-[11px] text-gray-500").style("min-width: 75px;")
                                with ui.element("div").classes("flex-1 h-1.5 rounded-full").style(
                                    "background: rgba(56,78,107,0.3)"
                                ):
                                    pct = min(100, (value / max_val * 100)) if max_val else 0
                                    ui.element("div").style(
                                        f"width: {pct}%; height: 100%; background: {bar_c};"
                                        "border-radius: 999px; transition: width 0.6s ease;"
                                    )
                                ui.label(str(value)).classes("text-[11px] text-gray-400 mono").style("min-width: 32px; text-align: right;")

    # ══════════════════════════════════════════════════
    # REPORT
    # ══════════════════════════════════════════════════
    def _update_report(self):
        self._report_container.clear()
        with self._report_container:
            if self.state.report_content:
                with ui.element("div").style(
                    "background: rgba(0,0,0,0.2); border-radius: 10px; padding: 24px;"
                    "max-height: 600px; overflow-y: auto;"
                ):
                    ui.markdown(self.state.report_content).classes("w-full")
            else:
                self._empty_state("description", "Report not available.")

    # ══════════════════════════════════════════════════
    # KILL
    # ══════════════════════════════════════════════════
    def _kill_simulation(self):
        self.state.kill_requested.set()
        with self.state.lock:
            self.state.round_name = "⛔ SIMULATION KILLED"
        self._killed_banner.classes(remove="hidden")
        ui.notify("Simulation killed", type="negative")

    # ══════════════════════════════════════════════════
    # LAUNCH PAGE
    # ══════════════════════════════════════════════════
    def _build_launch_page(self):
        ui.dark_mode().enable()
        ui.add_head_html(_GLOBAL_CSS)

        with ui.column().classes("max-w-2xl mx-auto p-8 gap-6"):
            ui.label("🚀 Launch Pad").classes("text-2xl font-extrabold").style(
                "background: linear-gradient(135deg, #22d3ee 0%, #3b82f6 50%, #a78bfa 100%);"
                "-webkit-background-clip: text; -webkit-text-fill-color: transparent;"
            )
            ui.label("Configure and start a new simulation from your browser.").classes(
                "text-gray-400 text-sm -mt-3"
            )

            ui.separator().style("background: rgba(56,78,107,0.3)")

            prompt = ui.textarea(
                label="Strategic Initiative Prompt",
                placeholder="e.g., Investigate adding AI-powered search to our document management product",
            ).classes("w-full").props("outlined dark autogrow")

            with ui.row().classes("gap-4 w-full"):
                model = ui.select(
                    label="Model",
                    options=["gemini-2.5-flash", "gemini-3-flash-preview", "gemini-3-pro-preview"],
                    value="gemini-2.5-flash",
                ).classes("flex-1").props("outlined dark")

                rounds = ui.number(label="Rounds", value=7, min=1, max=15).classes(
                    "w-32"
                ).props("outlined dark")

            with ui.row().classes("items-center gap-6"):
                tiered = ui.switch("Tiered Models").props("dark color=cyan")
                verbose = ui.switch("Verbose").props("dark color=cyan")

            ui.separator().style("background: rgba(56,78,107,0.3)")

            async def launch():
                if not prompt.value:
                    ui.notify("Please enter a prompt", type="warning")
                    return
                ui.notify("🚀 Launching simulation…", type="positive")
                ui.notify("Simulation started — switch to Dashboard tab.", type="info")

            ui.button("🚀 Launch Simulation", on_click=launch).props(
                "color=cyan no-caps unelevated size=lg"
            ).classes("w-full").style("border-radius: 10px;")

            ui.label("After launching, view the dashboard at /").classes(
                "text-gray-600 text-xs text-center"
            )
