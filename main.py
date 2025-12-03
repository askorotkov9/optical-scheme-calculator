import sys
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QGroupBox, QLabel, QLineEdit, QComboBox, QCheckBox, 
                             QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, 
                             QSpinBox, QDoubleSpinBox, QTabWidget, QSplitter, QTextEdit, QMessageBox, QDialog, QSizePolicy, QSizePolicy)
from PyQt5.QtCore import Qt

from main_controller import AdvancedController # type: ignore
from parameters_micro1 import LENS_PRESETS, LensGenerator
from lens_editor import TFEditorDialog, LensDetailDialog # type: ignore
from computations import LENS_RESULT_FIELDS
from column_settings import ColumnSettingsDialog # type: ignore
from source_editor import SourceEditorDialog # type: ignore

# --- Расширение контроллера для поддержки детальной настройки --- #Перенести в main_controller (?)

    
# --- Компонент: Редактор списка линз (Таблица) ---
class LensGroupEditor(QWidget):
    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)

        #Кнопки управления
        btn_layout = QHBoxLayout()
        self.btn_add = QPushButton("Add Group")
        self.btn_remove = QPushButton("Remove Last")
        self.btn_add.clicked.connect(self.add_row)
        self.btn_remove.clicked.connect(self.remove_row)
        btn_layout.addWidget(self.btn_add)
        btn_layout.addWidget(self.btn_remove)
        self.layout.addLayout(btn_layout)

        #таблица

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["N Lenses", "Preset (R)", "In Beam", "Description"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.layout.addWidget(self.table)

        #Initial data (как в tf1 по умолчанию)
        self.add_default_rows()

    def add_default_rows(self):
        # Добавляем стандартную конфигурацию: 1, 2, 3 линзы R500
        for n in [1, 2, 3]:
            self.add_row(n_val = n, preset = "R500")

    def add_row(self, n_val=1, preset="R500"):
        row = self.table.rowCount()
        self.table.insertRow(row)

        # 1. SpinBox для количества линз
        sb_n = QSpinBox()
        sb_n.setRange(1, 100)
        sb_n.setValue(n_val)
        self.table.setCellWidget(row, 0, sb_n)

        # 2. ComboBox для типа линзы
        cb_preset = QComboBox()
        cb_preset.addItems(LENS_PRESETS.keys()) # ['R50', 'R100', ...]
        cb_preset.setCurrentText(preset)
        self.table.setCellWidget(row, 1, cb_preset)

        # 3. CheckBox для In Beam
        chk_active = QCheckBox()
        chk_active.setChecked(True)
        # Центрируем чекбокс
        cell_widget = QWidget()
        layout = QHBoxLayout(cell_widget)
        layout.addWidget(chk_active)
        layout.setAlignment(Qt.AlignCenter)
        layout.setContentsMargins(0,0,0,0)
        self.table.setCellWidget(row, 2, cell_widget)
        
        # Сохраняем ссылку на чекбокс, чтобы читать его состояние
        cell_widget.chk = chk_active

        # 4. Описание (просто текст)
        item_desc = QTableWidgetItem(f"Group {row + 1}")
        self.table.setItem(row, 3, item_desc)

    def remove_row(self):
        row = self.table.rowCount()
        if row > 0:
            self.table.removeRow(row - 1)

    def get_config(self):
        """Собирает данные из таблицы в список словарей."""
        config = []
        for r in range(self.table.rowCount()):
            sb_n = self.table.cellWidget(r, 0)
            cb_preset = self.table.cellWidget(r, 1)
            # Достаем чекбокс из виджета-контейнера
            chk_active = self.table.cellWidget(r, 2).chk 
            
            config.append({
                'N': sb_n.value(),
                'preset': cb_preset.currentText(),
                'active': chk_active.isChecked()
            })
        return config
    
# --- Основное окно ---
class XRayCalcApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("X-Ray Transfocator Calculator (PyQt5)") #Optical Lens Scheme Parameters Calculator
        self.resize(1200, 800)

        default_display_fields = {'lens_index_in_block','position', 'L1', 'L2', 'sfx', 'sfy', 'T', 'M'}
        self.current_display_fields = [
            field for field in LENS_RESULT_FIELDS
            if field[0] in default_display_fields and field[2] is not None
]
        
        # Инициализация контроллера
        self.controller = AdvancedController()
        self.tf1_air_config = [
            {'preset': 'R500', 'active': (i < 9)}
            for i in range(100)
        ]

        # TF2 Air: 100 линз, первые 9 активны  
        self.tf2_air_config = [
            {'preset': 'R50', 'active': (i < 9)}
            for i in range(100)
        ]

        self.source_params = {
            'energy': 10300.0,
            'sx_fwhm': 32.9 * 2.35482,   # мкм
            'sy_fwhm': 5.9 * 2.35482,    # мкм
            'wx_fwhm': 9.4 * 2.35482,    # мкрад
            'wy_fwhm': 11.0 * 2.35482,   # мкрад
            #'use_fwhm': True,
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
        
        # Главный layout (Сплиттер: слева настройки, справа результаты)
        main_layout = QHBoxLayout(central_widget)
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)

        # --- ЛЕВАЯ ПАНЕЛЬ: НАСТРОЙКИ ---
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        
        # 1. Глобальные параметры
        gb_global = QGroupBox("Source & Global Params")
        gl_layout = QVBoxLayout()
        
        hbox_energy = QHBoxLayout()
        hbox_energy.addWidget(QLabel("Energy, eV:"))
        self.inp_energy = QLineEdit("10300")
        self.inp_energy.editingFinished.connect(self.on_energy_input_changed)
        
        hbox_energy.addWidget(self.inp_energy)
        gl_layout.addLayout(hbox_energy)

        # Кнопка Edit Source
        self.btn_edit_source = QPushButton("Edit Source")
        self.btn_edit_source.clicked.connect(self.open_source_editor)
        gl_layout.addWidget(self.btn_edit_source)
        gl_layout.addWidget(self.lbl_source_info)

        
        gb_global.setLayout(gl_layout)
        left_layout.addWidget(gb_global)

        # 2. Настройки TF1
        gb_tf1 = QGroupBox("Transfocator 1 (TF1)")
        gb_tf1.setCheckable(True)
        gb_tf1.setChecked(True)
        tf1_layout = QVBoxLayout()
        
        # Тип TF1
        hbox_tf1_type = QHBoxLayout()
        hbox_tf1_type.addWidget(QLabel("Type:"))
        self.combo_tf1_type = QComboBox()
        self.combo_tf1_type.addItems(["Vacuum (Groups)", "Air (Array)"])
        #self.combo_tf1_type.currentIndexChanged.connect(self._on_tf_type_changed)
        hbox_tf1_type.addWidget(self.combo_tf1_type)
        self.btn_edit_tf1 = QPushButton("Edit TF1")
        tf1_layout.addLayout(hbox_tf1_type)
        tf1_layout.addWidget(self.btn_edit_tf1)

        self.btn_edit_tf1.clicked.connect(
            lambda: self.open_tf_editor('TF1', self.combo_tf1_type.currentText())
        )

        # L1 to first TF
        hbox_l1 = QHBoxLayout()
        hbox_l1.addWidget(QLabel("Start Dist (m):"))
        self.spin_l1 = QDoubleSpinBox()
        self.spin_l1.setRange(0, 100)
        self.spin_l1.setValue(27.075) # 27.1 - 0.05/2
        self.spin_l1.setDecimals(4)
        hbox_l1.addWidget(self.spin_l1)
        tf1_layout.addLayout(hbox_l1)
        self.chk_l1_center = QCheckBox("Measure L1 to center of TF1")
        self.chk_l1_center.setChecked(True)  # можно по умолчанию включить
        tf1_layout.addWidget(self.chk_l1_center)

        # Стек виджетов для TF1 (Таблица или простые настройки)
        self.stack_tf1 = QTabWidget() 
        self.stack_tf1.tabBar().hide() # Скрываем табы, управляем программно
        self.stack_tf1.setStyleSheet("QTabWidget::pane { border: 0; }")

        # Виджет 1: Редактор групп (Vacuum)
        self.tf1_editor = LensGroupEditor()
        self.stack_tf1.addTab(self.tf1_editor, "Vacuum")

        # Виджет 2: Простые настройки (Air)
        self.wdg_tf1_air = QWidget()
        air_layout = QVBoxLayout(self.wdg_tf1_air)
        self.spin_tf1_air_N = QSpinBox()
        self.spin_tf1_air_N.setRange(1, 200)
        self.spin_tf1_air_N.setValue(10)
        self.combo_tf1_air_R = QComboBox()
        self.combo_tf1_air_R.addItems(LENS_PRESETS.keys())
        air_layout.addWidget(QLabel("Count (N):"))
        air_layout.addWidget(self.spin_tf1_air_N)
        air_layout.addWidget(QLabel("Preset:"))
        air_layout.addWidget(self.combo_tf1_air_R)
        air_layout.addStretch()
        self.stack_tf1.addTab(self.wdg_tf1_air, "Air")

        tf1_layout.addWidget(self.stack_tf1)
        gb_tf1.setLayout(tf1_layout)
        left_layout.addWidget(gb_tf1)

        # 3. Настройки TF2
        gb_tf2 = QGroupBox("Transfocator 2 (TF2)")
        gb_tf2.setCheckable(True)
        gb_tf2.setChecked(True)
        self.gb_tf2 = gb_tf2 # сохраняем ссылку
        tf2_layout = QVBoxLayout()

        # Тип TF2
        hbox_tf2_type = QHBoxLayout()
        hbox_tf2_type.addWidget(QLabel("Type:"))
        self.combo_tf2_type = QComboBox()
        self.combo_tf2_type.addItems(["Air (Array)", "Vacuum (Groups)"]) # По умолчанию Air
        #self.combo_tf2_type.currentIndexChanged.connect(self._on_tf_type_changed)
        hbox_tf2_type.addWidget(self.combo_tf2_type)
        self.btn_edit_tf2 = QPushButton("Edit TF2")
        tf2_layout.addLayout(hbox_tf2_type)
        tf2_layout.addWidget(self.btn_edit_tf2)

        self.btn_edit_tf2.clicked.connect(
            lambda: self.open_tf_editor('TF2', self.combo_tf2_type.currentText())
        )

        hbox_l2 = QHBoxLayout()
        hbox_l2.addWidget(QLabel("TF2 Position (m):"))
        self.l2_input = QDoubleSpinBox()
        self.l2_input.setRange(0, 100)
        self.l2_input.setValue(64)  # пример
        self.l2_input.setDecimals(4)
        hbox_l2.addWidget(self.l2_input)
        tf2_layout.addLayout(hbox_l2)

        self.chk_gap_center = QCheckBox("Measure TF2 position to center of TF2")
        self.chk_gap_center.setChecked(True)
        tf2_layout.addWidget(self.chk_gap_center)

        # Стек для TF2
        self.stack_tf2 = QTabWidget()
        self.stack_tf2.tabBar().hide()
        self.stack_tf2.setStyleSheet("QTabWidget::pane { border: 0; }")

        # Виджет 1: Air (По умолчанию для TF2)
        self.wdg_tf2_air = QWidget()
        air2_layout = QVBoxLayout(self.wdg_tf2_air)
        self.spin_tf2_air_N = QSpinBox()
        self.spin_tf2_air_N.setRange(1, 200)
        self.spin_tf2_air_N.setValue(9)
        #self.spin_tf2_air_N.valueChanged.connect(self.on_tf2_air_n_changed)
        #self.combo_tf2_air_R.currentTextChanged.connect(self.on_tf2_air_preset_changed) #для air_tf1 тоже
        self.combo_tf2_air_R = QComboBox()
        self.combo_tf2_air_R.addItems(LENS_PRESETS.keys())
        self.combo_tf2_air_R.setCurrentText('R50')
        air2_layout.addWidget(QLabel("Count (N):"))
        air2_layout.addWidget(self.spin_tf2_air_N)
        air2_layout.addWidget(QLabel("Preset:"))
        air2_layout.addWidget(self.combo_tf2_air_R)
        air2_layout.addStretch()
        self.stack_tf2.addTab(self.wdg_tf2_air, "Air")

        # Виджет 2: Vacuum editor
        self.tf2_editor = LensGroupEditor()
        # Очистим дефолтные строки для TF2, чтобы не путать
        while self.tf2_editor.table.rowCount() > 0:
            self.tf2_editor.remove_row()
        self.tf2_editor.add_row(5, 'R500') # Пример
        self.stack_tf2.addTab(self.tf2_editor, "Vacuum")

        tf2_layout.addWidget(self.stack_tf2)
        gb_tf2.setLayout(tf2_layout)
        left_layout.addWidget(gb_tf2)

        # Кнопка расчета
        self.btn_calc = QPushButton("CALCULATE")
        self.btn_calc.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; padding: 10px;")
        self.btn_calc.clicked.connect(self.run_calculation)
        left_layout.addWidget(self.btn_calc)
        
        left_layout.addStretch() # Поджим вверх
        
        # Подключаем обработчики смены типа TF
        tf_configs = [
            (self.combo_tf1_type, self.stack_tf1, self.tf1_editor, 'R500'),
            (self.combo_tf2_type, self.stack_tf2, self.tf2_editor, 'R50'),
        ]
        for combo, stack, editor, preset in tf_configs:
            self._connect_tf_type_combo(combo, stack, editor, preset)

        # Синхронизация Air-TF
        self.spin_tf1_air_N.valueChanged.connect(
            lambda v: self.on_air_n_changed(v, 'TF1', self.spin_tf1_air_N, self.combo_tf1_air_R, 'tf1_air_config')
        )
        self.spin_tf2_air_N.valueChanged.connect(
            lambda v: self.on_air_n_changed(v, 'TF2', self.spin_tf2_air_N, self.combo_tf2_air_R, 'tf2_air_config')
        )

        # Синхронизация пресета (опционально)
        self.combo_tf1_air_R.currentTextChanged.connect(
            lambda p: self.on_air_preset_changed(p, 'TF1', self.combo_tf1_air_R, 'tf1_air_config')
        )
        self.combo_tf2_air_R.currentTextChanged.connect(
            lambda p: self.on_air_preset_changed(p, 'TF2', self.combo_tf2_air_R, 'tf2_air_config')
        )

        # --- ПРАВАЯ ПАНЕЛЬ: РЕЗУЛЬТАТЫ ---
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        self.txt_summary = QTextEdit()
        self.txt_summary.setMaximumHeight(150)
        self.txt_summary.setReadOnly(True)
        right_layout.addWidget(QLabel("Summary Report:"))
        right_layout.addWidget(self.txt_summary)

        # Таблица истории
        self.table_res = QTableWidget(0, 0)
        self.table_res.verticalHeader().setVisible(False)
        #self.table_res.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table_res.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        #self.table_res.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Preferred)

        self.table_res.setStyleSheet("QTableWidget::item { padding: 2px 40px; }")

        # Кнопка настроек колонок
        self.btn_column_settings = QPushButton("Columns...")
        self.btn_column_settings.clicked.connect(self.open_column_settings)

        # Добавляем в layout
        right_layout.addWidget(QLabel("Beam Propagation History:"))
        right_layout.addWidget(self.btn_column_settings)
        right_layout.addWidget(self.table_res)

        # Инициализируем колонки
        self._update_results_table_columns()
        '''
        # Таблица истории
        headers = [idx[1] for idx in DISPLAY_FIELDS]  # Берём "заголовок"
        self.table_res = QTableWidget(0, len(headers))
        self.table_res.setHorizontalHeaderLabels(headers)
        self.table_res.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)


        #cols = ["Idx", "Pos (m)", "L1", "L2", "Size X (um)", "Size Y (um)", "Trans (%)", "M total"]
        #self.table_res = QTableWidget(0, len(cols))  # ← автоматически 9 столбцов
        #self.table_res.setHorizontalHeaderLabels(cols)
        #self.table_res.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        right_layout.addWidget(QLabel("Beam Propagation History:"))
        right_layout.addWidget(self.table_res)
        '''
        # Добавляем панели в сплиттер
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([400, 800]) # Пропорции

    def update_source_info_label(self):
        """Обновляет метку с информацией об источнике и оптических константах."""
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
            self.use_fwhm = dialog.get_use_fwhm()  # ← сохраняйте новое состояние
            self.source_params.update(new_params)  # ← new_params — всегда в FWHM!
            # Обновляем поле энергии в основном окне для синхронизации
            #self.inp_energy.setText(str(int(new_params['energy'])))
            self.update_energy_input()
            self.update_source_info_label()
    
    def on_energy_input_changed(self):
        try:
            energy = float(self.inp_energy.text())
            self.source_params['energy'] = energy
            self.update_source_info_label()  # обновляем оптические константы
        except ValueError:
            # Если введено не число — возвращаем последнее валидное значение
            self.update_energy_input()
    
    def update_energy_input(self):
        """Обновляет поле ввода энергии из self.source_params."""
        self.inp_energy.setText(f"{self.source_params['energy']:.0f}")

    def _on_tf_type_changed(self, stack_widget, editor_widget, idx, default_preset='R500'):
        stack_widget.setCurrentIndex(idx)
        if idx == 1:  # Vacuum
            while editor_widget.table.rowCount() > 0:
                editor_widget.remove_row()
            editor_widget.add_row(1, default_preset)

    def on_air_n_changed(self, value, tf_name, n_spin, preset_combo, config_attr):
        """
        Универсальный обработчик изменения Count (N) для Air-TF.
        
        Args:
            value: новое значение N
            tf_name: имя TF ('TF1' или 'TF2')
            n_spin: QSpinBox с Count (N)
            preset_combo: QComboBox с пресетом
            config_attr: имя атрибута конфигурации ('tf1_air_config' или 'tf2_air_config')
        """
        # Проверяем, что текущий тип TF — Air
        combo_type = self.combo_tf1_type if tf_name == 'TF1' else self.combo_tf2_type
        if combo_type.currentText() != "Air (Array)":
            return
        
        preset = preset_combo.currentText()
        current_config = getattr(self, config_attr)
        
        # Сохраняем active-состояния существующих линз
        active_states = [lens.get('active', True) for lens in current_config]
        
        # Обрезаем или дополняем список
        if value <= len(active_states):
            active_states = active_states[:value]
        else:
            active_states.extend([True] * (value - len(active_states)))
        
        # Обновляем конфигурацию
        new_config = [{'preset': preset, 'active': active} for active in active_states]
        setattr(self, config_attr, new_config)

    def _connect_tf_type_combo(self, combo_widget, stack_widget, editor_widget, default_preset):
        combo_widget.currentIndexChanged.connect(
            lambda idx: self._on_tf_type_changed(stack_widget, editor_widget, idx, default_preset)
        )

    ''' 
    def _on_tf_type_changed(self, stack_widget, editor_widget, idx, default_preset='R500', save_key=None):
        if save_key and hasattr(self, '_tf_configs'):
            # Сохраняем текущую конфигурацию
            self._tf_configs[save_key] = editor_widget.get_config()
        
        stack_widget.setCurrentIndex(idx)
        
        if idx == 1:  # Vacuum
            while editor_widget.table.rowCount() > 0:
                editor_widget.remove_row()
            # Восстанавливаем или используем дефолт
            config = self._tf_configs.get(save_key, [{'N': 1, 'preset': default_preset, 'active': True}])
            for block in config:
                editor_widget.add_row(block['N'], block['preset'])
                # Обновить active — потребует доработки add_row

    def _connect_tf_type_combo(self, combo_widget, stack_widget, editor_widget, default_preset):
        """Подключает комбобокс типа TF к универсальному обработчику."""
        combo_widget.currentIndexChanged.connect(
            lambda idx: self._on_tf_type_changed(stack_widget, editor_widget, idx, default_preset)
        )
    '''
    def _calculate_tf_length(self, tf_type, config_data): #вынести длины в отдельные переменные в parameters_micro1 (переименовать в scheme_parameters)
        """Вычисляет физическую длину трансфокатора (в метрах)."""
        p = self.controller.defaults['p']
        u_vac = self.controller.defaults['u_vac']
        u_air = self.controller.defaults['u_air']
        
        total_length = 0.0

        if tf_type == 'air':
            #N = config_data['lens_count']
            total_length = 0.1396
        else:  # vacuum
            total_length = 0.153 #if dist between groups = 0.001
            """
            for group in config_data['groups']:
                if not group['active']:
                    continue
                N = group['N']
                total_length += N * p + (N - 1) * u_vac
            """
        return total_length    

    def get_tf_config_from_widgets(self, combo_type, spin_n=None, combo_preset=None, editor=None):
        """Универсальный метод для любого TF."""
        is_air = (combo_type.currentText() == "Air (Array)")
        if is_air:
            return [{'preset': combo_preset.currentText(), 'active': True} 
                    for _ in range(spin_n.value())]
        else:
            return editor.get_config()
    '''
    def _get_tf1_config(self):
            if self.combo_tf1_type.currentText() == "Air (Array)":
                return [{'preset': self.combo_tf1_air_R.currentText(), 'active': True} 
                        for _ in range(self.spin_tf1_air_N.value())]
            else:
                return self.tf1_editor.get_config()
    '''
    def _build_tf_config(self, tf_name, is_air, absolute_start, air_n=None, air_preset=None, vacuum_groups=None):
        if is_air:
            return {
                'type': 'air',
                'tf_name': tf_name,
                'absolute_start': absolute_start,
                'lens_count': air_n,
                'preset': air_preset
            }
        else:
            return {
                'type': 'vacuum',
                'tf_name': tf_name,
                'absolute_start': absolute_start,
                'groups': vacuum_groups
            }   
            
    def open_tf_editor(self, name, tf_type):
        is_air = (tf_type == "Air (Array)")
        
        # Выбираем, какую конфигурацию передавать
        if name == "TF1":
            if is_air:
                config = self.tf1_air_config
            else:
                config = self.tf1_editor.get_config()
        else:  # TF2
            if is_air:
                config = self.tf2_air_config
            else:
                config = self.tf2_editor.get_config()

        dialog = TFEditorDialog(
            self, 
            tf_type='air' if is_air else 'vacuum',
            config=config,
            title=f"Edit {name}"
        )
        if dialog.exec_() == QDialog.Accepted:
            new_config = dialog.get_config()
            # Сохраняем внутреннюю конфигурацию
            if name == "TF1":
                if is_air:
                    self.tf1_air_config = new_config
                else:
                    # Для vacuum — просто обновим таблицу (по желанию)
                    self.tf1_editor.table.setRowCount(0)
                    for block in new_config:
                        self.tf1_editor.add_row(n_val=block['N'], preset=block['preset'])
                        # Примечание: active не обновляется — можно доработать позже
            else:  # TF2
                if is_air:
                    self.tf2_air_config = new_config
                else:
                    self.tf2_editor.table.setRowCount(0)
                    for block in new_config:
                        self.tf2_editor.add_row(n_val=block['N'], preset=block['preset'])

    def _update_tf1_from_editor(self, config, is_air):
        if is_air:
            # Обновляем N и preset по первому элементу (или усредняем)
            self.spin_tf1_air_N.setValue(len(config))
            if config:
                self.combo_tf1_air_R.setCurrentText(config[0]['preset'])
        else:
            # Обновляем таблицу tf1_editor
            self.tf1_editor.table.setRowCount(0)
            for block in config:
                self.tf1_editor.add_row(n_val=block['N'], preset=block['preset'])
                # Обновить чекбокс 'active' — потребует доработки LensGroupEditor

    def on_air_preset_changed(self, preset, tf_name, preset_combo, config_attr):
        """Универсальный обработчик изменения пресета для Air-TF."""
        combo_type = self.combo_tf1_type if tf_name == 'TF1' else self.combo_tf2_type
        if combo_type.currentText() != "Air (Array)":
            return
        
        config = getattr(self, config_attr)
        for lens in config:
            lens['preset'] = preset


    def run_calculation(self):
        calc_params = self.source_params.copy()
        energy = float(self.source_params['energy'])

        structure_config = []

        # --- TF1 ---
        tf1_is_air = (self.combo_tf1_type.currentText() == "Air (Array)")
        l1_input = self.spin_l1.value()

        # Длина TF1
        if tf1_is_air:
            tf1_length = self._calculate_tf_length('air', None)
            lenses = self.tf1_air_config
        else:
            tf1_length = self._calculate_tf_length('vacuum', {'groups': self.tf1_editor.get_config()})
            lenses = None

        # Позиция
        if self.chk_l1_center.isChecked():
            absolute_start = l1_input - tf1_length / 2
        else:
            absolute_start = l1_input

        # Конфиг
        if tf1_is_air:
            tf1_config = {
                'type': 'air',
                'tf_name': 'TF1',
                'absolute_start': absolute_start,
                'lenses': self.tf1_air_config
            }
        else:
            tf1_config = {
                'type': 'vacuum',
                'tf_name': 'TF1',
                'absolute_start': absolute_start,
                'groups': self.tf1_editor.get_config()
            }
        structure_config.append(tf1_config)
        tf1_end = absolute_start + tf1_length

        # --- TF2 ---
        if self.gb_tf2.isChecked():
            tf2_is_air = (self.combo_tf2_type.currentText() == "Air (Array)")
            l2_input = self.l2_input.value()

            if tf2_is_air:
                tf2_length = self._calculate_tf_length('air', None)
            else:
                tf2_length = self._calculate_tf_length('vacuum', {'groups': self.tf2_editor.get_config()})

            if self.chk_gap_center.isChecked():
                absolute_start = l2_input - tf2_length / 2
            else:
                absolute_start = l2_input

            if tf2_is_air:
                tf2_config = {
                    'type': 'air',
                    'tf_name': 'TF2',
                    'absolute_start': absolute_start,
                    'lenses': self.tf2_air_config
                }
            else:
                tf2_config = {
                    'type': 'vacuum',
                    'tf_name': 'TF2',
                    'absolute_start': absolute_start,
                    'groups': self.tf2_editor.get_config()
                }
            structure_config.append(tf2_config)

        if not self.use_fwhm:  # т.е. используется Sigma
            calc_params['sx_fwhm'] = self.source_params['sx_fwhm'] / 2.35482
            calc_params['sy_fwhm'] = self.source_params['sy_fwhm'] / 2.35482
            calc_params['wx_fwhm'] = self.source_params['wx_fwhm'] / 2.35482
            calc_params['wy_fwhm'] = self.source_params['wy_fwhm'] / 2.35482

        # Расчёт
        try:
            # Передаём КОПИЮ source_params, чтобы контроллер не мог его изменить
            report = self.controller.run_calculations(
                energy, 
                structure_config, 
                source_params=calc_params  # ← безопасно
            )
        except Exception as e:
            QMessageBox.critical(self, "Calculation Error", str(e))
            import traceback
            traceback.print_exc()
            return

        self.display_results(report)

    
    '''
    def run_calculation(self):
        # 1. Считываем энергию
        try:
            energy = self.source_params['energy']
        except ValueError:
            QMessageBox.critical(self, "Error", "Invalid Energy value")
            return

        structure_config = []

        # 2. Конфиг TF1
        tf1_is_air = (self.combo_tf1_type.currentText() == "Air (Array)")
        l1_input = self.spin_l1.value()

        if tf1_is_air:
            tf1_config_data = {
                'lenses': self.tf1_air_config
            }
            """
            N = self.spin_tf1_air_N.value()
            preset = self.combo_tf1_air_R.currentText()
            lens = LensGenerator.create_lens_group(preset, N=1)  # один элемент
            tf1_length = N * lens['p'] + (N - 1) * lens['u']
            actual_start = self.spin_l1.value() - tf1_length / 2
            
            structure_config.append({
                'type': 'air',
                'start_dist': tf1_start,
                'lens_count': self.spin_tf1_air_N.value(),
                'preset': self.combo_tf1_air_R.currentText() # Передаем пресет в метод _build_air_tf
            })
            """
        else:
            tf1_config_data = {
                'groups': self.tf1_editor.get_config()
            }
        """ 
            # Vacuum (Editor)
            groups = self.tf1_editor.get_config()
            structure_config.append({
                'type': 'vacuum',
                'start_dist': tf1_start,
                'groups': groups # Передаем список словарей [{'N':.., 'preset':.., 'active':..}]
            })
        """
        #Вычисляем длину TF1
        tf1_length = self._calculate_tf_length('air' if tf1_is_air else 'vacuum', tf1_config_data)

        #Применяем "Measure to center"
        if self.chk_l1_center.isChecked():
            absolute_start = l1_input - tf1_length / 2
            #tf1_end = absolute_start + tf1_length / 2
        else:
            absolute_start = l1_input  # расстояние до первой линзы
            #tf1_end = absolute_start + tf1_length

        # Теперь передаём start_dist в structure_config
        if tf1_is_air:
            tf1_config = {
                'type': 'air',
                'tf_name': 'TF2',
                'absolute_start': absolute_start,
                'lenses': self.tf1_air_config  # ← список словарей с 'active'
            }
        else:
            tf1_config = self._build_tf_config(
                'TF1', False, absolute_start,
                vacuum_groups = self.tf1_editor.get_config()
            )
            
        structure_config.append(tf1_config)
        tf1_end = absolute_start + tf1_length


        # 3. Конфиг TF2
        if self.gb_tf2.isChecked():
            tf2_is_air = (self.combo_tf2_type.currentText() == "Air (Array)")
            l2_input = self.l2_input.value()

            if tf2_is_air:
                tf2_config_data = {
                    'lenses': self.tf2_air_config
                }
            else:
                tf2_config_data = {
                    'groups': self.tf2_editor.get_config()
                    }
                
        #Вычисляем длину TF2
        tf2_length = self._calculate_tf_length('air' if tf2_is_air else 'vacuum', tf2_config_data)

        #"Measure to center"
        if self.chk_gap_center.isChecked():
            absolute_start = l2_input - tf2_length / 2.0 if self.chk_gap_center.isChecked() else l2_input
        else:
            absolute_start = l2_input  # расстояние до первой линзы

        #gap = start_dist - tf1_end

        # Теперь передаём start_dist в structure_config
        if tf2_is_air:
            tf2_config = {
                'type': 'air',
                'tf_name': 'TF2',
                'absolute_start': absolute_start,
                'lenses': self.tf2_air_config  # ← список словарей с 'active'
            }
        else:
            tf2_config = self._build_tf_config(
                'TF2', False, absolute_start,
                vacuum_groups = self.tf2_editor.get_config()
            )

        structure_config.append(tf2_config)

        # 4. Запуск расчета через расширенный контроллер
        try:
            report = self.controller.run_calculations(energy, structure_config, source_params=self.source_params.copy())
        except Exception as e:
            QMessageBox.critical(self, "Calculation Error", str(e))
            # Для отладки можно распечатать traceback
            import traceback
            traceback.print_exc()
            return

        # 5. Вывод результатов
        #print(f"TF1 length = {tf1_length:.6f} m")
        #print(f"Start dist = {start_dist:.6f} m")
        self.display_results(report)
        #print("Defaults:", self.controller.defaults)
    '''

    def display_results(self, report):
        self._last_report = report
        if not report or "Error" in report:
            self.txt_summary.setText("No results or error occurred.")
            return

        focus_pos = report['final_pos'] + report['L2']
        # Текст
        summary = (
            f"<b>Energy:</b> {report['energy']} eV<br>"
            f"<b>Final Position:</b> {report['final_pos']:.4f} m<br>"
            f"<b>Focal Distance (L2) from last lens:</b> {report['L2']:.4f} m<br>"
            f"<b>Focus position:</b> {focus_pos:.4f} m<br>"
            f"<b>Transmission:</b> {report['T']*100:.2f} %<br>"
            f"<b>Focus Size X:</b> {report['size_x']*1e6:.2f} um<br>"
            f"<b>Focus Size Y:</b> {report['size_y']*1e6:.2f} um<br>"
            #Gain, DoF, Symmetry Size
        )
        self.txt_summary.setHtml(summary)
        history = report.get('full_history', [])
        if not history:
            self.table_res.setRowCount(0)
            return

        display_rows = []
        n = len(history)

        # Внутри цикла по history:
        for i, item in enumerate(history):
            display_rows.append(item)

            # Проверяем флаги напрямую
            is_last_in_block = getattr(item, 'is_last_in_block', False)
            is_last_in_tf = getattr(item, 'is_last_in_tf', False)

            # После последней линзы в блоке (но не последней в TF) — вставляем заголовок следующего блока
            if is_last_in_block and not is_last_in_tf and i + 1 < len(history):
                next_block_index = getattr(history[i + 1], 'block_index', None)
                if next_block_index is not None:
                    display_rows.append(f"Block {next_block_index}")

            # После последней линзы в TF — если есть следующий TF, вставляем его имя
            if is_last_in_tf and i + 1 < len(history):
                next_tf_name = getattr(history[i + 1], 'tf_name', None)
                if next_tf_name:
                    display_rows.append(next_tf_name)
        
        self.table_res.setRowCount(len(display_rows))
        for row, item in enumerate(display_rows):
            if isinstance(item, str):
                # Заголовок — только в первую колонку
                self.table_res.setItem(row, 0, QTableWidgetItem(item))
                for col in range(1, self.table_res.columnCount()):
                    self.table_res.setItem(row, col, QTableWidgetItem(""))
                font = self.table_res.item(row, 0).font()
                font.setBold(True)
                self.table_res.item(row, 0).setFont(font)
            else:
                # Обычная строка — используем current_display_fields
                for col, field in enumerate(self.current_display_fields):
                    field_name = field[0]      # name
                    formatter = field[3]       # formatter (может быть None)
                    value = getattr(item, field_name)

                    if formatter is not None:
                        text = formatter(value)
                    else:
                        # Резервный форматтер
                        text = str(value)

                    self.table_res.setItem(row, col, QTableWidgetItem(text))            

    def open_column_settings(self):
        # Все возможные поля (из LENS_RESULT_FIELDS)
        all_fields_info = [
            (field[0], field[2], field[3])  # name, header, formatter
            for field in LENS_RESULT_FIELDS
            if field[2] is not None
            ]
        
        # Текущие отображаемые поля
        current_names = [field[0] for field in self.current_display_fields] if self.current_display_fields else None
        
        dialog = ColumnSettingsDialog(self, current_names, all_fields_info)
        if dialog.exec_() == QDialog.Accepted:
            selected_names = set(dialog.get_selected_fields())
            # Только отображаемые поля
            self.current_display_fields = [
                field for field in LENS_RESULT_FIELDS
                if field[0] in selected_names and field[2] is not None
                ]
            # Обновляем таблицу
            self._update_results_table_columns()
            # Сохраняем настройки (опционально)
            #self.save_column_settings(selected_names)

    def _update_results_table_columns(self):
        if not self.current_display_fields:
            self.current_display_fields = [
                field for field in LENS_RESULT_FIELDS
                if field[2] is not None  # header != None
                ]
        
        headers = [field[2] for field in self.current_display_fields]
        self.table_res.setColumnCount(len(headers))
        self.table_res.setHorizontalHeaderLabels(headers)
        #self.table_res.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table_res.setStyleSheet("QTableWidget::item { padding: 2px 4px; }")

        header = self.table_res.horizontalHeader()
        for col, field in enumerate(self.current_display_fields):
            field_name = field[0]
            width = 100#self.COLUMN_WIDTHS.get(field_name, 100)  # 100 — значение по умолчанию
            self.table_res.setColumnWidth(col, width)
            # Важно: отключаем изменение размера пользователем (опционально)
            header.setSectionResizeMode(col, QHeaderView.Fixed)
        
        if hasattr(self, '_last_report'):
            self.display_results(self._last_report)
        ''' 
        # Если уже есть данные — обновляем отображение
        if self.table_res.rowCount() > 0:
            # Сохраняем текущие данные (например, из последнего отчёта)
            if hasattr(self, '_last_report'):
                self.display_results(self._last_report)
        '''

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = XRayCalcApp()
    window.show()
    sys.exit(app.exec_())