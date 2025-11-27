from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, 
                             QTableWidgetItem, QPushButton, QComboBox, QCheckBox, 
                             QLabel, QHeaderView, QMessageBox, QWidget, QSpinBox)
from PyQt5.QtCore import Qt
from parameters_micro1 import LENS_PRESETS

class TFEditorDialog(QDialog):
    def __init__(self, parent=None, tf_type='air', config=None, title="Edit TF"):
        super().__init__(parent)
        self.tf_type = tf_type
        self.setWindowTitle(title)
        self.resize(600, 400)
        
        self.config = config or self._default_config()
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

        btn_layout.addWidget(self.btn_details)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_ok)
        btn_layout.addWidget(self.btn_cancel)
        layout.addLayout(btn_layout)

        self.btn_ok.clicked.connect(self.accept)
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_details.clicked.connect(self.open_lens_details)

        self.setup_table_headers()

    def setup_table_headers(self):
        if self.tf_type == 'air':
            self.table.setColumnCount(3)
            self.table.setHorizontalHeaderLabels(["Preset", "In Beam", "Position"])
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
        self.table.setCellWidget(row, 2, container)

        # Position (read-only)
        pos_item = QTableWidgetItem(f"{row * 1.4:.1f} mm")  # пример
        pos_item.setFlags(pos_item.flags() & ~Qt.ItemIsEditable)
        self.table.setItem(row, 2, pos_item)

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

    def on_block_n_changed(self, row, n):
        # Обновляем внутреннюю структуру block['lenses']
        if 'lenses' not in self.config[row]:
            preset = self.config[row]['preset']
            active = self.config[row]['active']
            self.config[row]['lenses'] = [
                {'preset': preset, 'active': active} for _ in range(n)
            ]
        else:
            # Увеличиваем/уменьшаем список линз
            current = self.config[row]['lenses']
            if n > len(current):
                # Добавляем новые линзы с теми же параметрами, что и у блока
                preset = self.config[row]['preset']
                active = self.config[row]['active']
                current.extend(
                    {'preset': preset, 'active': active} 
                    for _ in range(n - len(current))
                )
            elif n < len(current):
                current = current[:n]
            self.config[row]['lenses'] = current

    def open_lens_details(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Select Block", "Please select a block first.")
            return

        block = self.config[row]
        if 'lenses' not in block:
            # Инициализируем, если ещё не было
            block['lenses'] = [
                {'preset': block['preset'], 'active': block['active']}
                for _ in range(block['N'])
            ]

        dialog = LensDetailDialog(self, block['lenses'], block_length_mm=10.0)
        if dialog.exec_() == QDialog.Accepted:
            self.config[row]['lenses'] = dialog.get_lenses()

    def get_config(self):
        """Возвращает обновлённую конфигурацию"""
        result = []
        for row in range(self.table.rowCount()):
            if self.tf_type == 'air':
                cb = self.table.cellWidget(row, 0)
                chk_container = self.table.cellWidget(row, 1)
                result.append({
                    'preset': cb.currentText(),
                    'active': chk_container.chk.isChecked()
                })
            else:
                sb = self.table.cellWidget(row, 0)
                cb = self.table.cellWidget(row, 1)
                chk_container = self.table.cellWidget(row, 2)
                result.append({
                    'N': sb.value(),
                    'preset': cb.currentText(),
                    'active': chk_container.chk.isChecked(),
                    'lenses': self.config[row].get('lenses', None)  # может быть None
                })
        return result
    
class LensDetailDialog(QDialog):
    def __init__(self, parent=None, lenses=None, block_length_mm=10.0):
        super().__init__(parent)
        self.lenses = lenses or []
        self.block_length = block_length_mm
        self.setWindowTitle("Edit Lenses in Block")
        self.resize(500, 300)
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
        self.table.setHorizontalHeaderLabels(["Preset", "In Beam", "From Left (mm)", "From Right (mm)"])
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

            # Position from left
            from_left = spacing * (i + 1)
            from_right = self.block_length - from_left
            self.table.setItem(i, 2, QTableWidgetItem(f"{from_left:.2f}"))
            self.table.setItem(i, 3, QTableWidgetItem(f"{from_right:.2f}"))

            # Make position read-only
            for col in [2, 3]:
                item = self.table.item(i, col)
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)

    def get_lenses(self):
        result = []
        for i in range(self.table.rowCount()):
            cb = self.table.cellWidget(i, 0)
            chk_container = self.table.cellWidget(i, 1)
            result.append({
                'preset': cb.currentText(),
                'active': chk_container.chk.isChecked()
            })
        return result