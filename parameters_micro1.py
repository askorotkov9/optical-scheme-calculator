from xraydb import xray_delta_beta, get_material


#Параметры линз
LENS_PRESETS = {
    'R50': {'R': 50E-6, 'A': 440E-6},
    'R100': {'R': 100E-6, 'A': 600E-6},
    'R200': {'R': 200E-6, 'A': 800E-6},
    'R500': {'R': 500E-6, 'A': 1400E-6},
}

# Данные по материалу (Бериллий) для интерполяции или выбора
# В идеале здесь должна быть библиотека (xraylib), но пока оставим твои табличные данные
MATERIAL_DATA_BE = {
    '10300': {
        'delta': 3.2067436008938E-6, # Примерные значения из твоего кода
        'betta': 7.0311452433564E-10,
        'mu': 1/8756.72906865E-6
    },
    '30900': {
        'delta': 3.5573889045265E-07,
        'betta': 5.9022238720663E-12,
        'mu': 1/30673.69471476385627E-6
    }
}

#Динамические классы

class SourceManager:
    """Управляет параметрами источника и пересчётом энергии"""
    def __init__(self, energy = 10300, sx_fwhm = 32.84*2.35482, sy_fwhm = 5.9*2.35482, wx_fwhm = 9.4*2.35482, wy_fwhm = 11.0*2.35482, material = 'Be'):
        ''' 
        Базовые параметры пучка, размеры на входе в мкм, хранение в м
        '''
        self.sx_base = sx_fwhm * 1e-6# / 2.35482 # FWHM → метры
        self.sy_base = sy_fwhm * 1e-6# / 2.35482
        self.wx_base = wx_fwhm * 1e-6# / 2.35482  # мкрад → радианы
        self.wy_base = wy_fwhm * 1e-6# / 2.35482
        self.material = material
        self.fwhm_conv = 2.35482
        self.set_energy(energy)

        ''' 
        #5 гармоника
        E = 10300
        delta = 3.2067436008938E-6
        betta = 7.0311452433564E-10
        mu = 1/8756.72906865E-6
        w0x= 9.4E-6*2.35482
        w0y= 11.0E-6*2.35482

        #15 гармоника
        E = 30900
        delta = 3.5606138234135E-7
        betta = 5.9177017660069E-12
        mu = 1/30667.662209E-6
        w0x= 5E-6*2.35482
        w0y= 10.0E-6*2.35482
        '''

    def set_energy(self, energy):
        """Обновляет физические параметры при смене энергии."""
        self.E = energy
        self.lamda = (12398.4 / self.E) * 1e-10

        mat_obj = get_material(self.material)
        if mat_obj is not None and hasattr(mat_obj, 'density'):
            density = mat_obj.density
        else:
            # fallback плотности для Be, Al и т.д.
            fallback = {"Be": 1.848, "Al": 2.7, "Si": 2.33, "Ni": 8.9}
            density = fallback.get(self.material, 1.848)

        result = xray_delta_beta(self.material, density, self.E)
        self.delta, self.betta, self.atlen = result[0], result[1], result[2]
        result = xray_delta_beta(self.material, density, self.E)

        self.mu = 1.0 / (self.atlen * 1e-2)


    def get_params_dict(self):
        """Возвращает словарь, совместимый со старым кодом"""
        return {
            'sx': self.sx_base,
            'sy': self.sy_base,
            'w0x': self.wx_base,
            'w0y': self.wy_base,
            'E': self.E,
            'lamda': self.lamda
        }
    

class LensGenerator:
    """Генератор конфигураций линз"""

    @staticmethod
    def create_lens_group(preset_name, N, p = 1e-3, u = 0, source_manager = None):
        """
        Создает словарь параметров для группы линз.
        
        Args:
            preset_name (str): Ключ из LENS_PRESETS ('R500', 'R50')
            N (int): Количество линз
            p (float): Шаг (pitch)
            u (float): Зазор
            source_manager (SourceManager): Объект источника для получения delta/mu
        """
        base = LENS_PRESETS.get(preset_name, LENS_PRESETS['R500'])

        #Собираем словарь
        lens_config = {
            'R': base['R'],
            'A': base['A'],
            'p': p,
            'u': u,
            'N': N,
            'd': 30E-6 #толщина перемычки
        }

        #Если передан менеджер (?) источника, добавляем оптические свойства
        if source_manager:
            lens_config.update({
                'delta': source_manager.delta,
                'betta': source_manager.betta,
                'mu': source_manager.mu
            })

        return lens_config