# Sensory neuron mapping evidence

Research checked 2026-09-04/05. This file separates published cell-type assignments,
release-specific neuron identifiers, and implementation proposals. It does not
establish that the simulator reproduces the corresponding behavior.

## Taste: use the final 2026 companion paper

Primary source: Tastekin et al., [The complete gustatory connectome of adult
Drosophila reveals how taste guides feeding, foraging, and social
behavior](https://www.cell.com/cell/fulltext/S0092-8674(26)00943-8), Cell 189,
5527–5551.e5 (2026), DOI
[10.1016/j.cell.2026.08.016](https://doi.org/10.1016/j.cell.2026.08.016).
The final full text was read in the browser; institutional login was not required.
It supersedes the coarse labels in older FlyWire annotations. The earlier
[preprint](https://doi.org/10.1101/2025.08.25.671814) has a different title.

The assignments below are the authors' anatomical/receptor-driver matches and
connectivity-supported interpretations, not direct physiological measurements
of every reconstructed neuron.

| MaleCNS type | Supported assignment | Exact evidence location |
| --- | --- | --- |
| LB3a | Labellar water; ppk28 match | [Paragraph p0125](https://www.cell.com/cell/fulltext/S0092-8674(26)00943-8#p0125), Fig. 2D–E |
| LB3b, LB3c | Labellar sweet; Gr64f match | p0125, Fig. 2D–E |
| LB3b | Also attractive low salt; Ir56b match | p0125 |
| LB3d | Putative aversive high salt/heavy metals; Ir7c/ppk23/Ir47a matches | p0125 |
| LgAG2 | Appetitive leg ascending; Gr61a match | [p0175](https://www.cell.com/cell/fulltext/S0092-8674(26)00943-8#p0175), Fig. 3J; p0235/Fig. 5 |
| LgLG4 | Appetitive leg local; Gr64f/Ir56b matches | [p0205](https://www.cell.com/cell/fulltext/S0092-8674(26)00943-8#p0205), Fig. 4J |
| LgLG3 | Sugar candidate; indirect Dandelion-partner inference | p0205 |
| PhG1a–c | Pharyngeal Gr64e match | p0150, Fig. 3E |
| PhG3, PhG4 | Pharyngeal water; ppk28 match | p0150, p0320, Fig. 3E |
| LgAG1 | Gr33a/Gr32a; aversive taste/contact pheromones | p0175 |

LgAG2 and LgLG4 converge on feeding pathways; LgLG4 has strong modeled
connectivity to MN9/MN4a/MN6/MN8/MN11D/CEM (p0365/Fig. S18). The paper does **not**
supply an exact water-specific LgAG assignment. LgAG4/7 were unclustered; LgAG3/8
and LgAG6/9 belong to putative aversive groups (p0230–p0240).

### Implementation interpretation

- For an initial sugar-contact assay, select **LgAG2 and LgLG4** at the contacting
  leg. Their evidence is stronger than LgLG3's functional inference. Model the
  stimulus as generic appetitive sugar, since this evidence does not give a
  calibrated concentration-response curve or distinguish all sugar molecules.
- Stimulate **LB3b/c** only when sugar contacts the labellum. Stimulate **LB3a**
  only when water contacts the labellum. Whole-`LB3*` sugar stimulation mixes
  sweet, water, and aversive candidates and should be rejected.
- Pharyngeal stimulation belongs downstream of actual intake. Turning on
  PhG3/4 merely because a foot touches water would introduce a false sensory
  shortcut. Until a water-specific tarsal mapping is available, leave that
  channel explicitly unassigned rather than borrowing sweet leg neurons.
- A ground-contact sensor needs both geometry and chemical overlap. A foot
  suspended over food should not trigger taste. Nerve and root-side metadata
  support leg selection; they do not identify individual tarsal bristles or
  distal segment coordinates.
- Keep receptor mappings in a curated provenance table: the released
  `receptorType` column is null for these neurons. Do not overwrite that source
  column with inferred receptor identities.

## Exact local MaleCNS release mappings

Read from the public [v1.0 minconf-0.5 body-annotation Feather
file](https://storage.googleapis.com/flyem-male-cns/v1.0/connectome-data/flat-connectome/body-annotations-male-cns-v1.0-minconf-0.5.feather),
saved at `data/raw/body-annotations-male-cns-v1.0-minconf-0.5.feather`.

SHA-256:
`2177e246113e4cfbf1e7772ec37c6da1955ff22e8063d0b1f833101f99a9a3b2`.
Counts below are annotation rows, before any graph-specific filtering.
Use `rootSide` for these sensory neurons; their `somaSide` is null.
`ProLN` = foreleg, `MesoLN` = middle leg, `MetaLN` = hindleg.

| Type | Leg | Side | bodyId values |
| --- | --- | --- | --- |
| LgAG2 | Fore | L | 87710, 92929 |
| LgAG2 | Fore | R | 91221, 526151 |
| LgAG2 | Middle | L | 91302, 219573 |
| LgAG2 | Middle | R | 93294, 94367 |
| LgAG2 | Hind | L | 162704 |
| LgAG2 | Hind | R | 123191, 151556 |
| LgLG4 | Fore | L | 814336, 815749, 817031, 817173, 817565, 817849, 818080, 863321, 1057442452 |
| LgLG4 | Fore | R | 811874, 815267, 821083, 881519, 914315, 935121, 1050190015 |
| LgLG4 | Middle | L | 810811, 815872, 816396, 827154, 844312, 881126, 941022, 1338931584 |
| LgLG4 | Middle | R | 809227, 809833, 810550, 825524, 912794 |
| LgLG4 | Hind | L | 816151, 820780, 822246, 909028, 913195, 1050291683 |
| LgLG4 | Hind | R | 812898, 814362, 815989, 819335, 819719, 820809, 911351, 933183 |

Type counts: LgAG2 11; LgLG4 43; LB3a 17; LB3b 11; LB3c 23; LB3d 26;
PhG1a/b/c 2/2/4; PhG3 2; PhG4 4. Type filters should match exact names.
One LB3c row (957530, R) lacks `entryNerve`; do not silently discard it when
selecting by known type, or invent the missing field.

Reproduce the leg mapping from the frozen file:

```python
import pyarrow.feather as feather
annotations = feather.read_table(
    "data/raw/body-annotations-male-cns-v1.0-minconf-0.5.feather"
).to_pandas()
selected = annotations[annotations.type.isin(["LgAG2", "LgLG4"])]
for (kind, nerve, side), group in selected.groupby(
    ["type", "entryNerve", "rootSide"]
):
    print(kind, nerve, side, sorted(group.bodyId.tolist()))
```

### Annotation-version trap

The [FlyWire annotation repository](https://github.com/flyconnectome/flywire_annotations)
at commit `8587524c1748ce5ef2080822a2fc890fc03bf597` has broad labels such as
`LB3 → sugar/water`. The final Cell paper splits this into the types above, and
also notes reassignment of previous LB2/LB3 labels (p0130). Those broad cross-dataset
labels are not a safe substitute for the MaleCNS type names. An older v0.9
explorer also gives different type counts; the table here uses local v1.0 data.

## Walking and steering readouts

| MaleCNS type | L bodyId | R bodyId | Evidence and interpretation |
| --- | --- | --- | --- |
| DNp09 / P9 | 10783 | 11177 | Forward-walking-associated command-like pair; useful direct-stimulation calibration target |
| DNa02 | 523769 | 10360 | Steering-associated pair; bilateral activity difference is a candidate turn readout |
| DNa01 | 10442 | 10760 | Identifiers verified, but do not assume an interchangeable DNa02 readout |
| DNp01 / Giant Fiber | 10010 | 10001 | Escape pathway; not a generic forward-walking channel |

IDs and sides are from the same annotation file, using `somaSide` for these DNs.

Primary functional sources:

- Bidaye et al., [Two Brain Pathways Initiate Distinct Forward Walking Programs
  in Drosophila](https://pubmed.ncbi.nlm.nih.gov/32822613/), Neuron (2020),
  DOI 10.1016/j.neuron.2020.07.032. P9 is a forward-walking pathway with contextual
  steering and courtship relevance. Activating it tests motor coupling, not
  food-seeking from sensory input.
- Braun et al., [Descending networks transform command signals into population
  motor control](https://www.nature.com/articles/s41586-024-07523-9), Nature
  (2024), DOI 10.1038/s41586-024-07523-9. DNp09 recruits other DNs; full forward
  walking depends on that network. The paper's experiments used female flies.
  A scalar DNp09-to-gait decoder is therefore an engineering approximation,
  even if all anatomical downstream neurons are also simulated.
- [Neural circuit mechanisms for steering control in walking
  Drosophila](https://elifesciences.org/articles/102230), eLife,
  DOI 10.7554/eLife.102230. Bilateral DNa02 activity relates to turning; motor
  state matters. Treat sign and gain as quantities to validate against the
  body coordinate convention, not constants supplied by the connectome.

## Hypotheses and next validation

These are proposals derived for this project, not published results:

1. Compare leg-only LgAG2/LgLG4 input with labellum-only LB3b/c input at matched
   sensory drive, measuring feeding MN latency and response. The two contact
   routes should remain distinguishable in the experiment log.
2. Test left/right and fore/middle/hind contact separately. Unequal annotation
   counts should not automatically imply unequal chemical sensitivity; report
   both per-neuron and population drive conventions.
3. Separate an output-readout mute from silencing neurons. A readout mute proves
   that the body depends on the decoder, not that a particular circuit is
   biologically necessary.
4. Document negative sensory-to-walking results. They may reveal missing
   physiological state, sensory transduction, sign/dynamics assumptions, or
   decoder calibration; they do not falsify the biological connectome.
