# γ-KC reporter data and author model audit

Completed 2026-09-05 UTC. This is a read-only data/code audit after the closed [γ-KC recurrent batch](../docs/kc-gamma-intervention-results.md), with no new fit, neural simulation, or runtime change.

The public author workbook supplies a useful WT/KD calcium-summary comparison. It does **not** identify a male KC electrical synapse, graded APL release law, or conversion from calcium fluorescence to spike rate. The author model is a possible local reporter-level reference, not a ready replacement for the CNS engine.

## Acquisition and provenance

The [author repository](https://github.com/nawrotlab/KC_KC_lateral_interactions/tree/f0ee2079dae6761cc2d07f04e96e76e2654b6e3c), associated in its README with DOI `10.1016/j.cub.2026.01.014`, was cloned at commit `f0ee2079dae6761cc2d07f04e96e76e2654b6e3c`. Its README attributes the calcium data to Manoim et al. 2022. Source code is GPL-3.0 and remains unmodified in ignored `data/raw/kc-reporter-data/author-code`; no author implementation was imported or copied into the runtime. The [audit receipt](../validation/kc-reporter-data-audit.json) pins every tracked author file, including the workbook, source, requirements and license.

The two direct PMC supplement requests returned HTTP 200 **HTML browser challenges**, not XLSX files. Their response bytes, hashes and failed acquisition status are retained in the [acquisition receipt](../validation/kc-reporter-workbook-acquisition.json). This is not evidence of an institutional-login requirement. The complete primary supplement and Table S1 have not been recovered by this acquisition.

Reacquiring the public repository requires `git clone https://github.com/nawrotlab/KC_KC_lateral_interactions data/raw/kc-reporter-data/author-code` followed by checkout of the commit above. Existing raw data should be preserved. The acquisition/audit scripts refuse to overwrite their first receipts.

## Workbook contents and checks

`data/gamma_mch_responses_manoim_supplement.xlsx` is 28,573 bytes, SHA-256 `f92ab807009e2e8160fbc8c6c100731012052843484de6c796c7faf673712a1d`. An artifact-tool read identified one sheet (`Sheet1`, `A1:D501`). Headers `A1:D2` specify WT/KD, each with Mean/SE. The **499 rows × 4 numeric values** in `A3:D501` are finite, contain no formulas, and have strictly positive SE columns. All 1,996 cells match an independent direct OOXML numeric decoding exactly; the source checksum and author checkout remain unchanged.

The [CSV extraction](../validation/kc-reporter-traces.csv) preserves every number, including 13 negative KD mean samples. It adds original Excel row numbers and explicitly **code-derived** timing, never invented animal records. The workbook contains no time column, units, individual responses, sample sizes, sex, genotype details, or explicit primary figure/panel identification. The filename and author fit code support the MCH γ-response interpretation; they do not independently resolve the exact primary cohort or normalization.

Descriptive maxima over the entire retained trace are WT 0.651523357142857 (Excel row 135) and KD 0.998030222222222 (row 151). With the author code's 30 Hz time construction, these occur at 4.4 and 4.9333333333 s. These are maxima of means, not means of individual peak responses; their difference or ratio is not a statistical test or an electrical gain estimate. No SE-to-SD conversion is justified without cohort information.

The retained [Manoim primary article](https://pmc.ncbi.nlm.nih.gov/articles/PMC9613607/) describes GCaMP6f ΔF/F means and SEM, 30 Hz imaging, MCH/OCT stimuli, and a γ-axon versus calyx dissociation. Figure 3 reports multiple drivers/regions and distinct sample sizes. The missing full supplement prevents a verified exact join from this four-column export to those cohorts. Do not silently assign one caption's n, sex or driver to the export. The earlier [source review](24-kc-spatial-mechanism-constraints.md) remains the frozen protocol record.

## What the author fitting code actually does

Reviewed source: [`fit_rate_model_to_data.py`](https://github.com/nawrotlab/KC_KC_lateral_interactions/blob/f0ee2079dae6761cc2d07f04e96e76e2654b6e3c/codes/fit_rate_model_to_data.py), [`fit_functions.py`](https://github.com/nawrotlab/KC_KC_lateral_interactions/blob/f0ee2079dae6761cc2d07f04e96e76e2654b6e3c/codes/fit_functions.py), and the stimulus/adaptation/inhibition/sigmoid helpers in [`KC_population_calcium_rate_model_functions.py`](https://github.com/nawrotlab/KC_KC_lateral_interactions/blob/f0ee2079dae6761cc2d07f04e96e76e2654b6e3c/codes/KC_population_calcium_rate_model_functions.py). Other learning and valence scripts are pinned but not fully audited here.

| Component | Source implementation | Consequence for reuse |
|---|---|---|
| Time/stimulus | 30 Hz; onset 3.6 s; nominal 5 s pulse; 499 samples through 16.6 s | Timing comes from code, not workbook metadata |
| Population | 700 KCs; seed 666; 35 reliable inputs uniformly 0.5–1 and 105 unreliable inputs uniformly 0–0.5; 560 zero-input cells | A declared synthetic recruitment distribution, not fitted MaleCNS recruitment |
| Measurement | Fit and plotted population responses average only the 140 positive-input cells | Not an all-KC mean or a prediction of KC sparsity from anatomy |
| KD state | Calcium input/leak, adaptation, clipping at zero; no lateral inhibition | Reporter dynamics, without a membrane-voltage or spike equation |
| WT state | Separate calyx/lobe calcium; shared input and calyx-driven adaptation; lobe suppression | Supports testing compartment-specific reporter effects; does not supply compartment electrical parameters |
| Connectivity | Uniform row-normalized all-to-all lateral matrix, diagonal zero | No actual connectome or per-contact receptor assignment |
| Objective | Scalar sum of squared SE-standardized residuals plus parameter L1 penalty, coefficient 3.885 | Conditional penalized curve fit; no animal-level likelihood or measured temporal covariance |
| Fit sequence | KD first; then WT holding KD parameters; optimizer `lbfgsb` | Results depend on staging, bounds, initialization and synthetic input scales |
| Decay window | Post-offset tails initialize shared decay time; main objectives use samples through 8.6 s | The tail is already used and cannot be advertised as untouched evaluation data |
| OE comparison | Tune inhibition factor against a simulated voltage-independent trace | Not a fit to an independent empirical OE workbook |

The repository does not ship fitted parameter outputs. Initial values such as `tauinh=1.5`, `inhfactor=15`, `infp=0.5` and `slf=0.03` are not published measurement estimates extracted by this audit. The requirements file pins `statsmodels` to both 0.13.5 and 0.14.0; those declarations cannot both be satisfied by one environment. Do not install the file blindly or import the top-level fit script merely to inspect it.

## Numerical details that must survive a reference comparison

1. **Pulse boundaries:** the helper rounds labels to two decimal places, whereas integration uses fixed `dt=1/30 s`. Maximum label error is 0.0033333333 s. Both endpoints are stimulus-positive: indices 108–258, 151 samples. A full-length Euler simulation therefore receives 151 nonzero driving intervals, or 5.0333333333 s. The fit truncated at index 258 has only 150 such updates because its final sample is not advanced. This is a one-step difference between fit-window and full-trace execution, not evidence about actual valve timing.

2. **Inhibitory memory gating:** the code multiplies the entire updated inhibitory state by the sigmoid, including the retained old state. Writing `a=dt/tauinh`, lateral drive `D`, and modulation `m(C)=1/(1+exp((C-infp)/slf))`, its recurrence is

   `I_next = m(C) * ((1-a)*I + a*D)`.

   Lobe calcium then receives a subtraction using **old** `I`. This differs from multiplying only the new drive in a continuous-time inhibitory filter. For constant C/D and `0<m<1`, elementary algebra gives `I_equilibrium = m*a*D / (1-m*(1-a))`. Holding the same parameters while shrinking dt sends this equilibrium toward zero. Thus a direct transfer from 30 Hz to the CNS's 0.1 ms step would change the mechanism, even before anatomy or physiology enters. This is a derived property of the inspected discrete recurrence, not a fitted biological finding. At m=1 the ordinary filter is recovered.

3. **Noise normalization:** the top-level plotting path scales the fitted KD residual standard deviation by `r=sqrt(2*dt/tauKCdec)` before calling either simulator; both simulators multiply that argument by r again. That specific call path therefore applies r² to the raw residual scale. This audit does not claim a numerical effect size without fitted parameters, or that all other author call paths behave identically.

4. **Normalization and clipping:** the author comments acknowledge fitting without noise and baseline while noisy simulations can shift the baseline. The biological export retains negative normalized values; the latent model calcium is clipped nonnegative. Observation baseline handling must be stated separately from latent positivity, rather than silently clipping the data.

## Derived implications and next bounded step

The recurrent γ intervention showed that removing a particular assumed fast positive term reduces model γ activity. The primary physiology and author reference instead concern activity-dependent local suppression of reporter signals and output. These observations motivate separating **spike production, axonal calcium and release**. They do not establish that deleting fast current is equivalent to mAChR-B modulation, nor that this reporter model resolves APL/MBON saturation.

Before any fit, recover or establish the export's exact figure/cohort and normalization; retain a predeclared development/evaluation split that does not reuse the author decay-initialization tail as a holdout. Then freeze a small **reporter-level** reference comparison, with explicit baseline/observation mapping, source-faithful discrete timing and a separately labeled continuous-time alternative if needed. Include source WT/KD contrast, amplitudes and timing, out-of-window response, seed robustness and timestep sensitivity. State which quantities remain non-identifiable from population means and unknown covariance.

An electrical/graded-release promotion needs additional compatible evidence and a mapping to actual male circuit anatomy. No new graph run or fit is justified merely by acquiring this workbook. H1 remains experimental; the Eon body integration remains cancelled; future long-running trials remain fixed complete batches followed by one combined review and a quiet completion trigger.

Artifacts: [audit script](../scripts/audit_kc_reporter_data.py), [source/data receipt](../validation/kc-reporter-data-audit.json), [unaltered summary extraction](../validation/kc-reporter-traces.csv), [failed supplement acquisition script](../scripts/acquire_kc_reporter_workbooks.py). Source raw files remain ignored; the tracked hashes and public commit permit reacquisition.
