# Minimal KC waveform candidate: independent mathematical review

2026-09-05. For implementation design only; no production imports, neural time integration, fit to raw recordings, runtime changes or promotion. This note uses the two retained primary sources in [research 21](../research/21-pn-kc-physiology-calibration.md), especially Turner 2008 pp.735–736 and 739–740. Its source receipt remains unchanged. The scalar numbers below were calculated from closed-form waveforms and bracketed threshold/root equations with SciPy `brentq`; they are conditional parameter identification from reported means, not a new electrophysiological fit.

**Implement the double-exponential-current / effective-membrane cascade as a deliberately falsifiable minimal candidate. It cannot match all four central timing targets when both reported decay constants are interpreted as late exponential tails.** Keep Turner's original finite-transmitter conductance model as a separately labeled historical control. Neither supplies the >200 ms somatic intrinsic response.

## Candidate and identifiable quantities

Use milliseconds and baseline-relative voltage `u = V − V0`. For one event at time zero:

\[
k(t)=\big(e^{-t/\tau_d}-e^{-t/\tau_r}\big)\mathbf 1_{t\ge0},\qquad
0<\tau_r<\tau_d,
\]
\[
\dot u=-u/\tau_m+a\,k(t),\qquad u(0)=0.
\]

Here `k` is dimensionless and is **not peak normalized**; `a` has units mV/ms. A physiological RC interpretation would make it an effective current-amplitude/capacitance ratio. Neither factor is individually identified. No spike threshold, reset, refractory rule or APL parameter enters this subthreshold identification.

For distinct time constants define

\[
J(\tau,t)=\frac{e^{-t/\tau}-e^{-t/\tau_m}}{1/\tau_m-1/\tau},\quad
u(t)=a\,[J(\tau_d,t)-J(\tau_r,t)].
\]

At `τ = τm`, use the limit `J = t exp(−t/τm)`. Use `expm1` or equivalent stable divided differences near equal constants; subtracting nearly equal exponentials directly is unsafe. The current peak is at

\[
t_{I,\mathrm{peak}}=\frac{\tau_r\tau_d}{\tau_d-\tau_r}\log\frac{\tau_d}{\tau_r}.
\]

Define each 10–90% rise **relative to that waveform's own baseline and peak**, choosing the first crossings on its rising limb. The voltage peak solves `k(t) − [Jd(t)−Jr(t)]/τm = 0`. These definitions have no arbitrary onset displacement or decay-fitting window.

Under the declared asymptotic-tail interpretation:

1. Set `τd = 2.8 ms` from EPSC decay. Solve `t90(k)−t10(k)=0.9 ms` for `τr` in `(0,τd)`. Check admissibility and whether multiple roots exist before treating the identification as unique; do not introduce extra delay to alter a rise *duration*.
2. For positive current gain, the voltage's slow tail has time constant `max(τm,τd)`. A target of 11.5 ms therefore sets `τm=11.5 ms` in this family. Predict the EPSP rise; do not tune `τm` a second time against the 2.1 ms target while still claiming the 11.5 ms tail is matched.
3. Set `a = 1.4/max_t[Jd−Jr]` to match the reported mean EPSP amplitude. This identifies an effective voltage gain only. It does not identify pA, total capacitance, nS per graph contact, number of release sites or release probability. A peak-normalized `k` requires a different numerical gain.

A bracketed analytic calculation gives:

| Quantity | Conditional value |
|---|---:|
| `τr`, with `τd=2.8 ms` | 1.0019853605 ms |
| Current peak time | 1.6034872268 ms |
| Current `t10`, `t90` | 0.0588073662, 0.9588073662 ms |
| `τm` | 11.5 ms |
| Predicted voltage peak time | 6.4822279050 ms |
| Voltage `t10`, `t90` | 0.6950157866, 4.2706071851 ms |
| **Predicted EPSP rise** | **3.5755913985 ms**, versus reported 2.1 ms |
| Unnormalized-current gain `a` for a 1.4 mV EPSP | 1.2523575697 mV/ms |

The current's peak is 0.3621813055 in this normalization. Amplitude changes leave every normalized rise/decay metric unchanged. Even the zero-current-rise limiting example (`k=exp(−t/2.8)`, same 11.5 ms membrane) has a 2.8938788582 ms EPSP rise; this limiting example is not presented as a proof covering arbitrary current kernels.

This is incompatibility of the **central descriptors under a specified model/metric**, not rejection of the paper or of PN→KC physiology. EPSP and EPSC events came from different small cohorts; the reported dispersions are not paired measurements, and no covariance or exact decay fitting window is supplied. The reported ranges cannot be turned into a box of independently interchangeable parameter values or formal acceptance probabilities.

## Decay fitting is a material ambiguity

The paper reports an exponential fit to the falling phase, not an explicitly asymptotic fit with a stated start/end window. A difference/sum of exponentials has a curved log-decay near its peak. Thus `τd=2.8` and `τm=11.5` above are explicit assumptions, not parameter values uniquely compelled by the published fit summaries.

For the candidate above, instantaneous voltage log-slope decay `−u/u′` is approximately 40.26, 14.59, 12.13, 11.54 and 11.50 ms at 1, 5, 10, 20 and 40 ms after its peak, respectively; it diverges at the peak. A finite-window exponential fit can therefore report a constant larger than the true 11.5 ms tail. Choosing a different finite fitting window after seeing a mismatch would change the question.

Before any dataset fit, freeze one primary decay metric and its baseline handling, window, weighting, and single-event versus averaged-waveform calculation. Use reported tail matching as an explicitly conditional first comparison, or obtain the original fit protocol / perform a separately planned graphical extraction. Do not silently equate a 1/e crossing, half-width, least-squares exponential fit and asymptotic pole. A fitted exponential of an average waveform need not equal the average of individual fitted exponentials. Fig.3D lacks an absolute EPSC amplitude scale, so only normalized current kinetics can currently be compared.

## Original Turner equations are a historical control, not the same candidate

The paper uses

\[
C_m\dot V=-g_L(V-E_L)-\bar g\,O(t)(V-E_{syn}),\qquad
\dot O=\alpha(1-O)T(t)-\beta O,
\]
\[
T(t)=A\mathbf1_{0\le t\le w},\quad
C_m=1\,\mu F/cm^2,\ g_L=0.089\,mS/cm^2,\ E_L=-57.8\,mV,
\]
\[
E_{syn}=0,\ A=0.5,\ w=0.3\,ms,\alpha=2.5\,ms^{-1},\beta=0.4\,ms^{-1};
\quad\bar g=0.05\text{ or }0.04\,mS/cm^2.
\]

These are the **authors' model settings**. The membrane ratio is 11.235955 ms (rounded model settings; the text says tuned to an 11.5 ms EPSP decay). The conductance gate after the transmitter pulse decays with `1/β=2.5 ms`. During the pulse, `O=αA/(αA+β) × [1−exp(−(αA+β)t)]`. At a fixed voltage clamp and without an additional recording filter, its 10–90% rise is **0.2382377 ms**, bounded within the 0.3 ms pulse, rather than 0.9 ms. This follows algebraically; the historical model does not exactly realize every printed central waveform descriptor. Its varying driving force also makes it different from an imposed-current cascade. Do not change its listed settings and still label it an exact reproduction of the original model.

The source's somatic >10 GΩ and >200 ms current-injection observations are not identified by its conductance *density* values. Total cell area/capacitance is missing. A single passive point cell with a fast excitatory current and `τm>200 ms` has a slow positive voltage tail >200 ms, so it cannot also have an 11.5 ms asymptotic EPSP decay. Any effective synaptic approximation must report that somatic constraint as unmet, rather than quietly replacing the measurement. More compartments, voltage-dependent currents or an additional effective transfer pathway would need a new declared model and additional constraints; these summaries do not identify them.

## Small finite checks for today's implementation

- Verify zero input remains at the declared baseline, causal support, positive current/EPSP, and decay to baseline without a hard state reset. No threshold or APL tuning can rescue a subthreshold waveform mismatch.
- Compare analytical voltages with an independent high-accuracy integration for one event; check rising crossings/peak and stable equal-time-constant limits. Verify the declared event-arrival convention and interpolation error; 0.1 ms output sampling alone is coarse relative to the 0.9 ms current rise.
- Report all five descriptors (EPSC rise/decay, EPSP rise/decay/amplitude), with the original control and each candidate. Preserve the predicted rise mismatch; do not optimize only the successful descriptors and omit the fourth timing target.
- Keep amplitude identification, baseline/threshold constraints and the somatic current-response mismatch separately visible. Current-clamp holding voltage is not an independently calibrated resting-potential parameter.
- Reserve Gruntman's first-claw amplitude distribution and measured multi-input voltage responses for later evaluation; synthetic exact PN timing, gain, APL absence and graph-to-claw mapping remain engineering choices. Do not fit a four-claw firing rule or recruitment fraction to compensate for this local mismatch.

A phenomenological voltage kernel could be given independent rise/decay/amplitude to match the EPSP alone; a separate current kernel could match the EPSC. That is a descriptive two-observable surrogate, **not** a self-consistent one-compartment current-to-voltage mechanism. It may be a useful explicit failure comparator, but it does not solve parameter identification.
