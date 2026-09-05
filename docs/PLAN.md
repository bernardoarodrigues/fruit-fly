# Active implementation plan: one male fly

User scope update: 2026-09-04. Focus on **one male Drosophila** to accelerate testing; a second fly and paired reproduction are deferred. The user wants a solid simulation through the relevant planned milestones, a way to watch it, and a GitHub repository updated during development. Additional compute can be supplied when measurements justify it.

This is the active implementation plan. The research roadmap records the broader two-animal program and remains the source of scientific validation requirements. This scope update does not turn a body animation or a small substitute graph into completion.

## Current scientific priority: 2026-09-05 UTC

The user's latest direction is a [staged causal navigation ladder](navigation-ladder-plan.md), with local physiological calibration before broader navigation claims. The [first stage readout](navigation-ladder-readouts.md) is complete and independently reviewed: it reuses all 60 inhibitory-panel trials across 34 cohorts, reveals strong immediate PN recruitment and persistent activity in selected MBON/DN populations, and keeps the narrow walking-output failure explicit. The [exact-spike timing diagnostic](navigation-ladder-timing.md), [VM2 depression-panel extraction](orn-pn-depression-digitization.md) and [conditional fixed-reference comparison](orn-pn-depression-comparison.md) are also complete. The subsequent [local calibration](orn-pn-depression-calibration.md) fits only the designated 20 Hz curve, retains 15/50 Hz for evaluation, and finds a conditional recovery time near 104 s after a separate ceiling check. Cross-frequency transfer remains poor and the starting recovery state is not established by the source. No parameter is promoted. Next, audit the actual presynaptic inputs sustaining MBON12–14 activity in the saved H1 trials before defining a bounded causal intervention. Further local fitting needs compatible amplitude/history constraints. No new whole-network E/I gain sweep is planned; the suggested synapse-handling decomposition is superseded.

The user explicitly cancelled the proposed embodied Eon integration benchmark. Its existing bounded neural results were independently reviewed, committed and pushed at `ab2bd63`. The [inhibitory C0/C1/H0/H1 factorial](inhibitory-factorial.md) and subsequent recurrent panel are complete. No arm is selected. Do not continue copying Eon's stimulation or fitting motor gains as the main path to realism. No embodied P9/taste benchmark is required.

H1 must not be selected because its voltage plot looks better. Before promotion it must satisfy numerical bound and accuracy checks, relevant physiological amplitude/timing comparisons, meaningful stimulus contrasts, seed robustness, and improved recurrent full-network behavior without uncontrolled persistence. Conditional fixed-input replay cannot satisfy the recurrent gate. Record failed and unresolved criteria explicitly; see [operational promotion gates](inhibitory-promotion-gates.md).

The [recurrent implementation/performance check](inhibitory-recurrent-performance.md) completes all five 50 ms runs with 280 checks and 499 independent saved-data checks. C0 matches the original full endpoint state exactly; altered arms generate their own distinct recurrent histories. The [matched four-thread check](inhibitory-recurrent-parallel-performance.md) passes 1,242 checks with exact retained-array parity and lower measured H integration time. The [three-seed stimulus/withdrawal panel](inhibitory-recurrent-panel-results.md) completed all 60 trials and its independent batch review; it was committed and pushed at `94826f2`. Do not restart it. Its completion heartbeat is paused. Neither numerical bounds nor retained local contrasts overcome the persistent-activity and physiological-calibration failures, so the recurrent result does not promote H1.

Still-air odor ON/OFF behavior, odor-plus-wind orientation and fed/hungry state effects are separate assays. Future neural batches must have a fixed complete condition set and be analyzed together after the quiet completion trigger, as requested by the user. Source-rate declarations, hDelta identities, circular coordinates and decoder assumptions must remain visible in their records.

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
