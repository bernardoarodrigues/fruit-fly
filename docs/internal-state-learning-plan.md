# Internal state, sleep, and learning: research plan

This is a research plan and an exact annotation catalogue, not an implemented sleep or learning controller. The smallest defensible extension separates four processes: a circadian clock, sleep need and arousability, compartment-specific associative plasticity, and seconds-long navigation working memory. None should be inferred merely from an inactive body or from a dopamine neuron spiking.

The accompanying [`data/internal-state-learning-mapping.json`](../data/internal-state-learning-mapping.json) contains 30 exact MaleCNS types and 239 body IDs. It deliberately covers selected experimental anchors rather than claiming a complete internal-state inventory. IDs are `bodyId`, not graph row numbers; resolve them against the loaded graph. Anatomical `somaSide` does not determine the hemisphere containing all a neuron's synapses.

## What the male annotations support

The catalogue was extracted by exact `type` equality from the imported MaleCNS v1.0 annotations, with the original annotation file's SHA-256 verified against the import manifest. Its source is the [MaleCNS v1.0 annotation table](https://storage.googleapis.com/flyem-male-cns/v1.0/connectome-data/flat-connectome/body-annotations-male-cns-v1.0-minconf-0.5.feather). These are cells of the male connectome specimen. Their behavioral roles come from separate experiments and type correspondence, often in females or mixed experimental populations.

| Clock annotation | Male cells | Interpretation permitted here |
| --- | ---: | --- |
| `DN1a` | 4 | Anterior DN1 class |
| `DN1pA`, `DN1pB` | 8, 4 | Exact named posterior DN1 subtypes |
| `l-LNv`, `s-LNv` | 8, 8 | Large and small ventrolateral clock groups |
| `5thsLNv_LNd6` | 4 | Combined label; individual identities remain unresolved |
| `LNd_b`, `LNd_c` | 4, 6 | Lateral dorsal subtypes; molecular CRY/ITP classes not inferred |
| `LPN_a`, `LPN_b` | 4, 2 | Broad LPN correspondence supported by `hemibrainType=LPN` |

The 52 cells above are a conservative named subset. Missing DN2/DN3 labels do not establish absence of those neurons. Generic descending-neuron names beginning with `DN`, and sensory `LN-DN1`/`LN-DN2`, are not clock identities.

Reinhard et al. reconstruct a substantially larger clock network in female FlyWire, with about 240 identified neurons; anatomy also supports more than 70 DN3 per hemisphere in both sexes. Chemical synapses alone miss substantial peptide communication. The paper integrates transcriptomics and receptor mapping to propose paracrine coupling and output pathways. Its clock-type nomenclature supports the broad crosswalk above, but it does not give the male specimen's receptor concentrations or electrical phase relationships. [Primary clock connectome, 2024](https://doi.org/10.1038/s41467-024-54694-0).

| Sleep/arousal anchor | Exact male type/count | Evidence boundary |
| --- | --- | --- |
| Sleep-pressure ring cells | `ER5`: 21 | Historical R2/R5 naming must be resolved through the connectome crosswalk; `ExR5` is different |
| Helicon cells | `ExR1`: 4 | Visual/movement and sleep-circuit role, not a scalar sleep switch |
| Serotonergic sleep-circuit cells | `ExR3`: 2 | Circuit anchor; receptor-dependent effects remain unresolved |
| dFB wake-associated DAN morphology | `FB5H`, `FB6H`, `FB7B`: 2 each | Male consensus is dopamine for FB5H but **unclear** for FB6H/FB7B |
| Wake activation candidates | `hDeltaF`: 8; `SMP368`: 2; `SMP531`: 2 | Activation phenotypes, not complete mechanisms |

Hulse et al. map ER5, ExR1/helicon, and ExR3 into interconnected central-complex circuits. Their light/EM comparison identifies FB5H, FB6H, and FB7B among TH-positive dFB neurons. Their R23E10 population contains multiple FB types, which does not assign the same function to every member. [Primary central-complex connectome, 2021, Figs. 48–53](https://doi.org/10.7554/eLife.66039).

Wolff et al. test identified lines in both sexes: hDeltaF, SMP368, and SMP531 activation reduces sleep measures. This is a candidate screen; arousal thresholds and deprivation recovery were not tested. hDeltaK effects disagree across driver lines, so it receives no sleep-promoting or wake-promoting sign here. Their EASI-FISH supports tyramine in `PFGs` (Tdc2 present, Tbh absent), while the male annotation has `consensus_nt=unclear`. They also provide cell-type RNA profiles and peptide/receptor evidence, a useful next source for physiological refinement. [Primary driver/transmitter study, 2025, Figs. 4, 9–12](https://doi.org/10.7554/eLife.104764).

## Sleep: distinguish measurement from mechanism

The foundational experiments establish reversible reduced responsiveness and rebound after deprivation, alongside rest/activity rhythms. These are behavioral constraints on a model. A five-minute inactivity criterion is an operational scoring convention: it cannot make a simulated fly asleep by definition. [Hendricks et al., 2000](https://doi.org/10.1016/S0896-6273(00)80877-6); [Shaw et al., 2000](https://doi.org/10.1126/science.287.5459.1834).

Recent dFB-specific work is particularly important for avoiding a false implementation. The widely used 23E10 driver also labels VNC sleep-promoting neurons. In a more specific dFB intersection, 1-Hz stimulation was insufficient, while sufficiently strong protocols increased sleep with reversibility and raised arousal threshold; video and multibeam measurements addressed grooming/feeding confounds. The same dFB population contained cholinergic, glutamatergic, and coexpressing cells rather than the previously assumed GABAergic population. Optogenetic pulse frequency is not a measured natural firing-rate setpoint. [Jones et al., PLOS Biology 2025](https://doi.org/10.1371/journal.pbio.3003014).

Proposed minimal modules, still to implement and calibrate:

1. **Behavior observer.** Record locomotion, appendage movement, posture, feeding/grooming, inactivity duration, and responses to graded stimuli. Preserve `inactive`, `sleep_candidate`, and experimentally supported `sleep_like` as distinct analysis labels. A motor command of `rest`, a stalled neural model, a fallen fly, or resource exhaustion must never count as validated sleep.
2. **Circadian process.** Track internal phase independently of wall-clock time. First reproduce a published autonomous oscillator under darkness and entrainment under light/dark cycles before adding any coupling to named neurons. Leloup–Goldbeter's PER/TIM model is a compact existing starting point, with sustained oscillations and light-dependent TIM degradation; its old parameterization is a declared model, not measured kinetics of each male neuron. [Primary computational model and accessible author PDF, 1998](https://utc.ulb.be/ARTICLES/1998_Leloup_JBR.pdf). A phase-only reduction is acceptable only if labelled phenomenological and checked against the parent oscillator. Feeding generic brightness into every clock cell is not an established pathway.
3. **Sleep homeostat.** Add a slow physiological state tied to an explicitly selected sleep-pressure mechanism. ER5 plasticity is one experimentally grounded candidate; its state must be separate from the body's energy and hydration reserves. Liu et al. report calcium/NMDA-dependent changes with prolonged waking and persistence of sleep drive over hours. Their deprivation assay uses 5 seconds of mechanical stimulation per minute for 12 or 24 hours and assesses recovery over the first 6 hours. Those are assay durations, not fitted exponential time constants. [Primary sleep-pressure study, 2016](https://doi.org/10.1016/j.cell.2016.04.013).
4. **Arousal and expression.** Couple a validated internal-state model to cellular excitability/receptors before declaring an endogenous state transition. Use graded mechanical or visual stimuli through actual sensory interfaces and measure response probability and latency. A hard actuator disable would manufacture the desired phenotype and defeat this test. Do not simulate an increased arousal threshold by hiding stimuli from all sensory neurons.

The validation sequence should include several simulated light/dark cycles, free running in darkness, deprivation/recovery compared at matched circadian phases, and graded arousal probes with prompt reversibility. Analyze individual trajectories across multiple seeds, report distributions, and keep feeding availability, temperature, age, sex, and genotype explicit. Van Alphen et al. observed changing depth within a bout, including deeper periods near 15 and 30 minutes; a single fixed five-minute latch cannot reproduce that observation. [Primary sleep-depth study, 2013](https://doi.org/10.1523/JNEUROSCI.0061-13.2013).

## Associative learning: select a compartment before a rule

The crosswalk below was checked against Li et al.'s Figure 6—figure supplement 1 and the current male annotations. It is a small set of anchors, not every DAN/MBON in each compartment. In particular, PPL102 and atypical γ1 MBONs are not included in the first anchor; PPL105 also innervates α′2. PAM07/PAM08 denote broad γ4-associated types, and the paper describes a finer PAM08-md subtype in γ3, so an individual-neuron ROI/subtype audit is required before treating every PAM08 as equivalent. [Primary mushroom-body connectome, 2020/2021](https://doi.org/10.7554/eLife.62576).

| Compartment anchor | DAN male type/count | MBON male type/count | Intended comparison |
| --- | --- | --- | --- |
| γ1pedc | `PPL101`: 2 | `MBON11`: 2, GABA consensus | Fast odor-specific aversive plasticity |
| γ4 | `PAM07`: 14; `PAM08`: 50 | `MBON05`: 2, glutamate consensus | Temporal-order-dependent depression/potentiation |
| α1 | `PAM11`: 15 | `MBON07`: 4, glutamate consensus | Appetitive consolidation feedback |
| α2 | `PPL105`: 2 | `MBON18`: 2, acetylcholine consensus | Different training requirements |

Hige et al. induced odor-specific depression at KC→MBON-γ1pedc with brief odor/DAN pairing; suppression of postsynaptic spikes did not prevent induction. A longer, one-minute odor pairing with 120 stimulation pulses was needed in their α2 comparison. This argues against applying one generic postsynaptic spike-timing rule to all mushroom-body edges. [Primary physiological learning study, 2015](https://doi.org/10.1016/j.neuron.2015.11.003).

Handler et al. show that relative timing can reverse the plasticity and behavioral association. DopR1/cAMP and DopR2/Gαq/calcium pathways have different roles; **DopR2 here is not the D2-family receptor Dop2R**. Their forward protocol used a two-second odor with a one-second DAN stimulus during its final second; in backward pairing the DAN stimulus began two seconds before odor onset. Subsecond shifts matter. A dopamine scalar with a fixed reward sign loses this mechanism. [Primary timing/receptor study, 2019](https://doi.org/10.1016/j.cell.2019.05.040).

Minimum implementation sequence:

1. Establish distinct odor-evoked KC ensembles through the sensory network. If the current odor interface represents only one generic intensity, it cannot yet support a meaningful two-odor conditioning assay.
2. Preserve a frozen anatomical weight matrix and add a separately saved plastic efficacy factor only on the selected existing KC→MBON edges. Use exact neuron identities and compartment/ROI evidence, not a broad neuron-name prefix or all mushroom-body connections. No new anatomical edges should be invented by learning.
3. Maintain separate KC eligibility and local dopamine/receptor traces. Fit their temporal kernels to a chosen published protocol before specifying rate constants. A preliminary bounded depression-only γ1 model can be called a restricted physiological approximation; it must not claim the bidirectional γ4 mechanism.
4. Keep electrically mediated synaptic effects separate from dopamine modulation. Do not double count a single DAN spike as an arbitrary excitatory current plus a universal plasticity reward. Reward delivery must arise from measured taste/ingestion or a declared experimental DAN intervention, never from distance to a hidden food coordinate.
5. Compare paired, unpaired, odor-only, DAN-only, and reversed-order training; counterbalance odor identities and test without reinforcement. Preserve baseline attraction, locomotor capacity, sensory discriminability, and memory state across reset/checkpoint boundaries. A change in walking speed alone is not associative memory.

Aso and Rubin's compartment comparison used 4–10-day-old females. Their γ1pedc memory was retained after ten minutes but largely decayed by 24 hours under the tested protocol, with different requirements and retention in other compartments. Those observations constrain assay design, not a universal fly-memory decay constant, and transfer to the male requires explicit validation. [Primary learning-rule comparison, 2016](https://doi.org/10.7554/eLife.16135).

Long-term α1 learning should be a later milestone. Ichinose et al. found that disrupting its feedback components for the first hour after conditioning impaired 24-hour memory, whereas a similar intervention 22 hours later did not. PAM-α1 NMDA-receptor perturbation affected long-term memory, supporting receptor-specific glutamatergic feedback. This is an explicit counterexample to treating all glutamatergic outputs as inhibitory. A persistent consolidation variable or recurrent activity would need a tested mechanism; simply extending a memory decay constant is insufficient. [Primary consolidation study, 2015](https://doi.org/10.7554/eLife.10719).

## Navigation working memory is a separate target

Kathman et al.'s July 2026 final paper measures odor-triggered activity persisting after odor loss in VT062617-labelled fan-shaped-body neurons, with an exponential persistence time of **5.59 ± 0.55 seconds**. Its plume simulation performs best around **6.4 seconds**, a result specific to the tested plume and model. A specific hΔK split line reproduces impaired post-odor upwind persistence under silencing. Imaging used 7–12-day-old females starved for about 24 hours; freely walking experiments used younger females. The measured persistence is therefore not a validated male time constant or a receptor decay constant. [Primary final paper, 25 July 2026](https://doi.org/10.1038/s41467-026-75945-2).

The male catalogue contains **31 `hDeltaK`** neurons and **18 `PFGs`** neurons. The 2024 addendum to the earlier navigation paper states that VT062617 additionally or predominantly labels hΔK, so its original functional effects cannot be assigned unqualified to hΔC. [Primary addendum](https://doi.org/10.1038/s41467-024-46225-8). The follow-up Lanz et al. preprint tests hΔK/PFG recurrence and proposes slow recurrent excitation with fast inhibition and disinhibitory gating. Its current status in the sources consulted is a preprint. [Primary mechanistic preprint, 2025](https://doi.org/10.1101/2025.10.07.681003).

A defensible later test would compare persistent neural activity and heading stability after odor loss, with intact versus interrupted recurrence. Such a model stores an internally estimated direction, not the arena's actual food coordinates. The current generic transmitter model cannot implement the proposed PFG physiology merely by turning unclear outgoing weights positive.

## Concrete next work and remaining evidence

The highest-value next deliverable is an assay harness and state recorder, followed by a compartment-restricted learning experiment. Full sleep claims should wait for long-duration state dynamics and arousal/rebound validation. Simulating hours by silently accelerating selected neural or metabolic constants changes the scientific model; use explicit, validated reductions and separate biological time from playback speed.

Before implementing cellular sleep or consolidation dynamics, obtain or extract receptor/transmitter profiles for the exact selected types, the compartment locations of plastic synapses, electrical response curves, and source-data time courses. The accessible Wolff cell-type profiles (GEO **GSE271123**) are a concrete starting point. No institutional login is presently needed for the core plan: primary full text, author manuscripts, or open PDFs were available. Source papers remain external references; locally downloaded research copies live under ignored `tmp/internal-state/`.

Derived engineering insight, not new biological discovery: a connectome-plus-body system can fail these tasks despite containing all named neurons because three distinct missing mechanisms have different time scales—receptor-dependent synaptic modulation, persistent circuit state, and autonomous slow physiology. Adding a single generic “motivation” number would conceal these separate deficiencies and make validation ambiguous.
