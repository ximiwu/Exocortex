from __future__ import annotations

import math
from pathlib import Path

from PySide6 import QtCore, QtGui

from codex.pdf2img import convert_pdf_to_images

from assets.assets_manager import ask_tutor, asset_init, group_dive_in, integrate
from ..pymupdf_compat import fitz
from ..renderer import PdfRenderer


class _RenderSignals(QtCore.QObject):
    finished = QtCore.Signal(int, int, QtGui.QImage)
    failed = QtCore.Signal(int, int, str)


class _RenderTask(QtCore.QRunnable):
    def __init__(self, renderer: PdfRenderer, page_index: int, generation: int) -> None:
        super().__init__()
        self._renderer = renderer
        self._page_index = page_index
        self._generation = generation
        self.signals = _RenderSignals()

    def run(self) -> None:
        try:
            image = self._renderer.render_page(self._page_index)
        except Exception as exc:  # pragma: no cover - GUI runtime path
            self.signals.failed.emit(self._page_index, self._generation, str(exc))
            return
        self.signals.finished.emit(self._page_index, self._generation, image)


class _AssetInitSignals(QtCore.QObject):
    progress = QtCore.Signal(str)
    finished = QtCore.Signal(str)
    failed = QtCore.Signal(str)


class _AssetInitTask(QtCore.QRunnable):
    def __init__(self, source_path: str, asset_name: str, rendered_pdf_path: str | None = None) -> None:
        super().__init__()
        self._source_path = source_path
        self._asset_name = asset_name
        self._rendered_pdf_path = rendered_pdf_path
        self.signals = _AssetInitSignals()

    def run(self) -> None:
        try:
            asset_init(
                self._source_path,
                self._asset_name,
                progress_callback=self.signals.progress.emit,
                rendered_pdf_path=self._rendered_pdf_path,
            )
        except Exception as exc:  # pragma: no cover - GUI runtime path
            self.signals.failed.emit(str(exc))
            return
        self.signals.finished.emit(self._asset_name)


class _CompressSignals(QtCore.QObject):
    finished = QtCore.Signal(str)
    failed = QtCore.Signal(str)


class _CompressTask(QtCore.QRunnable):
    def __init__(
        self,
        source_pdf: Path,
        fraction_rect: tuple[float, float, float, float],
        ratio: int,
        output_path: Path,
        *,
        compress_scale: float = 1.0,
        draw_badge: bool = True,
        badge_position: str = "top_left",
    ) -> None:
        super().__init__()
        self._source_pdf = source_pdf
        self._fraction_rect = fraction_rect
        self._ratio = max(1, ratio)
        self._output_path = output_path
        self._compress_scale = compress_scale
        self._draw_badge = draw_badge
        self._badge_position = (
            badge_position
            if badge_position in {"top_left", "top_right", "bottom_left", "bottom_right"}
            else "top_left"
        )
        self.signals = _CompressSignals()

    @staticmethod
    def _visual_clip_rect(page: fitz.Page, frac_rect: fitz.Rect) -> fitz.Rect:
        """Return a clip rect in the page's *visual* coordinates (i.e., page.rect space)."""
        page_rect = page.rect
        clip_rect = fitz.Rect(
            page_rect.x0 + frac_rect.x0 * page_rect.width,
            page_rect.y0 + frac_rect.y0 * page_rect.height,
            page_rect.x0 + frac_rect.x1 * page_rect.width,
            page_rect.y0 + frac_rect.y1 * page_rect.height,
        )
        clip_rect.normalize()
        return clip_rect

    @staticmethod
    def _clamp_rect(rect: fitz.Rect, bounds: fitz.Rect) -> fitz.Rect:
        clamped = fitz.Rect(
            max(bounds.x0, rect.x0),
            max(bounds.y0, rect.y0),
            min(bounds.x1, rect.x1),
            min(bounds.y1, rect.y1),
        )
        clamped.normalize()
        return clamped

    def _badge_rect(self, left: float, top: float, cell_width: float, cell_height: float) -> fitz.Rect:
        scale = max(0.1, self._compress_scale)
        margin = max(4.0, 6.0 * scale)
        size = max(24.0, 32.0 * scale)
        if cell_width < size + 2 * margin:
            margin = max(2.0, (cell_width - size) / 2)
        if cell_height < size + 2 * margin:
            margin = max(2.0, (cell_height - size) / 2)
        if self._badge_position in {"top_right", "bottom_right"}:
            x0 = left + cell_width - size - margin
        else:
            x0 = left + margin
        if self._badge_position in {"bottom_left", "bottom_right"}:
            y0 = top + cell_height - size - margin
        else:
            y0 = top + margin
        return fitz.Rect(x0, y0, x0 + size, y0 + size)

    def _compress(self) -> Path:
        if self._ratio <= 0:
            raise ValueError("compress ratio must be positive")
        if len(self._fraction_rect) != 4:
            raise ValueError("invalid clip rectangle")
        if self._compress_scale <= 0:
            raise ValueError("compress scale must be positive")
        base_frac = fitz.Rect(*self._fraction_rect)
        base_frac.normalize()
        if base_frac.width <= 0 or base_frac.height <= 0:
            raise ValueError("compress block is empty")
        side = int(math.isqrt(self._ratio))
        if side * side != self._ratio:
            raise ValueError("compress ratio must be a perfect square")

        source_doc = fitz.open(str(self._source_pdf))
        try:
            if source_doc.page_count == 0:
                raise ValueError("PDF has no pages")
            pages = list(range(source_doc.page_count))
            chunk_size = max(1, self._ratio)

            # GUI 选区使用的是 page.get_pixmap 的视觉坐标系（即 page.rect 空间）
            # 这里保持 frac_rect 为视觉比例矩形。
            frac_rect = base_frac

            out_doc = fitz.open()
            try:
                for start in range(0, len(pages), chunk_size):
                    chunk = pages[start : start + chunk_size]
                    if not chunk:
                        continue

                    # 1) 以该 chunk 的第一页确定拼图网格的单元尺寸（视觉裁剪框的宽高）。
                    first_page = source_doc.load_page(chunk[0])
                    clip_template = self._visual_clip_rect(first_page, frac_rect)

                    if clip_template.width <= 0 or clip_template.height <= 0:
                        raise ValueError("Computed clip is empty.")

                    # 2) 确定拼图后的单元格大小：直接使用视觉裁剪框的宽高。
                    cell_width = clip_template.width
                    cell_height = clip_template.height

                    # 3) 创建新页面
                    cols = side
                    rows = max(1, math.ceil(len(chunk) / cols))
                    page_width = cell_width * cols * self._compress_scale
                    page_height = cell_height * rows * self._compress_scale
                    dest_page = out_doc.new_page(width=page_width, height=page_height)

                    for idx, src_index in enumerate(chunk):
                        src_page = source_doc.load_page(src_index)

                        # 关键修复：PyMuPDF 的 show_pdf_page 对带有 /Rotate 的源页面支持不稳定，
                        # 且 clip 使用的是“未旋转”的页面坐标。为保证裁剪区域和方向都正确：
                        #   1) 先在“视觉坐标系”(page.rect) 计算 clip_visual（对应 GUI 看到的区域）
                        #   2) 使用 derotation_matrix 映射到未旋转坐标 clip_unrot
                        #   3) 将源页面 rotation 归零（仅内存中，不写回源文件）
                        #   4) 调用 show_pdf_page 时用 rotate=-orig_rotation 把视觉方向补回来
                        orig_rotation = int(src_page.rotation or 0) % 360
                        if orig_rotation not in (0, 90, 180, 270):
                            orig_rotation = 0

                        clip_visual = self._visual_clip_rect(src_page, frac_rect)
                        clip_unrot = clip_visual * src_page.derotation_matrix
                        clip_unrot.normalize()

                        # 归零 rotation 后，page.rect 变为未旋转坐标系；clip_unrot 应该落在其中
                        src_page.set_rotation(0)
                        clip_unrot = self._clamp_rect(clip_unrot, src_page.rect)
                        if clip_unrot.width <= 0 or clip_unrot.height <= 0:
                            raise ValueError("Computed clip is empty after derotation.")

                        rotate_apply = (-orig_rotation) % 360

                        col = idx % cols
                        row = idx // cols
                        left = cell_width * col
                        top = cell_height * row
                        left_scaled = left * self._compress_scale
                        top_scaled = top * self._compress_scale
                        cell_width_scaled = cell_width * self._compress_scale
                        cell_height_scaled = cell_height * self._compress_scale

                        target_rect = fitz.Rect(
                            left_scaled,
                            top_scaled,
                            left_scaled + cell_width_scaled,
                            top_scaled + cell_height_scaled,
                        )

                        # 4) 绘制页面：clip 使用未旋转坐标，rotate 用于恢复视觉方向
                        dest_page.show_pdf_page(
                            target_rect, source_doc, src_index, clip=clip_unrot, rotate=rotate_apply
                        )

                        if self._draw_badge:
                            badge_rect = self._badge_rect(
                                left_scaled, top_scaled, cell_width_scaled, cell_height_scaled
                            )
                            center = fitz.Point(
                                (badge_rect.x0 + badge_rect.x1) / 2,
                                (badge_rect.y0 + badge_rect.y1) / 2,
                            )
                            radius = badge_rect.width / 2
                            line_width = max(2.0, 3.0 * self._compress_scale)
                            dest_page.draw_circle(
                                center, radius, color=(1, 0, 0), fill=None, width=line_width
                            )
                            size_hint = min(badge_rect.width, badge_rect.height)
                            fontsize = max(12.0, min(size_hint * 0.7, 32.0 * self._compress_scale))
                            dest_page.insert_textbox(
                                badge_rect,
                                str(idx + 1),
                                fontsize=fontsize,
                                color=(1, 0, 0),
                                align=1,
                            )

                self._output_path.parent.mkdir(parents=True, exist_ok=True)
                self._output_path.unlink(missing_ok=True)
                out_doc.save(self._output_path)
            finally:
                out_doc.close()
            return self._output_path
        finally:
            source_doc.close()

    def run(self) -> None:
        try:
            output_path = self._compress()
        except Exception as exc:  # pragma: no cover - GUI runtime path
            self.signals.failed.emit(str(exc))
            return
        self.signals.finished.emit(str(output_path))


class _PreviewSignals(QtCore.QObject):
    finished = QtCore.Signal(str, int, int, int)
    failed = QtCore.Signal(str)


class _CompressPreviewTask(QtCore.QRunnable):
    def __init__(
        self,
        source_pdf: Path,
        fraction_rect: tuple[float, float, float, float],
        ratio: int,
        output_dir: Path,
        *,
        compress_scale: float,
        draw_badge: bool,
        badge_position: str,
    ) -> None:
        super().__init__()
        self._source_pdf = source_pdf
        self._fraction_rect = fraction_rect
        self._ratio = ratio
        self._output_dir = output_dir
        self._compress_scale = compress_scale
        self._draw_badge = draw_badge
        self._badge_position = badge_position
        self.signals = _PreviewSignals()

    def run(self) -> None:
        try:
            self._output_dir.mkdir(parents=True, exist_ok=True)
            preview_pdf = self._output_dir / "compressed_preview.pdf"
            compress_task = _CompressTask(
                self._source_pdf,
                self._fraction_rect,
                self._ratio,
                preview_pdf,
                compress_scale=self._compress_scale,
                draw_badge=self._draw_badge,
                badge_position=self._badge_position,
            )
            pdf_path = compress_task._compress()

            images_dir = self._output_dir / "images"
            images_dir.mkdir(parents=True, exist_ok=True)
            image_paths = convert_pdf_to_images(pdf_path, images_dir, dpi=300, prefix="preview")
            if not image_paths:
                raise RuntimeError("Preview conversion produced no images.")
            image_path = image_paths[0]
            qimage = QtGui.QImage(str(image_path))
            if qimage.isNull():
                raise RuntimeError("Failed to load preview image.")
            size_bytes = image_path.stat().st_size
            self.signals.finished.emit(str(image_path), qimage.width(), qimage.height(), size_bytes)
        except Exception as exc:  # pragma: no cover - GUI runtime path
            self.signals.failed.emit(str(exc))


class _GroupDiveSignals(QtCore.QObject):
    finished = QtCore.Signal(str)
    failed = QtCore.Signal(str)
    gemini_ready = QtCore.Signal(str, int)


class _GroupDiveTask(QtCore.QRunnable):
    def __init__(self, asset_name: str, group_idx: int) -> None:
        super().__init__()
        self._asset_name = asset_name
        self._group_idx = group_idx
        self.signals = _GroupDiveSignals()

    def run(self) -> None:
        try:
            output_path = group_dive_in(
                self._asset_name,
                self._group_idx,
                on_gemini_ready=lambda path: self.signals.gemini_ready.emit(
                    str(path), self._group_idx
                ),
            )
        except Exception as exc:  # pragma: no cover - GUI runtime path
            self.signals.failed.emit(str(exc))
            return
        try:
            output_path = Path(output_path)
            if not output_path.is_file():
                raise FileNotFoundError(f"Explainer output not found: {output_path}")
            if output_path.name != "enhanced.md":
                raise ValueError(f"Unexpected explainer output: {output_path.name}")
        except Exception as exc:  # pragma: no cover - GUI runtime path
            self.signals.failed.emit(str(exc))
            return
        self.signals.finished.emit(str(output_path))


class _AskTutorSignals(QtCore.QObject):
    finished = QtCore.Signal(str)
    failed = QtCore.Signal(str)


class _AskTutorTask(QtCore.QRunnable):
    def __init__(self, asset_name: str, group_idx: int, tutor_idx: int, question: str) -> None:
        super().__init__()
        self._asset_name = asset_name
        self._group_idx = group_idx
        self._tutor_idx = tutor_idx
        self._question = question
        self.signals = _AskTutorSignals()

    def run(self) -> None:
        try:
            output_path = ask_tutor(self._question, self._asset_name, self._group_idx, self._tutor_idx)
        except Exception as exc:  # pragma: no cover - GUI runtime path
            self.signals.failed.emit(str(exc))
            return
        self.signals.finished.emit(str(output_path))


class _IntegrateSignals(QtCore.QObject):
    finished = QtCore.Signal(str)
    failed = QtCore.Signal(str)


class _IntegrateTask(QtCore.QRunnable):
    def __init__(self, asset_name: str, group_idx: int, tutor_idx: int) -> None:
        super().__init__()
        self._asset_name = asset_name
        self._group_idx = group_idx
        self._tutor_idx = tutor_idx
        self.signals = _IntegrateSignals()

    def run(self) -> None:
        try:
            output_path = integrate(self._asset_name, self._group_idx, self._tutor_idx)
        except Exception as exc:  # pragma: no cover - GUI runtime path
            self.signals.failed.emit(str(exc))
            return
        self.signals.finished.emit(str(output_path))


__all__ = [
    "_AskTutorTask",
    "_AssetInitTask",
    "_CompressPreviewTask",
    "_CompressTask",
    "_GroupDiveTask",
    "_IntegrateTask",
    "_RenderTask",
]
