"""Image preprocessing and manipulation module."""
from __future__ import annotations

import io
from typing import Sequence
from PIL import Image, ImageEnhance, ImageFilter, ImageOps


class ImageProcessor:
    @staticmethod
    def load_image(data: bytes) -> Image.Image:
        """Load image bytes into an RGB PIL Image with EXIF orientation correction."""
        image = Image.open(io.BytesIO(data))
        # Correct orientation if EXIF tags are present
        image = ImageOps.exif_transpose(image)
        return image.convert("RGB")

    @staticmethod
    def preprocess_for_ocr(image: Image.Image) -> Image.Image:
        """Apply light contrast adjustment to enhance OCR accuracy without introducing sharpening artifacts."""
        enhancer = ImageEnhance.Contrast(image)
        return enhancer.enhance(1.1)

    @staticmethod
    def crop_region(image: Image.Image, bbox: Sequence[float], padding: int = 4) -> Image.Image:
        """Safely crop a bounding box [x1, y1, x2, y2] with optional padding."""
        img_w, img_h = image.size
        x1 = max(0, int(bbox[0]) - padding)
        y1 = max(0, int(bbox[1]) - padding)
        x2 = min(img_w, int(bbox[2]) + padding)
        y2 = min(img_h, int(bbox[3]) + padding)

        # Guard against zero-area crops
        if x2 <= x1:
            x2 = min(img_w, x1 + 10)
        if y2 <= y1:
            y2 = min(img_h, y1 + 10)

        return image.crop((x1, y1, x2, y2))


image_processor = ImageProcessor()
