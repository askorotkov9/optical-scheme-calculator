import time
from computations import Calculator, Formulas
from parameters_micro1 import SourceManager, LensGenerator, LENS_PRESETS


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
        self._optical_cache = {}

    def _get_optical_params(self, preset, material, energy):
        """Кэшированный расчёт оптических параметров"""
        cache_key = (preset, material, energy)
        if cache_key not in self._optical_cache:
            # Создаём временный source_manager для расчёта
            source_mgr = SourceManager(energy=energy)
            # Вызываем LensGenerator.create_lens_group один раз
            lens_config = LensGenerator.create_lens_group(
                preset, N=1, p=1e-3, u=0,
                source_manager=source_mgr,
                material=material
            )
            self._optical_cache[cache_key] = {
                'R': lens_config['R'],
                'A': lens_config['A'],
                'delta': lens_config['delta'],
                'betta': lens_config['betta'],
                'mu': lens_config['mu']
            }
        return self._optical_cache[cache_key]

    def _get_optical_cache(self, preset, material, energy, tf_type):
        """Кэшированный расчёт оптических параметров"""
        cache_key = (preset, material, energy)
        u_val = self.defaults['u_vac'] if tf_type == 'vacuum' else self.defaults['u_air']
        if cache_key not in self._optical_cache:
            # Выполняем расчёт только один раз
            lens_config = LensGenerator.create_lens_group(
                preset, N=1, p=self.defaults['p'], u=u_val, 
                source_manager=SourceManager(energy=energy),
                material=material
            )
            self._optical_cache[cache_key] = {
                'R': lens_config['R'],
                'A': lens_config['A'],
                'material': lens_config['material'],
                'delta': lens_config['delta'],
                'betta': lens_config['betta'],
                'mu': lens_config['mu']
            }
        return self._optical_cache[cache_key] 
    
    def _build_vacuum_tf(self, source_mgr, groups_data, first_dist, tf_name="Vacuum"):
        if not groups_data:
            return []

        p = self.defaults['p']
        u_vac = self.defaults['u_vac']
        block_length = 0.01
        inter_block_gap = self.defaults.get('inter_block_gap', 0.001)
        
        chain = []
        current_block_start = first_dist
        
        for group_idx, group in enumerate(groups_data):
            #if not group.get('active', True):
            #    continue
                
            n_lenses = min(group['N'], 5)
            total_lens_width = n_lenses * p
            free_space = block_length - total_lens_width
            wall_thickness = free_space / 2.0
            
            # Определяем, есть ли детализация по линзам (режим GUI)
            has_individual_lenses = ('lenses' in group and 
                                    group['lenses'] and 
                                    len(group['lenses']) >= n_lenses)
            
            # РАЗВОРАЧИВАЕМ ВСЕ ЛИНЗЫ В БЛОКЕ
            for lens_idx in range(n_lenses):
                if has_individual_lenses:
                    # Режим GUI: используем параметры отдельной линзы
                    lens_info = group['lenses'][lens_idx]
                    preset = lens_info['preset']
                    material = lens_info.get('material', 'Be')
                    active = lens_info.get('active', True)
                else:
                    # Режим RL: все линзы в блоке одинаковые
                    preset = group['preset']
                    material = group.get('material', 'Be')
                    active = group.get('active', True)
                
                # Пропускаем неактивные линзы (только в режиме GUI)
                if not active:
                    continue
                
                # Получаем оптические параметры
                optical_params = self._get_optical_cache(preset, material, source_mgr.E, 'vacuum')
                
                abs_pos = current_block_start + wall_thickness + (lens_idx + 0.5) * p
                
                lens = {
                    'R': optical_params['R'],
                    'A': optical_params['A'],
                    'p': p,
                    'u': u_vac,
                    'd': 30e-6,
                    'delta': optical_params['delta'],
                    'betta': optical_params['betta'],
                    'mu': optical_params['mu'],
                    'material': material,
                    'abs_pos': abs_pos,
                    'tf_name': tf_name,
                    'block_index': group_idx + 1,
                    'lens_index_in_tf': len(chain) + 1,
                    'lens_index_in_block': lens_idx + 1,
                    'is_first_in_tf': (len(chain) == 0),
                    'is_last_in_block': (lens_idx + 1 == n_lenses),
                    'is_last_in_tf': False,
                    'tf_type': 'vacuum'
                }
                chain.append(lens)
            
            current_block_start += block_length + inter_block_gap
        
        if chain:
            chain[-1]['is_last_in_tf'] = True
        
        return chain
    
    def _build_air_tf(self, source_mgr, lenses, first_dist, tf_name="Air"):
        if not lenses:
            return []
        
        p = self.defaults['p']
        u = self.defaults['u_air']
        step = p + u
        
        # Кэшируем уникальные пресеты
        unique_presets = set(lens.get('preset', 'R50') for lens in lenses if lens.get('active', True))
        preset_cache = {}
        for preset in unique_presets:
            preset_cache[preset] = self._get_optical_cache(preset, 'Be', source_mgr.E, 'air')
        
        chain = []
        for i, lens_info in enumerate(lenses):
            if not lens_info.get('active', True):
                continue

            material = lens_info.get('material', 
                    LENS_PRESETS[lens_info['preset']].get('material', 'Be'))
            
            preset = lens_info.get('preset', 'R50')
            optical_params = self._get_optical_cache(preset, material, source_mgr.E, 'air')
            abs_pos = first_dist + i * step
            
            lens = {
                'R': optical_params['R'],
                'A': optical_params['A'],
                'p': p,
                'u': u,
                'd': 30e-6,
                'delta': optical_params['delta'],
                'betta': optical_params['betta'],
                'mu': optical_params['mu'],
                'material': lens_info.get('material', 'Be'),
                'abs_pos': abs_pos,
                'tf_name': tf_name,
                'block_index': 1,
                'lens_index_in_tf': len(chain) + 1,
                'lens_index_in_block': i + 1,
                'is_first_in_tf': (len(chain) == 0),
                'is_last_in_block': False,
                'is_last_in_tf': False,
                'tf_type': 'air'
            }
            chain.append(lens)
        
        if chain:
            chain[-1]['is_last_in_tf'] = True
        
        return chain    
    
    '''
    def _build_vacuum_tf(self, source_mgr, groups_data, first_dist, tf_name="Vacuum"):
        if not groups_data:
            return []

        p = self.defaults['p']  # 1e-3 = 1 мм
        u_vac = self.defaults['u_vac']
        block_length = 0.01  # 10 мм
        inter_block_gap = self.defaults.get('inter_block_gap', 0.001)

        # === 1. РАССТАНОВКА БЛОКОВ (все линзы, включая неактивные) ===
        all_lenses = []

        current_block_start = first_dist

        for group_idx, group in enumerate(groups_data):
            n_lenses = min(group['N'], 5)

            # === Позиции линз внутри блока ===
            if n_lenses * p > block_length:
                raise ValueError(f"Block {group_idx+1}: {n_lenses} lenses don't fit in 10 mm block")

            total_lens_width = n_lenses * p
            free_space = block_length - total_lens_width
            wall_thickness = free_space / 2.0

            for lens_idx in range(n_lenses):
                pos_in_block = wall_thickness + (lens_idx + 0.5) * p
                abs_pos = current_block_start + pos_in_block

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
                    'material': lens_info.get('material', LENS_PRESETS[lens_info['preset']].get('material', 'Be'))
                })

            # Переход к следующему блоку
            current_block_start += block_length + inter_block_gap

        # === 2. СОЗДАНИЕ ЦЕПОЧКИ (только активные линзы) ===
        chain = []
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

            lens['abs_pos'] = lens_geom['abs_pos']  # ← передаём абсолютную позицию
            lens['tf_name'] = tf_name
            lens['block_index'] = lens_geom['block_index']
            lens['lens_index_in_tf'] = len(chain) + 1
            lens['lens_index_in_block'] = lens_geom['lens_index_in_block']
            lens['is_first_in_tf'] = (len(chain) == 0)
            lens['is_last_in_block'] = (lens_geom['lens_index_in_block'] == groups_data[lens_geom['block_index'] - 1]['N'])
            lens['is_last_in_tf'] = False
            lens['tf_type'] = 'vacuum'

            chain.append(lens)

        if chain:
            chain[-1]['is_last_in_tf'] = True

        return chain

    def _build_air_tf(self, source_mgr, lenses, first_dist, tf_name="Air"):
        if not lenses:
            return []

        p = self.defaults['p']
        u = self.defaults['u_air']
        
        step = p + u

        all_positions = []
        for i in range(len(lenses)):
            pos = first_dist + i * step  # ← теперь это absolute_start + offset
            all_positions.append(pos)

        chain = []
        for i, (lens_info, abs_pos) in enumerate(zip(lenses, all_positions)):
            if not lens_info.get('active', True):
                continue

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

            lens['abs_pos'] = abs_pos  # ← передаём абсолютную позицию
            lens['tf_name'] = tf_name
            lens['block_index'] = 1
            lens['lens_index_in_tf'] = len(chain) + 1
            lens['is_first_in_tf'] = (len(chain) == 0)
            lens['lens_index_in_block'] = i + 1
            lens['is_last_in_block'] = False
            lens['is_last_in_tf'] = False
            lens['tf_type'] = 'Air (Array)'

            chain.append(lens)

        if chain:
            chain[-1]['is_last_in_tf'] = True

        return chain
    '''
    def _calculate_block_length(self, block_type, block_conf):
        """Вычисляет длину TF в метрах."""
        if block_type == 'air':
            #N = block_conf['lens_count']
            return 0.1396  # 10 мм на линзу
        else:  # vacuum
            return 0.153
            #groups = block_conf['groups']
            #N_blocks = sum(1 for g in groups if g['active'])
            #return N_blocks * 0.01  # 10 мм на блок
    
    def run_calculations(self, energy, structure_config, source_params = None):
        # 1. Настройка источника
        #start_time = time.time()
        #print(f"[DEBUG] Config received in controller: {len(structure_config)} TFs")
        #for i, tf in enumerate(structure_config):
        #    if tf['type'] == 'vacuum':
        #        print(f"  TF{i} (vacuum): {len(tf['groups'])} groups")
        #        for j, g in enumerate(tf['groups']):
        #            print(f"    Group {j}: N={g.get('N')}, active={g.get('active')}")

        if source_params is not None:
            source_mgr = SourceManager(
                energy = source_params['energy'],
                sx_fwhm = source_params['sx_fwhm'],
                sy_fwhm = source_params['sy_fwhm'],
                wx_fwhm = source_params['wx_fwhm'],
                wy_fwhm = source_params['wy_fwhm'],
            )
        else:
            source_mgr = SourceManager(energy = energy)
            
        source_params = source_mgr.get_params_dict()
        #source_params['sx_fwhm'] = 7.47e-5# source_params['sx_fwhm'],
        #source_params['sy_fwhm'] = 1.39e-5#source_params['sy_fwhm'],

        # 2. Сборка конфигурации системы (геометрия)
        lens_chain = []

        for index, block_conf in enumerate(structure_config):
            block_type = block_conf.get('type')
            absolute_start = block_conf.get('absolute_start')  # ← теперь получаем готовый absolute_start

            if block_type == 'vacuum':
                groups = block_conf.get('groups', [])
                tf_name = block_conf.get('tf_name', f'Vacuum {index}')
                block_chain = self._build_vacuum_tf(
                    source_mgr,
                    groups_data = groups,
                    first_dist = absolute_start,  # ← передаём абсолютную позицию начала TF
                    tf_name = tf_name
                )
                for lens in block_chain:
                    lens['tf_type'] = 'vacuum'
                lens_chain.extend(block_chain)

            elif block_type == 'air':
                lenses = block_conf.get('lenses', [])
                tf_name = block_conf.get('tf_name', f'Air {index}')
                block_chain = self._build_air_tf(
                    source_mgr,
                    lenses = lenses,
                    first_dist = absolute_start,  # ← передаём абсолютную позицию начала TF
                    tf_name = tf_name
                )
                for lens in block_chain:
                    lens['tf_type'] = 'air'
                lens_chain.extend(block_chain)

        # 3. Расчёт
        results, final_state = Calculator.propagate(
            lens_config = lens_chain,
            source_params = source_params
        )

        # 4. Отчёт
        #build_time = time.time()
        #results, final_state = Calculator.propagate(lens_chain, source_params)
        #calc_time = time.time()

        #print(f"Build time: {(build_time - start_time)*1000:.1f}ms, "
        #    f"Calc time: {(calc_time - build_time)*1000:.1f}ms")

        return self._generate_report(source_params, results, final_state)
    
    def _generate_report(self, source_params, results, final_state):
        if not results:
            return {"error": "No results computed"}
        
        last = results[-1]

        #print(f"DEBUG: final_state has T_blocks: {hasattr(final_state, 'T_blocks')}")
        #if hasattr(final_state, 'T_blocks'):
        #    print(f"DEBUG: T_blocks length: {len(final_state.T_blocks)}")
        #    print(f"DEBUG: T_blocks content: {final_state.T_blocks}")
        
        T_total = 1.0
        if hasattr(final_state, 'T_blocks') and final_state.T_blocks:
            for t in final_state.T_blocks:
                T_total *= t
        else:
            # АЛЬТЕРНАТИВНЫЙ ИСТОЧНИК
            T_total = getattr(last, 'T_total', 1.0)
            print(f"DEBUG: Using last.T_total = {T_total}")

            
        #T_total = 1.0
        #for t in final_state.T_blocks:
        #    T_total *= t
            #print(t)
        
        #print('T_total', T_total)
        #print('size_x', last.sfx)
            #'size_y': last.sfy,

        G_total = 1.0
        #for g in final_state.G_blocks:
        #    G_total *= g

        return {
            'energy': source_params['energy'], #'energy': source_params['E'],
            'final_pos': last.position,
            'L2': last.L2,
            'M_total': last.M_total,
            'T': T_total,
            'G': G_total,
            'size_x': last.sfx,
            'size_y': last.sfy,
            'dof_x': last.dof_x,
            'dof_y': last.dof_y,
            'full_history': results  # ← свежий, независимый список
        }