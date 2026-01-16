from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

import os
import shutil
import torch
from PIL import Image
from transformers import AutoModel, AutoModelForCausalLM, AutoProcessor, AutoTokenizer
from huggingface_hub import snapshot_download


def _pick_device(requested: str) -> str:
    if requested == "cpu":
        return "cpu"
    if requested == "cuda":
        return "cuda" if torch.cuda.is_available() else "cpu"
    # auto
    return "cuda" if torch.cuda.is_available() else "cpu"


@dataclass(frozen=True)
class FoodCheck:
    is_food: bool
    food_confidence: float


class ClipFoodDetector:
    def __init__(self, model_name: str, device: str = "auto") -> None:
        self.device = _pick_device(device)
        self.processor = AutoProcessor.from_pretrained(model_name)
        self.model = AutoModel.from_pretrained(model_name).to(self.device)
        self.model.eval()

        # Two-label zero-shot classification.
        self.labels = ["a photo of food", "a photo of a non-food object"]

    @torch.inference_mode()
    def predict(self, image: Image.Image) -> FoodCheck:
        inputs = self.processor(text=self.labels, images=image, return_tensors="pt", padding=True).to(self.device)
        outputs = self.model(**inputs)
        logits_per_image = outputs.logits_per_image  # [1, 2]
        probs = logits_per_image.softmax(dim=1).detach().cpu().numpy()[0].tolist()
        p_food = float(probs[0])
        return FoodCheck(is_food=p_food >= 0.5, food_confidence=p_food)

    @torch.inference_mode()
    def top_text_match(self, image: Image.Image, texts: list[str]) -> tuple[int, float]:
        """
        Returns (best_index, best_probability) over the provided texts.
        Uses CLIP logits_per_image softmax across the candidates.
        """
        inputs = self.processor(text=texts, images=image, return_tensors="pt", padding=True).to(self.device)
        outputs = self.model(**inputs)
        probs = outputs.logits_per_image.softmax(dim=1).detach().cpu().numpy()[0].tolist()
        best_idx = int(max(range(len(probs)), key=lambda i: probs[i]))
        return best_idx, float(probs[best_idx])


def _extract_json(text: str) -> dict[str, Any] | None:
    # Try to find the first {...} block.
    m = re.search(r"\{[\s\S]*\}", text)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


def _coerce_confidence(v: Any) -> float:
    """
    Normalize confidence to [0, 1].

    Some VLMs may return:
    - 0..1 (already normalized)
    - 0..100 (percent)
    - strings like "60%" / "0.6"
    """
    if v is None:
        return 0.5

    if isinstance(v, str):
        s = v.strip()
        if s.endswith("%"):
            try:
                n = float(s[:-1].strip())
                return max(0.0, min(1.0, n / 100.0))
            except Exception:
                return 0.5
        try:
            v = float(s)
        except Exception:
            return 0.5

    try:
        n = float(v)
    except Exception:
        return 0.5

    # Heuristic: 2..100 probably means percent.
    if n > 1.0 and n <= 100.0:
        n = n / 100.0

    # Clamp.
    return max(0.0, min(1.0, n))


class LocalVLM:
    """
    A small local VLM wrapper. Default model is moondream2 (lightweight).

    Note: Many VLMs require `trust_remote_code=True` and can vary in API.
    This wrapper supports a pragmatic "generate text and extract JSON" approach.
    """

    def __init__(self, model_name: str, device: str = "auto") -> None:
        if not model_name:
            raise ValueError("VLM model_name is empty. Set VLM_MODEL to a valid model id or local path.")
        self.device = _pick_device(device)
        self.model_name = model_name

        # Resolve model to a local directory so missing weights produce a clear error.
        # This also avoids a transformers edge-case where resolved weight path can be None and crash with:
        # AttributeError: 'NoneType' object has no attribute 'endswith'
        self.model_path = self._resolve_to_local_path(model_name)

        # Moondream-style models expose encode_image + answer_question; use that if available.
        self.tokenizer = None
        self.processor = None

        self.model = AutoModelForCausalLM.from_pretrained(
            self.model_path,
            trust_remote_code=True,
            torch_dtype=torch.float16 if self.device == "cuda" else torch.float32,
        ).to(self.device)
        self.model.eval()

        # Try tokenizer first (moondream2 commonly uses AutoTokenizer).
        try:
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_path, trust_remote_code=True)
        except Exception:
            self.tokenizer = None

        # Try processor for generic VLMs (or if moondream tokenizer isn't present).
        try:
            self.processor = AutoProcessor.from_pretrained(self.model_path, trust_remote_code=True)
        except Exception:
            self.processor = None

    def _resolve_to_local_path(self, model_name: str) -> str:
        # If user provided a local path, use it.
        if os.path.exists(model_name):
            return model_name

        # Otherwise treat as a Hugging Face repo id. This requires internet unless offline cache exists.
        offline = os.getenv("HF_HUB_OFFLINE", "0").strip() in ("1", "true", "yes", "on")
        try:
            snapshot_path = snapshot_download(
                repo_id=model_name,
                local_files_only=offline,
                resume_download=True,
            )
            # Fix a common transformers remote-code cache issue:
            # `transformers` copies python files into HF_HOME/modules/transformers_modules/<commit>/.
            # If that directory exists but is incomplete (e.g. missing layers.py), model loading fails with:
            # FileNotFoundError: .../transformers_modules/<commit>/layers.py
            self._repair_transformers_modules_cache(snapshot_path)
            return snapshot_path
        except Exception as e:
            hint = (
                "Model weights are not available locally. Run `docker compose run --rm prefetch` once (online), "
                "then rerun with HF_HUB_OFFLINE=1/TRANSFORMERS_OFFLINE=1 for offline."
            )
            raise RuntimeError(f"Failed to resolve VLM model '{model_name}'. {hint}. Root error: {e}") from e

    def _repair_transformers_modules_cache(self, snapshot_path: str) -> None:
        hf_home = os.getenv("HF_HOME") or os.path.expanduser("~/.cache/huggingface")
        commit = os.path.basename(snapshot_path.rstrip("/"))
        modules_dir = os.path.join(hf_home, "modules", "transformers_modules", commit)
        # `transformers` copies remote-code python files into:
        #   HF_HOME/modules/transformers_modules/<commit>/
        #
        # We have observed this directory can become *incomplete* (e.g. missing layers.py),
        # which breaks model loading with:
        #   FileNotFoundError: .../transformers_modules/<commit>/layers.py
        #
        # To make this robust, we ensure all *.py files from the snapshot exist in the modules cache.
        os.makedirs(modules_dir, exist_ok=True)

        # Ensure package init exists.
        init_path = os.path.join(modules_dir, "__init__.py")
        if not os.path.exists(init_path):
            open(init_path, "a", encoding="utf-8").close()

        for fname in os.listdir(snapshot_path):
            if not fname.endswith(".py"):
                continue
            src = os.path.join(snapshot_path, fname)
            dst = os.path.join(modules_dir, fname)
            if os.path.exists(src) and not os.path.exists(dst):
                shutil.copy2(src, dst)

    @torch.inference_mode()
    def describe_food_json(self, image: Image.Image) -> dict[str, Any]:
        prompt = (
            "You are a nutrition assistant. Identify the food in the image.\n"
            "Return ONLY valid JSON with these keys:\n"
            '{ "dish_name": string, "portion_label": string, "confidence": number }\n'
            "Rules:\n"
            "- dish_name should be short (e.g. 'mixed green salad', 'fried chicken').\n"
            "- portion_label examples: '1 bowl', '2 slices', '6 pieces', '1 plate', 'medium serving'.\n"
        )

        text: str | None = None

        # Preferred path for moondream-style remote-code models.
        if hasattr(self.model, "encode_image") and hasattr(self.model, "answer_question") and self.tokenizer is not None:
            enc = self.model.encode_image(image)  # type: ignore[attr-defined]
            text = self.model.answer_question(enc, prompt, self.tokenizer)  # type: ignore[attr-defined]

        # Generic VLM fallback path.
        if text is None:
            if self.processor is None:
                raise RuntimeError(
                    "VLM processor/tokenizer unavailable. Model requires a Processor or moondream-style tokenizer."
                )
            inputs = self.processor(text=prompt, images=image, return_tensors="pt")
            # Some processors return a dict; some return BatchFeature. Try to move tensors only.
            try:
                inputs = inputs.to(self.device)  # type: ignore[union-attr]
            except Exception:
                for k, v in list(inputs.items()):  # type: ignore[union-attr]
                    if torch.is_tensor(v):
                        inputs[k] = v.to(self.device)
            out = self.model.generate(**inputs, max_new_tokens=200)
            text = self.processor.decode(out[0], skip_special_tokens=True)

        j = _extract_json(text)
        if not j:
            # Fallback: very defensive default.
            return {"dish_name": "food", "portion_label": "1 serving", "confidence": 0.5}

        # Normalize keys.
        return {
            "dish_name": str(j.get("dish_name") or j.get("dish") or "food"),
            "portion_label": str(j.get("portion_label") or j.get("portion") or "1 serving"),
            "confidence": _coerce_confidence(j.get("confidence")),
        }

