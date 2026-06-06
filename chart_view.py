"""
pyqtgraph 기반 일봉 캔들 차트 위젯.
- 캔들(상승 빨강 / 하락 파랑) + 이동평균선(MA5, MA20) + 거래량
"""
import numpy as np
import pyqtgraph as pg
from PyQt5.QtCore import QPointF, QRectF
from PyQt5.QtGui import QPicture, QPainter, QPen, QColor
from PyQt5.QtWidgets import QWidget, QVBoxLayout

pg.setConfigOption("background", "w")
pg.setConfigOption("foreground", "k")
pg.setConfigOptions(antialias=True)

UP = QColor("#d32f2f")     # 상승 빨강
DOWN = QColor("#1565c0")   # 하락 파랑


class CandlestickItem(pg.GraphicsObject):
    def __init__(self, data):
        super().__init__()
        self.data = data   # [(x, open, high, low, close), ...]
        self.picture = QPicture()
        self._draw()

    def _draw(self):
        p = QPainter(self.picture)
        w = 0.3
        for (t, o, h, l, c) in self.data:
            color = UP if c >= o else DOWN
            p.setPen(QPen(color))
            p.drawLine(QPointF(t, l), QPointF(t, h))
            p.setBrush(color)
            p.drawRect(QRectF(t - w, o, w * 2, c - o).normalized())
        p.end()

    def paint(self, p, *args):
        p.drawPicture(0, 0, self.picture)

    def boundingRect(self):
        return QRectF(self.picture.boundingRect())


class CandleChart(QWidget):
    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.glw = pg.GraphicsLayoutWidget()
        lay.addWidget(self.glw)

        self.price = self.glw.addPlot(row=0, col=0)
        self.price.showGrid(x=True, y=True, alpha=0.2)
        self.price.addLegend(offset=(10, 10))

        self.vol = self.glw.addPlot(row=1, col=0)
        self.vol.showGrid(x=True, y=True, alpha=0.2)
        self.vol.setXLink(self.price)

        self.glw.ci.layout.setRowStretchFactor(0, 4)
        self.glw.ci.layout.setRowStretchFactor(1, 1)

    def set_data(self, df):
        self.price.clear()
        self.vol.clear()
        if df is None or len(df) == 0:
            return
        n = len(df)
        x = np.arange(n)
        o = df["open"].values
        h = df["high"].values
        l = df["low"].values
        c = df["close"].values

        self.price.addItem(CandlestickItem(list(zip(x, o, h, l, c))))
        ma5 = df["close"].rolling(5).mean().values
        ma20 = df["close"].rolling(20).mean().values
        self.price.plot(x, ma5, pen=pg.mkPen("#ff9800", width=1.3), name="MA5")
        self.price.plot(x, ma20, pen=pg.mkPen("#7b1fa2", width=1.3), name="MA20")

        self.vol.addItem(pg.BarGraphItem(x=x, height=df["volume"].values, width=0.6, brush="#9e9e9e"))

        step = max(1, n // 8)
        ticks = [(int(i), df["date"].iloc[int(i)].strftime("%y/%m/%d")) for i in range(0, n, step)]
        self.price.getAxis("bottom").setTicks([ticks])
        self.vol.getAxis("bottom").setTicks([ticks])
        self.price.enableAutoRange()
        self.vol.enableAutoRange()
