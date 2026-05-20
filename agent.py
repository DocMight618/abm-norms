"""
agent.py — CountryAgent for the UN Naming & Shaming model (Mesa 3.x).

Binary state: SHAME or NEUTRAL.

Each step the model drives two mechanisms:
  1. Neighbour-weighted spread — shaming agents recruit neutral agents, with
     probability proportional to the sum of edge weights (GDI diplomatic
     strength) from shaming neighbours. P5 members exert a 2× bonus.
  2. Spontaneous reversion — SHAMING agents revert to NEUTRAL; probability
     is inversely proportional to diplomatic_strength; P5 halved further.

`diplomatic_strength` (float in [0, 1]) is set by UNModel at construction
using Lowy Institute GDI 2024 data (posts / 274).  It is read-only thereafter.
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


def classify_regime(full_name: str) -> str:
    return DEMOCRACY if full_name in _DEMOCRACY_SET else NON_DEMOCRACY


class CountryAgent(Agent):
    """
    A UN member state node in a Mesa NetworkGrid.

    State transitions are orchestrated by UNModel.step().

    Attributes set at construction by UNModel
    -----------------------------------------
    diplomatic_strength : float in [0, 1]
        Normalised count of overseas diplomatic posts from the
        Lowy Institute Global Diplomacy Index 2024 (max = China, 274 posts).
        Used as edge weight and to modulate spread / reversion.

    Parameters
    ----------
    model         : UNModel instance
    country_name  : Full official UN country name
    short_name    : Short display label
    """

    def __init__(self, model, country_name: str, short_name: str):
        super().__init__(model)
        self.country_name        = country_name
        self.short_name          = short_name
        self.regime              = classify_regime(country_name)
        self.state               = NEUTRAL
        self._next_state         = NEUTRAL
        self.diplomatic_strength = 0.0  # overwritten by UNModel._build_agents()

    def step(self) -> None:
        """Phase 1: copy current state into buffer (model will overwrite)."""
        self._next_state = self.state

    def advance(self) -> None:
        """Phase 2: commit buffered state."""
        self.state = self._next_state

    def reset(self, state: str = NEUTRAL) -> None:
        self.state       = state
        self._next_state = state

    def __repr__(self) -> str:
        return (
            f"CountryAgent({self.country_name!r}, "
            f"regime={self.regime}, node={self.pos}, "
            f"state={self.state!r}, strength={self.diplomatic_strength:.3f})"
        )
