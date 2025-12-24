from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets


DELETE_DRAG_TOLERANCE = 6
RUBBER_PEN_COLOR = QtGui.QColor(255, 0, 0)
RUBBER_PEN_WIDTH = 1
RUBBER_PEN_STYLE = QtCore.Qt.DashLine
RUBBER_BRUSH_COLOR = QtGui.QColor(255, 0, 0, 40)


class PdfPageView(QtWidgets.QGraphicsView):
    selection_finished = QtCore.Signal(QtCore.QRectF)
    block_clicked = QtCore.Signal(int)
    block_right_clicked = QtCore.Signal(int)
    drag_started = QtCore.Signal()
    drag_finished = QtCore.Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setMouseTracking(True)
        self.setDragMode(QtWidgets.QGraphicsView.NoDrag)
        self.setRenderHint(QtGui.QPainter.SmoothPixmapTransform)
        self._dragging = False
        self._origin = QtCore.QPointF()
        self._hand_dragging = False
        self._rubber_started = False
        self._rubber_item: QtWidgets.QGraphicsRectItem | None = None
        self._press_center: QtCore.QPointF | None = None
        self._right_dragging = False
        self._right_press_pos: QtCore.QPointF | None = None
        self._right_press_item_id: int | None = None
        self._last_pan_pos: QtCore.QPointF | None = None

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        if event.button() == QtCore.Qt.MiddleButton:
            self._hand_dragging = True
            self.setDragMode(QtWidgets.QGraphicsView.ScrollHandDrag)
            super().mousePressEvent(event)
            return
        if event.button() == QtCore.Qt.LeftButton:
            hit_item = self.itemAt(event.position().toPoint())
            if isinstance(hit_item, QtWidgets.QGraphicsProxyWidget):
                super().mousePressEvent(event)
                return
            if hit_item is not None:
                data = hit_item.data(0)
                if isinstance(data, int):
                    self.block_clicked.emit(data)
                    event.accept()
                    return
            self._dragging = True
            self._rubber_started = False
            self._origin = self.mapToScene(event.position().toPoint())
            self._press_center = self.mapToScene(
                QtCore.QPoint(self.viewport().width() // 2, self.viewport().height() // 2)
            )
            self.drag_started.emit()
            event.accept()
            return
        if event.button() == QtCore.Qt.RightButton:
            self._right_dragging = True
            self._right_press_pos = event.position()
            self._last_pan_pos = event.position()
            hit_item = self.itemAt(event.position().toPoint())
            data = hit_item.data(0) if hit_item is not None else None
            self._right_press_item_id = data if isinstance(data, int) else None
            self.setCursor(QtCore.Qt.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:
        if self._right_dragging:
            if self._last_pan_pos is not None:
                delta = event.position() - self._last_pan_pos
                hbar = self.horizontalScrollBar()
                vbar = self.verticalScrollBar()
                hbar.setValue(hbar.value() - int(delta.x()))
                vbar.setValue(vbar.value() - int(delta.y()))
            self._last_pan_pos = event.position()
            event.accept()
            return
        if self._dragging:
            current = self.mapToScene(event.position().toPoint())
            if not self._rubber_started:
                delta = current - self._origin
                if abs(delta.x()) >= 4 or abs(delta.y()) >= 4:
                    self._start_rubber(self._origin)
                    self._rubber_started = True
            if self._rubber_item:
                rect = QtCore.QRectF(self._origin, current).normalized()
                self._rubber_item.setRect(rect)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:
        if self._dragging and event.button() == QtCore.Qt.LeftButton:
            self._dragging = False
            if self._rubber_item and self._rubber_started:
                rect = QtCore.QRectF(
                    self._origin, self.mapToScene(event.position().toPoint())
                ).normalized()
                scene = self.scene()
                if scene:
                    scene.removeItem(self._rubber_item)
                self._rubber_item = None
                if rect.width() >= 4 and rect.height() >= 4:
                    self.selection_finished.emit(rect)
            else:
                self._rubber_item = None
            if self._press_center is not None:
                self.centerOn(self._press_center)
                self._press_center = None
            self.drag_finished.emit()
            event.accept()
            return
        if event.button() == QtCore.Qt.RightButton and self._right_dragging:
            release_pos = event.position()
            delete_candidate: int | None = None
            if self._right_press_pos is not None:
                delta = release_pos - self._right_press_pos
                within_tolerance = (
                    abs(delta.x()) <= DELETE_DRAG_TOLERANCE
                    and abs(delta.y()) <= DELETE_DRAG_TOLERANCE
                )
                if within_tolerance and self._right_press_item_id is not None:
                    hit_item = self.itemAt(release_pos.toPoint())
                    data = hit_item.data(0) if hit_item is not None else None
                    if isinstance(data, int) and data == self._right_press_item_id:
                        delete_candidate = data
            self._right_dragging = False
            self._right_press_pos = None
            self._right_press_item_id = None
            self._last_pan_pos = None
            self.setCursor(QtCore.Qt.ArrowCursor)
            if delete_candidate is not None:
                self.block_right_clicked.emit(delete_candidate)
            event.accept()
            return
        if event.button() == QtCore.Qt.MiddleButton and self._hand_dragging:
            super().mouseReleaseEvent(event)
            self.setDragMode(QtWidgets.QGraphicsView.NoDrag)
            self._hand_dragging = False
            return
        super().mouseReleaseEvent(event)

    def _start_rubber(self, origin: QtCore.QPointF) -> None:
        scene = self.scene()
        if not scene:
            return
        pen = QtGui.QPen(RUBBER_PEN_COLOR)
        pen.setStyle(RUBBER_PEN_STYLE)
        pen.setWidth(RUBBER_PEN_WIDTH)
        brush = QtGui.QBrush(RUBBER_BRUSH_COLOR)
        self._rubber_item = scene.addRect(QtCore.QRectF(origin, origin), pen, brush)
        self._rubber_item.setZValue(10)
