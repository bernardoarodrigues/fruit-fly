# H1 saved-data audit batch

The twelve assigned completed H1 trials passed all **705,549 checks** on their first reader execution. No existing receipts were skipped, no failures occurred, and no reader, reference helper, or model code was changed. The batch ran only the frozen saved-data reader; it did not rerun a network simulation.

The checks covered 55,961,722 retained spikes, 5,351,307 selected event rows, and 32,343 predeclared scalar reference intervals. The maximum production–independent quadrature and production–64-point differences were both 4.26326e-14 mV. The maximum independent ODE–quadrature difference was 2.08189e-12 mV; the largest quadrature error estimate was 2.03663e-13 mV. No sampled threshold decision had a margin within its observed reference discrepancy.

| Ordinal | Trial | Checks | Reference intervals | Result |
| --- | --- | ---: | ---: | --- |
| 26 | 26-H1-seed11-constant_baseline | 60,393 | 2,995 | Pass |
| 29 | 29-H1-seed12-constant_baseline | 60,401 | 2,994 | Pass |
| 32 | 32-H1-seed13-constant_baseline | 60,534 | 2,991 | Pass |
| 35 | 35-H1-seed11-ethyl_acetate | 60,395 | 2,995 | Pass |
| 38 | 38-H1-seed12-ethyl_acetate | 60,401 | 2,994 | Pass |
| 41 | 41-H1-seed13-ethyl_acetate | 60,582 | 2,992 | Pass |
| 44 | 44-H1-seed11-isoamyl_acetate | 60,394 | 2,995 | Pass |
| 47 | 47-H1-seed12-isoamyl_acetate | 60,401 | 2,994 | Pass |
| 50 | 50-H1-seed13-isoamyl_acetate | 60,567 | 2,993 | Pass |
| 53 | 53-H1-seed11-ethyl_acetate_source_outputs_blocked | 53,827 | 1,800 | Pass |
| 56 | 56-H1-seed12-ethyl_acetate_source_outputs_blocked | 53,827 | 1,800 | Pass |
| 59 | 59-H1-seed13-ethyl_acetate_source_outputs_blocked | 53,827 | 1,800 | Pass |

The [machine-readable index](../validation/inhibitory-recurrent-panel-H1-batch-review.json) retains each receipt and reference-array checksum, numerical maxima, counts, and ambiguity count. The [batch plan](../validation/inhibitory-recurrent-panel-H1-batch-review-plan.json) records exact source pins and assigned ordinals; the [batch log](../validation/inhibitory-recurrent-panel-H1-batch-review.log) retains every reader output. All pinned files had unchanged hashes at completion.

This batch author also authored the independent scalar reference helper, which is disclosed rather than counted as another independent numerical reviewer. Adaptive and fixed quadrature share a coordinate and Brent inversion; the three-state ODE is separate. Quadrature error estimates are not certified total floating-point bounds. Selected 48-cell synaptic state, source-event dispositions, direct/reset arithmetic and the saved scalar intervals were checked; full global voltage between checkpoints and reference-winner optimality over unselected cells were not reconstructed. Zero sampled threshold ambiguity does not certify every network interval. These results establish numerical and saved-data consistency only, with no physiological validation or H1 promotion. Earlier H1 no-input audits and all H0 audits remain separate.
