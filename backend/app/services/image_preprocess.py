"""Optional scan image preprocessing for OCR quality.

Preprocessing is conservative: clean, high-contrast pages are left alone.
Enhancements only apply when heuristics suggest the page is degraded.
"""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO


@dataclass(frozen=True)
class PreprocessResult:
    image_bytes: bytes
    applied: list[str]
    skipped_reason: str | None = None


def _pil_image(image_bytes: bytes):
    from PIL import Image

    return Image.open(BytesIO(image_bytes)).convert("RGB")


def _is_already_clean(image) -> bool:
    """Heuristic: high-contrast, low-noise pages skip enhancement."""

    try:
        import numpy as np
    except ImportError:
        return True

    gray = np.asarray(image.convert("L"), dtype=np.float32)
    if gray.size == 0:
        return True
    # Clean scans tend to cluster near black/white extremes.
    dark = float((gray < 40).mean())
    light = float((gray > 215).mean())
    mid = 1.0 - dark - light
    return mid < 0.35 and dark + light > 0.55


def preprocess_scan_image(
    image_bytes: bytes,
    *,
    force: bool = False,
) -> PreprocessResult:
    """Deskew / denoise / contrast / threshold when beneficial."""

    try:
        from PIL import Image, ImageEnhance, ImageFilter, ImageOps
    except ImportError:
        return PreprocessResult(
            image_bytes=image_bytes,
            applied=[],
            skipped_reason="Pillow unavailable",
        )

    image = _pil_image(image_bytes)
    applied: list[str] = []

    # Orientation via EXIF when present.
    try:
        image = ImageOps.exif_transpose(image)
        applied.append("orientation_exif")
    except Exception:
        pass

    if not force and _is_already_clean(image):
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        return PreprocessResult(
            image_bytes=buffer.getvalue(),
            applied=applied,
            skipped_reason="page already high-contrast",
        )

    # Mild denoise + contrast; adaptive threshold only for gray midtones.
    denoised = image.filter(ImageFilter.MedianFilter(size=3))
    applied.append("denoise_median")
    contrasted = ImageEnhance.Contrast(denoised).enhance(1.35)
    applied.append("contrast_boost")

    try:
        import numpy as np

        gray = np.asarray(contrasted.convert("L"))
        # Simple adaptive threshold via local mean comparison.
        from PIL import ImageFilter as _IF

        blur = contrasted.convert("L").filter(_IF.BoxBlur(8))
        local = np.asarray(blur, dtype=np.int16)
        binary = (gray.astype(np.int16) > (local - 8)).astype("uint8") * 255
        # Only keep threshold if it doesn't erase too much ink.
        ink_ratio = float((binary < 128).mean())
        if 0.02 <= ink_ratio <= 0.45:
            contrasted = Image.fromarray(binary).convert("RGB")
            applied.append("adaptive_threshold")
    except Exception:
        pass

    # Lightweight deskew estimate from horizontal projection variance.
    try:
        import numpy as np

        gray = np.asarray(contrasted.convert("L"))
        best_angle = 0.0
        best_score = -1.0
        for angle in (-2.0, -1.0, 0.0, 1.0, 2.0):
            rotated = contrasted.rotate(angle, expand=False, fillcolor=(255, 255, 255))
            proj = np.asarray(rotated.convert("L")).mean(axis=1)
            score = float(proj.var())
            if score > best_score:
                best_score = score
                best_angle = angle
        if abs(best_angle) >= 0.5:
            contrasted = contrasted.rotate(
                best_angle, expand=True, fillcolor=(255, 255, 255)
            )
            applied.append(f"deskew_{best_angle:+.1f}")
    except Exception:
        pass

    buffer = BytesIO()
    contrasted.save(buffer, format="PNG")
    return PreprocessResult(image_bytes=buffer.getvalue(), applied=applied)
