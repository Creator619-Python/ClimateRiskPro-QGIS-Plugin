"""
ClimateRisk Pro - Dock Widget
PyQt5 panel that hosts the plugin UI.
"""

from qgis.PyQt.QtWidgets import (
    QDockWidget,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QDoubleSpinBox,
    QComboBox,
    QCheckBox,
    QPushButton,
    QTextEdit,
    QSizePolicy,
    QSpacerItem,
    QFrame,
)
from qgis.PyQt.QtCore import Qt


_QSS = """
/* Dock panel background */
QWidget#crp_root {
    background-color: #f5f7fa;
}

/* Section labels */
QLabel#crp_section {
    font-weight: bold;
    font-size: 11px;
    color: #34495e;
    margin-top: 6px;
}

/* Input fields */
QLineEdit, QDoubleSpinBox, QComboBox {
    background: #ffffff;
    border: 1px solid #ccd1d9;
    border-radius: 4px;
    padding: 4px 6px;
    font-size: 12px;
    color: #2c3e50;
}
QLineEdit:focus, QDoubleSpinBox:focus, QComboBox:focus {
    border-color: #3498db;
}

/* Primary run button */
QPushButton#crp_run {
    background-color: #2980b9;
    color: white;
    font-weight: bold;
    font-size: 13px;
    border: none;
    border-radius: 5px;
    padding: 8px 0px;
}
QPushButton#crp_run:hover  { background-color: #3498db; }
QPushButton#crp_run:pressed{ background-color: #1a6091; }
QPushButton#crp_run:disabled{ background-color: #aab7c4; }

/* Export button */
QPushButton#crp_export {
    background-color: #27ae60;
    color: white;
    font-weight: bold;
    font-size: 12px;
    border: none;
    border-radius: 5px;
    padding: 6px 0px;
}
QPushButton#crp_export:hover   { background-color: #2ecc71; }
QPushButton#crp_export:pressed { background-color: #1e8449; }
QPushButton#crp_export:disabled{ background-color: #aab7c4; }

/* Results area */
QTextEdit#crp_results {
    background: #ffffff;
    border: 1px solid #ccd1d9;
    border-radius: 4px;
    font-family: "Courier New", monospace;
    font-size: 11px;
    color: #2c3e50;
}

/* Horizontal rule */
QFrame#crp_line {
    color: #dce1e7;
}

/* Status label */
QLabel#crp_status {
    font-size: 10px;
    color: #7f8c8d;
    font-style: italic;
}

/* Title bar label inside dock */
QLabel#crp_title {
    font-size: 14px;
    font-weight: bold;
    color: #2c3e50;
    padding: 4px 0px;
}
"""


def _hr():
    """Thin horizontal separator line."""
    line = QFrame()
    line.setObjectName("crp_line")
    line.setFrameShape(QFrame.HLine)
    line.setFrameShadow(QFrame.Sunken)
    return line


def _section_label(text):
    lbl = QLabel(text)
    lbl.setObjectName("crp_section")
    return lbl


class ClimateRiskDockWidget(QDockWidget):
    """Right-side dock panel for ClimateRisk Pro."""

    def __init__(self, parent=None):
        super().__init__("ClimateRisk Pro", parent)
        self.setObjectName("ClimateRiskProDock")
        self.setAllowedAreas(Qt.RightDockWidgetArea | Qt.LeftDockWidgetArea)
        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        root = QWidget()
        root.setObjectName("crp_root")
        root.setStyleSheet(_QSS)

        layout = QVBoxLayout(root)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        # Title
        title_lbl = QLabel("🌍 ClimateRisk Pro")
        title_lbl.setObjectName("crp_title")
        layout.addWidget(title_lbl)
        layout.addWidget(_hr())

        # --- Location ---
        layout.addWidget(_section_label("Location Name"))
        self.location_edit = QLineEdit()
        self.location_edit.setPlaceholderText("e.g. Banjara Hills, Hyderabad")
        layout.addWidget(self.location_edit)

        # Lat / Lon row
        coord_row = QHBoxLayout()
        lat_col = QVBoxLayout()
        lat_col.addWidget(_section_label("Latitude"))
        self.lat_spin = QDoubleSpinBox()
        self.lat_spin.setRange(-90.0, 90.0)
        self.lat_spin.setDecimals(6)
        self.lat_spin.setSingleStep(0.01)
        lat_col.addWidget(self.lat_spin)
        coord_row.addLayout(lat_col)

        lon_col = QVBoxLayout()
        lon_col.addWidget(_section_label("Longitude"))
        self.lon_spin = QDoubleSpinBox()
        self.lon_spin.setRange(-180.0, 180.0)
        self.lon_spin.setDecimals(6)
        self.lon_spin.setSingleStep(0.01)
        lon_col.addWidget(self.lon_spin)
        coord_row.addLayout(lon_col)

        layout.addLayout(coord_row)
        layout.addWidget(_hr())

        # --- Framework ---
        layout.addWidget(_section_label("Reporting Framework"))
        self.framework_combo = QComboBox()
        self.framework_combo.addItems(["TCFD", "ISSB S2", "BRSR", "CSRD"])
        layout.addWidget(self.framework_combo)

        # --- Batch Mode ---
        self.batch_checkbox = QCheckBox("Batch Mode (assess all features in active layer)")
        layout.addWidget(self.batch_checkbox)
        layout.addWidget(_hr())

        # --- Run button ---
        self.run_button = QPushButton("▶  Run Assessment")
        self.run_button.setObjectName("crp_run")
        self.run_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout.addWidget(self.run_button)

        # --- Results ---
        layout.addWidget(_section_label("Assessment Results"))
        self.results_text = QTextEdit()
        self.results_text.setObjectName("crp_results")
        self.results_text.setReadOnly(True)
        self.results_text.setPlaceholderText(
            "Run an assessment to see results here…"
        )
        self.results_text.setMinimumHeight(180)
        layout.addWidget(self.results_text)

        # --- Export ---
        self.export_button = QPushButton("📄  Export Report")
        self.export_button.setObjectName("crp_export")
        self.export_button.setEnabled(False)
        self.export_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout.addWidget(self.export_button)

        layout.addWidget(_hr())

        # --- Status ---
        self.status_label = QLabel("Ready.")
        self.status_label.setObjectName("crp_status")
        self.status_label.setAlignment(Qt.AlignLeft)
        layout.addWidget(self.status_label)

        layout.addSpacerItem(QSpacerItem(0, 0, QSizePolicy.Minimum, QSizePolicy.Expanding))

        self.setWidget(root)

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def set_status(self, message: str):
        self.status_label.setText(message)
