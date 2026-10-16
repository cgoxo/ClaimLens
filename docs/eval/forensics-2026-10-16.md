# Pixel forensics: measurement report (2026-10-16)

Field-level scores on our own forged test set (fictional bills, phone-like photos). Thresholds are fixed on half A of the bills at 5% false positives on genuine numbers; everything below is half B. **Keep rule:** AUC ≥ 0.70 on G or G2, and ≤ 5% false positives on every genuine condition.

Forgery kinds:
- **G:** a Gemini image edit pasted back into the field;
- **G2:** G, then shared at q70;
- **G3:** total and item edited together (the arithmetic still holds);
- **P:** retyped;
- **C:** a copied digit.

## Verdict

| Detector | AUC (G) | AUC (G2) | Catches G at 5% FP | Worst genuine FP | No opinion | ₹/case | Verdict |
| --- | --- | --- | --- | --- | --- | --- | --- |
| catnet | 0.40 | 0.26 | 0% | 14% | 348 | – | **DROP** |
| chars | 0.85 | 0.78 | 0% | 0% | 0 | ₹0.00 | **KEEP** |
| copymove | 0.42 | – | 0% | 0% | 2373 | ₹0.00 | **DROP** |
| dq | – | – | – | – | 3280 | ₹0.00 | **DROP** |
| ela | 0.86 | 0.56 | 10% | 5% | 348 | ₹0.00 | **KEEP** |
| fused_max | 0.43 | 0.26 | 0% | 0% | 0 | – | **DROP** |
| fused_mean | 0.65 | 0.47 | 30% | 28% | 0 | – | **DROP** |
| noise | 0.58 | 0.65 | 5% | 26% | 0 | ₹0.00 | **DROP** |

## Per detector

### catnet

| Kind | AUC | Caught at 5% FP | Positives | Negatives |
| --- | --- | --- | --- | --- |
| G | 0.40 | 0% | 20 | 1428 |
| G2 | 0.26 | 0% | 20 | 1428 |
| G3 | 0.46 | 5% | 40 | 1428 |
| P | 0.48 | 0% | 20 | 1428 |
| C | 0.62 | 10% | 20 | 1428 |

False positives by genuine condition: crease_shadow 13%, original 12%, second_photo 14%, whatsapp 3%.

### chars

| Kind | AUC | Caught at 5% FP | Positives | Negatives |
| --- | --- | --- | --- | --- |
| G | 0.85 | 0% | 20 | 1600 |
| G2 | 0.78 | 0% | 20 | 1600 |
| G3 | 0.86 | 0% | 40 | 1600 |
| P | 0.96 | 0% | 20 | 1600 |
| C | 0.55 | 0% | 20 | 1600 |

False positives by genuine condition: crease_shadow 0%, original 0%, screenshot 0%, second_photo 0%, whatsapp 0%.

### copymove

| Kind | AUC | Caught at 5% FP | Positives | Negatives |
| --- | --- | --- | --- | --- |
| G | 0.42 | 0% | 5 | 438 |
| G2 | – | – | 0 | 438 |
| G3 | 0.52 | 0% | 10 | 438 |
| P | 0.32 | 0% | 5 | 438 |
| C | 0.62 | 0% | 5 | 438 |

False positives by genuine condition: crease_shadow 0%, original 0%, screenshot 0%, second_photo 0%.

### dq

| Kind | AUC | Caught at 5% FP | Positives | Negatives |
| --- | --- | --- | --- | --- |
| G | – | – | 0 | 0 |
| G2 | – | – | 0 | 0 |
| G3 | – | – | 0 | 0 |
| P | – | – | 0 | 0 |
| C | – | – | 0 | 0 |

False positives by genuine condition: .

### ela

| Kind | AUC | Caught at 5% FP | Positives | Negatives |
| --- | --- | --- | --- | --- |
| G | 0.86 | 10% | 20 | 1428 |
| G2 | 0.56 | 0% | 20 | 1428 |
| G3 | 0.85 | 30% | 40 | 1428 |
| P | 0.96 | 55% | 20 | 1428 |
| C | 0.50 | 10% | 20 | 1428 |

False positives by genuine condition: crease_shadow 3%, original 3%, second_photo 5%, whatsapp 1%.

### fused_max

| Kind | AUC | Caught at 5% FP | Positives | Negatives |
| --- | --- | --- | --- | --- |
| G | 0.43 | 0% | 20 | 1600 |
| G2 | 0.26 | 0% | 20 | 1600 |
| G3 | 0.53 | 0% | 40 | 1600 |
| P | 0.73 | 0% | 20 | 1600 |
| C | 0.61 | 0% | 20 | 1600 |

False positives by genuine condition: crease_shadow 0%, original 0%, screenshot 0%, second_photo 0%, whatsapp 0%.

### fused_mean

| Kind | AUC | Caught at 5% FP | Positives | Negatives |
| --- | --- | --- | --- | --- |
| G | 0.65 | 30% | 20 | 1600 |
| G2 | 0.47 | 0% | 20 | 1600 |
| G3 | 0.80 | 52% | 40 | 1600 |
| P | 0.93 | 80% | 20 | 1600 |
| C | 0.59 | 20% | 20 | 1600 |

False positives by genuine condition: crease_shadow 28%, original 8%, screenshot 6%, second_photo 8%, whatsapp 6%.

### noise

| Kind | AUC | Caught at 5% FP | Positives | Negatives |
| --- | --- | --- | --- | --- |
| G | 0.58 | 5% | 20 | 1600 |
| G2 | 0.65 | 20% | 20 | 1600 |
| G3 | 0.59 | 10% | 40 | 1600 |
| P | 0.52 | 5% | 20 | 1600 |
| C | 0.44 | 0% | 20 | 1600 |

False positives by genuine condition: crease_shadow 1%, original 1%, screenshot 1%, second_photo 1%, whatsapp 26%.

## Known limits

- A page that is entirely AI-generated, or a forgery re-photographed from a screen, leaves no local trace to find.
- PNG uploads carry no JPEG history: ela, dq and catnet have no opinion on them.
- Copy-move only judges near-lossless images (PNG, or JPEG q ≥ 93).
- The set is our own fictional bills: real phone photos vary more (lighting, angle, paper).

## Cost basis

- ₹/case assumes 10 photographed pages per case at ₹84/$.
- catnet: L4 GPU job in asia-southeast1, $0.0003488/s (or a CPU job in asia-south1, $0.0000880/s).
- Every other detector runs in the existing service, $0.0000200/vCPU-s.
- gemini_closeup also costs about ₹0.3 per case in Gemini tokens.
