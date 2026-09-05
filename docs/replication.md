# Shiu reference replication evidence

The local engine has been compared with the original Shiu Brian2 implementation
on a complete source connectome, then used for a selected sugar-GRN/MN9 activation
sweep. Results are in [`validation/shiu/results.json`](../validation/shiu/results.json).
This is separate from the male CNS import and embodied male behavior validation.

## Correct reference release

Both `example.ipynb` and `figures.ipynb` in the pinned [original repository
commit 91bdd1e7](https://github.com/philshiu/Drosophila_brain_model/tree/91bdd1e7dcf193f3e7ca5a8933497fcef63b7960)
select **FlyWire 630**, containing 127,400 neurons and 14,687,178 directed
neuron-pair edges in the supplied model table. All source cells, including
zero-degree neurons, are retained. The figure notebook supplies the exact 21
right-hemisphere sugar GRN IDs and MN9 ID `720575940660219265`; the script reads
these literal assignments rather than inventing a cell-type mapping.

The repository also supplies a v783 model with 138,639 neurons and 15,091,983
edges. However, notebook sugar GRN ID `720575940620900446` is absent from its
completeness table. A v783 run of that exact source experiment is therefore
blocked on a verified release crosswalk. The script rejects the missing ID
instead of deleting an input or assuming a replacement. Source IDs from either
female FlyWire release are also distinct from male CNS body IDs.

The model code and data remain in the separate MIT-licensed reference checkout;
they have not been copied into this repository. The results record the exact
commit and SHA-256 hashes of source code, notebook and data files. The runner
requires that pinned clean source revision. Its local implementation imports
the original `create_model` function for the Brian2 comparison.

## Complete-network numerical comparison

The first comparison replayed exactly the same fixed external voltage events
through both complete graphs for 100 ms. It used the notebook's 21 sugar-GRN
targets and a 150 Hz Bernoulli arrival distribution, seeded at 1000. Brian2's
original neuron equations, graph, refractory behavior and reset code were used
unchanged; only its stochastic input generator was replaced with a
`SpikeGeneratorGroup` replay so that both implementations received identical
events. This distinction matters because they use different RNG algorithms.

| Measurement | Result |
|---|---:|
| External voltage events | 321 |
| Network spikes in each engine | 1,309 |
| Every spike index matches | Yes |
| Every spike timestamp matches within 1e-9 ms | Yes |
| Maximum final membrane error | 2.60e-6 mV |
| Maximum final synaptic-state error | 2.30e-6 mV |
| Local engine wall time | 0.188 s |
| Original Brian2 2.10.1 run wall time | 0.886 s |
| Original graph construction wall time | 0.488 s |

The remaining numerical difference is consistent with local float32 edge
weights versus original Brian2 float64 weights. Acceptance for this comparison
requires identical spike identities/ticks and both final-state errors below
`0.001 mV`; all conditions passed. This numerical tolerance is an implementation
criterion, not a biological accuracy threshold.

An additional **1,000 ms complete-network replay** also passed, covering the
full source trial duration: 3,232 external events produced 13,749 network
spikes in each implementation, with every spike identity and timestamp matching.
Maximum final voltage/synaptic errors were `1.90e-6 / 3.02e-6 mV`. The local
run took 1.994 s and the original Brian2 run took 7.164 s, excluding its 0.442 s
graph construction. This result is recorded as `numerical_parity_1000_ms`.

## Selected activation conditions

The local engine ran 30 independent seeds (1000–1029), each lasting the source
default **1,000 ms**, for sugar-GRN stimulation at 100 and 200 Hz. These are
two conditions from the Figure 1D source sweep; an additional unstimulated
zero-Hz control used the same population configuration. Total simulated time
was 90 s across 90 trials, with 112.14 s of measured neural evolution time.
These runs use the original parameter values and fixed signed-contact graph;
there is no fitted adjustment to the MN9 response.

| Sugar-GRN input | MN9 mean firing rate | Across-seed SD | SEM | 95% t interval on mean |
|---|---:|---:|---:|---:|
| 0 Hz | 0 Hz | 0 Hz | 0 Hz | 0–0 Hz |
| 100 Hz | 68.17 Hz | 4.65 Hz | 0.85 Hz | 66.43–69.90 Hz |
| 200 Hz | 92.63 Hz | 5.17 Hz | 0.94 Hz | 90.70–94.56 Hz |

The unstimulated graph stayed silent and higher GRN drive increased MN9 output
in this test. These results quantify stochastic simulation variability for one
connectome. Thirty random seeds are not thirty biological specimens. This is a
replication of selected source experiment conditions and a qualitative response;
the published figure's numerical response values and raw biological observations
have not been imported, so quantitative empirical agreement remains unverified.
The full source frequency grid, all neuron ablations, 164 experimental predictions,
grooming comparisons, and biological effect-size acceptance tests remain outside
this executed subset.

## Reproduce

Prepare a clean reference checkout at the stated commit, preserving its license:

```
git clone https://github.com/philshiu/Drosophila_brain_model /tmp/fruit-fly-shiu-reference
git -C /tmp/fruit-fly-shiu-reference checkout 91bdd1e7dcf193f3e7ca5a8933497fcef63b7960
.venv/bin/python scripts/replicate_shiu.py \
  --reference /tmp/fruit-fly-shiu-reference --release 630 \
  --duration-ms 1000 --trials 30 --rates-hz 0 100 200 \
  --brian-parity-ms 100 --output validation/shiu/results.json
```

The command needs NumPy, pandas, pyarrow, Numba, Brian2 and joblib in the project
environment. It does not use parallel source trials or require a GPU. One can
raise `--brian-parity-ms` to 1000 to compare the full trial length, or choose
a shorter `--duration-ms` for a clearly labeled smoke experiment. Changes to
duration, trials, rates, input IDs, releases, numerical parameters or sign rules
must remain visible in the saved manifest. A source-connectome numerical pass
does not transfer biological validity to MaleCNS or the physical motor adapter.
