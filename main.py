import sys
import os
import pandas as pd
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QGroupBox, QLabel, QLineEdit, QComboBox, QCheckBox, 
                             QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, 
                             QSpinBox, QDoubleSpinBox, QTabWidget, QSplitter, QTextEdit, QMessageBox, QDialog, QSizePolicy, QPushButton, QFileDialog)
from PyQt5.QtCore import Qt

from main_controller import AdvancedController
from parameters_micro1 import LENS_PRESETS, LensGenerator
from lens_editor import TFEditorDialog, LensDetailDialog
from computations import LENS_RESULT_FIELDS
from column_settings import ColumnSettingsDialog
from source_editor import SourceEditorDialog

# --- Универсальный класс трансфокатора ---
class Transfocator:
    def __init__(self, name, tf_type="Air (Array)", preset="R50", total_lenses=100, active_ranges=None, measure_to_center=True):
        self.name = name
        self.tf_type = tf_type
        self.preset = preset
        self.total_lenses = total_lenses
        self.active_ranges = active_ranges or [(0, 8)]
        self.measure_to_center = measure_to_center
        
        # Конфигурация
        self.lenses = self._build_air_lenses() if tf_type == "Air (Array)" else []
        # Теперь groups — это список словарей с N, preset, active
        self.groups = [{"N": 1, "preset": preset, "active": True}, {"N": 2, "preset": preset, "active": True}, {"N": 1, "preset": preset, "active": True}] if tf_type == "Vacuum (Groups)" else []

        # UI виджеты (инициализируются при создании UI)
        self.ui_widgets = {}

    def _build_air_lenses(self):
        active_set = set()
        for start, end in self.active_ranges:
            active_set.update(range(start, end + 1))
        return [
            {"preset": self.preset, "active": (i in active_set)}
            for i in range(self.total_lenses)
        ]

    def update_active_ranges(self, ranges):
        self.active_ranges = ranges
        self.lenses = self._build_air_lenses()

    def update_preset(self, preset):
        self.preset = preset
        if self.tf_type == "Air (Array)":
            for lens in self.lenses:
                lens["preset"] = preset
        else:
            for group in self.groups:
                group["preset"] = preset

    def get_config(self):
        if self.tf_type == "Air (Array)":
            return {"type": "air", "lenses": self.lenses}
        else:
            return {"type": "vacuum", "groups": self.groups}


# --- Менеджер трансфокаторов ---
class TransfocatorManager:
    def __init__(self):
        self.tfs = []

    def add_tf(self, name, tf_type="Air (Array)", preset="R50", total_lenses=100, active_ranges=None):
        tf = Transfocator(name, tf_type, preset, total_lenses, active_ranges)
        self.tfs.append(tf)
        return tf

    def remove_tf(self, name):
        self.tfs = [tf for tf in self.tfs if tf.name != name]

    def get_tf_by_name(self, name):
        for tf in self.tfs:
            if tf.name == name:
                return tf
        return None

    def get_all_configs(self):
        return [tf.get_config() for tf in self.tfs]


# --- Основное окно ---
class XRayCalcApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("X-Ray Transfocator Calculator (PyQt5)")
        self.resize(1200, 800)

        default_display_fields = {'lens_index_in_block','position', 'L1', 'L2', 'sfx', 'sfy', 'T', 'M'}
        self.current_display_fields = [
            field for field in LENS_RESULT_FIELDS
            if field[0] in default_display_fields and field[2] is not None
        ]

        # Инициализация
        self.controller = AdvancedController()
        self.tf_manager = TransfocatorManager()

        # Создаём TF1 и TF2 по умолчанию
        self.tf_manager.add_tf("TF1", "Vacuum (Groups)", "R500", total_lenses=100, active_ranges=[(0, 8)])  # Vacuum по умолчанию
        self.tf_manager.add_tf("TF2", "Air (Array)", "R50", total_lenses=100, active_ranges=[(0, 8)])

        self.source_params = {
            'energy': 10300.0,
            'sx_fwhm': 32.9 * 2.35482,
            'sy_fwhm': 5.9 * 2.35482,
            'wx_fwhm': 9.4 * 2.35482,
            'wy_fwhm': 11.0 * 2.35482,
            'material': 'Be'
        }

        self.use_fwhm = True
        self.lbl_source_info = QLabel("")
        self.lbl_source_info.setWordWrap(True)
        self.lbl_source_info.setStyleSheet("font-family: monospace; font-size: 9pt;")

        self.init_ui()
        self.update_energy_input()
        self.update_source_info_label()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QHBoxLayout(central_widget)
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)

        # --- ЛЕВАЯ ПАНЕЛЬ ---
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)

        # Глобальные параметры
        gb_global = QGroupBox("Source & Global Params")
        gl_layout = QVBoxLayout()
        hbox_energy = QHBoxLayout()
        hbox_energy.addWidget(QLabel("Energy, eV:"))
        self.inp_energy = QLineEdit("10300")
        self.inp_energy.editingFinished.connect(self.on_energy_input_changed)
        hbox_energy.addWidget(self.inp_energy)
        gl_layout.addLayout(hbox_energy)

        self.btn_edit_source = QPushButton("Edit Source")
        self.btn_edit_source.clicked.connect(self.open_source_editor)
        gl_layout.addWidget(self.btn_edit_source)
        gl_layout.addWidget(self.lbl_source_info)
        gb_global.setLayout(gl_layout)
        left_layout.addWidget(gb_global)

        # Добавить TF
        btn_add_tf = QPushButton("Add TF")
        btn_add_tf.clicked.connect(self.add_new_tf)
        left_layout.addWidget(btn_add_tf)

        # Динамические TF
        self.tf_widgets_layout = QVBoxLayout()
        left_layout.addLayout(self.tf_widgets_layout)

        # Кнопка расчета
        self.btn_calc = QPushButton("CALCULATE")
        self.btn_calc.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; padding: 10px;")
        self.btn_calc.clicked.connect(self.run_calculation)
        left_layout.addWidget(self.btn_calc)

        left_layout.addStretch()

        # Создаём UI для каждого TF
        for tf in self.tf_manager.tfs:
            self.create_tf_ui(tf)

        # --- ПРАВАЯ ПАНЕЛЬ ---
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        self.txt_summary = QTextEdit()
        self.txt_summary.setMaximumHeight(150)
        self.txt_summary.setReadOnly(True)
        right_layout.addWidget(QLabel("Summary Report:"))
        right_layout.addWidget(self.txt_summary)

        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet("QTabWidget::item { padding: 4px; }")

        self.btn_column_settings = QPushButton("Columns...")
        self.btn_column_settings.clicked.connect(self.open_column_settings)

        right_layout.addWidget(QLabel("Beam Propagation History:"))
        right_layout.addWidget(self.btn_column_settings)
        right_layout.addWidget(self.tab_widget)
        self._update_results_table_columns()

        self.btn_export_csv = QPushButton("Export to CSV")
        self.btn_export_csv.clicked.connect(self.export_to_csv)
        right_layout.addWidget(self.btn_export_csv)

        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([400, 800])

    def create_tf_ui(self, tf):
        gb_tf = QGroupBox(f"{tf.name}")
        gb_tf.setCheckable(True)
        gb_tf.setChecked(True)

        tf_layout = QVBoxLayout()

        # Тип TF
        hbox_type = QHBoxLayout()
        hbox_type.addWidget(QLabel("Type:"))
        combo_type = QComboBox()
        combo_type.addItems(["Vacuum (Groups)", "Air (Array)"])
        combo_type.setCurrentText(tf.tf_type)
        hbox_type.addWidget(combo_type)

        btn_edit = QPushButton("Edit TF")
        hbox_type.addWidget(btn_edit)

        btn_remove = QPushButton("Remove TF")
        btn_remove.clicked.connect(lambda: self.remove_tf(tf.name))
        hbox_type.addWidget(btn_remove)

        tf_layout.addLayout(hbox_type)

        # Позиция
        hbox_pos = QHBoxLayout()
        hbox_pos.addWidget(QLabel("Position (m):"))
        spin_pos = QDoubleSpinBox()
        spin_pos.setRange(0, 100)
        spin_pos.setValue(27.1 if tf.name == "TF1" else 64)
        spin_pos.setDecimals(4)
        hbox_pos.addWidget(spin_pos)
        tf_layout.addLayout(hbox_pos)

        # Чекбокс Measure to center
        chk_center = QCheckBox("Measure to center of TF")
        chk_center.setChecked(tf.measure_to_center)
        tf_layout.addWidget(chk_center)

        # Виджеты для Air
        wdg_air = QWidget()
        air_layout = QVBoxLayout(wdg_air)
        spin_n = QSpinBox()
        spin_n.setRange(1, 200)
        spin_n.setValue(tf.total_lenses)
        combo_preset = QComboBox()
        combo_preset.addItems(LENS_PRESETS.keys())
        combo_preset.setCurrentText(tf.preset)
        #air_layout.addWidget(QLabel("Count (N):"))
        #air_layout.addWidget(spin_n)
        air_layout.addWidget(QLabel("Preset:"))
        air_layout.addWidget(combo_preset)
        air_layout.addStretch()
        tf_layout.addWidget(wdg_air)

        # Виджеты для Vacuum (скрыты по умолчанию)
        wdg_vac = QWidget()
        vac_layout = QVBoxLayout(wdg_vac)
        combo_vac_preset = QComboBox()
        combo_vac_preset.addItems(LENS_PRESETS.keys())
        combo_vac_preset.setCurrentText(tf.preset)
        vac_layout.addWidget(QLabel("Preset:"))
        vac_layout.addWidget(combo_vac_preset)
        vac_layout.addStretch()
        tf_layout.addWidget(wdg_vac)

        # Синхронизация
        spin_n.valueChanged.connect(lambda v: self.on_air_n_changed(v, tf.name, spin_n, combo_preset, tf))
        combo_preset.currentTextChanged.connect(lambda p: self.on_air_preset_changed(p, tf.name, combo_preset, tf))
        combo_vac_preset.currentTextChanged.connect(lambda p: self.on_vac_preset_changed(p, tf.name, combo_vac_preset, tf))
        combo_type.currentTextChanged.connect(lambda t: self.on_tf_type_changed(t, tf, wdg_air, wdg_vac))

        # Скрыть/показать виджеты в зависимости от типа
        if tf.tf_type == "Air (Array)":
            wdg_air.setVisible(True)
            wdg_vac.setVisible(False)
        else:
            wdg_air.setVisible(False)
            wdg_vac.setVisible(True)

        gb_tf.setLayout(tf_layout)
        self.tf_widgets_layout.addWidget(gb_tf)

        # Сохраняем виджеты в tf.ui_widgets
        tf.ui_widgets = {
            'gb': gb_tf,
            'combo_type': combo_type,
            'btn_edit': btn_edit,
            'btn_remove': btn_remove,
            'spin_pos': spin_pos,
            'chk_center': chk_center,  # ← добавлено
            'wdg_air': wdg_air,
            'wdg_vac': wdg_vac,
            'spin_n': spin_n,
            'combo_preset': combo_preset,
            'combo_vac_preset': combo_vac_preset
        }

        # Подключаем кнопку Edit
        btn_edit.clicked.connect(lambda: self.open_tf_editor(tf.name, combo_type.currentText(), tf))

    def on_air_n_changed(self, value, tf_name, n_spin, preset_combo, tf_obj):
        tf_obj.total_lenses = value
        tf_obj.update_active_ranges(tf_obj.active_ranges)

    def on_air_preset_changed(self, preset, tf_name, preset_combo, tf_obj):
        tf_obj.update_preset(preset)

    def on_vac_preset_changed(self, preset, tf_name, preset_combo, tf_obj):
        tf_obj.update_preset(preset)

    def on_tf_type_changed(self, tf_type, tf_obj, air_widget, vac_widget):
        # Обновляем tf_obj.tf_type
        tf_obj.tf_type = tf_type
        
        # Скрываем/показываем виджеты
        air_widget.setVisible(tf_type == "Air (Array)")
        vac_widget.setVisible(tf_type == "Vacuum (Groups)")
        
        # Если переключаемся в Air, инициализируем lenses
        if tf_type == "Air (Array)" and not tf_obj.lenses:
            tf_obj.lenses = tf_obj._build_air_lenses()
        
        # Если переключаемся в Vacuum, инициализируем groups
        if tf_type == "Vacuum (Groups)" and not tf_obj.groups:
            tf_obj.groups = [{"N": 1, "preset": tf_obj.preset, "active": True}]

    def add_new_tf(self):
        name = f"TF{len(self.tf_manager.tfs) + 1}"
        new_tf = self.tf_manager.add_tf(name, "Air (Array)", "R50", total_lenses=100, active_ranges=[(0, 8)])
        self.create_tf_ui(new_tf)

    def remove_tf(self, name):
        tf = self.tf_manager.get_tf_by_name(name)
        if tf:
            # Удаляем UI
            gb = tf.ui_widgets['gb']
            self.tf_widgets_layout.removeWidget(gb)
            gb.deleteLater()
            # Удаляем из менеджера
            self.tf_manager.remove_tf(name)

    def update_source_info_label(self):
        energy = self.source_params['energy']
        if self.use_fwhm:
            sx = self.source_params['sx_fwhm']
            sy = self.source_params['sy_fwhm']
            wx = self.source_params['wx_fwhm']
            wy = self.source_params['wy_fwhm']
            size_label_x = "Source size X, um (FWHM):"
            size_label_y = "Source size Y, um (FWHM):"
            div_label_x = "Divergence X, mrad (FWHM):"
            div_label_y = "Divergence Y, mrad (FWHM):"
        else:
            sx = self.source_params['sx_fwhm'] / 2.35482
            sy = self.source_params['sy_fwhm'] / 2.35482
            wx = self.source_params['wx_fwhm'] / 2.35482
            wy = self.source_params['wy_fwhm'] / 2.35482
            size_label_x = "Source size X, um (Sigma):"
            size_label_y = "Source size y, um (Sigma):"
            div_label_x = "Divergence X, mrad (Sigma):"
            div_label_y = "Divergence Y, mrad (Sigma):"

        text = (
            f"Energy: {energy:.0f} eV\n"
            f"{size_label_x} {sx:.2f}\n"
            f"{size_label_y} {sy:.2f}\n"
            f"{div_label_x} {wx:.2f}\n"
            f"{div_label_y} {wy:.2f}"
        )

        self.lbl_source_info.setText(text)

    def open_source_editor(self):
        dialog = SourceEditorDialog(
            self,
            source_params = self.source_params.copy(),
            use_fwhm = self.use_fwhm 
        )
        if dialog.exec_() == QDialog.Accepted:
            new_params = dialog.get_params()
            self.use_fwhm = dialog.get_use_fwhm()
            self.source_params.update(new_params)
            self.update_energy_input()
            self.update_source_info_label()

    def open_tf_editor(self, name, tf_type, tf_obj):
        # Выбираем, какую конфигурацию передавать
        config = tf_obj.lenses if tf_type == "Air (Array)" else tf_obj.groups

        dialog = TFEditorDialog(
            self, 
            tf_type='air' if tf_type == "Air (Array)" else 'vacuum',
            config=config,
            title=f"Edit {name}",
            energy = self.source_params['energy']
        )
        if dialog.exec_() == QDialog.Accepted:
            new_config = dialog.get_config()
            if tf_type == "Air (Array)":
                tf_obj.lenses = new_config
                # Обновляем total_lenses и active_ranges
                tf_obj.total_lenses = len(new_config)
                tf_obj.active_ranges = [(i, i) for i in range(len(new_config)) if new_config[i]['active']]
            else:
                tf_obj.groups = new_config  # <-- Сохраняем обновлённые группы

    def on_energy_input_changed(self):
        try:
            energy = float(self.inp_energy.text())
            self.source_params['energy'] = energy
            self.update_source_info_label()
        except ValueError:
            self.update_energy_input()

    def update_energy_input(self):
        self.inp_energy.setText(f"{self.source_params['energy']:.0f}")

    def run_calculation(self):
        calc_params = self.source_params.copy()
        if not self.use_fwhm:
            calc_params['sx_fwhm'] = self.source_params['sx_fwhm'] / 2.35482
            calc_params['sy_fwhm'] = self.source_params['sy_fwhm'] / 2.35482
            calc_params['wx_fwhm'] = self.source_params['wx_fwhm'] / 2.35482
            calc_params['wy_fwhm'] = self.source_params['wy_fwhm'] / 2.35482

        structure_config = []
        for tf in self.tf_manager.tfs:
            if not tf.ui_widgets['gb'].isChecked():
                continue

            config = tf.get_config()
            config['tf_name'] = tf.name

            pos = tf.ui_widgets['spin_pos'].value()
            if tf.ui_widgets['chk_center'].isChecked():
                # Примерные длины для Air и Vacuum
                length = 0.1396 if tf.tf_type == "Air (Array)" else 0.153
                absolute_start = pos - length / 2
            else:
                absolute_start = pos

            config['absolute_start'] = absolute_start
            structure_config.append(config)

        try:
            report = self.controller.run_calculations(
                calc_params['energy'],
                structure_config,
                source_params=calc_params
            )
        except Exception as e:
            QMessageBox.critical(self, "Calculation Error", str(e))
            import traceback
            traceback.print_exc()
            return

        self.display_results(report)

    def display_results(self, report):
        self._last_report = report
        if not report or "Error" in report:
            self.txt_summary.setText("No results or error occurred.")
            return
        
        history = report.get('full_history', [])
        if not history:
            self.txt_summary.setText("No results computed.")
            return

        last = history[-1]
        focus_pos = report['final_pos'] + report['L2']
        summary = (
            f"<b>Energy:</b> {report['energy']} eV<br>"
            #f"<b>Final Position:</b> {report['final_pos']:.4f} m<br>"
            f"<b>Focal Distance (L2) from last lens:</b> {report['L2']:.4f} m<br>"
            f"<b>Focus position:</b> {focus_pos:.4f} m<br>"
            f"<b>Transmission:</b> {report['T']*100:.2f} %<br>"
            f"<b>Focus Size X:</b> {report['size_x']*1e6:.2f} um<br>"
            f"<b>Focus Size Y:</b> {report['size_y']*1e6:.2f} um<br>"
            f"<b>Depth of Field X:</b> {last.dof_x:.3f} m<br>"
            f"<b>Depth of Field Y:</b> {last.dof_y:.3f} m<br>"
            f"<b>Symmetry Distance (from focus position):</b> {last.symmetry_dist:.4f} m<br>"
            f"<b>Symmetry Distance (from last lens position):</b> {(focus_pos - last.symmetry_dist):.4f}m,  {(focus_pos + last.symmetry_dist):.4f}m<br>"
            f"<b>Symmetry Beam Size X:</b> {last.symm_beam_size_x * 1e6:.2f} um<br>"
            f"<b>Symmetry Beam Size Y:</b> {last.symm_beam_size_y * 1e6:.2f} um<br>"
        )
        self.txt_summary.setHtml(summary)


        tf_histories = {}
        for item in history:
            tf_name = item.tf_name
            if tf_name not in tf_histories:
                tf_histories[tf_name] = []
            tf_histories[tf_name].append(item)

        self.tab_widget.clear()

        for tf_name, tf_history in tf_histories.items():
            table = QTableWidget(0, 0)
            table.verticalHeader().setVisible(False)
            table.setStyleSheet("QTableWidget::item {padding: 2px 4px; }")
            table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)

            # Headers setup
            headers = [field[2] for field in self.current_display_fields]
            table.setColumnCount(len(headers))
            table.setHorizontalHeaderLabels(headers)
            table.horizontalHeader().setSectionResizeMode(QHeaderView.Fixed)
            for col, field in enumerate(self.current_display_fields):
                width = 100
                table.setColumnWidth(col, width)

            # Table content
            display_rows = []
            for i, item in enumerate(tf_history):
                display_rows.append(item)
                is_last_in_block = getattr(item, 'is_last_in_block', False)
                is_last_in_tf = getattr(item, 'is_last_in_tf', False)

                if is_last_in_block and not is_last_in_tf and i + 1 < len(tf_history):
                    next_block_index = getattr(tf_history[i + 1], 'block_index', None)
                    if next_block_index is not None:
                        display_rows.append(f"Block {next_block_index}")
                
            table.setRowCount(len(display_rows))
            for row, item in enumerate(display_rows):
                if isinstance(item, str):
                    table.setItem(row, 0, QTableWidgetItem(item))
                    for col in range(1, table.columnCount()):
                        table.setItem(row, col, QTableWidgetItem(""))
                    font = table.item(row, 0).font()
                    font.setBold(True)
                    table.item(row, 0).setFont(font)
                else:
                    for col, field in enumerate(self.current_display_fields):
                        field_name = field[0]
                        formatter = field[3]
                        value = getattr(item, field_name)
                        text = formatter(value) if formatter else str(value)
                        table.setItem(row, col, QTableWidgetItem(text))

            self.tab_widget.addTab(table, tf_name) 

    def open_column_settings(self):
        all_fields_info = [
            (field[0], field[2], field[3])
            for field in LENS_RESULT_FIELDS
            if field[2] is not None
        ]
        current_names = [field[0] for field in self.current_display_fields] if self.current_display_fields else None
        dialog = ColumnSettingsDialog(self, current_names, all_fields_info)
        if dialog.exec_() == QDialog.Accepted:
            selected_names = set(dialog.get_selected_fields())
            self.current_display_fields = [
                field for field in LENS_RESULT_FIELDS
                if field[0] in selected_names and field[2] is not None
            ]
            self._update_results_table_columns()

    def _update_results_table_columns(self):
        if not self.current_display_fields:
            self.current_display_fields = [
                field for field in LENS_RESULT_FIELDS
                if field[2] is not None
            ]
        headers = [field[2] for field in self.current_display_fields]

        for i in range(self.tab_widget.count()):
            table = self.tab_widget.widget(i)
            if isinstance(table, QTableWidget):
                table.setColumnCount(len(headers))
                table.setHorizontalHeaderLabels(headers)
                table.setStyleSheet("QTableWidget::item { padding: 2px 4px; }")

                header = table.horizontalHeader()
                for col, field in enumerate(self.current_display_fields):
                    width = 100
                    table.setColumnWidth(col, width)
                    header.setSectionResizeMode(col, QHeaderView.Fixed)

        if hasattr(self, '_last_report'):
            self.display_results(self._last_report)


    def export_to_csv(self):
        if not hasattr(self, '_last_report') or not self._last_report:
            QMessageBox.warning(self, "Export Error", "No results to export. Please run calculation first.")
            return

        # Диалог выбора директории
        directory = QFileDialog.getExistingDirectory(self, "Select Directory to Save CSV Files")
        if not directory:
            return

        history = self._last_report.get('full_history', [])
        if not history:
            QMessageBox.information(self, "Export", "No history data to export.")
            return

        try:
            # 1. Экспорт Summary Report
            focus_pos = self._last_report['final_pos'] + self._last_report['L2']
            last = history[-1]
            summary_data = {
                "Field": [
                    "Energy",
                    "Final Position",
                    "Focal Distance (L2)",
                    "Focus Position",
                    "Transmission",
                    "Focus Size X",
                    "Focus Size Y",
                    "Depth of Field X",
                    "Depth of Field Y",
                    "Symmetry Distance",
                    "Symmetry Distance (from lens)",
                    "Symmetry Distance (from lens)",
                    "Symmetry Beam Size X",
                    "Symmetry Beam Size Y"
                ],
                "Value": [
                    self._last_report['energy'],
                    self._last_report['final_pos'],
                    self._last_report['L2'],
                    focus_pos,  # focus_pos
                    self._last_report['T'] * 100,
                    self._last_report['size_x'] * 1e6,
                    self._last_report['size_y'] * 1e6,
                    last.dof_x,  # если есть
                    last.dof_y,  # если есть
                    last.symmetry_dist,
                    focus_pos - last.symmetry_dist,
                    focus_pos + last.symmetry_dist,
                    last.symm_beam_size_x * 1e6,
                    last.symm_beam_size_y * 1e6
                ]
            }
            df_summary = pd.DataFrame(summary_data)
            summary_path = os.path.join(directory, "summary_report.csv")
            df_summary.to_csv(summary_path, index=False)

            # 2. Экспорт истории каждого TF


            tf_histories = {}
            for item in history:
                tf_name = item.tf_name
                if tf_name not in tf_histories:
                    tf_histories[tf_name] = []
                tf_histories[tf_name].append(item)

            for tf_name, tf_history in tf_histories.items():
                # Подготовим данные для DataFrame
                rows = []
                for item in tf_history:
                    if isinstance(item, str):
                        # Пропускаем заголовки блоков, если не нужно их сохранять
                        continue
                    row = {}
                    for field in self.current_display_fields:
                        field_name = field[0]
                        value = getattr(item, field_name)
                        row[field_name] = value
                    rows.append(row)

                df_tf = pd.DataFrame(rows)
                tf_path = os.path.join(directory, f"{tf_name}_history.csv")
                df_tf.to_csv(tf_path, index=False)

            QMessageBox.information(self, "Export", f"Data exported successfully to:\n{directory}")

        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export data:\n{str(e)}")


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = XRayCalcApp()
    window.show()
    sys.exit(app.exec_())