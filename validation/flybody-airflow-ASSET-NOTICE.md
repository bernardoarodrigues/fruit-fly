# FlyBody airflow geometry attribution

`flybody-airflow-geometry.npz` and `flybody-airflow-geometry.png` derive selected mesh vertices and body landmarks from [TuragaLab/flybody](https://github.com/TuragaLab/flybody) at commit `d015e9bfe441bd90ae431bac24c55cb74bdbce26`, distributed under Apache License 2.0. The retained [license text](flybody-airflow-LICENSE-Apache-2.0.txt) applies to the source material.

Alterations: source meshes are compiled by MuJoCo 3.2.7, transformed into world coordinates at native reset, and extracted into a small diagnostic NPZ/plot. Positions are reported in centimeters in the NPZ and millimeters in the figure. Points identifying antenna body origins and inertial centers are added. No new biological specimen, measurement, receptor localization, or male-specific morphology is implied.

The separately distributed walking policy has its own GPL-3.0-or-later collection license and remains in ignored local data. The geometry subset does not redistribute policy weights. See the repository's [third-party record](../THIRD_PARTY.md) and source manifest for complete provenance.
