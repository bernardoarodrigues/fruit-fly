# Behavior, sensory interfaces, internal physiology and reproduction

Research date: 2026-09-04. Scope: primarily adult *Drosophila melanogaster*, with a separate proposal for developmental stages. This is a broad engineering literature survey, not an exhaustive systematic review. Sixty-one screened primary studies and official resources are recorded in [sources-behavior.json](sources-behavior.json), including access limitations. Quantitative physiological parameters have **not** been fitted in this project.

**Evidence** below means a result or resource reported by the cited study, in that study's preparation. **Proposal** means a design choice for this simulation. **Hypothesis** means an untested prediction worth evaluating. These labels must remain visible in later implementation and demonstrations.

## What the simulation should aim to reproduce

A useful initial target is a pair of adult flies that can sense, move, forage, eat, drink, groom, rest, interact, court, mate and lay eggs in a small controlled arena. Each behavior should have a measurable experimental counterpart and an explicit account of which parts came from neurons, surrogate controllers, peripheral physiology or event rules. A complete-looking lifecycle is not evidence that a complete biological organism has been emulated.

The premise that a female brain connectome is unavailable is incorrect: the 2024 FlyWire publication explicitly reconstructs an adult **female** whole brain. Brain, ventral nerve cord, peripheral nerves, sensory receptor cells, reproductive organs and endocrine signaling are different scopes. A brain connectome alone does not encode all of them. [FlyWire whole-brain paper; B01](https://www.nature.com/articles/s41586-024-07558-y)

Changing activation strength alone is not a validated way to convert one sex into the other. A primary study identified sex-specific routing of visual versus olfactory inputs associated with male pursuit and female communal oviposition. That is a connectivity difference, alongside sex-specific body and reproductive physiology. [Sex-specific input routing; B61](https://pubmed.ncbi.nlm.nih.gov/33508219/)

The software should therefore keep distinct:

1. Physical body and environmental fields.
2. Peripheral sensory transduction and motor/muscle interfaces.
3. Neural dynamics, including the chosen connectome and any modeled plasticity.
4. Physiological state and endocrine/enteric feedback.
5. Reproductive/developmental state and resource accounting.
6. Experiment instrumentation, which may observe ground truth unavailable to the fly.

This separation permits substitution and ablation. For example, changing an odor receptor model should not secretly change the food's nutrient content; changing egg production should not automatically turn all female behaviors on. An implementation can be useful before all six layers are detailed, provided its substitutions are documented.

## Sensory systems: evidence and an implementable interface

| System | Evidence relevant to implementation | Proposed first representation | Validation target |
|---|---|---|---|
| Airborne odors | Receptor response profiles are combinatorial and incomplete. ORNs adapt to signal statistics. Bilateral timing can carry odor-motion information. [DoOR; B03](https://www.nature.com/articles/srep21841), [ORN dynamics; B06](https://pmc.ncbi.nlm.nih.gov/articles/PMC5524537/), [odor motion; B05](https://www.nature.com/articles/s41586-022-05423-4) | Separate chemical concentrations at left/right antennae and maxillary-palpal sensors; receptor identity, baseline, signed response, saturation, delay, adaptation and noise. | Pulse/background dose-response; bilateral timing reversal; source-finding under novel plume statistics. |
| Wind | Central wind coding combines ambiguous left/right antennal displacement signals. [Suver et al.; B09](https://pmc.ncbi.nlm.nih.gov/articles/PMC6533146/) | Local air velocity minus sensor velocity, transformed to head coordinates; antennal mechanics or a calibrated transfer function to appropriate mechanosensory channels. | Change wind direction while keeping odor fixed; unilateral antenna ablation. |
| External taste | Taste, texture and internal pharyngeal sensing contribute to different feeding steps. [Texture; B16](https://www.nature.com/articles/ncomms14192), [pharyngeal sugar; B57](https://www.nature.com/articles/ncomms7667) | Tarsal/labellar contact events with local sugar, bitter compound, salt, pH, water activity/osmolality, amino-acid/yeast proxy and texture. Internal taste only during ingestion. | Proboscis extension and actual intake measured separately; hard/soft food at matched chemistry. |
| Water taste | PPK28-dependent neurons respond to external water/hypo-osmotic solutions. [Cameron et al.; B13](https://www.nature.com/articles/nature09011) | A contact-dependent water channel based on solution properties, distinct from humidity and internal dehydration. | Water acceptance after dehydration; sugar/water mixtures; ppk28-like channel ablation. |
| Humidity | IR68a-dependent moist and IR40a-dependent dry pathways contribute to hygrotaxis, with hydration-dependent behavioral differences. [Knecht et al.; B20](https://pmc.ncbi.nlm.nih.gov/articles/PMC5495567/) | Relative humidity and its recent change at antennal sites; separate moist/dry response kernels; body water alters downstream drive. | Humidity choice with temperature controlled, in hydrated/dehydrated states. |
| Temperature | Antennal hot/cold channels and thermal projection neurons encode different signs and timescales. [Gallio et al.; B21](https://pubmed.ncbi.nlm.nih.gov/21335241/), [Frank et al.; B22](https://www.nature.com/articles/nature14284) | Air and substrate temperature fields; body temperature state; tonic and phasic warming/cooling channels. | Shallow thermal preference versus rapid temperature-step avoidance; avoid one universal threshold. |
| Vision | Eye geometry affects motion tuning. LC10 supports courtship tracking; LPLC2 supports looming selectivity. [Eye geometry; B26](https://www.nature.com/articles/s41586-025-09276-5), [LC10; B28](https://www.sciencedirect.com/science/article/pii/S0092867418307888), [LPLC2; B27](https://www.nature.com/articles/nature24626) | Compound-eye sampling with field of view, local optical axes, blur, adaptation and latency. Start with contrast/luminance channels; add spectral channels only with specified calibration. | Motion direction/tuning, object size, looming versus translation, optomotor compensation, tracking under visual occlusion. |
| Leg proprioception | Femoral chordotonal claw, hook and club populations encode different kinematic features; later connectivity work distinguishes proprioceptive feedback from vibration-related exteroception. [Mamiya et al.; B23](https://pmc.ncbi.nlm.nih.gov/articles/PMC6481666/), [circuit divergence; B24](https://pmc.ncbi.nlm.nih.gov/articles/PMC11071415/) | Joint position, directional velocity, strain/load and vibration mapped through named sensor models. Keep VNC feedback delays explicit. | Passive joint ramps, oscillations and load perturbations; gait recovery without granting global position to the neural controller. |
| Touch and grooming | Competing grooming motor modules can produce ordered sequences through suppression and reduction of sensory drive. [Seeds et al.; B35](https://elifesciences.org/articles/02951) | Body-part contact and contamination values; cleaning contacts physically remove contamination. | Selective contamination, simultaneous stimulation, interrupted cleaning and change of sensory burden. |
| Hearing and song | Courtship song is dynamic, has at least three distinguishable modes, and auditory experience changes discrimination. [Song dynamics; B29](https://www.nature.com/articles/nature13131), [three modes; B30](https://pubmed.ncbi.nlm.nih.gov/30057309/), [experience; B31](https://elifesciences.org/articles/34348) | Near-field antennal particle-velocity signal or documented feature surrogate, with distance, orientation, pulse shape and history. | Song playback and silence, species/strain-matched temporal patterns, dependence on female state. |
| Contact pheromones | ppk23-associated foreleg chemosensory function contributes to responses to the female cuticular hydrocarbon 7,11-heptacosadiene. [Lu et al.; B32](https://pmc.ncbi.nlm.nih.gov/articles/PMC3305452/) | Surface chemical composition sampled by actual contact; chemistry differs by body region/state. | Perfumed target, washed target and contact-blocked target controls; blind versus intact conditions. |
| Volatile/social pheromones | cVA promotes male aggression in the tested Or67d-dependent setting. Mating transfers cVA and 7-tricosene through different routes. [Wang and Anderson; B33](https://pubmed.ncbi.nlm.nih.gov/19966787/), [pheromone transfer; B47](https://www.nature.com/articles/ncomms12322) | A cVA emission/transfer pool and separate low-volatility cuticular pools; consequences depend on sex, history and other stimuli. | cVA with/without food and competitors; fresh versus previously mated female. |
| Flight mechanosensation | Halteres help regulate wing-steering timing and are subject to motor control. [Dickerson et al.; B25](https://www.sciencedirect.com/science/article/pii/S0960982219311157) | Initially a labeled body-rotation/wing-phase surrogate; later haltere oscillation and strain feedback coupled to wing mechanics. | Rotation disturbances, visual–mechanical cue conflicts, loss/delay of haltere feedback. |
| Noxious stimuli | Adult heat-avoidance assays have demonstrated relevant TRPA1-dependent neural requirements. This is a behavioral/circuit claim. [Neely et al.; B55](https://pmc.ncbi.nlm.nih.gov/articles/PMC3164203/) | Thresholded thermal/mechanical/chemical exposure channels with optional damage accumulation, each identified as a model. | Escape latency and dose-response, separating sensor loss from inability to move. |
| Internal sensors | Crop distension, nutrient state, osmolarity and reproductive-tract signals contribute to behavior. [Gut Piezo; B17](https://pmc.ncbi.nlm.nih.gov/articles/PMC7920550/), [hunger/thirst; B14](https://pmc.ncbi.nlm.nih.gov/articles/PMC4983267/), [mating/oviposition; B42](https://www.nature.com/articles/s41586-020-2055-9) | Physiology produces interoceptive inputs and slow modulatory variables through explicit adapters. | Vary stomach fill independently of calories; vary water independently of energy; manipulate reproductive state independently of age. |

Gravity/orientation, ocellar signals, polarized light, substrate vibration, CO2, detailed taste classes, volatile repellents, magnetic cues and additional modalities should be marked **unimplemented or uncalibrated** until their particular sensors and assays are documented. This table is a coverage map, not a claim to have found every possible sensory channel.

## Odor, food and other environmental signals

### Airborne chemistry should have spatial and temporal structure

**Evidence.** A single scalar called `food_scent` misses odor identity and temporal coding. Different adaptive processes operate in ORN transduction, spike generation and antennal-lobe transformation. A matrix of normalized receptor responses is valuable as a prior but is not an absolute physical concentration-to-current law. [Early olfactory adaptation; B07](https://pmc.ncbi.nlm.nih.gov/articles/PMC4831330/), [DoOR; B03](https://www.nature.com/articles/srep21841)

**Proposal.** Represent each airborne species `k` by a concentration field `c_k(x,t)` and source emission `q_k(x,t)`. The reference field equation is:

```text
∂c_k/∂t + u · ∇c_k = ∇ · (D_k ∇c_k) - λ_k c_k + q_k
```

Here `u` is airflow, `D_k` diffusion or an explicitly labeled effective mixing model, and `λ_k` a modeled loss term. This form assumes incompressible flow; use conservative transport if that assumption is relaxed. Boundaries specify ventilation, wall interaction and leakage. Physical units must be consistent. Begin with a measured/replayed plume or a stochastic puff model, plus a stationary smooth field for debugging. Full computational fluid dynamics is not a prerequisite for a useful assay. A smooth radial gradient should be reported as that particular artificial environment, not as a natural turbulent plume.

Use small, physically meaningful stimulus sets first: for example, one documented attractive volatile, one aversive odor, cVA, water vapor and air velocity. A fruit/yeast patch can emit a mixture, but its constituents and emission rates must be declared. A patch's depletion or fermentation state may modify emissions through a separate model. Odor diffusion does not replenish nutrients.

The fly receives only local measurements at its sensor positions. The simulation renderer and experiment logger may display an entire plume, but the neural model must not receive source coordinates, gradient vectors, true target distance or the world map. If those quantities are used to train a low-level controller, identify them as training information and record whether deployment still depends on them.

A minimal receptor model could use a signed odor response prior, saturation and history:

```text
odor_drive_r = Σ_k response_prior[r,k] × f_rk(c_k)
τ_adapt,r × da_r/dt = odor_drive_r - a_r
drive_r(t) = baseline_r + gain_r(state) × g_r(odor_drive_r, a_r)
```

This is a **phenomenological proposal**, not an equation inferred directly from DoOR. Fit `f`, `g`, delays and gain against chosen receptor recordings. Do not treat a missing DoOR value as zero response, merge incompatible units, assume mixture responses are linear, or impose Poisson variability without identifying that assumption. For neurons inhibited by an odor, preserve reductions from baseline; clamping every odor input to positive excitation erases information.

Both antennae need distinct samples and timestamps. Sensor separation, body pose, plume mesh interpolation and physics time step jointly determine whether bilateral timing is actually resolvable. An environment that gives both sensors identical samples cannot test odor-motion computation. Conversely, different sampled values caused solely by a coarse mesh can create fictitious direction cues.

### Navigation should include competing explanations

**Evidence.** Bilateral odor-motion sensing improved navigation of complex plumes in freely walking preparations. A newer, open-access July 2026 study found edge tracking supported by directional memory in a head-fixed virtual corridor: FC2 neurons represented the direction back to the boundary and EPG inhibition impaired effective returns. These studies use different stimulus geometries and preparations; one does not make the other obsolete. [Kadakia et al.; B05](https://www.nature.com/articles/s41586-022-05423-4), [Siliciano et al.; B10](https://www.nature.com/articles/s41586-026-10827-7)

**Proposal.** Maintain three comparison controllers: (a) simple local concentration/turning, (b) odor-event and wind-driven navigation, and (c) connectome-constrained heading/goal memory. Add the bilateral odor-motion component as an independently ablatable feature. PFL-based heading-to-steering transformations offer experimentally grounded constraints on the third option. [Heading-to-steering circuit; B11](https://www.nature.com/articles/s41586-024-07039-2)

Discriminating virtual assays should include crossed odor/wind directions, interruption of odor, moving plume edges, removal of an entire corridor after experience, and synchronized versus offset antennal stimulation. Report success, path efficiency, turn distributions and trajectories after loss of the plume. Tuning solely to arrival at food will not establish which mechanism caused navigation.

### Taste is a contact and ingestion process

**Evidence.** External taste acceptance and continued ingestion are distinguishable. Internal pharyngeal sensing contributes to sustained sugar consumption; texture can alter selection; acidic and alkaline chemistry add dimensions beyond sweetness. [Pharyngeal taste; B57](https://www.nature.com/articles/ncomms7667), [texture; B16](https://www.nature.com/articles/ncomms14192), [acid; B58](https://www.nature.com/articles/ncomms3042), [alkaline taste; B56](https://www.nature.com/articles/s42255-023-00765-3)

**Proposal.** A food patch stores geometry, edible volume, carbohydrate, amino-acid/protein proxy, water, salt, pH, aversive compounds, stiffness and viscosity. Contact triggers taste, proboscis motor output permits a feeding configuration, and pumping creates actual transfer from patch to crop. The feeding rate can initially be a calibrated rule gated by mouth contact, mouth state and the relevant motor signal. Label the rule explicitly if detailed fluid uptake and cibarial-pump mechanics are absent.

Never give energy merely for standing near food or for smelling it. A normal sensory response can coexist with failed consumption, and a successful feeding event must decrease the patch's remaining resource. Proboscis extension alone is an insufficient feeding endpoint. The 2024 computational brain model's selected taste and grooming validations are a useful starting point for neural response comparisons, not proof of digestion or a complete behavioral repertoire. [Shiu et al.; B12](https://www.nature.com/articles/s41586-024-07763-9)

## Internal physiology, motivation and behavioral time

### Minimum useful state

**Proposal.** Track an explicit per-fly record like this; initial dimensionless values are allowed if clearly labeled and never presented as measured concentrations:

```text
age, developmental_stage, sex_model, body_size
crop_volume, crop_composition, gut_transit_state
carbohydrate_reserve, amino_acid_or_protein_reserve, water_reserve
osmolarity_proxy, body_temperature
sleep_pressure, circadian_phase, arousal_state
reproductive_maturity, reproductive_resources, mating_history
female: mature_oocytes, ovulation_state, stored_sperm_by_donor,
        sperm_viability, free_SP, sperm_bound_SP, coital_sensory_trace
male: sperm_reserve, seminal_product_reserves, refractory_state
learning_state, sensory_adaptation_state
contamination_by_body_part, optional_damage_state
```

Do not conflate `sex_model`, current mating receptivity, genotype, apparent morphology and connectome specimen sex. Those are separate provenance-bearing fields. A setting called `female=true` should not silently swap unknown wiring or claim that sex-specific physiology was reconstructed.

**Evidence.** Starvation affects early olfactory gain through specific sNPF/insulin-linked pathways. Energy and water needs can act antagonistically through shared interoceptive neurons. Crop distension supplies a rapid satiety signal; nutrient balancing also depends on protein deprivation and mating. [Root et al.; B08](https://pubmed.ncbi.nlm.nih.gov/21458672/), [Jourjine et al.; B14](https://pmc.ncbi.nlm.nih.gov/articles/PMC4983267/), [gut distension; B17](https://pmc.ncbi.nlm.nih.gov/articles/PMC7920550/), [nutrient choice; B18](https://pubmed.ncbi.nlm.nih.gov/20471268/)

The engineering implication is that **hunger, thirst and fullness cannot be one variable**. A water-filled crop can be mechanically full while calorie-deficient. A protein-deprived animal can have ample carbohydrate. A mated female can change protein intake through signals separable from the energetic demands of egg production. [Reproductive nutrient demand; B19](https://pmc.ncbi.nlm.nih.gov/articles/PMC5166518/)

Water seeking also deserves a separate endpoint from drinking: thirst-interneuron studies provide circuit and behavioral evidence for motivated seeking rather than only a taste reflex. [Landayan et al.; B15](https://pmc.ncbi.nlm.nih.gov/articles/PMC8139827/)

### Resource accounting

**Proposal.** Start with conservation-based compartments, not a detailed metabolic network:

```text
d(crop_volume)/dt = ingestion - emptying
d(energy_reserve)/dt = assimilated_energy - basal_cost - movement_cost - reproduction_cost
d(protein_reserve)/dt = assimilated_protein - maintenance_cost - gamete_cost
d(water_reserve)/dt = absorbed_water - evaporative_loss - excretion_loss
```

Every term needs units, a range and a provenance tag (`measured`, `literature range`, `fitted`, `assumed`). Allow substrate temperature, humidity, airflow and body area to affect the chosen evaporative-loss approximation. A reversible action-selection baseline can respond to deficits, but do not use that baseline's success as evidence that the connectome generated its decisions.

More detailed endocrine models can later distinguish insulin-like peptides, AKH, sNPF/NPF, DH44/Hugin, octopamine, serotonin, juvenile hormone and ecdysteroids. The presence of a known molecule or receptor transcript is insufficient to specify its concentration, release dynamics, targets or causal effect in a particular simulation. Use the Fly Cell Atlas to identify relevant tissues and expression candidates, not as a ready-made set of physiological rate constants. [Fly Cell Atlas; B50](https://pmc.ncbi.nlm.nih.gov/articles/PMC8944923/)

### Sleep, circadian phase and memory

**Evidence.** Fly sleep was established using behavioral criteria including reversible rest. Homeostatic rebound depends on circadian circuitry and R5-related signals. Recent work implicates neuron–glia dynamics in rest/sleep/feeding, reinforcing that a chemical-synapse graph omits relevant regulation. Five minutes of immobility is a common experimental scoring convention, not a complete physiological definition or an instruction to freeze the body on a timer. [Hendricks et al.; B36](https://pubmed.ncbi.nlm.nih.gov/10707978/), [circadian homeostat; B37](https://pmc.ncbi.nlm.nih.gov/articles/PMC9270026/), [neuron–glia dynamics; B38](https://www.nature.com/articles/s41593-025-01942-1)

**Proposal.** Separate circadian phase, accumulating sleep pressure, an arousal response and measured immobility. Validate activity profiles across light/dark cycles, free-running conditions and temporary deprivation. Probe arousal thresholds rather than scoring a stuck or energy-depleted fly as asleep. A simple oscillator and homeostatic accumulator are acceptable provisional models; they do not reconstruct the full clock-gene network.

**Evidence.** Dopamine's effect is cell- and circuit-specific: PAM neurons can convey sugar reinforcement, and mushroom-body output coding is shaped by plasticity. Learned responses can be revised through reactivation/extinction-related processes. [Sugar reinforcement; B39](https://www.nature.com/articles/nature11304), [MBON plasticity; B40](https://www.nature.com/articles/nature15396), [memory re-evaluation; B41](https://www.nature.com/articles/nature21716)

**Proposal.** Add learning only through declared, compartment-specific plasticity rules or explicit surrogate memory modules. Preserve training/test separation, per-fly learning state and independent random seeds. Validate paired versus unpaired odor–reward conditioning, retention, satiation dependence and reversal/extinction. Global Hebbian updates or a universal `dopamine = reward` signal should not be called a reconstruction of fly learning.

Long-term physiology requires a simulation clock distinct from render rate and wall-clock speed. Accelerating simulated time is acceptable; arbitrarily shrinking just egg maturation or sleep pressure while leaving sensory, neural and motor time unchanged changes the biological regime. If event scheduling skips inactive periods, validate that it preserves the relevant coupled dynamics. Report both simulated and wall-clock time.

## Male–female behavior and reproductive bookkeeping

### The pair must interact through sensing

**Evidence.** Male courtship uses visual tracking and wing choice, chemical contact, odor and dynamic song. The literature distinguishes at least two pulse modes in addition to sine song. Female sensory responses and decisions are state- and history-dependent. [Directed courtship; B28](https://www.sciencedirect.com/science/article/pii/S0092867418307888), [song modes; B30](https://pubmed.ncbi.nlm.nih.gov/30057309/), [auditory experience; B31](https://elifesciences.org/articles/34348)

**Proposal.** Give each fly its own sensory stream, neural/physiological state and controller. The male should encounter the other body visually and chemically, orient, follow, tap, extend the appropriate wing, generate song, approach the abdomen and attempt mounting. These are observable motifs, not a mandatory uninterruptible script. The female can continue moving, slow, turn, reject or permit a compatible mating posture according to her own circuit output/state model.

A useful baseline can be a stochastic state machine with loops and interruptions; the intended neural implementation should replace its decisions one pathway at a time. A deterministic `near_male + near_female → mate` rule demonstrates proximity-based animation only. Likewise, passing a hidden `target_sex` or `ready_to_mate` variable directly to the partner bypasses the sensory questions the project is meant to investigate.

First implement song as a calibrated acoustic feature generator driven by the modeled wing/song motor output, then upgrade biomechanics if needed. Store mode, pulse waveform, amplitude, pulse timing, bout timing and left/right wing. A near-field transfer function should be based on particle velocity and orientation; treating all sound as a generic far-field pressure signal with arbitrary inverse-square attenuation risks the wrong sensory stimulus. If only extracted song features enter the receiver, mark this as an auditory-processing surrogate.

### Physical and physiological events are different

**Evidence.** Copulation duration and persistence are regulated and change over the bout; they are not equivalent to a fixed amount of sperm transfer. Coital mechanosensory inputs can affect subsequent female receptivity independently of ejaculate-derived signaling. [Crickmore and Vosshall; B46](https://pmc.ncbi.nlm.nih.gov/articles/PMC4048588/), [Shao et al.; B43](https://pubmed.ncbi.nlm.nih.gov/31072787/)

**Proposal.** Model these as separate event channels:

1. Courtship acceptance/rejection is an observable outcome of the two interacting models.
2. Mounting/contact requires compatible poses, contact locations and motor state.
3. Copulation begins only once the modeled coupling criteria hold; maintain a physically constrained pose rather than teleporting the flies.
4. Sperm and seminal products transfer through declared schedules conditional on sustained coupling. Male stores decrease. Interrupted bouts can have different outcomes.
5. Female reproductive-tract mechanosensation records a coital signal separately from sperm and sex peptide.
6. Storage, ejection, fertilization and egg laying are distinct later events with their own resource effects.

Detailed genital mechanics, ejaculate fluid dynamics and reproductive-tract muscle contractions can initially be surrogates. Their use must be named in the run manifest. A renderer can show anatomically plausible copulation without implying that those mechanics emerged from a reconstructed motor circuit.

### Female postmating state cannot be a single permanent switch

**Evidence.** Sperm-bound sex peptide can be gradually released, extending postmating effects. Reproductive-tract secretory cells matter for sperm storage. Female attractiveness also changes after transfer and removal of male pheromones. [Sperm-bound SP; B44](https://pubmed.ncbi.nlm.nih.gov/15694303/), [storage physiology; B45](https://journals.plos.org/plosbiology/article?id=10.1371%2Fjournal.pbio.1001192), [pheromone removal; B47](https://www.nature.com/articles/ncomms12322)

**Proposal.** Track at least free SP, sperm-bound SP, sperm count/viability, coital sensory history and available mature oocytes. Represent the seminal receptacle and paired spermathecae as explicit storage pools when testing storage-specific hypotheses; otherwise document a single pooled approximation. Sperm can be transferred without full storage, stored without immediate fertilization, and depleted or lost. SP can change behavior without being a sperm count. Attraction of future males need not follow the same time course as female receptivity.

A minimal model can use bounded pools and transfer/decay rates, but those rates are assumptions until fitted. If there is only one male, retain donor identity in sperm records so that later multi-male experiments do not require replacing the data model. Do not impose a universal “last male wins” paternity rule. Sperm competition and differential storage require additional evidence and validation.

### Oviposition has a strong candidate neural entry point

**Evidence.** A mapped circuit links mating status to egg-laying output: reproductive sensory/ascending input influences pC1 and inhibitory/excitatory oviposition pathways that converge on female-specific oviDNs. The study also distinguishes mating-status and substrate-related inputs. Activating an egg-laying pathway is therefore separable from evaluating a site or producing a viable egg. [Wang et al.; B42](https://www.nature.com/articles/s41586-020-2055-9)

**Proposal.** Use the named circuit as a prioritized mapping target, checking each cell type against the selected dataset rather than assuming identifiers transfer between connectomes. Couple oviDN or surrogate output to a sequence involving substrate evaluation, abdomen/ovipositor positioning and egg deposition. Require a mature oocyte. Fertilization additionally requires viable stored sperm and a modeled release event. An unfertilized egg remains a valid possible output, not an automatic failure of the egg-laying system.

**Evidence.** Feeding preference and egg-laying preference cannot simply share a scalar reward. In controlled sucrose-versus-plain assays, females can reject sucrose for oviposition despite accepting it in other contexts. [Yang et al.; B48](https://pubmed.ncbi.nlm.nih.gov/18356529/), [context-dependent sucrose rejection; B59](https://pmc.ncbi.nlm.nih.gov/articles/PMC4308591/)

**Proposal.** The oviposition surface should include stiffness, water content, texture, chemistry and accessibility. Begin with matched plain/sugar agar-like patches and a yeast-rich patch. Log patch visits and sampling before deposition. Vary one factor at a time, then test interactions and patch arrangement. A universal “lay at maximum food scent” policy is an unvalidated simplification.

### Reproduction is not equivalent to a generative developmental model

**Evidence.** Embryonic timing responds systematically to temperature, and development contains many separately observable milestones. This does not justify taking a neural time step and declaring a new adult every fixed number of frames. [Kuntz and Eisen; B49](https://journals.plos.org/plosgenetics/article?id=10.1371%2Fjournal.pgen.1004293)

**Proposal.** Add a population/lifecycle layer only after adult behavior works:

```text
oocyte → laid egg {fertilized or not} → embryo → larva L1 → L2 → L3
       → pupa → newly eclosed adult → mature adult
```

Each transition has age/temperature/nutrition conditions, duration distributions, mortality/survival accounting and individual identity. Larvae require a separate body and sensory/controller model. Metamorphosis entails a substantially different body and nervous system; shrinking an adult or switching mesh scale is not a larval model. A new adult initialized from a sex-specific template and sampled parameters is a **population-model birth**, not digitally reconstructed embryogenesis, synaptogenesis or inherited autobiographical memory.

For the first visible prototype, show eggs as objects with fertility and age metadata and report developmental stages as a separate optional coarse model. Genetics, meiotic recombination, sex determination, development of the wiring diagram, parental effects, microbiome transmission and mutation-driven evolution remain additional research programs. Reusing a measured connectome for offspring is an explicit approximation.

## Other adult behaviors and competing demands

| Behavior family | Grounded requirement | Proposed testable scope |
|---|---|---|
| Walking, turning, climbing, righting and flight | Existing neuromechanical platforms provide parts of the sensorimotor substrate. [NeuroMechFly v2; B02](https://www.nature.com/articles/s41592-024-02497-y) | Start with reliable walking/turning and body contact; add terrain, climbing, righting, takeoff, stable flight and landing as separately accepted capabilities. |
| Grooming | Sensory burden and competition can organize a sequence. [Seeds et al.; B35](https://elifesciences.org/articles/02951) | Body-part contamination and actual cleaning contacts; no permanent scripted loop detached from sensory state. |
| Escape and avoidance | Looming and noxious heat have different sensory/circuit evidence. [Looming; B27](https://www.nature.com/articles/nature24626), [heat avoidance; B55](https://pmc.ncbi.nlm.nih.gov/articles/PMC3164203/) | Distinct looming, contact and thermal assays; quantify whether failed escape is sensory, neural or mechanical. |
| Aggression and social encounters | Both sexes exhibit aggression, with shared and dimorphic components, and social history influences circuitry. [Female aggression; B34](https://pmc.ncbi.nlm.nih.gov/articles/PMC7787668/), [shared/dimorphic circuit; B60](https://pmc.ncbi.nlm.nih.gov/articles/PMC7856078/) | Add same-sex pairs and resource competition after the two-sex baseline; score approach and attack motifs separately. |
| Exploration and local search | Navigation can depend on internal direction/goal representations and recent odor history. [Goal steering; B11](https://www.nature.com/articles/s41586-024-07039-2), [edge memory; B10](https://www.nature.com/articles/s41586-026-10827-7) | Landmark shifts, reward removal, plume loss and arena novelty; distinguish path-memory surrogates from neural computation. |
| Feeding, drinking, resting and courtship conflict | Different needs and histories alter sensory gain and decisions. [Hunger/thirst; B14](https://pmc.ncbi.nlm.nih.gov/articles/PMC4983267/), [nutrient balancing; B18](https://pubmed.ncbi.nlm.nih.gov/20471268/) | Factorial conditions such as hungry + thirsty, fed + courting, sleep-deprived + attractive odor; report the arbitration layer. |

**Proposal.** Use an interpretable action-selection baseline for integration tests before relying on whole-network emergence. It can combine needs, cue salience and stochasticity while enforcing physical compatibility of simultaneous actions. Log `controller_origin` for each actuator or behavioral channel. Replacing only part of that baseline with neural output should result in a mixed-control label, not an “all neurons” label.

Stateful effects should be localized where supported: a hunger-dependent sensory gain, a learning-dependent synapse or an oviposition gate are different mechanisms. Adding one global “motivation multiplier” can obscure causal questions even when the animation looks plausible.

## Public resources and how to use them

| Resource | Best use | Important boundary |
|---|---|---|
| [DoOR.data; B04](https://github.com/ropensci/DoOR.data/blob/master/DESCRIPTION) and [matrix/mapping documentation](https://github.com/ropensci/DoOR.data/blob/master/R/DoOR.data-package.R) | Receptor–odor priors, receptor/glomerulus mappings, source-study provenance. | Missing values, normalized scales, mixed assays and uncertain receptor mappings need explicit handling. Current branch metadata states CC BY-SA 4.0; freeze a commit and retain attribution. |
| [Odor-motion Dryad dataset](https://doi.org/10.5061/dryad.1ns1rn8xd) and [opto-track code](https://github.com/emonetlab/opto-track) | Naturalistic stimulus statistics, bilateral timing experiments and trajectory analysis. | Fictive optogenetic stimulus is not automatically calibrated odor concentration. |
| [Wind-encoding analysis code](https://github.com/nagellab/Suveretal2019) | Antennal/wind response processing and experiment reproduction. | Match head orientation, stimulus speed and recording preparation. |
| [FlyBase bulk release; B51](https://flybase.org/downloads/bulkdata) | Gene identifiers, genotype/phenotype associations, expression, anatomy/development ontologies. | A curated genetic association does not give an ODE parameter or prove direct synaptic causality. The observed page was FB2026_02; use named release files. |
| [Virtual Fly Brain; B52](https://pmc.ncbi.nlm.nih.gov/articles/PMC9908962/) | Harmonizing cell-type names, registered anatomy, expression and connectome queries. | Registration and type matching have uncertainty; retain specimen and dataset identifiers. |
| [FlyCircuit documentation; B53](https://www.virtualflybrain.org/docs/data/lm/flycircuit/) | Single-cell morphology and searches for corresponding anatomy. | Light-microscopy overlap is not a measured synapse. |
| [Fly Cell Atlas; B50](https://pmc.ncbi.nlm.nih.gov/articles/PMC8944923/) | Peripheral tissues, reproductive cell types and candidate peptide/receptor expression. | Transcript abundance alone does not establish protein localization, conductance, release or functional connectivity. |
| [MABe22; B54](https://proceedings.mlr.press/v202/sun23g.html) | Interacting-fly pose and behavior benchmark, useful for shared scoring pipelines. | Experimental condition, strain and optogenetic interventions matter; do not treat all clips as untreated natural behavior. |
| Study supplementary videos, source data and intervention methods | Tuning curves, pose motifs, doses, deprivation protocols and distributions. | Extract numerical parameters only after checking actual protocol, units, sex, strain and age. |

Pose estimators/behavior classifiers such as APT, FlyTracker and JAABA appear in the MABe22 methods. Use a common observation/scoring pipeline for real and rendered data where feasible, and inspect failures. A classifier assigning the same behavior label to both is only one check; compare kinematics, durations and perturbation responses too.

## Validation matrix and acceptance logic

These are **proposed experiments**, not experiments already performed in this repository. Acceptance thresholds should be preregistered from an identified dataset and empirical variation before fitting. “Looks like a fly” is not an acceptance criterion.

| Experiment | Control / intervention | Measurements | What a positive result would support |
|---|---|---|---|
| Receptor pulse replay | Concentration staircase; background shifts; novel mixture; withheld recordings | Response sign, latency, peak, adaptation, recovery, trial variation | The sensory adapter in the tested regime. |
| Odor navigation | Odor/wind crossed; bilateral timing reversed; one antenna disabled; plume changed | Encounter-triggered turns, upwind progress, source arrival, return trajectories | Specific navigation computations, after ruling out leaked map/gradient input. |
| Head/goal steering | Landmark rotation, temporary cue loss, unilateral circuit perturbation | Heading/goal population signals, turn direction and dynamics | Chosen heading-to-action transformation. |
| Taste versus ingestion | Mouth contact blocked; nutritive/non-nutritive matched taste; crop prefill | Proboscis extension, ingested amount, bout duration, crop volume | Separation of acceptance, consumption and satiety. |
| Hunger and thirst | Independent energy/water deficits; water-filled calorie-poor crop | Sugar/water choice, intake, humidity seeking | Distinct coupled homeostatic variables. |
| Protein balance | Sugar/yeast choice; virgin versus mated; egg production independently varied | Intake composition, search bias, oocyte production | Reproductive-state/nutrient coupling in the chosen model. |
| Humidity/temperature | Hold one constant while varying the other; change hydration | Occupancy, transition probabilities, response lag | Correct stimulus separation and state effects. |
| Mechanical feedback | Passive joint ramps; uneven ground; delayed/ablated proprioception | Sensor tuning, joint torques, slips, support patterns | The sensor–VNC–body loop, not higher cognition. |
| Visual feature selectivity | Expanding/contracting disk, translation, full-field motion, small target | Neural tuning, escape probability/latency, tracking error | Selected visual transformations. |
| Grooming | Region-specific contamination; simultaneous stimuli; interruption | Sequence transitions, contact accuracy, contamination removed | Feedback-driven sequencing in the implemented conditions. |
| Courtship | Muted song, incorrect timing, washed/perfumed target, visual occlusion | Courtship index with stated definition, tracking, wing choice, female speed, acceptance probability | Multisensory interaction and its component contributions. |
| Copulation and storage | Interrupted bouts; spermless/SP-null surrogate transfer; sensory-only manipulation | Transfer, storage, female state traces, remating, fertility | Distinct physical, ejaculate and coital-state mechanisms. |
| Oviposition | Matched substrates; change position/contrast; virgin/mated and sperm states | Visits, deposition site, latency, egg count, fertilized fraction | Site choice, output gating and resource bookkeeping. |
| Sleep | Light/dark versus constant condition; deprivation; graded arousal stimulus | Rest bouts, activity phase, recovery/rebound, arousal response | The modeled sleep/homeostasis regime. |
| Learning | Paired/unpaired, reversed pairing, reward removal, delayed testing | Preference, retention, generalization, state dependence | The specified plasticity/memory mechanism. |
| Aggression | Same-sex pairs; resource/no resource; isolated/group history | Approach, contact/attack motifs, duration and displacement | Context-dependent social behavior in each sex. |
| Lifecycle | Temperature/food shifts; infertility; resource shortage | Stage durations, viable offspring, cohort resources | Coarse population model, unless development is explicitly modeled. |

For every assay compare at least a no-controller or baseline control, the chosen biological model, and an ablated/shuffled alternative that preserves relevant complexity. Hold out at least one stimulus regime and perturbation from fitting. An ablation that prevents all movement is not selective evidence for food seeking or mating.

Replicate across independent initial states, seeds and plausible parameter ranges. Samples nested within one virtual animal are not independent animal replicates. Real comparisons need matched sex, strain, age, temperature, humidity, diet, deprivation duration, mating/social history, lighting, arena geometry and intervention strength. Report uncertainty and the limits of cross-assay generalization.

## Candidate insights and experiments to test them

The following are **derived hypotheses/design insights**, not newly established biological findings and not claims of priority.

1. **The interfaces may limit realism before neuron count does.** A large neural graph cannot infer chemical identity or contact timing erased by its adapter. Compare richer sensory adapters with the same neural graph, then compare graph variants with the same adapter. Measure which change improves held-out behavior and neural responses more.
2. **Odor boundary memory and bilateral odor motion should contribute differently by environment.** Train/calibrate on separate corridor and intermittent plume regimes. Test crossed wind/plume directions with each mechanism ablated. A state/geometry-dependent benefit would clarify which component is needed without assuming one universal foraging algorithm.
3. **Reproductive behavior can expose missing body-to-brain feedback.** Compare a model with only a postmating flag against one with separate coital, sperm, SP and egg-resource variables. Test interrupted, spermless and SP-altered matings. Differences in remating and oviposition are more informative than one successful mating animation.
4. **A behavior can be reproduced for the wrong reason.** A controller with source coordinates may navigate despite failed receptor dynamics; a timed copulation script may generate eggs despite absent sensory interaction. Remove privileged inputs and perturb the implicated biological pathway before attributing behavior to the connectome.
5. **Interoceptive conservation makes counterfactuals stronger.** A calorie-poor but mechanically full crop should distinguish volume-based satiety from energetic recovery. Separate protein and water pools permit qualitatively different needs at the same total “energy.” Their numerical outcomes remain model-dependent until fitted.
6. **Sex comparisons need matched computational budgets and provenance.** Compare sex-specific sensory/peripheral/reproductive models and supported circuit differences, while exposing surrogate pieces. A male/female behavioral difference induced only by hardcoded reward coefficients says little about dimorphic wiring.
7. **Grooming could be a useful test of sensor maintenance.** Add a declared contamination-induced sensory degradation model, let physically effective grooming restore it, and test whether foraging performance recovers. The specific degradation law is an engineering hypothesis until measured; do not assume it from the existence of grooming.
8. **Long-time behavior is a test of coupling, not just speed.** Accelerating physiology independently can change the frequency of hunger–courtship–sleep conflicts. Test time-step convergence and accelerated scheduling against a matched real-time reference before interpreting lifecycle behavior.

## Known incompleteness and research priorities

This survey supports a staged model with many experimentally constrained modules. It does not establish a universal model of an individual fly. Important remaining gaps include exact intrinsic electrophysiology across cell types; transmitter/receptor-specific effects and cotransmission; gap junctions; spatial neuromodulation; glial regulation; peripheral sensory counts/kinetics and innervation; detailed VNC-to-muscle mapping; muscle fatigue and energetics; enteric reflexes and digestion; tracheal respiration, circulation, excretion and water balance; immune state, microbiome, pathogen/toxin effects and aging; oogenesis/spermatogenesis; sperm competition; the endocrine control of development; and how stable or variable wiring is across individuals and conditions.

These omissions should be recorded as such, not all turned into arbitrary scalar sliders. Prioritize a missing system when it changes an intended assay or closes a required causal loop. For a two-adult arena, accurate contact taste, water/energy separation and reproductive feedback are likely to be more immediately useful than a detailed molecular model of every tissue; that is an engineering prioritization, not a biological completeness claim.

Recommended implementation order:

1. One fly: body stability, contact/proprioception, vision and odor response replay.
2. Closed-loop foraging and feeding with resource conservation, followed by thirst and texture.
3. Grooming, avoidance and validated navigation memory; sleep/circadian behavior across sufficiently long simulated time.
4. Two agents with multimodal courtship and independent female responses.
5. Separate mating, transfer, storage, postmating and oviposition models, with interruption/ablation tests.
6. Coarse egg/development/population layer, then learning, richer social contexts and physiology according to experiments.

## Access notes

No institutional login was attempted. Public abstracts, publisher text, repositories, datasets and author manuscripts were sufficient for this architectural survey. Some PMC/eLife fetches returned automated-browser challenges/403 errors; these are **not** evidence of a subscription requirement. The registry records review depth so that an indexed excerpt is not mistaken for a full methods review.

For quantitative replication, these are useful institutional-access priorities **only if their publisher or public manuscript/supplement routes remain unavailable**:

- [Odour motion sensing, Nature 2022; B05](https://www.nature.com/articles/s41586-022-05423-4): stimulus calibration and full methods. Data and code are already public.
- [LC10 directed courtship, Cell 2018; B28](https://www.sciencedirect.com/science/article/pii/S0092867418307888): visual tuning and perturbation details.
- [Coital experience circuit, Neuron 2019; B43](https://pubmed.ncbi.nlm.nih.gov/31072787/): isolated mechanosensory versus ejaculate effects.
- [Sperm-bound sex peptide, Current Biology 2005; B44](https://pubmed.ncbi.nlm.nih.gov/15694303/): release/persistence measurements and construct-specific protocols.
- [Temperature representation, Nature 2015; B22](https://www.nature.com/articles/nature14284), [LPLC2 looming, Nature 2017; B27](https://www.nature.com/articles/nature24626), and [PAM reward, Nature 2012; B39](https://www.nature.com/articles/nature11304): parameter-level replication if these modules are prioritized.

An institutional PDF is not presently a blocker to building the first scientifically labeled prototype. Read full methods and supplements before claiming quantitative reproduction of any particular paper.
