"""
model.py — UNModel (Mesa 3.x), binary SHAME / NEUTRAL.

193 agents on a NetworkX weighted graph.

Diplomatic strength (0–1) per country
──────────────────────────────────────
Source: Lowy Institute Global Diplomacy Index 2024.
  • The 65 GDI-covered countries have their total diplomatic posts recorded.
  • The remaining ~128 UN member states (not in the GDI) receive an estimated
    post count derived from their regional group and population tier.
  • All raw counts are normalised to [0, 1] relative to China (max = 274 posts).

Forum network
─────────────
The UN forum is represented as a complete directed weighted graph: every state
can observe every other state, but influence is asymmetric. An edge A -> B
measures how much pressure A's public position places on B.

Spreading mechanic
──────────────────
  spread > 0 : recruit NEUTRAL agents weighted by neighbour shaming pressure
               AND by the edge weight (stronger diplomatic tie = more pressure).
               P5 shamers grant a 2× bonus to their neighbours.
               Only agents whose normalised pressure crosses their individual
               threshold are eligible before weighted sampling.
  spread < 0 : revert SHAMING agents; weaker states easier to flip; P5 halved.
  spread = 0 : no global spread / reversion.

Per-agent Granovetter threshold distribution (Option B)
───────────────────────────────────────────────────────
Each agent draws its own threshold from Beta(alpha, beta_agent) at
construction.  beta_agent is anchored to (1 - diplomatic_strength) and
a regime factor (democracies lower, non-democracies higher, P5 lowest).
After each cascade window the model updates each neutral agent's beta_param
and redraws its threshold based on cascade outcome:
  large cascade  --> beta drifts down  (norm consolidating, easier to join)
  small cascade  --> beta drifts up    (norm eroding, deviation normalised)

Global model params: alpha (left-skew, shared), beta_scale (starting threshold scale).

Every NEUTRAL_RESET_EVERY (5) steps states are re-randomised; network is fixed.
"""

import networkx as nx

from mesa import Model
from mesa.space import NetworkGrid
from mesa.datacollection import DataCollector

from agent import (
    CountryAgent,
    NEUTRAL,
    SHAME,
    DEMOCRACY,
    NON_DEMOCRACY,
    P5_NAMES,
)


# ── 193 UN General Assembly members ──────────────────────────────────────────
_UN_193: list[str] = [
    "Afghanistan", "Albania", "Algeria", "Andorra", "Angola",
    "Antigua and Barbuda", "Argentina", "Armenia", "Australia", "Austria",
    "Azerbaijan", "Bahamas", "Bahrain", "Bangladesh", "Barbados", "Belarus",
    "Belgium", "Belize", "Benin", "Bhutan", "Bolivia",
    "Bosnia and Herzegovina", "Botswana", "Brazil", "Brunei Darussalam",
    "Bulgaria", "Burkina Faso", "Burundi", "Cabo Verde", "Cambodia",
    "Cameroon", "Canada", "Central African Republic", "Chad", "Chile",
    "China", "Colombia", "Comoros", "Congo",
    "Democratic Republic of the Congo", "Costa Rica", "Côte d'Ivoire",
    "Croatia", "Cuba", "Cyprus", "Czech Republic", "Denmark", "Djibouti",
    "Dominica", "Dominican Republic", "Ecuador", "Egypt", "El Salvador",
    "Equatorial Guinea", "Eritrea", "Estonia", "Eswatini", "Ethiopia",
    "Fiji", "Finland", "France", "Gabon", "Gambia", "Georgia", "Germany",
    "Ghana", "Greece", "Grenada", "Guatemala", "Guinea", "Guinea-Bissau",
    "Guyana", "Haiti", "Honduras", "Hungary", "Iceland", "India",
    "Indonesia", "Iran", "Iraq", "Ireland", "Israel", "Italy", "Jamaica",
    "Japan", "Jordan", "Kazakhstan", "Kenya", "Kiribati",
    "Democratic People's Republic of Korea", "Republic of Korea", "Kuwait",
    "Kyrgyzstan", "Lao People's Democratic Republic", "Latvia", "Lebanon",
    "Lesotho", "Liberia", "Libya", "Liechtenstein", "Lithuania",
    "Luxembourg", "Madagascar", "Malawi", "Malaysia", "Maldives", "Mali",
    "Malta", "Marshall Islands", "Mauritania", "Mauritius", "Mexico",
    "Federated States of Micronesia", "Republic of Moldova", "Monaco",
    "Mongolia", "Montenegro", "Morocco", "Mozambique", "Myanmar", "Namibia",
    "Nauru", "Nepal", "Netherlands", "New Zealand", "Nicaragua", "Niger",
    "Nigeria", "North Macedonia", "Norway", "Oman", "Pakistan", "Palau",
    "Panama", "Papua New Guinea", "Paraguay", "Peru", "Philippines",
    "Poland", "Portugal", "Qatar", "Romania", "Russia", "Rwanda",
    "Saint Kitts and Nevis", "Saint Lucia",
    "Saint Vincent and the Grenadines", "Samoa", "San Marino",
    "Sao Tome and Principe", "Saudi Arabia", "Senegal", "Serbia",
    "Seychelles", "Sierra Leone", "Singapore", "Slovakia", "Slovenia",
    "Solomon Islands", "Somalia", "South Africa", "South Sudan", "Spain",
    "Sri Lanka", "Sudan", "Suriname", "Sweden", "Switzerland", "Syria",
    "Tajikistan", "United Republic of Tanzania", "Thailand", "Timor-Leste",
    "Togo", "Tonga", "Trinidad and Tobago", "Tunisia", "Turkey",
    "Turkmenistan", "Tuvalu", "Uganda", "Ukraine", "United Arab Emirates",
    "United Kingdom", "United States of America", "Uruguay", "Uzbekistan",
    "Vanuatu", "Venezuela", "Viet Nam", "Yemen", "Zambia", "Zimbabwe",
]
assert len(_UN_193) == 193 and len(set(_UN_193)) == 193

# ── Lowy Institute GDI 2024: total diplomatic posts per country ───────────────
# Source: Wikipedia / GDI 2024
# (https://en.wikipedia.org/wiki/List_of_countries_by_number_of_diplomatic_missions)
# Max = 274 (China). Names matched to _UN_193 keys.
_GDI_POSTS: dict[str, int] = {
    "China":                                    274,
    "United States of America":                 271,
    "Turkey":                                   252,
    "Japan":                                    251,
    "France":                                   249,
    "Russia":                                   230,
    "United Kingdom":                           225,
    "Spain":                                    218,
    "Germany":                                  217,
    "Italy":                                    206,
    "Brazil":                                   205,
    "India":                                    201,
    "Republic of Korea":                        187,
    "Mexico":                                   161,
    "Canada":                                   157,
    "Argentina":                                150,
    "Netherlands":                              149,
    "Switzerland":                              141,
    "Hungary":                                  140,
    "Poland":                                   135,
    "Greece":                                   134,
    "Indonesia":                                130,
    "Saudi Arabia":                             128,
    "Portugal":                                 127,
    "Australia":                                124,
    "Pakistan":                                 121,
    "Chile":                                    121,
    "Czech Republic":                           120,
    "Colombia":                                 117,
    "South Africa":                             114,
    "Belgium":                                  113,
    "Israel":                                   107,
    "Malaysia":                                 106,
    "Austria":                                  104,
    "Sweden":                                   102,
    "Ireland":                                  98,
    "Thailand":                                 97,
    "Viet Nam":                                 94,
    "Philippines":                              94,
    "Norway":                                   91,
    "Finland":                                  90,
    "Denmark":                                  90,
    "Slovakia":                                 82,
    "Bangladesh":                               80,
    "New Zealand":                              68,
    "Lithuania":                                62,
    "Sri Lanka":                                60,
    "Slovenia":                                 58,
    "Costa Rica":                               52,
    "Mongolia":                                 50,
    "Singapore":                                50,
    "Latvia":                                   47,
    "Estonia":                                  46,
    "Myanmar":                                  46,
    "Luxembourg":                               46,
    "Democratic People's Republic of Korea":    43,
    "Cambodia":                                 43,
    "Brunei Darussalam":                        42,
    "Nepal":                                    40,
    "Lao People's Democratic Republic":         40,
    "Timor-Leste":                              31,
    "Iceland":                                  26,
    "Papua New Guinea":                         21,
    "Bhutan":                                   10,
}

# ── Estimated posts for ~128 UN members not covered by the GDI ───────────────
# Anchored to GDI comparators and grouped by regional/size tier.
_GDI_ESTIMATED: dict[str, int] = {
    "Iran":                                     90,
    "Egypt":                                    88,
    "Nigeria":                                  85,
    "Venezuela":                                75,
    "Cuba":                                     70,
    "Algeria":                                  65,
    "Ethiopia":                                 60,
    "Morocco":                                  58,
    "Ukraine":                                  56,
    "Belarus":                                  55,
    "Kazakhstan":                               54,
    "Qatar":                                    52,
    "United Arab Emirates":                     50,
    "Jordan":                                   48,
    "Peru":                                     48,
    "Ecuador":                                  46,
    "Serbia":                                   45,
    "Romania":                                  44,
    "Libya":                                    40,
    "Sudan":                                    38,
    "Syria":                                    35,
    "Kenya":                                    35,
    "Ghana":                                    34,
    "United Republic of Tanzania":              33,
    "Tunisia":                                  32,
    "Iraq":                                     32,
    "Azerbaijan":                               32,
    "Croatia":                                  31,
    "Georgia":                                  30,
    "Armenia":                                  30,
    "Senegal":                                  30,
    "Bolivia":                                  30,
    "Zimbabwe":                                 29,
    "Uruguay":                                  29,
    "Paraguay":                                 28,
    "Guatemala":                                28,
    "Panama":                                   27,
    "Dominican Republic":                       27,
    "Albania":                                  27,
    "North Macedonia":                          26,
    "Bosnia and Herzegovina":                   26,
    "Montenegro":                               26,
    "Uzbekistan":                               26,
    "Kyrgyzstan":                               24,
    "Tajikistan":                               24,
    "Turkmenistan":                             23,
    "Kuwait":                                   23,
    "Bahrain":                                  22,
    "Oman":                                     22,
    "Cyprus":                                   22,
    "Republic of Moldova":                      22,
    "Malta":                                    20,
    "Uganda":                                   20,
    "Cameroon":                                 20,
    "Democratic Republic of the Congo":         20,
    "Zambia":                                   19,
    "Angola":                                   19,
    "Mozambique":                               19,
    "Madagascar":                               18,
    "Congo":                                    18,
    "Côte d'Ivoire":                           18,
    "Rwanda":                                   18,
    "Malawi":                                   17,
    "Namibia":                                  17,
    "Botswana":                                 17,
    "Lebanon":                                  16,
    "Jamaica":                                  16,
    "Trinidad and Tobago":                      16,
    "Honduras":                                 16,
    "El Salvador":                              16,
    "Nicaragua":                                15,
    "Guyana":                                   15,
    "Suriname":                                 15,
    "Burkina Faso":                             15,
    "Mali":                                     15,
    "Niger":                                    15,
    "Chad":                                     15,
    "South Sudan":                              14,
    "Somalia":                                  14,
    "Haiti":                                    14,
    "Liberia":                                  14,
    "Sierra Leone":                             14,
    "Guinea":                                   13,
    "Benin":                                    13,
    "Togo":                                     13,
    "Eritrea":                                  12,
    "Gabon":                                    12,
    "Equatorial Guinea":                        12,
    "Central African Republic":                 12,
    "Burundi":                                  12,
    "Djibouti":                                 12,
    "Yemen":                                    12,
    "Afghanistan":                              12,
    "Maldives":                                 12,
    "Lesotho":                                  11,
    "Eswatini":                                 11,
    "Cabo Verde":                               11,
    "Mauritius":                                11,
    "Seychelles":                               10,
    "Mauritania":                               10,
    "Gambia":                                   10,
    "Guinea-Bissau":                            10,
    "Sao Tome and Principe":                    9,
    "Comoros":                                  9,
    "Samoa":                                    9,
    "Solomon Islands":                          9,
    "Vanuatu":                                  8,
    "Fiji":                                     8,
    "Tonga":                                    8,
    "Bahamas":                                  7,
    "Barbados":                                 7,
    "Belize":                                   7,
    "Grenada":                                  7,
    "Dominica":                                 7,
    "Saint Lucia":                              7,
    "Saint Kitts and Nevis":                    6,
    "Saint Vincent and the Grenadines":         6,
    "Antigua and Barbuda":                      6,
    "Andorra":                                  6,
    "Liechtenstein":                            6,
    "San Marino":                               6,
    "Monaco":                                   5,
    "Palau":                                    5,
    "Federated States of Micronesia":           5,
    "Marshall Islands":                         5,
    "Kiribati":                                 4,
    "Tuvalu":                                   4,
    "Nauru":                                    4,
}

_MAX_POSTS = 274  # China — normalisation anchor


def _diplomatic_strength(country_name: str) -> float:
    """
    Return a normalised diplomatic strength score in [0, 1].
    Uses GDI 2024 data where available; falls back to regional estimate.
    Minimum floor of 4 posts (≈ 0.015) for any UN member.
    """
    posts = _GDI_POSTS.get(country_name) or _GDI_ESTIMATED.get(country_name, 8)
    return round(min(1.0, posts / _MAX_POSTS), 4)


# ── Safe casting helpers ──────────────────────────────────────────────────────

def _safe_float(value, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value, default: int) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


# ── Network builder ───────────────────────────────────────────────────────────

def _build_un_network(
    agents: list,
) -> nx.DiGraph:
    """
    Build a complete directed weighted forum network.

    In the UN, every state can observe every other state's public position.
    The model therefore gives every ordered pair a tie and lets edge direction
    encode asymmetric influence:

      edge A -> B      = pressure from A on B
      influence core   = 0.10 + 0.90 * diplomatic strength of A
      regime affinity  = 1.00 for same-regime pairs, 0.65 otherwise
      P5 visibility    = 1.25 when A is a P5 member

    This makes a P5 member's pressure on a small state much larger than the
    small state's pressure on the P5 member, while still keeping both states
    formally visible to one another in the forum.
    """
    G = nx.DiGraph()
    G.add_nodes_from(range(len(agents)))

    for source_idx, source in enumerate(agents):
        for target_idx, target in enumerate(agents):
            if source_idx == target_idx:
                continue

            source_influence = 0.10 + (0.90 * source.diplomatic_strength)
            regime_affinity = 1.00 if source.regime == target.regime else 0.65
            p5_visibility = 1.25 if source.country_name in P5_NAMES else 1.00
            weight = min(1.0, source_influence * regime_affinity * p5_visibility)
            G.add_edge(source_idx, target_idx, weight=round(max(0.01, weight), 4))

    return G


# ── Model ─────────────────────────────────────────────────────────────────────

class UNModel(Model):
    """
    Parameters
    ----------
    alpha       : float  Beta distribution alpha (shared, controls global left-skew).
                  Higher alpha = distribution mass shifts left = lower thresholds
                  globally = easier cascades.  Default 2.0.
    beta_scale  : float  Multiplier on each agent's baseline beta before first draw.
                  Higher beta_scale = higher initial thresholds = harder cascades.
                  Default 1.0.
    shame_min   : minimum initial shamers (0–193)
    shame_max   : maximum initial shamers (0–193)
    spread      : signed integer
                    > 0 → recruit up to this many neutrals per step
                    < 0 → revert up to |spread| shamers per step
                    = 0 → no spread
    seed        : UI-facing random seed. Passed to Mesa as rng because the
                  seed keyword is deprecated in Mesa.
    """

    N_AGENTS            = 193
    NEUTRAL_RESET_EVERY = 5

    def __init__(
        self,
        alpha       = 2.0,
        beta_scale  = 1.0,
        shame_min   = 20,
        shame_max   = 77,
        spread      = 10,
        seed        = None,
    ):
        super().__init__(rng=_safe_int(seed, 42))

        self.alpha      = max(0.1, _safe_float(alpha, 2.0))
        self.beta_scale = max(0.1, _safe_float(beta_scale, 1.0))

        raw_min = _safe_int(shame_min, 20)
        raw_max = _safe_int(shame_max, 77)
        self.shame_min = max(0, min(self.N_AGENTS, raw_min))
        self.shame_max = max(0, min(self.N_AGENTS, raw_max))
        if self.shame_min > self.shame_max:
            self.shame_min, self.shame_max = self.shame_max, self.shame_min

        raw_spread = _safe_int(spread, 10)
        self.spread = max(-self.N_AGENTS, min(self.N_AGENTS, raw_spread))

        self.step_count       = 0
        self._cascade_history: list[float] = []   # fraction shaming at each window end

        # Build agents (diplomatic_strength + threshold set before network)
        self._agent_list: list[CountryAgent] = []
        self._build_agents()

        # Build the complete directed forum network and attach Mesa NetworkGrid.
        self.G    = _build_un_network(self._agent_list)
        self.grid = NetworkGrid(self.G)

        for i, agent in enumerate(self._agent_list):
            self.grid.place_agent(agent, i)

        self.datacollector = DataCollector(
            model_reporters={
                "Shaming":        lambda m: m._count(SHAME),
                "Neutral":        lambda m: m._count(NEUTRAL),
                "DemShame":       lambda m: m._regime_count(DEMOCRACY,     SHAME),
                "NonDemShame":    lambda m: m._regime_count(NON_DEMOCRACY, SHAME),
                "MeanThreshold":  lambda m: m._mean_threshold(),
                "StdThreshold":   lambda m: m._std_threshold(),
                "NormEroding":    lambda m: m._norm_eroding(),
            },
            agent_reporters={
                "State":              "state",
                "Regime":             "regime",
                "DiplomaticStrength": "diplomatic_strength",
                "Threshold":          "threshold",
                "BetaParam":          "beta_param",
            },
        )

        self._randomise_states()
        self.datacollector.collect(self)

    # ── Construction ──────────────────────────────────────────────────────────

    def _build_agents(self) -> None:
        entries = list(_UN_193)
        self.random.shuffle(entries)
        for full_name in entries:
            a = CountryAgent(self, full_name)
            a.diplomatic_strength = _diplomatic_strength(full_name)
            a.initialise_threshold(self.alpha, self.beta_scale, self.random)
            self._agent_list.append(a)

    # ── State reset ───────────────────────────────────────────────────────────

    def _randomise_states(self) -> None:
        n_shame = self.random.randint(
            max(0, self.shame_min),
            max(0, self.shame_max),
        )
        n_shame = min(n_shame, self.N_AGENTS)
        self.agents.do("reset", NEUTRAL)
        if n_shame > 0:
            for a in self.random.sample(self._agent_list, n_shame):
                a.reset(SHAME)

    # ── Mesa step ─────────────────────────────────────────────────────────────

    def step(self) -> None:
        self.step_count += 1

        if self.step_count % self.NEUTRAL_RESET_EVERY == 0:
            # Record cascade outcome before reset, then update thresholds
            cascade_frac = self._count(SHAME) / self.N_AGENTS
            self._cascade_history.append(cascade_frac)
            self.agents.do("update_threshold", cascade_frac, self.random)
            self._randomise_states()

        # Phase 1: every agent copies its visible state to a buffer. This keeps
        # spread/reversion synchronous; no agent reacts to another's new choice
        # until the commit phase below.
        self.agents.do("step")

        if self.spread > 0:
            self._apply_spread(self.spread)
        elif self.spread < 0:
            self._apply_revert(abs(self.spread))

        # Phase 2: commit all buffered choices together.
        self.agents.do("advance")

        self.datacollector.collect(self)

    def _apply_spread(self, n: int) -> None:
        """
        Recruit up to `n` NEUTRAL agents to SHAME.

        Agent-level threshold and pressure rules live in CountryAgent.
        This method only groups candidates and samples from their weights.
        """
        dem_neutrals = [
            a for a in self._agent_list
            if a.regime == DEMOCRACY and a._next_state == NEUTRAL
        ]
        nondem_neutrals = [
            a for a in self._agent_list
            if a.regime == NON_DEMOCRACY and a._next_state == NEUTRAL
        ]

        for pool in (dem_neutrals, nondem_neutrals):
            if not pool:
                continue

            eligible = []
            weights  = []
            for a in pool:
                weight = a.recruitment_weight(self.G, self.grid)
                if weight > 0:
                    eligible.append(a)
                    weights.append(weight)

            if not eligible:
                continue

            k = self.random.randint(0, min(n, len(eligible)))
            if not k:
                continue

            chosen = self._weighted_sample_without_replacement(
                eligible, weights, min(k, len(eligible))
            )
            for a in chosen:
                a.choose_shaming()

    def _apply_revert(self, n: int) -> None:
        """
        Revert up to `n` SHAMING agents to NEUTRAL.
        Weaker states (lower diplomatic_strength) are easier to flip back.
        P5 members are additionally protected (weight halved).
        """
        shamers = [a for a in self._agent_list if a._next_state == SHAME]
        if not shamers:
            return
        weights = [a.revert_weight() for a in shamers]
        k = self.random.randint(0, min(n, len(shamers)))
        if k:
            chosen = self._weighted_sample_without_replacement(
                shamers, weights, min(k, len(shamers))
            )
            for a in chosen:
                a.choose_neutral()

    def _weighted_sample_without_replacement(
        self,
        agents: list[CountryAgent],
        weights: list[float],
        k: int,
    ) -> list[CountryAgent]:
        """
        Draw up to k unique agents using weights.

        Python's random.choices samples with replacement. The previous code
        handled duplicates with a seen set after the draw, which meant fewer
        than k agents could change state. This helper removes each selected
        agent before the next draw, so k means k distinct choices whenever
        enough candidates exist.
        """
        remaining_agents = list(agents)
        remaining_weights = list(weights)
        chosen: list[CountryAgent] = []

        while remaining_agents and len(chosen) < k:
            selected = self.random.choices(
                remaining_agents,
                weights=remaining_weights,
                k=1,
            )[0]
            idx = remaining_agents.index(selected)
            chosen.append(selected)
            remaining_agents.pop(idx)
            remaining_weights.pop(idx)

        return chosen

    # ── Statistics ────────────────────────────────────────────────────────────

    def _count(self, state: str) -> int:
        return sum(1 for a in self._agent_list if a.state == state)

    def _mean_threshold(self) -> float:
        vals = [a.threshold for a in self._agent_list]
        return round(sum(vals) / len(vals), 4) if vals else 0.0

    def _std_threshold(self) -> float:
        import math
        vals = [a.threshold for a in self._agent_list]
        if not vals:
            return 0.0
        mu = sum(vals) / len(vals)
        return round(math.sqrt(sum((v - mu) ** 2 for v in vals) / len(vals)), 4)

    def _norm_eroding(self) -> float:
        """
        Fraction of agents whose beta_param has risen above their initial
        value — proxy for how many agents have internalised non-shaming
        as acceptable behaviour (Barnett & Finnemore 2004).
        Computed relative to regime baseline betas.
        """
        eroding = 0
        for a in self._agent_list:
            if a.beta_param > a.baseline_beta(self.beta_scale):
                eroding += 1
        return round(eroding / self.N_AGENTS, 4)

    def _regime_count(self, regime: str, state: str) -> int:
        return sum(1 for a in self._agent_list
                   if a.regime == regime and a.state == state)

    def _regime_pct(self, regime: str) -> float:
        group = [a for a in self._agent_list if a.regime == regime]
        if not group:
            return 0.0
        return round(100 * sum(1 for a in group if a.state == SHAME) / len(group), 1)

    def get_stats(self) -> dict:
        shaming = self._count(SHAME)
        return {
            "step":           self.step_count,
            "shaming":        shaming,
            "neutral":        self.N_AGENTS - shaming,
            "pct_shame":      round(100 * shaming / self.N_AGENTS, 1),
            "dem_pct":        self._regime_pct(DEMOCRACY),
            "ndem_pct":       self._regime_pct(NON_DEMOCRACY),
            "mean_threshold": self._mean_threshold(),
            "std_threshold":  self._std_threshold(),
            "norm_eroding":   round(self._norm_eroding() * 100, 1),
        }

    def reset(self) -> None:
        self.step_count = 0
        self.agents.do("reset", NEUTRAL)
