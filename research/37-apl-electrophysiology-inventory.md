# Complete electrophysiology archive and header inventory

Completed 2026-09-06 UTC. The [Chen source archive](35-apl-direct-electrophysiology-source.md) is fully acquired. The completion heartbeat was paused before inventory. This stage accounts for the complete deposit and every APL electrical file; it does not fit voltage responses or select a physiological parameter.

## Integrity and preserved sources

The complete ZIP is 2,287,477,173 bytes, published MD5 `c6d63ac25c504db4fc3ee45578d63169`, SHA-256 `bc723b55aa0655452a828bec71e42da5e037a800a970823e3997b00c1bfe631f`. [Acquisition receipt](../validation/apl-sk-ephys-acquisition.json) records the original download, which completed in 722.31 seconds. [Inventory](../validation/apl-sk-ephys-inventory.json) independently rechecks both digests and reads every ZIP member to EOF, validating its CRC and computing a member SHA-256. No path traversal, normalized duplicate names, symlinks or encrypted entries were encountered.

There are 1,695 entries, including 1,227 files totaling 4,354,553,089 uncompressed bytes: 475 ABF electrical files, 354 text files, 177 JSON files, 210 TIFF images, eight workbooks and three temporary files. The original archive retains everything. APL ABFs and text/JSON metadata plus all eight author workbooks were extracted under `data/raw/apl-sk-electrophysiology/inventory-files` (380 files). No source code was executed.

| Source folder | ABF files | Candidate recording directories |
|---|---:|---:|
| APL normal/deprived/recovery, Fig. 4B–G | 122 | 50 |
| APL SK RNAi/control, Fig. 4H–J | 49 | 19 |
| KC, Fig. 3 | 304 | 89 |

These are directory/file counts, not verified biological sample sizes. Repeated protocols, paired drug recordings, bilateral cells, missing files and author inclusion rules must be joined before defining independent observations.

## Complete APL header pass

All **171/171 APL ABF files** passed source-hash verification and header parsing with [pyABF](https://swharden.com/pyabf/) 2.3.8 and `loadData=False`. The [header inventory](../validation/apl-sk-abf-headers.json) preserves public metadata and protocol/ADC/DAC/epoch sections for each source file. No voltage samples were loaded for this pass. The parser version is pinned in the optional research dependencies.

All files declare **10 kHz** sampling and **Clampex 11.3.0.2**. The software version differs from the paper's general pCLAMP 10 methods description; retain the actual file metadata. Channels are heterogeneous:

| ADC units by file | Files |
|---|---:|
| mV, pA | 88 |
| mV only | 69 |
| mV, mV | 8 |
| pA only | 3 |
| mV, pA, V | 3 |

There is no valid universal rule to treat channel 1 as recorded current or every file as current clamp. Some break-in filenames refer to a stored `VC_Gap free` protocol while the ADC is mV; names alone cannot determine clamp mode. Three files use an optogenetic voltage-clamp protocol and require separate handling.

### Command protocol findings

The epoch tables resolve part of the source's 1 nA/2 nA ambiguity:

- Eleven dedicated AHP files in the SK RNAi/control folder command **2,000 pA for 7,500 samples (750 ms)**. They comprise six control and five RNAi files by their source folders, consistent with the caption counts but still requiring workbook inclusion/identity checks.
- Three dedicated AHP files in the normal/deprived/recovery folder command **1,000 pA for 750 ms**. These are not the whole normal/deprived/recovery cohort; the other records and author workbooks must identify the measurements used for each cell.
- Four of the 2 nA files use a protocol named `IC_AHP_750ms 30s APL` without “2nA” in its name. Thus even the protocol name cannot supply the amplitude reliably.
- All 82 firing-pattern files have a **−50 pA, 500 ms** passive epoch, a **1 s** intervening zero epoch, then a **500 ms** series epoch incremented by 50 pA per sweep. Eighty-one start the series at −100 pA; one starts at −250 pA. The protocol names contain “750ms” despite these 500 ms epoch durations.

These are **commanded DAC epoch values**, not independent measurements of delivered current. Absolute onset includes the file's pre-epoch holding convention and must be reconstructed from the actual sweep layout. Recorded pA channels, where present, can check delivery, offsets and timing. For files with voltage only, any use of reconstructed commands must remain explicit. The dedicated 750 ms AHP pulses must not be pooled blindly with 500 ms firing-pattern pulses.

### Duplicate and identity findings

The complete-archive hashes identify **16 identical ABF pairs across KC NS and SD directories**, involving four recording IDs (two α′β′-folder IDs and two γ-folder IDs). These are byte-identical files under different condition paths, not independent observations. Their correct condition is unresolved; preserve both paths and consult the author workbooks before any KC comparison. No duplicate APL ABF content was found. No file is deleted or reassigned by this inventory.

The eight author workbooks include the five top-level final summary workbooks and three nested APL workbooks. They remain unparsed at this stage. Example image `comments.txt` files contain Micro-Manager property maps, so their existence alone is not an experimental annotation or exclusion log.

## Next scientific step

Read the APL author workbooks and join their cell IDs, NS/SD/RS labels, paired NS8593 records, RNAi/control groups and exclusion evidence to this complete source inventory. Establish which files/sweeps generated each reported observation; retain unmatched, duplicate and uncertain records. Resolve correction and bridge/holding state without interpreting header scale offsets as liquid-junction correction. Freeze complete calibration/evaluation groups, per-protocol windows and quality rules before applying the [electrical measurement functions](36-apl-electrical-measurement-reference.md).

This step establishes access and concrete protocol differences. It does not yet establish passive/AHP distributions, male-specific physiology, a natural synaptic drive law or a calcium-to-release mapping. The mated-female ex vivo transfer limitation remains explicit. No neural runtime, H1 promotion, gain sweep or cancelled Eon integration was introduced.
