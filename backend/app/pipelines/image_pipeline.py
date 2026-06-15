import os
from typing import List, Dict, Any
from uuid import UUID
from app.pipelines.base import BaseIngestPipeline


class ImageIngestPipeline(BaseIngestPipeline):
    """处理图片：OCR 提取文本并抽取 EXIF 元数据。"""

    @property
    def supported_types(self) -> List[str]:
        return [
            "image",
            "jpg", "jpeg", "png", "gif",
            "webp", "bmp", "tiff", "tif",
        ]

    def process(
        self,
        file_path: str,
        doc_id: UUID,
        metadata: Dict[str, Any] = None,
    ) -> List[Dict[str, Any]]:
        metadata = metadata or {}
        image_description = metadata.get("description") or "图片内容"

        ocr_text = self._extract_ocr(file_path)
        exif_metadata = self._extract_exif(file_path)

        content_parts = [image_description]
        if ocr_text and ocr_text != "[OCR_UNAVAILABLE]":
            content_parts.extend(["[OCR_TEXT]", ocr_text, "[/OCR_TEXT]"])
        content = "\n".join(content_parts)

        merged_meta = {**metadata, **exif_metadata}

        return [{
            "content": content,
            "modality": "image",
            "chunk_index": 0,
            "position_info": {
                "type": "image",
                "file_name": os.path.basename(file_path),
                "original_path": file_path,
            },
            "metadata": merged_meta,
        }]

    def _extract_ocr(self, file_path: str) -> str:
        """使用 pytesseract 进行 OCR，未安装时返回占位提示。"""
        try:
            from PIL import Image
            import pytesseract

            image = Image.open(file_path)
            return pytesseract.image_to_string(image, lang="chi_sim+eng")
        except Exception:
            # TODO: 安装 pytesseract 与对应语言包后启用图片 OCR。
            return "[OCR_UNAVAILABLE]"

    def _extract_exif(self, file_path: str) -> Dict[str, Any]:
        """抽取图片 EXIF 元数据。"""
        try:
            from PIL import Image
            from PIL.ExifTags import TAGS

            image = Image.open(file_path)
            exif = image._getexif()
            if not exif:
                return {}
            return {
                TAGS.get(tag_id, tag_id): str(value)
                for tag_id, value in exif.items()
            }
        except Exception:
            return {}
