# hΔK–PFG slow recurrence: primary-source and author-code audit

Audited 2026-09-05. A bounded reproduction of the public Lanz model runs successfully. At the author's default excitation/inhibition point, slow PFG signaling gives an exponential recovery fit of **5.843 s**, versus **1.321 s** with fast signaling. This establishes an executable circuit hypothesis. It does not identify a male PFG receptor, determine every PFG connection's sign, or validate whole-brain navigation.

## Sources, versions, and access

- Lanz et al., *Disinhibition of a recurrent attractor gates a persistent goal signal for navigation*, [preprint DOI](https://doi.org/10.1101/2025.10.07.681003). The downloaded [Europe PMC XML](https://www.ebi.ac.uk/europepmc/webservices/rest/PMC12632281/fullTextXML) explicitly says `article-version=1`. Local reading copies: `tmp/navigation-memory/lanz2025.xml` and `.txt`.
- The [bioRxiv version API](https://api.biorxiv.org/details/biorxiv/10.1101/2025.10.07.681003) lists v1 on 2025-10-07 and v2 on 2026-04-15. Its publication field was `NA` when checked. Direct v2 XML/PDF access returned HTTP 429 here; v2 methods were not read. Do not treat the v1 methods as the latest methods.
- The [author repository](https://github.com/nagellab/Lanzetal2025) is public, despite v1's prospective code-availability statement. This audit pins **`b52ee5742e96a579356bc475d01a08d640759789`**, dated 2026-08-24. The [model notebook](https://github.com/nagellab/Lanzetal2025/blob/b52ee5742e96a579356bc475d01a08d640759789/model_code/recurrent_python_clean.ipynb) has SHA-256 **`f3174d6a279fd5b488c79910d8336c2ae2baa69380e7268dd93450e908226a54`**.
- Code license: [GPL-3.0](https://github.com/nagellab/Lanzetal2025/blob/b52ee5742e96a579356bc475d01a08d640759789/LICENSE). The wrapper downloads and executes the pinned notebook in ignored `tmp/`; no author model implementation was merged into the fly runtime. Retain the upstream attribution/license when distributing its code. The preprint's license is a separate CC-BY-NC-ND license.
- The author [model README](https://github.com/nagellab/Lanzetal2025/blob/b52ee5742e96a579356bc475d01a08d640759789/model_code/README.md) links [Zenodo record 19584831](https://zenodo.org/records/19584831) for precomputed grids and hemibrain connectivity. Its API returned HTTP 403 in this environment. This is an access failure, not evidence that the archive is absent. Gaussian connectivity needs no archive; real-connectivity and saved-heading runs were not reproduced.

## Physiological evidence and its limit

In v1, hΔK current injection alone did not maintain excitation. Persistence following broad R65C03 stimulation was reduced by nicotinic blockers and hΔK tetanus toxin. R65C03 includes roughly 17 tangential neurons per hemisphere, not only FB6A/D. ExR3 stimulation caused persistence reduced by methysergide. FB6M/FB5V stimulation inhibited hΔK; picrotoxin converted responses toward excitation. PFG stimulation excited some hΔK recordings and inhibited others. These are functional network interventions, not isolated receptor measurements. [Lanz v1, Figure 2 and Extended Data](https://doi.org/10.1101/2025.10.07.681003)

The separate [Wolff et al. molecular atlas](https://doi.org/10.7554/eLife.104764) identifies PFG tyramine and peptide expression, including MIP and Dh31. Its expression evidence does not establish the sign, release contribution, receptor kinetics, or efficacy at each hΔK target. The current MaleCNS annotation snapshot labels all 18 `PFGs` transmitter consensus `unclear`; that classifier label should remain distinguishable from curated molecular evidence. Exact male IDs are already saved in [internal-state-learning-mapping.json](../data/internal-state-learning-mapping.json).

**Supported boundary:** represent evidence about transmitter identity separately from functional sign and kinetic confidence. A neutral/zero fast-current placeholder means unsupported fast transmission is omitted; it must not be described as proof that PFG cells have no signaling. Conversely, changing every outgoing PFG edge into slow excitation is unsupported. A tested positive recurrent PFG channel is currently a reduced-model assumption, not a receptor-resolved MaleCNS parameter.

## What the fitting code actually fits

The pinned electrophysiology routines are executable specifications but were not refit here because their input recordings were unavailable:

| Author routine | Experimental target | Fitting method | Interpretation limit |
|---|---|---|---|
| [`fit_fast.m`](https://github.com/nagellab/Lanzetal2025/blob/b52ee5742e96a579356bc475d01a08d640759789/ephys_code/fit_fast.m) | FB6M control recordings, cells 1–4 and 6; 200 ms on/800 ms off pulses | Baseline-subtract mean voltage, normalize individual rise/decay intervals, jointly minimize their mean squared errors, then average fitted coefficients across pulses. Grid `a=0.1:0.1:50`, `b=0.1:1:200`, with `b>a`. | A measured inhibitory network response is used to motivate a generic fast kernel. It is not an hΔK cholinergic receptor fit. |
| [`fit_slow.m`](https://github.com/nagellab/Lanzetal2025/blob/b52ee5742e96a579356bc475d01a08d640759789/ephys_code/fit_slow.m) | R65C03 recordings under imidacloprid + curare; 4 s stimulation | Mean voltage baseline-subtracted; normalized rise/decay fits; grid `a=0.001:0.01:1`, `b=0.01:1:100`, `b>a`. | This is broad tangential-neuron stimulation under nicotinic blockade, **not isolated PFG→hΔK transmission**. |

Both fit the same second-order linear filter used by the model, with a 1 ms Euler step. The repository therefore provides a path from recordings to generic kinetic fits. We did not verify that running these grids yields the notebook's rounded `4.63`, `0.64`, and `25`, and cannot claim those constants are directly measured tyramine-receptor parameters. Ligand-specific antagonism/knockdown, target receptors, effective release, target-specific signs, and male validation remain unresolved.

## Exact simulated system at the pinned notebook

The reproduced cells are 0, 3, 5, 8, and 10. There are 30 hΔK units, 18 PFG units, and one global inhibitory unit. The helper also allocates an extra excitatory unit named ExR3, but all its connections and external input are zero in this experiment. Activities are dimensionless rates, not spike counts or membrane voltages.

Let `r_H`, `r_P`, and `r_I` denote activity; `S_x` synaptic output; and `v_x` its derivative. Dynamic terms use the previous integration step; external input uses the current sample. The author code updates:

```text
v_x[next] = v_x + dt * (-(a_x + b_x) * v_x + a_x*b_x*(r_x - S_x))
S_x[next] = S_x + dt * v_x

r_H[next] = clip(r_H + dt*(-alpha*r_H + exc*W_H←P @ S_P - S_I + I_H), 0, 1)
r_P[next] = clip(r_P + dt*(-alpha*r_P + exc*W_P←H @ S_H - S_I + I_P), 0, 1)
r_I[next] = r_I + dt*(-alpha*r_I + inh*(sum(S_H) + sum(S_P)))
```

The hΔK/PFG updates are clipped after Euler integration. The global inhibitory state is not explicitly clipped in this helper; the reproduced inputs keep it nonnegative. The manuscript instead writes activation functions in the synaptic filter. This audit reproduces code behavior, without asserting identical behavior outside the demonstrated regime.

Local connectivity is a Gaussian of wrapped angular distance. Preferred hΔK angles span `[-π,π)`; PFG angles span `[0,2π)`. Code names put the postsynaptic population first: `W_HDK_PFG` means PFG→hΔK. The constructor first divides by the first row sum, then divides the whole matrix by its maximum. The final matrices are **not row-stochastic**. Copying gains onto raw synapse-count matrices would change their meaning.

| Parameter | Accessible v1 manuscript | Pinned Figure 3 code reproduced here |
|---|---|---|
| Local populations | 30 hΔK; 18 PFG | Same |
| Passive parameters | `tau=1`, `alpha=10` | `alpha=10`, implicit `tau=1`; passive decay 0.1 s |
| Integration | Euler, 0.001 s | Same |
| Fast filter `a,b` in s⁻¹ | `10,10.1` | `4.63,25` |
| Slow filter `a,b` in s⁻¹ | `0.8,1` | `0.64,25` |
| Gaussian widths | 0.4 rad PFG→hΔK; 0.3 rad hΔK→PFG | 0.25 rad both ways |
| Single-run gains | Parameter sweep | `exc=5.6`, `inh=3.6` |
| Input | Several tested patterns | `1+cos(angle)` into both populations, 5–9 s in a 20 s simulation |

For the code filter, `1/a` is 0.216 s fast and 1.563 s slow, with `1/b=0.040 s` in both cases. These filter constants are not the network recovery time. V1 calls inverse coefficients “rates” in places; dimensionally they are time constants. The current values also differ from v1, so they are labeled as pinned-code values rather than latest-paper values.

Other implementation details matter if expanding this reproduction:

- The real-connectivity branch lists 31 **hemibrain** hΔK IDs and removes the last to obtain 30. It is not a MaleCNS model. It also appears to return preferred-angle variables only assigned in the Gaussian branch; that possible branch error is code-inspection evidence, not a reproduced failure.
- The saved-heading gating experiment uses `exc=7`, `inh=4`, a 12–18 s gate, and hΔK input −5 outside the gate/0 inside. Its `.npy` heading input was unavailable. It was not reproduced.
- The random-heading helper squares a normal draw and assigns a random sign; that is not the ordinary Gaussian heading increment described in v1. The later two-dimensional example overwrites one `a_fast` assignment. Neither exploratory path supplies calibrated male parameters.
- The author's recovery-fit helper hardcodes stimulus offset at sample 8999. Its fitted exponential rate is per sample; conversion is `tau=-dt/rate`. A returned zero denotes a nondecaying classification or rejected fit, not evidence of unlimited memory.

## Actual reproduction and numerical check

Run from the repository root:

```sh
.venv/bin/python scripts/replicate_navigation_memory.py
```

The [wrapper](../scripts/replicate_navigation_memory.py) checks the notebook SHA-256 before execution. It leaves model functions unchanged, selects slow then fast PFG dynamics in the author's default single simulation, and adds a half-timestep check for the slow run. This is a reproduction of two parameter points, not the full parameter sweep or a refit of electrophysiology.

| Observed metric | Fast PFG | Slow PFG |
|---|---:|---:|
| Author exponential recovery fit | 1.320739 s | 5.843214 s |
| Population contrast at offset | 0.862291 | 0.485913 |
| Contrast 1 s after offset | 0.393096 | 0.288651 |
| Contrast 5 s after offset | 0.018759 | 0.153331 |
| Contrast at final sample, approximately 20 s | 0.000236 | 0.058670 |
| Direct first 1/e crossing after offset | 1.263 s | 4.019 s |
| hΔK peak neuron at offset and end | 15 / 15 | 15 / 15 |

The author fit and the direct 1/e crossing answer different questions and need not agree for a non-single-exponential tail. The slow comparison at `dt=0.0005 s` was finite, with maximum absolute hΔK difference **0.001** and RMS difference **5.355×10⁻⁵** relative to the 1 ms run. This is a useful local discretization check, not a proof of stability over all gains. The author's unused logarithm calculation emits a divide-by-zero warning; it is captured in the result, and both reported trajectories are finite.

Artifacts: [complete JSON](../validation/navigation-memory-author-code.json), [100 Hz contrast CSV](../validation/navigation-memory-author-code.csv), [plot](../validation/navigation-memory-author-code.png). Python 3.12.14, NumPy 2.5.2; roughly 10 seconds total wall time in this environment.

## Integration decision

Keep this circuit as an independent reference experiment. No changes were made to whole-brain neurotransmitter signs, `neural.py`, or `conductance.py`.

An eventual curated slow-signaling layer should retain: molecular source, presynaptic type, target/receptor evidence, functional-sign evidence, kernel provenance, units, confidence, and whether a value is a measured fit or an engineering hypothesis. A molecularly known cell with an unknown functional effect must be representable without inventing a sign. The current evidence supports comparing a positive slow recurrent hypothesis against omitted-PFG and fast-PFG ablations; it does not yet select a receptor-resolved implementation for the full male graph.

A meaningful later test would ask whether actual MaleCNS topology, an independently specified receptor hypothesis, and physical odor/wind input preserve a heading-related bump after odor loss, without injecting a food target or remembered heading directly. The present single-circuit reproduction makes that hypothesis reviewable but does not perform that embodied test.
