"""Exclude heavy ML frameworks from faster-whisper / ctranslate2 bundling.

faster-whisper uses CTranslate2 (C++), not torch/tensorflow. But PyInstaller's
_collect_submodules may follow imports into torch -> tensorboard -> tensorflow
if those are installed on the host. This hook blocks them.
"""
import os

excluded = {
    "torch", "torchvision", "torchaudio",
    "tensorboard", "tensorflow", "tensorflow_intel", "keras",
    "jax", "flax", "optax",
    "transformers", "tokenizers", "huggingface_hub", "safetensors",
    "onnxruntime", "onnxruntime_cxx",
    "sklearn", "scipy", "pandas", "matplotlib", "PIL", "cv2",
    "notebook", "jupyter", "jupyter_client", "jupyter_core", "IPython",
    "pytest", "_pytest",
}

# PyInstaller reads `excludedimports` from hook globals.
excludedimports = list(sorted(excluded))
