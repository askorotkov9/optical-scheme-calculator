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
        
        default_params = {
            'energy': 10300.0,
            'sx_fwhm': 32.84,
            'sy_fwhm': 5.9,
            'wx_fwhm': 9.4,
            'wy_fwhm': 11.0,
        }
        self.original_params = source_params if source_params is not None else default_params
        
        # Internal state — always in FWHM (um, urad)
        self._sx_fwhm = self.original_params['sx_fwhm']
        self._sy_fwhm = self.original_params['sy_fwhm']
        self._wx_fwhm = self.original_params['wx_fwhm']
        self._wy_fwhm = self.original_params['wy_fwhm']
        
        self.setup_ui()
        self.load_params()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # --- Energy ---
        gb_energy = QGroupBox("Photon Energy")
        fl_energy = QFormLayout()
        
        self.spin_energy = QDoubleSpinBox()
        self.spin_energy.setRange(1000, 1000000)
        self.spin_energy.setDecimals(0)
        self.spin_energy.setSuffix(" eV")
        fl_energy.addRow("Energy:", self.spin_energy)
        
        gb_energy.setLayout(fl_energy)
        layout.addWidget(gb_energy)

        # --- Source size ---
        gb_size = QGroupBox("Source Size")
        fl_size = QFormLayout()
        
        self.chk_use_fwhm = QCheckBox("Use FWHM (uncheck for Sigma σ)")
        fl_size.addRow("", self.chk_use_fwhm)
        
        self.spin_sx = QDoubleSpinBox()
        self.spin_sx.setRange(0.01, 1000)
        self.spin_sx.setDecimals(2)
        self.spin_sx.setSuffix(" µm")
        fl_size.addRow("Size X:", self.spin_sx)
        
        self.spin_sy =  QDoubleSpinBox()
        self.spin_sy.setRange(0.01, 1000)
        self.spin_sy.setDecimals(2)
        self.spin_sy.setSuffix(" µm")
        fl_size.addRow("Size Y:", self.spin_sy)
        
        gb_size.setLayout(fl_size)
        layout.addWidget(gb_size)

        # --- Divergence ---
        gb_div = QGroupBox("Beam Divergence")
        fl_div = QFormLayout()
        self.spin_wx = QDoubleSpinBox()
        self.spin_wx.setRange(0, float('inf'))
        self.spin_wx.setDecimals(3)
        self.spin_wx.setSuffix(" µrad")
        fl_div.addRow("Div X:", self.spin_wx)
        
        self.spin_wy = QDoubleSpinBox()
        self.spin_wy.setRange(0, float('inf'))
        self.spin_wy.setDecimals(3)
        self.spin_wy.setSuffix(" µrad")
        fl_div.addRow("Div Y:", self.spin_wy)
        gb_div.setLayout(fl_div)
        layout.addWidget(gb_div)

        """
        # --- Optical constants (for viewing only) ---
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
        """

        # --- Buttons ---
        btn_layout = QHBoxLayout()
        self.btn_reset = QPushButton("Reset")
        self.btn_ok = QPushButton("OK")
        self.btn_cancel = QPushButton("Cancel")
        
        btn_layout.addWidget(self.btn_reset)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_ok)
        btn_layout.addWidget(self.btn_cancel)
        layout.addLayout(btn_layout)

        # --- Connecting signals ---
        self.spin_sx.valueChanged.connect(self.update_internal_state)
        self.spin_sy.valueChanged.connect(self.update_internal_state)
        self.spin_wx.valueChanged.connect(self.update_internal_state)
        self.spin_wy.valueChanged.connect(self.update_internal_state)
        self.chk_use_fwhm.toggled.connect(self.on_use_fwhm_toggled)
        self.spin_energy.valueChanged.connect(self.update_optical_constants)
        self.btn_reset.clicked.connect(self.load_params)
        self.btn_ok.clicked.connect(self.accept)
        self.btn_cancel.clicked.connect(self.reject)

    def load_params(self):
        p = self.original_params
        self.spin_energy.setValue(p['energy'])
        
        # Restore internal values ​​(always FWHM)
        self._sx_fwhm = p['sx_fwhm']
        self._sy_fwhm = p['sy_fwhm']
        self._wx_fwhm = p['wx_fwhm']
        self._wy_fwhm = p['wy_fwhm']

        # Disable signals to avoid calling update_internal_state
        self.chk_use_fwhm.blockSignals(True)
        self.spin_sx.blockSignals(True)
        self.spin_sy.blockSignals(True)
        self.spin_wx.blockSignals(True)
        self.spin_wy.blockSignals(True)
        
        # Setting the state of the checkbox
        self.chk_use_fwhm.setChecked(self.use_fwhm)
        
        # Updating the display
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
        
        # Turn the signals back on
        self.chk_use_fwhm.blockSignals(False)
        self.spin_sx.blockSignals(False)
        self.spin_sy.blockSignals(False)
        self.spin_wx.blockSignals(False)
        self.spin_wy.blockSignals(False)

    def on_units_changed(self, use_fwhm):
        """Updates the display of spinboxes without changing their internal values"""
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

        if is_fwhm:
            self._sx_fwhm = sx_val
        else:
            self._sx_fwhm = sx_val * 2.35482

        self._sx_fwhm = self.spin_sx.value() * factor
        self._sy_fwhm = self.spin_sy.value() * factor
        self._wx_fwhm = self.spin_wx.value() * factor
        self._wy_fwhm = self.spin_wy.value() * factor

        #sx_fwhm = self.inp_sx.value() * factor# if is_fwhm else self.inp_sx.value() * 2.35482
        #sy_fwhm = self.inp_sy.value() * factor# if is_fwhm else self.inp_sy.value() * 2.35482
        #wx_fwhm = self.inp_wx.value() * factor# if is_fwhm else self.inp_wx.value() * 2.35482
        #wy_fwhm = self.inp_wy.value() * factor# if is_fwhm else self.inp_wy.value() * 2.3548

    def on_use_fwhm_toggled(self, checked):
        """Called when the checkbox is toggled"""
        factor = 1.0 if checked else (1/2.35482)
        
        self.spin_sx.blockSignals(True)
        self.spin_sy.blockSignals(True)
        self.spin_wx.blockSignals(True)
        self.spin_wy.blockSignals(True)

        self.spin_sx.setValue(self._sx_fwhm * factor)
        self.spin_sy.setValue(self._sy_fwhm * factor)
        self.spin_wx.setValue(self._wx_fwhm * factor)
        self.spin_wy.setValue(self._wy_fwhm * factor)

        self.spin_sx.blockSignals(False)
        self.spin_sy.blockSignals(False)
        self.spin_wx.blockSignals(False)
        self.spin_wy.blockSignals(False)