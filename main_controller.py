#сделать Initial_L1 с выбором установки по первой линзе, либо на середину (lens 1 pos = L1 - tf['length']/2)
#Выводь инфу о трансфокаторах над ними, по дефолту везде R500 стоят

#_______________

#def tf_vacuum_create(R = R500['R'], A = R500['A'], ):
'''
    R = 
    if tf_vacuum_block_type == 'vacuum':
        tf_vacuum_1 = lens_data_init(init_set = tf_vacuum['block 1'], pos = initial_L1, R = R500['R'], A = R500['A'], p = p, u = tf_vacuum['block 1']['u']) #Переделать R, A на input с приложения; tf_vaccum_block_type
        tf_vacuum_2 = lens_data_init(init_set = tf_vacuum['block 2'], pos = tf_vacuum_1[list(tf_vacuum_1)[-1]]['position'] + tf_vacuum[] + 0.001, R = R500['R'], A = R500['A'], p = p, u = tf_vacuum['block 2']['u'])
        tf_vacuum_3 = lens_data_init(init_set = tf_vacuum['block 3'], pos = tf_vacuum_2[list(tf_vacuum_2)[-1]]['position'] + tf_vacuum[] + 0.001, R = R500['R'], A = R500['A'], p = p, u = tf_vacuum['block 2']['u'])
        tf_vacuum_4 = lens_data_init(init_set = tf_vacuum['block 4'], pos = tf_vacuum_2[list(tf_vacuum_2)[-1]]['position'] + tf_vacuum[] + 0.001, R = R500['R'], A = R500['A'], p = p, u = tf_vacuum['block 2']['u'])
    return tf_vacuum_data_init
'''



#___________________________________________________________________________________________________________

import json
import math
from computations import Calculator, Formulas
from parameters_micro1 import SourceManager, LensGenerator
#Destop (для компа на SL) и веб-версия калькулятора, tkinter/PyQt5/PyQt6


class AdvancedController:
    """
    Расширенная версия контроллера, которая умеет читать 
    детальные настройки групп (пресеты, in_beam) из GUI.
    """

    def __init__(self):#, source_params, initial_scheme_params):
        """В PyQt5 эти значения будут приходить из полей ввода"""
        self.defaults = {
            'p': 1e-3,
            'd': 30e-6,
            'u_vac': 0,
            'u_air': 400e-6,
            #'gap_between_tfs': 36 #вынести в настройки ui
            'inter_block_gap': 1e-3
        }
        self.results = [] #Список вычисленных параметров по каждой линзе
        self.final_state = None #Конечное состояние пучка

        self.input_L1 = 27.1

    
    def _build_vacuum_tf(self, source_mgr, groups_data, first_dist, tf_name = "Vacuum"):
        """
        Метод сборки вакуумного TF.
        """
        chain = []
        active_groups = [g for g in groups_data if g['active']]
        total_active = len(active_groups)
        group_counter = 0
        current_block_start = first_dist  # абсолютная позиция левого края текущего блока

        lens_counter_in_tf = 0

        for block_idx, group_info in enumerate(active_groups):
            # Если галочка 'In Beam' снята - пропускаем добавление линзы в цепочку
            # (физически это означает, что линза выведена из пучка, остается только дрейф)
            # Если нужно сохранить дрейф, логика будет сложнее, но пока просто исключаем.

            if not group_info['active']:
                # Можно добавить логику добавления пустого промежутка, 
                # но пока просто пропускаем расчет элемента
                continue

            group_counter += 1
            n_lenses = group_info['N']
            preset = group_info['preset']
            #is_last_block = (block_idx == total_active - 1)

            block_length = 0.01 # 10 мм
            #spacing = block_length / (n_lenses + 1)
            p = self.defaults['p']

            if n_lenses * p > block_length:
                raise ValueError(f"Block {block_idx+1}: {n_lenses} lenses don't fit in 10 mm block")
            
            # Отступ слева и справа
            free_space = block_length - n_lenses * p
            offset_left = free_space / 2.0

            for lens_idx in range(1, n_lenses + 1):
                lens_counter_in_tf += 1
                pos_in_block = offset_left + (lens_idx - 0.5) * p
                lens_abs_pos = current_block_start + pos_in_block

                lens = LensGenerator.create_lens_group(
                    preset,
                    N = 1,
                    p = self.defaults['p'],
                    u = self.defaults['u_vac'],
                    source_manager = source_mgr
                )
                
                if not chain:
                    # Это первая линза в TF
                    lens['distance_from_prev'] = lens_abs_pos
                else:
                    prev_abs_pos = chain[-1]['absolute_position']
                    lens['distance_from_prev'] = lens_abs_pos - prev_abs_pos
                '''
                #первая линза в TF: первая линза первого активного блока
                is_first_in_tf = (group_counter == 1 and lens_idx == 1)
                #первая линза в блоке: всегда при local_idx == 1
                is_first_in_block = (lens_idx == 1)
                
                lens['is_first_in_tf'] = is_first_in_tf
                lens['is_first_in_block'] = is_first_in_block
                lens['is_last_in_tf'] = (group_counter == total_active and lens_idx == n_lenses)
                lens['is_last_in_block'] = (lens_idx == n_lenses)
                lens['is_last_in_tf'] = is_last_block and (lens_idx == n_lenses)
                lens['lens_index_in_tf'] = lens_idx + 1
                '''
                
                # Метаданные
                lens['absolute_position'] = lens_abs_pos
                lens['tf_name'] = tf_name
                lens['block_index'] = block_idx + 1
                lens['lens_index_in_tf'] = lens_counter_in_tf #len(chain) + 1 #sum(g['N'] for g in active_groups[:block_idx]) + lens_idx + 1
                lens['is_first_in_tf'] = (not chain)
                lens['is_last_in_block'] = (lens_idx == n_lenses)
                lens['is_last_in_tf'] = (block_idx == total_active - 1) and (lens_idx == n_lenses)   
                
                chain.append(lens)
            
            # Обновляем начало следующего блока
            if block_idx < total_active - 1:
                current_block_start += block_length + self.defaults.get('inter_block_gap', 0.001)

        # Удаляем служебное поле
        for lens in chain:
            lens.pop('absolute_position', None)
            ''' 
                
                # Сохраняем абсолютную позицию для следующей линзы
                lens['absolute_position'] = lens_abs_pos

                # Устанавливаем метаданные
                lens['tf_name'] = tf_name
                lens['block_index'] = block_idx + 1
                lens['tf_id'] = tf_name
                lens['lens_index_in_tf'] = lens_idx  # 1, 2, 3...

                # Расстояние
                if block_idx == 0 and lens_idx == 1:
                    lens['distance_from_prev'] = lens_abs_pos
                elif lens_idx == 1:
                    # Первая линза в группе → используем межгрупповой зазор
                    gap = inter_group_gaps[block_idx-1] if (block_idx-1) < len(inter_group_gaps) else 0.02
                    lens['distance_from_prev'] = gap + 0.001
                else:
                    # Последующие линзы в группе → шаг p + зазор u
                    lens['distance_from_prev'] = self.defaults['p'] + self.defaults['u_vac']
                
                is_last_in_tf = (group_counter == total_active and lens_idx == n_lenses)
                lens['is_last_in_tf'] = is_last_in_tf

                chain.append(lens)
            '''

        return chain
    
    def _build_air_tf(self, source_mgr, n_lenses, first_dist, preset = 'R50', tf_name = "TF Air"):
        """Расширенный метод для воздушного TF с выбором пресета."""
        chain = []
        base_lens = LensGenerator.create_lens_group(
            preset, N = 1, p = self.defaults['p'], u = self.defaults['u_air'], 
            source_manager=source_mgr
        )
        
        for local_idx in range(1, n_lenses + 1):
            lens = base_lens.copy()
            lens['is_first_in_tf'] = (local_idx == 1)
            #lens['is_first_in_block'] = True
            lens['tf_name'] = ''#tf_name
            lens['lens_index_in_tf'] = local_idx
            lens['distance_from_prev'] = first_dist if local_idx == 1 else (self.defaults['p'] + self.defaults['u_air'])
            chain.append(lens)
            is_last_in_tf = (local_idx == n_lenses)
            lens['is_last_in_tf'] = is_last_in_tf
        return chain
    
    def _calculate_block_length(self, block_type, block_conf):
        """Вычисляет длину TF в метрах."""
        if block_type == 'air':
            N = block_conf['lens_count']
            return N * 0.01  # 10 мм на линзу
        else:  # vacuum
            groups = block_conf['groups']
            N_blocks = sum(1 for g in groups if g['active'])
            return N_blocks * 0.01  # 10 мм на блок
    
    def run_calculations(self, energy, structure_config):
        # 1. Настройка источника
        source_mgr = SourceManager(energy = energy)
        source_params = source_mgr.get_params_dict()

        # 2. Сборка конфигурации системы (геометрия)
        lens_chain = []

        current_end_pos = 0.0  # текущая конечная позиция системы (после источника = 0)

        for index, block_conf in enumerate(structure_config):
            block_type = block_conf.get('type')
            absolute_start = block_conf.get('absolute_start')
            distance_from_prev = absolute_start - current_end_pos

            if block_type == 'vacuum':
                groups = block_conf.get('groups', [])
                tf_name = block_conf.get('tf_name', f'Vacuum {index}')
                block_chain = self._build_vacuum_tf(
                    source_mgr,
                    groups_data = groups,        # ← правильное имя параметра
                    first_dist = distance_from_prev,
                    tf_name = tf_name
                )
                lens_chain.extend(block_chain)

            elif block_type == 'air':
                count = block_conf.get('lens_count', 10)
                preset = block_conf.get('preset', 'R50')
                tf_name = block_conf.get('tf_name', f'Air {index}')
                block_chain = self._build_air_tf(
                    source_mgr,
                    n_lenses = count,
                    first_dist = distance_from_prev,
                    preset = preset
                )
                lens_chain.extend(block_chain)
            
            block_length = self._calculate_block_length(block_type, block_conf)
            current_end_pos = absolute_start + block_length

        # 3. Расчёт
        self.results, self.final_state = Calculator.propagate(
            lens_config = lens_chain,
            source_params = source_params
        )

        # 4. Отчёт
        return self._generate_report(source_params)
    
    def _generate_report(self, source_params):
        if not self.results:
            return {"error": "No results computed"}
        
        last = self.results[-1]
        state = self.final_state

        # Глубина резкости (опционально, можно упростить)
        # Если не используете — уберите вызов Formulas.dof
        # Но для совместимости оставим базовый отчёт:

        T_total = 1.0
        for t_block in state.T_blocks:
            T_total *= t_block

        G_total = 0.0
        for g_block in state.G_blocks:
            G_total = math.sqrt(G_total**2 + g_block**2)

        return {
            'energy': source_params['E'],
            'final_pos': last.position,
            #'F': last.F,
            'L2': last.L2,
            'M_total': last.M_total,
            'T': T_total if state else 1.0,
            'G': G_total,
            'size_x': last.sfx,
            'size_y': last.sfy,
            'full_history': self.results
        }


#________________________
''' 
    def _build_vacuum_tf(self, source_mgr, groups_lens_counts, first_dist):
        """
        Собирает вакуумный трансфокатор.
        Структура: [Группа 1] -> дрейф -> [Группа 2] -> дрейф ...
        Args:
            groups_lens_counts (list): Список кол-ва линз в группах, например [1, 2, 3]
            first_dist (float): Расстояние до ПЕРВОЙ линзы этого TF.
        """
        chain = []
        # Расстояния МЕЖДУ группами внутри вакуумного TF (из твоего кода)
        # tf1_1 (N=1) -> tf1_2 (N=2) -> tf1_3 (N=3)
        # В старом коде дельты были: 0.0185, 0.0175 и т.д.
        # Для упрощения зададим стандартный межблочный дрейф, или передадим список.
        inter_group_gaps = [0.0185, 0.0175, 0.0165, 0.0155] # Примерный список зазоров

        for i, n_lenses in enumerate(groups_lens_counts):
            #Создаём группу линз
            #В вакууме обычно R500
            group = LensGenerator.create_lens_group(
                'R500', N = n_lenses, p = self.defaults['p'], u = self.defaults['u_vac'],
                source_manager = source_mgr
            )

            #Расчёт дистанции
            if i == 0:
                #Самая первая группа в трансфокаторе
                group['distance_from_prev'] = first_dist
            else:
                #Последующие группы
                if i - 1 < len(inter_group_gaps): #переделать группу
                    gap = inter_group_gaps[i - 1] + 0.001 #+1mm на корпус
                else:
                    gap = 0.02 #Дефолт, если список кончился (?)
                group['distance_from_prev'] = gap

            chain.append(group)

        return chain
    
    def _build_air_tf(self, source_mgr, n_lenses, first_dist):
        """
        Собирает on_air TF (длинный массив линз).
        """
        chain = []
        # R50 usuall
        base_lens = LensGenerator.create_lens_group(
            'R50', N = 1, p = self.defaults['p'], u = self.defaults['u_air'],
            source_manager = source_mgr
        )

        for i in range(n_lenses):
            lens = base_lens.copy()
            if i == 0:
                lens['distance_from_prev'] = first_dist
            else:
                lens['distance_from_prev'] = self.defaults['p'] + self.defaults['u_air']

            chain.append(lens)

        return chain
'''
'''
block = {
    'preset': 'R500',
    'N': 3,
    'active': True,
    'lenses': [  # ← опционально, для детального редактора
        {'preset': 'R500', 'active': True},
        {'preset': 'R500', 'active': False},
        {'preset': 'R100', 'active': True}
    ]
}
'''