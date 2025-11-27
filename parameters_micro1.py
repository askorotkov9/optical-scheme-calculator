#_________________
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
    def __init__(self, energy = 10300):
        #Базовые параметры пучка
        self.sx_base = 32.9E-6 #сдлеать возможность выбора в чём считать: в FWHM или sigma. Также в статье с формулами
        self.sy_base = 5.9E-6
        self.wx_base = 9.4E-6*2.35482 #15 гармоника
        self.wy_base = 11.0E-6*2.35482 #15 гармоника
        self.fwhm_conv = 2.35482
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

        self.set_energy(energy)

    def set_energy(self, energy):
        """Обновляет физические параметры при смене энергии."""
        self.E = energy
        self.lamda = (12398.4 / self.E) * 1e-10

        #Здесь логика выбора оптических констант.
        #В будущем сюда подключить xraylib.calc_delta(Z, E)

        if 10000 <= self.E < 20000:
            ref = MATERIAL_DATA_BE['10300']
        else:
            ref = MATERIAL_DATA_BE['30900']

        self.delta = ref['delta']
        self.betta = ref['betta']
        self.mu = ref['mu']

    def get_params_dict(self):
        """Возвращает словарь, совместимый со старым кодом"""
        return {
            'sx': self.sx_base * self.fwhm_conv,
            'sy': self.sy_base * self.fwhm_conv,
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


# --- 3. Инициализация по умолчанию (для совместимости) ---

# Создаем глобальный объект источника
current_source = SourceManager(energy=30900) #?? через 

# Вместо 10 одинаковых словарей tf1_1...tf1_10, мы можем создавать их на лету.

#Подумать над этим блоком
def calculate_layout(tf1_config, tf2_config):
    """Рассчитывает геометрию системы на основе конфигов линз."""
    tf1_len = tf1_config['p'] * tf1_config['N'] + tf1_config['u'] * (tf1_config['N'] - 1) #0.244, u = 0.008
    tf2_len = tf2_config['p'] * tf2_config['N'] + tf2_config['u'] * (tf2_config['N'] - 1) #0.27, u = 0.01, Оба на 60 линз всего, блоков 14
    
    init_L1 = 27 - tf1_len / 2 #изменить 27 на input_L1, сделать switch на отсчёт от первой линзы, либо середины tf
    # И так далее...
    return init_L1, tf1_len, tf2_len



# Но если тебе нужно сохранить структуру для старого кода:

tf1_template = LensGenerator.create_lens_group('R500', N=1, source_manager=current_source)

# Пример создания tf2
tf2 = LensGenerator.create_lens_group(
    'R50', 
    N=63, 
    u=400e-6, 
    source_manager=current_source
)




'''
tf1_length = (init_tf['p'] * init_tf['N'] + init_tf['u'] * (init_tf['N'] - 1))
tf2_length = tf2['p'] * tf2['N'] + tf2['u'] * (tf2['N'] - 1)
initial_L1 = 27 - tf1_length/2 # по середину TF1
#print(initial_L1)
L_between = 37 - (tf1_length)/2 - tf2_length/2 + init_tf['p'] #(tf2['p'] * tf2['N'] + tf2['u'] * (tf2['N'] - 1))/2
'''