"""
Shared embedding service.

Both the text-query mode and the image-upload mode produce embeddings
in the SAME vector space via CLIP, so both can be compared against the
same `products.embedding` column using one similarity search.
"""

import io

import open_clip
import torch
from PIL import Image

from app.config import settings

_model = None
_preprocess = None
_tokenizer = None
_device = "cuda" if torch.cuda.is_available() else "cpu"


def load_model() -> None:
    """Load the CLIP model once on startup — this is slow, don't call per-request."""
    global _model, _preprocess, _tokenizer

    _model, _, _preprocess = open_clip.create_model_and_transforms(
        settings.clip_model_name,
        pretrained=settings.clip_pretrained,
    )
    _tokenizer = open_clip.get_tokenizer(settings.clip_model_name)
    _model.to(_device)
    _model.eval()


def embed_text(text: str) -> list[float]:
    if _model is None:
        raise RuntimeError("Model not loaded — call load_model() on startup")

    tokens = _tokenizer([text]).to(_device)
    with torch.no_grad():
        features = _model.encode_text(tokens)
        features /= features.norm(dim=-1, keepdim=True)

    return features[0].cpu().tolist()


def embed_image(image_bytes: bytes) -> list[float]:
    if _model is None:
        raise RuntimeError("Model not loaded — call load_model() on startup")

    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    tensor = _preprocess(image).unsqueeze(0).to(_device)

    with torch.no_grad():
        features = _model.encode_image(tensor)
        features /= features.norm(dim=-1, keepdim=True)

    return features[0].cpu().tolist()