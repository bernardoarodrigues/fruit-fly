# Active implementation plan: one male fly

User scope update: 2026-09-04. Focus on **one male Drosophila** to accelerate testing; a second fly and paired reproduction are deferred. The user wants a solid simulation through the relevant planned milestones, a way to watch it, and a GitHub repository updated during development. Additional compute can be supplied when measurements justify it.

This is the active implementation plan. The research roadmap records the broader two-animal program and remains the source of scientific validation requirements. This scope update does not turn a body animation or a small substitute graph into completion.

## Current scientific priority: 2026-09-05 UTC

The user explicitly cancelled the proposed embodied Eon integration benchmark. The existing bounded Eon neural results were independently reviewed, committed and pushed at `ab2bd63`. The [inhibitory C0/C1/H0/H1 factorial](inhibitory-factorial.md) is now executed: C0 reproduces the original traces exactly, the hybrid equations obey their numerical bounds, and all arms retain the same two-cell spike trains. No arm is selected. Do not continue copying Eon's stimulation or fitting motor gains as the main path to realism. No embodied P9/taste benchmark is required by the latest steering.

H1 must not be selected because its voltage plot looks better. Before promotion it must satisfy numerical bound and accuracy checks, relevant physiological amplitude/timing comparisons, meaningful stimulus contrasts, seed robustness, and improved recurrent full-network behavior without uncontrolled persistence. Conditional fixed-input replay cannot satisfy the recurrent gate. Record failed and unresolved criteria explicitly; see [operational promotion gates](inhibitory-promotion-gates.md).

The [recurrent implementation/performance check](inhibitory-recurrent-performance.md) now completes all five 50 ms runs with 280 checks. C0 matches the original full state exactly; altered arms generate their own distinct recurrent histories. The hybrid cost rises as inhibition spreads. Next is a matched four-thread check, then the [separately scoped three-seed stimulus/withdrawal comparison](inhibitory-recurrent-design.md), preserving all four controls. The short startup probe cannot satisfy the longer recurrent gate.

The [5 ms filter comparison](ln-inhibitory-linear-filter-results.md) and its [independent numerical review](ln-inhibitory-linear-filter-independent-review.md) reject the declared direct mapping between the displayed rate and current summaries: the bounded filtered-rate change is negative while the current change is positive. Different cohorts, acausal smoothing and unresolved circuit identities prevent interpreting this as receptor or full-network rejection. No gain or time constant was fitted.

BANC is available as a female CNS structural comparison; the [retained metadata audit](../research/17-banc-comparative-circuit-insights.md) informs identities and circuit hypotheses without supplying missing electrophysiological parameters or reopening the deferred paired-animal scope.

## Required milestones and evidence

| Milestone | Required implementation | Completion evidence |
|---|---|---|
| M0 Provenance/repository | GitHub repository; pinned code/data; retained notes; no hidden downloads/filters | Remote commit exists; manifests, hashes and licensing notes agree with actual imports |
| M1 Single physical fly | One body; controlled arena; food/water/terrain; documented intended-male morphology profile | Stable reproducible trajectories, contacts, units, controller parity and declared anatomy gaps |
| M2 Sensory pipeline | Bilateral odor, contact taste, vision/proprioception; appropriate stimulus channels and state | Numeric calibration/geometry tests; input replay; no privileged source coordinates enter neural policy |
| M3 Neural replication | Persistent LIF engine checked against Shiu/Brian2 equations and selected published circuit experiments | Independent numerical comparison; delay/refractory/chunk/reset tests; published assay reproduction recorded separately |
| M4 Male CNS import | Full retained MaleCNS neuronal graph with explicit transmitter/sign assumptions | Dataset inventory/filter audit, all selected neurons retained, connectivity and source checksums |
| M5 Closed sensorimotor loop | Actual male neural activity drives the physical body's motor interface | Causal ablation, shuffled/control outputs, stable dynamics, timestep/coupling checks, synchronized clocks |
| M6 Foraging/feeding/homeostasis | Sense food, approach/stop/feed, deplete food, maintain separate energy/water/fullness | Held-out layouts/plumes, input dissociations, intake/resource conservation and neural dependence |
| M7 Single-animal repertoire | Grooming, escape/avoidance, rest/sleep/circadian state, learning; male social-cue/song assays where feasible alone | Per-behavior source/assay, quantitative comparisons, interventions and documented surrogate components |
| M8 Mechanistic motor expansion | Assess/refine VNC–motor–actuator pathways against retained controller baseline | Better neural/kinematic held-out predictions; documented remaining motor/muscle approximations |
| M9 Watch/control/record | Browser or application viewer showing the actual current simulation; pause/reset/camera/stimulus/ablation controls | Live UI inspected; controls verified against process state, frames and recorded trajectory; errors surfaced |
| M10 Robustness/performance | Reproducible runs, automated focused tests, profiling and compute recommendation | Longer-run checks, CPU/memory/full-loop measurements, reproducible launch from repository |

Flight/lifespan expansion remains part of the broader roadmap and must be assessed after the walking loop. A flight requirement cannot be supported by a walking-only check. Paired courtship, copulation, sperm transfer to a female, oviposition and offspring require the deferred second-animal stage; do not fake them as single-male behaviors.

## Scientific boundaries

- The available body is female-derived; intended-male configuration must disclose this until measured male morphology is implemented. A filename or changed color is not male anatomy.
- The male connectome is a measured structural scaffold with incomplete synaptic attachment; LIF dynamics and many signs/parameters remain model assumptions.
- A trained/CPG/reflex walking controller is a declared motor surrogate. Decisions must depend on recorded neural outputs for neural-control claims.
- Engine numerical parity, published-circuit replication, and biological whole-animal fidelity are separate validation levels.
- Any module with engineering constants must state them as such. New hypotheses remain unvalidated until appropriate experiments support them.

## Execution record

Initial state: research dossier and two-body/controller smoke examples only; no neural engine, male graph import or viewer existed. This implementation phase begins from that evidence. Record progress and remaining gates in `docs/STATUS.md` with current result paths and Git commits.
