# Isolated PER/TIM oscillator reproduction

`fruitfly/circadian.py` implements the ten-state biochemical oscillator in
Leloup and Goldbeter (1998), equations 1a-j. The source is the
[author-hosted primary article](https://utc.ulb.be/ARTICLES/1998_Leloup_JBR.pdf)
([DOI](https://doi.org/10.1177/074873098128999934)). Equations and captions were
checked visually against the downloaded PDF. This is a historical model
reproduction, not measured male circadian physiology.

The module is **not connected to the brain, body, environmental light slider,
physiology, or sleep**. It runs only when its explicit `advance_hours` method is
called. Biological hours are its time unit. Running a long biochemical experiment
quickly on a computer does not advance or rescale any neural/physics clock.

## State, reactions, and units

The fixed state order is `MP, P0, P1, P2, MT, T0, T1, T2, C, CN`:

- `MP/MT`: per/tim mRNA.
- `P0/P1/P2` and `T0/T1/T2`: unphosphorylated, mono- and bisphosphorylated protein.
- `C/CN`: cytosolic and nuclear PER-TIM complex.

The paper tentatively expresses concentrations in nM and defines all parameters
and concentrations relative to **total cell volume**. The equations represent
Hill repression by nuclear complex, mRNA synthesis and saturating degradation,
translation, two reversible phosphorylation steps for each protein, saturating
degradation of free `P2/T2`, bimolecular complex formation, dissociation, nuclear
import/export, and linear degradation. Every free mRNA/protein state includes
`kd`; complexes use `kdC` and `kdN`.

The total PER concentration is `P0+P1+P2+C+CN`; total TIM is
`T0+T1+T2+C+CN`. Each complex contributes one protein to each total. These totals
are not conserved because translation and degradation remain active. The tests
check that internal phosphorylation/association/transport fluxes cancel from
each protein-total derivative.

The complete default parameter set follows the Figure 2 caption:

| Parameter(s) | Value | Unit |
|---|---:|---|
| vsP, vsT | 1 | nM/h |
| vmP, vmT | 0.7 | nM/h |
| KmP, KmT | 0.2 | nM |
| ksP, ksT | 0.9 | 1/h |
| vdP, vdT | 2 | nM/h |
| k1 | 0.6 | 1/h |
| k2 | 0.2 | 1/h |
| k3 | 1.2 | 1/(nM h) |
| k4 | 0.6 | 1/h |
| KIP, KIT | 1 | nM |
| KdP, KdT | 0.2 | nM |
| n | 4 | dimensionless |
| K1P through K4P; K1T through K4T | 2 | nM |
| kd, kdC, kdN | 0.01 | 1/h |
| V1P, V1T, V3P, V3T | 8 | nM/h |
| V2P, V2T, V4P, V4T | 1 | nM/h |

`LG1998Parameters.figure4()` changes only `vsP=0.8`, `vmP=0.8`, and `k1=1.2`.
For Figure 4's light/dark protocol, `LightDarkSchedule()` imposes light during
hours [0,12) of each 24-hour cycle and darkness during [12,24). Only `vdT` changes:
4 nM/h in light and 2 nM/h in darkness. This represents the paper's imposed
TIM-degradation mechanism, not a photoreceptor or measured light-intensity curve.
Figure 2 and Figure 4A-C remain in constant darkness.

The authors chose parameters to generate plausible circadian oscillations. They
are not a male-specific fit, and no parameters were adjusted in this reproduction.

## Initial phase and numerical method

The figure captions do not provide their exact initial concentrations or phase.
We declare an analyst-chosen positive initial state of **0.1 nM for every state**,
discard 1,200 biological hours, then measure 240 hours. There is no phase fitting,
alignment to the published drawing, or hidden reset to a desired peak. A second
explicit positive initial state tests attraction to the same oscillation; its
free-running phase can differ, while under LD the absolute Zeitgeber phase
converges. Zeitgeber time zero means the declared onset of light.

The integrator is fixed-step fourth-order Runge-Kutta with a default **0.01 h**
step. Model evaluation is accelerated with Numba, but its clock is still measured
in hours. Durations and light transitions must fall on this grid. At a light
transition, the final RK4 stage uses the coefficient for the interval just ending;
the next step uses the new coefficient. The solver never averages across the
square-wave discontinuity.

All RK4 stages and accepted concentrations must be finite and nonnegative.
Invalid stages stop the operation before either the state or clock is committed;
there is no concentration clipping. Coarse steps or extreme parameters can fail
this check, so arbitrary parameter choices require renewed convergence checks.
Constructor parameters, timestep, schedule, and public tick are read-only.
The exposed concentration vector is a copy.

Checkpoints identify the model, solver, state ordering, parameter values,
initial conditions, schedule, timestep, biological-hour unit, and tentative-nM
unit. Incompatible metadata, negative/nonfinite concentrations, boolean values,
and invalid ticks are rejected before writes. Reset restores the declared
initial concentrations and hour zero. Chunked and uninterrupted integration,
including light boundaries, continue bitwise identically.

## Results and comparison limits

The symmetric Figure 2 configuration settles to a **24.134585 h** period, compared
with the explicit **24.135 h** value for the same parameters in the paper's Figure
6 caption. The PER and TIM branches coincide exactly. Peaks in total protein
follow mRNA by **2.428 h**; nuclear complex follows mRNA by **5.138 h**. The paper
describes these approximately as 3 and 5 hours, respectively.

| Symmetric Figure 2 output | Minimum | Maximum | Peak-to-trough amplitude |
|---|---:|---:|---:|
| per/tim mRNA | 0.03091 | 2.56408 | 2.53317 |
| Total PER/TIM | 1.26750 | 5.10331 | 3.83581 |
| Nuclear complex | 0.53464 | 2.04473 | 1.51009 |

All concentrations in the table are tentative nM. Amplitude means the full
peak-to-trough range, not half that range. Extrema use samples every 0.05 h;
peak times use three-point quadratic interpolation. Small period/lag standard
deviations in the JSON describe sampling error of a deterministic waveform,
not biological variability.

The asymmetric Figure 4 configuration in constant darkness has a computed
**25.036901 h** period. The article describes this only as close to 24 hours.
The mRNA peak lag is **1.835 h**, consistent with its approximate 1.8-hour account.
The computed PER-to-TIM protein peak lag is **2.659 h**, whereas the prose says
approximately 2.3 hours. This difference is retained, with no parameter or phase
adjustment. There is no source raw trajectory or digitized-figure error estimate.

With the published 12:12 LD forcing, the asymmetric model entrains to **24 h**.
The peak Zeitgeber times are:

| Output | Peak ZT (h) |
|---|---:|
| per mRNA | 16.252 |
| tim mRNA | 17.802 |
| Total PER | 19.245 |
| Total TIM | 21.688 |
| Nuclear complex | 22.254 |

The article's prose broadly places protein peaks near ZT19; that approximates
our PER peak, while TIM peaks later. Both exact equations and the Figure 4
caption parameters were independently rechecked; the computed distinction is
preserved rather than edited to match the prose. Concentration amplitudes
visually agree with the published panels, but this is not quantitative image
digitization or a fit to biological measurements.

All eight reproduction checks pass. Comparing the three protocols over 48 hours
against an independently transcribed reaction-flux RHS integrated with SciPy
DOP853 gives maximum concentration errors of approximately **1.3e-10 nM** at
the default RK4 step. Halving the step shows fourth-order convergence. Different
positive initial conditions give matching settled amplitudes and periods; under
LD their same-time trajectories differ by only about **2.3e-14 nM** after burn-in.
These checks support the specified numerical model, not empirical physiology.

## Reproduction and artifacts

```sh
.venv/bin/python -m pytest -q tests/test_circadian.py
.venv/bin/python scripts/reproduce_circadian.py
```

Example isolated use:

```python
from fruitfly.circadian import CircadianClock, LG1998Parameters, LightDarkSchedule

clock = CircadianClock(LG1998Parameters.figure4(), light_schedule=LightDarkSchedule())
state = clock.advance_hours(24.0)
clock.save_checkpoint("circadian-state.json")
```

- `data/circadian/lg1998-provenance.json`: primary-source receipt, pages, units, rights, limits.
- `validation/circadian-lg1998/results.json`: all parameters, initial states,
  numerical comparisons, periods, amplitudes, lags, checks, and source-code hashes.
- `validation/circadian-lg1998/*-timeseries.npz`: all ten states sampled over the
  240-hour post-burn-in window, with explicit biological-hour times and state order.
- `validation/circadian-lg1998/*-checkpoint.json`: complete final states for each protocol.
- `validation/circadian-lg1998/reproduction.png`: inspected six-panel scientific plot.

The primary PDF remains an ignored research copy at
`tmp/circadian/leloup-goldbeter-1998.pdf`, SHA256
`efdb43c8d3d8a434721ddfe00afc8ba038bfb1b36e566a12b69265f55d12f1aa`.
Its equations occupy physical PDF pages 3-4, Figure 2's caption page 5, and
Figure 4's caption page 9. The CellML repository returned 403 during source
review; it was not bypassed or treated as a consulted implementation.

## What this permits next

A biochemical oscillator can supply an independently tracked slow state without
assuming that every process is a spiking neuron. Connecting it to neural clock
cells would require explicit identities, coupling mechanisms and gains, and
shared physical time. Connecting it to sleep would additionally require a
homeostatic mechanism and behavioral validation. None follows from reproducing
this historical oscillator, and none is implemented here.
