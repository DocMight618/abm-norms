# UN Shaming Cascade — Simulation README

A Mesa 3.x agent-based model of naming-and-shaming dynamics in the UN General Assembly. 193 member states occupy nodes in a weighted diplomatic network. At each step, states are either **shaming** a target or **neutral**. The simulation tracks how shaming coalitions form, grow, collapse, and re-form over time.

---

## Table of contents

1. [Model overview](#1-model-overview)
2. [Network architecture](#2-network-architecture)
3. [Diplomatic strength and GDI data](#3-diplomatic-strength-and-gdi-data)
4. [Simulation mechanics](#4-simulation-mechanics)
5. [The role of P5 members](#5-the-role-of-p5-members)
6. [Effects of gaining or losing allies](#6-effects-of-gaining-or-losing-allies)
7. [Information cascades in the network](#7-information-cascades-in-the-network)
8. [Parameter guide](#8-parameter-guide)
9. [Limitations and future directions](#9-limitations-and-future-directions)

---

## 1. Model overview

The model is built on the theoretical framework of Miller & Page's work on social dynamics in complex systems, applied to the specific institutional context of UN naming-and-shaming — the practice by which states publicly condemn another state's behaviour in multilateral forums.

Each of the 193 UN member states is an agent with a binary state:

- **SHAME** — the state is actively participating in a shaming coalition against a target.
- **NEUTRAL** — the state has not joined the coalition.

The key departure from grid-based models is that influence travels through a **weighted diplomatic network** rather than across geographic proximity. Two states that share many diplomatic missions, trade relationships, and institutional ties exert stronger pressure on each other than two states that barely interact. This is operationalised through edge weights derived from the Lowy Institute Global Diplomacy Index 2024.

Every 5 steps, all agent states are re-randomised. This is not a bug — it models the empirical reality that shaming coalitions at the UN are episodic and issue-specific. A country that joined a shaming resolution over human rights in one session may sit out the next one entirely. The network topology (who is connected to whom, and how strongly) remains fixed between resets, so the *structure* of diplomatic relationships persists even as coalition membership turns over.

---

## 2. Network architecture

The network is an undirected weighted graph with 193 nodes (one per UN member). Edges are constructed by four rules applied in order:

### Intra-regime clustering

Same-regime pairs (democracy–democracy or non-democracy–non-democracy) are connected with probability:

```
p_connect = p_intra × 4 × avg_strength(A, B)
           = 0.25 × 4 × avg_strength
           = avg_strength   (capped at 1.0)
```

Because `avg_strength` is the mean of two scores each in [0, 1], this means two major democracies (e.g. USA strength ≈ 0.99, Germany ≈ 0.79) have a connection probability near 0.89 — near-certain. Two micro-states (e.g. Nauru and Tuvalu, both ≈ 0.015) have a connection probability near 0.015 — rare. The result is a realistic **core-periphery structure** within each cluster: major powers are tightly interconnected, small states are loosely attached.

### Cross-regime bridging

Democracy–non-democracy pairs connect at a lower base rate:

```
p_connect = p_inter × 4 × avg_strength(A, B)
           = 0.06 × 4 × avg_strength
           = 0.24 × avg_strength
```

Strong cross-regime pairs (e.g. USA–China, edge weight ≈ 0.96) still have a ~23% chance of a direct connection, reflecting the reality of diplomatic and economic entanglement between major powers regardless of regime type. Weak cross-regime pairs are effectively isolated from each other.

### P5 as guaranteed hubs

The five permanent members of the UN Security Council — China, France, Russia, the United Kingdom, and the United States — are wired differently from all other states:

- Each P5 member is **connected to every other node in its own regime cluster** (guaranteed, not probabilistic).
- **All five P5 members are fully connected to each other**, creating a dense backbone that bridges the two clusters.
- Each P5 member receives an additional **20 random cross-cluster edges**, giving it reach into the opposing bloc.

The effect is that P5 nodes have degree orders of magnitude higher than the average non-P5 node. In graph theory terms, P5 members are **scale-free hubs** — their removal would dramatically fragment the network, while removing any single non-P5 node has negligible structural impact.

### Edge weights

Every edge `(A, B)` carries a weight:

```
w(A, B) = (diplomatic_strength[A] + diplomatic_strength[B]) / 2
```

This weight governs how much influence flows across that edge during spread. A high-weight edge between two major powers is a highway for shaming pressure; a low-weight edge between two small states is a dirt road.

---

## 3. Diplomatic strength and GDI data

Each agent has a `diplomatic_strength` attribute in [0, 1] derived from the **Lowy Institute Global Diplomacy Index 2024**, which counts the total overseas diplomatic posts (embassies, high commissions, consulates, permanent missions, and other representations) maintained by each country.

The normalisation formula is:

```
diplomatic_strength = total_posts / 274
```

where 274 is China's post count — the highest in the 2024 dataset. This makes China's strength exactly 1.0 and scales all other countries relative to it.

### GDI coverage

The GDI covers 65 countries (all G20, OECD, and major Asian states). The remaining 128 UN members not in the GDI are assigned estimated post counts based on regional comparators and population tier, anchored to the nearest GDI-covered country. These estimates are conservative and intentionally do not exceed the lowest GDI-measured entry for any given region.

### Strength distribution

The distribution is strongly right-skewed:

| Tier | Countries | Strength range | Examples |
|---|---|---|---|
| Superpowers | 2 | 0.97–1.00 | China (1.00), USA (0.99) |
| Major powers | ~15 | 0.45–0.91 | France (0.91), Russia (0.84), Germany (0.79) |
| Mid-range | ~60 | 0.15–0.44 | Brazil (0.75), Indonesia (0.47), Pakistan (0.44) |
| Small states | ~80 | 0.04–0.14 | Costa Rica (0.19), Fiji (0.03) |
| Micro-states | ~36 | 0.01–0.03 | Nauru (0.015), Tuvalu (0.015), Bhutan (0.036) |

This distribution has two important consequences for the simulation. First, the diplomatic network is highly unequal — a small number of nodes carry most of the edge weight. Second, the shaming pressure experienced by any given neutral state depends almost entirely on whether its high-strength neighbours are shaming, not on whether its low-strength neighbours are.

---

## 4. Simulation mechanics

### Step sequence

Each model step runs four phases in order:

1. **Periodic reset** (every 5 steps): all agent states are re-randomised, with a new random number of shamers drawn uniformly from `[shame_min, shame_max]`. The network topology does not change.
2. **Buffer phase**: each agent copies its current state into `_next_state`. This implements a synchronous update — no agent sees the within-step changes of its neighbours until the commit phase.
3. **Spread / revert phase**: the model applies either `_apply_spread` or `_apply_revert` depending on the sign of the `spread` parameter.
4. **Commit phase**: all agents advance from `_next_state` to `state`.

### Spread mechanics (`spread > 0`)

Each step, up to `spread` neutral agents are recruited into the shaming coalition. Recruitment is not uniform — it is **weighted by diplomatic pressure**:

```
pressure(A) = Σ  edge_weight(A, B) × [B is shaming]
              B ∈ neighbours(A)
```

If any shaming neighbour of A is a P5 member, a **2× multiplier** is applied to A's total pressure. The model then samples `k` agents from each regime pool (democracy neutrals and non-democracy neutrals separately), where `k` is random up to `min(spread, pool_size)`, with selection probabilities proportional to pressure + a small floor of 0.01.

The separation by regime pool is important: democracies recruit from democracies, non-democracies from non-democracies. This reflects the empirical tendency of states to follow the lead of ideologically aligned partners on human rights issues.

### Reversion mechanics (`spread < 0`)

When `spread` is negative, up to `|spread|` shaming states are flipped back to neutral each step. Reversion probability is **inversely proportional to diplomatic strength**:

```
reversion_weight(A) = 1.0 - diplomatic_strength(A)
                      × 0.5  (if A is P5)
```

This means micro-states with strength near 0 have reversion weight near 1.0 — they are easy to peel away from the coalition. Major powers with strength near 0.8 have reversion weight near 0.2 — they are resilient. P5 members are additionally protected by the 0.5 multiplier, making them the last to defect even under sustained pressure.

---

## 5. The role of P5 members

The P5 are not just quantitatively different from other states — they are structurally different. Their effect on the simulation operates through three distinct channels.

### Channel 1: Hub degree

A typical non-P5 major power (e.g. Japan, Germany) has connections to perhaps 40–80% of its regime cluster and a handful of cross-regime edges. A P5 member is connected to **100% of its regime cluster** plus 20 random cross-cluster edges. This makes P5 nodes the most influential in terms of raw network reach.

When a P5 member enters the shaming state, it immediately becomes a shaming neighbour of every node in its cluster. The pressure experienced by every neutral democracy rises simultaneously the moment the USA or France begins shaming. Conversely, when a P5 member leaves the shaming state, the pressure on all its neighbours drops at once.

### Channel 2: Pressure amplification

Even beyond their degree advantage, shaming P5 members grant a **2× bonus** to the recruitment pressure on any neutral neighbour. This models the qualitative difference between being pressured by France versus being pressured by Luxembourg — both are democracies, but French diplomatic pressure carries weight that Luxembourgish pressure does not.

In practice, a single P5 member shaming can effectively double the recruitment probability of a large fraction of its cluster. Two or more P5 members shaming simultaneously creates near-certain recruitment pressure on well-connected neutral states in that cluster.

### Channel 3: Reversion resistance

P5 members are twice as resistant to reversion as their raw strength score would imply. A country with strength 0.84 (Russia) would normally have a reversion weight of 0.16; with the P5 halving, it drops to 0.08. This means that once a P5 member joins a shaming coalition, it tends to stay in it for multiple steps unless the reset event overrides it.

### The chokepoint effect

Because P5 members bridge the two regime clusters (via their guaranteed cross-cluster edges and the P5–P5 full connection), a shaming P5 member from one bloc can exert pressure on states in the opposing bloc. A shaming USA reaches non-democracy nodes through cross-cluster edges; a shaming China reaches democracy nodes similarly. This creates an asymmetric chokepoint: **shaming cascades that capture a P5 member from one cluster can leak into the opposing cluster**, something that is nearly impossible without P5 involvement given the low cross-regime connection probability for ordinary states.

### Simulation implications

| Scenario | Expected outcome |
|---|---|
| 0 P5 members shaming | Cascade probability low; coalitions small and unstable |
| 1 P5 member shaming (same cluster) | Moderate cascade within that cluster; cross-cluster effects limited |
| 2+ same-cluster P5 shaming | High cascade probability within cluster; likely majority coalition |
| P5 members split (e.g. USA shaming, China not) | Intra-cluster cascades proceed independently; cross-cluster leakage muted |
| All 5 P5 shaming | Near-universal cascade — neutral states face combined pressure from both clusters simultaneously |

The split-P5 scenario is the most interesting and arguably the most realistic. It models situations like the 2022 UNGA vote on Ukraine, where Western P5 members (USA, UK, France) drove condemnation while Russia actively opposed it and China abstained. The simulation captures this as sustained democratic-cluster shaming pressure co-existing with a resistant non-democratic cluster.

---

## 6. Effects of gaining or losing allies

### Gaining allies (coalition growth)

When a neutral state flips to shaming, the effect on the coalition depends almost entirely on the flipping state's diplomatic strength and network position.

**Gaining a high-strength ally** (e.g. Brazil, India, Turkey — strength 0.44–0.73) has a multiplicative effect. These states have many connections within their regime cluster, so their transition immediately increases the pressure felt by all their neutral neighbours. The effect is non-linear: gaining one high-strength ally may tip several of their neighbours over an implicit pressure threshold in the following steps, producing a **secondary cascade**.

**Gaining a low-strength ally** (e.g. a small island state, strength < 0.05) has almost no effect on cascade dynamics. Its connections are sparse and its edge weights are small, so it contributes negligibly to the pressure felt by any remaining neutral state. The raw count of shamers rises by one, but the weighted shaming power (the metric that actually drives recruitment) barely moves.

This creates a counterintuitive result: a coalition of 60 small states may be less effective at growing than a coalition of 20 mid-range states, because the 20 mid-range states have stronger connections to the remaining neutrals.

### Losing allies (coalition erosion)

Coalition erosion under negative spread follows the same logic in reverse, but with an important asymmetry: **reversion targets weak states first**.

Because reversion weight is `1 - diplomatic_strength`, the states most likely to defect are the ones contributing least to coalition pressure. The coalition sheds its periphery before its core. This produces a characteristic pattern: under negative spread, you observe a slow decline in shaming count as small states defect one by one, but the weighted shaming power (what actually drives recruitment pressure) declines much more slowly — because the high-strength core members are protected.

The practical consequence is that coalitions are **more durable than their raw size suggests**. A coalition that has lost half its members but retained its major-power members may still exert nearly the same recruitment pressure on neutrals as at its peak.

### The tipping point

Because recruitment probability is proportional to the sum of shaming neighbours' edge weights, there is an implicit tipping point for any given neutral state. If its shaming neighbours' combined edge weight crosses a threshold, the probability of recruitment in any given step becomes high enough that conversion is nearly certain within a few steps. If it falls below that threshold, the neutral state may persist indefinitely.

This creates **hysteresis**: a coalition that grew large enough to put all neutrals above the tipping point will remain large even if a few members defect, because the remaining coalition still provides enough pressure. Only if defections cascade past the tipping point does the coalition rapidly collapse.

---

## 7. Information cascades in the network

### What a cascade looks like

A shaming cascade is a self-reinforcing wave of state transitions from neutral to shaming, propagating through the diplomatic network. In the simulation, it begins when enough initial shamers are placed in positions of high centrality — connected to many neutral states with high-weight edges.

The typical cascade proceeds in phases:

1. **Ignition** (steps 1–2): initial shamers exert pressure on their direct neighbours. High-strength neighbours of P5 shamers are most vulnerable. A few additional states convert.

2. **Amplification** (steps 2–4): converted states become new sources of pressure, adding to the pressure already exerted by the original shamers. States that were previously below the implicit threshold may now cross it. Conversion rate accelerates.

3. **Saturation** (steps 4–5): most reachable neutral states have converted. The remaining neutral states are either isolated (few connections to shamers), high-strength (low reversion risk, but also low recruitment pressure from their peers if peers are already shaming), or across the regime boundary.

4. **Reset** (step 5): the model re-randomises all states, collapsing the coalition and beginning a new cycle.

### Cascade geometry

The cascade geometry depends critically on where the initial shamers are placed. Because agent placement is randomised at each reset, the simulation samples different starting configurations every 5 steps.

Three geometries dominate:

**Hub-anchored cascade**: one or more P5 members are in the initial shaming set. The cascade propagates rapidly through the P5 member's cluster because every node in that cluster is a direct neighbour. This is the fastest possible cascade and can reach a majority within 2–3 steps.

**Peripheral cascade**: initial shamers are concentrated among small states. The cascade propagates slowly along sparse edges. It may reach a local cluster of small states without ever reaching the high-strength core. These cascades look significant by raw count but are diplomatically weak.

**Bridged cascade**: initial shamers include at least one member from each regime cluster, plus the P5–P5 bridge. Pressure propagates across the regime boundary through the cross-cluster edges. These cascades are rarer but can produce the largest coalitions because they recruit from both pools simultaneously.

### Why cascades stop

Cascades do not run to completion (unanimous shaming) under typical parameters for two reasons:

1. **Isolation**: states with no shaming neighbours receive only the floor pressure of 0.01. They are selected for recruitment with positive probability but at very low rates. Complete saturation would require many steps beyond the 5-step reset window.

2. **Regime separation**: the cross-regime connection probability is much lower than the intra-regime probability. A cascade fully saturating the democracy cluster will still have limited reach into the non-democracy cluster without P5 bridging. The two clusters act as partially independent systems.

### The oscillation pattern

Because states are re-randomised every 5 steps, the shaming count oscillates rather than converging. The amplitude and mean of the oscillation encode useful information:

- **High mean, low amplitude**: the network structure strongly determines outcomes regardless of initial conditions. Every reset produces a similar shaming coalition because the network's core members drive recruitment.

- **Low mean, high amplitude**: outcomes are highly sensitive to initial conditions. Whether the initial shamers include P5 members matters enormously.

- **Trending upward then plateau**: positive spread is strong enough to recruit near-universally within 5 steps, so the coalition always reaches saturation before the reset.

### Cascade speed and the `spread` parameter

The `spread` parameter directly controls cascade velocity. At `spread = 10`, up to 10 states per regime pool can be recruited per step, producing moderately fast cascades. At `spread = 30`, the cascade can sweep through a cluster in 1–2 steps. At `spread = 1`, cascades are slow and rarely reach saturation before the reset.

The interaction between `spread` and network structure is important: a high `spread` on a sparse network (many micro-states, few connections) still produces slow cascades because most candidate states have low pressure scores and are unlikely to be selected even when many recruitment slots are available.

---

## 8. Parameter guide

| Parameter | Default | Effect |
|---|---|---|
| `seed` | 42 | Controls all randomness. Same seed = identical run. Different seeds test structural robustness. |
| `shame_threshold` | 0.50 | Display-only parameter shown in tooltips. Does not affect state transitions. |
| `shame_min` | 20 | Minimum initial shamers after each reset. Lower = more runs start with small coalitions. |
| `shame_max` | 77 | Maximum initial shamers after each reset (~40% of the assembly). |
| `spread` | 10 | Cascade speed. Positive = recruitment, negative = reversion. Zero = no global spread. |

### Recommended experiments

**Test P5 chokepoint effect**: set `shame_min = shame_max = 5` and run repeatedly. Observe whether the 5 initial shamers happen to include any P5 members (visible in the P5 counter). Compare runs where P5 are shaming vs. not — the cascade size difference illustrates the chokepoint.

**Test coalition fragility**: set `spread = -5`. Watch how the coalition erodes — which states defect first? The weighted shame percentage in the counter should decline much more slowly than the raw count, showing that high-strength members hold.

**Test cascade speed**: compare `spread = 1` vs `spread = 20` with the same seed. At `spread = 1` you will see gradual accumulation within each 5-step window; at `spread = 20` the coalition likely saturates in 2 steps then collapses at the reset.

**Test regime separation**: set a high seed and repeatedly step. Look at the Regime plot. When the democracy cluster and non-democracy cluster shame at very different rates, it indicates that cascade is propagating through one cluster without crossing the regime boundary — no P5 bridge is active in that direction.

---

## 9. Limitations and future directions

### Current limitations

**Binary state model**: real countries express shaming in degrees — a statement of concern, a co-sponsored resolution, a vote for a resolution, a speech, sanctions. The binary SHAME/NEUTRAL abstraction loses this gradation.

**Episodic reset**: the 5-step reset is a modelling convenience that captures the episodic nature of UN sessions, but it is not calibrated to any real diplomatic calendar. Future versions could tie resets to observable events (Security Council sessions, UNGA special sessions, treaty body reviews).

**Static network**: the diplomatic network is fixed for the duration of a run. In reality, diplomatic ties change — the Russia-Ukraine war severed many connections, India and Turkey have rapidly expanded their networks, and bilateral disputes cause embassy closures. A dynamic network model would capture these shifts.

**No target-specific dynamics**: the model does not represent the target state — the country being shamed. In practice, targets respond to shaming through counter-mobilisation, economic inducements, and reciprocal diplomatic pressure. Modelling the target as an active agent would significantly change cascade dynamics.

**Regime classification is binary**: countries are classified as democracy or non-democracy, but the empirical literature identifies a spectrum — full democracies, flawed democracies, hybrid regimes, authoritarian states. A finer regime classification would produce more realistic intra-cluster variation.

### Future directions

- **Trade tie weighting**: supplement GDI post counts with bilateral trade volume as an additional edge weight component, reflecting that economic interdependence also structures diplomatic pressure.

- **Issue-specific alignment**: different shaming episodes activate different sub-networks. Human rights shaming activates different coalitions than environmental shaming. Future versions could parameterise edge weights by issue area.

- **Targeted counter-shaming**: introduce a second target agent that actively recruits neutral states into a counter-coalition, creating a genuine competitive dynamic between two blocs.

- **Calibration against historical votes**: match the model's shaming coalition distributions against the actual distribution of UNGA resolution votes on specific human rights issues, and fit `spread` and `shame_min/max` to historical data.

---

*Built with Mesa 3.x, NetworkX, and Solara. Diplomatic strength data from the Lowy Institute Global Diplomacy Index 2024.*
