"""
agents.py  —  AudienceMember agent for the Standing Ovation Model.

Source: Miller, J. H., & Page, S. E. (2004). The standing ovation problem.
        Complexity, 9(5), 8-16.

FAITHFUL IMPLEMENTATION NOTES
-------------------------------
The paper's Section 6 computational model specifies:

  PRIVATE DECISION (Step 1, t=0):
    - Quality signal q_ij drawn from [0, 1] (Uniform).
    - Each agent has an IDENTICAL threshold T = 0.5 (not a distribution).
    - Agent stands immediately if q_ij >= T.
    - NOTE: Earlier code used heterogeneous thresholds drawn from
      Uniform(T_min, T_max). The paper's computational model explicitly
      uses identical thresholds of 0.5 for all agents.

  SOCIAL RULE (Step 2, t >= 1):
    - Applied to ALL agents each tick — both sitters AND standers.
    - "An agent stands if and only if a majority of her neighbors are
      standing." [p. 14]
    - TIE: "she sits or stands with equal probability." [p. 14]
    - NOTE: Standing is NOT absorbing in Section 6. The paper explicitly
      states "symmetry induced by the use of identical rules for sitting
      and standing greatly simplifies the analysis." [p. 14]
      Earlier code made STAND absorbing — this contradicts the paper's
      stated symmetry assumption.

SYNCHRONOUS UPDATE
  Mesa's two-phase step()/advance() protocol implements the paper's
  synchronous updating: all agents read the current state snapshot before
  any agent commits a new state.

  For asynchronous modes the model calls apply_social_rule() directly
  and commits immediately, bypassing the step()/advance() protocol.
"""

from mesa import Agent

SIT   = "sit"
STAND = "stand"


class AudienceMember(Agent):
    """
    A single audience member in Miller & Page's (2004) SOP model.

    Attributes
    ----------
    initial_quality : float
        Private quality estimate drawn from Uniform(0, 1) at Step 1.
    state : str
        Current visible state — SIT or STAND.
    _next_state : str
        Buffered next state used by the synchronous update protocol.
    """

    def __init__(self, model: "StandingOvationModel") -> None:
        super().__init__(model)
        self.initial_quality: float = 0.0
        self.state:           str   = SIT
        self._next_state:     str   = SIT

    # ── Step 1: private decision ──────────────────────────────────────────────

    def make_private_decision(self, quality_threshold: float = 0.5) -> None:
        """
        Step 1 of the paper: draw a private quality signal and stand
        immediately if it meets or exceeds the quality threshold.

        The paper draws quality from [0,1] with a threshold of 0.5
        (identical across all agents — see docstring above).

        Parameters
        ----------
        quality_threshold : float
            T — the standing threshold. Defaults to 0.5 per the paper.
        """
        # Quality signal: Uniform(0, 1) per Section 6 of the paper
        self.initial_quality = self.model.random.random()
        self.state = STAND if self.initial_quality >= quality_threshold else SIT
        self._next_state = self.state

    # ── Social rule (used by all three update protocols) ─────────────────────

    def compute_social_decision(self, neighbours: list) -> str:
        """
        Majority rule: stand if a majority of visible neighbours stand.

        Implements the paper's rule exactly [p. 14]:
          - frac_standing > 0.5  → STAND
          - frac_standing < 0.5  → SIT
          - frac_standing = 0.5  → STAND or SIT with equal probability

        Applied symmetrically to ALL agents (both sitters and standers).

        Parameters
        ----------
        neighbours : list of AudienceMember
            Agents visible to self according to the chosen neighbourhood.
        """
        if not neighbours:
            return self.state   # isolated agent: no social information

        n_standing = sum(1 for n in neighbours if n.state == STAND)
        frac = n_standing / len(neighbours)

        if frac > 0.5:
            return STAND
        elif frac < 0.5:
            return SIT
        else:
            # Tie: sit or stand with equal probability [paper p.14]
            return STAND if self.model.random.random() < 0.5 else SIT

    # ── Phase 1 of synchronous update (reads neighbours → writes buffer) ─────

    def step(self) -> None:
        """
        Synchronous update Phase 1: compute next state from current
        neighbour snapshot into _next_state. Does NOT commit yet.
        Only called by the model when update_rule == 'synchronous'.
        """
        neighbours = self.model.get_visible_neighbors(self)
        self._next_state = self.compute_social_decision(neighbours)

    # ── Phase 2 of synchronous update (commits buffer) ───────────────────────

    def advance(self) -> None:
        """Synchronous update Phase 2: commit buffered state."""
        self.state = self._next_state

    # ── Immediate update (used by async protocols) ────────────────────────────

    def update_immediately(self) -> bool:
        """
        Read current neighbour states and commit new state in one step.
        Used by async_random and async_incentive update protocols.

        Returns True if the agent's state changed.
        """
        neighbours = self.model.get_visible_neighbors(self)
        old        = self.state
        self.state = self.compute_social_decision(neighbours)
        self._next_state = self.state
        return self.state != old

    # ── Utility ───────────────────────────────────────────────────────────────

    def dissimilarity(self) -> float:
        """
        Fraction of visible neighbours in the OPPOSITE state.
        Used to rank agents for asynchronous-incentive-based updating:
        agents most unlike their neighbourhood update first.
        """
        neighbours = self.model.get_visible_neighbors(self)
        if not neighbours:
            return 0.0
        opposite = STAND if self.state == SIT else SIT
        return sum(1 for n in neighbours if n.state == opposite) / len(neighbours)

    def reset(self) -> None:
        """Return to sitting state (used between runs)."""
        self.state          = SIT
        self._next_state    = SIT
        self.initial_quality = 0.0

    def __repr__(self) -> str:
        return (f"AudienceMember(id={self.unique_id}, "
                f"quality={self.initial_quality:.2f}, "
                f"state={self.state!r}, pos={self.pos})")
