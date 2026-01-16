from __future__ import annotations

"""
Prefetch model weights into HF_HOME (default: /hf_cache in docker).

This is how you get a truly OFFLINE-capable setup:
1) Run this once while you have internet
2) Then run with HF_HUB_OFFLINE=1 / TRANSFORMERS_OFFLINE=1
"""

import os

from transformers import AutoModel, AutoModelForCausalLM, AutoProcessor, AutoTokenizer
from huggingface_hub import snapshot_download

from config import settings


def main() -> None:
    print(f"[prefetch] HF_HOME={os.getenv('HF_HOME')}")
    print(f"[prefetch] clip_model={settings.clip_model}")
    print(f"[prefetch] vlm_model={settings.vlm_model}")
    print(f"[prefetch] device={settings.device}")

    # Ensure repos are fully present in cache (helps offline mode).
    snapshot_download(repo_id=settings.clip_model, resume_download=True)
    snapshot_download(repo_id=settings.vlm_model, resume_download=True)

    # CLIP
    AutoProcessor.from_pretrained(settings.clip_model)
    AutoModel.from_pretrained(settings.clip_model)
    print("[prefetch] CLIP downloaded/available")

    # VLM
    # Some VLMs use AutoTokenizer (moondream2); others use AutoProcessor.
    try:
        AutoTokenizer.from_pretrained(settings.vlm_model, trust_remote_code=True)
    except Exception:
        pass
    try:
        AutoProcessor.from_pretrained(settings.vlm_model, trust_remote_code=True)
    except Exception:
        pass
    AutoModelForCausalLM.from_pretrained(settings.vlm_model, trust_remote_code=True)
    print("[prefetch] VLM downloaded/available")

    print("[prefetch] done")


if __name__ == "__main__":
    main()

