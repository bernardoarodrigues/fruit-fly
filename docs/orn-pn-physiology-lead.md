# Next physiological constraint: ORN-to-PN transmission

[Kazama & Wilson (2008)](https://doi.org/10.1016/j.neuron.2008.02.030) studied female flies aged 2–7 days. Minimal antennal-nerve stimulation at 0.033 Hz gave pooled somatic uEPSCs of **29.0 ± 2.6 pA (n=45)** and uEPSPs of **6.19 ± 0.45 mV (n=23)**; errors are SEM. The compared antennal glomeruli were DM6, VM2, DL5 and DM4. Their VM7 recordings instead isolated lateral antennal excitation of palp PNs. At 7 Hz, responses depressed by roughly 40%; Figure 8 uses four seconds of 7 Hz stimulation before 500 ms trains at 20 or 50 Hz.

The [supplement](https://kazamalab.riken.jp/pdf/Neuron_Kazama%26Wilson_2008_supplement.pdf) includes VM2 recovery after strong stimulation (Figure S8), offering a separate temporal constraint. Paper and supplement are downloaded locally with [hashes and access record](../validation/orn-pn-physiology-sources.json).

These observations motivate an isolated synapse audit before changing the male model. Current `fruitfly/neural.py` uses fixed signed edge strengths and exponential synaptic decay; decay of an existing current is different from depression of newly evoked responses. First identify the corresponding male ORN/PN populations and examine the present single-spike transfer. Then reproduce a published depression/recovery model or fit explicitly separated training/held-out electrophysiology, preserving sex, compartment and preparation uncertainty.

Do not substitute these pooled somatic values for every connectome contact, equate a neuron-pair edge with one vesicle release site, or transfer them directly to VM7d. No parameter or runtime change is made by this note. This is a quantitative research lead, not a resolved explanation of the whole-network voltage failure.
