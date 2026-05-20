"""
sop_gui.py  —  SolaraViz GUI for Miller & Page (2004) Standing Ovation Model.

Run with:
    solara run sop_gui.py

PARAMETERS (matching Section 6 of the paper)
  Update Rule     : synchronous | async_random | async_incentive
  Neighbourhood   : five | cone | global
  Quality threshold: T — default 0.5 per paper (identical for all agents)
  Social threshold : S — default 0.5 per paper (majority rule)
  Grid size       : rows × cols (default 20×20 = 400 seats per paper)

LAYOUT (top to bottom)
  1. Live metrics  — NI, SM, IE counters (paper's Table 1 & 2 measures)
  2. Audience grid — yellow = standing, navy = sitting
  3. Fraction Standing plot — primary outcome variable over time
  4. Standing / Sitting counts — raw counts over time
"""

import solara
from mesa.visualization import SolaraViz, Slider
from mesa.visualization.components.matplotlib_components import (
    make_mpl_space_component,
    make_mpl_plot_component,
    update_counter,
)
from mesa.visualization.components import AgentPortrayalStyle

from model import StandingOvationModel
from agents import SIT, STAND

# ── Colours ───────────────────────────────────────────────────────────────────
_STAND_COL  = "#f5c518"   # golden yellow
_SIT_COL    = "#1a2a4a"   # dark navy
_BG         = "#0d1422"
_PANEL_BG   = "#111b2e"
_ACCENT     = "#1e90ff"


# ── Agent portrayal ───────────────────────────────────────────────────────────

def agent_portrayal(agent) -> AgentPortrayalStyle:
    """
    Yellow = standing, navy = sitting.
    Standing agents are drawn larger so cascades are visually obvious.
    Edge colour encodes row position: brighter = closer to front (lower y).
    """
    is_standing = agent.state == STAND
    # Row-position hint: front row is brightest edge (maximum signalling power)
    x, y        = agent.pos
    rows        = agent.model.rows
    # Front-row agents (y=0) get white edge; back-row agents get dim edge
    row_brightness = 1.0 - (y / max(rows - 1, 1))
    edge_val    = int(80 + 175 * row_brightness)
    edge_hex    = f"#{edge_val:02x}{edge_val:02x}{edge_val:02x}"

    n_vis       = agent.model.get_visible_neighbors(agent)
    n_standing  = sum(1 for n in n_vis if n.state == STAND)
    frac        = n_standing / len(n_vis) if n_vis else 0.0

    return AgentPortrayalStyle(
        color      = _STAND_COL if is_standing else _SIT_COL,
        marker     = "o",
        size       = 140 if is_standing else 70,
        alpha      = 0.95 if is_standing else 0.55,
        edgecolors = edge_hex,
        linewidths = 1.0,
        tooltip    = (
            f"Agent {agent.unique_id}  —  row {y} (0=front)\n"
            f"State          : {'STANDING' if is_standing else 'Sitting'}\n"
            f"Initial quality: {agent.initial_quality:.3f}  "
            f"(threshold {agent.model.quality_threshold})\n"
            f"Visible neighbours : {len(n_vis)}\n"
            f"Fraction standing  : {frac:.2f}  "
            f"(social threshold {agent.model.social_threshold})"
        ),
    )


# ── Space component ───────────────────────────────────────────────────────────

def post_process(ax) -> None:
    ax.set_facecolor(_BG)
    ax.figure.set_size_inches(8, 8)
    ax.figure.patch.set_facecolor(_BG)
    ax.set_title(
        "Audience seating  ·  🟡 Standing   🔵 Sitting\n"
        "Row 0 = front (stage)  ·  brighter border = closer to stage",
        color="#c9d8e8", fontsize=8, pad=6,
    )
    for spine in ax.spines.values():
        spine.set_edgecolor("#1a3050")


_space_fn = make_mpl_space_component(
    agent_portrayal=agent_portrayal,
    post_process=post_process,
    draw_grid=True,
)

_frac_fn, _  = make_mpl_plot_component({"Fraction Standing": _STAND_COL})
_count_fn, _ = make_mpl_plot_component({"Standing": _STAND_COL, "Sitting": _SIT_COL})


# ── Live metrics counter ──────────────────────────────────────────────────────

@solara.component
def LiveMetrics(model):
    """
    Six tiles updated every step, displaying the paper's key metrics:
      Step | Standing | Sitting | NI | SM | IE
    """
    update_counter.get()

    step     = model.step_count
    standing = model.count_state(STAND)
    sitting  = model.count_state(SIT)
    frac     = model.fraction_standing()
    total    = model.n_agents
    at_eq    = model.is_equilibrium()

    ni_val   = (f"{model._ni}" if model._ni is not None
                else f"{step} (running)")
    sm_val   = (f"{model._sm}%" if model._sm is not None
                else f"{model._compute_sm()}%")
    ie_val   = ("✓ Yes" if model._ie == 1
                else "✗ No" if model._ie == 0
                else "—")
    ie_col   = (_STAND_COL if model._ie == 1
                else "#e8003d" if model._ie == 0
                else "#4a6a8a")

    def _tile(label, value, colour, sub=""):
        return (
            f'<div style="display:flex;flex-direction:column;align-items:center;'
            f'background:{_BG};border-radius:6px;padding:10px 18px;min-width:95px;'
            f'border:1px solid #1a3050;">'
            f'<span style="font-size:10px;color:#4a6a8a;font-weight:700;'
            f'letter-spacing:.06em;margin-bottom:4px;">{label}</span>'
            f'<span style="font-size:28px;font-weight:700;color:{colour};'
            f'line-height:1;">{value}</span>'
            f'<span style="font-size:10px;color:#4a6a8a;margin-top:3px;">{sub}</span>'
            f'</div>'
        )

    eq_badge = (
        '<span style="background:#27ae60;color:#fff;font-size:10px;'
        'font-weight:700;padding:3px 10px;border-radius:10px;'
        'letter-spacing:.05em;">EQUILIBRIUM</span>'
        if at_eq else
        '<span style="background:#2c3e50;color:#7f8c8d;font-size:10px;'
        'font-weight:700;padding:3px 10px;border-radius:10px;">'
        'RUNNING…</span>'
    )

    solara.HTML(
        "div",
        unsafe_innerHTML=(
            f'<div style="margin:6px 0;">{eq_badge}</div>'
            f'<div style="display:flex;flex-direction:row;flex-wrap:wrap;gap:10px;'
            f'padding:12px 14px;background:{_PANEL_BG};border-radius:8px;'
            f'border:1px solid #1a3050;margin:4px 0;">'
            + _tile("STEP",      step,     _ACCENT)
            + _tile("STANDING",  standing, _STAND_COL,
                    f"{frac*100:.1f}% of {total}")
            + _tile("SITTING",   sitting,  "#5aa0c8",
                    f"{(1-frac)*100:.1f}% of {total}")
            + _tile("NI",        ni_val,   "#9b59b6",
                    "iterations to equilibrium")
            + _tile("SM",        sm_val,   "#e67e22",
                    "% in global minority")
            + _tile("IE",        ie_val,   ie_col,
                    "majority matches initial")
            + '</div>'
            + f'<div style="font-size:9px;color:#4a6a8a;padding:2px 14px;">'
            + f'NI = Number of Iterations  ·  SM = Stick in the Muds  ·  '
            + f'IE = Informational Efficiency  (Miller &amp; Page 2004, Tables 1 &amp; 2)</div>'
        ),
    )


# ── Page layout ───────────────────────────────────────────────────────────────

@solara.component
def PageLayout(model):
    """Vertical column: metrics → grid → fraction plot → count plot."""
    with solara.Column(style="width:100%; align-items:stretch;"):
        LiveMetrics(model)
        _space_fn(model)
        _frac_fn(model)
        _count_fn(model)


# ── Model parameters ──────────────────────────────────────────────────────────
# Matches the two experimental dimensions in Section 6 of the paper.

model_params = {
    "seed": {
        "type":  "InputText",
        "value": 42,
        "label": "Random seed",
    },
    # Updating rule — Tables 1 & 2 in the paper
    "update_rule": {
        "type":   "Select",
        "value":  "synchronous",
        "values": ["synchronous", "async_random", "async_incentive"],
        "label":  "Update rule  (paper's primary variable)",
    },
    # Neighbourhood structure — Tables 1 & 2 in the paper
    "neighborhood": {
        "type":   "Select",
        "value":  "five",
        "values": ["five", "cone", "global"],
        "label":  "Neighbourhood  (five / cone / global)",
    },
    # Grid size — paper uses 20×20 = 400 seats
    "rows": Slider("Rows (depth)", value=20, min=5, max=40, step=1),
    "cols": Slider("Cols (width)", value=20, min=5, max=40, step=1),
    # Quality threshold — paper fixes at 0.5
    "quality_threshold": Slider(
        "Quality threshold T  (paper: 0.5)",
        value=0.5, min=0.0, max=1.0, step=0.05,
    ),
    # Social threshold — paper uses majority = 0.5
    "social_threshold": Slider(
        "Social threshold S  (paper: 0.5 = majority)",
        value=0.5, min=0.0, max=1.0, step=0.05,
    ),
}


# ── Model instance and page ───────────────────────────────────────────────────

model = StandingOvationModel()

page = SolaraViz(
    model,
    components=[PageLayout],
    model_params=model_params,
    name="Standing Ovation Model  —  Miller & Page (2004)",
    play_interval=250,
)

page
