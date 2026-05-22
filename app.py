"""
app.py — UN Shaming Cascade visualised with Mesa SolaraViz.

Layout (top → bottom):
  1. Live counter  — step, shaming, neutral, dem/non-dem, P5 counts
  2. Network map   — complete forum ties weighted by strength and regime
  3. Shaming plot  — Shaming vs Neutral over time
  4. Regime plot   — Democracy vs Non-democracy shaming over time

Network portrayal
─────────────────
  Node colour   : Red (#e8003d) = shaming, Dark-blue (#1e3a5f) = neutral
  Node border   : White = democracy, Amber = non-democracy
  Node size     : Scaled by diplomatic_strength (GDI 2024); P5 always largest
  Edge colour   : Brightness proportional to forum tie weight
  Edge width    : Proportional to edge weight
  Tooltip       : Country name, state, regime, GDI strength score, P5 status
"""

import solara
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.colors as mcolors
import networkx as nx
import numpy as np
import plotly.graph_objects as go

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
    """
    Zoomable / pannable Plotly network map.
    Scroll to zoom, drag to pan, hover for country details.
    """
    update_counter.get()

    agents = model._agent_list
    G      = model.G
    pos    = _get_pos(model)

    p5_ids = {i for i, a in enumerate(agents) if a.country_name in P5_NAMES}

    # ── Edge traces (regular vs hub, batched with None separators) ────────────
    reg_x, reg_y, hub_x, hub_y = [], [], [], []
    for u, v, data in G.edges(data=True):
        x0, y0 = pos[u]
        x1, y1 = pos[v]
        if u in p5_ids or v in p5_ids:
            hub_x += [x0, x1, None]
            hub_y += [y0, y1, None]
        else:
            reg_x += [x0, x1, None]
            reg_y += [y0, y1, None]

    edge_traces = []
    if reg_x:
        edge_traces.append(go.Scatter(
            x=reg_x, y=reg_y, mode="lines",
            line=dict(width=0.8, color="rgba(30,60,100,0.35)"),
            hoverinfo="none", showlegend=False,
        ))
    if hub_x:
        edge_traces.append(go.Scatter(
            x=hub_x, y=hub_y, mode="lines",
            line=dict(width=1.8, color="rgba(58,127,193,0.55)"),
            hoverinfo="none", showlegend=False,
        ))

    # ── Node traces — four groups for the legend ──────────────────────────────
    groups = {
        ("dem",    "shame"):   {"label": "Democracy · Shaming",     "color": "#e8003d", "border": "#ffffff"},
        ("dem",    "neutral"): {"label": "Democracy · Neutral",      "color": "#1e3a5f", "border": "#ffffff"},
        ("nondem", "shame"):   {"label": "Non-democracy · Shaming",  "color": "#e8003d", "border": "#f39c12"},
        ("nondem", "neutral"): {"label": "Non-democracy · Neutral",  "color": "#1e3a5f", "border": "#f39c12"},
    }
    group_data = {k: {"x": [], "y": [], "text": [], "size": [], "labels": []}
                  for k in groups}

    MIN_SZ, MAX_SZ, P5_SZ = 12, 55, 80

    for i, a in enumerate(agents):
        rk  = "dem" if a.regime == DEMOCRACY else "nondem"
        key = (rk, a.state)
        x, y = pos[i]
        sz = P5_SZ if a.country_name in P5_NAMES else int(
            MIN_SZ + a.diplomatic_strength * (MAX_SZ - MIN_SZ))
        p5_tag = " \u2605 P5" if a.country_name in P5_NAMES else ""

        # Compute normalised pressure for tooltip
        raw_p = 0.0
        max_p = 0.0
        for nb_node in G.neighbors(i):
            ew = G[i][nb_node].get("weight", 0.1)
            max_p += ew
            for nbr in model.grid.get_cell_list_contents([nb_node]):
                if nbr.state == SHAME:
                    raw_p += ew
        norm_p    = (raw_p / max_p) if max_p > 0 else 0.0
        threshold = a.threshold
        eligible  = "Yes" if norm_p >= threshold else f"No (needs {threshold:.3f})"

        tip = (
            f"<b>{a.country_name}</b>{p5_tag}<br>"
            f"State: {'Shaming' if a.state == 'shame' else 'Neutral'}<br>"
            f"Regime: {'Democracy' if a.regime == DEMOCRACY else 'Non-democracy'}<br>"
            f"GDI strength: {a.diplomatic_strength:.3f}<br>"
            f"Network degree: {G.degree(i)}<br>"
            f"Normalised pressure: {norm_p:.3f}<br>"
            f"Personal threshold \u03b8: {threshold:.3f}  "
            f"[\u03b1={a.alpha_param:.2f}, \u03b2={a.beta_param:.2f}]<br>"
            f"Eligible for recruitment: {eligible}"
        )
        group_data[key]["x"].append(x)
        group_data[key]["y"].append(y)
        group_data[key]["text"].append(tip)
        group_data[key]["size"].append(sz)
        group_data[key]["labels"].append(a.short_name if a.country_name in P5_NAMES else "")

    node_traces = []
    for key, meta in groups.items():
        gd = group_data[key]
        if not gd["x"]:
            continue
        node_traces.append(go.Scatter(
            x=gd["x"], y=gd["y"],
            mode="markers+text",
            name=meta["label"],
            marker=dict(
                size=gd["size"],
                color=meta["color"],
                line=dict(color=meta["border"], width=2),
                opacity=0.92,
            ),
            text=gd["labels"],
            textposition="middle center",
            textfont=dict(color="#e8f0ff", size=11, family="Arial Black"),
            hovertext=gd["text"],
            hoverinfo="text",
            hoverlabel=dict(
                bgcolor="#0d1b2a", bordercolor="#3a7fc1",
                font=dict(color="#c9d8e8", size=13),
            ),
        ))

    # ── Assemble Plotly figure ────────────────────────────────────────────────
    s = model.get_stats()
    pfig = go.Figure(data=edge_traces + node_traces)
    pfig.update_layout(
        title=dict(
            text=(
                f"UN Shaming Cascade · 193 member states · "
                f"complete forum network · weighted by strength + regime affinity<br>"
                f"<sup>Step {s['step']} · {s['shaming']} shaming "
                f"({s['pct_shame']}%) · Left = Democracies · "
                f"Right = Non-democracies · Node size ∝ diplomatic strength</sup>"
            ),
            font=dict(color="#c9d8e8", size=22),
            x=0.5, xanchor="center",
        ),
        paper_bgcolor="#0d1b2a",
        plot_bgcolor="#0d1b2a",
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False,
                   scaleanchor="x"),
        legend=dict(
            font=dict(color="#c9d8e8", size=18),
            bgcolor="rgba(13,27,42,0.7)",
            bordercolor="#1a3050",
            borderwidth=1,
            itemsizing="constant",
            x=0.01, y=0.01,
        ),
        margin=dict(l=10, r=10, t=90, b=10),
        height=900,
        autosize=True,
        dragmode="pan",
        uirevision="network",
    )

    with solara.Column(style="width:100%; max-width:100%;"):
        solara.FigurePlotly(pfig)


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


@solara.component
def ThresholdPlot(model):
    """
    Three-panel Granovetter threshold plot.
      Top    : Mean threshold over time (with ±1 std band).
      Middle : Norm-erosion index — fraction of agents whose beta has risen
               above baseline (Barnett & Finnemore 2004 internalisation metric).
      Bottom : Current threshold distribution as a histogram (all 193 agents).
    """
    update_counter.get()
    df = model.datacollector.get_model_vars_dataframe()

    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(72, 48), dpi=120)
    fig.patch.set_facecolor("#0d1b2a")
    for ax in (ax1, ax2, ax3):
        ax.set_facecolor("#0d1b2a")
        ax.tick_params(colors="#c9d8e8", labelsize=28)
        for spine in ax.spines.values():
            spine.set_edgecolor("#1a3050")

    # Panel 1: mean threshold ± std
    if not df.empty and "MeanThreshold" in df.columns:
        mu  = df["MeanThreshold"]
        std = df["StdThreshold"]
        ax1.plot(df.index, mu,  color="#f0c040", linewidth=2, label="Mean threshold")
        ax1.fill_between(df.index, mu - std, mu + std,
                         color="#f0c040", alpha=0.20, label="±1 std")
        ax1.set_ylim(0, 1)
    ax1.set_xlabel("Step", color="#c9d8e8", fontsize=36)
    ax1.set_ylabel("Threshold", color="#c9d8e8", fontsize=36)
    ax1.set_title(
        "Mean Granovetter threshold over time  "
        "(rising = norm eroding / deviation normalised)",
        color="#c9d8e8", fontsize=36, pad=20)
    ax1.legend(fontsize=32, facecolor="#0d1b2a", edgecolor="#1a3050", labelcolor="#c9d8e8")

    # Panel 2: norm-erosion index
    if not df.empty and "NormEroding" in df.columns:
        ax2.plot(df.index, df["NormEroding"] / 100,
                 color="#e8003d", linewidth=2, label="Norm-erosion index")
        ax2.set_ylim(0, 1)
    ax2.set_xlabel("Step", color="#c9d8e8", fontsize=36)
    ax2.set_ylabel("Fraction", color="#c9d8e8", fontsize=36)
    ax2.set_title(
        "Norm-erosion index  "
        "(fraction of agents who have internalised deviation as acceptable)",
        color="#c9d8e8", fontsize=36, pad=20)
    ax2.legend(fontsize=32, facecolor="#0d1b2a", edgecolor="#1a3050", labelcolor="#c9d8e8")

    # Panel 3: current threshold distribution histogram
    thresholds = [a.threshold for a in model._agent_list]
    dem_t      = [a.threshold for a in model._agent_list if a.regime == DEMOCRACY]
    ndem_t     = [a.threshold for a in model._agent_list if a.regime != DEMOCRACY]
    bins = 30
    ax3.hist(dem_t,  bins=bins, color="royalblue", alpha=0.65,
             label="Democracies",     edgecolor="#0d1b2a")
    ax3.hist(ndem_t, bins=bins, color="tomato",    alpha=0.65,
             label="Non-democracies", edgecolor="#0d1b2a")
    s = model.get_stats()
    ax3.axvline(s["mean_threshold"], color="#f0c040", linewidth=3,
                linestyle="--", label=f"Mean θ={s['mean_threshold']:.3f}")
    ax3.set_xlabel("Individual threshold θ", color="#c9d8e8", fontsize=36)
    ax3.set_ylabel("# agents", color="#c9d8e8", fontsize=36)
    ax3.set_title(
        "Current Granovetter threshold distribution  "
        "(Barnett & Finnemore 2004: deviation internalised as new norm when distribution shifts right)",
        color="#c9d8e8", fontsize=36, pad=20)
    ax3.legend(fontsize=32, facecolor="#0d1b2a", edgecolor="#1a3050", labelcolor="#c9d8e8")

    fig.tight_layout(pad=1.2)
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

            # Mean Granovetter threshold
            + _tile("MEAN θ", f"{s['mean_threshold']:.3f}", "#f0c040",
                    f"±{s['std_threshold']:.3f} std", sub_color="#906010",
                    border_color="#2a3010", label_color="#8a8a20")

            # Norm-erosion index
            + _tile("NORM ERODING", f"{s['norm_eroding']}%", "#e87060",
                    "agents above baseline", sub_color="#803020",
                    border_color="#3a1010", label_color="#8a4030")

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
            width: 100vw !important;
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
        ThresholdPlot(model)


# ── Model parameters ──────────────────────────────────────────────────────────

model_params = {
    "seed": {
        "type":  "InputText",
        "value": 42,
        "label": "Random seed",
    },
    "alpha": {
        "type":  "InputText",
        "value": 2.0,
        "label": "Alpha — Beta left-skew (higher = easier cascades globally)",
    },
    "beta_scale": {
        "type":  "InputText",
        "value": 1.0,
        "label": "Beta scale — initial threshold height (higher = harder cascades)",
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
