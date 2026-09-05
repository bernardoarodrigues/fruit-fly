# Female optical-template source notice

`zhao-female-right-eye-directions.csv` is a modified data extraction from Zhao et al. (2025), *Eye structure shapes neuron function in Drosophila motion vision*, DOI [10.1038/s41586-025-09276-5](https://doi.org/10.1038/s41586-025-09276-5).

Source: [reiserlab/eyemap_T4](https://github.com/reiserlab/eyemap_T4/tree/99d2a43123db636cedb55af9ff31a59657e7d17e), commit `99d2a43123db636cedb55af9ff31a59657e7d17e`. The repository declares GNU GPL version 3; the verbatim [upstream license](UPSTREAM-GPL-3.0.txt) is retained here. This data extraction retains those terms and is supplied without warranty. The primary publication has its own terms.

Changes made 2026-09-05 UTC: extract the 852 right-eye female geometric axes, preserve one-based source indices and lattice coordinates, normalize/report Cartesian directions, and calculate azimuth/elevation using x forward, y left, z dorsal. No male neural correspondence is introduced. Source RData remains separately acquired; [the receipt](zhao-extraction.json) gives exact URLs and hashes, and [the extraction script](../../scripts/extract_zhao_eye_template.py) specifies the complete transformation. The source repository also supplies the original processing scripts.

The coverage CSV/plots under `validation/visual-template-coverage/` use these same source-derived axes, with numerical camera-support calculations added. They retain this source attribution and GPL-3.0 terms for the source-derived data.

Upstream license SHA-256: `3972dc9744f6499f0f9b2dbf76696f2ae7ad8af9b23dde66d6af86c9dfb36986`.
