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

Edge weights
────────────
An edge between countries A and B gets weight:
    w(A, B) = (strength[A] + strength[B]) / 2
clipped to [0, 1].  Stronger nations exert more influence on each other.

Network structure
─────────────────
  • Intra-regime edges drawn with probability scaled by avg diplomatic strength.
  • Cross-regime edges drawn with lower base probability, also strength-scaled.
  • P5 members are connected to ALL agents in their regime cluster and to
    each other (regardless of probability draw).
  • P5 members receive p5_extra additional random cross-cluster edges.

Spreading mechanic
──────────────────
  spread > 0 : recruit NEUTRAL agents weighted by neighbour shaming pressure
               AND by the edge weight (stronger diplomatic tie = more pressure).
               P5 shamers grant a 2× bonus to their neighbours.
  spread < 0 : revert SHAMING agents; weaker states easier to flip; P5 halved.
  spread = 0 : no global spread / reversion.

Every NEUTRAL_RESET_EVERY (5) steps states are re-randomised; network is fixed.
"""

import networkx as nx

from mesa import Model
from mesa.space import NetworkGrid
from mesa.datacollection import DataCollector

from agent import CountryAgent, NEUTRAL, SHAME, DEMOCRACY, NON_DEMOCRACY


# ── 193 UN General Assembly members ──────────────────────────────────────────
_UN_193: list[tuple[str, str]] = [
    ("Afghanistan", "Afghan."), ("Albania", "Albania"), ("Algeria", "Algeria"),
    ("Andorra", "Andorra"), ("Angola", "Angola"),
    ("Antigua and Barbuda", "Antigua"), ("Argentina", "Argent."),
    ("Armenia", "Armenia"), ("Australia", "Austral"), ("Austria", "Austria"),
    ("Azerbaijan", "Azerba."), ("Bahamas", "Bahamas"), ("Bahrain", "Bahrain"),
    ("Bangladesh", "Banglad"), ("Barbados", "Barbado"), ("Belarus", "Belarus"),
    ("Belgium", "Belgium"), ("Belize", "Belize"), ("Benin", "Benin"),
    ("Bhutan", "Bhutan"), ("Bolivia", "Bolivia"),
    ("Bosnia and Herzegovina", "Bosnia"), ("Botswana", "Botswan"),
    ("Brazil", "Brazil"), ("Brunei Darussalam", "Brunei"),
    ("Bulgaria", "Bulgari"), ("Burkina Faso", "Burkina"),
    ("Burundi", "Burundi"), ("Cabo Verde", "C.Verde"),
    ("Cambodia", "Cambod."), ("Cameroon", "Cameroo"), ("Canada", "Canada"),
    ("Central African Republic", "CAR"), ("Chad", "Chad"), ("Chile", "Chile"),
    ("China", "China"), ("Colombia", "Colombi"), ("Comoros", "Comoros"),
    ("Congo", "Congo"), ("Democratic Republic of the Congo", "DR Congo"),
    ("Costa Rica", "C.Rica"), ("Côte d'Ivoire", "C.Ivoir"),
    ("Croatia", "Croatia"), ("Cuba", "Cuba"), ("Cyprus", "Cyprus"),
    ("Czech Republic", "Czech R"), ("Denmark", "Denmark"),
    ("Djibouti", "Djibouti"), ("Dominica", "Dominic"),
    ("Dominican Republic", "Dom.Rep"), ("Ecuador", "Ecuador"),
    ("Egypt", "Egypt"), ("El Salvador", "El Salv"),
    ("Equatorial Guinea", "Eq.Guin"), ("Eritrea", "Eritrea"),
    ("Estonia", "Estonia"), ("Eswatini", "Eswatin"),
    ("Ethiopia", "Ethiopi"), ("Fiji", "Fiji"), ("Finland", "Finland"),
    ("France", "France"), ("Gabon", "Gabon"), ("Gambia", "Gambia"),
    ("Georgia", "Georgia"), ("Germany", "Germany"), ("Ghana", "Ghana"),
    ("Greece", "Greece"), ("Grenada", "Grenada"), ("Guatemala", "Guatema"),
    ("Guinea", "Guinea"), ("Guinea-Bissau", "Guin-B."), ("Guyana", "Guyana"),
    ("Haiti", "Haiti"), ("Honduras", "Hondura"), ("Hungary", "Hungary"),
    ("Iceland", "Iceland"), ("India", "India"), ("Indonesia", "Indones"),
    ("Iran", "Iran"), ("Iraq", "Iraq"), ("Ireland", "Ireland"),
    ("Israel", "Israel"), ("Italy", "Italy"), ("Jamaica", "Jamaica"),
    ("Japan", "Japan"), ("Jordan", "Jordan"), ("Kazakhstan", "Kazakhs"),
    ("Kenya", "Kenya"), ("Kiribati", "Kiribat"),
    ("Democratic People's Republic of Korea", "N.Korea"),
    ("Republic of Korea", "S.Korea"), ("Kuwait", "Kuwait"),
    ("Kyrgyzstan", "Kyrgyz."),
    ("Lao People's Democratic Republic", "Laos"), ("Latvia", "Latvia"),
    ("Lebanon", "Lebanon"), ("Lesotho", "Lesotho"), ("Liberia", "Liberia"),
    ("Libya", "Libya"), ("Liechtenstein", "Liechtn"),
    ("Lithuania", "Lithuan"), ("Luxembourg", "Luxembg"),
    ("Madagascar", "Madagas"), ("Malawi", "Malawi"), ("Malaysia", "Malaysi"),
    ("Maldives", "Maldive"), ("Mali", "Mali"), ("Malta", "Malta"),
    ("Marshall Islands", "Marshal"), ("Mauritania", "Maurita"),
    ("Mauritius", "Mauriti"), ("Mexico", "Mexico"),
    ("Federated States of Micronesia", "Micrones"),
    ("Republic of Moldova", "Moldova"), ("Monaco", "Monaco"),
    ("Mongolia", "Mongoli"), ("Montenegro", "Montene"), ("Morocco", "Morocco"),
    ("Mozambique", "Mozambi"), ("Myanmar", "Myanmar"), ("Namibia", "Namibia"),
    ("Nauru", "Nauru"), ("Nepal", "Nepal"), ("Netherlands", "Netherl"),
    ("New Zealand", "N.Zeala"), ("Nicaragua", "Nicarag"), ("Niger", "Niger"),
    ("Nigeria", "Nigeria"), ("North Macedonia", "N.Maced"), ("Norway", "Norway"),
    ("Oman", "Oman"), ("Pakistan", "Pakista"), ("Palau", "Palau"),
    ("Panama", "Panama"), ("Papua New Guinea", "Papua"), ("Paraguay", "Paragua"),
    ("Peru", "Peru"), ("Philippines", "Philipp"), ("Poland", "Poland"),
    ("Portugal", "Portuga"), ("Qatar", "Qatar"), ("Romania", "Romania"),
    ("Russia", "Russia"), ("Rwanda", "Rwanda"),
    ("Saint Kitts and Nevis", "St.Kitts"), ("Saint Lucia", "St.Lucia"),
    ("Saint Vincent and the Grenadines", "St.Vinc"), ("Samoa", "Samoa"),
    ("San Marino", "S.Marin"), ("Sao Tome and Principe", "SaoTome"),
    ("Saudi Arabia", "S.Arabi"), ("Senegal", "Senegal"), ("Serbia", "Serbia"),
    ("Seychelles", "Seychel"), ("Sierra Leone", "S.Leone"),
    ("Singapore", "Singapor"), ("Slovakia", "Slovak."),
    ("Slovenia", "Sloveni"), ("Solomon Islands", "Solomon"),
    ("Somalia", "Somalia"), ("South Africa", "S.Afric"),
    ("South Sudan", "S.Sudan"), ("Spain", "Spain"), ("Sri Lanka", "SriLank"),
    ("Sudan", "Sudan"), ("Suriname", "Surinam"), ("Sweden", "Sweden"),
    ("Switzerland", "Swiss"), ("Syria", "Syria"), ("Tajikistan", "Tajikis"),
    ("United Republic of Tanzania", "Tanzani"), ("Thailand", "Thailan"),
    ("Timor-Leste", "Timor"), ("Togo", "Togo"), ("Tonga", "Tonga"),
    ("Trinidad and Tobago", "TrinTob"), ("Tunisia", "Tunisia"),
    ("Turkey", "Turkey"), ("Turkmenistan", "Turkmen"), ("Tuvalu", "Tuvalu"),
    ("Uganda", "Uganda"), ("Ukraine", "Ukraine"),
    ("United Arab Emirates", "UAE"), ("United Kingdom", "UK"),
    ("United States of America", "USA"), ("Uruguay", "Uruguay"),
    ("Uzbekistan", "Uzbekis"), ("Vanuatu", "Vanuatu"),
    ("Venezuela", "Venezue"), ("Viet Nam", "VietNam"),
    ("Yemen", "Yemen"), ("Zambia", "Zambia"), ("Zimbabwe", "Zimbabw"),
]
assert len(_UN_193) == 193 and len(set(n for n, _ in _UN_193)) == 193

# UN Security Council P5 permanent members
P5_NAMES: frozenset[str] = frozenset({
    "China", "France", "Russia", "United Kingdom", "United States of America",
})

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
    rng,
    p_intra: float = 0.25,
    p_inter: float = 0.06,
    p5_extra: int  = 20,
) -> nx.Graph:
    """
    Build a weighted undirected network of 193 UN member state agents.

    Edge weight w(A,B) = (strength[A] + strength[B]) / 2  ∈ (0, 1].

    Connection rules:
    1. Same-regime pair: edge drawn with prob  p_intra * 4 * avg_strength(A,B)
    2. Cross-regime pair: edge drawn with prob p_inter * 4 * avg_strength(A,B)
       Stronger nations are more likely to be connected (incl. across regimes).
    3. Every P5 member → all agents in its own regime cluster (guaranteed).
    4. All P5 members fully connected to each other.
    5. Each P5 member gets p5_extra additional random cross-cluster edges.
    """
    G = nx.Graph()
    G.add_nodes_from(range(len(agents)))

    strengths = [a.diplomatic_strength for a in agents]

    dem_idx  = [i for i, a in enumerate(agents) if a.regime == DEMOCRACY]
    ndem_idx = [i for i, a in enumerate(agents) if a.regime != DEMOCRACY]
    p5_idx   = [i for i, a in enumerate(agents) if a.country_name in P5_NAMES]

    def _add(u, v):
        w = (strengths[u] + strengths[v]) / 2
        if G.has_edge(u, v):
            G[u][v]["weight"] = max(G[u][v]["weight"], w)
        else:
            G.add_edge(u, v, weight=w)

    # 1. Intra-regime probabilistic edges (strength-scaled)
    for cluster in (dem_idx, ndem_idx):
        for ii in range(len(cluster)):
            for jj in range(ii + 1, len(cluster)):
                u, v = cluster[ii], cluster[jj]
                avg_s = (strengths[u] + strengths[v]) / 2
                if rng.random() < p_intra * avg_s * 4:
                    _add(u, v)

    # 2. Cross-regime probabilistic edges (strength-scaled, lower base)
    for di in dem_idx:
        for ni in ndem_idx:
            avg_s = (strengths[di] + strengths[ni]) / 2
            if rng.random() < p_inter * avg_s * 4:
                _add(di, ni)

    # 3. P5 → all same-regime agents (guaranteed hub connections)
    for pi in p5_idx:
        cluster = dem_idx if agents[pi].regime == DEMOCRACY else ndem_idx
        for ci in cluster:
            if ci != pi:
                _add(pi, ci)

    # 4. P5 fully inter-connected (cross-regime P5 links)
    for ii in range(len(p5_idx)):
        for jj in range(ii + 1, len(p5_idx)):
            _add(p5_idx[ii], p5_idx[jj])

    # 5. P5 extra cross-cluster edges
    for pi in p5_idx:
        cross = ndem_idx if agents[pi].regime == DEMOCRACY else dem_idx
        sample_k = min(p5_extra, len(cross))
        for ci in rng.sample(cross, sample_k):
            _add(pi, ci)

    return G


# ── Model ─────────────────────────────────────────────────────────────────────

class UNModel(Model):
    """
    Parameters
    ----------
    shame_threshold : display threshold shown in tooltips (0.0–1.0)
    shame_min       : minimum initial shamers (0–193)
    shame_max       : maximum initial shamers (0–193)
    spread          : signed integer
                        > 0 → recruit up to this many neutrals per step
                        < 0 → revert up to |spread| shamers per step
                        = 0 → no spread
    seed            : RNG seed
    """

    N_AGENTS            = 193
    NEUTRAL_RESET_EVERY = 5

    def __init__(
        self,
        shame_threshold = 0.50,
        shame_min       = 20,
        shame_max       = 77,
        spread          = 10,
        seed            = None,
    ):
        super().__init__(seed=_safe_int(seed, 42))

        self.shame_threshold = max(0.0, min(1.0, _safe_float(shame_threshold, 0.50)))

        raw_min = _safe_int(shame_min, 20)
        raw_max = _safe_int(shame_max, 77)
        self.shame_min = max(0, min(self.N_AGENTS, raw_min))
        self.shame_max = max(0, min(self.N_AGENTS, raw_max))
        if self.shame_min > self.shame_max:
            self.shame_min, self.shame_max = self.shame_max, self.shame_min

        raw_spread = _safe_int(spread, 10)
        self.spread = max(-self.N_AGENTS, min(self.N_AGENTS, raw_spread))

        self.step_count = 0

        # Build agents (diplomatic_strength set before network construction)
        self._agent_list: list[CountryAgent] = []
        self._build_agents()

        # Build weighted network and attach Mesa NetworkGrid
        self.G    = _build_un_network(self._agent_list, self.random)
        self.grid = NetworkGrid(self.G)

        for i, agent in enumerate(self._agent_list):
            self.grid.place_agent(agent, i)

        self._p5_agents: list[CountryAgent] = [
            a for a in self._agent_list if a.country_name in P5_NAMES
        ]

        self.datacollector = DataCollector(
            model_reporters={
                "Shaming":     lambda m: m._count(SHAME),
                "Neutral":     lambda m: m._count(NEUTRAL),
                "DemShame":    lambda m: m._regime_count(DEMOCRACY,     SHAME),
                "NonDemShame": lambda m: m._regime_count(NON_DEMOCRACY, SHAME),
            },
            agent_reporters={
                "State":              "state",
                "Regime":             "regime",
                "DiplomaticStrength": "diplomatic_strength",
            },
        )

        self._randomise_states()
        self.datacollector.collect(self)

    # ── Construction ──────────────────────────────────────────────────────────

    def _build_agents(self) -> None:
        entries = list(_UN_193)
        self.random.shuffle(entries)
        for full_name, short_name in entries:
            a = CountryAgent(self, full_name, short_name)
            a.diplomatic_strength = _diplomatic_strength(full_name)
            self._agent_list.append(a)

    # ── State reset ───────────────────────────────────────────────────────────

    def _randomise_states(self) -> None:
        n_shame = self.random.randint(
            max(0, self.shame_min),
            max(0, self.shame_max),
        )
        n_shame = min(n_shame, self.N_AGENTS)
        for a in self._agent_list:
            a.reset(NEUTRAL)
        if n_shame > 0:
            for a in self.random.sample(self._agent_list, n_shame):
                a.reset(SHAME)

    # ── Mesa step ─────────────────────────────────────────────────────────────

    def step(self) -> None:
        self.step_count += 1

        if self.step_count % self.NEUTRAL_RESET_EVERY == 0:
            self._randomise_states()

        for agent in self.agents:
            agent.step()

        if self.spread > 0:
            self._apply_spread(self.spread)
        elif self.spread < 0:
            self._apply_revert(abs(self.spread))

        for agent in self.agents:
            agent.advance()

        self.datacollector.collect(self)

    def _apply_spread(self, n: int) -> None:
        """
        Recruit up to `n` NEUTRAL agents to SHAME.
        Recruitment probability weighted by:
          • sum of edge-weight-scaled shaming neighbour pressure
          • 2× bonus if any P5 shaming neighbour is present
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
            k = self.random.randint(0, min(n, len(pool)))
            if not k:
                continue
            weights = []
            for a in pool:
                pressure = 0.0
                p5_bonus = 1.0
                for nb_node in self.G.neighbors(a.pos):
                    ew = self.G[a.pos][nb_node].get("weight", 0.1)
                    for nbr in self.grid.get_cell_list_contents([nb_node]):
                        if nbr._next_state == SHAME:
                            pressure += ew
                            if nbr.country_name in P5_NAMES:
                                p5_bonus = 2.0
                weights.append(pressure * p5_bonus + 0.01)

            total = sum(weights)
            probs = [w / total for w in weights]
            chosen = self.random.choices(pool, weights=probs, k=min(k, len(pool)))
            seen = set()
            for a in chosen:
                if id(a) not in seen:
                    a._next_state = SHAME
                    seen.add(id(a))

    def _apply_revert(self, n: int) -> None:
        """
        Revert up to `n` SHAMING agents to NEUTRAL.
        Weaker states (lower diplomatic_strength) are easier to flip back.
        P5 members are additionally protected (weight halved).
        """
        shamers = [a for a in self._agent_list if a._next_state == SHAME]
        if not shamers:
            return
        weights = []
        for a in shamers:
            w = 1.0 - a.diplomatic_strength
            if a.country_name in P5_NAMES:
                w *= 0.5
            weights.append(max(w, 0.01))
        k = self.random.randint(0, min(n, len(shamers)))
        if k:
            total = sum(weights)
            probs = [w / total for w in weights]
            chosen = self.random.choices(shamers, weights=probs, k=min(k, len(shamers)))
            seen = set()
            for a in chosen:
                if id(a) not in seen:
                    a._next_state = NEUTRAL
                    seen.add(id(a))

    # ── Statistics ────────────────────────────────────────────────────────────

    def _count(self, state: str) -> int:
        return sum(1 for a in self._agent_list if a.state == state)

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
            "step":      self.step_count,
            "shaming":   shaming,
            "neutral":   self.N_AGENTS - shaming,
            "pct_shame": round(100 * shaming / self.N_AGENTS, 1),
            "dem_pct":   self._regime_pct(DEMOCRACY),
            "ndem_pct":  self._regime_pct(NON_DEMOCRACY),
        }

    def reset(self) -> None:
        self.step_count = 0
        for a in self._agent_list:
            a.reset(NEUTRAL)
