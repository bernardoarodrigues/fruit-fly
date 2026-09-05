# Independent review of the isolated ORN–PN transfer audit

The saved anatomy and isolated numerical responses pass **74 independent checks** in [the receipt](../validation/orn-pn-transfer-independent-review.json). The [reviewer](../scripts/review_orn_pn_transfer.py) reads the graph arrays directly and uses SciPy matrix exponentials for the linear impulse response. It imports neither the producer nor the neural runtime and runs no simulation or parameter fit.

All frozen source and artifact hashes match. Independent exact type/class selection reproduces 174 antennal ORNs, 14 adPNs and two separately retained other PNs. Independent tokenization reproduces the wider alias candidate set; 161 optic `Dm4`/`Dm6` case collisions remain excluded. Thirteen ORNs carry the literal annotation `unknown` for root side; these are retained, not assigned a side.

Direct CSR lookup verifies all 2,784 possible pairs, including absent connections, graph positions, contact counts and exact float32 weights. The same-glomerulus adPN subset contains 616 actual edges and 25,884 contacts, with 2–155 contacts per edge. Its calculated passive single-spike peak spans 0.08662–6.71302 mV, below the unchanged 7 mV threshold gap from rest. This calculation concerns an isolated postsynaptic point neuron without concurrent input.

The independent propagator is `expm(A t)`, where `A = [[−1/20, 1/20], [0, −1/5]]` in milliseconds and the state is voltage displacement plus synaptic state. A bounded numerical extremum search also reproduces the producer's 9.24196 ms peak time after delivery. All eight saved isolated cases match their passive voltage/synaptic trajectories, ordered spike stamps and reset behavior. The largest errors are below 1.8e−13 mV for voltage and 4.6e−13 mV for synaptic state. The synthetic 161-contact input stays below threshold; 162 contacts produce the saved 10.4 ms spike stamp. Those controls are numerical boundaries, not additional anatomical edges.

The 1.8 ms delivery stamp occurs after that tick's integration; the first saved post-delivery state is at 1.9 ms. The review preserves this scheduling distinction. Engine construction and traversal counts remain producer-reported execution evidence; the saved arrays independently establish the specified isolated response.

No check establishes an equivalence between EM contacts and release sites, female somatic measurements and male point-neuron voltage, or isolated responses and a recurrent network. The result does not justify a global gain change or explain the full-network physiological failure by itself.

Reproduce the saved-data review with `.venv/bin/python scripts/review_orn_pn_transfer.py`. The command rewrites only its review receipt.
