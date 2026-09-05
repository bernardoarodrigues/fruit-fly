# Descending-population sensory decodability

This is a brain-only diagnostic of whether a fitted observer can recover a
left–right input contrast from the simulated descending population. It does not
train the body's motor policy, optimize food approach, or establish innate
biological decoding. No runtime decoder or trained weights are installed.

## Why the scope is limited

The assay uses DM1/DM4 input only, with artificial presynaptic conductance events.
That is not a verified upwind-navigation stimulus. Matheson et al. found that
broad ORN activation with wind could elicit upwind movement, whereas activation
of individual vinegar-responsive ORN types did not reproduce that behavior.
Without wind, their broad activation produced search after stimulus offset but
not upwind orientation. Odor contrast and wind direction must therefore remain
distinct candidate signals in this project.
[Matheson et al., 2022](https://www.nature.com/articles/s41467-022-32247-7)

The same study's functional attribution to hΔC must be read with its 2024
addendum: VT062617 additionally or predominantly labels hΔK. The driver-based
functional results cannot uniquely identify hΔC as the demonstrated circuit.
[Matheson et al., addendum 2024](https://www.nature.com/articles/s41467-024-46225-8)

## Frozen assay

`scripts/assess_dn_decodability.py` uses all 166,700 neurons and 25,582,938 edges
of the retained MaleCNS graph, the uncalibrated conductance default parameters,
and explicitly selected `.2 ms` Padé integration with the validated exponential
fallback in stiff regimes. It advances at a fixed 5 ms coupling interval. This
choice does not change the simulation's default neural backend or timestep.

For independently reset trials, 100 ms of bilateral 5 Hz baseline input precedes
100 ms of stimulus. Spike counts become rates over each complete interval, and
the trial's baseline is subtracted. Input contrast is
`(rate_left - rate_right)/(rate_left + rate_right)`; the five contrasts are
`-.75, -.25, 0, .25, .75`. Rates are external presynaptic events delivered to
the modeled ORNs, not imposed ORN firing rates. Actual ORN firing is measured
separately. The same seed across contrast conditions provides paired stochastic
replicates, and complete seeds are withheld from training.

| Split | Neural seeds | Mean event rate | Responses |
|---|---|---|---:|
| Train | 101, 102, 103 | 40, 100 Hz | 30 |
| New seeds | 1001, 1002, 1003 | 40, 100 Hz | 30 |
| New seeds and intensities | 1001, 1002, 1003 | 70, 130 Hz | 30 |
| ORN outgoing ablation | 1001, 1002 | 100 Hz | 10 |
| Persistent sequences | 2001, 2002 | 70 then 130 Hz | 20 |

The ablation suppresses actual outgoing synaptic events from the stimulated
ORN sources; their membrane and spike dynamics remain active. This tests the
input route, not the necessity of any individual descending type. The sequence
test has a single initial baseline and ten successive 100 ms stimulus blocks
per seed, with no intervening reset. It detects reliance on a freshly initialized
brain and an independently sampled per-trial baseline.

Four observer feature sets are evaluated:

- All 1,314 descending neurons' baseline-corrected firing rates.
- Left minus right mean rates for each DN type with both sides annotated.
- Individual DNg97, DNa01, DNa02, DNb05, DNg34 and DNp09 rates.
- The two measured ORN population rates, as a direct sensory comparator.

Each observer is linear ridge regression with an intercept. Training-only
means and standard deviations normalize each varying feature; dividing by the
square root of the number of varying features gives each feature set equal
total standardized energy. The penalty `alpha=1` was fixed before the run.
No test data select features, normalizers, penalty or model parameters. Targets
never contain food locations, body coordinates, reward or movement labels.
An independent primal normal-equation calculation agrees with the implemented
dual ridge solver to `1e-12` on a seeded synthetic matrix that includes a
constant feature; the constant feature is excluded correctly.

The script reports held-out RMSE, R², nonzero-contrast sign accuracy, error at
equal bilateral input, and results by seed. One hundred training-label
permutations within each seed/intensity block provide a diagnostic null. These
small synthetic samples do not provide biological significance or population
uncertainty; neighboring sequence blocks are especially not independent trials.

## Reproduction and evidence

```
.venv/bin/python scripts/assess_dn_decodability.py
```

The full report is `validation/dn-decodability.json`; raw baseline and response
rates, recorded neuron IDs and feature matrices are compressed into
`data/derived/dn-decodability.npz` with a checksum in the report. The bulk data
are local generated outputs, not bundled connectome data. All outcomes are
retained, including failed generalization and the direct sensory comparator.

Interpretation requires comparing held-out seeds, intensity transfer,
persistent-state transfer and ablation. A high fresh-trial score alone only
establishes recoverable information under those assumptions. Even robust
decodability would not demonstrate the correct biological motor command,
benefit over direct sensory control, or a validated foraging circuit.

## Executed result: no supported descending decoder

The complete run took **190.8 s** and retained all 120 responses. Of 1,314 DN
features, 241 varied during training; 142 of 471 bilateral type differences
varied, and only five of the 12 named motor-cell rates varied. The graph produced
25,974,361 spikes over all stimulus and baseline epochs.

| Observer | New seeds R² / sign accuracy | New seeds + intensity R² / sign accuracy | Persistent sequence R² / sign accuracy |
|---|---:|---:|---:|
| All DNs | −.073 / 45.8% | −.159 / 41.7% | −.431 / 31.2% |
| Bilateral DN type differences | .016 / 58.3% | −.038 / 45.8% | −.436 / 25.0% |
| Named motor DNs | −.016 / 58.3% | −.079 / 45.8% | −.358 / 43.8% |
| Actual ORN rate comparator | .606 / 95.8% | .582 / 100% | .595 / 100% |

The descending observers did not show robust held-out recovery in this assay.
Their R² values did not exceed the corresponding 95th percentile of the
shuffled-label diagnostic on any of the three test splits. The ORN rate
comparator retained the input's sign across both new seeds and the evolving
network. This establishes a usable positive control for delivery and recording,
but the comparator is only one fixed linear estimator, not an optimal sensory
decoder. The exact null distributions and seed results remain in the JSON.

Suppressing the stimulated ORNs' outgoing edges produced **zero traversed edges
and zero DN spikes**. Its 8,622 whole-network spikes came from directly driven
sensory cells. The fitted regressors can still emit constant nonzero predictions
when every DN is quiet, due to training centering and their learned intercept in
raw feature coordinates. The named-cell model was particularly poor under this
intervention (R² −3.434). A regression output is therefore not intrinsically a
safe or causal motor command merely because its inputs are neural spikes.

No learned DN steering adapter is justified by these results, and none was
installed. The negative result applies to this finite training set, observer,
short response windows, default conductance hypotheses and two-glomerulus input.
It does not prove that no nonlinear or better-trained observer could recover
contrast, nor does it invalidate the biological wiring. Missing wind input,
uncalibrated receptor drive and synapses, sparse named motor activity and strong
dependence on recurrent history remain unresolved. The next source-grounded
step is sensory and physiological calibration with independent data, followed
by crossed odor/wind assays; tuning a decoder to successful food trajectories
would answer a different question.
