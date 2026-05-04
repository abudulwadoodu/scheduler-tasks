# Clustering Pipeline — Developer Documentation

**Module:** `training_pipeline.py`
**Section:** Webpage Classification via HDBSCAN Clustering

---

## Purpose

This pipeline clusters webpages based on their text content, unit type, and pricing data. The goal is to group pages that likely share the same **mathematical structure for unit price conversion** (e.g., how they calculate unit price from sales price). Instead of sending every webpage to an LLM to generate a formula, only one representative page per cluster needs an LLM call — the generated formula is then reused for all pages in that cluster.

```
Raw Webpages → Cluster → Pick 1 representative per cluster → LLM generates formula → Apply to all pages in cluster
```

---

## Pipeline Overview

```
DataFrame
    │
    ▼
[Step 1] FeatureTransformer
         ├── SentenceTransformer  (Description, URL, Comments → 384-dim embeddings)
         ├── OneHotEncoder        (Unit → binary encoded)
         └── StandardScaler       (Rate → normalized)
                │
                ▼ Combined + Block-normalized feature matrix
    │
    ▼
[Step 2] UMAP
         └── High-dim features → 15-dim manifold
                │
                ▼ Low-dim representation
    │
    ▼
[Step 3] HDBSCAN
         └── Density-based clustering → cluster labels
                │
                ▼ labels, probabilities
    │
    ▼
[Step 4] Cluster Profiles
         └── Medoid + distance threshold per cluster
```

---

## Stage 1: Feature Transformation (`FeatureTransformer`)

### What it does

Converts mixed-type data (text, categorical, numerical) into a single numeric matrix suitable for distance-based clustering.

### Column Mapping

| Column | Type | Transformer | Output Dim |
|---|---|---|---|
| `Description`, `URL`, `Comments` | Text | `SentenceTransformer('all-MiniLM-L6-v2')` | 384 |
| `Unit` | Categorical | `OneHotEncoder` | # unique units |
| `Rate` | Numerical | `StandardScaler` | 1 |

### Block Normalization (Critical Detail)

After concatenating all blocks, each block is **L2-norm normalized** independently:

```python
block_norm = np.linalg.norm(X[:, block_start:block_end], axis=1).mean()
X[:, block_start:block_end] /= block_norm
```

**Why this matters:** Without normalization, the 384-dimensional text embeddings would dominate the distance calculations, effectively making Unit and Rate invisible to the clustering. After normalization, all three blocks contribute roughly equally to how similar two pages appear.

**Effect on clustering:**
- More normalization weight on text → pages cluster by description similarity
- Without normalization → Unit and Rate are drowned out by text volume
- Current approach: equal contribution from all three data types

### Tweakable: Relative Block Weights

Currently all blocks are auto-normalized to equal weight. If you want text to matter more than price (or vice versa), you can apply a manual multiplier after normalization:

```python
# Example: make text 2x more influential than price
TEXT_WEIGHT = 2.0
CATEGORICAL_WEIGHT = 1.0
NUMERICAL_WEIGHT = 0.5

X[:, text_start:text_end] *= TEXT_WEIGHT
X[:, cat_start:cat_end] *= CATEGORICAL_WEIGHT
X[:, num_start:num_end] *= NUMERICAL_WEIGHT
```

---

## Stage 2: UMAP Dimensionality Reduction

### What it does

UMAP (Uniform Manifold Approximation and Projection) reduces the high-dimensional feature matrix (~386 dims) down to 15 dimensions while preserving the local neighborhood structure — i.e., pages that were similar in the original space remain neighbors in the reduced space.

### Parameters

```python
umap.UMAP(
    n_components=15,   # Output dimensionality
    n_neighbors=15,    # Controls local vs global structure
    min_dist=0.1,      # Minimum distance between points in low-dim space
    metric='euclidean',
    random_state=42
)
```

#### `n_components` — Output Dimensions
- **Current:** `15`
- **Effect:** Higher values preserve more structure but make HDBSCAN slower and less effective. Lower values compress too aggressively and merge distinct clusters.
- **Tuning guide:**
  - Small dataset (< 500): try `5–10`
  - Medium dataset (500–5000): `10–20` is typical
  - Large dataset (> 5000): `20–50`
- **Rule of thumb:** Should be significantly lower than input dims but high enough that HDBSCAN can find meaningful density variation.

#### `n_neighbors` — Local Neighborhood Size
- **Current:** `15`
- **Effect:** Controls the balance between local and global structure.
  - **Low values (5–10):** UMAP focuses on very local structure → more fragmented, micro-clusters. Useful if you want fine-grained groupings.
  - **High values (30–50):** UMAP sees broader patterns → smoother, fewer but larger clusters. Useful if you want coarse groupings.
- **Interaction with dataset size:** Should scale with dataset size. A rough guide: `n_neighbors ≈ sqrt(n_samples) / 2`, but 15 is a reliable default for most sizes.

#### `min_dist` — Minimum Point Separation
- **Current:** `0.1`
- **Effect:** Controls how tightly UMAP packs points in the low-dimensional space.
  - **Low values (0.0–0.05):** Points cluster tightly together → sharper, more compact clusters. Better for HDBSCAN density detection.
  - **High values (0.5–1.0):** Points spread out more evenly → visually nicer for 2D plots but harder for HDBSCAN to detect density peaks.
- **Recommendation for clustering (not visualization):** Keep `min_dist` low (`0.0–0.1`). For 2D visualization only, increase to `0.3–0.5`.

---

## Stage 3: HDBSCAN Clustering

### What it does

HDBSCAN (Hierarchical Density-Based Spatial Clustering of Applications with Noise) finds clusters of varying density and explicitly marks low-confidence points as **outliers** (label `-1`). This is the core clustering step.

### Parameters

```python
hdbscan.HDBSCAN(
    min_cluster_size=min_cluster_size,   # Auto-calculated
    min_samples=min_samples,             # Auto-calculated
    metric='euclidean',
    cluster_selection_method='eom',
    prediction_data=True
)
```

### Auto-Calculated Parameters

Parameters are calculated relative to dataset size via `calculate_hdbscan_params()`:

```python
# conservative mode
min_cluster_size = max(5,  int(0.02 * n_samples))   # 2% of data, min 5
min_samples      = max(3,  int(0.03 * n_samples))   # 3% of data, min 3
# enforced: min_samples > min_cluster_size (conservative constraint)
```

| Dataset Size | `min_cluster_size` | `min_samples` |
|---|---|---|
| 100 | 5 | 5 → adjusted to 8 |
| 500 | 10 | 15 |
| 1000 | 20 | 30 |
| 5000 | 100 | 150 |

#### `min_cluster_size` — Minimum Group Size
- **What it is:** The smallest number of pages that can form a valid cluster. Any group smaller than this becomes outliers.
- **Effect:**
  - **Smaller value:** More clusters, including very small ones. Risk of over-fragmentation.
  - **Larger value:** Fewer, larger clusters. Risk of merging distinct page types into one cluster.
- **For this project:** A cluster represents a "formula type." If you set this too small, you'll generate redundant LLM calls for near-identical page types. Too large and you'll group pages with genuinely different formulas together.

#### `min_samples` — Core Point Strictness
- **What it is:** How many neighbors a point needs within its reachability distance to be considered a "core point" (not an outlier).
- **Effect:**
  - **Higher than `min_cluster_size` (current: conservative mode):** Strict core definition → more outliers, but clusters that do form are highly reliable. Good when formula correctness is more important than coverage.
  - **Equal to `min_cluster_size` (permissive mode):** More points get assigned to clusters, fewer outliers. Good when you want maximum coverage and can tolerate some noise in clusters.
- **Key ratio:** The `min_samples / min_cluster_size` ratio is the main dial between conservative and permissive behavior.

#### `preference` — Conservative vs Permissive

| Setting | `cluster_pct` | `sample_pct` | Behavior |
|---|---|---|---|
| `'conservative'` | 2% | 3% | Fewer clusters, high purity, more outliers |
| `'permissive'` | 1.5% | 2% | More clusters, more coverage, fewer outliers |

**When to use conservative:** When it's costly to apply the wrong formula — you'd rather send a page to the LLM individually (as an outlier) than apply a bad formula from a mismatched cluster.

**When to use permissive:** When you want to maximize the number of pages covered by a cluster formula and are okay with a small error rate.

#### `cluster_selection_method='eom'` — Excess of Mass
- **Current:** `'eom'` (Excess of Mass)
- **Alternative:** `'leaf'`
- **Effect:**
  - `'eom'`: Selects clusters that maximize the total cluster stability. Tends to produce fewer, larger clusters.
  - `'leaf'`: Selects the finest-grained clusters from the hierarchy. Produces more clusters, potentially smaller. Better if you expect many distinct formula subtypes.

---

## Stage 4: Cluster Profiles

### What it does

For each cluster, computes a **medoid** (the most central real data point) and a **distance threshold** (90th percentile of member distances to medoid). These are used during inference to decide whether a new webpage fits into an existing cluster or should be treated as novel.

### Medoid vs Centroid

| | Medoid | Centroid |
|---|---|---|
| Definition | Actual data point with minimum avg distance to all others | Mathematical mean of all points (not a real data point) |
| Advantage | Always a real webpage — can be used as the LLM prompt representative | Pure math — may not correspond to any real page |
| Use in this project | The one page per cluster you send to the LLM | Not used |

### Threshold (90th Percentile)

```python
threshold = np.percentile(distances_to_medoid, 90)
```

- **What it is:** The distance beyond which a point is considered "not confidently in this cluster."
- **Current value:** 90th percentile of training member distances.
- **Effect of changing percentile:**
  - **Lower (e.g., 75th):** Tighter threshold. New pages must be very close to the medoid to be accepted. More pages fall back to LLM calls.
  - **Higher (e.g., 95th–99th):** Looser threshold. More new pages get assigned to existing clusters. Risk of accepting pages that don't actually share the formula.
- **Recommendation:** Keep at 90th for a balanced approach. Lower to 75th if formula accuracy is critical. Raise to 95th if LLM costs are high and you want maximum reuse.

---

## Saved Model Files

| File | Contents | Used For |
|---|---|---|
| `feature_transformer.joblib` | `FeatureTransformer` instance (scaler + encoder + sentence model ref) | Transforming new pages at inference |
| `umap_model.joblib` | Fitted UMAP model | Projecting new pages into cluster space |
| `hdbscan_model.joblib` | Fitted HDBSCAN model | Soft-assigning new pages to clusters |
| `cluster_profiles.json` | Medoid + threshold + size per cluster | Confidence-based cluster assignment at inference |
| `metadata.json` | `n_clusters`, `outlier_rate`, `min_cluster_size`, `min_samples` | Auditing and reproducibility |
| `clustered_data.csv` | Original DataFrame + `cluster_type` + `cluster_probability` columns | Analysis and debugging |

---

## Loading Note for Notebooks

When loading the model in a Jupyter notebook, **always import `FeatureTransformer` explicitly** alongside the loading function. Without this, `joblib`/`pickle` cannot resolve the class during deserialization:

```python
# ✅ Correct
from training_pipeline import load_clustering_model, FeatureTransformer

# ❌ Will throw AttributeError on load
from training_pipeline import load_clustering_model
```

---

## Quick Tuning Reference

| Goal | Parameter to Change | Direction |
|---|---|---|
| More clusters, finer grouping | `n_neighbors` (UMAP) | Lower |
| Fewer, broader clusters | `n_neighbors` (UMAP) | Higher |
| Tighter, more compact clusters | `min_dist` (UMAP) | Lower |
| Reduce outlier rate | `preference` | Switch to `'permissive'` |
| Increase cluster purity | `preference` | Switch to `'conservative'` |
| Stricter formula matching at inference | Threshold percentile | Lower (75th) |
| Maximize cluster coverage at inference | Threshold percentile | Higher (95th) |
| Text description drives clustering | Block weights | Increase `TEXT_WEIGHT` |
| Unit type drives clustering | Block weights | Increase `CATEGORICAL_WEIGHT` |
| Price similarity drives clustering | Block weights | Increase `NUMERICAL_WEIGHT` |