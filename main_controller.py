import math
from computations import Calculator, Formulas
from parameters_micro1 import SourceManager, LensGenerator, LENS_PRESETS
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
        #self.results = [] #Список вычисленных параметров по каждой линзе
        #self.final_state = None #Конечное состояние пучка

        self.input_L1 = 27.1

    
    def _build_vacuum_tf(self, source_mgr, groups_data, first_dist, tf_name="Vacuum"):
        if not groups_data:
            return []

        p = self.defaults['p']  # 1e-3 = 1 мм
        u_vac = self.defaults['u_vac']
        block_length = 0.01  # 10 мм
        inter_block_gap = self.defaults.get('inter_block_gap', 0.001)

        # === 1. РАССТАНОВКА БЛОКОВ ===
        block_positions = []
        current_pos = first_dist

        for group_idx, group in enumerate(groups_data):
            n_lenses = min(group['N'], 5)  # максимум 5 линз

            if group_idx == 0:
                block_start = current_pos
            else:
                # Зазор между блоками (пока фиксированный)
                # Если хотите, можно сделать: gap = base - factor * (N_prev + N_curr)
                # Но по вашему примеру: 1 мм между стенками
                gap = 0.001  # 1 мм
                block_start = current_pos + gap

            block_end = block_start + block_length
            block_center = block_start + block_length / 2.0

            block_positions.append({
                'start': block_start,
                'end': block_end,
                'center': block_center,
                'n_lenses': n_lenses
            })

            current_pos = block_end

        # === 2. РАЗМЕЩЕНИЕ ЛИНЗ ВНУТРИ БЛОКОВ ===
        all_lenses = []

        for group_idx, (group, block_pos) in enumerate(zip(groups_data, block_positions)):
            n_lenses = block_pos['n_lenses']
            block_start = block_pos['start']

            if n_lenses * p > block_length:
                raise ValueError(f"Block {group_idx+1}: {n_lenses} lenses don't fit in 10 mm block")

            # === Стенки по бокам ===
            total_lens_width = n_lenses * p
            free_space = block_length - total_lens_width
            wall_thickness = free_space / 2.0

            # === Позиции линз внутри блока ===
            for lens_idx in range(n_lenses):
                pos_in_block = wall_thickness + (lens_idx + 0.5) * p
                abs_pos = block_start + pos_in_block

                # Получаем preset и active
                if 'lenses' in group and group['lenses'] is not None and len(group['lenses']) == n_lenses:
                    lens_info = group['lenses'][lens_idx]
                else:
                    lens_info = {'preset': group['preset'], 'active': group.get('active', True)}

                all_lenses.append({
                    'preset': lens_info['preset'],
                    'active': lens_info.get('active', True),
                    'abs_pos': abs_pos,
                    'block_index': group_idx + 1,
                    'lens_index_in_block': lens_idx + 1,
                    'material': lens_info.get('material', LENS_PRESETS[lens_info['preset']]['material'])
                })

        # === 3. СОЗДАНИЕ ЦЕПОЧКИ ===
        chain = []
        prev_active_pos = 0.0
        first_active_found = False

        for i, lens_geom in enumerate(all_lenses):
            if not lens_geom['active']:
                continue

            lens = LensGenerator.create_lens_group(
                lens_geom['preset'],
                N=1,
                p=p,
                u=u_vac,
                source_manager=source_mgr,
                material = lens_geom.get('material')
            )

            if not first_active_found:
                lens['distance_from_prev'] = lens_geom['abs_pos']
                prev_active_pos = lens_geom['abs_pos']
                first_active_found = True
            else:
                lens['distance_from_prev'] = lens_geom['abs_pos'] - prev_active_pos
                prev_active_pos = lens_geom['abs_pos']

            lens['tf_name'] = tf_name
            lens['block_index'] = lens_geom['block_index']
            lens['lens_index_in_tf'] = len(chain) + 1
            lens['lens_index_in_block'] = lens_geom['lens_index_in_block']
            lens['is_first_in_tf'] = (len(chain) == 0)
            lens['is_last_in_block'] = (lens_geom['lens_index_in_block'] == groups_data[lens_geom['block_index'] - 1]['N'])
            lens['is_last_in_tf'] = False

            chain.append(lens)

        if chain:
            chain[-1]['is_last_in_tf'] = True

        return chain
    
    def _build_air_tf(self, source_mgr, lenses, first_dist, tf_name = "Air"):
        """
        Собирает воздушный TF с физическим удалением неактивных линз.
        lenses: список словарей [{'preset': ..., 'active': ...}, ...]
        first_dist: расстояние от источника до ПЕРВОЙ линзы (даже если она неактивна!)
        """
        if not lenses:
            return []

        p = self.defaults['p']
        u = self.defaults['u_air']
        
        # Шаг между центрами соседних линз
        step = p + u

        # 1. Строим полную геометрию: позиции ВСЕХ линз
        all_positions = []
        for i in range(len(lenses)):
            pos = first_dist + i * step
            all_positions.append(pos)

        # 2. Собираем цепочку только из активных линз
        chain = []
        prev_active_pos = 0.0  # позиция предыдущей активной линзы (абсолютная)
        first_active_found = False

        for i, (lens_info, abs_pos) in enumerate(zip(lenses, all_positions)):
            if not lens_info.get('active', True):
                continue  # пропускаем неактивную

            preset = lens_info.get('preset', 'R50')
            material = lens_info.get('material')
            lens = LensGenerator.create_lens_group(
                preset,
                N=1,
                p=p,
                u=u,
                source_manager=source_mgr,
                material = material
            )

            if not first_active_found:
                # Первая активная линза: расстояние от источника
                lens['distance_from_prev'] = abs_pos
                prev_active_pos = abs_pos
                first_active_found = True
            else:
                # Последующие: расстояние от предыдущей активной
                lens['distance_from_prev'] = abs_pos - prev_active_pos
                prev_active_pos = abs_pos

            # Метаданные
            lens['tf_name'] = tf_name
            lens['block_index'] = 1
            lens['lens_index_in_tf'] = len(chain) + 1
            lens['is_first_in_tf'] = (len(chain) == 0)
            lens['lens_index_in_block'] = i + 1
            lens['is_last_in_block'] = False #True
            lens['is_last_in_tf'] = False  # обновим позже

            chain.append(lens)

        # Обновляем is_last_in_tf
        if chain:
            chain[-1]['is_last_in_tf'] = True

        return chain
    
    def _calculate_block_length(self, block_type, block_conf):
        """Вычисляет длину TF в метрах."""
        if block_type == 'air':
            #N = block_conf['lens_count']
            return 0.1396  # 10 мм на линзу
        else:  # vacuum
            groups = block_conf['groups']
            N_blocks = sum(1 for g in groups if g['active'])
            return N_blocks * 0.01  # 10 мм на блок
    
    def run_calculations(self, energy, structure_config, source_params = None):
        # 1. Настройка источника
        if source_params is not None:
            source_mgr = SourceManager(
                energy = source_params['energy'],
                sx_fwhm = source_params['sx_fwhm'],
                sy_fwhm = source_params['sy_fwhm'],
                wx_fwhm = source_params['wx_fwhm'],
                wy_fwhm = source_params['wy_fwhm'],
                #material = source_params['material']
            )

        else:
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
                block_length = self._calculate_block_length(block_type, block_conf)
                current_end_pos = absolute_start + block_length

            elif block_type == 'air':
                lenses = block_conf.get('lenses', [])
                if lenses is None:
                    # fallback для обратной совместимости (не должно сработать)
                    count = block_conf.get('lens_count', 10)
                    preset = block_conf.get('preset', 'R50')
                    lenses = [{'preset': preset, 'active': True} for _ in range(count)]
                    #current_end_pos = absolute_start + block_length
                
                tf_name = block_conf.get('tf_name', f'Air {index}')
                block_chain = self._build_air_tf(
                    source_mgr,
                    lenses = lenses,
                    first_dist = distance_from_prev,
                    tf_name = tf_name
                )
                lens_chain.extend(block_chain)
            
                block_length = self._calculate_block_length(block_type, block_conf)
                current_end_pos = absolute_start + block_length#self._calculate_block_length(block_type, 1)

        # 3. Расчёт
        results, final_state = Calculator.propagate( #self.results, self.final_state = Calculator.propagate
            lens_config = lens_chain,
            source_params = source_params
        )

        # 4. Отчёт
        return self._generate_report(source_params, results, final_state) #self._generate_report(source_params)
    
    def _generate_report(self, source_params, results, final_state):
        if not results:
            return {"error": "No results computed"}
        
        last = results[-1]
        T_total = 1.0
        for t in final_state.T_blocks:
            T_total *= t

        G_total = 0.0
        for g in final_state.G_blocks:
            G_total = math.sqrt(G_total**2 + g**2)

        return {
            'energy': source_params['energy'], #'energy': source_params['E'],
            'final_pos': last.position,
            'L2': last.L2,
            'M_total': last.M_total,
            'T': T_total,
            'G': G_total,
            'size_x': last.sfx,
            'size_y': last.sfy,
            'full_history': results  # ← свежий, независимый список
        }

    """
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
    """

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


Про вопрос с передачей use_fwhm в SourceManager; более элегантный вариант
Используйте Вариант 2 — он надёжен и легко поддерживается:
# В main_controller.py, в run_calculations
SOURCE_MANAGER_KEYS = {'energy', 'sx_fwhm', 'sy_fwhm', 'wx_fwhm', 'wy_fwhm', 'material'}

def run_calculations(self, energy, structure_config, source_params=None):
    if source_params is not None:
        # Фильтруем только нужные ключи
        sm_params = {k: v for k, v in source_params.items() if k in SOURCE_MANAGER_KEYS}
        source_mgr = SourceManager(**sm_params)
    else:
        source_mgr = SourceManager(energy=energy)
    # ...

✅ Это предотвратит ошибки при добавлении новых GUI-флагов (типа use_fwhm, database, density и т.д.).

После этого ошибка исчезнет, и расчёты будут работать корректно.



'''