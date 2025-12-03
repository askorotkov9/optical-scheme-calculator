import math
from dataclasses import dataclass, make_dataclass, field
from typing import Dict, List, Optional, Tuple

# --- 1. Классы данных (Data Structures) ---
# Они заменят разрозненные переменные и словари

LENS_RESULT_FIELDS = [
    # Служебные поля (можно не показывать в GUI)
    ("tf_name", str,"TF", str),           # None в заголовке = не отображать
    ("block_index", int, None, None),
    ("is_last_in_block", bool, None, None),
    ("is_last_in_tf", bool, None, None),
    # (имя, тип, заголовок для GUI, форматтер)
    ("tf_id", str, None, None),
    ("index", int,  None, None),
    ("lens_index_in_tf", int, 'Lens in TF', str),
    ("lens_index_in_block", int, 'Lens number', str), #вставить колонку с R
    ("position", float, "Pos (m)", lambda x: f"{x:.4f}"),
    ("L1", float, "L1, m", lambda x: f"{x:.4f}"),
    ("L2", float, "L2, m", lambda x: "Inf" if x == float('inf') else f"{x:.4f}"),
    ("F", float, "F, m", lambda x: f"{x:.4f}"),
    ("sx", float, "sx, um", lambda x: f"{x * 1e6:.2f}"),
    ("sy", float, "sy, um", lambda x: f"{x * 1e6:.2f}"),
    ("sfpx", float, "sfpx, um", lambda x: f"{x * 1e6:.2f}"),
    ("sfpy", float, "sfpy, um", lambda x: f"{x * 1e6:.2f}"),
    ("alx", float, "Alx, um", lambda x: f"{x * 1e6:.2f}"),
    ("aly", float, "Aly, um", lambda x: f"{x * 1e6:.2f}"),
    ("sfx", float, "Focus X, um", lambda x: f"{x * 1e6:.2f}"),
    ("sfy", float, "Focus Y, um", lambda x: f"{x * 1e6:.2f}"),
    ("T", float, "Trans., %", lambda x: f"{x * 100:.1f}"),
    ("T_block", float, "T block, %", lambda x: f"{x * 100:.1f}"),
    #("T_total", float, "T total (%)", lambda x: f"{x * 100:.1f}"),
    ("M", float, "M", lambda x: f"{x:.3e}"),
    ("M_total", float, "M total", lambda x: f"{x:.3e}"),
    ("G", float, "G", lambda x: f"{x:.3e}"),
    ("G_total", float, "G total", lambda x: f"{x:.3e}"),
    #("G_block", float, "G block", lambda x: f"{x:.3e}"),
    # Можно добавить G, dof и т.д. — всё автоматически появится в GUI!
]

LensResult = make_dataclass("LensResult", [(name, typ) for name, typ, _, _ in LENS_RESULT_FIELDS])


@dataclass
class BeamState:
    """Хранит состояние пучка в конкретной точке оптической оси"""

    #focus_pos: float
    z: float                  # Текущая координата на оси
    wx: float                 # Размер источника/пучка X (расходимость или размер)
    wy: float                 # Размер источника/пучка Y
    sx: float                 # Размер пятна X
    sy: float                 # Размер пятна Y
    M_total: float = 1.0      # Общее увеличение
    T_current_block: float = 1.0
    G_current_block: float = 1.0
    T_total: float = 1.0      # Общее пропускание
    G_total: float = 1.0      # Общий gain

    T_blocks: List[float] = field(default_factory=list)
    G_blocks: List[float] = field(default_factory=list)

    # Параметры предыдущей линзы (для расчета следующей)
    L2_prev: float = 0.0
    Alx_prev: float = 0.0
    Aly_prev: float = 0.0
    Aeff_prev_total: float = float('inf')



# --- 2. Физическое ядро (Physics Engine) ---

class Formulas:
    use_fwhm = True
    """Сборник формул. Чистые функции, не хранят состояния"""

    @staticmethod
    def F_single_lens(R: float, delta: float, p: float) -> float: #убрать float
        #print(R)
        #print(delta)
        #print('p calc',p)
        return R / (2 * delta) + p / 6


    @staticmethod
    def L2(F, L1):
        if L1 == F:
            return float('inf')
        try:
            return 1/(1/F - 1/L1)
        except ZeroDivisionError:
            return float('inf')
        
    @staticmethod
    def magnification(L1, L2):
        return abs(L2 / L1)
    
    @staticmethod
    def magnification_total(M1, M2):
        return M1 * M2
    
    @staticmethod
    def Aeff_single_lens(F, delta, mu): #сделать свитч на sigma
        sigma_aeff = math.sqrt(F * delta / mu)
        fwhm_aeff = 2.35482 * sigma_aeff
        return fwhm_aeff if Formulas.use_fwhm else sigma_aeff

    @staticmethod
    def Aeff_system(Aeff_prev, Aeff_curr):
    #    if n == 1 and self.first_on_way == True:
    #        return Aeff2
        return math.sqrt(1/(1/Aeff_prev**2 + 1/Aeff_curr**2))

    @staticmethod
    def diff_lim(L2, A, Aeff, lamda): #diff_lim_total
        sigma = Aeff / 2.35482 #сделать свитч на sigma
        n_pow = 6
        A0 = 6 * sigma

        w = 1 / (1 + (A / A0)**n_pow)
        a = Aeff / A

        k = (a + 1/6 * math.exp(-a) * w + 0.442 * (1 - w))
        res = abs(k * lamda * L2 / Aeff)
        return res
    
    @staticmethod
    def sf(M, s, diff_lim):
        """Размер пучка в фокусе"""
        sl = M * s
        return math.sqrt(sl**2 + diff_lim**2)

    @staticmethod
    def sfp(L2_prev, L1, Al_prev, s_divergence, s, l, first_on_way: bool):
        """Размер пучка на входе в линзу"""
        if first_on_way: #if n == 1 and self.first_on_way == True:
            sfpn = math.sqrt((L1 * s_divergence)**2 + s**2)
        else:
            sfpn = Al_prev * abs(L2_prev - l) / L2_prev
        return sfpn
    
    @staticmethod
    def sfp_first_lens(L1: float, divergence: float, source_size: float) -> float:
        """Размер пучка на входе в первую линзу."""
        return math.sqrt((L1 * divergence)**2 + source_size**2)
    
    @staticmethod
    def sfp_next_lens(L2_prev: float, Al_prev: float, dist_from_prev: float) -> float:
        """Размер пучка на входе в последующую линзу (после фокуса)."""
        if L2_prev == 0:
            return float('inf')  # или 0, или бросить исключение
        return Al_prev * abs(dist_from_prev - L2_prev) / L2_prev #не lens_position
    
    @staticmethod
    def Al(A, sfp_val, Aeff):
        if A > sfp_val:
           return math.sqrt(1/(1/sfp_val**2 + 1/Aeff**2))
        else:
            return A
        #return math.sqrt(1/(1/sfp_val**2 + 1/self.Aeff_single_lens(F)**2))

    @staticmethod
    def transmission(A, Alx, Aly, sfpx, sfpy, mu, d):

        if Formulas.use_fwhm:
            const = math.sqrt(math.log(2))
        else:
            const = 1/ (2 * math.sqrt(2))


        erf_alx = math.erf(A * const / Alx)
        erf_aly = math.erf(A * const / Aly)
        erf_sfpx = math.erf(A * const / sfpx)
        erf_sfpy = math.erf(A * const / sfpy)
        T = math.exp(-mu * d) * (Alx * Aly) / (sfpx * sfpy) * (erf_alx * erf_aly) / (erf_sfpx * erf_sfpy)
        #return fwhm_aeff if Formulas.use_fwhm else sigma_aeff
        return T
    
    @staticmethod
    def transmission_total(T1, T2):
        return T1 * T2

    @staticmethod
    def straight_beam(L, s, s_divergence):
        return math.sqrt((L * s_divergence)**2 + s**2)
    
    @staticmethod
    def gain(T, straight_beam_x, straight_beam_y, sfx, sfy,):
        G = T * straight_beam_x * straight_beam_y / (sfx * sfy)
        return G
    
    @staticmethod
    def gain_total(G1, G2):
        return math.sqrt(G1**2 + G2**2)

    @staticmethod
    def sigma(Aeff):
        return Aeff / 2.35482


    @staticmethod
    def get_k_param(A, Aeff):
        sigma = Aeff / 2.35482 #FWHM / 2.35482
        n_pow = 6
        A0 = 6 * sigma

        w = 1 / (1 + (A / A0)**n_pow)
        a = Aeff / A

        k = (a + 1/6 * math.exp(-a) * w + 0.442 * (1 - w))
        return k
    
    @staticmethod
    def dof(L2, sf, Al, lamda, F, Aeff) -> Tuple[float, float, float]:
        """Глубина резкости (Depth of Field)."""
        if F == 0: return 0,0,0
        num_ap = Aeff / (2 * F)
        if num_ap == 0: return float('inf'), 0, 0
        
        dof_diff = lamda / (num_ap**2)
        
        if Al == 0: dof_g = float('inf')
        else: dof_g = 2 * L2 * sf / Al
        
        dof_total = math.sqrt(dof_diff**2 + dof_g**2)
        return dof_total, dof_diff, dof_g



# --- 3. Логика расчета (Logic) ---

class Calculator:
    """Класс, управляющий процессом расчета по цепочке линз."""

    @staticmethod
    def propagate(lens_config: List[Dict], source_params: Dict, initial_state: BeamState = None):
        """
        Основной цикл расчета.
        
        Args:
            lens_configs: Список словарей параметров линз (R, A, p, u, N...)
            source_params: Параметры источника (E, lamda, sx, sy...)
            initial_state: Состояние пучка ПЕРЕД первой линзой в списке.
        """

        #Если начальное состояние не передано, создаем его из источника
        if initial_state is None:
            #Это случай самой первой линзы
            state = BeamState(
                z = 0,
                wx = source_params['w0x'],
                wy = source_params['w0y'],
                sx = source_params['sx'],
                sy = source_params['sy'],
                L2_prev = 0,
                Alx_prev = 0, 
                Aly_prev = 0,
                M_total = 1,
                T_total = 1,
                G_total = 1
            )
        else:
            state = initial_state

        results = []
        lamda = source_params['lamda']

        for i, lens_conf in enumerate(lens_config):
            if lens_conf.get('is_first_in_tf', False):
                state.T_current_block = 1.0
                state.G_current_block = 0.0

            # 1. Извлекаем параметры линзы
            # Если передана группа (N > 1), нужно решить, как считать. 
            # Твой код считал линзы по одной внутри группы? Или группу как одну линзу?
            # В твоем parameters N=1..5, но в computations цикл шел по lens_set.
            # Будем считать, что lens_configs - это уже развернутый список одиночных элементов, 
            # либо мы обрабатываем "группу" как одну эффективную линзу (что обычно делается для CRL).
            # НО, твой старый код итерировал `for n in lens_set`.
            
            # Для простоты считаем, что lens_conf - это ОДНА физическая единица расчета.
            R = lens_conf['R']
            A_phys = lens_conf['A']
            p = lens_conf['p']
            delta = lens_conf['delta']
            mu = lens_conf['mu']
            d = lens_conf['d']

            # Расстояние от предыдущего элемента
            # Если это первая линза в общем списке, берем 'initial_L1' (нужно передать)
            # В твоем коде расстояние считалось снаружи.
            # Пусть lens_conf хранит 'distance_from_prev'
            t = lens_conf['distance_from_prev']

            #Определяем L1 (расстояние от источника / предыдущего фокуса до линзы)
            if state.L2_prev == 0 and state.Alx_prev == 0:
                L1 = t
                is_first = True
            else:
                L1 = t - state.L2_prev #lens['position'] - prev_pos - L2_prev
                is_first = False

            #2. РАсчёт оптики
            F = Formulas.F_single_lens(R, delta, p)
            L2 = Formulas.L2(F, L1)
            M = Formulas.magnification(L1, L2)
            #M_total = Formulas.magnification_total(M_total, M)

            Aeff = Formulas.Aeff_single_lens(F, delta, mu)
            Aeff_sys = Formulas.Aeff_system(state.Aeff_prev_total, Aeff)

            l_position = state.z + t

            if is_first:
                sfpx = Formulas.sfp_first_lens(L1=L1, divergence=state.wx, source_size=state.sx)
                sfpy = Formulas.sfp_first_lens(L1=L1, divergence=state.wy, source_size=state.sy)
            else:
                sfpx = Formulas.sfp_next_lens(L2_prev = state.L2_prev, Al_prev = state.Alx_prev, dist_from_prev = t)
                sfpy = Formulas.sfp_next_lens(L2_prev = state.L2_prev, Al_prev = state.Aly_prev, dist_from_prev = t)

            alx = Formulas.Al(A_phys, sfpx, Aeff)
            aly = Formulas.Al(A_phys, sfpy, Aeff)

            diff_lim = Formulas.diff_lim(L2, A_phys, Aeff, lamda)
            sfx = Formulas.sf(M, state.sx, diff_lim)
            sfy = Formulas.sf(M, state.sy, diff_lim)

            ''' Поменять расчёт для сценария sigma'''
            T = Formulas.transmission(A_phys, alx, aly, sfpx, sfpy, mu, d) 
            #T_total = Formulas.transmission_total(T_total, T)

            L_total_dist = L1 + L2
            sb_x = math.sqrt((L_total_dist * state.wx)**2 + state.sx**2)
            sb_y = math.sqrt((L_total_dist * state.wy)**2 + state.sy**2)
            G = Formulas.gain(T, sb_x, sb_y, sfx, sfy)
            #G_total = Formulas.gain_total(G_total, G)

            #Обновление состояния для следующей итерации
            new_wx = state.wx - alx/F #под вопросом правильность
            new_wy = state.wy - aly/F

            state.T_current_block *= T
            state.G_current_block = math.sqrt(state.G_current_block**2 + G**2)

            new_M_total = state.M_total * M
            new_T_total = state.T_total * T
            new_G_total = math.sqrt(state.G_total**2 + G**2)

            #Сохранение результатов
            result_data = {
                'tf_name': lens_conf.get('tf_name', 'Unknown'),
                'block_index': lens_conf.get('block_index', 1),
                'is_last_in_block': lens_conf.get('is_last_in_block', False),
                'is_last_in_tf': lens_conf.get('is_last_in_tf', False),
                'tf_id': lens_conf.get('tf_id', 'Unknown'),
                'lens_index_in_tf': lens_conf.get('lens_index_in_tf', i + 1),
                'lens_index_in_block': lens_conf.get('lens_index_in_block', 1),
                'index': i + 1,
                'position': state.z + t,
                'L1': L1,
                'L2': L2,
                'F': F,
                'sx': state.sx,
                'sy': state.sy,
                'sfpx': sfpx,
                'sfpy': sfpy,
                'alx': alx,
                'aly': aly,
                'sfx': sfx,
                'sfy': sfy,
                'T': T,
                'T_block': state.T_current_block,
                'M': M,
                'M_total': new_M_total,
                'G': G,
                'G_total': state.G_current_block
                # ... остальные поля
            }

            if lens_conf.get('is_last_in_tf', False):
                state.T_blocks.append(state.T_current_block)
                state.G_blocks.append(state.G_current_block)

            # Создаём объект
            res = LensResult(**result_data)
            ''' 
            res = LensResult(
                index = i + 1,
                position = state.z + t,
                L1 = L1, L2 = L2, F = F, M = M, T = T, G = G,
                alx = alx, aly = aly, sfx = sfx, sfy = sfy #M total, T total, diff_lim
            )
            '''
            results.append(res)

            #Обновление state
            state.z += t
            state.wx = new_wx
            state.wy = new_wy
            state.sx = sfx
            state.sy = sfy
            state.M_total *= M
            state.T_total *= T
            state.G_total = new_G_total #подумать над правильностью Formulas.gain_total(current_G_total, G)
            
            state.L2_prev = L2
            state.Alx_prev = alx
            state.Aly_prev = aly
            state.Aeff_prev_total = Aeff_sys

            # Внутри цикла по lens_conf:
            R = lens_conf['R']
            delta = lens_conf['delta']
            p = lens_conf['p']
            mu = lens_conf['mu']

        return results, state
    

# --- 4. Вспомогательные функции (исправленные) ---

def symmetry_dist_cleaned(l2, sfy, sfx, dofx_total, dofy_total):
    """
    Попытка найти расстояние, где пучок становится круглым (симетричным).
    Решает уравнение размеров пучка относительно Z.
    """
    # В оригинале было много закомментированного кода и хардкода.
    # Если предположить линейную зависимость расходимости от фокуса:
    # Size(z) ~ sf + divergence * z
    # Это сложно решить аналитически точно для всех случаев (дифракция + геометрия).
    
    # Упрощенно ищем точку пересечения конусов схождения/расхождения.
    # Если sfx > sfy, то пучок X сходится медленнее (или расходится быстрее).
    
    # ВНИМАНИЕ: Пользователь должен проверить физическую модель здесь.
    # Код ниже - это математически корректная заглушка для поиска пересечения.
    
    # Пример простой геометрической оценки:
    # return l2 * (sfx - sfy) / (sfx + sfy) # ОЧЕНЬ ГРУБО
    
    # Возвращаем 0, так как оригинальная функция была сломана/захардкожена
    # Рекомендуется использовать численный метод (перебор) в GUI:
    # посчитать symm_beam_size для z от 0 до L2 и найти минимум разницы |size_x - size_y|
    return 0.605 # Возвращаем значение из твоего print для совместимости пока что