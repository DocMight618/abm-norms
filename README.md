# UN Shaming Cascade

A Mesa 3.x agent-based model of how naming-and-shaming norms emerge, weaken,
and re-form in UN-style human-rights forums. The model is motivated by the UN
Human Rights Council's Universal Periodic Review process and represents all 193
UN member states as agents in a complete directed weighted forum network. At
each step, a state is either `SHAME` or `NEUTRAL`.

The research question is: how do norms emerge in international relations? The
central claim is simple: norms in these forums do not emerge because every state
independently changes its mind. They emerge when public positions become
socially visible, influential states make participation less costly, and enough
states cross their personal thresholds that joining the coalition starts to feel
like the expected behavior.

## Table of Contents

1. [Research Question And Motivation](#1-research-question-and-motivation)
2. [Underlying Mechanism](#2-underlying-mechanism)
3. [How Norms Emerge In The Model](#3-how-norms-emerge-in-the-model)
4. [Why Networks Matter](#4-why-networks-matter)
5. [How Democracy Interacts With The Network](#5-how-democracy-interacts-with-the-network)
6. [Diplomatic Strength](#6-diplomatic-strength)
7. [Step Mechanics](#7-step-mechanics)
8. [Agent Decision Rules](#8-agent-decision-rules)
9. [P5 Members](#9-p5-members)
10. [Parameters](#10-parameters)
11. [Recommended Experiments](#11-recommended-experiments)
12. [Analysis Summary](#12-analysis-summary)
13. [Current Limitations](#13-current-limitations)
14. [Code Availability And AI Statement](#14-code-availability-and-ai-statement)
15. [License](#15-license)

## 1. Research Question And Motivation

This project uses agent-based modeling to study how norms appear in
international relations. The substantive case is naming and shaming in the UN
Human Rights Council and related UN human-rights forums. Naming and shaming is
modeled as a public act: a state either joins a coalition condemning a target or
remains neutral.

The model builds on three ideas from the paper. First, international
organizations can generate public pressure that changes state behavior. Second,
human-rights review processes are politicized: states evaluate violations
through alliances, regime similarity, strategic interests, and reputational
concerns. Third, deviations from institutional norms can themselves become
normalized when repeated often enough. The model therefore treats norm emergence
and norm erosion as dynamic processes produced by repeated state interaction.

The computational contribution is to combine this norms literature with a
threshold model of collective behavior. Rather than assuming that every state
responds identically to a shaming campaign, each state has its own threshold for
joining. A norm emerges when enough states cross their thresholds that shaming
becomes self-reinforcing.

## 2. Underlying Mechanism

The underlying mechanism is public diplomatic pressure. Naming and shaming is
not treated as a purely moral choice or as a simple expression of fixed state
preferences. States adopt public positions in response to a changing strategic
and reputational environment. When some states shame a target, they alter the
costs and benefits faced by other states. Remaining neutral may become more
costly if many visible actors have already condemned the target, while joining
the coalition may become more attractive if it signals alignment with powerful
states or with an emerging international norm.

This pressure works through two main channels. The first is strategic alignment.
Middle powers and smaller states may gain material, diplomatic, or political
benefits by adopting positions similar to those of larger states. A small state
that joins a shaming coalition led by a powerful actor can signal reliability,
strengthen a relationship, or avoid the costs of opposing an influential partner.
In this sense, shaming can spread not because every state independently agrees
with the normative claim, but because joining the coalition is strategically
useful.

The second channel is reputational gain. States may join shaming coalitions to
be seen as defenders of human rights, international law, or institutional order.
Publicly adopting the same position as a growing coalition can generate soft
power by allowing states to present themselves as responsible members of the
international community. This reputational mechanism matters especially in
public forums, where state behavior is visible to allies, rivals, domestic
audiences, NGOs, and international organizations.

The model captures this mechanism using directed weighted ties and individual
thresholds. Directed ties represent asymmetric public pressure: powerful states
exert more pressure on smaller states than smaller states exert in return.
Individual thresholds represent the amount of incoming pressure a state needs
before joining the coalition becomes worthwhile.

## 3. How Norms Emerge In The Model

Naming-and-shaming is modeled as a threshold cascade. Every state has a personal
threshold: the amount of visible diplomatic pressure it must experience before it
joins a shaming coalition. That threshold is not identical across states.
Democracies and powerful states begin with lower thresholds; weaker
non-democracies begin with higher ones.

At each step, neutral states observe the weighted share of their forum network
that is currently shaming. If the pressure they receive exceeds their individual
threshold, they become eligible to join. Eligible states are then sampled with
probability proportional to the strength of the shaming pressure they receive.

This makes norms emergent in three linked ways:

1. Public shaming by one state changes the environment for every other state.
2. New joiners become new sources of pressure, so coalition growth can feed on
   itself.
3. Repeated success or failure changes later thresholds. Large cascades lower
   neutral states' thresholds in future rounds; failed cascades raise them.

The last piece is the norm-learning mechanism. When shaming repeatedly fails to
attract a large coalition, neutral states internalize non-participation as
acceptable. Their thresholds drift upward, making future shaming harder. When
large coalitions repeatedly form, participation becomes normalized; thresholds
drift downward.

## 4. Why Networks Matter

The UN is not modeled as a sparse friendship network anymore. In a forum, every
state can observe every other state's public position. For that reason, the
network is now a complete directed graph: every state has a tie to every other
state, but the tie from A to B can be stronger or weaker than the tie from B to
A.

The important question is not whether a tie exists, but how much exposure and
salience move through it, and in which direction. The network should not be
interpreted as a map of friendship or ideological agreement. It is a map of
diplomatic exposure and asymmetric influence: a high-weight tie from A to B
means that A's public position is likely to be noticed by B and to place
meaningful pressure on B.

This means adversarial pairs, such as the United States and China, can still be
deeply tied. Their relationship is substantively conflictual, but diplomatically
dense. However, the model does not assume that the two directions are equal. A
P5 member or major power places much more pressure on a small state than a small
state places on it. In naming-and-shaming politics, this matters because
influence often operates through salience, reputational pressure, and
agenda-setting rather than persuasion alone. Contact creates the channel; source
power, regime affinity, and individual thresholds determine whether that exposure
translates into behavioral change.

Each edge has a weight based on:

```text
edge A -> B     = pressure from A on B
influence core  = 0.10 + 0.90 * diplomatic strength of A
regime affinity = 1.00 for same-regime pairs, 0.65 for cross-regime pairs
P5 visibility   = 1.25 if A is a P5 member
```

This structure better reflects the forum setting. All states are formally
co-present, but pressure from a major diplomatic actor is more consequential
than pressure from a micro-state. Same-regime pressure also travels more easily
than cross-regime pressure because states tend to interpret criticism,
legitimacy, and audience costs through ideological and institutional affinities.

The network matters because a coalition's raw size is not the same as its
diplomatic force. A coalition of many weak states can be numerically large but
apply little pressure. A smaller coalition that includes high-strength states or
P5 members can move many more agents over their thresholds.

## 5. How Democracy Interacts With The Network

Democracy matters in two places.

First, it affects thresholds. Democracies are modeled as more likely to join
human-rights shaming coalitions, so their initial beta factor is lower:

```text
Democracy beta factor     = 0.7
Non-democracy beta factor = 1.4
P5 beta factor            = 0.5
```

A lower beta factor produces a lower threshold, meaning democratic states need
less social pressure before joining. This captures the idea that democracies are
more exposed to human-rights discourse, domestic audience costs, and liberal
internationalist norms.

Second, democracy affects directed edge weights. Same-regime influence is
stronger than cross-regime influence. This does not mean cross-regime influence
is impossible; the complete directed graph ensures that every state can pressure
every other state. It means that regime-similar pressure is more persuasive.
Democracies more readily follow other democracies, while non-democracies more
readily follow states with similar sovereignty-first priors.

Together, this creates clustered cascades. A shaming norm can consolidate quickly
inside the democracy group, struggle to cross into the non-democracy group, and
then become broader only if enough powerful or cross-regime actors also join.

## 6. Diplomatic Strength

Each agent has a `diplomatic_strength` value in `[0, 1]`. The value is based on
the Lowy Institute Global Diplomacy Index 2024, using total diplomatic posts
where available and conservative estimates for countries not covered by the
index.

```text
diplomatic_strength = total diplomatic posts / 274
```

China's 274 posts define the maximum. Diplomatic strength affects:

- outgoing edge weights in the forum network;
- initial threshold values;
- recruitment pressure;
- resistance to reverting from `SHAME` back to `NEUTRAL`.

The model therefore treats power as relational. Powerful states do not just have
larger nodes in the visualization; their choices change the pressure environment
for everyone else.

| Tier | Countries | Strength Range | Examples |
|---|---:|---:|---|
| Superpowers | 2 | 0.97-1.00 | China, United States |
| Major powers | ~15 | 0.45-0.91 | France, Russia, Germany |
| Mid-range | ~60 | 0.15-0.44 | Indonesia, Pakistan, South Africa |
| Small states | ~80 | 0.04-0.14 | Fiji, Barbados, Belize |
| Microstates | ~36 | 0.01-0.03 | Nauru, Tuvalu, Bhutan |

## 7. Step Mechanics

Each model step runs in a synchronous two-phase update.

1. Every agent copies its current state into `_next_state`.
2. The model applies spread or reversion by asking agents for their decision
   weights.
3. Every agent commits `_next_state` back to `state`.
4. The data collector records the new state of the model.

Mesa's `self.agents.do("step")` and `self.agents.do("advance")` methods run the
agent-level step scripts. This keeps the model file focused on sequencing rather
than manually looping over every agent.

Every five steps, the model records the current cascade size, updates neutral
agents' thresholds, and re-randomizes the initial shaming coalition. The reset
represents the episodic nature of UN votes, resolutions, and agenda items:
coalitions do not persist mechanically from one issue to the next, but the
underlying social structure and learned thresholds do.

## 8. Agent Decision Rules

The agent decision rules live in `agent.py`.

Each state has an individual shaming threshold drawn from a Beta distribution:

```text
threshold(A) ~ Beta(alpha, beta_A)
```

`alpha` is shared across the model and represents the general ease with which
shaming can cascade through the forum. The agent-specific `beta_A` represents
state-level resistance to joining the shaming coalition. It is anchored in
diplomatic strength and regime type, so powerful and democratic states are
modeled as easier to recruit, while weaker and non-democratic states generally
require more pressure before joining.

`CountryAgent.recruitment_weight()` decides whether a neutral state is eligible
to join the shaming coalition. It calculates:

```text
raw_pressure(A) = sum of directed edge weights from shaming states to A
max_pressure(A) = sum of all directed edge weights into A
norm_pressure(A) = raw_pressure(A) / max_pressure(A)
```

If `norm_pressure(A)` is below the agent's personal threshold, the recruitment
weight is zero. Otherwise, the weight is:

```text
raw_pressure * P5_bonus + 0.01
```

The small floor prevents eligible but weakly pressured agents from having
exactly zero probability. If a shaming source is a P5 member, pressure receives
a bonus.

`CountryAgent.revert_weight()` handles movement in the other direction. Weaker
states are easier to peel away from a coalition:

```text
revert_weight = 1.0 - diplomatic_strength
```

P5 members receive an additional protection factor, making them less likely to
defect once they are shaming.

The model samples without replacement when choosing agents to change state. The
older implementation used `random.choices()` and then filtered duplicates with a
`seen` set. That made the code harder to read and could produce fewer actual
state changes than the sampled `k`. The helper in `model.py` now removes each
selected agent before the next draw.

## 9. P5 Members

The P5 no longer matter because they have artificially guaranteed extra edges.
In a complete directed forum network, everyone already has an edge to everyone
else.

They still matter through three mechanisms:

- high diplomatic strength, which raises their outgoing influence;
- P5 visibility, which amplifies edges from them to other states;
- P5 shaming bonus, which increases pressure on eligible neighbors.

This is closer to the substantive interpretation: P5 members are not influential
because only they can reach everyone. They are influential because everyone can
see them and their public positions carry unusual diplomatic weight.

## 10. Parameters

| Parameter | Default | Effect |
|---|---:|---|
| `seed` | 42 | UI-facing random seed. Internally passed to Mesa as `rng` because Mesa's `seed` keyword is deprecated. |
| `alpha` | 2.0 | Shared Beta alpha parameter. Higher values make cascades easier by lowering thresholds. |
| `beta_scale` | 1.0 | Multiplier on each agent's initial threshold anchor. Higher values make cascades harder. |
| `shame_min` | 20 | Minimum number of initial shamers after each reset. |
| `shame_max` | 77 | Maximum number of initial shamers after each reset. |
| `spread` | 10 | Positive values recruit neutral states; negative values revert shaming states. |

## 11. Recommended Experiments

The paper analyzes five simulation runs. The table below lists the parameter
values used to reproduce them.

| Simulation | `seed` | `alpha` | `beta_scale` | `shame_min` | `shame_max` | `spread` | Steps |
|---|---:|---:|---:|---:|---:|---:|---:|
| Baseline | 42 | 2.0 | 1.0 | 20 | 77 | 10 | 30-50 |
| Norm emergence | 42 | 2.5 | 0.5 | 35 | 77 | 15 | 50+ |
| Norm erosion | 42 | 1.5 | 2.5 | 5 | 25 | 3 | 50+ |
| P5 visibility | 42 | 2.0 | 1.0 | 5 | 5 | 10 | 15-25 |
| Power versus numbers | 42 | 2.0 | 1.0 | 60 | 90 | 5 | 30 |

**Norm emergence:** use low resistance and stronger recruitment
(`alpha = 2.5`, `beta_scale = 0.5`, `spread = 15`). Watch whether repeated
windows push mean thresholds down. If they do, the shaming norm is
consolidating.

**Norm erosion:** use higher resistance and weaker recruitment
(`alpha = 1.5`, `beta_scale = 2.5`, `spread = 3`). Repeated failed cascades
should push thresholds upward and increase the norm-erosion index.

**Democracy clustering:** compare the democracy and non-democracy shaming plots.
If democracies rise first and non-democracies lag, the model is producing a
regime-clustered cascade.

**Power versus numbers:** compare the raw shaming count to weighted shaming.
Large coalitions of weak states may look impressive by count but exert less
pressure than smaller coalitions containing high-strength states.

**P5 visibility:** hold initial shaming counts low (`shame_min = shame_max = 5`)
and compare runs where one or more P5 members start as shaming against runs
where they do not. P5-start runs should usually grow faster.

## 12. Analysis Summary

The baseline model shows two patterns. First, high-strength states are more
likely to drive shaming cascades because their outgoing influence creates more
incoming pressure for other states. Second, democratic regimes generally spread
the norm faster than non-democracies because democracies begin with lower
thresholds and stronger within-regime receptivity to human-rights shaming.

The baseline results also show an important conditional effect. If China,
Russia, or both are among the initial shamers, the cascade can move faster in
the non-democracy cluster than in the democracy cluster. This is because China
and Russia combine high diplomatic strength, P5 visibility, and same-regime
affinity with many non-democratic states. Their public positions generate large
incoming pressure for smaller non-democracies. The model therefore suggests that
regime type shapes receptivity, but powerful states shape activation.

The norm-emergence simulation illustrates the self-reinforcing logic of public
pressure. Once a state joins the shaming coalition, it becomes a new source of
pressure on surrounding neutral states. If multiple states join in one step, the
pressure increases further. Participation generates pressure, and pressure
generates more participation. This is how a shaming position becomes a cascade.

The norm-erosion simulation shows the opposite process. When thresholds are high
and recruitment is weak, public pressure may be present but insufficient. States
do not perceive enough strategic or reputational value in joining the coalition,
so shaming fails to spread. Repeated failed cascades push thresholds upward,
making non-participation easier to maintain.

The P5 simulation reinforces the claim that power matters more than numbers. A
large coalition of weak states may not generate enough pressure to recruit
powerful actors. By contrast, when P5 members or other high-strength states join
early, cascades are more likely to form and move quickly. This supports the
model's core mechanism: norm diffusion depends not only on how many states shame,
but on who those states are.

## 13. Current Limitations

The model keeps a binary `SHAME`/`NEUTRAL` state, while real states can abstain,
co-sponsor, vote yes, vote no, issue speeches, or remain strategically silent.

Democracy is also simplified into a binary classification. A richer model could
use continuous regime scores, regional blocs, aid dependence, trade ties, treaty
membership, or issue-specific alignments.

Finally, the network weights are theoretically motivated rather than estimated
from observed voting or speech data. The complete forum network is more
intuitive for a UN setting, but future versions could calibrate edge weights to
actual UNGA voting similarity, co-sponsorship patterns, or diplomatic mission
overlap.

## 14. Code Availability And AI Statement

The Python scripts used for the simulation are part of this project directory.
The model code is organized across `agent.py`, `model.py`, and `app.py`.

Codex was used to help debug, organize, and document the Python scripts and the
README.

## 15. License

This project is licensed under the Creative Commons Attribution 4.0
International License (CC BY 4.0). See [LICENSE.md](LICENSE.md) for details.
