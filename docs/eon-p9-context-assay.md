# Eon-inspired P9-context neural assay

The frozen twelve-trial panel completed with **167/167 consistency checks passing**. P9 activation recruited steering readouts, but adding the known male LgAG2 subset changed the steering imbalance in opposite directions across the two seeds. Sustained MN9 activity appeared in only one P9-plus-taste trial. P9-context forward spikes were confined to the first 50 ms. Extreme negative model voltages remain. These are neural simulation outcomes; no body, navigation, food intake, motor command or physiological calibration was evaluated.

The [plan](../validation/eon-p9-context-plan.json) was saved before neural advancement, with SHA-256 `0d7511333583899f05c6ba983b72973c76365251cad25c4ebbb104bc0df52919`. The [producer](../scripts/assay_eon_p9_context.py) retained the existing full male graph: 166,700 neurons, 25,582,938 edges, graph digest `e8d7babaecf923402d32fa1dd7fa687130968ac9ce57fa1b1af80ffea55c82e8`. Source, graph-array and upstream notebook hashes are recorded in the plan and were unchanged after execution.

The adaptation follows the public Eon neural notebook at `c976c7a9`: P9 context at 100 Hz, with leg-associated input at 200 Hz. Our panel uses two verified male DNp09 cells and eleven male LgAG2 cells. The source notebook instead uses twelve lgAG2 cells plus two separately named ascending-leg inputs; those ascending inputs and an unverified twelfth counterpart are absent here. This is an Eon-inspired subset assay, not literal reproduction of that neural protocol or the embodied demo. Direct P9 stimulation is an imposed locomotor context, not spontaneous walking. The [design note](eon-taste-replication-design.md) records these distinctions.

Every condition lists the same ordered thirteen input IDs:

```text
DNp09: 10783, 11177
LgAG2: 87710, 91221, 91302, 92929, 93294, 94367,
       123191, 151556, 162704, 219573, 526151
```

Seeds 11 and 12 each received six 500 ms trials: the four P9 0/100 Hz × LgAG2 0/200 Hz conditions, P9-only with P9 outgoing edges blocked, and P9-plus-taste with LgAG2 outgoing edges blocked. No other cells received external inputs. Weights and dynamics were unchanged: 0.1 ms steps, −52 mV rest/reset, −45 mV threshold, 20/5 ms membrane/synaptic time constants, 1.8 ms delay, and 68.75 mV external voltage increments. Listed inputs have zero refractory duration, including at zero input rate; other cells retain 2.2 ms. Accordingly, the no-events condition controls the common input eligibility convention rather than representing untouched physiology.

Rates below are raw spike counts divided by cell count and 0.5 seconds. Forward is the two DNg97/oDN1 cells; each steering column pools DNa01 and DNa02 on that side; MN9 pools its two cells. These are not smoothed decoder outputs. The source author's displayed 1 s, thirty-trial means use another graph and protocol, so numerical agreement is not a success criterion.

| Seed | Condition | All-network spikes | Forward Hz | Left Hz | Right Hz | MN9 Hz |
|---|---|---:|---:|---:|---:|---:|
| 11 | No events | 0 | 0 | 0 | 0 | 0 |
| 11 | Taste only | 45,453 | 0 | 0 | 0 | 0 |
| 11 | P9 only | 41,516 | 1 | 9 | 2 | 0 |
| 11 | P9 + taste | 45,069 | 1 | 14 | 0 | 0 |
| 11 | P9 only; P9 outputs blocked | 104 | 0 | 0 | 0 | 0 |
| 11 | P9 + taste; taste outputs blocked | 42,526 | 1 | 9 | 2 | 0 |
| 12 | No events | 0 | 0 | 0 | 0 | 0 |
| 12 | Taste only | 32,316 | 2 | 3 | 3 | 1 |
| 12 | P9 only | 46,949 | 2 | 11 | 5 | 0 |
| 12 | P9 + taste | 304,677 | 2 | 3 | 0 | 12 |
| 12 | P9 only; P9 outputs blocked | 104 | 0 | 0 | 0 | 0 |
| 12 | P9 + taste; taste outputs blocked | 48,045 | 2 | 11 | 5 | 0 |

Relative to P9-only, adding taste changes pooled left-minus-right activity by +7 Hz in seed 11 and −3 Hz in seed 12. This two-seed panel does not establish a consistent steering direction. In the separately retained [50, 500) ms window, every P9-context condition has zero forward spikes. Seed 12 P9-plus-taste MN9 activity is sustained in that window at 13.3333 Hz; seed 11 remains zero. Blocking taste outputs restores the named readout rates to P9-only values while taste cells continue to spike. Blocking P9 outputs leaves only 104 P9 spikes in each trial and no other spiking cells.

The minimum full-network voltage sampled at 1 ms intervals is −474.388875 mV, in seed 12 P9-plus-taste. Active unblocked trials reach minima between −434.289416 and −474.388875 mV. Finiteness checks pass, but that does not establish physiological plausibility. Interior 0.1 ms membrane minima were not retained; the reported minimum is a sampled statistic, not an exact continuous or every-step extremum.

Each trial consumes 65,000 uniform draws. The common draw sequence is preserved within each seed, and each output-block pair has identical source order, rates, uniforms and candidate event masks. Candidate arrivals, applied voltage increments and actual source spikes are different quantities: for seed 12 P9-plus-taste their totals are 1,219, 1,200 and 1,201 respectively. Applied increments are inferred from the pinned kernel's ordering and same-tick source spike stamps, not directly instrumented writes. Recurrent feedback can change applied masks and source spikes despite matched candidates. The event-partition check is algebraic; independent checks cover RNG progression, source counts, delayed unblocked edge visits and final pending queues. Edge visits are not a claim that every postsynaptic write was accepted during refractoriness.

The [results](../validation/eon-p9-context/results.json) retain all conditions, windows, per-cell source counts, checks and 72 artifact hashes. Their SHA-256 is `5a9a1bf7db56472e43604f687ebab9dd5ee0ee0fbaeb1571e674f4c4bb4ed6cd`. All 606,759 ordered spike events are saved with integer ticks; each trial also has 501 × 25 selected voltage/synaptic/refractory/last-spike samples, 500 full-network summary records, external input arrays, and full initial/final checkpoints. The initial checkpoint precedes input configuration. Per-trial summaries and the aggregate results accompany approximately 30.3 MB of retained data.

The commands used were `.venv/bin/python scripts/assay_eon_p9_context.py --prepare`, followed by `.venv/bin/python scripts/assay_eon_p9_context.py`. Both refuse to overwrite their existing plan or outputs. Reproduction requires an isolated copy with the pinned sources and fresh designated output paths; preserve these receipts. The bounded panel is finished, with no parameter search or additional trial. Its consistency checks establish execution accounting, not biological validity or readiness for body integration; an independent results review precedes that decision.

The subsequent [independent saved-data review](eon-p9-context-independent-review.md) passes 1,483 checks and preserves one corrected reviewer assertion. It confirms exact restoration of the entire non-taste spike stream under taste-output blocking and severe hyperpolarization in a raw checkpoint. The user explicitly cancelled the proposed body integration benchmark; the inhibitory factorial is the next primary work, with no Eon model/default promotion.
