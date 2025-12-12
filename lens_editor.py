from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, 
                             QTableWidgetItem, QPushButton, QComboBox, QCheckBox, 
                             QLabel, QHeaderView, QMessageBox, QWidget, QSpinBox)
from PyQt5.QtCore import Qt
from xraydb import xray_delta_beta, get_material
from parameters_micro1 import LENS_PRESETS

MATERIALS = ['Be', 'Al', 'Si', "Ni"]

class TFEditorDialog(QDialog):
    def __init__(self, parent=None, tf_type='air', config=None, title="Edit TF", energy = 10300):
        super().__init__(parent)
        self.tf_type = tf_type
        self.setWindowTitle(title)
        self.resize(600, 400)
        
        self.config = config or self._default_config()
        self.energy = energy
        self.setup_ui()
        self.load_data()



    def _default_config(self):
        if self.tf_type == 'air':
            return [{'preset': 'R50', 'active': True} for _ in range(10)]
        else:  # vacuum
            return [{'preset': 'R500', 'N': 1, 'active': True} for _ in range(3)]

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Таблица
        self.table = QTableWidget()
        layout.addWidget(self.table)

        # Кнопки
        btn_layout = QHBoxLayout()
        self.btn_ok = QPushButton("OK")
        self.btn_cancel = QPushButton("Cancel")
        self.btn_details = QPushButton("Edit Lens Details...")  # Только для vacuum
        self.btn_details.setVisible(self.tf_type == 'vacuum')

        # Кнопки Add/Remove Group (только для Vacuum)
        self.btn_add_group = QPushButton("Add Group")
        self.btn_remove_group = QPushButton("Remove Last")
        if self.tf_type == 'vacuum':
            btn_layout.addWidget(self.btn_add_group)
            btn_layout.addWidget(self.btn_remove_group)

        btn_layout.addWidget(self.btn_details)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_ok)
        btn_layout.addWidget(self.btn_cancel)
        layout.addLayout(btn_layout)

        self.btn_ok.clicked.connect(self.accept)
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_details.clicked.connect(self.open_lens_details)
        if self.tf_type == 'vacuum':
            self.btn_add_group.clicked.connect(self.add_vacuum_group)
            self.btn_remove_group.clicked.connect(self.remove_vacuum_group)

        self.setup_table_headers()

    def setup_table_headers(self):
        if self.tf_type == 'air':
            self.table.setColumnCount(4)
            self.table.setHorizontalHeaderLabels(["Preset", "In Beam", "Position", "Material"])
        else:  # vacuum
            self.table.setColumnCount(4)
            self.table.setHorizontalHeaderLabels(["N Lenses", "Preset", "In Beam", "Block Length (mm)"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

    def load_data(self):
        self.table.setRowCount(len(self.config))
        for row, item in enumerate(self.config):
            if self.tf_type == 'air':
                self._load_air_row(row, item)
            else:
                self._load_vacuum_row(row, item)
    
    def update_optical_constants_for_row(self, row, material, energy):

        mat_obj = get_material(material)
        if mat_obj is not None and hasattr(mat_obj, 'density'):
            density = mat_obj.density
        else:
            fallback = {"Be": 1.848, "Al": 2.7, "Si": 2.33, "Ni": 8.9}
            density = fallback.get(material, 1.848)

        try:
            delta, betta, atlen = xray_delta_beta(material, density, energy)
            mu = 1.0 / (atlen * 1e-2)
        except:
            delta, betta, mu = 0, 0, 0

        # Найдём QLabel в строке и обновим
        delta_lbl = self.table.cellWidget(row, 4)
        betta_lbl = self.table.cellWidget(row, 5)
        mu_lbl = self.table.cellWidget(row, 6)

        if delta_lbl:
            delta_lbl.setText(f"{delta:.2e}")
        if betta_lbl:
            betta_lbl.setText(f"{betta:.2e}")
        if mu_lbl:
            mu_lbl.setText(f"{mu:.2e}")

    def _load_air_row(self, row, lens):
        # Preset
        cb = QComboBox()
        cb.addItems(LENS_PRESETS.keys())
        cb.setCurrentText(lens['preset'])
        self.table.setCellWidget(row, 0, cb)

        # Active
        chk = QCheckBox()
        chk.setChecked(lens['active'])
        container = QWidget()
        lay = QHBoxLayout(container)
        lay.addWidget(chk)
        lay.setAlignment(Qt.AlignCenter)
        lay.setContentsMargins(0,0,0,0)
        container.chk = chk
        self.table.setCellWidget(row, 1, container)

        # Position (read-only)
        pos_item = QTableWidgetItem(f"{row * 1.4:.1f} mm")
        pos_item.setFlags(pos_item.flags() & ~Qt.ItemIsEditable)
        self.table.setItem(row, 2, pos_item)

        # Material
        mat_combo = QComboBox()
        mat_combo.addItems(MATERIALS)
        mat_combo.setCurrentText(lens.get('material', LENS_PRESETS[lens['preset']]['material']))  # по умолчанию из пресета
        self.table.setCellWidget(row, 3, mat_combo)

        # Добавим метки для оптических констант
        delta_lbl = QLabel("-")
        betta_lbl = QLabel("-")
        mu_lbl = QLabel("-")
        self.update_optical_constants_for_row(row, mat_combo.currentText(), self.energy)
        #self.table.setCellWidget(row, 4, delta_lbl)
        #self.table.setCellWidget(row, 5, betta_lbl)
        #self.table.setCellWidget(row, 6, mu_lbl)

        # Подключим обновление при смене материала
        mat_combo.currentTextChanged.connect(lambda mat, r=row: self.update_optical_constants_for_row(r, mat, self.energy))

    def _load_vacuum_row(self, row, block):
        # N lenses
        sb = QSpinBox()
        sb.setRange(1, 10)
        sb.setValue(block['N'])
        sb.valueChanged.connect(lambda n, r=row: self.on_block_n_changed(r, n))
        self.table.setCellWidget(row, 0, sb)

        # Preset
        cb = QComboBox()
        cb.addItems(LENS_PRESETS.keys())
        cb.setCurrentText(block['preset'])
        self.table.setCellWidget(row, 1, cb)

        # Active
        chk = QCheckBox()
        chk.setChecked(block['active'])
        container = QWidget()
        lay = QHBoxLayout(container)
        lay.addWidget(chk)
        lay.setAlignment(Qt.AlignCenter)
        lay.setContentsMargins(0,0,0,0)
        container.chk = chk
        self.table.setCellWidget(row, 2, container)

        # Block length = 10 mm (fixed)
        len_item = QTableWidgetItem("10.0")
        len_item.setFlags(len_item.flags() & ~Qt.ItemIsEditable)
        self.table.setItem(row, 3, len_item)

    def add_vacuum_group(self):
        row = self.table.rowCount()
        self.table.insertRow(row)

        # N lenses
        sb = QSpinBox()
        sb.setRange(1, 10)
        sb.setValue(1)
        sb.valueChanged.connect(lambda n, r=row: self.on_block_n_changed(r, n))
        self.table.setCellWidget(row, 0, sb)

        # Preset
        cb = QComboBox()
        cb.addItems(LENS_PRESETS.keys())
        cb.setCurrentText('R500')
        self.table.setCellWidget(row, 1, cb)

        # Active
        chk = QCheckBox()
        chk.setChecked(True)
        container = QWidget()
        lay = QHBoxLayout(container)
        lay.addWidget(chk)
        lay.setAlignment(Qt.AlignCenter)
        lay.setContentsMargins(0,0,0,0)
        container.chk = chk
        self.table.setCellWidget(row, 2, container)

        # Block length = 10 mm (fixed)
        len_item = QTableWidgetItem("10.0")
        len_item.setFlags(len_item.flags() & ~Qt.ItemIsEditable)
        self.table.setItem(row, 3, len_item)

        # Добавляем в config
        self.config.append({
            'N': 1,
            'preset': 'R500',
            'active': True,
            'lenses': [{'preset': 'R500', 'active': True, 'material': LENS_PRESETS['R500']['material']} for _ in range(1)]
        })

    def remove_vacuum_group(self):
        row = self.table.rowCount()
        if row > 0:
            self.table.removeRow(row - 1)
            if len(self.config) >= row:
                self.config.pop(row - 1)  # удаляем последний элемент
            #self.config.pop()  # удаляем последний элемент

    def on_block_n_changed(self, row, n):
        # Обновляем внутреннюю структуру block['lenses']
        block = self.config[row]
        
        if 'lenses' not in block or block['lenses'] is None:
            # Инициализируем lenses, если его нет
            preset = block['preset']
            active = block.get('active', True)
            material = block.get('material', LENS_PRESETS[preset]['material'])
            block['lenses'] = [
                {'preset': preset, 'active': active, 'material': material}
                for _ in range(n)
            ]
        else:
            current = block['lenses']
            if n > len(current):
                # Добавляем новые линзы с теми же параметрами, что и у блока
                preset = block['preset']
                active = block.get('active', True)
                material = block.get('material', LENS_PRESETS[preset]['material'])
                current.extend([
                    {'preset': preset, 'active': active, 'material': material}
                    for _ in range(n - len(current))
                ])
            elif n < len(current):
                current = current[:n]
                block['lenses'] = current

    def open_lens_details(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Select Block", "Please select a block first.")
            return

        block = self.config[row]
        if 'lenses' not in block or block['lenses'] is None:
            # Инициализируем, если ещё не было
            block['lenses'] = [
                {'preset': block['preset'], 
                 'active': block.get('active', True), 
                 'material': block.get('material', LENS_PRESETS[block['preset']]['material'])}

                for _ in range(block['N'])
            ]

        dialog = LensDetailDialog(self, block['lenses'], block_length_mm=10.0, energy = self.energy)
        if dialog.exec_() == QDialog.Accepted:
            self.config[row]['lenses'] = dialog.get_lenses()

    def get_config(self):
        """Возвращает обновлённую конфигурацию"""
        result = []
        for row in range(self.table.rowCount()):
            if self.tf_type == 'air':
                cb = self.table.cellWidget(row, 0)
                chk_container = self.table.cellWidget(row, 1)
                mat_combo = self.table.cellWidget(row, 3)

                result.append({
                    'preset': cb.currentText(),
                    'material': mat_combo.currentText(),
                    'active': chk_container.chk.isChecked()
                })
            else:
                sb = self.table.cellWidget(row, 0)
                cb = self.table.cellWidget(row, 1)
                chk_container = self.table.cellWidget(row, 2)
                #mat_combo = self.table.cellWidget(row, 3)

                # Обновляем config[row] напрямую
                n = sb.value()
                preset = cb.currentText()
                active = chk_container.chk.isChecked()
                #material = mat_combo.currentText() if mat_combo else 'Be'

                # Обновляем внутреннюю структуру
                if row < len(self.config):
                    self.config[row]['N'] = n
                    self.config[row]['preset'] = preset
                    self.config[row]['active'] = active
                    #self.config[row]['material'] = material
                else:
                    self.config.append({'N': n, 'preset': preset, 'active': active})

                lenses = self.config[row].get('lenses', None)

                result.append({
                    'N': sb.value(),
                    'preset': cb.currentText(),
                    #'material': material,
                    'active': chk_container.chk.isChecked(),
                    'lenses': lenses
                })
        return result

class LensDetailDialog(QDialog):
    def __init__(self, parent=None, lenses=None, block_length_mm=10.0, material = 'Be', energy = 10300.0):
        super().__init__(parent)
        self.lenses = lenses or []
        self.energy = energy
        self.block_length = block_length_mm
        self.setWindowTitle("Edit Lenses in Block")
        self.resize(700, 300)
        self.setup_ui()
        self.load_lenses()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        self.table = QTableWidget()
        layout.addWidget(self.table)

        btns = QHBoxLayout()
        btns.addStretch()
        btn_ok = QPushButton("OK")
        btn_cancel = QPushButton("Cancel")
        btn_ok.clicked.connect(self.accept)
        btn_cancel.clicked.connect(self.reject)
        btns.addWidget(btn_ok)
        btns.addWidget(btn_cancel)
        layout.addLayout(btns)

        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Preset", "In Beam", "Material", "Wall thickness from Left/Right (mm)"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

    def load_lenses(self):
        n = len(self.lenses)
        if n == 0:
            return

        block_length = self.block_length  # 10.0 мм
        p = 1.0  # 1 мм на линзу (должно браться из defaults, но для GUI в мм)

        if n * p > block_length:
            return
        
        free_space = block_length - n * p
        offset_left = free_space / 2.0

        spacing = self.block_length / (n + 1)  # 10mm / (N+1)
        self.table.setRowCount(n)

        for i, lens in enumerate(self.lenses):
            # Preset
            cb = QComboBox()
            cb.addItems(LENS_PRESETS.keys())
            cb.setCurrentText(lens['preset'])
            self.table.setCellWidget(i, 0, cb)

            # Active
            chk = QCheckBox()
            chk.setChecked(lens['active'])
            container = QWidget()
            lay = QHBoxLayout(container)
            lay.addWidget(chk)
            lay.setAlignment(Qt.AlignCenter)
            lay.setContentsMargins(0,0,0,0)
            container.chk = chk
            self.table.setCellWidget(i, 1, container)

            # Material
            mat_combo = QComboBox()
            mat_combo.addItems(MATERIALS)
            mat_combo.setCurrentText(lens.get('material', 'Be'))
            self.table.setCellWidget(i, 2, mat_combo)  # колонка 2
            #self.update_optical_constants_for_row(i, mat_combo.currentText(), self.energy)

            # Position from left
            from_left = spacing * (i + 1)
            from_right = self.block_length - from_left
            pos_item = QTableWidgetItem(f"{from_left:.2f} / {from_right:.2f}")
            pos_item.setFlags(pos_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(i, 3, pos_item)

            mat_combo.currentTextChanged.connect(
                lambda mat, row = i: self.update_optical_constants_for_row(row, mat, self.energy)
            )

            # Make position read-only
            #for col in [3, 4]:
            #    item = self.table.item(i, col)
            #    item.setFlags(item.flags() & ~Qt.ItemIsEditable)

    def update_optical_constants_for_row(self, row, material, energy):
        mat_obj = get_material(material)
        if mat_obj is not None and hasattr(mat_obj, 'density'):
            density = mat_obj.density
        else:
            fallback = {"Be": 1.848, "Al": 2.7, "Si": 2.33, "Ni": 8.9}
            density = fallback.get(material, 1.848)

        try:
            delta, betta, atlen = xray_delta_beta(material, density, energy)
            mu = 1.0 / (atlen * 1e-2)
        except:
            delta, betta, mu = 0, 0, 0

        # Найдём QLabel в строке и обновим
        delta_lbl = self.table.cellWidget(row, 3)
        betta_lbl = self.table.cellWidget(row, 4)
        mu_lbl = self.table.cellWidget(row, 5)

        if delta_lbl:
            delta_lbl.setText(f"{delta:.2e}")
        if betta_lbl:
            betta_lbl.setText(f"{betta:.2e}")
        if mu_lbl:
            mu_lbl.setText(f"{mu:.2e}")

    def get_lenses(self):
        result = []
        for i in range(self.table.rowCount()):
            cb = self.table.cellWidget(i, 0)
            chk_container = self.table.cellWidget(i, 1)
            mat_combo = self.table.cellWidget(i, 2)
            result.append({
                'preset': cb.currentText(),
                'active': chk_container.chk.isChecked(),
                'material': mat_combo.currentText() if mat_combo else 'Be'
            })
        return result