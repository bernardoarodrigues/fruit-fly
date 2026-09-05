# FlyMimic tibia-muscle identifier boundary

The numerical suffixes in `LFTibia_flex_93434` and
`LFTibia_extensor_93932` remain **unresolved author identifiers**. The verified
namespace is the complete FlyMimic/OpenSim muscle name. This review found no
primary declaration making either suffix a FANC, MANC or MaleCNS motor-neuron
ID, and no verified declaration that it is a muscle segmentation ID. Do not
join those bare integers to a neural catalogue.

In the pinned
[FlyMimic source](https://github.com/gizemozd/FlyMimic/tree/9ea1131626cd76f7203b74076ef8f0e9cab30bef),
both strings name `Millard2012EquilibriumMuscle` objects in
`flymimic/assets/models/opensim/best_combined.osim`. The same strings are
preserved in MuJoCo actuator, tendon and attachment-site names. Object names and
their reuse establish a mechanical-source correspondence, not an EM identifier
namespace. The OpenSim file SHA-256 is
`091a173b9cfb26a64228935c6f6ebfc93c26a9425a0b5e5c1bb463c644cb89de`.

The [published methods](https://proceedings.iclr.cc/paper_files/paper/2026/file/222843b731e2c7813291586e2b39fe89-Paper-Conference.pdf)
describe the femoral geometry's X-ray anatomical provenance and the two modeled
MTUs' fast flexor/extensor interpretation, but do not define the numeric
suffixes. The public tree has no segmentation-ID or neuron-to-MTU crosswalk
table. The README's original model-development repository link returned 404
during acquisition and remains unavailable in this bounded follow-up. Neither
exact suffix produced a relevant primary indexed match outside the mechanical
model; unrelated stock numbers are not crosswalks.

The current MaleCNS annotation was independently queried for both exact numeric
tokens in `mancBodyid`; there are **zero matches**. Annotation SHA-256:
`d35c2428957c7f18ce4290f02606d2f99b851381dd63edc3f760483f6c70b9a8`.
That negative query does not establish the suffixes' true origin or prove an
absent correspondence in another release. An author-provided source-ID
definition or an inspectable original segmentation/model-development table is
needed before an exact namespace join can replace the broad motor-class
candidates in [the feasibility audit](musculoskeletal-feasibility.md).
