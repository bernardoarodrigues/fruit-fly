# Prospective review: inhibition and refractory handling

**Design advice only; no experiment was run.** Implementation is paused while the Eon embodied-emulation work is rechecked following the user's request. That comparison may supersede this proposal. This note changes no runtime, parameters, source recordings, results or previously frozen plans.

The starting evidence is the [381-check independent replay](/Users/bernardo/Documents/Code/fruit-fly/docs/negative-voltage-replay-independent-review.md), its [producer](/Users/bernardo/Documents/Code/fruit-fly/scripts/negative-voltage-replay.py), and the two separate kernels in [neural.py](/Users/bernardo/Documents/Code/fruit-fly/fruitfly/neural.py) and [conductance.py](/Users/bernardo/Documents/Code/fruit-fly/fruitfly/conductance.py). The replay exactly reconstructs the signed-current model under recorded inputs. It does not validate the extreme negative model voltages biologically. Switching directly to the existing full conductance backend changes excitation and refractory handling as well as inhibition; that comparison cannot isolate the inhibitory driving-force change.

The minimal proposed factorial has four arms, run separately for each of the three retained 12 s source histories and each target, 67052 and 13314:

| Arm | Inhibitory voltage dependence | Synapse handling during/after spikes |
|---|---|---|
| C0 | Original signed current-like state | Original freeze, reject unavailable deliveries, reset synapses |
| C1 | Same current-like equation | Always decay, receive available source deliveries, retain synapses |
| H0 | Inhibition-only driving force; positive input remains current-like | Original freeze/reject/reset package |
| H1 | Same inhibition-only driving force | Always decay/receive/retain package |

The second factor is explicitly a **three-part handling package**, not an isolated test of refractory duration or event rejection alone. C1 is necessary: H1 versus C0 would conflate the two factors. Report H0−C0 and H1−C1 within each history, plus the interaction `(H1−C1)−(H0−C0)`. Do not pool histories or declare any arm biologically correct from a preferred voltage or spike count.

**Fixed input boundary.** Use the raw source-index/timestamp stream and complete incoming-edge inventory, including zero-weight edges and events the original target rejected. Do not use only the earlier accepted-event arrays. Preserve original source order, each source's separate target edges, float32 graph-weight bytes promoted to float64, the 18-tick delay, and source-output blocking evaluated at delivery. The known source mask remains external and fixed within each original condition; its per-interval membership was established from the frozen design, aggregate journal checks and final full mask, not archived as a complete mask at every interval. Keep that provenance limitation.

Recompute target availability and threshold decisions independently in every arm. A changed target spike train must never regenerate self/cross/recurrent input: even source spikes whose IDs equal either target stay the original exogenous recordings. Both targets had no direct Poisson or current drive; retain that absence and make no RNG draws. Partition each potential edge delivery once into beyond-horizon, source-blocked, target-unavailable, or accepted, preserving the original precedence for in-horizon events. Beyond-horizon events remain pending without pretending a future source-mask decision was observed. Retain ordered accepted/rejected tick/edge IDs so altered acceptance is visible.

**Equations and normalization.** Keep `Δ=0.1 ms`, `τm=20 ms`, `τs=5 ms`, `E_L=Vreset=−52 mV`, threshold `−45 mV`, refractory 22 ticks and delay 18 ticks. Initial voltage is `E_L`, synaptic states zero and last-spike tick `−2**60`. Current arms use the original signed state `s`:

```
τm dv/dt = E_L − v + s,        ds/dt = −s/τs.
```

Hybrid arms retain a nonnegative positive effective-current state `p` and add nonnegative inhibitory leak ratio `h`:

```
τm dv/dt = E_L − v + p + h(E_I − v)
dp/dt = −p/τs,               dh/dt = −h/τs.
positive edge: Δp = float64(w_float32)
negative edge: Δh = −float64(w_float32) * (1 / 23)
E_I = −75 mV; all gains = 1.
```

At rest, each negative event gives the same initial signed driving term as its original weight. This is an engineering normalization, not measured nS or pA. Preserve the canonical single signed state and original operation/event order in C0: replacing it with separate positive/negative sums can break bitwise parity through floating-point summation alone. Any split-state bookkeeping should report that roundoff difference instead of replacing the baseline. H arms need no excitatory reversal or new excitation/input amplitude.

The existing `−75 mV` prior is fixed to avoid another factor. It is **not identified for these two targets** by the [recovered reversal supplement](/Users/bernardo/Documents/Code/fruit-fly/docs/wilson-gaba-reversal-source.md). That source's solution-dependent somatic responses, censored endpoints and holding limitation must remain distinct from native synaptic reversal. The [inhibitory literature audit](/Users/bernardo/Documents/Code/fruit-fly/research/13-antennal-lobe-inhibitory-constraints.md) likewise does not identify per-contact conductance, receptor complement or inhibitory kinetics for these exact cells. No fast/slow receptor mixture, depression, gain fitting or chloride dynamics is added here.

**Tick semantics.** At tick `k`, determine availability by `k−last_spike >= 22`. Integrate an available voltage from the states saved before this tick, then test strict `v > −45`. Record a crossing at `k*0.1 ms`, as the original source does, and mark it unavailable for original-package event delivery. Deliver source events stamped `k−18` after threshold testing. Apply reset after delivery. Save the resulting state at array index `k+1`; the original threshold stamp and post-transition state index must not be silently shifted to a new clock convention.

In package 0, unavailable voltage and synapses freeze; available synapses decay during integration, newly fired/unavailable targets reject deliveries, and a spike clears all synaptic states along with resetting voltage. In package 1, voltage is held at reset while refractory, every synaptic state decays every tick, all unblocked arrivals are accepted even on the firing tick, and reset changes voltage only. Threshold checks stay on the same macro clock. No target state is clamped to a reversal to conceal integration error.

**Numerical references and acceptance evidence.** C0 must match all original per-tick voltage/synaptic states, spike stamps, endpoint bookkeeping and eligibility arrays bitwise. For C1, retain the same exact linear transition coefficient and test isolated impulses, no input, constant drive if included in an isolated numerical check, and a pulse arriving on the firing/refractory/release boundary. Equivalent tests for H0/H1 must distinguish decay, acceptance and reset behavior. These are synthetic numerical checks, separately labeled from the recorded-input trials.

A possible H integrator freezes `h` at its exponentially decayed midpoint while integrating positive `p(t)` exactly. With `λ=(1+h_mid)/τm`, `ν=1/τs`, `v∞=(E_L+h_mid E_I)/(1+h_mid)`, its available-step update is:

```
v_next = v∞ + (v−v∞) exp(−λΔ)
       + (p0/τm) [exp(−νΔ)−exp(−λΔ)]/(λ−ν).
```

Use the `λ=ν` limit `Δ exp(−λΔ)`, stable `expm1` evaluation nearby, and the exact source operation order for `h=0`. Ordinary midpoint freezing of `p` would alter even the excitation-only impulse response. This scheme's nominal second-order accuracy is **not uniform at extreme conductance**: when `h≫1` with `p/h` appreciable, the true endpoint approaches `E_I+p0/h0`, while frozen midpoint `h` with decaying `p` approaches approximately `E_I+(p0/h0)exp(−Δ/(2τs))`. Bounds alone therefore cannot establish accuracy.

An independent time-varying reference is available from an integrating factor. For one available interval, let `y=v−E_I`, `D=E_L−E_I=23`, and

```
A(t) = t/τm + h0 τs/τm [1−exp(−t/τs)]
y(t) = exp(−A(t)) y0
     + (1/τm) ∫₀ᵗ exp[−(A(t)−A(u))] [D+p0 exp(−u/τs)] du.
```

Evaluate this nonnegative kernel with a controlled quadrature/reference solver and verify its own error estimate. At very large `h`, rescale or explicitly resolve the endpoint boundary layer; naive quadrature across the whole interval can miss it. Validate against passive and constant-conductance analytic solutions, the exact no-inhibition impulse response, the `λ=ν` limit, and high-conductance cases with both negligible and appreciable `p/h`. Compare this reference to a second independent high-accuracy scalar ODE solver on the predeclared synthetic grid. These references do not create new source spikes.

With nonnegative `p,h` and the stated initialization/reset, H has a lower bound `v>=E_I`. It has **no universal upper bound of 0 mV**, because positive excitation remains current-like. Within an available event-free interval, a useful upper bound is `max(v0,E_L+p0)`. Preserve pre-threshold as well as post-reset voltage so resets cannot hide overshoot or nonfinite intermediates. Report maximum `h`, effective stiffness `(1+h)Δ/τm`, lower-bound violations, one-step reference errors and threshold margins.

If comparing internal steps `0.1/0.05/0.025 ms`, keep delayed impulses and threshold/refractory decisions on the original 0.1 ms macro clock. Otherwise the comparison also changes event phases and threshold timing. Audit selected steps from each arm's own saved preceding state against the high-accuracy reference; this isolates local integration error from accumulated threshold/acceptance differences. Predeclare selection rules, including largest conductance, closest threshold margin and regular temporal samples, before producing results. A separate reference with a fixed recorded arm-specific reset/acceptance schedule can characterize accumulated conditional error. Label that conditioning; never impose original C0 target spikes on the other primary arms.

The eventual frozen plan should specify numerical tolerances, integration/reference methods, sampling rules, source hashes and all failure-retention rules before execution. Save full per-tick states, pre-threshold voltages, availability/firing decisions, event disposition and final pending evidence for all four arms. No numerical failure should trigger silent gain changes, source replacement, event dropping or selection of a preferred arm. Any conclusion is conditional on these recorded input histories; it does not establish how a modified recurrent brain, body or biological fly would behave.
