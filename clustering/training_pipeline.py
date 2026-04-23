# import
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.compose import ColumnTransformer
from sentence_transformers import SentenceTransformer
import umap
import hdbscan
import warnings
import joblib
import json
import numpy as np
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')
warnings.filterwarnings('ignore')

class FeatureTransformer:
    """Handles feature engineering for mixed data types"""
    def __init__(self, text_cols, categorical_cols, numerical_cols):
        """
            Args:
            text_cols: list of text column names
            categorical_cols: list of categorical column names
            numerical_cols: list of numerical column names
        """
        self.text_cols = text_cols
        self.categorical_cols = categorical_cols
        self.numerical_cols = numerical_cols
        
        # Initialize transformers
        self.sentence_model = SentenceTransformer('all-MiniLM-L6-v2')
        self.scaler = StandardScaler()
        self.encoder = OneHotEncoder(sparse_output=False, handle_unknown='ignore')
        
        self.is_fitted = False
        
    def fit_transform(self, df):
        """
        Fit transformers and transform the dataframe
        
        Args:
            df: pandas DataFrame with columns matching text_cols, categorical_cols, numerical_cols
            
        Returns:
            numpy array: transformed feature matrix
        """
        transformed_blocks = []
        
        # 1. Transform text columns
        if self.text_cols:
            # Combine all text columns into one string per row
            text_combined = df[self.text_cols].fillna('').agg(' '.join, axis=1).tolist()
            text_embeddings = self.sentence_model.encode(
                text_combined, 
                show_progress_bar=True,
                convert_to_numpy=True
            )
            transformed_blocks.append(text_embeddings)
            print(f"Text embeddings shape: {text_embeddings.shape}")
        
        # 2. Transform categorical columns
        if self.categorical_cols:
            cat_data = df[self.categorical_cols].fillna('MISSING')
            cat_encoded = self.encoder.fit_transform(cat_data)
            transformed_blocks.append(cat_encoded)
            print(f"Categorical encoded shape: {cat_encoded.shape}")
        
        # 3. Transform numerical columns
        if self.numerical_cols:
            num_data = df[self.numerical_cols].fillna(0).values
            num_scaled = self.scaler.fit_transform(num_data)
            transformed_blocks.append(num_scaled)
            print(f"Numerical scaled shape: {num_scaled.shape}")
        
        # Concatenate all transformed blocks
        X_transformed = np.hstack(transformed_blocks)
        
        # Weight blocks so each contributes equally to distance
        # Calculate average L2 norm per block and normalize
        block_start = 0
        for i, block in enumerate(transformed_blocks):
            block_end = block_start + block.shape[1]
            block_norm = np.linalg.norm(X_transformed[:, block_start:block_end], axis=1).mean()
            if block_norm > 0:
                X_transformed[:, block_start:block_end] /= block_norm
            block_start = block_end
        
        self.is_fitted = True
        print(f"Final transformed shape: {X_transformed.shape}")
        
        return X_transformed
    
    def transform(self, df):
        """
        Transform new data using fitted transformers
        
        Args:
            df: pandas DataFrame with same columns as training data
            
        Returns:
            numpy array: transformed feature matrix
        """
        if not self.is_fitted:
            raise ValueError("FeatureTransformer must be fitted before transform")
        
        transformed_blocks = []
        
        # 1. Transform text columns
        if self.text_cols:
            text_combined = df[self.text_cols].fillna('').agg(' '.join, axis=1).tolist()
            text_embeddings = self.sentence_model.encode(
                text_combined,
                show_progress_bar=False,
                convert_to_numpy=True
            )
            transformed_blocks.append(text_embeddings)
        
        # 2. Transform categorical columns
        if self.categorical_cols:
            cat_data = df[self.categorical_cols].fillna('MISSING')
            cat_encoded = self.encoder.transform(cat_data)
            transformed_blocks.append(cat_encoded)
        
        # 3. Transform numerical columns
        if self.numerical_cols:
            num_data = df[self.numerical_cols].fillna(0).values
            num_scaled = self.scaler.transform(num_data)
            transformed_blocks.append(num_scaled)
        
        # Concatenate and apply same weighting as in fit_transform
        X_transformed = np.hstack(transformed_blocks)
        
        return X_transformed


def calculate_hdbscan_params(n_samples, preference='conservative'):
    """
    Calculate HDBSCAN parameters based on dataset size
    
    Args:
        n_samples: number of items in dataset
        preference: 'conservative' (outlier > misclassification) or 'permissive'
        
    Returns:
        tuple: (min_cluster_size, min_samples)
    """
    if preference == 'conservative':
        cluster_pct = 0.02  # 2% of data
        sample_pct = 0.03   # 3% of data (higher for stricter core definition)
        min_abs_cluster = 5
        min_abs_sample = 3
    elif preference == 'permissive':
        cluster_pct = 0.015
        sample_pct = 0.02
        min_abs_cluster = 3
        min_abs_sample = 2
    else:
        raise ValueError("preference must be 'conservative' or 'permissive'")
    
    min_cluster_size = max(min_abs_cluster, int(cluster_pct * n_samples))
    min_samples_param = max(min_abs_sample, int(sample_pct * n_samples))
    
    # Ensure min_samples > min_cluster_size for conservative approach
    if preference == 'conservative' and min_samples_param <= min_cluster_size:
        min_samples_param = int(min_cluster_size * 1.5)
    
    return min_cluster_size, min_samples_param


def train_clustering_pipeline(df, preference='conservative'):
    """
    Complete training pipeline for HDBSCAN clustering
    
    Args:
        df: pandas DataFrame with columns:
            - Description (text)
            - URL (text)
            - comments (text)
            - Unit (categorical)
            - Rate (numerical)
        preference: 'conservative' or 'permissive'
        
    Returns:
        dict containing:
            - df_clustered: original dataframe with 'cluster_type' column
            - feature_transformer: fitted FeatureTransformer
            - umap_model: fitted UMAP model
            - hdbscan_model: fitted HDBSCAN model
            - cluster_profiles: dict of medoid and threshold per cluster
    """
    
    print("="*60)
    print("HDBSCAN CLUSTERING TRAINING PIPELINE")
    print("="*60)
    print(f"Dataset size: {len(df)} samples")
    print(f"Preference: {preference}")
    print()
    
    # Define column types
    text_cols = ['Description', 'URL', 'Comments']
    categorical_cols = ['Unit']
    numerical_cols = ['Rate']
    
    # Step 1: Feature Transformation
    print("Step 1: Feature Transformation")
    print("-" * 40)
    feature_transformer = FeatureTransformer(text_cols, categorical_cols, numerical_cols)
    X_transformed = feature_transformer.fit_transform(df)
    print()
    
    # Step 2: Dimensionality Reduction with UMAP
    print("Step 2: UMAP Dimensionality Reduction")
    print("-" * 40)
    umap_model = umap.UMAP(
        n_components=15,
        n_neighbors=15,
        min_dist=0.1,
        metric='euclidean',
        random_state=42
    )
    X_umap = umap_model.fit_transform(X_transformed)
    print(f"UMAP reduced shape: {X_umap.shape}")
    print()
    
    # Step 3: Calculate HDBSCAN parameters
    print("Step 3: Calculate HDBSCAN Parameters")
    print("-" * 40)
    min_cluster_size, min_samples = calculate_hdbscan_params(len(df), preference)
    print(f"min_cluster_size: {min_cluster_size}")
    print(f"min_samples: {min_samples}")
    print(f"Ratio (min_samples/min_cluster_size): {min_samples/min_cluster_size:.2f}")
    print()
    
    # Step 4: Train HDBSCAN
    print("Step 4: HDBSCAN Clustering")
    print("-" * 40)
    hdbscan_model = hdbscan.HDBSCAN(
        min_cluster_size=min_cluster_size,
        min_samples=min_samples,
        metric='euclidean',
        cluster_selection_method='eom',  # Excess of Mass
        prediction_data=True
    )
    hdbscan_model.fit(X_umap)
    
    labels = hdbscan_model.labels_
    probabilities = hdbscan_model.probabilities_
    
    n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
    n_outliers = (labels == -1).sum()
    outlier_rate = n_outliers / len(labels)
    
    print(f"Number of clusters found: {n_clusters}")
    print(f"Number of outliers: {n_outliers} ({outlier_rate:.1%})")
    print()
    
    # Step 5: Compute cluster profiles (medoid + threshold for each cluster)
    print("Step 5: Computing Cluster Profiles")
    print("-" * 40)
    cluster_profiles = {}
    
    for cluster_id in set(labels):
        if cluster_id == -1:  # Skip outliers
            continue
        
        # Get all points in this cluster
        cluster_mask = (labels == cluster_id)
        cluster_points = X_umap[cluster_mask]
        
        # Compute pairwise distances within cluster
        from scipy.spatial.distance import cdist
        pairwise_dist = cdist(cluster_points, cluster_points, metric='euclidean')
        
        # Find medoid: point with smallest average distance to others
        avg_distances = pairwise_dist.mean(axis=1)
        medoid_idx = np.argmin(avg_distances)
        medoid = cluster_points[medoid_idx]
        
        # Compute distances from all cluster members to medoid
        distances_to_medoid = np.linalg.norm(cluster_points - medoid, axis=1)
        
        # 90th percentile as threshold
        threshold = np.percentile(distances_to_medoid, 90)
        
        cluster_profiles[cluster_id] = {
            'medoid': medoid,
            'threshold': threshold,
            'size': cluster_mask.sum()
        }
        
        print(f"Cluster {cluster_id}: {cluster_mask.sum()} members, threshold={threshold:.4f}")
    
    print()
    
    # Step 6: Add cluster labels to dataframe
    print("Step 6: Adding cluster labels to dataframe")
    print("-" * 40)
    df_clustered = df.copy()
    df_clustered['cluster_type'] = labels
    df_clustered['cluster_probability'] = probabilities
    
    print("Cluster distribution:")
    print(df_clustered['cluster_type'].value_counts().sort_index())
    print()
    
    print("="*60)
    print("TRAINING COMPLETE")
    print("="*60)
    
    return {
        'df_clustered': df_clustered,
        'feature_transformer': feature_transformer,
        'umap_model': umap_model,
        'hdbscan_model': hdbscan_model,
        'cluster_profiles': cluster_profiles,
        'params': {
            'min_cluster_size': min_cluster_size,
            'min_samples': min_samples,
            'n_clusters': n_clusters,
            'outlier_rate': outlier_rate
        }
    }

def train_clustering_pipeline(df, preference='conservative'):
    """
    Complete training pipeline for HDBSCAN clustering
    
    Args:
        df: pandas DataFrame with columns:
            - Description (text)
            - URL (text)
            - comments (text)
            - Unit (categorical)
            - Rate (numerical)
        preference: 'conservative' or 'permissive'
        
    Returns:
        dict containing:
            - df_clustered: original dataframe with 'cluster_type' column
            - feature_transformer: fitted FeatureTransformer
            - umap_model: fitted UMAP model
            - hdbscan_model: fitted HDBSCAN model
            - cluster_profiles: dict of medoid and threshold per cluster
    """
    
    print("="*60)
    print("HDBSCAN CLUSTERING TRAINING PIPELINE")
    print("="*60)
    print(f"Dataset size: {len(df)} samples")
    print(f"Preference: {preference}")
    print()
    
    # Define column types
    text_cols = ['Description', 'URL', 'Comments']
    categorical_cols = ['Unit']
    numerical_cols = ['Rate']
    
    # Step 1: Feature Transformation
    print("Step 1: Feature Transformation")
    print("-" * 40)
    feature_transformer = FeatureTransformer(text_cols, categorical_cols, numerical_cols)
    X_transformed = feature_transformer.fit_transform(df)
    print()
    
    # Step 2: Dimensionality Reduction with UMAP
    print("Step 2: UMAP Dimensionality Reduction")
    print("-" * 40)
    umap_model = umap.UMAP(
        n_components=15,
        n_neighbors=15,
        min_dist=0.1,
        metric='euclidean',
        random_state=42
    )
    X_umap = umap_model.fit_transform(X_transformed)
    print(f"UMAP reduced shape: {X_umap.shape}")
    print()
    
    # Step 3: Calculate HDBSCAN parameters
    print("Step 3: Calculate HDBSCAN Parameters")
    print("-" * 40)
    min_cluster_size, min_samples = calculate_hdbscan_params(len(df), preference)
    print(f"min_cluster_size: {min_cluster_size}")
    print(f"min_samples: {min_samples}")
    print(f"Ratio (min_samples/min_cluster_size): {min_samples/min_cluster_size:.2f}")
    print()
    
    # Step 4: Train HDBSCAN
    print("Step 4: HDBSCAN Clustering")
    print("-" * 40)
    hdbscan_model = hdbscan.HDBSCAN(
        min_cluster_size=min_cluster_size,
        min_samples=min_samples,
        metric='euclidean',
        cluster_selection_method='eom',  # Excess of Mass
        prediction_data=True
    )
    hdbscan_model.fit(X_umap)
    
    labels = hdbscan_model.labels_
    probabilities = hdbscan_model.probabilities_
    
    n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
    n_outliers = (labels == -1).sum()
    outlier_rate = n_outliers / len(labels)
    
    print(f"Number of clusters found: {n_clusters}")
    print(f"Number of outliers: {n_outliers} ({outlier_rate:.1%})")
    print()
    
    # Step 5: Compute cluster profiles (medoid + threshold for each cluster)
    print("Step 5: Computing Cluster Profiles")
    print("-" * 40)
    cluster_profiles = {}
    
    for cluster_id in set(labels):
        if cluster_id == -1:  # Skip outliers
            continue
        
        # Get all points in this cluster
        cluster_mask = (labels == cluster_id)
        cluster_points = X_umap[cluster_mask]
        
        # Compute pairwise distances within cluster
        from scipy.spatial.distance import cdist
        pairwise_dist = cdist(cluster_points, cluster_points, metric='euclidean')
        
        # Find medoid: point with smallest average distance to others
        avg_distances = pairwise_dist.mean(axis=1)
        medoid_idx = np.argmin(avg_distances)
        medoid = cluster_points[medoid_idx]
        
        # Compute distances from all cluster members to medoid
        distances_to_medoid = np.linalg.norm(cluster_points - medoid, axis=1)
        
        # 90th percentile as threshold
        threshold = np.percentile(distances_to_medoid, 90)
        
        cluster_profiles[cluster_id] = {
            'medoid': medoid,
            'threshold': threshold,
            'size': cluster_mask.sum()
        }
        
        print(f"Cluster {cluster_id}: {cluster_mask.sum()} members, threshold={threshold:.4f}")
    
    print()
    
    # Step 6: Add cluster labels to dataframe
    print("Step 6: Adding cluster labels to dataframe")
    print("-" * 40)
    df_clustered = df.copy()
    df_clustered['cluster_type'] = labels
    df_clustered['cluster_probability'] = probabilities
    
    print("Cluster distribution:")
    print(df_clustered['cluster_type'].value_counts().sort_index())
    print()
    
    print("="*60)
    print("TRAINING COMPLETE")
    print("="*60)
    
    return {
        'df_clustered': df_clustered,
        'feature_transformer': feature_transformer,
        'umap_model': umap_model,
        'hdbscan_model': hdbscan_model,
        'cluster_profiles': cluster_profiles,
        'params': {
            'min_cluster_size': min_cluster_size,
            'min_samples': min_samples,
            'n_clusters': n_clusters,
            'outlier_rate': outlier_rate
        }
    }

def save_clustering_model(results, save_dir='clustering_model'):
    """
    Save all components of the trained clustering pipeline
    
    Args:
        results: Dictionary returned from train_clustering_pipeline()
        save_dir: Directory path where models will be saved
        
    Returns:
        dict: Paths to all saved files
    """
    # Create directory if it doesn't exist
    save_path = Path(save_dir)
    save_path.mkdir(parents=True, exist_ok=True)
    
    print("="*60)
    print("SAVING CLUSTERING MODEL")
    print("="*60)
    print(f"Save directory: {save_path.absolute()}")
    print()
    
    saved_files = {}
    
    # 1. Save Feature Transformer (includes scaler, encoder, sentence model reference)
    print("1. Saving Feature Transformer...")
    transformer_path = save_path / 'feature_transformer.joblib'
    joblib.dump(results['feature_transformer'], transformer_path)
    saved_files['feature_transformer'] = str(transformer_path)
    print(f"   ✓ Saved to {transformer_path.name}")
    
    # 2. Save UMAP Model
    print("2. Saving UMAP Model...")
    umap_path = save_path / 'umap_model.joblib'
    joblib.dump(results['umap_model'], umap_path)
    saved_files['umap_model'] = str(umap_path)
    print(f"   ✓ Saved to {umap_path.name}")
    
    # 3. Save HDBSCAN Model (optional but useful for reference)
    print("3. Saving HDBSCAN Model...")
    hdbscan_path = save_path / 'hdbscan_model.joblib'
    joblib.dump(results['hdbscan_model'], hdbscan_path)
    saved_files['hdbscan_model'] = str(hdbscan_path)
    print(f"   ✓ Saved to {hdbscan_path.name}")
    
    # 4. Save Cluster Profiles (convert numpy arrays to lists for JSON)
    print("4. Saving Cluster Profiles...")
    cluster_profiles_serializable = {}
    for cluster_id, profile in results['cluster_profiles'].items():
        cluster_profiles_serializable[str(cluster_id)] = {
            'medoid': profile['medoid'].tolist(),  # Convert numpy array to list
            'threshold': float(profile['threshold']),
            'size': int(profile['size'])
        }
    
    profiles_path = save_path / 'cluster_profiles.json'
    with open(profiles_path, 'w') as f:
        json.dump(cluster_profiles_serializable, f, indent=2)
    saved_files['cluster_profiles'] = str(profiles_path)
    print(f"   ✓ Saved to {profiles_path.name}")
    
    # 5. Save Training Parameters and Metadata
    print("5. Saving Metadata...")
    metadata = {
        'params': results['params'],
        'n_clusters': results['params']['n_clusters'],
        'outlier_rate': results['params']['outlier_rate'],
        'min_cluster_size': results['params']['min_cluster_size'],
        'min_samples': results['params']['min_samples']
    }
    
    metadata_path = save_path / 'metadata.json'
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)
    saved_files['metadata'] = str(metadata_path)
    print(f"   ✓ Saved to {metadata_path.name}")
    
    # 6. Save Clustered DataFrame (optional - for reference)
    print("6. Saving Clustered Data (optional)...")
    df_path = save_path / 'clustered_data.csv'
    results['df_clustered'].to_csv(df_path, index=False)
    saved_files['clustered_data'] = str(df_path)
    print(f"   ✓ Saved to {df_path.name}")
    
    print()
    print("="*60)
    print("✓ ALL MODELS SAVED SUCCESSFULLY")
    print("="*60)
    print(f"Total files saved: {len(saved_files)}")
    print(f"Directory size: {sum(f.stat().st_size for f in save_path.glob('*')) / 1024:.2f} KB")
    print()
    
    return saved_files


def load_clustering_model(load_dir='clustering_model'):
    """
    Load all components of a saved clustering pipeline
    
    Args:
        load_dir: Directory path where models were saved
        
    Returns:
        dict: Dictionary containing all loaded models and profiles
    """
    load_path = Path(load_dir)
    
    if not load_path.exists():
        raise ValueError(f"Model directory not found: {load_path.absolute()}")
    
    print("="*60)
    print("LOADING CLUSTERING MODEL")
    print("="*60)
    print(f"Load directory: {load_path.absolute()}")
    print()
    
    loaded_models = {}
    
    # 1. Load Feature Transformer
    print("1. Loading Feature Transformer...")
    transformer_path = load_path / 'feature_transformer.joblib'
    if not transformer_path.exists():
        raise FileNotFoundError(f"Feature transformer not found: {transformer_path}")
    loaded_models['feature_transformer'] = joblib.load(transformer_path)
    print(f"   ✓ Loaded from {transformer_path.name}")
    
    # 2. Load UMAP Model
    print("2. Loading UMAP Model...")
    umap_path = load_path / 'umap_model.joblib'
    if not umap_path.exists():
        raise FileNotFoundError(f"UMAP model not found: {umap_path}")
    loaded_models['umap_model'] = joblib.load(umap_path)
    print(f"   ✓ Loaded from {umap_path.name}")
    
    # 3. Load HDBSCAN Model (optional)
    print("3. Loading HDBSCAN Model...")
    hdbscan_path = load_path / 'hdbscan_model.joblib'
    if hdbscan_path.exists():
        loaded_models['hdbscan_model'] = joblib.load(hdbscan_path)
        print(f"   ✓ Loaded from {hdbscan_path.name}")
    else:
        loaded_models['hdbscan_model'] = None
        print(f"   ⚠ HDBSCAN model not found (optional)")
    
    # 4. Load Cluster Profiles
    print("4. Loading Cluster Profiles...")
    profiles_path = load_path / 'cluster_profiles.json'
    if not profiles_path.exists():
        raise FileNotFoundError(f"Cluster profiles not found: {profiles_path}")
    
    with open(profiles_path, 'r') as f:
        cluster_profiles_json = json.load(f)
    
    # Convert back to proper format (lists → numpy arrays, string keys → int keys)
    cluster_profiles = {}
    for cluster_id_str, profile in cluster_profiles_json.items():
        cluster_profiles[int(cluster_id_str)] = {
            'medoid': np.array(profile['medoid']),
            'threshold': profile['threshold'],
            'size': profile['size']
        }
    
    loaded_models['cluster_profiles'] = cluster_profiles
    print(f"   ✓ Loaded {len(cluster_profiles)} cluster profiles")
    
    # 5. Load Metadata
    print("5. Loading Metadata...")
    metadata_path = load_path / 'metadata.json'
    if metadata_path.exists():
        with open(metadata_path, 'r') as f:
            loaded_models['metadata'] = json.load(f)
        print(f"   ✓ Loaded metadata")
        print(f"      - Clusters: {loaded_models['metadata']['n_clusters']}")
        print(f"      - Outlier rate: {loaded_models['metadata']['outlier_rate']:.1%}")
    else:
        loaded_models['metadata'] = None
        print(f"   ⚠ Metadata not found (optional)")
    
    print()
    print("="*60)
    print("✓ ALL MODELS LOADED SUCCESSFULLY")
    print("="*60)
    print()
    
    return loaded_models