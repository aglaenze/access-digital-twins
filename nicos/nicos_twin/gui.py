"""ESS NICOS GUI ("flowui"): main window, Experiment and detector-image panels, with small adaptations for the twins.

1. Workaround for a NICOS bug at the tested commit (44bec9c): the generic main window
   (nicos/clients/gui/mainwindow.py) uses an action `actionInstrumentWebsite` that the flowui window
   (nicos/clients/flowui/mainwindow.py, used by all ESS instruments) does not define, so the GUI crashes when it starts.
   The missing action is added. To be removed once fixed upstream.
2. Small screens: the ESS layout needs about 1170 pixels of height (the instrument computers at ESS have large
   screens); on a laptop the bottom of the window (Apply button of the Experiment tab, device list) was out of the
   screen. The content is put in a scroll area and the window is kept within the screen.
3. Experiment panel: the Apply button right under the form (ExpPanel below), not at the bottom of the window.
4. Detector image (ODIN): color levels recomputed for every new image (LiveDataPanel below).
5. Instrument interaction tab, as at ESS: command line and output / detector image on the left, device list on the
   right (hsplit of the ESS guiconfig). NICOS restores the splitters as last saved, orientation included: a layout
   saved by an older version of the twin (device list below) came back at each start. The orientation of each
   splitter is set again from the configuration. The device list gets a third of the width at start. Only the tab
   shown sets the height of the left part (a QTabWidget is otherwise as tall as its tallest tab, the detector image,
   ~810 pixels): the Output tab fits in the window with its own scroll bar only; on a small screen the window
   scrolls (2.) for the detector image alone.
6. Test mode (GitHub Actions, container/desktop_test.sh): NICOS_TWIN_SHOW_TAB="Instrument interaction,Detector Image"
   opens these tabs once connected (for the screenshot of the detector image).
"""
import os

from nicos.clients.flowui.mainwindow import MainWindow as FlowuiMainWindow
from nicos.clients.gui.panels.splitter import HorizontalSplitter, VerticalSplitter
from nicos.guisupport.qt import QAction, QApplication, QFrame, QScrollArea, QSizePolicy, QSplitter, QTabWidget, \
    QTimer, Qt
from nicos_ess.gui.panels.exp_panel import ExpPanel as EssExpPanel
from nicos_ess.odin.gui.panels.live import MultiLiveDataPanel as OdinMultiLiveDataPanel


class LiveDataPanel(OdinMultiLiveDataPanel):
    """The ODIN detector-image panel of ESS, with automatic color levels for every new image.

    The ESS image widget sets its color levels once, from the first image it receives (5 %-95 % of the pixel values),
    then keeps them: at ESS the image is refreshed continuously during a count. The twin sends one image per count,
    and successive counts differ a lot (dark: almost nothing; open beam: ~330 counts per pixel; sample: ~200), so
    fixed levels gave an all-yellow or all-dark image. Here the levels are recomputed for each new image (the
    Autoscale button and the level fields still work in between)."""

    def on_client_livedata(self, params, blobs):
        widgets = [getattr(self, "plotwidget", None)]
        widgets += [getattr(p, "widget", None) for p in getattr(self, "_previews", {}).values()]
        for w in widgets:
            if w is not None and hasattr(w, "autolevel_complete"):
                w.autolevel_complete = False
        OdinMultiLiveDataPanel.on_client_livedata(self, params, blobs)


class ExpPanel(EssExpPanel):
    """The ESS Experiment panel, with its Apply button (and the "not applied" warning) right under the form instead
    of at the very bottom of the window (the ESS layout puts the free space between the form and the button)."""

    def __init__(self, *args, **kwargs):
        EssExpPanel.__init__(self, *args, **kwargs)
        form = self.dataBox.layout()
        for i in reversed(range(form.count())):        # the stretchable space under the form
            if form.itemAt(i).spacerItem() is not None:
                form.takeAt(i)
        outer = self.layout()
        for w in (self.applyWarningLabel, self.buttonBox):
            outer.removeWidget(w)
            form.addWidget(w)
        form.addStretch(1)                             # free space now below the button


def _height_of_current_tab_only(tw):
    """Only the tab shown counts for the height of a QTabWidget: the other tabs ignore their size."""
    def update(current):
        for i in range(tw.count()):
            page = tw.widget(i)
            policy = QSizePolicy.Preferred if i == current else QSizePolicy.Ignored
            page.setSizePolicy(policy, policy)
            page.updateGeometry()
        tw.updateGeometry()

    tw.currentChanged.connect(update)
    update(tw.currentIndex())


class MainWindow(FlowuiMainWindow):
    DEVICES_SHARE = 1 / 3               # width of the device list at start (fraction of the Instrument interaction tab)

    def __init__(self, *args, **kwargs):
        FlowuiMainWindow.__init__(self, *args, **kwargs)
        for sp in self.findChildren(QSplitter):        # the orientation of the configuration, not of a saved layout
            if isinstance(sp, HorizontalSplitter):
                sp.setOrientation(Qt.Orientation.Horizontal)
            elif isinstance(sp, VerticalSplitter):
                sp.setOrientation(Qt.Orientation.Vertical)
        for tw in self.findChildren(QTabWidget):
            if any(tw.tabText(i).strip() == "Output" for i in range(tw.count())):
                _height_of_current_tab_only(tw)
        content = self.takeCentralWidget()
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(content)
        self.setCentralWidget(scroll)
        self._fitted = False
        self._device_splitters = [sp for sp in self.findChildren(QSplitter) if sp.count() >= 2 and any(
            "DevicesPanel" in type(sp.widget(i)).__name__ for i in range(sp.count()))]

    def showEvent(self, event):
        FlowuiMainWindow.showEvent(self, event)
        if not self._fitted:            # once: never larger than the free part of the screen
            self._fitted = True
            screen = self.screen() if hasattr(self, "screen") else QApplication.primaryScreen()
            avail = screen.availableGeometry()
            frame = self.frameGeometry().height() - self.geometry().height()
            w, h = min(self.width(), avail.width()), min(self.height(), avail.height() - frame)
            if (w, h) != (self.width(), self.height()):
                self.resize(w, h)
                self.move(avail.x() + (avail.width() - w) // 2, avail.y())
            QTimer.singleShot(500, self._size_device_list)     # after NICOS has laid out the window

    def _size_device_list(self):
        for sp in self._device_splitters:
            total = sum(sp.sizes())
            if total <= 0:
                continue
            dev = [i for i in range(sp.count()) if "DevicesPanel" in type(sp.widget(i)).__name__][0]
            sizes = [0] * sp.count()
            sizes[dev] = int(total * self.DEVICES_SHARE)
            others = [i for i in range(sp.count()) if i != dev]
            for i in others:
                sizes[i] = (total - sizes[dev]) // len(others)
            sp.setSizes(sizes)

    def _ensure_website_action(self):
        if not hasattr(self, "actionInstrumentWebsite"):
            self.actionInstrumentWebsite = QAction("Instrument &home page", self)
            self.actionInstrumentWebsite.setVisible(False)

    def on_client_connected(self):
        self._ensure_website_action()
        FlowuiMainWindow.on_client_connected(self)
        if os.environ.get("NICOS_TWIN_SHOW_TAB"):
            QTimer.singleShot(3000, self._show_tabs)

    def _show_tabs(self):
        wanted = [t.strip() for t in os.environ["NICOS_TWIN_SHOW_TAB"].split(",") if t.strip()]
        for name in wanted:                  # outer tabs first (the order given)
            for tw in self.findChildren(QTabWidget):
                for i in range(tw.count()):
                    if tw.tabText(i).strip() == name:
                        tw.setCurrentIndex(i)

    def on_client_disconnected(self):
        self._ensure_website_action()
        FlowuiMainWindow.on_client_disconnected(self)
