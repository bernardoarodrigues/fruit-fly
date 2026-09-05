# Sources and attribution

Dependencies and research artifacts retain their respective licenses. Preserve upstream notices when redistributing code, assets or data.

| Source | Use and provenance |
|---|---|
| [MaleCNS v1.0](https://www.janelia.org/project-team/flyem/male-cns-connectome) | Separately downloaded data, CC BY 4.0. Berg et al., Cell 2026, DOI 10.1016/j.cell.2026.08.015. Exact hashes/URLs in data manifest. |
| [FlyGym/NeuroMechFly](https://github.com/NeLy-EPFL/flygym) | Body assets, composition and hybrid gait controller, installed at commit 38c8ec61034cd59bc5ba0de20688d4a3c0000d60. Preserve upstream code and asset notices. |
| [MuJoCo](https://github.com/google-deepmind/mujoco) | Physics/rendering dependency, Apache 2.0; version recorded per run. |
| [Shiu model](https://github.com/philshiu/Drosophila_brain_model) | MIT reference checkout at 91bdd1e7dcf193f3e7ca5a8933497fcef63b7960; unchanged original builder with matched input-event replay. |
| [Eon fly-brain](https://github.com/eonsystemspbc/fly-brain) | Research/code audit only, GPL-2.0-or-later root license noted; code is not copied here. |
| User-provided PDFs | Preserved unchanged; each retains its stated publication license; hashes in research/provided-papers.json. |
| [Lanz et al. model](https://github.com/nagellab/Lanzetal2025) | GPL-3.0 author notebook, downloaded separately and checksum-verified for a bounded reproduction. No model code imported into the full-brain runtime. Pin and protocol in docs/navigation-memory-model-audit.md. |
| [Suver et al. wind data](https://doi.org/10.5061/dryad.k06kh8f) | CC0 primary dataset; local acquisition and measured-fit provenance in docs/wind-calibration.md. The paper has a separate publication license. |
| [Özdil et al. grooming data](https://doi.org/10.7910/DVN/N8ITTG) | CC0 measured kinematic examples; source hashes and numeric transformations in data/grooming/provenance.json. Author analysis code is Apache-2.0 and is inspected separately. |
| [Ispizua, Abe et al. free behavior data](https://doi.org/10.64898/2026.05.03.722293) | Public single-fly HDF5 acquired separately, with observed checksum and original source identity. An explicit data license was not identified; bulk data remain local. The associated code package declares BSD-3-Clause, separate from data terms. |

Morphology acquisition has separate specimen, license and checksum provenance. Biological measurements, model approximations and project hypotheses are distinguished in the research notes.
