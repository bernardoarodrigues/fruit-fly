# Navigation calibration: missing wind channel and source corrections

Research update: 2026-09-05 UTC. The executed DM1/DM4-only odor assay does not yet reproduce food approach. The model's oversuppressed motor neurons are one problem; the sensory experiment also omits a relevant modality. This negative result cannot be interpreted as a biological failure of the measured connectivity.

## Primary evidence

[Suver et al., Neuron 2019](https://pmc.ncbi.nlm.nih.gov/articles/PMC6533146/) found that walking flies combine information from both antennae to orient to wind. Deflection toward the head preferentially activates JO-E channels; deflection away activates JO-C channels. A single antenna's displacement is ambiguous about airflow direction, whereas comparison across the pair supports direction coding. Their physiological measurements and antennal mechanics provide calibration targets, rather than permission to send a source-bearing angle directly to descending neurons.

[Matheson et al., Nature Communications 2022](https://www.nature.com/articles/s41467-022-32247-7) tested odor and optogenetic stimulation under roughly 12 cm/s wind. Broad ORN activation supported upwind movement and odor-offset search; single tested vinegar-responsive ORN types did not. Odor and wind information enter the fan-shaped body through different pathways. Thus the current two-glomerulus input is not a complete reproduction of that navigation assay.

The [2024 addendum](https://www.nature.com/articles/s41467-024-46225-8) changes interpretation of the original functional hDeltaC results: driver VT062617 also, or predominantly, labels hDeltaK. Responses in Fig. 5E–I and behavioral effects in Fig. 6 may therefore belong to hDeltaK. The anatomical direct FB5AB/PFNa inputs to hDeltaC do not resolve that driver ambiguity; hDeltaK can receive indirect inputs. Do not use the unqualified older functional assignment to calibrate male hDeltaC.

The later 2026 navigation-memory paper is being audited separately in the internal-state/learning notes, including its more specific hDeltaK intervention and sex/preparation limits.

## Implementation implications and hypotheses

These are project proposals, not new biological findings:

1. Expose local air velocity relative to antenna/head motion. Use measured antennal response curves, or a visibly parameterized mechanics approximation, before JO-C/JO-E input. No resource coordinate belongs in this adapter.
2. Audit exact male JO subtypes and root-side assignments. Broad historical C/E labels do not supply all modern subtype tuning or distinguish wind from gravity and touch.
3. Match plume transport resolution to wind speed. The current default 2 mm/s flow and 10 Hz puff emission are engineering choices, not the 2019/2022 assay conditions. Changing speed without emission resolution can create unintended sampling artifacts.
4. Compare odor-only, wind-only, combined and crossed inputs. Record wind/odor encoding, head-direction populations, descending activity, upwind velocity and search curvature before fitting a motor decoder.
5. A learned decoder could demonstrate an engineering interface if trained and tested on independent local-stimulus trials. It would not demonstrate that the intact biological fly uses the fitted weights. Preserve the anatomical readout baseline and all failed conditions.
