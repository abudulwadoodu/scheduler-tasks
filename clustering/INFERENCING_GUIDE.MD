# Inference Pipeline — Developer Documentation

**Module:** `inference_pipeline.py`
**Section:** Webpage Cluster Assignment at Runtime

---

## Purpose

Given a new webpage (or batch of webpages), determine which cluster it belongs to — and with what confidence. If a page fits a known cluster, its pre-generated formula is reused. If it doesn't fit anywhere confidently, it gets flagged as an outlier and sent to the LLM individually.

```
New Webpage(s)
      │
      ▼
[Same FeatureTransformer as training]
      │
      ▼
[Same UMAP model as training]   ← project into the cluster space
      │
      ▼
[Distance to each cluster's medoid]
      │
      ├── confidence > threshold  →  Assign to cluster  →  Reuse formula
      └── confidence ≤ threshold  →  Outlier (-1)        →  LLM call
```

**Important:** No re-training happens at inference. The same `feature_transformer` and `umap_model` saved during training are reused — new data is projected into the existing cluster space.

---

## Core Concept: How Confidence Is Calculated

This is the most important thing to understand about this inference pipeline. It does **not** use HDBSCAN's own soft-clustering at inference time. Instead it uses a **medoid-distance approach** based on the cluster profiles saved during training.

### The Formula

```python
confidence = 1.0 - (distance_to_medoid / cluster_threshold)
```

| Scenario | Distance | Confidence | Meaning |
|---|---|---|---|
| Item is identical to medoid | 0 | 1.0 | Perfect match |
| Item is exactly at the 90th percentile boundary | = threshold | 0.0 | Borderline |
| Item is beyond the boundary | > threshold | Negative | Outlier territory |
| Item is closer than any training member | < all members | > 1.0 → capped to 1.0 | Exceptionally close |

### Why This Works

During training, the `threshold` for each cluster was set to the **90th percentile** of member distances to that cluster's medoid. So:
- A confidence of `1.0` = right at the center of the cluster
- A confidence of `0.0` = at the edge of what training data considered "in cluster"
- A confidence of `-0.5` = 50% further out than the cluster's boundary

The confidence score is therefore directly interpretable as **how far inside or outside the cluster boundary the new item sits**.

### Assignment Decision

```python
if best_confidence > confidence_threshold:
    assigned_cluster = best_cluster   # Reuse formula
else:
    assigned_cluster = -1             # Send to LLM
```

The `confidence_threshold` parameter (default `0.0`) is the **main operational dial** — it controls where you draw the line between "good enough to reuse a formula" and "needs its own LLM call."

---

## Key Parameter: `confidence_threshold`

This is the single most impactful parameter in the inference pipeline.

```python
results = predict_batch(df, loaded_models, confidence_threshold=0.0)
```

| Value | Behavior | Use When |
|---|---|---|
| `0.0` (default) | Any positive confidence gets assigned | Minimizing LLM calls is priority |
| `0.3` | Only assign if item is clearly inside the cluster | Balanced — good starting point |
| `0.5` | Only assign if item is solidly in the cluster interior | Formula correctness is important |
| `0.7` | Only assign high-confidence matches | Formula must be very reliable |
| Negative (e.g. `-0.2`) | Even some items outside the boundary get assigned | Maximum coverage, lower accuracy |

**Practical guidance for this project:**

Setting `confidence_threshold=0.3` is a reasonable production default. It means a page must be within 70% of the distance from medoid to cluster boundary before it gets a formula applied. Items that scored between `0.0` and `0.3` get sent to the LLM — a small LLM cost that buys you protection against applying the wrong unit conversion formula.

### Interpretation Tiers (built into `predict_with_interpretation`)

```python
confidence >= 0.7  →  HIGH confidence    (solidly inside cluster)
confidence >= 0.4  →  MEDIUM confidence  (inside but toward edges)
confidence >= 0.0  →  LOW confidence     (just inside boundary)
confidence <  0.0  →  OUTLIER            (outside cluster boundary)
```

You can adjust these tier boundaries to match your tolerance for formula error.

---

## Functions

### `predict_single_item(new_item_umap, cluster_profiles, confidence_threshold)`

Low-level function. Operates on a **single item already projected to UMAP space** — does not do feature transformation or UMAP projection itself.

**Input:** `new_item_umap` — numpy array of shape `(15,)` (the 15 UMAP dimensions)

**Output:**
```python
{
    'cluster': 2,              # Assigned cluster ID, or -1
    'confidence': 0.63,        # Confidence score
    'distance': 0.21,          # Raw distance to nearest medoid
    'nearest_cluster': 2,      # Which cluster was closest (even if flagged as outlier)
    'all_distances': {0: 1.2, 1: 0.8, 2: 0.21},   # Distance to every cluster
    'all_confidences': {0: -0.4, 1: 0.1, 2: 0.63}  # Confidence for every cluster
}
```

Note: `nearest_cluster` is always populated even for outliers. This tells you which cluster the outlier was *closest* to, which is useful for debugging — if an outlier consistently appears near cluster 3, it may represent a new formula subtype emerging in the data.

---

### `predict_batch(df, loaded_models, confidence_threshold, return_details)`

Main inference function. Takes a raw DataFrame (same schema as training), runs the full pipeline, and returns the original data with prediction columns appended.

**Output columns added:**

| Column | Type | Description |
|---|---|---|
| `predicted_cluster` | int | Cluster ID, or `-1` for outlier |
| `confidence` | float | Confidence score (see formula above) |
| `nearest_cluster` | int | Closest cluster regardless of assignment |
| `distance` | float | Raw Euclidean distance to nearest medoid |
| `all_distances` | dict | *(only if `return_details=True`)* Distance to every cluster |
| `all_confidences` | dict | *(only if `return_details=True`)* Confidence for every cluster |

**`return_details=True`** is useful during development to understand why borderline items were assigned or rejected. In production, keep it `False` to avoid storing large dicts per row.

---

### `predict_with_interpretation(df, loaded_models, confidence_threshold)`

Wrapper around `predict_batch` that adds a human-readable `interpretation` column. Good for inspection and debugging, not needed in production pipelines.

```
"HIGH confidence - Cluster 2 (0.82)"
"MEDIUM confidence - Cluster 0 (0.51)"
"LOW confidence - Cluster 1 (0.12)"
"OUTLIER (confidence: -0.23)"
```

---

### `get_cluster_statistics(loaded_models)`

Returns a summary DataFrame of all clusters from the loaded model. Useful for understanding the shape of the cluster space before running inference.

```
   cluster_id  size  threshold  medoid_norm
0           0    25      0.420        2.145
1           1    18      0.380        1.987
2           2    22      0.450        2.301
```

- **`size`** — how many training pages were in this cluster. Small clusters (size < 10) have less reliable thresholds.
- **`threshold`** — larger values mean the cluster is spread out; smaller values mean it is tight and compact. A tight cluster with a small threshold is more discriminating at inference.
- **`medoid_norm`** — the L2 norm of the medoid vector. Not directly actionable but useful for spotting anomalous clusters.

---

## Inference Flow in Context of the Full Project

```
                    ┌─────────────────────────────────┐
                    │         New Webpage(s)           │
                    └────────────────┬────────────────┘
                                     │
                         predict_batch() called
                                     │
                    ┌────────────────▼────────────────┐
                    │      Feature Transformation      │
                    │  (same transformer as training)  │
                    └────────────────┬────────────────┘
                                     │
                    ┌────────────────▼────────────────┐
                    │         UMAP Projection          │
                    │    (same UMAP as training)       │
                    └────────────────┬────────────────┘
                                     │
                    ┌────────────────▼────────────────┐
                    │     Distance to all medoids      │
                    │   → confidence per cluster       │
                    └────────────────┬────────────────┘
                                     │
                    ┌────────────────▼────────────────┐
                    │   confidence > threshold?        │
                    └──────┬──────────────────┬───────┘
                           │ YES              │ NO
                    ┌──────▼──────┐    ┌──────▼──────┐
                    │ Assign to   │    │  Outlier     │
                    │  Cluster N  │    │  (label -1)  │
                    └──────┬──────┘    └──────┬───────┘
                           │                  │
                    ┌──────▼──────┐    ┌──────▼───────┐
                    │ Reuse pre-  │    │  Send to LLM  │
                    │  generated  │    │  to generate  │
                    │   formula   │    │  new formula  │
                    └─────────────┘    └──────────────┘
```

---

## Failure Modes to Watch For

### 1. Distribution Shift
If new webpages come from a different source (different retailer, different product category), their features may land in a completely different region of UMAP space. You'll see a sudden spike in outlier rate. This is a signal to retrain the pipeline on the expanded dataset.

**How to detect:** Monitor `outlier_rate` over time. A sustained increase beyond the training `outlier_rate` (stored in `metadata.json`) indicates drift.

### 2. Overconfident Assignment on Edge Cases
If `confidence_threshold=0.0`, items just barely inside the boundary (confidence `0.01`) get assigned the same way as items at the center (confidence `0.95`). For formula reuse, these low-confidence assignments are the most likely source of wrong formulas.

**Mitigation:** Use `confidence_threshold=0.3` and log all assignments with `confidence < 0.4` for periodic human review.

### 3. UMAP Transform vs Fit-Transform
UMAP's `.transform()` (used at inference) projects new points into the *existing* manifold. This is slightly less accurate than `.fit_transform()` because UMAP is non-parametric — it wasn't designed to be a generative projector. For most cases this is fine, but very novel pages may land in unexpected positions.

**Mitigation:** Use `return_details=True` to inspect `all_distances` — if a page has high distance to *all* clusters, it's genuinely novel, not just a boundary case.

---

## Quick Reference

```python
from training_pipeline import load_clustering_model, FeatureTransformer
from inference_pipeline import predict_batch, predict_with_interpretation, get_cluster_statistics

# Load
loaded = load_clustering_model('metals4u_model')

# Inspect clusters
print(get_cluster_statistics(loaded))

# Predict (production)
results = predict_batch(df_new, loaded, confidence_threshold=0.3)

# Separate assigned vs outliers
assigned = results[results['predicted_cluster'] != -1]
outliers  = results[results['predicted_cluster'] == -1]

# Outliers → send to LLM
# Assigned → look up formula by cluster ID and apply
```