from __future__ import annotations

from typing import Callable

from PySide6 import QtCore, QtWidgets


class _BlockGraphicsItem(QtWidgets.QGraphicsRectItem):
    def __init__(
        self,
        rect: QtCore.QRectF,
        block_id: int,
        on_hover: Callable[[int], None],
        on_leave: Callable[[int], None],
    ) -> None:
        super().__init__(rect)
        self._block_id = block_id
        self._on_hover = on_hover
        self._on_leave = on_leave
        self.setAcceptHoverEvents(True)

    def hoverEnterEvent(self, event: QtWidgets.QGraphicsSceneHoverEvent) -> None:
        if self._on_hover:
            self._on_hover(self._block_id)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event: QtWidgets.QGraphicsSceneHoverEvent) -> None:
        if self._on_leave:
            self._on_leave(self._block_id)
        super().hoverLeaveEvent(event)


__all__ = [
    "_BlockGraphicsItem",
]

