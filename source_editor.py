from xraydb import xray_delta_beta, get_material
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QGroupBox, QFormLayout,
                             QDoubleSpinBox, QComboBox, QCheckBox, QPushButton,
                             QLabel, QMessageBox, QHBoxLayout, QApplication)
from PyQt5.QtCore import Qt

class SourceEditorDialog(QDialog):
    def __init__(self, parent = None, source_params = None, use_fwhm = True):
        super().__init__(parent)
        self.setWindowTitle("Source Parameters")
        self.resize(450, 350)

        self.use_fwhm = use_fwhm
        
        # Сохраняем исходные параметры (in sigma?)
        default_params = {
            'energy': 10300.0,
            'sx_fwhm': 32.84,
            'sy_fwhm': 5.9,
            'wx_fwhm': 9.4,
            'wy_fwhm': 11.0,
            #'use_fwhm': True,
            'material': 'Be'
        }
        self.original_params = source_params if source_params is not None else default_params
        
        # Внутреннее состояние — ВСЕГДА в FWHM (мкм, мкрад)
        self._sx_fwhm = self.original_params['sx_fwhm']
        self._sy_fwhm = self.original_params['sy_fwhm']
        self._wx_fwhm = self.original_params['wx_fwhm']
        self._wy_fwhm = self.original_params['wy_fwhm']
        
        self.setup_ui()
        self.load_params()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # --- Энергия и материал ---
        gb_energy = QGroupBox("Photon Energy & Material")
        fl_energy = QFormLayout()
        
        self.spin_energy = QDoubleSpinBox()
        self.spin_energy.setRange(1000, 100000)
        self.spin_energy.setDecimals(0)
        self.spin_energy.setSuffix(" eV")
        fl_energy.addRow("Energy:", self.spin_energy)
        
        self.combo_material = QComboBox()
        self.combo_material.addItems(["Be", "Al", "Si", "Ni"])
        fl_energy.addRow("Lens Material:", self.combo_material)
        
        gb_energy.setLayout(fl_energy)
        layout.addWidget(gb_energy)

        # --- Размер источника ---
        gb_size = QGroupBox("Source Size")
        fl_size = QFormLayout()
        
        self.chk_use_fwhm = QCheckBox("Use FWHM (uncheck for Sigma σ)")
        fl_size.addRow("", self.chk_use_fwhm)
        
        self.spin_sx = QDoubleSpinBox()
        self.spin_sx.setRange(0.01, 1000)
        self.spin_sx.setDecimals(2)
        self.spin_sx.setSuffix(" µm")
        fl_size.addRow("Size X:", self.spin_sx)
        
        self.spin_sy = QDoubleSpinBox()
        self.spin_sy.setRange(0.01, 1000)
        self.spin_sy.setDecimals(2)
        self.spin_sy.setSuffix(" µm")
        fl_size.addRow("Size Y:", self.spin_sy)
        
        gb_size.setLayout(fl_size)
        layout.addWidget(gb_size)

        # --- Расходимость ---
        gb_div = QGroupBox("Beam Divergence")
        fl_div = QFormLayout()
        self.spin_wx = QDoubleSpinBox()
        self.spin_wx.setRange(0.001, 100)
        self.spin_wx.setDecimals(3)
        self.spin_wx.setSuffix(" µrad")
        fl_div.addRow("Div X:", self.spin_wx)
        
        self.spin_wy = QDoubleSpinBox()
        self.spin_wy.setRange(0.001, 100)
        self.spin_wy.setDecimals(3)
        self.spin_wy.setSuffix(" µrad")
        fl_div.addRow("Div Y:", self.spin_wy)
        gb_div.setLayout(fl_div)
        layout.addWidget(gb_div)

        # --- Оптические константы (только для просмотра) ---
        gb_optical = QGroupBox("Optical Constants (from xraydb)")
        fl_optical = QFormLayout()
        self.lbl_delta = QLabel("delta: -")
        self.lbl_betta = QLabel("betta: -")
        self.lbl_mu = QLabel("mu (1/m): -")
        fl_optical.addRow(self.lbl_delta)
        fl_optical.addRow(self.lbl_betta)
        fl_optical.addRow(self.lbl_mu)
        gb_optical.setLayout(fl_optical)
        layout.addWidget(gb_optical)

        # --- Кнопки ---
        btn_layout = QHBoxLayout()
        self.btn_reset = QPushButton("Reset")
        self.btn_ok = QPushButton("OK")
        self.btn_cancel = QPushButton("Cancel")
        
        btn_layout.addWidget(self.btn_reset)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_ok)
        btn_layout.addWidget(self.btn_cancel)
        layout.addLayout(btn_layout)

        # --- Подключаем сигналы ---
        self.spin_sx.valueChanged.connect(self.update_internal_state)
        self.spin_sy.valueChanged.connect(self.update_internal_state)
        self.spin_wx.valueChanged.connect(self.update_internal_state)
        self.spin_wy.valueChanged.connect(self.update_internal_state)
        self.chk_use_fwhm.toggled.connect(self.on_use_fwhm_toggled)
        #self.chk_use_fwhm.toggled.connect(self.on_units_changed)
        self.spin_energy.valueChanged.connect(self.update_optical_constants)
        self.combo_material.currentTextChanged.connect(self.update_optical_constants)
        self.btn_reset.clicked.connect(self.load_params)
        self.btn_ok.clicked.connect(self.accept)
        self.btn_cancel.clicked.connect(self.reject)

        # Обновляем внутреннее состояние при любом изменении


        # Подключаем спинбоксы
        #self.spin_sx.valueChanged.connect(self._on_sx_changed)
        #self.spin_sy.valueChanged.connect(self._on_sy_changed)
        #self.spin_wx.valueChanged.connect(self._on_wx_changed)
        #self.spin_wy.valueChanged.connect(self._on_wy_changed)

        self.update_optical_constants()

    def load_params(self):
        print("Loading params...")
        print("original_params:", self.original_params)
        print("use_fwhm:", self.use_fwhm)

        p = self.original_params
        self.spin_energy.setValue(p['energy'])
        self.combo_material.setCurrentText(p['material'])
        
        # Восстанавливаем внутренние значения (всегда FWHM)
        self._sx_fwhm = p['sx_fwhm']
        self._sy_fwhm = p['sy_fwhm']
        self._wx_fwhm = p['wx_fwhm']
        self._wy_fwhm = p['wy_fwhm']

        # Отключаем сигналы, чтобы избежать вызова update_internal_state
        self.chk_use_fwhm.blockSignals(True)
        self.spin_sx.blockSignals(True)
        self.spin_sy.blockSignals(True)
        self.spin_wx.blockSignals(True)
        self.spin_wy.blockSignals(True)
        
        # Устанавливаем состояние чекбокса
        self.chk_use_fwhm.setChecked(self.use_fwhm)

        print('sss', self._sx_fwhm)
        
        
        # Обновляем отображение
        if self.use_fwhm:
            self.spin_sx.setValue(self._sx_fwhm)
            self.spin_sy.setValue(self._sy_fwhm)
            self.spin_wx.setValue(self._wx_fwhm)
            self.spin_wy.setValue(self._wy_fwhm)
        else:
            self.spin_sx.setValue(self._sx_fwhm / 2.35482)
            self.spin_sy.setValue(self._sy_fwhm / 2.35482)
            self.spin_wx.setValue(self._wx_fwhm / 2.35482)
            self.spin_wy.setValue(self._wy_fwhm / 2.35482)
        
        # Включаем сигналы обратно
        self.chk_use_fwhm.blockSignals(False)
        self.spin_sx.blockSignals(False)
        self.spin_sy.blockSignals(False)
        self.spin_wx.blockSignals(False)
        self.spin_wy.blockSignals(False)

        
        
        # Обновляем виджеты
        #self.on_units_changed(self.use_fwhm)#self.on_units_changed(p['use_fwhm'])

    def on_units_changed(self, use_fwhm):
        """Обновляет отображение спинбоксов без изменения внутренних значений."""
        if use_fwhm:
            self.spin_sx.setValue(self._sx_fwhm)
            self.spin_sy.setValue(self._sy_fwhm)
            self.spin_wx.setValue(self._wx_fwhm)
            self.spin_wy.setValue(self._wy_fwhm)
        else:
            FWHM_TO_SIGMA = 1.0 / 2.35482
            self.spin_sx.setValue(self._sx_fwhm * FWHM_TO_SIGMA)
            self.spin_sy.setValue(self._sy_fwhm * FWHM_TO_SIGMA)
            self.spin_wx.setValue(self._wx_fwhm * FWHM_TO_SIGMA)
            self.spin_wy.setValue(self._wy_fwhm * FWHM_TO_SIGMA)

    def update_internal_state(self):
        """Обновляет внутренние FWHM-значения на основе текущего UI."""
        is_fwhm = self.chk_use_fwhm.isChecked()
        factor = 1.0 if is_fwhm else 2.35482
    
        sx_val = self.spin_sx.value()
        print(f"update_internal_state: is_fwhm={is_fwhm}, spin_sx={sx_val}")
        if is_fwhm:
            self._sx_fwhm = sx_val
        else:
            self._sx_fwhm = sx_val * 2.35482
        print(f"  -> _sx_fwhm = {self._sx_fwhm}")

        self._sx_fwhm = self.spin_sx.value() * factor
        self._sy_fwhm = self.spin_sy.value() * factor
        self._wx_fwhm = self.spin_wx.value() * factor
        self._wy_fwhm = self.spin_wy.value() * factor

        sx_fwhm = self.inp_sx.value() * factor# if is_fwhm else self.inp_sx.value() * 2.35482
        sy_fwhm = self.inp_sy.value() * factor# if is_fwhm else self.inp_sy.value() * 2.35482
        wx_fwhm = self.inp_wx.value() * factor# if is_fwhm else self.inp_wx.value() * 2.35482
        wy_fwhm = self.inp_wy.value() * factor# if is_fwhm else self.inp_wy.value() * 2.3548

    def on_use_fwhm_toggled(self, checked):
        """Вызывается при переключении чекбокса."""
        # 1. Зафиксируем текущие значения как FWHM
        print(f"on_use_fwhm_toggled: checked={checked}")
        #self.update_internal_state()
        # 2. Переключим отображение
        factor = 1.0 if checked else (1/2.35482)
        
        self.spin_sx.blockSignals(True)
        self.spin_sy.blockSignals(True)
        self.spin_wx.blockSignals(True)
        self.spin_wy.blockSignals(True)

        self.spin_sx.setValue(self._sx_fwhm * factor)
        #self.spin_sx.value(self._sx_fwhm * factor)
        self.spin_sy.setValue(self._sy_fwhm * factor)
        self.spin_wx.setValue(self._wx_fwhm * factor)
        self.spin_wy.setValue(self._wy_fwhm * factor)

        self.spin_sx.blockSignals(False)
        self.spin_sy.blockSignals(False)
        self.spin_wx.blockSignals(False)
        self.spin_wy.blockSignals(False)



    '''
    def _on_sx_changed(self, value):
        if self.chk_use_fwhm.isChecked():
            self._sx_fwhm = value
        else:
            self._sx_fwhm = value * 2.35482

    def _on_sy_changed(self, value):
        if self.chk_use_fwhm.isChecked():
            self._sy_fwhm = value
        else:
            self._sy_fwhm = value * 2.35482

    def _on_wx_changed(self, value):
        if self.chk_use_fwhm.isChecked():
            self._wx_fwhm = value
        else:
            self._wx_fwhm = value * 2.35482

    def _on_wy_changed(self, value):
        if self.chk_use_fwhm.isChecked():
            self._wy_fwhm = value
        else:
            self._wy_fwhm = value * 2.35482

    def on_use_fwhm_changed(self):
        is_fwhm = self.chk_use_fwhm.isChecked()
        factor = 1.0 if is_fwhm else (1.0 / 2.35482)

        # Сохраняем текущие "сырые" значения (всегда FWHM)
        sx_fwhm = self.inp_sx.value() * factor# if is_fwhm else self.inp_sx.value() * 2.35482
        sy_fwhm = self.inp_sy.value() * factor# if is_fwhm else self.inp_sy.value() * 2.35482
        wx_fwhm = self.inp_wx.value() * factor# if is_fwhm else self.inp_wx.value() * 2.35482
        wy_fwhm = self.inp_wy.value() * factor# if is_fwhm else self.inp_wy.value() * 2.35482

        # Отображаем в нужном режиме
        self.inp_sx.setValue(sx_fwhm)
        self.inp_sy.setValue(sy_fwhm)
        self.inp_wx.setValue(wx_fwhm)
        self.inp_wy.setValue(wy_fwhm)
    '''


    def update_optical_constants(self):
        try:
            energy_ev = self.spin_energy.value()
            material = self.combo_material.currentText()

            mat_obj = get_material(material)
            if mat_obj is not None and hasattr(mat_obj, 'density'):
                density = mat_obj.density
            else:
                fallback = {"Be": 1.848, "Al": 2.7, "Si": 2.33, "Ni": 8.9}
                density = fallback.get(material, 1.848)

            delta, beta, atlen_cm = xray_delta_beta(material, density, energy_ev)
            atlen_m = atlen_cm * 0.01
            mu_inv_m = 1.0 / atlen_m

            self.lbl_delta.setText(f"delta: {delta:.2e}")
            self.lbl_betta.setText(f"betta: {beta:.2e}")
            self.lbl_mu.setText(f"mu (1/m): {mu_inv_m:.2e}")

        except Exception as e:
            print(f"Error in update_optical_constants: {e}")
            self.lbl_delta.setText("delta: Error")
            self.lbl_betta.setText("betta: Error")
            self.lbl_mu.setText("mu: Error")
    '''
    def get_params(self):
        use_fwhm = self.chk_use_fwhm.isChecked()
        if use_fwhm:
            # Пользователь видит FWHM → значение и есть FWHM
            sx = self.spin_sx.value()
            sy = self.spin_sy.value()
            wx = self.spin_wx.value()
            wy = self.spin_wy.value()
        else:
            # Пользователь видит σ → чтобы получить FWHM, умножаем
            sx = self.spin_sx.value() / 2.35482
            sy = self.spin_sy.value() / 2.35482
            wx = self.spin_wx.value() / 2.35482
            wy = self.spin_wy.value() / 2.35482
        """Возвращает параметры ВСЕГДА в FWHM (мкм, мкрад)."""
        return {
            'energy': self.spin_energy.value(),
            'sx_fwhm': sx,
            'sy_fwhm': sy,
            'wx_fwhm': wx,
            'wy_fwhm': wy,
            #'use_fwhm': use_fwhm,
            'material': self.combo_material.currentText()
        }
    '''
    def get_params(self):
        """Возвращает параметры ВСЕГДА в FWHM."""
        return {
            'energy': self.spin_energy.value(),
            'sx_fwhm': self._sx_fwhm,
            'sy_fwhm': self._sy_fwhm,
            'wx_fwhm': self._wx_fwhm,
            'wy_fwhm': self._wy_fwhm,
            'material': self.combo_material.currentText()
        }
    
    def get_use_fwhm(self):
        return self.chk_use_fwhm.isChecked()