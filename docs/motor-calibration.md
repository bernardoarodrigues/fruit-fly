# Male CNS motor-interface diagnosis

The initial DM1/DM4 sensory-to-motor test exposes a neural-model calibration
problem. The named walking/steering cells exist and are reachable, but the
uniform current-based Shiu transfer drives several of them far below plausible
membrane potentials. Changing a renderer or declaring the highest-rate neuron
a motor command does not resolve this.

Measurements are saved in
[`validation/motor-connectivity.json`](../validation/motor-connectivity.json)
and reproduced by `scripts/audit_motor_connectivity.py`. The unchanged full
male graph was used: 166,700 neurons, 25,582,938 edges, 0.275 mV per signed
contact, default Shiu membrane/synapse constants, seed 42. Three 500 ms conditions
applied independent per-cell Poisson stimulation to the annotated DM1/DM4 ORNs,
with left/right rates 150/150, 150/5 and 5/150 Hz. All spikes were counted;
selected membrane/synaptic states were sampled each 1 ms.

## Observed cause of silence

Every inspected candidate had an all-positive structural path from DM1/DM4
ORNs, usually two or three edges long. This proves reachability only. The
bilateral 150 Hz test showed:

| Type | Left/right firing rate | Left/right mean membrane voltage | Interpretation |
|---|---|---|---|
| DNg97 / oDN1 | 0 / 0 Hz | −164 / −156 mV | Strong modeled inhibition |
| DNa01 | 0 / 0 Hz | −97 / −96 mV | Strong modeled inhibition |
| DNa02 | 0 / 0 Hz | −120 / −151 mV | Strong modeled inhibition |
| DNp09 / P9 | 0 / 0 Hz | −109 / −91 mV | Strong modeled inhibition |
| DNb05 | 236 / 256 Hz | −51 / −51 mV | Highly active, near refractory-limited saturation |
| DNg34 | 96 / 58 Hz | −50 / −50 mV | Active walking-correlated candidate |

DNg97's dominant active inhibitory sources included VES104, GNG127 and CB0677.
DNa02's included PS059, MBON31 and MBON32. For left DNg97, the excitatory and
inhibitory weight-times-rate sums were approximately +11,731 and −35,551 mV/s.
Multiplying the net −23,820 mV/s by the 0.005 s synaptic decay predicts about
−119.1 mV of mean synaptic drive, close to the observed −119.4 mV. The
current-based membrane equation can then push voltage arbitrarily far below
an inhibitory reversal potential because it has no such reversal term.

This is a diagnostic calculation, not an identification of biological inhibitory
strength. It ignores postsynaptic event rejection during refractory intervals,
and state samples miss sub-millisecond peaks. It nevertheless explains why
these outputs are silent without invoking missing graph paths. “All states are
finite” is an insufficient physiological stability criterion for this model.

The original Shiu numerical implementation is behaving as intended, as verified
on its original graph. Transferring a shared point-neuron parameter set and
global transmitter signs to a larger brain-and-cord graph has not been validated.
The sign of glutamatergic or modulatory effects may depend on postsynaptic
receptor expression. A neurotransmitter class alone is not a complete
physiological connection model. Source signs should not be flipped merely to
obtain movement.

## Motor identities and evidence

The male annotation table distinguishes DNg97/oDN1 (body IDs 13805 and 230783)
from DNp09/P9 (10783 and 11177). These are not aliases of one pair.
P9 activation can initiate forward walking with ipsilateral turning and has
been studied in male pursuit; see [Bidaye et al., Neuron 2020](https://pmc.ncbi.nlm.nih.gov/articles/PMC9435592/).
The oDN1 walking-promotion pathway is discussed in [Sapkal et al., Nature 2024](https://www.nature.com/articles/s41586-024-07854-7),
which also demonstrates distinct mechanisms for inhibiting walking and arresting
leg stepping. A single positive “walk” scalar cannot represent these mechanisms.

DNb05 has published ipsiversive steering correlations, alongside DNa01,
DNa02 and DNg13; DNb06 has contraversive correlations. DNg34 was reported to
have a graded relationship with forward velocity. This makes DNb05 and DNg34
reasonable candidates for an explicitly fitted readout, with separate evidence
levels for correlation and causal activation. The primary study is [Braun et al.,
Cell 2024](https://www.sciencedirect.com/science/article/pii/S0092867424009620)
([full manuscript](https://pmc.ncbi.nlm.nih.gov/articles/PMC12778575/)).
Its causal work on DNa02/DNg13 also shows that steering acts through distinct
leg gestures and phase-dependent effects, which a simple speed/turn adapter
does not reproduce.

DNa02 also integrates heading-related PFL pathways and multimodal signals.
Its left/right population difference and antagonistic input organization are
studied in [Rayshubskiy et al., eLife](https://elifesciences.org/articles/102230/figures)
and [Westeinde et al., Nature 2024](https://www.nature.com/articles/s41586-024-07039-2).
There is no evidence here that DM1/DM4 activation alone, without calibrated
state or other sensory pathways, should directly generate the desired output.

High activity alone is insufficient for assigning DNg33, DNp32 or DNp12 to
forward walking. In this import both DNp32 cells have uncertain transmitter
annotations and zero outgoing model sign. Their recorded spikes can be high
even while the engine deliberately gives them no outgoing synaptic effect.

## Bilateral sensitivity remains unproven

The DNb05 right-minus-left rate difference was +20 Hz for bilateral stimulation,
+20 Hz for stronger left stimulation and +24 Hz for stronger right stimulation.
DNg34 remained more active on the left in all three conditions. These diagnostic
single-seed results are dominated by a persistent side bias; they do not establish
reliable directional odor coding. A decoder that simply replaces silent DNa01/02
with DNb05 could make a body turn without passing a mirror-symmetric chemotaxis
test. The result must be evaluated across seeds, reflected stimuli and held-out
odor histories before claiming odor navigation.

Odor-driven walking also depends on temporal changes and receptor combinations,
not solely on the instantaneous concentration. Relevant primary behavioral
calibration data and methods are available from [Tao et al., Nature Communications
2023](https://www.nature.com/articles/s41467-023-42613-8) and
[Tao et al., PLOS Computational Biology 2020](https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1007718).
These offer actual response targets for future fitting and holdouts; their
results have not been numerically imported in this diagnostic.

The next numerical extension is therefore a separately named conductance-based
backend with excitatory/inhibitory reversal potentials, alongside the unchanged
Shiu replication backend. Reversal potentials bound synaptic hyperpolarization,
but they do not by themselves establish natural action selection. Sensory input
amplitudes, spontaneous activity, receptor-specific signs, population readouts
and behavioral calibration remain explicit research tasks.
