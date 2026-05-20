"""
app.py — UN Shaming Cascade visualised with Mesa SolaraViz.

Layout (top → bottom):
  1. Live counter  — step, shaming, neutral, dem/non-dem, P5 counts
  2. Network map   — nodes sized & edges weighted by GDI diplomatic strength
  3. Shaming plot  — Shaming vs Neutral over time
  4. Regime plot   — Democracy vs Non-democracy shaming over time

Network portrayal
─────────────────
  Node colour   : Red (#e8003d) = shaming, Dark-blue (#1e3a5f) = neutral
  Node border   : White = democracy, Amber = non-democracy
  Node size     : Scaled by diplomatic_strength (GDI 2024); P5 always largest
  Edge colour   : Brightness proportional to edge weight (avg strength of pair)
  Edge width    : Proportional to edge weight
  Tooltip       : Country name, state, regime, GDI strength score, P5 status
"""

import solara
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.colors as mcolors
import networkx as nx
import numpy as np

from mesa.visualization.components.matplotlib_components import (
    update_counter,
)
from mesa.visualization import SolaraViz

from model import UNModel, P5_NAMES
from agent import NEUTRAL, SHAME, DEMOCRACY, NON_DEMOCRACY


# ── Stable layout cache ───────────────────────────────────────────────────────

_POS_CACHE: dict = {}


def _get_pos(model: UNModel) -> dict:
    """
    Compute (once) a spring layout seeded so democracies cluster left,
    non-democracies right.  P5 nodes seeded near their cluster centre.
    """
    key = id(model)
    if key in _POS_CACHE:
        return _POS_CACHE[key]

    G      = model.G
    agents = model._agent_list
    rng_np = np.random.default_rng(42)

    seed_pos = {}
    for i, a in enumerate(agents):
        is_dem = a.regime == DEMOCRACY
        is_p5  = a.country_name in P5_NAMES
        if is_p5:
            x = -0.15 if is_dem else 0.15
            y = rng_np.uniform(-0.1, 0.1)
        elif is_dem:
            x = rng_np.uniform(-1.0, -0.05)
            y = rng_np.uniform(-0.9,  0.9)
        else:
            x = rng_np.uniform(0.05, 1.0)
            y = rng_np.uniform(-0.9, 0.9)
        seed_pos[i] = np.array([x, y])

    pos = nx.spring_layout(
        G,
        pos=seed_pos,
        fixed=None,
        iterations=150,
        seed=42,
        k=0.16,
        weight="weight",   # use diplomatic strength as attraction weight
    )
    _POS_CACHE[key] = pos
    return pos


# ── Custom network Matplotlib component ──────────────────────────────────────

@solara.component
def NetworkMap(model):
    """Draws the UN diplomatic network every model step."""
    update_counter.get()

    agents = model._agent_list
    G      = model.G
    pos    = _get_pos(model)
    n      = len(agents)

    fig, ax = plt.subplots(figsize=(72, 48), dpi=120)
    fig.patch.set_facecolor("#0d1b2a")
    ax.set_facecolor("#0d1b2a")
    ax.set_axis_off()

    p5_ids = {i for i, a in enumerate(agents) if a.country_name in P5_NAMES}

    # — Edges coloured and sized by diplomatic strength (edge weight) ──────────
    edge_list   = list(G.edges(data=True))
    hub_edges   = [(u, v) for u, v, _ in edge_list if u in p5_ids or v in p5_ids]
    reg_edges   = [(u, v) for u, v, _ in edge_list if u not in p5_ids and v not in p5_ids]

    def _edge_colors_widths(edges, base_alpha=0.4, hub=False):
        colors, widths = [], []
        for u, v in edges:
            w = G[u][v].get("weight", 0.1)
            # Interpolate from dim (#0e2a44) to bright (#3a7fc1) by weight
            r = int(14  + w * (58  - 14))
            g = int(42  + w * (127 - 42))
            b = int(68  + w * (193 - 68))
            colors.append(f"#{r:02x}{g:02x}{b:02x}")
            widths.append(0.3 + w * (2.5 if hub else 1.2))
        return colors, widths

    reg_colors, reg_widths = _edge_colors_widths(reg_edges, hub=False)
    hub_colors, hub_widths = _edge_colors_widths(hub_edges, hub=True)

    if reg_edges:
        nx.draw_networkx_edges(
            G, pos, edgelist=reg_edges, ax=ax,
            edge_color=reg_colors, width=reg_widths, alpha=0.38,
        )
    if hub_edges:
        nx.draw_networkx_edges(
            G, pos, edgelist=hub_edges, ax=ax,
            edge_color=hub_colors, width=hub_widths, alpha=0.60,
        )

    # — Nodes sized by diplomatic_strength ────────────────────────────────────
    MIN_SZ, MAX_SZ = 300, 4000   # area in scatter units
    P5_SZ          = 6000

    node_colors     = []
    node_edgecolors = []
    node_sizes      = []

    for i, a in enumerate(agents):
        node_colors.append("#e8003d" if a.state == SHAME else "#1e3a5f")
        node_edgecolors.append("#ffffff" if a.regime == DEMOCRACY else "#f39c12")
        if a.country_name in P5_NAMES:
            node_sizes.append(P5_SZ)
        else:
            node_sizes.append(int(MIN_SZ + a.diplomatic_strength * (MAX_SZ - MIN_SZ)))

    regular_nodes = [i for i in range(n) if i not in p5_ids]
    p5_node_list  = list(p5_ids)

    nx.draw_networkx_nodes(
        G, pos, nodelist=regular_nodes, ax=ax,
        node_color=[node_colors[i] for i in regular_nodes],
        node_size=[node_sizes[i]   for i in regular_nodes],
        edgecolors=[node_edgecolors[i] for i in regular_nodes],
        linewidths=1.0,
    )
    nx.draw_networkx_nodes(
        G, pos, nodelist=p5_node_list, ax=ax,
        node_color=[node_colors[i] for i in p5_node_list],
        node_size=[node_sizes[i]   for i in p5_node_list],
        edgecolors=[node_edgecolors[i] for i in p5_node_list],
        linewidths=2.8,
    )

    # — P5 labels ─────────────────────────────────────────────────────────────
    nx.draw_networkx_labels(
        G, {i: pos[i] for i in p5_node_list},
        labels={i: agents[i].short_name for i in p5_node_list},
        ax=ax, font_size=18, font_color="#e8f0ff", font_weight="bold",
    )

    # — Legend ────────────────────────────────────────────────────────────────
    legend_elements = [
        mpatches.Patch(facecolor="#e8003d", edgecolor="#fff", label="Shaming"),
        mpatches.Patch(facecolor="#1e3a5f", edgecolor="#fff", label="Neutral"),
        mpatches.Patch(facecolor="#555", edgecolor="#ffffff", linewidth=1.5,
                       label="Democracy (white border)"),
        mpatches.Patch(facecolor="#555", edgecolor="#f39c12", linewidth=1.5,
                       label="Non-democracy (amber border)"),
        mpatches.Patch(facecolor="#888", edgecolor="#fff",
                       label="Node size ∝ GDI diplomatic strength"),
        mpatches.Patch(facecolor="#1e4a8a", edgecolor="#3a7fc1",
                       label="Edge brightness ∝ avg diplomatic strength"),
    ]
    ax.legend(
        handles=legend_elements, loc="lower left", fontsize=36,
        framealpha=0.35, facecolor="#0d1b2a",
        edgecolor="#1a3050", labelcolor="#c9d8e8",
    )

    # — Title ─────────────────────────────────────────────────────────────────
    s = model.get_stats()
    ax.set_title(
        f"UN Shaming Cascade  ·  193 member states  ·  "
        f"edge weights = Lowy GDI 2024 diplomatic strength\n"
        f"Step {s['step']}  ·  {s['shaming']} shaming ({s['pct_shame']}%)  ·  "
        f"Left = Democracies  ·  Right = Non-democracies  ·  "
        f"Larger nodes = stronger diplomatic footprint",
        color="#c9d8e8", fontsize=36, pad=12,
    )

    fig.tight_layout(pad=0.5)
    solara.FigureMatplotlib(fig, dependencies=[model.step_count])
    plt.close(fig)


# ── Time-series plots (full-width custom components) ─────────────────────────

@solara.component
def ShamingPlot(model):
    update_counter.get()
    df = model.datacollector.get_model_vars_dataframe()
    fig, ax = plt.subplots(figsize=(72, 24), dpi=120)
    fig.patch.set_facecolor("#0d1b2a")
    ax.set_facecolor("#0d1b2a")
    if not df.empty:
        ax.plot(df.index, df["Shaming"], color="red",      linewidth=2, label="Shaming")
        ax.plot(df.index, df["Neutral"], color="steelblue", linewidth=2, label="Neutral")
    ax.set_xlabel("Step", color="#c9d8e8", fontsize=36)
    ax.set_ylabel("Count", color="#c9d8e8", fontsize=36)
    ax.set_title("Shaming vs Neutral over time", color="#c9d8e8", fontsize=36, pad=20)
    ax.tick_params(colors="#c9d8e8", labelsize=28)
    for spine in ax.spines.values():
        spine.set_edgecolor("#1a3050")
    ax.legend(fontsize=32, facecolor="#0d1b2a", edgecolor="#1a3050", labelcolor="#c9d8e8")
    fig.tight_layout(pad=0.5)
    solara.FigureMatplotlib(fig, dependencies=[model.step_count])
    plt.close(fig)


@solara.component
def RegimePlot(model):
    update_counter.get()
    df = model.datacollector.get_model_vars_dataframe()
    fig, ax = plt.subplots(figsize=(72, 24), dpi=120)
    fig.patch.set_facecolor("#0d1b2a")
    ax.set_facecolor("#0d1b2a")
    if not df.empty:
        ax.plot(df.index, df["DemShame"],    color="royalblue", linewidth=2, label="Democracy shaming")
        ax.plot(df.index, df["NonDemShame"], color="tomato",    linewidth=2, label="Non-democracy shaming")
    ax.set_xlabel("Step", color="#c9d8e8", fontsize=36)
    ax.set_ylabel("Count", color="#c9d8e8", fontsize=36)
    ax.set_title("Democracy vs Non-democracy shaming over time", color="#c9d8e8", fontsize=36, pad=20)
    ax.tick_params(colors="#c9d8e8", labelsize=28)
    for spine in ax.spines.values():
        spine.set_edgecolor("#1a3050")
    ax.legend(fontsize=32, facecolor="#0d1b2a", edgecolor="#1a3050", labelcolor="#c9d8e8")
    fig.tight_layout(pad=0.5)
    solara.FigureMatplotlib(fig, dependencies=[model.step_count])
    plt.close(fig)


# ── Live counter ──────────────────────────────────────────────────────────────

@solara.component
def LiveCounter(model):
    update_counter.get()

    s        = model.get_stats()
    step     = s["step"]
    shaming  = s["shaming"]
    neutral  = s["neutral"]
    pct      = s["pct_shame"]
    dem_n    = model._regime_count(DEMOCRACY,    SHAME)
    nondem_n = model._regime_count(NON_DEMOCRACY, SHAME)
    dem_total    = sum(1 for a in model._agent_list if a.regime == DEMOCRACY)
    nondem_total = sum(1 for a in model._agent_list if a.regime == NON_DEMOCRACY)
    p5_shaming   = sum(1 for a in model._agent_list
                       if a.country_name in P5_NAMES and a.state == SHAME)

    # Weighted shaming: sum of diplomatic_strength for shaming states
    w_shame = sum(a.diplomatic_strength for a in model._agent_list
                  if a.state == SHAME)
    w_total = sum(a.diplomatic_strength for a in model._agent_list)
    w_pct   = round(100 * w_shame / w_total, 1) if w_total else 0.0

    solara.HTML(
        "div",
        unsafe_innerHTML=(
            '<div style="display:flex;flex-direction:row;flex-wrap:wrap;gap:12px;'
            'padding:14px 16px;background:#0f1e30;border-radius:8px;'
            'border:1px solid #1a3050;margin:8px 0;">'
            + _tile("STEP", str(step), "#1e90ff", "")

            # Shaming
            + _tile("SHAMING", str(shaming), "#e8003d", f"{pct}%", sub_color="#a03050")

            # Neutral
            + _tile("NEUTRAL", str(neutral), "#5aa0c8",
                    f"{round(100 - pct, 1)}%", sub_color="#3a6a8a")

            # Demo shaming
            + _tile("DEMO. SHAMING", str(dem_n), "#2e86de",
                    f"of {dem_total} democracies", sub_color="#1a5090")

            # Non-dem shaming
            + _tile("NON-DEM. SHAMING", str(nondem_n), "#c0392b",
                    f"of {nondem_total} non-dem.", sub_color="#802020")

            # P5 shaming
            + _tile("P5 SHAMING", str(p5_shaming), "#f0c040",
                    "of 5 P5 members", sub_color="#906010",
                    border_color="#2e5a8a", label_color="#4a8aaa")

            # Weighted diplomatic power shaming
            + _tile("WEIGHTED SHAME", f"{w_pct}%", "#a0d8a0",
                    "by GDI strength", sub_color="#406040",
                    border_color="#1a4030", label_color="#4a8a6a")

            + '</div>'
        ),
    )


def _tile(
    label: str,
    value: str,
    value_color: str,
    sub: str = "",
    sub_color: str = "#555",
    border_color: str = "#1a3050",
    label_color: str = "#4a6a8a",
) -> str:
    return (
        f'<div style="display:flex;flex-direction:column;align-items:center;'
        f'background:#0d1b2a;border-radius:6px;padding:10px 18px;min-width:100px;'
        f'border:1px solid {border_color};">'
        f'<span style="font-size:11px;color:{label_color};font-weight:600;'
        f'letter-spacing:.05em;margin-bottom:4px;">{label}</span>'
        f'<span style="font-size:32px;font-weight:700;color:{value_color};'
        f'line-height:1;">{value}</span>'
        + (f'<span style="font-size:11px;color:{sub_color};margin-top:3px;">'
           f'{sub}</span>' if sub else "")
        + '</div>'
    )


# ── Combined layout ───────────────────────────────────────────────────────────


@solara.component
def PageLayout(model):
    solara.Style("""
        .un-full-width {
            width: 85vw !important;
            max-width: 100vw !important;
            margin-left: calc(-50vw + 50%) !important;
            box-sizing: border-box;
            overflow-x: hidden;
        }
        .un-full-width img {
            width: 100% !important;
            height: auto !important;
            display: block !important;
        }
    """)
    with solara.Column(classes=["un-full-width"],
                       style="align-items:stretch; padding:0; gap:0;"):
        LiveCounter(model)
        NetworkMap(model)
        ShamingPlot(model)
        RegimePlot(model)


# ── Model parameters ──────────────────────────────────────────────────────────

model_params = {
    "seed": {
        "type":  "InputText",
        "value": 42,
        "label": "Random seed",
    },
    "shame_threshold": {
        "type":  "InputText",
        "value": 0.50,
        "label": "Shame threshold θ  (0.0 – 1.0)",
    },
    "shame_min": {
        "type":  "InputText",
        "value": 20,
        "label": "Min initial shamers  (0 – 193)",
    },
    "shame_max": {
        "type":  "InputText",
        "value": 77,
        "label": "Max initial shamers  (0 – 193)",
    },
    "spread": {
        "type":  "InputText",
        "value": 10,
        "label": "Spread  (+ recruit  /  − revert)",
    },
}


# ── Model instance and page ───────────────────────────────────────────────────

model = UNModel()

page = SolaraViz(
    model,
    components=[PageLayout],
    model_params=model_params,
    name="UN Shaming Cascade  —  GDI Weighted Network (Mesa)",
    play_interval=300,
)

page
