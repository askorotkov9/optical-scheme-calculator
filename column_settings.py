from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QCheckBox, 
                             QPushButton, QScrollArea, QWidget, QLabel)
from PyQt5.QtCore import Qt
from computations import LENS_RESULT_FIELDS

class ColumnSettingsDialog(QDialog):
    def __init__(self, parent=None, current_fields=None, all_fields=None):
        super().__init__(parent)
        self.setWindowTitle("Choose Columns to Display")
        self.resize(300, 400)
        
        self.all_fields = all_fields or []
        self.current_fields = current_fields or [name for name, _, _ in all_fields]
        
        self.checkboxes = []
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Инструкция
        layout.addWidget(QLabel("Select columns to display:"))

        # Прокручиваемая область для чекбоксов
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setAlignment(Qt.AlignTop)

        # Чекбоксы для каждого поля
        for name, header, _ in self.all_fields:
            cb = QCheckBox(header)
            cb.setChecked(name in self.current_fields)
            cb.field_name = name  # сохраним имя поля
            self.checkboxes.append(cb)
            scroll_layout.addWidget(cb)

        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)

        # Кнопки
        btn_layout = QHBoxLayout()
        self.btn_reset = QPushButton("Reset to Default")
        self.btn_ok = QPushButton("OK")
        self.btn_cancel = QPushButton("Cancel")
        
        btn_layout.addWidget(self.btn_reset)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_ok)
        btn_layout.addWidget(self.btn_cancel)
        layout.addLayout(btn_layout)

        # Сигналы
        self.btn_ok.clicked.connect(self.accept)
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_reset.clicked.connect(self.reset_to_default)

    def reset_to_default(self):
        # Можно задать ваши дефолтные колонки
        default_fields = {'lens_index_in_tf', 'position', 'L1', 'L2', 'F', 'sfx', 'sfy', 'T', 'M'}
        for cb in self.checkboxes:
            cb.setChecked(cb.field_name in default_fields)

    def get_selected_fields(self):
        return [cb.field_name for cb in self.checkboxes if cb.isChecked()]