# Direct APL electrophysiology: source and acquisition

Source review and download launch, 2026-09-05 UTC. A newly located 2026 primary study provides **direct whole-cell APL recordings and a public raw electrophysiology archive**. This changes the next action: inspect these electrical recordings before adding more free parameters to the unsuccessful dye-driven reporter mapping. Acquisition is in progress; no raw electrophysiological outcomes have yet been computed in this project.

## Primary study and access

[Chen et al., *Sleep facilitates pattern separation through SK channel-mediated sparse coding*](https://doi.org/10.1016/j.cub.2026.02.028), Current Biology 36, 1633–1643.e6, published online March 16, 2026. The publisher/PMC record is PMID 41844155, PMCID PMC13075853. The [author institution's public PDF](https://eprints.whiterose.ac.uk/id/eprint/239294/1/1-s2.0-S0960982226002058-main.pdf) is retained as `data/raw/apl-sk-electrophysiology/chen-2026.pdf`, 3,471,600 bytes, SHA-256 `5320c8b48d2dfc0a0cee1d1e75d2efe3c30855e2f8ac968cfe014fa5b2b02505`. This deposited PDF carries article-in-press pagination. The relevant methods, text and complete Fig. 4 were inspected; Fig. 4 was rendered and visually checked.

PMC's web open presented a browser challenge, and the Europe PMC full-text XML endpoint returned HTTP 404. Neither was bypassed. The institutional PDF and public dataset were accessible without login.

The authors deposit raw imaging, electrophysiology and behavior at [Zenodo record 18644411](https://zenodo.org/records/18644411), version 1, February 14, 2026. The metadata assigns CC-BY-4.0 to the dataset. This is distinct from the article's CC-BY-NC-ND license. Retained metadata SHA-256: `f62d1a1c837f70578356713ecdc3aeab1d84ba52e42810c7888824851cc236b1`.

Only the electrophysiology ZIP is being downloaded:

| File | Published size | Published MD5 | Current scope |
|---|---:|---|---|
| Ephys_sparse coding.zip | 2,287,477,173 bytes | `c6d63ac25c504db4fc3ee45578d63169` | Full download in progress |
| 2P data_sparse coding_Fig2.zip | 30,702,541,661 bytes | `61c15375cab37f06cfedf629418e8242` | Metadata only |
| idoc_sparse coding.zip | 193,776,424 bytes | `17dd20b9e5e0d4d248b6609518a9a8b5` | Metadata only |

The [acquisition script](../scripts/acquire_apl_sk_ephys.py) streams to a new `.part` file, computes MD5 and SHA-256, and only renames the archive after validating size and published MD5. It refuses to overwrite either a final or partial download. A completion receipt will be written to `validation/apl-sk-ephys-acquisition.json`; that receipt is not present at this source-review stage. The [launch receipt](../validation/apl-sk-ephys-launch.json) pins the script, metadata and observed live process. Available disk space was approximately 236 GiB, so acquisition requires no additional compute or storage.

The existing completion heartbeat has been reused for this acquisition. It checks the matching live producer and completion receipt quietly, pauses before complete-file inventory, and retains any failure/partial file without automatic restart. It does not analyze recordings as bytes arrive. The completed γ-KC neural batch remains closed.

## Electrical and experimental constraints

**All experiments in this study use mated females.** These recordings are useful independent electrical constraints, but applying them to the native male graph requires an explicit sex/preparation transfer assumption. They do not change the one-male project scope or provide male-specific measurements.

The paper reports non-spiking, graded APL somatic responses, occasional initial bump-like responses at strong depolarization, and input resistance around **120 MΩ**. Its authors describe these as the first whole-cell APL recordings. Do not treat the older locust giant-GABAergic-neuron analogy or earlier APL calcium work as equivalent direct Drosophila electrical measurements. The approximate resistance in the text is not yet a per-cell parameter extracted from raw data here.

| Measurement detail | Source protocol | Consequence for reuse |
|---|---|---|
| Preparation | Dissected ex vivo brain; APL soma targeted using GFP | Preserve preparation and compartment; do not equate soma with local release sites |
| Recording | MultiClamp 700B, 3 kHz low-pass, 10 kHz sampling | Raw voltage can constrain subsecond dynamics more directly than the ~5 Hz reporter figures |
| Pipettes | APL 6–9 MΩ; internal 140 mM potassium gluconate, 10 HEPES, 1 EGTA, 4 MgATP, 0.5 Na₃GTP, 1 KCl, 13 biocytin | Retain access/solution metadata; EGTA and dialysis matter for calcium-dependent responses |
| Resting potential | Measured immediately after break-in without holding current or compensation | Do not infer resting potential from later held sweeps |
| Later current clamp | Pipette-capacitance neutralization and bridge balance; held around −60 ± 5 mV by current injection; liquid-junction correction reported | Identify command offsets and correction state in raw files before absolute-voltage fitting |
| APL passive step | −50 pA for 500 ms | Candidate source for per-cell passive deflection and membrane-response estimates |
| APL depolarization series | 500 ms steps in 50 pA increments, starting −100 pA; separated from the constant hyperpolarizing step by 1 s | Reconstruct actual recorded commands; do not substitute the KC protocol |
| AHP/bump assay | Text describes response to 1 nA current injection | Match charge/offset windows from raw protocol |
| SK pharmacology | 10 µM NS8593; fly SK is reported insensitive to apamin | Preserve paired before/after grouping and drug condition |

There is a concrete protocol reconciliation issue: **Fig. 4H visually labels a +2 nA command**, whereas the general APL methods and other panels discuss 1 nA. The SK-RNAi panel must not be pooled with other groups under an assumed common stimulus. Resolve this from raw commands and file metadata before comparing amplitudes.

The principal conditions are normal sleep, 12-hour sleep deprivation and recovery sleep. The paper reports stronger and longer AHP after deprivation, reduced by recovery, pharmacological SK modulation and APL-targeted SK RNAi. Fig. 4D reports AHP-amplitude cohorts of 20/20/11 for normal/deprived/recovery. Fig. 4E's decay comparison uses 17/18/11. These are caption counts, not an established raw-file join.

The authors specifically avoid a universal exponential decay fit across groups: low-amplitude AHP in many normal-sleep cells makes such fits unreliable. Cross-condition kinetics use the interval for AHP recovery from **70% to 30% of peak magnitude**. That interval is not itself an exponential time constant. It should remain the primary comparable observation rather than forcing an exponential onto weak responses.

## Implication for the model

This source supports a non-spiking APL candidate with substantial leak and a state-dependent afterhyperpolarizing mechanism. A generic spike refractory counter cannot express that graded history dependence. Increasing an inhibitory potassium conductance *inside APL* can reduce APL feedback onto KCs; global inhibition gains cannot represent that distinction reliably.

The raw data could provide separate passive-step and post-depolarization constraints, with SK perturbations testing the latter. It does not automatically identify local KC→APL synaptic conductance, dendritic calcium dynamics, GABA release, or receptor-specific KC inhibition. A soma fit must still be reconciled with the existing native male spatial geometry and attachment sensitivity.

After complete checksum verification, inventory the full ZIP before fitting. Identify recordings, cell/animal IDs, genotypes, sleep states, pharmacology pairing, channel units, actual commands and exclusion records. Then fix complete calibration/evaluation groups and define passive, bump and AHP measurements. Preserve low-signal exclusions and distinguish stimulus protocols. No individual-file parameter tuning or selection based on attractive traces is authorized by this source step.

A separate relevant lead is [Bergmann et al. 2026, *Conflicting adaptations in an inhibitory feedback circuit*](https://doi.org/10.1113/JP290394). Its abstract describes dual-color KC/APL calcium measurements after prolonged KC overactivation and reduced APL sensitivity. This lead is recorded, not yet fully audited or fitted. Direct electrical data take priority over another unconstrained dye-response fit.

No physiological parameter was promoted or neural experiment launched. H1 remains experimental, Eon embodied integration remains cancelled, and the complete single-male milestones remain active.
