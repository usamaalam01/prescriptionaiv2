"""Image preprocessing for messy handwritten prescription OCR.

Best-practice stack (privacy-preserving decision-support only — not clinical care):
  1. EXIF orientation + RGB
  2. Optional blue-ink isolation (boosts cursive on white pads)
  3. Autocontrast + contrast/sharpen
  4. Deskew via projection-profile angle search
  5. Optional adaptive (local) binarization for extreme mess
  6. Resize longest side to Vision-friendly max

Uses Pillow always; OpenCV/NumPy when installed for faster/more accurate deskew.
"""

from __future__ import annotations

import io
import logging
import math
from typing import Any

logger = logging.getLogger(__name__)


def preprocess_prescription_image(
    image_bytes: bytes,
    *,
    deskew: bool = True,
    ink_isolate: bool = True,
    adaptive_binarize: bool = True,
    sharpen: bool = True,
    max_side: int = 2400,
) -> bytes:
    """Return enhanced PNG bytes for OCR; falls back to original on failure."""
    try:
        from PIL import Image, ImageEnhance, ImageFilter, ImageOps
    except Exception as exc:  # noqa: BLE001
        logger.debug("Pillow unavailable for OCR preprocess: %s", exc)
        return image_bytes

    try:
        img = Image.open(io.BytesIO(image_bytes))
        img = ImageOps.exif_transpose(img)
        img = img.convert("RGB")

        stages: list[str] = ["exif_rgb"]

        if ink_isolate:
            img = _isolate_blue_ink(img)
            stages.append("blue_ink")

        img = ImageOps.autocontrast(img, cutoff=1)
        img = ImageEnhance.Contrast(img).enhance(1.35)
        if sharpen:
            img = ImageEnhance.Sharpness(img).enhance(1.45)
            img = img.filter(ImageFilter.UnsharpMask(radius=1.2, percent=130, threshold=2))
            stages.append("contrast_sharpen")

        if deskew:
            angled = _deskew_image(img)
            if angled is not img:
                img = angled
                stages.append("deskew")

        if adaptive_binarize:
            # Keep RGB 3-channel so Vision still sees a photo-like document;
            # blend binarized ink mask lightly rather than pure 1-bit (Vision prefers tone).
            img = _soft_binarize_blend(img)
            stages.append("soft_binarize")

        w, h = img.size
        scale = min(1.0, max_side / float(max(w, h)))
        if scale < 1.0:
            img = img.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.Resampling.LANCZOS)
            stages.append("resize")

        out = io.BytesIO()
        img.save(out, format="PNG", optimize=True)
        logger.info("OCR preprocess stages: %s", "+".join(stages))
        return out.getvalue()
    except Exception as exc:  # noqa: BLE001
        logger.warning("OCR preprocess failed; using original image: %s", exc)
        return image_bytes


def _isolate_blue_ink(img: Any) -> Any:
    """Boost blue/black ink and suppress warm paper background."""
    from PIL import Image

    r, g, b = img.split()
    # Ink score: dark + blue-dominant (or near-black)
    # out = clip( (B*1.2 + (255-R)*0.4 + (255-G)*0.3) )
    rf = r.point(lambda x: int(max(0, min(255, (255 - x) * 0.35))))
    gf = g.point(lambda x: int(max(0, min(255, (255 - x) * 0.25))))
    bf = b.point(lambda x: int(max(0, min(255, x * 1.15))))
    # Merge into grayscale ink mask then composite onto white
    from PIL import ImageChops

    mask = ImageChops.add(ImageChops.add(bf, rf), gf)
    mask = mask.point(lambda x: 255 if x > 90 else int(x * 1.4) if x > 40 else 0)
    # Dark ink on white
    ink = ImageChops.invert(mask).convert("L")
    rgb = Image.merge("RGB", (ink, ink, ink))
    # Blend with original so Vision still sees some color cues
    return Image.blend(img, rgb, 0.55)


def _soft_binarize_blend(img: Any) -> Any:
    """Local contrast + soft threshold blend (keeps grayscale tones for Vision)."""
    from PIL import Image, ImageFilter, ImageOps, ImageChops

    gray = ImageOps.grayscale(img)
    # Local mean approximation via large-box blur
    local = gray.filter(ImageFilter.BoxBlur(12))
    # ink where gray is darker than local mean
    diff = ImageChops.subtract(local, gray)
    binary = diff.point(lambda x: 0 if x > 12 else 255)
    binary_rgb = Image.merge("RGB", (binary, binary, binary))
    return Image.blend(img.convert("RGB"), binary_rgb, 0.4)


def _deskew_image(img: Any) -> Any:
    """Estimate skew angle and rotate. Prefers OpenCV; falls back to PIL projection."""
    try:
        return _deskew_cv2(img)
    except Exception:  # noqa: BLE001
        return _deskew_pil(img)


def _deskew_cv2(img: Any) -> Any:
    import numpy as np
    import cv2
    from PIL import Image

    arr = np.array(img.convert("RGB"))
    gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
    gray = cv2.bitwise_not(gray)
    thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]
    coords = np.column_stack(np.where(thresh > 0))
    if coords.size < 100:
        return img
    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle
    if abs(angle) < 0.15 or abs(angle) > 15:
        return img
    (h, w) = arr.shape[:2]
    center = (w // 2, h // 2)
    m = cv2.getRotationMatrix2D(center, angle, 1.0)
    rotated = cv2.warpAffine(
        arr, m, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE
    )
    return Image.fromarray(rotated)


def _deskew_pil(img: Any) -> Any:
    """Coarse deskew by maximizing horizontal projection variance over ±8°."""
    from PIL import ImageOps

    gray = ImageOps.grayscale(img)
    # Downscale for speed
    small = gray.resize((min(800, gray.width), max(1, int(gray.height * min(800, gray.width) / gray.width))))
    best_angle = 0.0
    best_score = -1.0
    for angle in (x * 0.5 for x in range(-16, 17)):  # -8 .. +8
        rotated = small.rotate(angle, expand=False, fillcolor=255)
        score = _projection_variance(rotated)
        if score > best_score:
            best_score = score
            best_angle = angle
    if abs(best_angle) < 0.25:
        return img
    return img.rotate(best_angle, expand=True, fillcolor=(255, 255, 255))


def _projection_variance(gray_img: Any) -> float:
    w, h = gray_img.size
    # Sample every other row for speed
    pixels = list(gray_img.getdata())
    row_sums: list[float] = []
    for y in range(0, h, 2):
        row = pixels[y * w : (y + 1) * w]
        # Count dark ink
        row_sums.append(sum(1 for p in row if p < 140))
    if not row_sums:
        return 0.0
    mean = sum(row_sums) / len(row_sums)
    return sum((v - mean) ** 2 for v in row_sums) / len(row_sums)


def preprocess_status() -> dict[str, bool]:
    """Report which native accelerate libs are available."""
    status = {"pillow": True, "numpy": False, "opencv": False}
    try:
        import numpy  # noqa: F401

        status["numpy"] = True
    except Exception:  # noqa: BLE001
        pass
    try:
        import cv2  # noqa: F401

        status["opencv"] = True
    except Exception:  # noqa: BLE001
        pass
    return status
