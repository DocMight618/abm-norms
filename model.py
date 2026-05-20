"""
model.py  —  Standing Ovation Model (Miller & Page 2004).

Source: Miller, J. H., & Page, S. E. (2004). The standing ovation problem.
        Complexity, 9(5), 8-16.

FAITHFUL IMPLEMENTATION
------------------------
Section 6 of the paper specifies a 400-seat (20×20) square auditorium.
This implementation matches the paper's two experimental dimensions:

  1. UPDATING RULE (Tables 1 & 2 in paper)
       synchronous         — all agents update simultaneously each tick
       async_random        — agents update one at a time in random order
       async_incentive     — agents most unlike their neighbourhood update first

  2. NEIGHBOURHOOD STRUCTURE (Tables 1 & 2 in paper)
       five   — 2 side neighbours + 3 directly ahead (5 total max)
       cone   — 2 side neighbours + expanding forward pyramid
       global — all other agents (full audience visibility)

  GRID ORIENTATION
    y = 0 is the FRONT ROW (stage side).
    y = rows-1 is the BACK ROW.
    "Ahead" means lower y (toward the stage).
    Non-toroidal: edges are real theatre walls.
    NOTE: The paper does not specify toroidal or non-toroidal. We use
    non-toroidal because it matches a real theatre and gives front-row
    agents fewer visible neighbours, preserving the paper's discussion
    of front-row signalling power.

  SOCIAL RULE
    Pure majority rule applied symmetrically to ALL agents. Standing is
    NOT absorbing — standers can sit if their visible neighbourhood has
    a sitting majority. This is consistent with the paper's stated
    "symmetry induced by the use of identical rules for sitting and
    standing" [p.14].

  METRICS (paper's Tables 1 & 2)
    NI  — Number of Iterations to reach a steady state
    SM  — Stick in the Muds: % of agents in the global minority at
           steady state (those doing the opposite of the global majority)
    IE  — Informational Efficiency: did the final global majority match
           the initial global majority? (1 = yes, 0 = no)
"""

from mesa import Model
from mesa.space import SingleGrid
from mesa.datacollection import DataCollector

from agents import AudienceMember, SIT, STAND


class StandingOvationModel(Model):
    """
    Miller & Page (2004) Standing Ovation Model.

    Parameters
    ----------
    rows             : number of audience rows (depth of auditorium)
    cols             : number of seats per row (width of auditorium)
    quality_threshold: T — quality level an agent must reach to stand initially.
                       Paper fixes this at 0.5 for all agents.
    social_threshold : S — fraction of visible neighbours standing needed to
                       cascade. Paper uses strict majority = 0.5.
                       NOTE: with the paper's exact majority rule the condition
                       is frac > 0.5 (not >=), with a 50/50 tie-break.
    update_rule      : 'synchronous' | 'async_random' | 'async_incentive'
    neighborhood     : 'five' | 'cone' | 'global'
    seed             : RNG seed for reproducibility
    """

    def __init__(
        self,
        rows:              int   = 20,
        cols:              int   = 20,
        quality_threshold: float = 0.5,
        social_threshold:  float = 0.5,
        update_rule:       str   = "synchronous",
        neighborhood:      str   = "five",
        seed:              int   = None,
    ) -> None:
        super().__init__(seed=seed)

        self.rows              = int(rows)
        self.cols              = int(cols)
        self.quality_threshold = float(quality_threshold)
        self.social_threshold  = float(social_threshold)
        self.update_rule       = str(update_rule)
        self.neighborhood      = str(neighborhood)

        self.step_count    = 0
        self.n_agents      = self.rows * self.cols

        # Metrics — recorded when equilibrium is reached
        self._ni              = None   # Number of Iterations
        self._sm              = None   # Stick in the Muds (%)
        self._ie              = None   # Informational Efficiency (0 or 1)
        self._initial_majority = None  # STAND or SIT — set after Step 1

        # Non-toroidal grid (real theatre, no wrapping)
        # y=0 = front row (stage), y=rows-1 = back row
        self.grid = SingleGrid(self.cols, self.rows, torus=False)

        self.datacollector = DataCollector(
            model_reporters={
                "Fraction Standing": lambda m: m.fraction_standing(),
                "Standing":          lambda m: m.count_state(STAND),
                "Sitting":           lambda m: m.count_state(SIT),
                # Metrics from the paper (None until equilibrium reached)
                "NI":  lambda m: m._ni  if m._ni  is not None else m.step_count,
                "SM":  lambda m: m._sm  if m._sm  is not None else m._compute_sm(),
                "IE":  lambda m: m._ie  if m._ie  is not None else None,
            },
            agent_reporters={
                "State":          "state",
                "InitialQuality": "initial_quality",
            },
        )

        self._place_agents()
        self._run_step1()
        self.datacollector.collect(self)

    # ── Construction ──────────────────────────────────────────────────────────

    def _place_agents(self) -> None:
        """Fill every grid cell with one audience member."""
        positions = list(self.grid.empties)
        self.random.shuffle(positions)
        for pos in positions:
            self.grid.place_agent(AudienceMember(self), pos)

    # ── Step 1: private decisions ─────────────────────────────────────────────

    def _run_step1(self) -> None:
        """
        Step 1 (t=0): all agents make private decisions independently.
        Quality drawn from Uniform(0,1); stand if quality >= quality_threshold.
        Records the initial global majority for IE computation.
        """
        for agent in self.agents:
            agent.make_private_decision(self.quality_threshold)

        n_stand = self.count_state(STAND)
        self._initial_majority = STAND if n_stand >= self.n_agents / 2 else SIT

    # ── Neighbourhood computation ─────────────────────────────────────────────

    def get_visible_neighbors(self, agent: AudienceMember) -> list:
        """
        Return the list of agents visible to `agent` based on
        the chosen neighbourhood structure.

        Grid orientation: y=0 = FRONT (stage), y=rows-1 = BACK.
        "Ahead" = toward stage = decreasing y.

        Five-neighbour layout (from paper p.14):
          F F F   (row directly ahead: y-1)
          F X F   (same row sides only)

        Cone layout (from paper p.14-15):
          F F F F F F F  (3 rows ahead)
            F F F F F    (2 rows ahead)
              F F F      (1 row ahead)
              F X F      (same row sides)
          Width expands by 2 per additional row ahead.

        Global: every other agent on the grid.
        """
        x, y = agent.pos

        if self.neighborhood == "global":
            return [a for a in self.agents if a is not agent]

        # Common: two side neighbours (same row)
        positions = []
        if x > 0:
            positions.append((x - 1, y))
        if x < self.cols - 1:
            positions.append((x + 1, y))

        if self.neighborhood == "five":
            # Three agents directly ahead (row y-1)
            if y > 0:
                for dx in (-1, 0, 1):
                    nx = x + dx
                    if 0 <= nx < self.cols:
                        positions.append((nx, y - 1))

        elif self.neighborhood == "cone":
            # Expanding pyramid toward stage: row y-k has width 2k+1
            for k in range(1, y + 1):   # k = distance ahead (1 to y)
                ny = y - k
                for dx in range(-k, k + 1):
                    nx = x + dx
                    if 0 <= nx < self.cols:
                        positions.append((nx, ny))

        # Collect agents at valid positions
        return [
            self.grid[px][py]
            for px, py in positions
            if self.grid[px][py] is not None
        ]

    # ── Mesa step ─────────────────────────────────────────────────────────────

    def step(self) -> None:
        """
        One tick of Step 2 (social influence update).
        Dispatches to the chosen update rule.

        The paper compares three protocols (Section 6):
          synchronous        — all agents update simultaneously
          async_random       — random agent order, each commits immediately
          async_incentive    — most-unlike-neighbourhood agents go first
        """
        if self.is_equilibrium():
            return   # already stable — no-op

        self.step_count += 1

        if self.update_rule == "synchronous":
            self._synchronous_step()
        elif self.update_rule == "async_random":
            self._async_random_step()
        elif self.update_rule == "async_incentive":
            self._async_incentive_step()

        self.datacollector.collect(self)

        # Record metrics when equilibrium is first reached
        if self.is_equilibrium() and self._ni is None:
            self._ni = self.step_count
            self._sm = self._compute_sm()
            n_stand  = self.count_state(STAND)
            final_majority = STAND if n_stand >= self.n_agents / 2 else SIT
            self._ie = 1 if final_majority == self._initial_majority else 0

    def _synchronous_step(self) -> None:
        """
        Synchronous updating: all agents compute next state from the
        CURRENT snapshot, then all commit simultaneously.
        Mesa's step()/advance() two-phase protocol implements this.
        """
        for agent in self.agents:
            agent.step()      # Phase 1: compute into _next_state
        for agent in self.agents:
            agent.advance()   # Phase 2: commit

    def _async_random_step(self) -> None:
        """
        Asynchronous-Random: agents update one at a time in a random
        order, committing immediately. Each agent sees the already-updated
        states of agents who went before it this tick.
        """
        order = list(self.agents)
        self.random.shuffle(order)
        for agent in order:
            agent.update_immediately()

    def _async_incentive_step(self) -> None:
        """
        Asynchronous-Incentive-Based: agents whose current state is MOST
        unlike their visible neighbourhood update first.

        "Those agents surrounded by agents taking the opposite action are
        the first to update." [paper p.14]

        Dissimilarity = fraction of visible neighbours in the opposite state.
        Agents are sorted descending by dissimilarity (ties broken randomly).
        """
        agents_ranked = sorted(
            self.agents,
            key=lambda a: (a.dissimilarity(), self.random.random()),
            reverse=True,
        )
        for agent in agents_ranked:
            agent.update_immediately()

    # ── Metrics ───────────────────────────────────────────────────────────────

    def count_state(self, state: str) -> int:
        """Count agents in the given state."""
        return sum(1 for a in self.agents if a.state == state)

    def fraction_standing(self) -> float:
        """Primary outcome: fraction of audience currently standing."""
        return round(self.count_state(STAND) / self.n_agents, 4)

    def _compute_sm(self) -> float:
        """
        Stick in the Muds: percentage of agents doing the OPPOSITE of
        the global majority. [paper Tables 1 & 2]
        """
        n_stand   = self.count_state(STAND)
        n_sit     = self.n_agents - n_stand
        minority  = min(n_stand, n_sit)
        return round(100 * minority / self.n_agents, 1)

    def is_equilibrium(self) -> bool:
        """
        True when no agent's state would change under the majority rule.
        Matches the paper's convergence criterion for Step 2.

        This method is DETERMINISTIC — it does not call model.random so
        that calling it does not corrupt the RNG state.

        Treatment of ties (frac == 0.5):
          Since ties produce a random outcome (50/50), they could cause a
          future state change, so ties are treated as NOT at equilibrium.

        NOTE: With synchronous updating on small grids, the system can
        enter persistent 2-cycles (documented in the paper: "Synchronous
        updating takes a very long time to settle down into a steady state.
        This is because members of the crowd can stand and sit many times
        while trying to coordinate." [p.15]). On the paper's 20×20 grid
        these cycles eventually resolve; on smaller grids they may persist.
        """
        for agent in self.agents:
            neighbours = self.get_visible_neighbors(agent)
            if not neighbours:
                continue
            n_standing = sum(1 for n in neighbours if n.state == STAND)
            frac       = n_standing / len(neighbours)

            # Definitive transitions
            if frac > 0.5 and agent.state == SIT:
                return False   # sitting agent would stand
            if frac < 0.5 and agent.state == STAND:
                return False   # standing agent would sit
            # Tie: 50/50 random → potentially unstable → not equilibrium
            if abs(frac - 0.5) < 1e-9:
                return False
        return True
