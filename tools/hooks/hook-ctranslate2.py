"""Exclude heavy ML frameworks from ctranslate2 bundling."""
excludedimports = [
    "torch", "torchvision", "torchaudio",
    "tensorboard", "tensorflow", "tensorflow_intel", "keras",
    "jax", "flax", "optax",
    "transformers", "tokenizers", "huggingface_hub", "safetensors",
    "onnxruntime", "onnxruntime_cxx",
    "sklearn", "scipy", "pandas", "matplotlib", "PIL", "cv2",
    "notebook", "jupyter", "jupyter_client", "jupyter_core", "IPython",
    "pytest", "_pytest",
]
