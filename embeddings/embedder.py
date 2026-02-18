import yaml
import torch
from pathlib import Path
from typing import List, Union
from sentence_transformers import SentenceTransformer

class Embedder:
    """
    A class to handle text embedding generation using SentenceTransformers.
    """

    def __init__(self, config_path: str = "settings.yaml"):
        """
        Initializes the Embedder with the model specified in settings.yaml.

        Args:
            config_path (str): Path to the settings.yaml file.
        """
        # Limit torch to 1 thread per process to prevent CPU saturation
        # This is critical for preventing system hangs in multi-process/agent environments
        torch.set_num_threads(1)
        
        self.config = self._load_config(config_path)
        self.model_name = self.config.get("model_name", "all-MiniLM-L6-v2")
        self.model = SentenceTransformer(self.model_name)

    def _load_config(self, config_path: str) -> dict:
        """Loads configuration from a YAML file."""
        path = Path(config_path)
        if not path.exists():
            return {}
        with open(path, "r") as f:
            return yaml.safe_load(f)

    def embed(self, text: str) -> List[float]:
        """
        Generates an embedding for the given text.

        Args:
            text (str): The text to embed.

        Returns:
            List[float]: The generated embedding vector.
        """
        if not text:
            return []
        
        embedding = self.model.encode(text)
        return embedding.tolist()

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generates embeddings for a batch of texts.

        Args:
            texts (List[str]): List of texts to embed.

        Returns:
            List[List[float]]: List of generated embedding vectors.
        """
        if not texts:
            return []
        
        embeddings = self.model.encode(texts)
        return embeddings.tolist()
