# Public source-data inventory for Salman et al.

The [paper-linked OSF project](https://osf.io/pfbea/) is public and its root storage is empty, but its child components contain the data. The completed [metadata inventory](../validation/salman-osf-inventory.json) finds **54 public nodes and 258 file entries**, whose provider-reported sizes sum to **42,382,076,892 bytes**. This total includes repeated files across figure components; it is not a unique-content total or a download receipt. No data payload was downloaded by the inventory script.

All 54 nodes declare the same OSF license identifier, resolving to [Creative Commons Attribution–NonCommercial 4.0](https://creativecommons.org/licenses/by-nc/4.0/legalcode). Each file retains its node, original title/path, version, provider hashes, metadata URL and download link. License and integrity information for individual acquired files must still accompany their acquisition; this listing does not verify their bytes.

The useful current-clamp subset is under [Figure 3d](https://osf.io/sutz6/):

| File | Reported bytes | Purpose of the next inspection |
|---|---:|---|
| Current Clamp analysis.xlsx | 274,638 | Inspect original sheets, units, formulas, cached summaries and sample identities |
| ALL CC pre DRUGS.pzf | 381,637 | Inspect the saved analysis report and group/current-axis labels |
| ILN2F.rar | 122,436,513 | Candidate raw Full-LN current-clamp recordings; not acquired by this inventory |
| il3LN6s Keystones current clamp and I0 experiments.rar | 121,973,234 | Candidate raw il3LN6 recordings; not acquired by this inventory |
| R32 ILN2Ps.rar | 197,977,630 | Candidate raw Patchy recordings; not acquired by this inventory |

The same three archive names/sizes also appear in the corresponding Figure 3a–c nodes. Equal names and sizes alone do not establish byte identity; the inventory retains provider hashes for explicit comparison. Other components contain large imaging collections, odor-response tables and pharmacology recordings. They were listed without bulk downloading them.

The first acquisition intentionally stopped at a **200 metadata-request ceiling**. Its [incomplete receipt](../validation/salman-osf-inventory-v0-incomplete.json) and [original script bytes](../scripts/inventory_salman_data_v0.py) are preserved. The completed [script](../scripts/inventory_salman_data.py) validates and reuses those exact 200 response files, raises the metadata ceiling to 600, and finishes at **230 retained responses**. The completed receipt identifies the prior receipt by hash. This is a live metadata snapshot spanning the acquisition interval, including reused responses, not an atomic or version-frozen OSF archive.

```sh
.venv/bin/python scripts/inventory_salman_data.py
```

Run in a checkout without its generated inventory receipt. `--resume` accepts a retained partial inventory and verifies every cached response's size and SHA-256 before reuse. Raw JSON responses remain under ignored `data/raw/antennal-lobe-inhibition/osf-pfbea/metadata/`; the small tracked receipt records their paths and hashes. Only public metadata endpoints are read. This inventory runs no downloaded analysis code and makes no neural or physiological parameter inference.

The source paper's physiological distinctions and reporting inconsistency are retained in [research13](../research/13-antennal-lobe-inhibitory-constraints.md). Acquiring an analysis file does not establish that it contains the complete published cohort or resolves the experimental current axis; those are separate data-audit questions.
