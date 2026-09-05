# Paper access, provided links, and next downloads

Checked 2026-09-04. **No institutional login is currently required to proceed with the initial architecture/prototype.** No login was attempted. A blocked automated request is not evidence that a paper is paywalled.

## Supplied references

| Input | What was available and how it was used |
|---|---|
| [Eon embodied-brain update](https://eon.systems/updates/embodied-brain-emulation) | Read the technical account and its stated limitations; saved interpretation in note 07 |
| [Alex Wissner-Gross X post](https://x.com/alexwg/status/2030217301929132323) | HTTP 403; post/video not independently inspected; did not infer its content |
| [Shiu brain repository](https://github.com/philshiu/Drosophila_brain_model) | Code inspected at `91bdd1e7dcf193f3e7ca5a8933497fcef63b7960`; whole-brain execution not performed |
| [TuragaLab FlyBody](https://github.com/TuragaLab/flybody) | Code/body/policy dependencies audited at `d015e9bfe441bd90ae431bac24c55cb74bdbce26`; original flight policy not run |
| [Eon fly-brain repository](https://github.com/eonsystemspbc/fly-brain) | Code inspected at `a3db62f9436074e485c0278290c2164ed6150808`; neural benchmark runner, not an installed all-system demo |
| [Google male-connectome announcement](https://research.google/blog/a-connectomics-milestone-mapping-the-complete-male-fruit-fly-brain/) | Read; followed links to datasets and newly available female BANC |
| [Janelia male CNS page](https://www.janelia.org/project-team/flyem/male-cns-connectome) | Read project/version/download information; checked public bulk URLs |
| [Male CNS bioRxiv v2](https://www.biorxiv.org/content/10.1101/2025.10.09.680999v2) | Automated fetch blocked; final supplied Cell article supersedes it for current counts |
| [Google Neural Mapping](https://sites.research.google/gr/neural-mapping/) | Read resource overview and publication abstract; recorded stale count differences |
| [Cell article](https://www.cell.com/cell/fulltext/S0092-8674(26)00942-6) | HTML request blocked; user-supplied full PDF successfully read; DOI 10.1016/j.cell.2026.08.015 |
| [drosophila-2024.pdf](../drosophila-2024.pdf) | 32 pages; Dorkenwald et al., *Neuronal wiring diagram of an adult brain*, DOI 10.1038/s41586-024-07558-y; metadata/text extraction and visual page inspection |
| [drosophila-2026.pdf](../drosophila-2026.pdf) | 51 pages; Berg et al., final Cell article plus extended material; metadata/text extraction and relevant visual page inspection |

The preprint, final article, institutional summary and social-media description are related evidence, not independent replications of the same finding. The final paper takes precedence for its version-specific measurements.

## Core open-access routes

- [Shiu model paper, public PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC11446845/).
- [Female BANC final paper](https://www.nature.com/articles/s41586-026-10735-w) and [authors' data index](https://github.com/htem/BANC-project/blob/main/manuscript/print/banc_data_locations.md).
- [NeuroMechFly v2 author-hosted full paper](https://gizemozd.github.io/assets/pdf/2024_neuromechflyv2.pdf).
- [FlyBody paper](https://www.nature.com/articles/s41586-025-09029-4).
- [July 2026 olfactory directional-memory study](https://www.nature.com/articles/s41586-026-10827-7).

Bulk connectome URLs, measured file sizes, corrected BANC filenames and version caveats are in [note 01](01-connectomes-and-neural-models.md) and [sources-connectomes.json](sources-connectomes.json). HTTP availability checks were performed; those large tables were not downloaded or imported into a neural simulator. Prefer aggregated tables initially, not raw EM imagery.

## Optional full-methods/supplement requests

For future quantitative replication, obtain full methods and supplements for the specific assay first. These links are priorities if public routes are insufficient; they are **not confirmed institutional-access blockers**:

1. [Odour motion sensing, Nature 2022](https://www.nature.com/articles/s41586-022-05423-4): plume calibration and bilateral timing.
2. [LC10-directed courtship, Cell 2018](https://www.sciencedirect.com/science/article/pii/S0092867418307888): visual tuning and perturbation details.
3. [Coital experience circuit, Neuron 2019](https://pubmed.ncbi.nlm.nih.gov/31072787/): dissociate mechanical mating input from ejaculate effects.
4. [Sperm-bound sex peptide, Current Biology 2005](https://pubmed.ncbi.nlm.nih.gov/15694303/): construct-specific release/persistence measurements.

Further candidates and review depth are recorded in the [behavior registry](sources-behavior.json). No subscription credentials or institutional account information should be embedded in downloaded data or source manifests.
