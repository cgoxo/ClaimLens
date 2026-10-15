# Licences: CAT-Net in ClaimLens

| Part | Source | Licence | Commercial use |
| --- | --- | --- | --- |
| CAT-Net code (`vendor/lib/models/network_CAT.py`, `vendor/Splicing/data/AbstractDataset.py`, `vendor/experiments/CAT_full.yaml`) | [mjkwon2021/CAT-Net](https://github.com/mjkwon2021/CAT-Net), commit `5eb85900b0e72423c95a8d41bc835b86c8671f8a` | Apache 2.0 (README, update of 2026-08-05) | Yes, with attribution |
| CAT-Net trained weights `CAT_full_v2.pth.tar` (fetched at build time, never in git) | The author's Google Drive copy refuses downloads ("only owner and editors"). Fetched instead from the community copy [jtz18/CAT-NET](https://huggingface.co/jtz18/CAT-NET) on Hugging Face (its "MIT" tag is not the authoritative licence) | CC-BY 4.0 (the author's update; it allows redistribution) | Yes, with attribution |
| HRNet backbone code (`vendor/lib/**` headers "Copyright (c) Microsoft") | HRNet, via CAT-Net | MIT (`vendor/LICENSE of HRNet`) | Yes |

**Attribution:** M.-J. Kwon, S.-H. Nam, I.-J. Yu, H.-K. Lee, C. Kim, *"Learning JPEG Compression Artifacts for Image
Manipulation Detection and Localization"*, International Journal of Computer Vision, 2022. Code and weights by
Myung-Joon Kwon, licensed Apache 2.0 / CC-BY 4.0.

The README also notes that the author accepts no liability, and that users must respect the licences of the
original images used to build their datasets. ClaimLens uses only the weights, not those datasets.
