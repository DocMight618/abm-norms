"""
agent.py — CountryAgent for the UN Naming & Shaming model (Mesa 3.x).

Binary state: SHAME or NEUTRAL.

Per-agent Granovetter threshold (Option B)
──────────────────────────────────────────
Each agent holds its own `threshold` drawn from a Beta(alpha, beta)
distribution at construction.  The threshold is the fraction of maximum
possible neighbour pressure an agent requires before it becomes eligible
for recruitment into the shaming coalition.

Thresholds are not fixed: after every cascade window the model calls
`update_threshold()` on each agent, shifting the agent's personal Beta
distribution parameters based on whether the cascade succeeded or failed
from the agent's perspective:

  • If the agent was NEUTRAL throughout and the cascade was large  (norm
    consolidated): threshold drifts DOWN   — it becomes easier to join
    next time (Finnemore & Sikkink 1998 norm cascade logic).
  • If the agent was NEUTRAL throughout and the cascade was small  (norm
    eroding): threshold drifts UP — deviation is being normalised, the
    agent internalises non-shaming as acceptable (Barnett & Finnemore 2004).
  • Shaming agents are unaffected (they already crossed their threshold).

The global `shame_threshold` slider is retired; individual thresholds now
govern eligibility entirely.

Threshold anchoring
────────────────────
Initial Beta parameters are anchored to observable state properties so the
distribution is theoretically grounded rather than arbitrary:

  alpha  (model-level, shared): controls left-skew / ease of cascades globally
  beta   (per-agent)          : anchored to (1 - diplomatic_strength) × regime_factor
      Democracies:      beta_factor = 0.7  (lower threshold — norm entrepreneurs)
      Non-democracies:  beta_factor = 1.4  (higher threshold — sovereignty-first)
      P5 members:       beta_factor = 0.5  (lowest — structural veto power,
                                            joining is costless relative to peers)

This means a strong democracy (e.g. France, strength≈0.91) gets a very low
beta and thus a very low threshold ≈ Beta(alpha, 0.64) mode.  A weak
non-democracy (e.g. Nauru, strength≈0.015) gets beta≈1.39, a much higher
threshold.  The distribution is heterogeneous as Granovetter requires.

`diplomatic_strength`, `threshold`, `alpha_param`, `beta_param` are set
by UNModel._build_agents() immediately after construction.
"""

from mesa import Agent

NEUTRAL = "neutral"
SHAME   = "shame"

DEMOCRACY     = "democracy"
NON_DEMOCRACY = "non_democracy"

_DEMOCRACY_SET: frozenset[str] = frozenset({
    "United States of America", "Canada", "Mexico", "Guatemala", "Honduras",
    "El Salvador", "Costa Rica", "Panama", "Belize",
    "Trinidad and Tobago", "Barbados", "Jamaica", "Dominican Republic",
    "Bahamas", "Antigua and Barbuda", "Dominica", "Grenada",
    "Saint Kitts and Nevis", "Saint Lucia", "Saint Vincent and the Grenadines",
    "Brazil", "Argentina", "Chile", "Colombia", "Peru", "Uruguay",
    "Paraguay", "Ecuador", "Bolivia", "Guyana", "Suriname",
    "United Kingdom", "Germany", "France", "Italy", "Spain", "Portugal",
    "Netherlands", "Belgium", "Austria", "Switzerland", "Sweden", "Norway",
    "Denmark", "Finland", "Iceland", "Luxembourg", "Ireland", "Greece",
    "Cyprus", "Malta", "Poland", "Czech Republic", "Hungary", "Slovakia",
    "Slovenia", "Estonia", "Latvia", "Lithuania", "Croatia", "Romania",
    "Bulgaria", "Serbia", "Montenegro", "North Macedonia", "Albania",
    "Bosnia and Herzegovina", "Republic of Moldova", "Ukraine", "Georgia",
    "Armenia", "Liechtenstein", "San Marino", "Monaco", "Andorra",
    "Japan", "Republic of Korea", "Australia", "New Zealand", "India",
    "Indonesia", "Philippines", "Timor-Leste", "Mongolia",
    "Fiji", "Papua New Guinea", "Solomon Islands", "Vanuatu", "Samoa",
    "Tonga", "Kiribati", "Palau", "Federated States of Micronesia",
    "Marshall Islands", "Nauru", "Tuvalu",
    "South Africa", "Ghana", "Senegal", "Cabo Verde", "Mauritius",
    "Botswana", "Namibia", "Lesotho", "Madagascar", "Seychelles",
    "United Republic of Tanzania", "Rwanda", "Malawi", "Zambia",
    "Israel", "Tunisia", "Morocco",
    "Nepal", "Bangladesh", "Sri Lanka", "Maldives",
})

P5_NAMES: frozenset[str] = frozenset({
    "China", "France", "Russia", "United Kingdom", "United States of America",
})

_P5_SHORT_NAMES: dict[str, str] = {
    "China": "China",
    "France": "France",
    "Russia": "Russia",
    "United Kingdom": "UK",
    "United States of America": "USA",
}


def classify_regime(full_name: str) -> str:
    return DEMOCRACY if full_name in _DEMOCRACY_SET else NON_DEMOCRACY


# Regime-based beta anchor factors (lower = easier to join coalition)
_REGIME_BETA_FACTOR: dict[str, float] = {
    DEMOCRACY:     0.7,
    NON_DEMOCRACY: 1.4,
}
_P5_BETA_FACTOR = 0.5

# How much thresholds shift per cascade window (learning rate)
_THRESHOLD_DRIFT = 0.04

# Cascade "success" threshold: if >40% of states shame, norm is consolidating
_CASCADE_SUCCESS_FRAC = 0.40


class CountryAgent(Agent):
    """
    A UN member state node in a Mesa NetworkGrid.

    State transitions are orchestrated by UNModel.step().

    Attributes set at construction by UNModel._build_agents()
    ----------------------------------------------------------
    diplomatic_strength : float in [0, 1]
        Normalised GDI 2024 post count (max = China, 274 posts).

    threshold : float in [0, 1]
        Individual Granovetter threshold — the normalised neighbour
        pressure this agent requires before joining the coalition.
        Drawn from Beta(alpha_param, beta_param) at construction;
        updated after each cascade window.

    alpha_param, beta_param : float
        Current Beta distribution shape parameters for this agent.
        alpha_param is shared from the model; beta_param is per-agent
        and drifts over time based on cascade outcomes.
    """

    def __init__(self, model, country_name: str):
        super().__init__(model)
        self.country_name        = country_name
        self.regime              = classify_regime(country_name)
        self.state               = NEUTRAL
        self._next_state         = NEUTRAL
        self.diplomatic_strength = 0.0   # set by model
        self.threshold           = 0.5   # set by model
        self.alpha_param         = 2.0   # set by model
        self.beta_param          = 2.0   # set by model

    @property
    def short_name(self) -> str:
        """Compact display label, currently only needed for P5 map labels."""
        return _P5_SHORT_NAMES.get(self.country_name, self.country_name)

    # ── Two-phase synchronous update ─────────────────────────────────────────

    def step(self) -> None:
        """Copy current state into the synchronous-update buffer."""
        self._next_state = self.state

    def advance(self) -> None:
        """Commit the buffered decision after all agents have been evaluated."""
        self.state = self._next_state

    def reset(self, state: str = NEUTRAL) -> None:
        self.state       = state
        self._next_state = state

    # ── Decision rules ───────────────────────────────────────────────────────

    def baseline_beta(self, beta_scale: float) -> float:
        """Initial beta anchor implied by strength, regime, and P5 status."""
        regime_factor = (
            _P5_BETA_FACTOR
            if self.country_name in P5_NAMES
            else _REGIME_BETA_FACTOR[self.regime]
        )
        return (1.0 - self.diplomatic_strength) * regime_factor * beta_scale * 4.0

    def initialise_threshold(self, alpha: float, beta_scale: float, rng) -> None:
        """Set this agent's starting threshold distribution and draw theta."""
        self.alpha_param = alpha
        self.beta_param = max(0.5, self.baseline_beta(beta_scale))
        self.threshold = rng.betavariate(self.alpha_param, self.beta_param)

    def recruitment_weight(self, graph, grid) -> float:
        """
        Return this agent's weighted eligibility to become SHAME.

        The agent joins the candidate pool only when current neighbour pressure
        crosses its personal Granovetter threshold. P5 shaming neighbours double
        the recruitment weight.
        """
        if self._next_state != NEUTRAL:
            return 0.0

        raw_pressure = 0.0
        max_pressure = 0.0
        p5_bonus = 1.0

        for nb_node in graph.neighbors(self.pos):
            edge_weight = graph[self.pos][nb_node].get("weight", 0.1)
            max_pressure += edge_weight
            for neighbour in grid.get_cell_list_contents([nb_node]):
                if neighbour._next_state == SHAME:
                    raw_pressure += edge_weight
                    if neighbour.country_name in P5_NAMES:
                        p5_bonus = 2.0

        norm_pressure = (
            raw_pressure / max_pressure
            if max_pressure > 0
            else 0.0
        )
        if norm_pressure < self.threshold:
            return 0.0

        return raw_pressure * p5_bonus + 0.01

    def revert_weight(self) -> float:
        """Return this agent's weighted likelihood of reverting to NEUTRAL."""
        if self._next_state != SHAME:
            return 0.0

        weight = 1.0 - self.diplomatic_strength
        if self.country_name in P5_NAMES:
            weight *= 0.5
        return max(weight, 0.01)

    def choose_shaming(self) -> None:
        """Buffer the decision to join the shaming coalition."""
        self._next_state = SHAME

    def choose_neutral(self) -> None:
        """Buffer the decision to leave the shaming coalition."""
        self._next_state = NEUTRAL

    # ── Threshold update (called by model after each cascade window) ──────────

    def update_threshold(self, cascade_fraction: float, rng) -> None:
        """
        Shift this agent's Beta distribution based on the cascade outcome,
        then re-draw the threshold from the updated distribution.

        cascade_fraction : float in [0, 1]
            Fraction of all agents that were shaming at end of window.

        Logic (Barnett & Finnemore 2004 + Granovetter 1978):
          - Large cascade (norm consolidating): beta drifts DOWN → lower
            threshold → easier to join next time.
          - Small cascade (norm eroding / deviation normalised): beta drifts
            UP → higher threshold → harder to join next time.
          Only neutral agents update; shamers already cleared their threshold.
        """
        if self.state == SHAME:
            return   # shamers don't update; they already joined

        if cascade_fraction >= _CASCADE_SUCCESS_FRAC:
            # Norm consolidating — lower threshold
            self.beta_param = max(0.5, self.beta_param - _THRESHOLD_DRIFT)
        else:
            # Norm eroding — raise threshold (deviation normalised)
            self.beta_param = min(10.0, self.beta_param + _THRESHOLD_DRIFT)

        # Re-draw threshold from updated distribution
        self.threshold = rng.betavariate(self.alpha_param, self.beta_param)

    def __repr__(self) -> str:
        return (
            f"CountryAgent({self.country_name!r}, "
            f"regime={self.regime}, node={self.pos}, "
            f"state={self.state!r}, strength={self.diplomatic_strength:.3f}, "
            f"threshold={self.threshold:.3f})"
        )
