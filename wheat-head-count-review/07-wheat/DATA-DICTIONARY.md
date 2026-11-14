# Wheat-head count review data dictionary

`data.json.gz` contains training, validation, and held-out image records. The training and validation records include observed counts. The baseline loads cached image features from `features.npz`.

| Field | Meaning |
| --- | --- |
| `id`, `domain` | Image record ID and dataset group |
| `width`, `height` | Original image dimensions |
| `image` | Bundled preview path when available |
| `image_sha256` | Hash used to verify the image for a correction |
| `source_file`, `source_row` | Location in the pinned source archive |
| `feature_index`, `rgb_features` | Cache index and basic RGB features |
| `target` | Observed wheat-head count in training and validation |

The review export records the original count, interval, review priority, and any manual correction with its image hash. [Source and license notes](NOTICE.md)
