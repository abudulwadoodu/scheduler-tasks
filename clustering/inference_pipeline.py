"""
Inference Pipeline - Classify New Items with Confidence Scores
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Union
import warnings
warnings.filterwarnings('ignore')


def predict_single_item(new_item_umap, cluster_profiles, confidence_threshold=0.0):
    """
    Predict cluster assignment for a single item (already transformed to UMAP space)
    
    Args:
        new_item_umap: numpy array of shape (15,) - the item in UMAP space
        cluster_profiles: dict of {cluster_id: {medoid, threshold, size}}
        confidence_threshold: minimum confidence to assign (default 0.0)
        
    Returns:
        dict with keys:
            - cluster: cluster ID or -1 for outlier
            - confidence: confidence score (0 to 1, or negative for outliers)
            - distance: distance to nearest cluster medoid
            - nearest_cluster: which cluster was closest
            - all_distances: dict of distances to all clusters
    """
    if len(cluster_profiles) == 0:
        raise ValueError("No clusters in cluster_profiles")
    
    # Calculate distance to each cluster's medoid
    distances_to_clusters = {}
    confidences = {}
    
    for cluster_id, profile in cluster_profiles.items():
        medoid = profile['medoid']
        threshold = profile['threshold']
        
        # Euclidean distance to medoid
        distance = np.linalg.norm(new_item_umap - medoid)
        distances_to_clusters[cluster_id] = distance
        
        # Confidence calculation: 1 - (distance / threshold)
        confidence = 1.0 - (distance / threshold)
        confidences[cluster_id] = confidence
    
    # Find the nearest cluster (highest confidence)
    best_cluster = max(confidences.keys(), key=lambda k: confidences[k])
    best_confidence = confidences[best_cluster]
    best_distance = distances_to_clusters[best_cluster]
    
    # Decision: assign or flag as outlier
    if best_confidence > confidence_threshold:
        # Assign to cluster
        assigned_cluster = best_cluster
        final_confidence = min(best_confidence, 1.0)  # Cap at 1.0
    else:
        # Flag as outlier
        assigned_cluster = -1
        final_confidence = best_confidence  # Keep negative value
    
    return {
        'cluster': assigned_cluster,
        'confidence': final_confidence,
        'distance': best_distance,
        'nearest_cluster': best_cluster,
        'all_distances': distances_to_clusters,
        'all_confidences': confidences
    }


def predict_batch(df, loaded_models, confidence_threshold=0.0, return_details=False):
    """
    Predict cluster assignments for a batch of new items
    
    Args:
        df: pandas DataFrame with same columns as training data
            (Description, URL, comments, Unit, Rate)
        loaded_models: dict from load_clustering_model() containing:
            - feature_transformer
            - umap_model
            - cluster_profiles
        confidence_threshold: minimum confidence to assign (default 0.0)
        return_details: if True, return detailed info for each prediction
        
    Returns:
        pandas DataFrame with original data plus prediction columns:
            - predicted_cluster: cluster assignment (-1 for outliers)
            - confidence: confidence score
            - nearest_cluster: which cluster was closest
            - distance: distance to nearest cluster
            - (optional) all_distances, all_confidences if return_details=True
    """
    
    print("="*60)
    print("INFERENCE PIPELINE - BATCH PREDICTION")
    print("="*60)
    print(f"Number of items to classify: {len(df)}")
    print(f"Confidence threshold: {confidence_threshold}")
    print()
    
    # Extract loaded components
    feature_transformer = loaded_models['feature_transformer']
    umap_model = loaded_models['umap_model']
    cluster_profiles = loaded_models['cluster_profiles']
    
    # Step 1: Transform features
    print("Step 1: Feature Transformation")
    print("-" * 40)
    X_transformed = feature_transformer.transform(df)
    print(f"Transformed shape: {X_transformed.shape}")
    print()
    
    # Step 2: UMAP projection
    print("Step 2: UMAP Projection")
    print("-" * 40)
    X_umap = umap_model.transform(X_transformed)
    print(f"UMAP shape: {X_umap.shape}")
    print()
    
    # Step 3: Predict for each item
    print("Step 3: Cluster Prediction")
    print("-" * 40)
    predictions = []
    
    for i, item_umap in enumerate(X_umap):
        pred = predict_single_item(item_umap, cluster_profiles, confidence_threshold)
        predictions.append(pred)
    
    # Create results dataframe
    results_df = df.copy()
    results_df['predicted_cluster'] = [p['cluster'] for p in predictions]
    results_df['confidence'] = [p['confidence'] for p in predictions]
    results_df['nearest_cluster'] = [p['nearest_cluster'] for p in predictions]
    results_df['distance'] = [p['distance'] for p in predictions]
    
    if return_details:
        results_df['all_distances'] = [p['all_distances'] for p in predictions]
        results_df['all_confidences'] = [p['all_confidences'] for p in predictions]
    
    # Summary statistics
    n_assigned = (results_df['predicted_cluster'] != -1).sum()
    n_outliers = (results_df['predicted_cluster'] == -1).sum()
    
    print(f"✓ Predictions complete")
    print(f"  Assigned to clusters: {n_assigned} ({n_assigned/len(df)*100:.1f}%)")
    print(f"  Flagged as outliers: {n_outliers} ({n_outliers/len(df)*100:.1f}%)")
    print()
    
    # Cluster distribution
    if n_assigned > 0:
        print("Cluster distribution:")
        cluster_counts = results_df[results_df['predicted_cluster'] != -1]['predicted_cluster'].value_counts().sort_index()
        for cluster_id, count in cluster_counts.items():
            print(f"  Cluster {cluster_id}: {count} items")
        print()
    
    # Confidence statistics
    assigned_confidences = results_df[results_df['predicted_cluster'] != -1]['confidence']
    if len(assigned_confidences) > 0:
        print("Confidence statistics (assigned items):")
        print(f"  Mean: {assigned_confidences.mean():.3f}")
        print(f"  Median: {assigned_confidences.median():.3f}")
        print(f"  Min: {assigned_confidences.min():.3f}")
        print(f"  Max: {assigned_confidences.max():.3f}")
        print()
    
    print("="*60)
    print("INFERENCE COMPLETE")
    print("="*60)
    print()
    
    return results_df


def predict_with_interpretation(df, loaded_models, confidence_threshold=0.0):
    """
    Predict with human-readable interpretation of results
    
    Args:
        df: pandas DataFrame with new items
        loaded_models: dict from load_clustering_model()
        confidence_threshold: minimum confidence to assign
        
    Returns:
        pandas DataFrame with predictions and interpretation column
    """
    
    # Get predictions
    results_df = predict_batch(df, loaded_models, confidence_threshold, return_details=False)
    
    # Add interpretation
    def interpret_prediction(row):
        if row['predicted_cluster'] == -1:
            return f"OUTLIER (confidence: {row['confidence']:.3f})"
        elif row['confidence'] >= 0.7:
            return f"HIGH confidence - Cluster {row['predicted_cluster']} ({row['confidence']:.3f})"
        elif row['confidence'] >= 0.4:
            return f"MEDIUM confidence - Cluster {row['predicted_cluster']} ({row['confidence']:.3f})"
        else:
            return f"LOW confidence - Cluster {row['predicted_cluster']} ({row['confidence']:.3f})"
    
    results_df['interpretation'] = results_df.apply(interpret_prediction, axis=1)
    
    return results_df


def get_cluster_statistics(loaded_models):
    """
    Get statistics about the trained clusters
    
    Args:
        loaded_models: dict from load_clustering_model()
        
    Returns: 
        pandas DataFrame with cluster statistics
    """
    cluster_profiles = loaded_models['cluster_profiles']
    
    stats = []
    for cluster_id, profile in cluster_profiles.items():
        stats.append({
            'cluster_id': cluster_id,
            'size': profile['size'],
            'threshold': profile['threshold'],
            'medoid_norm': np.linalg.norm(profile['medoid'])
        })
    
    stats_df = pd.DataFrame(stats).sort_values('cluster_id')
    return stats_df


# Example usage and testing
if __name__ == "__main__":
    print("="*60)
    print("INFERENCE PIPELINE - USAGE EXAMPLES")
    print("="*60)
    print()
    
    print("Example 1: Predict single item")
    print("-" * 40)
    print("""
# Assume model is loaded
loaded = load_clustering_model('my_model')

# New item
new_item = pd.DataFrame({
    'Description': ['New electronic device with features'],
    'URL': ['https://example.com/new'],
    'comments': ['Good quality'],
    'Unit': ['pieces'],
    'Rate': [350.0]
})

# Predict
results = predict_batch(new_item, loaded, confidence_threshold=0.0)
print(results[['Description', 'predicted_cluster', 'confidence', 'interpretation']])
    """)
    print()
    
    print("Example 2: Predict batch with different confidence thresholds")
    print("-" * 40)
    print("""
# Stricter threshold - more outliers
results_strict = predict_batch(df, loaded, confidence_threshold=0.3)

# Lenient threshold - fewer outliers
results_lenient = predict_batch(df, loaded, confidence_threshold=0.0)

# Very conservative - only high confidence assignments
results_conservative = predict_batch(df, loaded, confidence_threshold=0.5)
    """)
    print()
    
    print("Example 3: Get detailed predictions")
    print("-" * 40)
    print("""
# Include all distances and confidences
results_detailed = predict_batch(df, loaded, return_details=True)

# See which clusters were considered for each item
print(results_detailed[['Description', 'predicted_cluster', 'all_confidences']].head())
    """)
    print()
    
    print("Example 4: Interpret predictions")
    print("-" * 40)
    print("""
# Get human-readable interpretations
results_interpreted = predict_with_interpretation(df, loaded)

# Filter by interpretation
high_conf = results_interpreted[results_interpreted['interpretation'].str.contains('HIGH')]
outliers = results_interpreted[results_interpreted['predicted_cluster'] == -1]
    """)
    print()
    
    print("Example 5: View cluster statistics")
    print("-" * 40)
    print("""
# Get stats about trained clusters
stats = get_cluster_statistics(loaded)
print(stats)

# Output:
#    cluster_id  size  threshold  medoid_norm
# 0           0    25      0.420        2.145
# 1           1    18      0.380        1.987
# 2           2    22      0.450        2.301
    """)