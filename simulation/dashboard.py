"""
Web-Based Live Dashboard for R&D Simulation.
Opens a real-time dashboard in the user's browser.

Architecture:
  - Python http.server serves an HTML dashboard + /api/state JSON endpoint
  - Browser polls /api/state every 500ms for real-time updates
  - JavaScript updates the DOM with smooth animations
  - Zero new pip dependencies — uses only Python stdlib

Usage:
  The engine starts WebDashboard.start() which launches the server
  and auto-opens the browser. The simulation engine updates the shared
  DashboardState object, which the HTTP handler reads and serves as JSON.
"""

import json
import os
import socket
import threading
import time
import webbrowser
from datetime import datetime
from collections import deque
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse


# ── Agent Status Constants ────────────────────────

class Status:
    WAITING = "waiting"
    THINKING = "thinking"
    DONE = "done"
    ERROR = "error"


# ── Thread-Safe Dashboard State ───────────────────

class DashboardState:
    """Thread-safe state that the engine writes to and the dashboard reads from."""

    def __init__(self, agents: dict):
        self.lock = threading.Lock()
        self.start_time = datetime.now()

        # Per-agent state
        self.agent_states: dict[str, dict] = {}
        for agent_id, agent in agents.items():
            self.agent_states[agent_id] = {
                "name": agent.name,
                "title": agent.title,
                "level": agent.level,
                "department": agent.department,
                "status": Status.WAITING,
                "task_preview": "",
                "output_preview": "",
                "confidence": None,
            }

        # Global state
        self.round_number = 0
        self.round_name = ""
        self.total_rounds = 7
        self.api_calls = 0
        self.active_count = 0

        # Message feed (last N messages)
        self.messages: deque[dict] = deque(maxlen=20)

        # Conversation log — full agent task/response records
        self.conversation_log: list[dict] = []

        # Report viewer
        self.report_content: str | None = None
        self.simulation_complete = False

        # Kill switch — engine checks this to abort
        self.kill_requested = threading.Event()

        # ── New Feature Data ──────────────────
        # Communication flow log
        self.comm_flow: list[dict] = []

        # Cross-department request tracker
        self.cross_dept_requests: list[dict] = []

        # Confidence heatmap data (agents × rounds)
        self.confidence_grid: list[dict] = []

        # Token/cost tracking
        self.token_stats: dict = {
            "total_input": 0,
            "total_output": 0,
            "estimated_cost": 0.0,
            "per_agent": {},
        }

        # Knowledge graph visualization data
        self.knowledge_graph_data: dict | None = None

        # Reference to agents dict for memory inspector
        self.agents_ref: dict | None = None

    # ── State Mutation Methods (thread-safe) ──────

    def set_round(self, round_number: int, round_name: str):
        with self.lock:
            self.round_number = round_number
            self.round_name = round_name

    def set_thinking(self, agent_id: str, task_preview: str = ""):
        with self.lock:
            if agent_id in self.agent_states:
                self.agent_states[agent_id]["status"] = Status.THINKING
                self.agent_states[agent_id]["task_preview"] = task_preview
                self.agent_states[agent_id]["output_preview"] = ""
                self._update_active_count()

    def set_done(self, agent_id: str, output_preview: str = "", confidence: int | None = None):
        with self.lock:
            if agent_id in self.agent_states:
                self.agent_states[agent_id]["status"] = Status.DONE
                self.agent_states[agent_id]["output_preview"] = output_preview[:150]
                if confidence is not None:
                    self.agent_states[agent_id]["confidence"] = confidence
                self._update_active_count()

    def set_error(self, agent_id: str, error: str = ""):
        with self.lock:
            if agent_id in self.agent_states:
                self.agent_states[agent_id]["status"] = Status.ERROR
                self.agent_states[agent_id]["output_preview"] = error[:100]
                self._update_active_count()

    def reset_all(self):
        """Reset all agents to waiting (between rounds)."""
        with self.lock:
            for state in self.agent_states.values():
                state["status"] = Status.WAITING
                state["task_preview"] = ""
                state["output_preview"] = ""

    def add_message(self, from_name: str, to_name: str, msg_type: str, preview: str, department: str = None):
        with self.lock:
            icon = {"task_assignment": "📋", "question": "❓", "deliverable": "📦",
                    "chat_chain": "💬", "vote": "🗳️", "fact_check": "🔍",
                    "quality_gate": "⚡", "skip": "⏩"}.get(msg_type, "💬")
            self.messages.append({
                "icon": icon,
                "from": from_name,
                "to": to_name,
                "preview": preview[:100],
                "department": department or "",
                "time": datetime.now().strftime("%H:%M:%S"),
            })

    def increment_api_calls(self):
        with self.lock:
            self.api_calls += 1

    def add_conversation(self, agent_id: str, agent_name: str, department: str,
                         action: str, task: str, response: str, round_number: int = 0,
                         tools_used: list | None = None):
        """Add a full conversation record (agent task + response)."""
        with self.lock:
            self.conversation_log.append({
                "agent_id": agent_id,
                "agent_name": agent_name,
                "department": department or "executive",
                "action": action,
                "task": task,
                "response": response,
                "round": round_number,
                "time": datetime.now().strftime("%H:%M:%S"),
                "tools_used": tools_used or [],
            })

    def set_report(self, markdown_content: str):
        """Set the final report content (called after report generation)."""
        with self.lock:
            self.report_content = markdown_content
            self.simulation_complete = True

    def set_agents_ref(self, agents: dict):
        """Store reference to agents dict for memory inspector."""
        self.agents_ref = agents

    def add_comm_flow(self, from_name: str, to_name: str, msg_type: str,
                      preview: str = "", round_number: int = 0):
        """Record a communication flow entry."""
        with self.lock:
            self.comm_flow.append({
                "from_name": from_name,
                "to_name": to_name,
                "msg_type": msg_type,
                "preview": preview[:100],
                "round": round_number,
                "time": datetime.now().strftime("%H:%M:%S"),
            })

    def add_cross_dept_request(self, from_agent: str, from_dept: str,
                               to_dept: str, request: str, round_number: int = 0):
        """Record a cross-department request."""
        with self.lock:
            self.cross_dept_requests.append({
                "from_agent": from_agent,
                "from_dept": from_dept,
                "to_dept": to_dept,
                "request": request[:200],
                "round": round_number,
                "status": "pending",
                "response": "",
            })

    def fulfill_cross_dept_request(self, from_dept: str, to_dept: str,
                                    response: str = ""):
        """Mark a cross-department request as fulfilled."""
        with self.lock:
            for req in reversed(self.cross_dept_requests):
                if req["from_dept"] == from_dept and req["to_dept"] == to_dept and req["status"] == "pending":
                    req["status"] = "fulfilled"
                    req["response"] = response[:200]
                    break

    def add_confidence_entry(self, agent_id: str, agent_name: str,
                             score: int | None, round_number: int = 0):
        """Record a confidence score for the heatmap."""
        if score is not None:
            with self.lock:
                self.confidence_grid.append({
                    "agent_id": agent_id,
                    "agent_name": agent_name,
                    "round": round_number,
                    "score": score,
                })

    def update_token_stats(self, agent_id: str, input_tokens: int,
                           output_tokens: int, model: str = "gemini-2.5-flash"):
        """Update cumulative token usage and cost."""
        # Pricing per 1M tokens
        pricing = {
            "gemini-2.5-flash": (0.15, 0.60),
            "gemini-3-flash-preview": (0.15, 0.60),
            "gemini-3-pro-preview": (3.50, 10.50),
        }
        in_price, out_price = pricing.get(model, (0.15, 0.60))
        cost = (input_tokens * in_price + output_tokens * out_price) / 1_000_000

        with self.lock:
            self.token_stats["total_input"] += input_tokens
            self.token_stats["total_output"] += output_tokens
            self.token_stats["estimated_cost"] += cost
            if agent_id not in self.token_stats["per_agent"]:
                self.token_stats["per_agent"][agent_id] = {"input": 0, "output": 0, "cost": 0.0}
            self.token_stats["per_agent"][agent_id]["input"] += input_tokens
            self.token_stats["per_agent"][agent_id]["output"] += output_tokens
            self.token_stats["per_agent"][agent_id]["cost"] += cost

    def set_knowledge_graph(self, nodes: list, edges: list):
        """Set knowledge graph data for visualization."""
        with self.lock:
            self.knowledge_graph_data = {"nodes": nodes, "edges": edges}

    def get_elapsed(self) -> str:
        elapsed = (datetime.now() - self.start_time).total_seconds()
        mins, secs = divmod(int(elapsed), 60)
        return f"{mins}m{secs:02d}s"

    def _update_active_count(self):
        self.active_count = sum(
            1 for s in self.agent_states.values()
            if s["status"] == Status.THINKING
        )

    def to_json(self) -> str:
        """Serialize the full state to JSON for the web dashboard."""
        with self.lock:
            data = {
                "round_number": self.round_number,
                "round_name": self.round_name,
                "total_rounds": self.total_rounds,
                "api_calls": self.api_calls,
                "active_count": self.active_count,
                "elapsed": self.get_elapsed(),
                "killed": self.kill_requested.is_set(),
                "simulation_complete": self.simulation_complete,
                "agents": {
                    aid: {
                        "name": s["name"],
                        "title": s["title"],
                        "level": s["level"],
                        "department": s["department"] or "executive",
                        "status": s["status"],
                        "task_preview": s["task_preview"],
                        "output_preview": s["output_preview"],
                        "confidence": s["confidence"],
                    }
                    for aid, s in self.agent_states.items()
                },
                "messages": list(self.messages),
                "conversations": self.conversation_log,
            }
        return json.dumps(data)


# ── HTML Dashboard Template ──────────────────────

DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>R&D Simulation — Live Dashboard</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
  :root {
    --bg-primary: #0a0e17;
    --bg-secondary: #111827;
    --bg-card: #1a2332;
    --bg-card-hover: #1f2b3d;
    --border: #2a3a4e;
    --text-primary: #e2e8f0;
    --text-secondary: #94a3b8;
    --text-dim: #64748b;
    --accent-cyan: #22d3ee;
    --accent-blue: #3b82f6;
    --accent-green: #10b981;
    --accent-yellow: #f59e0b;
    --accent-red: #ef4444;
    --accent-purple: #a78bfa;
    --accent-pink: #ec4899;
    --dept-research: #60a5fa;
    --dept-engineering: #34d399;
    --dept-product: #fbbf24;
    --dept-executive: #c084fc;
    --gradient-thinking: linear-gradient(135deg, #f59e0b22, #f59e0b08);
    --gradient-done: linear-gradient(135deg, #10b98122, #10b98108);
    --gradient-error: linear-gradient(135deg, #ef444422, #ef444408);
    --shadow-glow-cyan: 0 0 20px rgba(34, 211, 238, 0.15);
    --shadow-card: 0 4px 12px rgba(0,0,0,0.3);
  }

  * { margin:0; padding:0; box-sizing:border-box; }

  body {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    background: var(--bg-primary);
    color: var(--text-primary);
    min-height: 100vh;
    overflow-x: hidden;
  }

  /* ── Header ─────────────────────────── */
  .header {
    background: var(--bg-secondary);
    border-bottom: 1px solid var(--border);
    padding: 16px 28px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    box-shadow: var(--shadow-card);
    position: sticky;
    top: 0;
    z-index: 100;
  }

  .header-left {
    display: flex;
    align-items: center;
    gap: 16px;
  }

  .header-title {
    font-size: 18px;
    font-weight: 700;
    background: linear-gradient(135deg, var(--accent-cyan), var(--accent-blue));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    letter-spacing: -0.3px;
  }

  .connection-dot {
    width: 8px; height: 8px;
    border-radius: 50%;
    background: var(--accent-green);
    box-shadow: 0 0 8px rgba(16, 185, 129, 0.6);
    animation: pulse 2s ease-in-out infinite;
  }
  .connection-dot.disconnected {
    background: var(--accent-red);
    box-shadow: 0 0 8px rgba(239, 68, 68, 0.6);
  }

  @keyframes pulse {
    0%, 100% { opacity: 1; transform: scale(1); }
    50% { opacity: 0.6; transform: scale(0.85); }
  }

  .stats-bar {
    display: flex;
    gap: 24px;
    align-items: center;
  }

  .stat {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 13px;
    color: var(--text-secondary);
  }

  .stat-value {
    font-weight: 600;
    font-family: 'JetBrains Mono', monospace;
    color: var(--text-primary);
  }

  /* ── Round Progress ─────────────────── */
  .round-section {
    padding: 14px 28px;
    background: var(--bg-secondary);
    border-bottom: 1px solid var(--border);
  }

  .round-info {
    display: flex;
    align-items: center;
    gap: 14px;
    margin-bottom: 8px;
  }

  .round-badge {
    background: linear-gradient(135deg, var(--accent-cyan), var(--accent-blue));
    color: #000;
    font-weight: 700;
    font-size: 12px;
    padding: 3px 10px;
    border-radius: 10px;
    letter-spacing: 0.5px;
  }

  .round-name {
    font-size: 14px;
    font-weight: 500;
    color: var(--text-primary);
  }

  .progress-track {
    height: 4px;
    background: var(--border);
    border-radius: 4px;
    overflow: hidden;
  }

  .progress-fill {
    height: 100%;
    background: linear-gradient(90deg, var(--accent-cyan), var(--accent-blue));
    border-radius: 4px;
    transition: width 0.6s ease;
    box-shadow: 0 0 10px rgba(34, 211, 238, 0.4);
  }

  /* ── Agent Grid ─────────────────────── */
  .main-content { padding: 20px 28px; }

  .section-title {
    font-size: 13px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 1.2px;
    color: var(--text-dim);
    margin-bottom: 14px;
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .agent-grid {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0;
    margin-bottom: 24px;
    position: relative;
  }

  /* ── Hierarchy Tiers ────────────────── */
  .org-tier {
    display: flex;
    justify-content: center;
    gap: 16px;
    width: 100%;
    position: relative;
  }
  .org-tier-label {
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    color: var(--text-dim);
    margin: 14px 0 6px;
    text-align: center;
    font-weight: 700;
  }
  .org-connector {
    width: 2px;
    height: 14px;
    background: linear-gradient(to bottom, var(--border), rgba(34,211,238,0.3));
    margin: 0 auto;
  }
  .dept-group {
    flex: 1;
    max-width: 340px;
  }
  .dept-group-label {
    font-size: 11px;
    font-weight: 700;
    text-align: center;
    padding: 4px 12px;
    margin-bottom: 6px;
    border-radius: 6px;
    letter-spacing: 0.5px;
  }
  .dept-group-label.research { color: var(--dept-research); background: rgba(139,92,246,0.1); }
  .dept-group-label.engineering { color: var(--dept-engineering); background: rgba(59,130,246,0.1); }
  .dept-group-label.product { color: var(--dept-product); background: rgba(16,185,129,0.1); }
  .dept-group-label.executive { color: var(--dept-executive); background: rgba(245,158,11,0.1); }
  .dept-group-cards {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .org-tier.vp-tier {
    justify-content: center;
  }
  .org-tier.vp-tier .agent-card {
    max-width: 380px;
    border-width: 2px;
  }
  .org-tier.lead-tier {
    display: flex;
    gap: 12px;
    justify-content: center;
  }
  .org-tier.ic-tier {
    display: flex;
    gap: 12px;
    justify-content: center;
  }

  .agent-card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 14px 16px;
    transition: all 0.3s ease;
    position: relative;
    overflow: hidden;
  }

  .agent-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0;
    width: 3px; height: 100%;
    border-radius: 10px 0 0 10px;
    transition: background 0.3s ease;
  }

  .agent-card.thinking {
    border-color: var(--accent-yellow);
    background: var(--gradient-thinking);
    animation: cardPulse 2s ease-in-out infinite;
  }
  .agent-card.thinking::before { background: var(--accent-yellow); }

  .agent-card.done {
    border-color: rgba(16, 185, 129, 0.4);
    background: var(--gradient-done);
  }
  .agent-card.done::before { background: var(--accent-green); }

  .agent-card.error {
    border-color: rgba(239, 68, 68, 0.4);
    background: var(--gradient-error);
  }
  .agent-card.error::before { background: var(--accent-red); }

  .agent-card.waiting::before { background: var(--border); }

  @keyframes cardPulse {
    0%, 100% { box-shadow: 0 0 0 rgba(245, 158, 11, 0); }
    50% { box-shadow: 0 0 16px rgba(245, 158, 11, 0.12); }
  }

  .agent-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 8px;
  }

  .agent-name {
    font-weight: 600;
    font-size: 14px;
    color: var(--text-primary);
  }

  .agent-title {
    font-size: 11px;
    color: var(--text-dim);
    margin-top: 2px;
  }

  .dept-badge {
    font-size: 10px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    padding: 2px 8px;
    border-radius: 6px;
    white-space: nowrap;
  }

  .dept-research { background: rgba(96, 165, 250, 0.15); color: var(--dept-research); }
  .dept-engineering { background: rgba(52, 211, 153, 0.15); color: var(--dept-engineering); }
  .dept-product { background: rgba(251, 191, 36, 0.15); color: var(--dept-product); }
  .dept-executive { background: rgba(192, 132, 252, 0.15); color: var(--dept-executive); }

  .agent-status {
    font-size: 12px;
    margin-top: 6px;
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .status-icon {
    font-size: 14px;
  }

  .status-text {
    color: var(--text-secondary);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 220px;
  }

  .spinner {
    display: inline-block;
    width: 14px; height: 14px;
    border: 2px solid var(--accent-yellow);
    border-top-color: transparent;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  .confidence-bar {
    margin-top: 6px;
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 11px;
    color: var(--text-dim);
  }

  .conf-track {
    flex: 1;
    height: 3px;
    background: var(--border);
    border-radius: 3px;
    overflow: hidden;
  }

  .conf-fill {
    height: 100%;
    border-radius: 3px;
    transition: width 0.5s ease;
  }

  /* ── Message Feed ───────────────────── */
  .feed-section {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 10px;
    overflow: hidden;
  }

  .feed-header {
    padding: 12px 16px;
    border-bottom: 1px solid var(--border);
    font-size: 13px;
    font-weight: 600;
    color: var(--text-secondary);
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .feed-body {
    max-height: 260px;
    overflow-y: auto;
    scrollbar-width: thin;
    scrollbar-color: var(--border) transparent;
  }

  .feed-body::-webkit-scrollbar { width: 6px; }
  .feed-body::-webkit-scrollbar-track { background: transparent; }
  .feed-body::-webkit-scrollbar-thumb {
    background: var(--border);
    border-radius: 3px;
  }

  .msg-row {
    display: flex;
    align-items: flex-start;
    gap: 10px;
    padding: 8px 16px;
    border-bottom: 1px solid rgba(42, 58, 78, 0.4);
    font-size: 13px;
    animation: fadeIn 0.3s ease;
  }

  .msg-row:last-child { border-bottom: none; }

  @keyframes fadeIn {
    from { opacity: 0; transform: translateY(-4px); }
    to { opacity: 1; transform: translateY(0); }
  }

  .msg-time {
    color: var(--text-dim);
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px;
    white-space: nowrap;
    min-width: 56px;
  }

  .msg-icon { font-size: 14px; }

  .msg-from {
    font-weight: 600;
    white-space: nowrap;
  }

  .msg-arrow { color: var(--text-dim); }

  .msg-to {
    font-weight: 500;
    white-space: nowrap;
    color: var(--text-secondary);
  }

  .msg-preview {
    color: var(--text-dim);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    flex: 1;
  }

  .empty-feed {
    padding: 30px;
    text-align: center;
    color: var(--text-dim);
    font-size: 13px;
  }

  /* ── Tab Bar ────────────────────────── */
  .tab-bar {
    display: flex;
    gap: 2px;
    border-bottom: 1px solid var(--border);
    margin-bottom: 0;
  }
  .tab {
    background: transparent;
    border: none;
    color: var(--text-dim);
    padding: 10px 18px;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    border-bottom: 2px solid transparent;
    transition: all 0.2s;
    font-family: inherit;
  }
  .tab:hover { color: var(--text-primary); }
  .tab.active {
    color: var(--accent-cyan);
    border-bottom-color: var(--accent-cyan);
  }
  .tab-count {
    background: var(--card-bg);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 1px 7px;
    font-size: 11px;
    margin-left: 4px;
  }
  .tab.has-report {
    color: var(--accent-green);
    animation: tabPulse 1s ease-in-out 3;
  }
  @keyframes tabPulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.5; }
  }
  .tab-content { display: none; }
  .tab-content.active { display: block; }

  /* ── Conversation Cards ────────────── */
  .conv-list {
    max-height: 450px;
    overflow-y: auto;
    padding: 8px;
  }
  .conv-round-header {
    font-weight: 700;
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 1px;
    color: var(--accent-cyan);
    padding: 10px 8px 4px;
    border-bottom: 1px solid rgba(34,211,238,0.15);
    margin-bottom: 6px;
  }
  .conv-card {
    background: rgba(255,255,255,0.03);
    border: 1px solid var(--border);
    border-radius: 8px;
    margin-bottom: 6px;
    cursor: pointer;
    transition: border-color 0.2s;
  }
  .conv-card:hover { border-color: var(--accent-cyan); }
  .conv-header {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 12px;
    font-size: 13px;
  }
  .conv-icon { font-size: 16px; }
  .conv-agent { font-weight: 600; }
  .conv-action {
    color: var(--text-dim);
    font-style: italic;
    flex: 1;
  }
  .conv-time {
    color: var(--text-dim);
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px;
  }
  .conv-expand {
    color: var(--text-dim);
    font-size: 10px;
    margin-left: 4px;
    transition: transform 0.2s;
  }
  .conv-body {
    border-top: 1px solid var(--border);
    padding: 12px;
    animation: fadeIn 0.2s ease;
  }
  .conv-section { margin-bottom: 10px; }
  .conv-section:last-child { margin-bottom: 0; }
  .conv-label {
    font-weight: 600;
    font-size: 12px;
    color: var(--text-secondary);
    margin-bottom: 4px;
  }
  .conv-text {
    font-size: 13px;
    color: var(--text-primary);
    line-height: 1.5;
    white-space: pre-wrap;
    word-break: break-word;
    max-height: 300px;
    overflow-y: auto;
    background: rgba(0,0,0,0.2);
    padding: 8px 10px;
    border-radius: 6px;
  }
  .tool-badges {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
    margin-left: auto;
  }
  .tool-badge {
    display: inline-flex;
    align-items: center;
    gap: 3px;
    background: rgba(245,158,11,0.15);
    border: 1px solid rgba(245,158,11,0.3);
    color: var(--accent-yellow);
    font-size: 10px;
    font-weight: 600;
    padding: 2px 7px;
    border-radius: 10px;
    white-space: nowrap;
  }
  .tool-badge-icon { font-size: 10px; }
  .tools-section {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    padding: 8px 0;
  }
  .tool-detail {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    background: rgba(245,158,11,0.1);
    border: 1px solid rgba(245,158,11,0.25);
    color: var(--accent-yellow);
    font-size: 12px;
    padding: 4px 10px;
    border-radius: 6px;
  }
  .tool-detail-time {
    color: var(--text-dim);
    font-family: 'JetBrains Mono', monospace;
    font-size: 10px;
  }

  /* ── Report Viewer ─────────────────── */
  .report-waiting {
    padding: 40px;
    text-align: center;
    color: var(--text-dim);
    font-size: 14px;
  }
  .report-body {
    padding: 20px 24px;
    font-size: 14px;
    line-height: 1.7;
    color: var(--text-primary);
    max-height: 600px;
    overflow-y: auto;
  }
  .report-body h1 { font-size: 22px; color: var(--accent-cyan); margin: 20px 0 10px; border-bottom: 1px solid var(--border); padding-bottom: 6px; }
  .report-body h2 { font-size: 18px; color: var(--text-primary); margin: 18px 0 8px; }
  .report-body h3 { font-size: 15px; color: var(--text-secondary); margin: 14px 0 6px; }
  .report-body p { margin: 8px 0; }
  .report-body ul, .report-body ol { padding-left: 24px; margin: 8px 0; }
  .report-body li { margin: 4px 0; }
  .report-body code {
    background: rgba(0,0,0,0.3);
    padding: 2px 6px;
    border-radius: 4px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 12px;
  }
  .report-body pre {
    background: rgba(0,0,0,0.3);
    padding: 12px;
    border-radius: 8px;
    overflow-x: auto;
    margin: 10px 0;
  }
  .report-body pre code { background: none; padding: 0; }
  .report-body table {
    width: 100%;
    border-collapse: collapse;
    margin: 10px 0;
  }
  .report-body th, .report-body td {
    border: 1px solid var(--border);
    padding: 8px 12px;
    text-align: left;
    font-size: 13px;
  }
  .report-body th {
    background: rgba(34,211,238,0.1);
    font-weight: 600;
  }
  .report-body hr {
    border: none;
    border-top: 1px solid var(--border);
    margin: 20px 0;
  }
  .report-body blockquote {
    border-left: 3px solid var(--accent-cyan);
    margin: 10px 0;
    padding: 8px 16px;
    color: var(--text-secondary);
    background: rgba(34,211,238,0.05);
    border-radius: 0 6px 6px 0;
  }

  /* ── Kill Button ────────────────────── */
  .kill-btn {
    background: linear-gradient(135deg, #dc2626, #991b1b);
    color: #fff;
    border: 1px solid rgba(239, 68, 68, 0.4);
    padding: 6px 16px;
    border-radius: 8px;
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 0.5px;
    cursor: pointer;
    transition: all 0.2s ease;
    display: flex;
    align-items: center;
    gap: 6px;
    text-transform: uppercase;
  }
  .kill-btn:hover {
    background: linear-gradient(135deg, #ef4444, #dc2626);
    box-shadow: 0 0 16px rgba(239, 68, 68, 0.4);
    transform: translateY(-1px);
  }
  .kill-btn:active { transform: translateY(0); }
  .kill-btn.killed {
    background: #374151;
    border-color: var(--border);
    cursor: not-allowed;
    opacity: 0.6;
  }

  /* ── Killed Overlay ─────────────────── */
  .killed-banner {
    display: none;
    background: linear-gradient(135deg, rgba(239,68,68,0.15), rgba(153,27,27,0.1));
    border: 1px solid rgba(239, 68, 68, 0.4);
    border-radius: 10px;
    padding: 16px 24px;
    margin-bottom: 20px;
    text-align: center;
  }
  .killed-banner.visible { display: block; }
  .killed-banner h3 {
    color: var(--accent-red);
    font-size: 16px;
    margin-bottom: 4px;
  }
  .killed-banner p {
    color: var(--text-secondary);
    font-size: 13px;
  }

  /* ── Responsive ─────────────────────── */
  @media (max-width: 900px) {
    .agent-grid { grid-template-columns: repeat(2, 1fr); }
  }
  @media (max-width: 600px) {
    .agent-grid { grid-template-columns: 1fr; }
    .header { flex-direction: column; gap: 10px; }
    .stats-bar { flex-wrap: wrap; }
  }
</style>
</head>
<body>

<!-- Header -->
<div class="header">
  <div class="header-left">
    <div class="connection-dot" id="connectionDot"></div>
    <div class="header-title">🏢 R&D Simulation — Live Dashboard</div>
  </div>
  <div class="stats-bar">
    <div class="stat">⏱ <span class="stat-value" id="elapsed">0m00s</span></div>
    <div class="stat">🔗 API Calls: <span class="stat-value" id="apiCalls">0</span></div>
    <div class="stat">⚡ Active: <span class="stat-value" id="activeCount">0</span></div>
    <button class="kill-btn" id="killBtn" onclick="killSimulation()">⛔ Kill</button>
  </div>
</div>

<!-- Round Progress -->
<div class="round-section">
  <div class="round-info">
    <div class="round-badge" id="roundBadge">ROUND 0/7</div>
    <div class="round-name" id="roundName">Initializing...</div>
  </div>
  <div class="progress-track">
    <div class="progress-fill" id="progressFill" style="width:0%"></div>
  </div>
</div>

<!-- Main Content -->
<div class="main-content">
  <div class="killed-banner" id="killedBanner">
    <h3>⛔ Simulation Killed</h3>
    <p>The simulation has been stopped. You can close this tab.</p>
  </div>
  <div class="section-title">👥 Agent Activity</div>
  <div class="agent-grid" id="agentGrid"></div>

  <div class="feed-section">
    <div class="tab-bar">
      <button class="tab active" onclick="switchTab('feed')" id="tabFeed">💬 Live Feed</button>
      <button class="tab" onclick="switchTab('conversations')" id="tabConversations">🗣️ Conversations <span class="tab-count" id="convCount">0</span></button>
      <button class="tab" onclick="switchTab('report')" id="tabReport">📄 Report</button>
    </div>

    <!-- Tab: Live Feed -->
    <div class="tab-content active" id="panelFeed">
      <div class="feed-body" id="feedBody">
        <div class="empty-feed">Waiting for agent activity...</div>
      </div>
    </div>

    <!-- Tab: Conversations -->
    <div class="tab-content" id="panelConversations">
      <div class="conv-list" id="convList">
        <div class="empty-feed">No conversations yet...</div>
      </div>
    </div>

    <!-- Tab: Report -->
    <div class="tab-content" id="panelReport">
      <div class="report-placeholder" id="reportPlaceholder">
        <div class="report-waiting">⏳ Report will appear here when the simulation completes</div>
      </div>
      <div class="report-body" id="reportBody" style="display:none"></div>
    </div>
  </div>
</div>

<!-- marked.js CDN for markdown rendering -->
<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>

<script>
const DEPT_COLORS = {
  research: 'var(--dept-research)',
  engineering: 'var(--dept-engineering)',
  product: 'var(--dept-product)',
  executive: 'var(--dept-executive)',
};
const DEPT_ICONS = {
  research: '🔬', engineering: '⚙️', product: '📦', executive: '👔',
};

let connectionOk = true;
let lastConvCount = 0;
let reportLoaded = false;

// ── Tab switching ─────────────────────
function switchTab(name) {
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.tab-content').forEach(p => p.classList.remove('active'));
  document.getElementById('tab' + name.charAt(0).toUpperCase() + name.slice(1)).classList.add('active');
  document.getElementById('panel' + name.charAt(0).toUpperCase() + name.slice(1)).classList.add('active');
}

// ── Main update function ──────────────
function updateDashboard(data) {
  connectionOk = true;
  document.getElementById('connectionDot').classList.remove('disconnected');

  // Header stats
  document.getElementById('elapsed').textContent = data.elapsed || '0m00s';
  document.getElementById('apiCalls').textContent = data.api_calls || 0;
  document.getElementById('activeCount').textContent = data.active_count || 0;

  // Round info
  const pct = data.total_rounds ? Math.round((data.round_number / data.total_rounds) * 100) : 0;
  document.getElementById('roundBadge').textContent = `ROUND ${data.round_number}/${data.total_rounds}`;
  document.getElementById('roundName').textContent = data.round_name || 'Initializing...';
  document.getElementById('progressFill').style.width = pct + '%';

  // Agent hierarchy
  const grid = document.getElementById('agentGrid');
  grid.innerHTML = '';
  if (data.agents) {
    renderAgentHierarchy(grid, data.agents);
  }

  // Live Feed
  const feedBody = document.getElementById('feedBody');
  if (data.messages && data.messages.length > 0) {
    feedBody.innerHTML = '';
    for (const msg of data.messages) {
      feedBody.appendChild(createMsgRow(msg));
    }
    feedBody.scrollTop = feedBody.scrollHeight;
  }

  // Conversations
  if (data.conversations && data.conversations.length !== lastConvCount) {
    lastConvCount = data.conversations.length;
    document.getElementById('convCount').textContent = lastConvCount;
    renderConversations(data.conversations);
  }

  // Report status
  if (data.simulation_complete && !reportLoaded) {
    loadReport();
  }
}

// ── Agent card renderer ─────────────
// ── Hierarchical agent renderer ─────
function renderAgentHierarchy(container, agents) {
  const vp = [], leads = {}, ics = {};
  for (const [aid, agent] of Object.entries(agents)) {
    const lvl = agent.level || 3;
    const dept = agent.department || 'executive';
    if (lvl === 1) {
      vp.push({ aid, ...agent });
    } else if (lvl === 2) {
      if (!leads[dept]) leads[dept] = [];
      leads[dept].push({ aid, ...agent });
    } else {
      if (!ics[dept]) ics[dept] = [];
      ics[dept].push({ aid, ...agent });
    }
  }

  // VP tier
  if (vp.length) {
    container.innerHTML += `<div class="org-tier-label">👔 Executive</div>`;
    let vpHTML = '<div class="org-tier vp-tier">';
    for (const a of vp) vpHTML += createAgentCard(a.aid, a);
    vpHTML += '</div>';
    container.innerHTML += vpHTML;
  }

  // Connector
  if (Object.keys(leads).length)
    container.innerHTML += '<div class="org-connector"></div>';

  // Lead tier
  const deptOrder = ['research', 'engineering', 'product'];
  const activeDepts = deptOrder.filter(d => leads[d] || ics[d]);
  if (activeDepts.length) {
    container.innerHTML += `<div class="org-tier-label">📋 Department Leads</div>`;
    let leadHTML = '<div class="org-tier lead-tier">';
    for (const dept of activeDepts) {
      const deptLeads = leads[dept] || [];
      leadHTML += `<div class="dept-group">`;
      leadHTML += `<div class="dept-group-label ${dept}">${(DEPT_ICONS[dept]||'')} ${dept.toUpperCase()}</div>`;
      leadHTML += '<div class="dept-group-cards">';
      for (const a of deptLeads) leadHTML += createAgentCard(a.aid, a);
      leadHTML += '</div></div>';
    }
    leadHTML += '</div>';
    container.innerHTML += leadHTML;
  }

  // Connector
  if (Object.keys(ics).length)
    container.innerHTML += '<div class="org-connector"></div>';

  // IC tier
  if (activeDepts.some(d => ics[d])) {
    container.innerHTML += `<div class="org-tier-label">🔧 Individual Contributors</div>`;
    let icHTML = '<div class="org-tier ic-tier">';
    for (const dept of activeDepts) {
      const deptICs = ics[dept] || [];
      if (!deptICs.length) continue;
      icHTML += `<div class="dept-group">`;
      icHTML += `<div class="dept-group-label ${dept}">${(DEPT_ICONS[dept]||'')} ${dept.toUpperCase()}</div>`;
      icHTML += '<div class="dept-group-cards">';
      for (const a of deptICs) icHTML += createAgentCard(a.aid, a);
      icHTML += '</div></div>';
    }
    icHTML += '</div>';
    container.innerHTML += icHTML;
  }
}

function createAgentCard(aid, agent) {
  const dept = agent.department || 'executive';
  const color = DEPT_COLORS[dept] || 'var(--text-primary)';
  const icon = DEPT_ICONS[dept] || '👤';
  const status = agent.status || 'waiting';

  let statusHTML = '';
  if (status === 'thinking') {
    statusHTML = `<div class="agent-status thinking">
      <span class="thinking-dot"></span><span class="thinking-dot"></span><span class="thinking-dot"></span>
      <span class="status-text">${escHtml(agent.task_preview || 'Thinking...')}</span>
    </div>`;
  } else if (status === 'done') {
    const confHTML = agent.confidence != null
      ? `<div class="confidence"><div class="conf-bar"><div class="conf-fill" style="width:${agent.confidence}%"></div></div><span class="conf-val">${agent.confidence}%</span></div>`
      : '';
    statusHTML = `<div class="agent-status done">✅ ${escHtml(agent.output_preview || 'Done')}</div>${confHTML}`;
  } else if (status === 'error') {
    statusHTML = `<div class="agent-status error">❌ ${escHtml(agent.output_preview || 'Error')}</div>`;
  } else {
    statusHTML = `<div class="agent-status waiting">⏳ Waiting</div>`;
  }

  return `
    <div class="agent-card ${status}">
      <div class="agent-header" style="border-left: 3px solid ${color}; padding-left: 8px;">
        <span class="agent-icon">${icon}</span>
        <div>
          <div class="agent-name">${escHtml(agent.name)}</div>
          <div class="agent-title">${escHtml(agent.title)}</div>
        </div>
      </div>
      ${statusHTML}
    </div>
  `;
}

// ── Message row ─────────────────────
function createMsgRow(msg) {
  const row = document.createElement('div');
  row.className = 'msg-row';
  const dept = msg.department || 'executive';
  const color = DEPT_COLORS[dept] || 'var(--text-primary)';
  row.innerHTML = `
    <span class="msg-time">${escHtml(msg.time)}</span>
    <span class="msg-icon">${msg.icon}</span>
    <span class="msg-from" style="color:${color}">${escHtml(msg.from)}</span>
    <span class="msg-arrow">→</span>
    <span class="msg-to">${escHtml(msg.to)}</span>
    <span class="msg-preview">${escHtml(msg.preview)}</span>
  `;
  return row;
}

// ── Conversations renderer ──────────
function renderConversations(conversations) {
  const container = document.getElementById('convList');
  if (!conversations || conversations.length === 0) {
    container.innerHTML = '<div class="empty-feed">No conversations yet...</div>';
    return;
  }

  // Group by round
  const byRound = {};
  for (const c of conversations) {
    const r = c.round || 0;
    if (!byRound[r]) byRound[r] = [];
    byRound[r].push(c);
  }

  let html = '';
  for (const [round, convs] of Object.entries(byRound).sort((a,b) => b[0]-a[0])) {
    html += `<div class="conv-round-header">Round ${round}</div>`;
    for (let i = convs.length - 1; i >= 0; i--) {
      const c = convs[i];
      const dept = c.department || 'executive';
      const color = DEPT_COLORS[dept] || 'var(--text-primary)';
      const icon = DEPT_ICONS[dept] || '👤';
      const cardId = `conv-${round}-${i}`;
      const toolBadges = (c.tools_used && c.tools_used.length)
        ? c.tools_used.map(t => `<span class="tool-badge"><span class="tool-badge-icon">🔧</span>${escHtml(t.tool)}</span>`).join('')
        : '';
      const toolsSection = (c.tools_used && c.tools_used.length)
        ? `<div class="conv-section">
            <div class="conv-label">🔧 Tools Used</div>
            <div class="tools-section">
              ${c.tools_used.map(t => `<div class="tool-detail">🔧 ${escHtml(t.tool)} <span class="tool-detail-time">${escHtml(t.time)}</span></div>`).join('')}
            </div>
          </div>`
        : '';
      html += `
        <div class="conv-card" onclick="toggleConv('${cardId}')">
          <div class="conv-header">
            <span class="conv-icon">${icon}</span>
            <span class="conv-agent" style="color:${color}">${escHtml(c.agent_name)}</span>
            <span class="conv-action">${escHtml(c.action)}</span>
            <div class="tool-badges">${toolBadges}</div>
            <span class="conv-time">${escHtml(c.time)}</span>
            <span class="conv-expand" id="${cardId}-arrow">▶</span>
          </div>
          <div class="conv-body" id="${cardId}" style="display:none">
            ${toolsSection}
            <div class="conv-section">
              <div class="conv-label">📋 Task</div>
              <div class="conv-text">${escHtml(c.task)}</div>
            </div>
            <div class="conv-section">
              <div class="conv-label">💡 Response</div>
              <div class="conv-text">${escHtml(c.response)}</div>
            </div>
          </div>
        </div>
      `;
    }
  }
  container.innerHTML = html;
}

function toggleConv(id) {
  const el = document.getElementById(id);
  const arrow = document.getElementById(id + '-arrow');
  if (el.style.display === 'none') {
    el.style.display = 'block';
    if (arrow) arrow.textContent = '▼';
  } else {
    el.style.display = 'none';
    if (arrow) arrow.textContent = '▶';
  }
}

// ── Report loader ───────────────────
async function loadReport() {
  try {
    const res = await fetch('/api/report');
    if (res.ok) {
      const data = await res.json();
      if (data.report) {
        reportLoaded = true;
        document.getElementById('reportPlaceholder').style.display = 'none';
        const body = document.getElementById('reportBody');
        body.style.display = 'block';
        body.innerHTML = marked.parse(data.report);
        // Flash the report tab
        document.getElementById('tabReport').classList.add('has-report');
      }
    }
  } catch (e) { /* retry next poll */ }
}

function escHtml(s) {
  if (!s) return '';
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}

// ── Kill switch ─────────────────────
let isKilled = false;

async function killSimulation() {
  if (isKilled) return;
  if (!confirm('⛔ Stop the simulation? This cannot be undone.')) return;
  try {
    await fetch('/api/kill', { method: 'POST' });
    isKilled = true;
    document.getElementById('killBtn').classList.add('killed');
    document.getElementById('killBtn').textContent = '⛔ Killed';
    document.getElementById('killedBanner').classList.add('visible');
  } catch (e) {
    alert('Failed to send kill signal.');
  }
}

// ── Polling loop ────────────────────
async function poll() {
  try {
    const res = await fetch('/api/state');
    if (res.ok) {
      const data = await res.json();
      updateDashboard(data);
      // Show killed state if set server-side
      if (data.killed && !isKilled) {
        isKilled = true;
        document.getElementById('killBtn').classList.add('killed');
        document.getElementById('killBtn').textContent = '⛔ Killed';
        document.getElementById('killedBanner').classList.add('visible');
      }
    }
  } catch (e) {
    connectionOk = false;
    document.getElementById('connectionDot').classList.add('disconnected');
  }
}

setInterval(poll, 500);
poll();  // Initial fetch
</script>
</body>
</html>
"""


# ── HTTP Request Handler ─────────────────────────

class DashboardHandler(BaseHTTPRequestHandler):
    """Handles HTTP requests for the web dashboard."""

    # Class-level reference to state (set before server starts)
    dashboard_state: DashboardState = None

    def do_GET(self):
        path = urlparse(self.path).path

        if path == "/" or path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(DASHBOARD_HTML.encode("utf-8"))

        elif path == "/api/state":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            if self.dashboard_state:
                self.wfile.write(self.dashboard_state.to_json().encode("utf-8"))
            else:
                self.wfile.write(b'{}')

        elif path == "/api/report":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            if self.dashboard_state and self.dashboard_state.report_content:
                data = json.dumps({"report": self.dashboard_state.report_content})
                self.wfile.write(data.encode("utf-8"))
            else:
                self.wfile.write(b'{"report": null}')
        else:
            self.send_error(404)

    def do_POST(self):
        path = urlparse(self.path).path

        if path == "/api/kill":
            if self.dashboard_state:
                self.dashboard_state.kill_requested.set()
                # Update round name to show killed state
                with self.dashboard_state.lock:
                    self.dashboard_state.round_name = "⛔ SIMULATION KILLED"
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status": "killed"}')
        else:
            self.send_error(404)

    def log_message(self, format, *args):
        """Suppress HTTP server log messages to keep terminal clean."""
        pass


# ── Find Available Port ──────────────────────────

def _find_free_port(start=8420, end=8480) -> int:
    """Find a free port in the given range."""
    for port in range(start, end):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("127.0.0.1", port))
                return port
        except OSError:
            continue
    raise RuntimeError(f"No free port found in range {start}-{end}")


# ── Public API: LiveDashboard ────────────────────

class LiveDashboard:
    """
    Web-based live dashboard.
    Starts a local HTTP server and opens the dashboard in the browser.
    """

    def __init__(self, state: DashboardState):
        self.state = state
        self._server: HTTPServer | None = None
        self._thread: threading.Thread | None = None
        self.port: int = 0

    def start(self):
        """Start the dashboard server and open the browser."""
        self.port = _find_free_port()

        # Wire state to handler class
        DashboardHandler.dashboard_state = self.state

        self._server = HTTPServer(("127.0.0.1", self.port), DashboardHandler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

        url = f"http://127.0.0.1:{self.port}"
        print(f"  🌐 Live dashboard: {url}")

        # Auto-open browser
        try:
            webbrowser.open(url)
        except Exception:
            print(f"  ⚠️  Could not auto-open browser. Navigate to {url} manually.")

    def stop(self):
        """Stop the dashboard server."""
        if self._server:
            self._server.shutdown()
        if self._thread:
            self._thread.join(timeout=3)
        print("  🔴 Dashboard server stopped")

    def update(self):
        """No-op — browser polls automatically. Kept for API compatibility."""
        pass
