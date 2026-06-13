"""
ClimateRisk Pro - Main Plugin Class
QGIS Plugin for TCFD/ISSB S2/BRSR/CSRD aligned climate risk assessment.
"""

import os
from qgis.PyQt.QtWidgets import QAction, QToolBar
from qgis.PyQt.QtGui import QIcon, QColor
from qgis.PyQt.QtCore import Qt
from qgis.core import (
    QgsProject,
    QgsVectorLayer,
    QgsFeature,
    QgsGraduatedSymbolRenderer,
    QgsRendererRange,
    QgsSymbol,
    QgsClassificationEqualInterval,
    QgsStyle,
    QgsWkbTypes,
    QgsMapLayerType,
    edit,
)
from qgis.gui import QgsMapCanvas

from .dock_widget import ClimateRiskDockWidget
from .assessment import run_assessment, format_results_text
from .report_exporter import export_report


class ClimateRiskPro:
    """Main plugin class registered with QGIS."""

    def __init__(self, iface):
        self.iface = iface
        self.canvas = iface.mapCanvas()
        self.dock_widget = None
        self.action = None
        self._last_result = None

    # ------------------------------------------------------------------
    # Plugin lifecycle
    # ------------------------------------------------------------------

    def initGui(self):
        """Create UI elements and connect signals."""
        icon_path = os.path.join(os.path.dirname(__file__), "icon.png")
        self.action = QAction(
            QIcon(icon_path),
            "ClimateRisk Pro Assessment",
            self.iface.mainWindow(),
        )
        self.action.setToolTip("ClimateRisk Pro Assessment")
        self.action.setCheckable(True)
        self.action.triggered.connect(self._toggle_dock)

        self.iface.addToolBarIcon(self.action)
        self.iface.addPluginToMenu("&ClimateRisk Pro", self.action)

        # Build dock widget
        self.dock_widget = ClimateRiskDockWidget(self.iface.mainWindow())
        self.iface.addDockWidget(Qt.RightDockWidgetArea, self.dock_widget)
        self.dock_widget.hide()

        # Wire up buttons
        self.dock_widget.run_button.clicked.connect(self._on_run_assessment)
        self.dock_widget.export_button.clicked.connect(self._on_export_report)

        # React to canvas selection changes
        self.canvas.selectionChanged.connect(self._on_selection_changed)

    def unload(self):
        """Remove UI elements when plugin is unloaded."""
        if self.dock_widget:
            self.iface.removeDockWidget(self.dock_widget)
            self.dock_widget.deleteLater()
            self.dock_widget = None

        self.iface.removeToolBarIcon(self.action)
        self.iface.removePluginMenu("&ClimateRisk Pro", self.action)

        if self.action:
            self.action.deleteLater()
            self.action = None

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _toggle_dock(self, checked):
        if self.dock_widget:
            if checked:
                self.dock_widget.show()
            else:
                self.dock_widget.hide()

    def _on_selection_changed(self):
        """When user selects a single feature on canvas, populate lat/lon."""
        layer = self.iface.activeLayer()
        if not layer or not isinstance(layer, QgsVectorLayer):
            return
        selected = layer.selectedFeatures()
        if len(selected) != 1:
            return
        feature = selected[0]
        geom = feature.geometry()
        if geom.isEmpty():
            return
        centroid = geom.centroid().asPoint()
        # Reproject to EPSG:4326 if needed
        crs = layer.crs()
        if not crs.isGeographic():
            from qgis.core import QgsCoordinateReferenceSystem, QgsCoordinateTransform
            wgs84 = QgsCoordinateReferenceSystem("EPSG:4326")
            xform = QgsCoordinateTransform(crs, wgs84, QgsProject.instance())
            centroid = xform.transform(centroid)
        if self.dock_widget:
            self.dock_widget.lat_spin.setValue(centroid.y())
            self.dock_widget.lon_spin.setValue(centroid.x())
            self.dock_widget.set_status("Location populated from selected feature.")

    def _on_run_assessment(self):
        """Run assessment — single or batch based on checkbox."""
        if not self.dock_widget:
            return

        batch = self.dock_widget.batch_checkbox.isChecked()
        framework = self.dock_widget.framework_combo.currentText()

        if batch:
            self._run_batch(framework)
        else:
            self._run_single(framework)

    def _run_single(self, framework):
        """Run assessment for the coordinates in the dock widget."""
        dw = self.dock_widget
        lat = dw.lat_spin.value()
        lon = dw.lon_spin.value()
        location_name = dw.location_edit.text().strip() or f"{lat:.4f}, {lon:.4f}"

        dw.set_status("Running assessment…")
        dw.run_button.setEnabled(False)
        dw.results_text.clear()

        try:
            result = run_assessment(lat, lon, location_name, framework)
            self._last_result = result
            display = format_results_text(result, framework)
            dw.results_text.setPlainText(display)
            dw.export_button.setEnabled(True)
            dw.set_status("Assessment complete.")
        except Exception as exc:
            dw.results_text.setPlainText(f"Error during assessment:\n{exc}")
            dw.set_status("Assessment failed.")
        finally:
            dw.run_button.setEnabled(True)

    def _run_batch(self, framework):
        """Run assessment on every feature in the active layer."""
        dw = self.dock_widget
        layer = self.iface.activeLayer()

        if not layer or not isinstance(layer, QgsVectorLayer):
            dw.set_status("No active vector layer for batch mode.")
            return

        fields_to_add = [
            ("crp_hazard_score", "real"),
            ("crp_water_risk", "real"),
            ("crp_heat_risk", "real"),
            ("crp_flood_risk", "real"),
            ("crp_overall_risk", "real"),
        ]

        # Add missing fields
        from qgis.core import QgsField
        from qgis.PyQt.QtCore import QVariant

        existing_names = [f.name() for f in layer.fields()]
        with edit(layer):
            for fname, ftype in fields_to_add:
                if fname not in existing_names:
                    layer.addAttribute(QgsField(fname, QVariant.Double))

        layer.updateFields()

        field_indices = {
            fname: layer.fields().indexOf(fname) for fname, _ in fields_to_add
        }

        features = list(layer.getFeatures())
        total = len(features)
        dw.set_status(f"Batch: assessing {total} features…")
        dw.run_button.setEnabled(False)
        dw.results_text.clear()
        errors = []

        crs = layer.crs()
        wgs84 = None
        xform = None
        if not crs.isGeographic():
            from qgis.core import QgsCoordinateReferenceSystem, QgsCoordinateTransform
            wgs84 = QgsCoordinateReferenceSystem("EPSG:4326")
            xform = QgsCoordinateTransform(crs, wgs84, QgsProject.instance())

        with edit(layer):
            for i, feat in enumerate(features):
                geom = feat.geometry()
                if geom.isEmpty():
                    continue
                centroid = geom.centroid().asPoint()
                if xform:
                    centroid = xform.transform(centroid)
                lat, lon = centroid.y(), centroid.x()
                try:
                    result = run_assessment(lat, lon, f"Feature {feat.id()}", framework)
                    layer.changeAttributeValue(
                        feat.id(), field_indices["crp_hazard_score"],
                        result.get("hazard_score", 0)
                    )
                    layer.changeAttributeValue(
                        feat.id(), field_indices["crp_water_risk"],
                        result.get("water_risk_score", 0)
                    )
                    layer.changeAttributeValue(
                        feat.id(), field_indices["crp_heat_risk"],
                        result.get("heat_risk_score", 0)
                    )
                    layer.changeAttributeValue(
                        feat.id(), field_indices["crp_flood_risk"],
                        result.get("flood_risk_score", 0)
                    )
                    layer.changeAttributeValue(
                        feat.id(), field_indices["crp_overall_risk"],
                        result.get("overall_risk_score", 0)
                    )
                except Exception as exc:
                    errors.append(f"Feature {feat.id()}: {exc}")

                dw.set_status(f"Batch: {i+1}/{total} done…")

        summary_lines = [f"Batch complete: {total} features processed."]
        if errors:
            summary_lines.append(f"{len(errors)} errors:")
            summary_lines.extend(errors[:10])
        dw.results_text.setPlainText("\n".join(summary_lines))
        dw.run_button.setEnabled(True)
        dw.set_status("Batch assessment complete. Applying style…")

        self._apply_graduated_renderer(layer, "crp_overall_risk")
        dw.set_status("Batch complete. Graduated renderer applied.")

    def _apply_graduated_renderer(self, layer, field_name):
        """Apply green→yellow→red graduated renderer on the given field."""
        ranges = [
            QgsRendererRange(
                0, 33,
                QgsSymbol.defaultSymbol(layer.geometryType()),
                "Low (0–33)"
            ),
            QgsRendererRange(
                33, 66,
                QgsSymbol.defaultSymbol(layer.geometryType()),
                "Medium (33–66)"
            ),
            QgsRendererRange(
                66, 100,
                QgsSymbol.defaultSymbol(layer.geometryType()),
                "High (66–100)"
            ),
        ]

        colors = [
            QColor("#2ecc71"),   # green
            QColor("#f1c40f"),   # yellow
            QColor("#e74c3c"),   # red
        ]

        for rng, color in zip(ranges, colors):
            sym = rng.symbol().clone()
            sym.setColor(color)
            rng.setSymbol(sym)

        renderer = QgsGraduatedSymbolRenderer(field_name, ranges)
        layer.setRenderer(renderer)
        layer.triggerRepaint()

    def _on_export_report(self):
        """Export the last assessment result as a text report."""
        if not self._last_result:
            return
        framework = self.dock_widget.framework_combo.currentText()
        export_report(self._last_result, framework, parent=self.dock_widget)
