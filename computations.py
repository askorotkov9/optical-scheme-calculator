import math
from dataclasses import dataclass, make_dataclass, field
from typing import Dict, List, Optional, Tuple

# --- 1. Классы данных (Data Structures) ---

LENS_RESULT_FIELDS = [
    # Служебные поля (можно не показывать в GUI)
    ("tf_name", str,"TF", str),           # None in header = do not display
    ("tf_type", str, None, None),
    ("block_index", int, 'Block', lambda x: f"Block {x}"),
    ("is_last_in_block", bool, None, None),
    ("is_last_in_tf", bool, None, None),
    ("is_first_in_tf", bool, None, None),
    ("is_first_in_block", bool, None, None),
    # (имя, тип, заголовок для GUI, форматтер)
    ("tf_id", str, None, None),
    ("index", int,  None, None),
    ("lens_index_in_tf", int, 'Lens in TF', str),
    ("lens_index_in_block", int, 'Lens number', str),
    ("position", float, "Pos (m)", lambda x: f"{x:.4f}"),
    ("R", float, "Radius, um", lambda x: f"{x * 1e6:.0f}"),
    ("L1", float, "L1, m", lambda x: f"{x:.4f}"),
    ("L2", float, "L2, m", lambda x: "Inf" if x == float('inf') else f"{x:.4f}"),
    ("F", float, "F, m", lambda x: f"{x:.4f}"),
    ("F_system", float, "F system, m", lambda x: f"{x:.4f}"),
    ("sx_fwhm", float, "source (x), um", lambda x: f"{x * 1e6:.2f}"),
    ("sy_fwhm", float, "source (y), um", lambda x: f"{x * 1e6:.2f}"),
    ("sfpx", float, "Sfp (x), um", lambda x: f"{x * 1e6:.2f}"),
    ("sfpy", float, "Sfp (y), um", lambda x: f"{x * 1e6:.2f}"),
    ("alx", float, "Al (x), um", lambda x: f"{x * 1e6:.2f}"),
    ("aly", float, "Al (y), um", lambda x: f"{x * 1e6:.2f}"),
    ("slx", float, "slx", lambda x: f"{x * 1e6:.2f}"),
    ("sly", float, "sly", lambda x: f"{x * 1e6:.2f}"),
    ("diff_lim", float, "Lens Res, um", lambda x: f"{x * 1e6:.2f}"),
    #("diff_lim_y", float, "Res (y), um", lambda x: f"{x * 1e6:.2f}"),
    ("sfx", float, "Focus Size (x), um", lambda x: f"{x * 1e6:.2f}"),
    ("sfy", float, "Focus Size (y), um", lambda x: f"{x * 1e6:.2f}"),
    ("T", float, "Trans., %", lambda x: f"{x * 100:.1f}"),
    ("T_block", float, "T block, %", lambda x: f"{x * 100:.1f}"),
    ("T_total", float, "T total (%)", lambda x: f"{x * 100:.1f}"),
    ("M", float, "M", lambda x: f"{x:.3e}"),
    ("M_total", float, "M total", lambda x: f"{x:.3e}"),
    ("G", float, "G", lambda x: f"{x:.3e}"),
    ("G_total", float, "G total", lambda x: f"{x:.3e}"),
    ("NA", float, "NA", lambda x: f"{x:.3e}"),
    ("NA_block", float, "NA block", lambda x: f"{x:.3e}"),
    ("Aeff", float, "Effective Aperture, um", lambda x: f"{x * 1e6:.2f}"),
    ("Aeff_total", float, "Aeff total", lambda x: f"{x * 1e6:.2f}"),
    ("Aeff_block", float, "Aeff block", lambda x: f"{x * 1e6:.2f}"),
    ("dof_x", float, None, lambda x: f'{x:.3e}'),
    ("dof_y", float, None, lambda x: f'{x:.3e}'),
    ("symmetry_dist", float, None, lambda x: f"{x:.4f}"),
    ("symm_beam_size_x", float, None, lambda x: f"{x * 1e6:.2f}"),
    ("symm_beam_size_y", float, None, lambda x: f"{x * 1e6:.2f}"),
]

LensResult = make_dataclass("LensResult", [(name, typ) for name, typ, _, _ in LENS_RESULT_FIELDS])


@dataclass
class BeamState:
    """Stores the state of the beam at a specific point on the optical axis"""

    #focus_pos: float
    z: float                  # Current coordinate
    wx: float                 # Source Divergence X
    wy: float                 # Source Divergence Y
    sx: float                 # Beam size X
    sy: float                 # Beam size Y
    M_total: float = 1.0      # Total magnification
    T_current_block: float = 1.0 # Block transmission
    G_current_block: float = 1.0
    T_total: float = 1.0      # Total transmission
    G_total: float = 1.0      # Total gain

    NA_current_block: float = 0.0
    Aeff_current_block: float = float('inf')
    Aeff_current_tf: float = float('inf')

    T_blocks: List[float] = field(default_factory=list)
    G_blocks: List[float] = field(default_factory=list)
    NA_blocks: List[float] = field(default_factory=list)
    Aeff_blocks: List[float] = field(default_factory=list)

    # Previous lens parameters
    L2_prev: float = 0.0
    Alx_prev: float = 0.0
    Aly_prev: float = 0.0
    Aeff_prev_total: float = float('inf')


class Formulas:
    use_fwhm = True

    @staticmethod
    def F_single_lens(R: float, delta: float, p: float, N = 1) -> float:
        return R / (2 * N * delta) + p / 6
    
    @staticmethod
    def F_system(F1, F2, distance):
        return 1/(1/F1 + 1/F2 - distance/(F1*F2))

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
        if Aeff_prev == float('inf'):
            return Aeff_curr
        return math.sqrt(1/(1/Aeff_prev**2 + 1/Aeff_curr**2))

    @staticmethod
    def diff_lim(L2, A, Aeff, lamda):
        sigma = Aeff / 2.35482 #сделать свитч на sigma
        n_pow = 6
        A0 = 6 * sigma

        w = 1 / (1 + (A / A0)**n_pow)
        a = Aeff / A

        k = (a + 1/6 * math.exp(-a) * w + 0.442 * (1 - w))
        res = abs(k * lamda * L2 / Aeff)
        return res
    
    @staticmethod
    def sigma(Aeff):
        return Aeff / 2.35482

    @staticmethod
    def get_k_param(A, Aeff):
        sigma = Aeff / 2.35482
        n_pow = 6
        A0 = 6 * sigma

        w = 1 / (1 + (A / A0)**n_pow)
        a = Aeff / A

        k = (a + 1/6 * math.exp(-a) * w + 0.442 * (1 - w))
        return k
    
    @staticmethod
    def sf(M, s, diff_lim):
        """Размер пучка в фокусе"""
        sl = M * s
        return math.sqrt(sl**2 + diff_lim**2)
    
    @staticmethod
    def sl(M, s):
        """Размер пучка в фокусе"""
        sl = M * s
        return sl

    @staticmethod
    def sfp(L2_prev, L1, Al_prev, s_divergence, s, l, first_on_way: bool):
        """Размер пучка на входе в линзу"""
        if first_on_way:
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
            return float('inf')
        return Al_prev * abs(dist_from_prev - L2_prev) / L2_prev
    
    @staticmethod
    def Al(A, sfp_val, Aeff):
        if A > sfp_val:
           return math.sqrt(1/(1/sfp_val**2 + 1/Aeff**2))
        else:
            return A

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
        T_fwhm = math.exp(-mu * d) * (Alx * Aly) / (sfpx * sfpy) * (erf_alx * erf_aly) / (erf_sfpx * erf_sfpy)
        T_sigma = math.exp(-mu * d) * (Alx * Aly) / (sfpx * sfpy) * (erf_alx * erf_aly) / (erf_sfpx * erf_sfpy) #Need correction
        return T_fwhm if Formulas.use_fwhm else T_sigma
    
    @staticmethod
    def transmission_total(T1, T2):
        return T1 * T2

    @staticmethod
    def straight_beam(L, s, s_divergence):
        return math.sqrt((L * s_divergence)**2 + s**2)
    
    @staticmethod
    def gain(T, straight_beam_x, straight_beam_y, sfx, sfy,):
        G = T * straight_beam_x * straight_beam_y / (sfx * sfy)
        return min(G, 1e10)
    
    @staticmethod
    def gain_total(G1, G2):
        return G1*G2
    
    @staticmethod
    def numerical_aperture(Aeff, F):
        return Aeff / (2 * F)
    
    @staticmethod
    def num_aper_total():
        return
    
    @staticmethod
    def symmetry_dist(l2, sfy, sfx, alx, aly, k):
        """Calculate distance from last lens for symmetry beam"""
        try:
            return l2*math.sqrt((math.pow((1 + k) * sfy, 2) - math.pow(sfx, 2)) / (math.pow(alx, 2) - math.pow((1 + k) * aly, 2)))
        except ZeroDivisionError:
            return 0
        except ValueError:
            return 0
    
    @staticmethod
    def beamsize_at_distance(Al, L2, L, sf):
        """Calculate size of beam at some distance"""
        sg = Al * L / L2
        return math.sqrt(sf**2 + sg**2)

    @staticmethod
    def dof(L2, sf, Al):
        """depth of field"""
        k = 0.1
        dof = 2 * L2 * (1 + k)* sf / Al
        return dof


# --- 3. Calculation logic ---

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

        if initial_state is None:
            #first lens
            state = BeamState(
                z = 0,
                wx = source_params['wx_fwhm'],
                wy = source_params['wy_fwhm'],
                sx = source_params['sx_fwhm'],
                sy = source_params['sy_fwhm'],
                L2_prev = 0,
                Alx_prev = 0, 
                Aly_prev = 0,
                M_total = 1,
                T_current_block = 1.0,
                T_blocks = [],
                T_total = 1,
                G_current_block = 1,
                G_blocks = [],
                G_total = 1,
                Aeff_prev_total = float('inf')
            )
        else:
            state = initial_state

        results = []
        lamda = source_params['lamda']

        for i, lens_conf in enumerate(lens_config):
            if lens_conf.get('is_first_in_tf', False):
                state.T_current_block = 1.0
                state.G_current_block = 1.0
                state.NA_current_block = 0.0
                state.Aeff_current_block = float('inf')

            abs_pos = lens_conf.get('abs_pos', None)
            if abs_pos is not None:
                if i == 0:
                    distance_from_prev = abs_pos  # distance from source
                else:
                    prev_abs_pos = lens_config[i - 1].get('abs_pos', state.z)
                    distance_from_prev = abs_pos - prev_abs_pos
            else:
                distance_from_prev = lens_conf.get('distance_from_prev', 0)

            R = lens_conf['R']
            A_phys = lens_conf['A']
            p = lens_conf['p']
            delta = lens_conf['delta']
            mu = lens_conf['mu']
            d = lens_conf['d']

            # Distance from previous element
            t = distance_from_prev

            # L1 definition (distance from source for 1st element or L2 from previous element)
            if state.L2_prev == 0 and state.Alx_prev == 0:
                L1 = t
                is_first = True
            else:
                L1 = t - state.L2_prev
                is_first = False

            #2. Расчёт оптики
            F = Formulas.F_single_lens(R, delta, p)
            L2 = Formulas.L2(F, L1)
            
            M = Formulas.magnification(L1, L2)

            Aeff = Formulas.Aeff_single_lens(F, delta, mu)
            Aeff_sys = Formulas.Aeff_system(state.Aeff_prev_total, Aeff)

            if is_first:
                sfpx = Formulas.sfp_first_lens(L1=L1, divergence=state.wx, source_size=state.sx) if state.wx else A_phys
                sfpy = Formulas.sfp_first_lens(L1=L1, divergence=state.wy, source_size=state.sy) if state.wy else A_phys
                F_system = F
            else:
                sfpx = Formulas.sfp_next_lens(L2_prev = state.L2_prev, Al_prev = state.Alx_prev, dist_from_prev = t)
                sfpy = Formulas.sfp_next_lens(L2_prev = state.L2_prev, Al_prev = state.Aly_prev, dist_from_prev = t)
                F_system = Formulas.F_system(F1 = F_system, F2 = F, distance = t)

            alx = Formulas.Al(A_phys, sfpx, Aeff)
            aly = Formulas.Al(A_phys, sfpy, Aeff)

            diff_lim = Formulas.diff_lim(L2, A_phys, Aeff, lamda)
            sfx = Formulas.sf(M, state.sx, diff_lim)
            sfy = Formulas.sf(M, state.sy, diff_lim)
            slx = Formulas.sl(M, state.sx)
            sly = Formulas.sl(M, state.sy)
            #diff_lim = Formulas.diff_lim(L2, A_phys, Aeff, lamda)

            ''' Поменять расчёт для сценария sigma'''
            T = Formulas.transmission(A_phys, alx, aly, sfpx, sfpy, mu, d)

            L_total_dist = abs(L1) + abs(L2)
            if is_first:
                sb_x = math.sqrt((L_total_dist * state.wx)**2 + state.sx**2)
                sb_y = math.sqrt((L_total_dist * state.wy)**2 + state.sy**2)
            else:
                sb_x = Formulas.beamsize_at_distance(alx, L2, L_total_dist, sfx)
                sb_y = Formulas.beamsize_at_distance(aly, L2, L_total_dist, sfy)
            G = Formulas.gain(T, sb_x, sb_y, sfx, sfy)

            NA = Formulas.numerical_aperture(Aeff, F)
            state.NA_current_block = NA
            state.Aeff_current_block = Aeff_sys

            #Обновление состояния для следующей итерации
            new_wx = state.wx# - alx/F #под вопросом правильность
            new_wy = state.wy# - aly/F

            state.T_current_block *= T
            state.G_current_block *= G #= math.sqrt(state.G_current_block**2 + G**2)

            new_M_total = state.M_total * M
            new_T_total = state.T_total * T
            #new_G_total = state.G_total * G

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
                'R': R,
                'L1': L1,
                'L2': L2,
                'F': F,
                'F_system': F_system,
                'sx_fwhm': state.sx,
                'sy_fwhm': state.sy,
                'sfpx': sfpx,
                'sfpy': sfpy,
                'alx': alx,
                'aly': aly,
                'slx': slx,
                'sly': sly,
                'diff_lim': diff_lim, 
                'sfx': sfx,
                'sfy': sfy,
                'T': T,
                'T_block': state.T_current_block,
                'T_total': new_T_total,
                'M': M,
                'M_total': new_M_total,
                'G': G,
                'G_total': state.G_current_block,

                'NA': NA,
                'NA_block': state.NA_current_block,
                'Aeff': Aeff,
                'Aeff_total': Aeff_sys,
                'Aeff_block': state.Aeff_current_block,
                # calculated only for last lens
                'dof_x': 0.0,
                'dof_y': 0.0, 
                'symmetry_dist': 0.0,
                'symm_beam_size_x': 0.0,
                'symm_beam_size_y': 0.0,
                'tf_type': lens_conf.get('tf_type', 'air')
            }

            # === ПРОСТАВЛЯЕМ is_first_in_tf и is_first_in_block ===
            is_first_in_tf = (i == 0) or (i > 0 and lens_config[i - 1]['tf_name'] != lens_conf['tf_name'])
            is_first_in_block = (i == 0) or (i > 0 and lens_config[i - 1]['block_index'] != lens_conf['block_index'])

            # === ПРОСТАВЛЯЕМ is_last_in_block и is_last_in_tf ===
            is_last_in_block = (i == len(lens_config) - 1) or (i < len(lens_config) - 1 and lens_config[i + 1]['block_index'] != lens_conf['block_index'])
            is_last_in_tf = (i == len(lens_config) - 1) or (i < len(lens_config) - 1 and lens_config[i + 1]['tf_name'] != lens_conf['tf_name'])

            result_data['is_first_in_tf'] = is_first_in_tf
            result_data['is_first_in_block'] = is_first_in_block
            result_data['is_last_in_block'] = is_last_in_block
            result_data['is_last_in_tf'] = is_last_in_tf

            if lens_conf.get('is_last_in_tf', False):
                state.T_blocks.append(state.T_current_block)
                state.G_blocks.append(state.G_current_block)
                state.NA_blocks.append(state.NA_current_block)
                state.Aeff_blocks.append(state.Aeff_current_block)
                dof_x = Formulas.dof(L2, sfx, alx)
                dof_y = Formulas.dof(L2, sfy, aly)
                result_data['dof_x'] = dof_x
                result_data['dof_y'] = dof_y

            # Создаём объект
            res = LensResult(**result_data)
            results.append(res)

            #Обновление state
            state.z += t
            #state.wx = new_wx
            #state.wy = new_wy
            state.sx = slx
            state.sy = sly
            state.M_total *= M
            state.T_total *= T
            state.G_total *= G#new_G_total #подумать над правильностью Formulas.gain_total(current_G_total, G)
            
            state.L2_prev = L2
            state.Alx_prev = alx
            state.Aly_prev = aly
            state.Aeff_prev_total = Aeff_sys

            # Внутри цикла по lens_conf:
            R = lens_conf['R']
            delta = lens_conf['delta']
            p = lens_conf['p']
            mu = lens_conf['mu']

        if results:
            last = results[-1]

            # === NA для последней линзы ===
            Aeff_last = Formulas.Aeff_single_lens(last.F, delta, mu)  # нужно передать актуальные delta, mu
            NA_last = Formulas.numerical_aperture(Aeff_last, last.F)

            # === k-коэффициент ===
            k = 0.01 #cltkfnm 

            # === DoF ===
            num_ap = NA_last
            if num_ap != 0:
                dof_x = Formulas.dof(last.L2, last.sfx, last.alx)
                dof_y = Formulas.dof(last.L2, last.sfy, last.aly)
            else:
                dof_x = 0.0
                dof_y = 0.0

            # === Symmetry ===
            try:
                sym_dist = Formulas.symmetry_dist(last.L2, last.sfy, last.sfx, last.alx, last.aly, k)
            except:
                sym_dist = 0.0

            try:
                sym_size_x = Formulas.beamsize_at_distance(last.alx, last.L2, sym_dist, last.sfx)
                sym_size_y = Formulas.beamsize_at_distance(last.aly, last.L2, sym_dist, last.sfy)
            except:
                sym_size_x, sym_size_y = 0.0, 0.0

            # === Обновляем только последний элемент ===
            last.dof_x, last.dof_y = dof_x, dof_y
            last.symmetry_dist = sym_dist
            last.symm_beam_size_x, last.symm_beam_size_y = sym_size_x, sym_size_y

        return results, state