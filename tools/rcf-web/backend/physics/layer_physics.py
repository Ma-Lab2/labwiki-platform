"""
Layer physics functions for energy deposition and transport

These functions calculate energy loss and particle stopping positions
as particles traverse different material layers.

Author: Tan Song
"""

import math as mt
import numpy as np
from physics.stopping_power import (
    s_Cu, s_Cr,
    s_EBT1_1, s_EBT1_2, s_EBT2_1, s_EBT2_2,
    s_HD1_1, s_HD1_2, s_HD1_3, s_HD1_4,
    s_HD2_1, s_HD2_2, s_HD2_3
)
from physics.stopping_power_bethe import s_AL_bethe
from config import (
    EBT1_LAYERS, EBT2_LAYERS, EBT2_CUTOFF_LAYER,
    HD1_LAYERS, HD1_CUTOFF_LAYER, HD2_LAYERS
)
from physics.material_registry import Material, registry


# ============================================================================
# Generic Passive Layer (for PSTAR materials)
# ============================================================================

def generic_passive_layer(Ein, thickness_um, material, path_factor=1.0):
    """
    Generic passive layer calculation using Material object

    This function can handle any material registered in the material registry,
    using tabulated stopping power data from PSTAR.

    Args:
        Ein: Input energy (MeV)
        thickness_um: Material thickness (μm)
        material: Material object (from material_registry)
        path_factor: Path length multiplier for oblique incidence (default=1.0)

    Returns:
        tuple: (Eout, stop_position, energy_deposited)
            - Eout: Output energy (MeV)
            - stop_position: Position where particle stopped (μm), or thickness if penetrated
            - energy_deposited: Total energy deposited in layer (MeV)
    """
    thickness_eff = thickness_um * path_factor
    E = Ein
    stop_pos = 0.0
    edep = 0.0

    # Integer and fractional parts
    whole_steps = int(thickness_eff)
    frac_step = thickness_eff - whole_steps

    # Step through whole micrometers
    for i in range(whole_steps):
        if E <= 0:
            stop_pos = i
            break

        dE = material.dE_per_um(E)
        E -= dE
        edep += dE

        if E <= 0:
            stop_pos = i + 1
            E = 0
            break
    else:
        # Particle penetrated all whole steps
        stop_pos = whole_steps

    # Handle fractional step
    if E > 0 and frac_step > 0:
        dE = material.dE_per_um(E) * frac_step
        E -= dE
        edep += dE
        stop_pos += frac_step

        if E < 0:
            E = 0

    Eout = max(0.0, E)
    edep = Ein - Eout

    return Eout, stop_pos, edep


# ============================================================================
# Passive Material Layers (Al, Cu, Cr)
# ============================================================================

def Al_layer(Ein, thickness_Al, path_factor=1.0):
    """
    Calculate energy after passing through aluminum layer

    Automatically uses PSTAR data if available, falls back to Bethe-Bloch formula.

    Args:
        Ein: Input energy (MeV)
        thickness_Al: Aluminum thickness (μm)
        path_factor: Path length multiplier for oblique incidence (default=1.0)

    Returns:
        Eout: Output energy (MeV)
    """
    # 优先使用PSTAR数据（高精度）
    if registry.exists('Al'):
        al_material = registry.get('Al')
        Eout, _, _ = generic_passive_layer(Ein, thickness_Al, al_material, path_factor)
        return Eout

    # 使用Bethe-Bloch理论公式（误差<10%，替代旧拟合65-90%误差）
    thickness_eff = thickness_Al * path_factor
    E = Ein

    # Integer and fractional parts
    whole_steps = int(thickness_eff)
    frac_step = thickness_eff - whole_steps

    # Step through whole micrometers
    for i in range(whole_steps):
        if E <= 0:
            break
        dE = s_AL_bethe(E)
        E -= dE
        if E < 0:
            E = 0
            break

    # Handle fractional step
    if E > 0 and frac_step > 0:
        dE = s_AL_bethe(E) * frac_step
        E -= dE
        if E < 0:
            E = 0

    Eout = max(0.0, E)
    return Eout

def Cr_layer(Ein, thickness, path_factor=1.0):
    """
    Calculate energy after passing through chromium layer

    Args:
        Ein: Input energy (MeV)
        thickness: Chromium thickness (μm)
        path_factor: Path length multiplier for oblique incidence (default=1.0)

    Returns:
        Eout: Output energy (MeV)
        Cr_stop_pos: Stopping position (layer index)
        edep: Energy deposited (MeV)
    """
    thickness_eff = thickness * path_factor
    E_init = Ein
    ST_Cr = np.empty(shape=[0, 1])
    E = np.empty(shape=[0, 1])
    thick = mt.floor(thickness_eff)

    for i in range(thick):
        ST_temp = s_Cr(Ein)
        if ST_temp < 0:
            break
        else:
            ST_Cr = np.append(ST_Cr, ST_temp)
            Ein = Ein - s_Cr(Ein)
            E = np.append(E, Ein)

    n = np.argmax(ST_Cr) if ST_Cr.size > 0 else 0
    Cr_stop_pos = n

    if Ein > 0 and len(E) >= thick:
        Eout = E[thick - 1]
        edep = E_init - Eout
    else:
        Eout = Ein
        edep = E_init if Ein <= 0 else E_init - Ein

    return Eout, Cr_stop_pos, edep


def Cu_layer(Ein, thickness, path_factor=1.0):
    """
    Calculate energy after passing through copper layer

    Args:
        Ein: Input energy (MeV)
        thickness: Copper thickness (μm)
        path_factor: Path length multiplier for oblique incidence (default=1.0)

    Returns:
        Eout: Output energy (MeV)
        Cu_stop_pos: Stopping position (layer index)
        edep: Energy deposited (MeV)
    """
    thickness_eff = thickness * path_factor
    E_init = Ein
    ST_Cu = np.empty(shape=[0, 1])
    E = np.empty(shape=[0, 1])
    thick = mt.floor(thickness_eff)

    for i in range(thick):
        ST_temp = s_Cu(Ein)
        if ST_temp < 0:
            break
        else:
            ST_Cu = np.append(ST_Cu, ST_temp)
            Ein = Ein - s_Cu(Ein)
            E = np.append(E, Ein)

    n = np.argmax(ST_Cu) if ST_Cu.size > 0 else 0
    Cu_stop_pos = n

    if Ein > 0 and len(E) >= thick:
        Eout = E[thick - 1]
        edep = E_init - Eout
    else:
        Eout = Ein
        edep = E_init if Ein <= 0 else E_init - Ein

    return Eout, Cu_stop_pos, edep


# ============================================================================
# RCF Detector Layers (EBT, HD)
# ============================================================================

def EBT1_layer(Ein, path_factor=1.0):
    """
    Calculate energy after passing through EBT protective layer 1

    Args:
        Ein: Input energy (MeV)
        path_factor: Path length multiplier for oblique incidence (default=1.0)

    Returns:
        Eout: Output energy (MeV)
    """
    N_eff = max(1, int(round(EBT1_LAYERS * path_factor)))
    ST_EBT1 = np.empty(shape=[0, 1])
    E = np.empty(shape=[0, 1])

    for i in range(N_eff):
        if Ein > 0.125:
            ST_EBT1 = np.append(ST_EBT1, s_EBT1_1(Ein))
            Ein = Ein - s_EBT1_1(Ein)
            E = np.append(E, Ein)
        else:
            if Ein > 0:
                ST_EBT1 = np.append(ST_EBT1, s_EBT1_2(Ein))
                Ein = Ein - s_EBT1_2(Ein)
                E = np.append(E, Ein)
            else:
                break

    Eout = Ein
    return Eout


def EBT2_layer(Ein, path_factor=1.0):
    """
    Calculate energy and deposition in EBT active layer 2

    Args:
        Ein: Input energy (MeV)
        path_factor: Path length multiplier for oblique incidence (default=1.0)

    Returns:
        Eout: Output energy (MeV)
        EBT2_stop_pos: Stopping position (layer index)
        edep: Energy deposited (MeV)
    """
    N_eff = max(1, int(round(EBT2_LAYERS * path_factor)))
    N_cutoff = int(round(EBT2_CUTOFF_LAYER * path_factor))

    E_init = Ein
    ST_EBT2 = np.empty(shape=[0, 1])
    E = np.empty(shape=[0, 1])

    # Validate input energy
    if Ein <= 0:
        return 0, 0, 0

    for i in range(N_eff):
        if Ein <= 0:
            break

        if Ein >= 0.15:
            try:
                stopping_power = s_EBT2_1(Ein)
                if stopping_power > 0:
                    ST_EBT2 = np.append(ST_EBT2, stopping_power)
                    Ein = Ein - stopping_power
                    E = np.append(E, Ein)
                else:
                    break
            except:
                break
        else:
            if Ein > 0:
                try:
                    stopping_power = s_EBT2_2(Ein)
                    if stopping_power > 0:
                        ST_EBT2 = np.append(ST_EBT2, stopping_power)
                        Ein = Ein - stopping_power
                        E = np.append(E, Ein)
                    else:
                        break
                except:
                    break
            else:
                break

    # Safe handling of empty arrays
    if ST_EBT2.size == 0 or len(ST_EBT2) == 0:
        EBT2_stop_pos = 0
        edep = 0
        Eout = max(0, Ein) if Ein > 0 else 0
    else:
        # Double check to prevent empty array argmax call
        if ST_EBT2.size > 0:
            n = np.argmax(ST_EBT2)
            EBT2_stop_pos = n
        else:
            EBT2_stop_pos = 0

        if Ein > 0 and len(E) >= N_eff:
            Eout = E[N_eff - 1]
            edep = E_init - Eout
        elif len(E) > 0:
            Eout = E[-1]  # Use last valid value
            edep = E_init - Eout
        else:
            Eout = max(0, Ein)
            edep = E_init - Eout

    return max(0, Eout), EBT2_stop_pos, max(0, edep)


def HD1_layer(Ein, path_factor=1.0):
    """
    Calculate energy and deposition in HD active layer 1

    Args:
        Ein: Input energy (MeV)
        path_factor: Path length multiplier for oblique incidence (default=1.0)

    Returns:
        Eout: Output energy (MeV)
        HD1_stop_pos: Stopping position (layer index)
        edep: Energy deposited (MeV)
    """
    N_eff = max(1, int(round(HD1_LAYERS * path_factor)))
    N_cutoff = int(round(HD1_CUTOFF_LAYER * path_factor))

    E_init = Ein
    ST_HD1 = np.empty(shape=[0, 1])
    E = np.empty(shape=[0, 1])

    # Validate input energy
    if Ein <= 0:
        return 0, 0, 0

    for i in range(N_eff):
        if Ein <= 0:
            break

        try:
            if Ein < 10:
                if Ein > 1:
                    stopping_power = s_HD1_3(Ein)
                    if stopping_power > 0:
                        ST_HD1 = np.append(ST_HD1, stopping_power)
                        Ein = Ein - stopping_power
                        E = np.append(E, Ein)
                    else:
                        break
                else:
                    if Ein > 0.15:
                        stopping_power = s_HD1_1(Ein)
                        if stopping_power > 0:
                            ST_HD1 = np.append(ST_HD1, stopping_power)
                            Ein = Ein - stopping_power
                            E = np.append(E, Ein)
                        else:
                            break
                    else:
                        if Ein > 0:
                            stopping_power = s_HD1_2(Ein)
                            if stopping_power > 0:
                                ST_HD1 = np.append(ST_HD1, stopping_power)
                                Ein = Ein - stopping_power
                                E = np.append(E, Ein)
                            else:
                                break
                        else:
                            break
            else:
                stopping_power = s_HD1_4(Ein)
                if stopping_power > 0:
                    ST_HD1 = np.append(ST_HD1, stopping_power)
                    Ein = Ein - stopping_power
                    E = np.append(E, Ein)
                else:
                    break
        except Exception as e:
            print(f"Warning: HD1 calculation error at iteration {i}: {e}")
            break

    # Safe handling of empty arrays
    if ST_HD1.size == 0 or len(ST_HD1) == 0:
        HD1_stop_pos = 0
        edep = 0
        Eout = max(0, Ein) if Ein > 0 else 0
    else:
        # Double check to prevent empty array argmax call
        if ST_HD1.size > 0:
            n = np.argmax(ST_HD1)
            HD1_stop_pos = n
        else:
            HD1_stop_pos = 0

        if Ein > 0 and len(E) > N_cutoff:
            Eout = E[N_cutoff]
            edep = E_init - Eout
        elif len(E) > 0:
            Eout = E[-1]  # Use last valid value
            edep = E_init - Eout
        else:
            Eout = max(0, Ein)
            edep = E_init - Eout

    return max(0, Eout), HD1_stop_pos, max(0, edep)


def HD2_layer(Ein, path_factor=1.0):
    """
    Calculate energy after passing through HD backing layer 2

    Args:
        Ein: Input energy (MeV)
        path_factor: Path length multiplier for oblique incidence (default=1.0)

    Returns:
        Eout: Output energy (MeV)
    """
    N_eff = max(1, int(round(HD2_LAYERS * path_factor)))
    ST_HD2 = np.empty(shape=[0, 1])
    E = np.empty(shape=[0, 1])

    for i in range(N_eff):
        if Ein > 10:
            ST_HD2 = np.append(ST_HD2, s_HD2_3(Ein))
            Ein = Ein - s_HD2_3(Ein)
            E = np.append(E, Ein)
        else:
            if Ein >= 0.125:
                ST_HD2 = np.append(ST_HD2, s_HD2_2(Ein))
                Ein = Ein - s_HD2_2(Ein)
                E = np.append(E, Ein)
            else:
                if Ein > 0:
                    ST_HD2 = np.append(ST_HD2, s_HD2_1(Ein))
                    Ein = Ein - s_HD2_1(Ein)
                    E = np.append(E, Ein)
                else:
                    break

    Eout = Ein
    return Eout


# ============================================================================
# Legacy design function (kept for compatibility)
# ============================================================================

def design():
    """
    Legacy design function - kept for backward compatibility
    Not recommended for new code
    """
    EBT2_stop_pos_zoom = np.empty(shape=[0, 1])
    E = np.empty(shape=[0, 1])
    HD1pk_zoom = np.empty(shape=[0, 1])
    HD1_stop_pos_zoom = np.empty(shape=[0, 1])

    for Ein in np.arange(1, 10.1, 0.1):
        # 1
        Eout = Al_layer(Ein, 30)
        Eout = EBT1_layer(Eout)
        Eout, EBT2_stop_pos, _ = EBT2_layer(Eout)
        if EBT2_stop_pos <= 29:
            E = np.append(E, Ein)
            EBT2_stop_pos_zoom = np.append(EBT2_stop_pos_zoom, EBT2_stop_pos)

        Eout = EBT1_layer(Eout)

        # 2
        Eout, HD1pk, HD1_stop_pos = HD1_layer(Eout)
        if HD1pk <= 7 or HD1pk <= 7:
            E = np.append(E, Ein)
            HD1pk_zoom = np.append(HD1pk_zoom, HD1pk)
            EBT2_stop_pos_zoom = np.append(EBT2_stop_pos_zoom, HD1_stop_pos)

            Eout = HD2_layer(Eout)

    return E, EBT2_stop_pos_zoom


# ============================================================================
# 多离子支持函数 (Multi-Ion Support Functions)
# ============================================================================

# 延迟导入以避免循环依赖
_ion_module_loaded = False
_PROTON = None


def _ensure_ion_module():
    """确保离子模块已加载"""
    global _ion_module_loaded, _PROTON
    if not _ion_module_loaded:
        try:
            from physics.ion import PROTON
            _PROTON = PROTON
            _ion_module_loaded = True
        except ImportError:
            pass


def generic_passive_layer_ion(Ein_per_nucleon, thickness_um, material, ion=None,
                               path_factor=1.0):
    """
    Generic passive layer calculation for any ion using Material object

    任意离子穿过被动层的能量损失计算

    Args:
        Ein_per_nucleon: Input energy per nucleon (MeV/u)
        thickness_um: Material thickness (μm)
        material: Material object (from material_registry)
        ion: Ion object (from physics.ion), default is proton
        path_factor: Path length multiplier for oblique incidence (default=1.0)

    Returns:
        tuple: (Eout_per_nucleon, stop_position, energy_deposited_total)
            - Eout_per_nucleon: Output energy per nucleon (MeV/u)
            - stop_position: Position where particle stopped (μm)
            - energy_deposited_total: Total energy deposited (MeV)

    Example:
        >>> from physics.ion import CARBON12
        >>> from physics.material_registry import registry
        >>> al = registry.get('Al')
        >>> Eout, pos, edep = generic_passive_layer_ion(100, 500, al, CARBON12)
    """
    _ensure_ion_module()

    # 默认为质子
    if ion is None:
        ion = _PROTON
        if ion is None:
            # 如果离子模块未加载，回退到普通计算
            Eout, stop_pos, edep = generic_passive_layer(Ein_per_nucleon, thickness_um,
                                                          material, path_factor)
            return Eout, stop_pos, edep

    # 对于质子，直接使用原有函数
    if ion.Z == 1 and ion.A == 1:
        Eout, stop_pos, edep = generic_passive_layer(Ein_per_nucleon, thickness_um,
                                                      material, path_factor)
        return Eout, stop_pos, edep

    # 重离子计算
    thickness_eff = thickness_um * path_factor
    E = Ein_per_nucleon  # MeV/u
    stop_pos = 0.0
    edep_per_nucleon = 0.0

    # 整数和小数部分
    whole_steps = int(thickness_eff)
    frac_step = thickness_eff - whole_steps

    # 逐微米步进
    for i in range(whole_steps):
        if E <= 0:
            stop_pos = i
            break

        # 获取质子阻止本领
        dE_proton = material.dE_per_um(E)

        # 使用 Z_eff² 缩放得到离子阻止本领
        ratio = ion.stopping_power_ratio(E)
        dE_ion = dE_proton * ratio

        # 每核子能量损失
        dE_per_nucleon = dE_ion / ion.A

        E -= dE_per_nucleon
        edep_per_nucleon += dE_per_nucleon

        if E <= 0:
            stop_pos = i + 1
            E = 0
            break
    else:
        stop_pos = whole_steps

    # 处理小数步
    if E > 0 and frac_step > 0:
        dE_proton = material.dE_per_um(E)
        ratio = ion.stopping_power_ratio(E)
        dE_ion = dE_proton * ratio * frac_step
        dE_per_nucleon = dE_ion / ion.A

        E -= dE_per_nucleon
        edep_per_nucleon += dE_per_nucleon
        stop_pos += frac_step

        if E < 0:
            E = 0

    Eout = max(0.0, E)

    # 使用能量守恒计算总沉积能量（更简单且更鲁棒）
    # Total deposited energy using energy conservation (simpler and more robust)
    edep_total = (Ein_per_nucleon - Eout) * ion.A

    # 仅在差异超过5%时发出警告（1-2%的差异是数值迭代的正常误差）
    # Only warn if discrepancy exceeds 5% (1-2% is normal numerical error from iteration)
    edep_accumulated = edep_per_nucleon * ion.A
    if abs(edep_total - edep_accumulated) > 0.05 * max(edep_total, 0.001):
        import warnings
        warnings.warn(
            f"Energy accounting discrepancy: conservation={edep_total:.4f}, "
            f"accumulated={edep_accumulated:.4f} MeV (>{5}%)",
            RuntimeWarning
        )

    return Eout, stop_pos, edep_total


def Al_layer_ion(Ein_per_nucleon, thickness_Al, ion=None, path_factor=1.0):
    """
    Calculate energy after ion passes through aluminum layer

    任意离子穿过铝层的能量计算

    Args:
        Ein_per_nucleon: Input energy per nucleon (MeV/u)
        thickness_Al: Aluminum thickness (μm)
        ion: Ion object (default: proton)
        path_factor: Path length multiplier for oblique incidence

    Returns:
        Eout_per_nucleon: Output energy per nucleon (MeV/u)

    Example:
        >>> from physics.ion import CARBON12
        >>> Eout = Al_layer_ion(100, 500, CARBON12)  # C12 at 100 MeV/u
    """
    _ensure_ion_module()

    if ion is None:
        ion = _PROTON

    # 对于质子，使用原有函数
    if ion is None or (ion.Z == 1 and ion.A == 1):
        return Al_layer(Ein_per_nucleon, thickness_Al, path_factor)

    # 尝试使用 PSTAR 材料
    if registry.exists('Al'):
        al_material = registry.get('Al')
        Eout, _, _ = generic_passive_layer_ion(Ein_per_nucleon, thickness_Al,
                                                al_material, ion, path_factor)
        return Eout

    # 回退到 Bethe-Bloch 公式
    from physics.stopping_power_bethe import s_Al_ion

    thickness_eff = thickness_Al * path_factor
    E = Ein_per_nucleon  # MeV/u

    whole_steps = int(thickness_eff)
    frac_step = thickness_eff - whole_steps

    for i in range(whole_steps):
        if E <= 0:
            break

        # 获取离子阻止本领 (MeV/μm)
        dE_ion = s_Al_ion(E, ion)

        # 每核子能量损失
        dE_per_nucleon = dE_ion / ion.A

        E -= dE_per_nucleon
        if E < 0:
            E = 0
            break

    # 小数步
    if E > 0 and frac_step > 0:
        dE_ion = s_Al_ion(E, ion) * frac_step
        dE_per_nucleon = dE_ion / ion.A
        E -= dE_per_nucleon
        if E < 0:
            E = 0

    return max(0.0, E)


def Cu_layer_ion(Ein_per_nucleon, thickness, ion=None, path_factor=1.0):
    """
    Calculate energy after ion passes through copper layer

    任意离子穿过铜层的能量计算

    Args:
        Ein_per_nucleon: Input energy per nucleon (MeV/u)
        thickness: Copper thickness (μm)
        ion: Ion object (default: proton)
        path_factor: Path length multiplier

    Returns:
        tuple: (Eout_per_nucleon, Cu_stop_pos, edep_total)
    """
    _ensure_ion_module()

    if ion is None:
        ion = _PROTON

    # 对于质子，使用原有函数
    if ion is None or (ion.Z == 1 and ion.A == 1):
        Eout, stop_pos, edep = Cu_layer(Ein_per_nucleon, thickness, path_factor)
        return Eout, stop_pos, edep

    # 使用阻止本领缩放
    from physics.stopping_power_bethe import stopping_power_ion_simple

    thickness_eff = thickness * path_factor
    E_init = Ein_per_nucleon
    E = Ein_per_nucleon

    thick = int(thickness_eff)
    stop_pos = 0
    max_dE = 0

    for i in range(thick):
        if E <= 0:
            break

        # 获取质子阻止本领
        dE_proton = s_Cu(E)
        if dE_proton < 0:
            break

        # 缩放到离子
        ratio = ion.stopping_power_ratio(E)
        dE_ion = dE_proton * ratio
        dE_per_nucleon = dE_ion / ion.A

        if dE_ion > max_dE:
            max_dE = dE_ion
            stop_pos = i

        E -= dE_per_nucleon
        if E < 0:
            E = 0
            break

    Eout = max(0.0, E)
    edep_total = (E_init - Eout) * ion.A

    return Eout, stop_pos, edep_total


def Cr_layer_ion(Ein_per_nucleon, thickness, ion=None, path_factor=1.0):
    """
    Calculate energy after ion passes through chromium layer

    任意离子穿过铬层的能量计算

    Args:
        Ein_per_nucleon: Input energy per nucleon (MeV/u)
        thickness: Chromium thickness (μm)
        ion: Ion object (default: proton)
        path_factor: Path length multiplier

    Returns:
        tuple: (Eout_per_nucleon, Cr_stop_pos, edep_total)
    """
    _ensure_ion_module()

    if ion is None:
        ion = _PROTON

    # 对于质子，使用原有函数
    if ion is None or (ion.Z == 1 and ion.A == 1):
        Eout, stop_pos, edep = Cr_layer(Ein_per_nucleon, thickness, path_factor)
        return Eout, stop_pos, edep

    thickness_eff = thickness * path_factor
    E_init = Ein_per_nucleon
    E = Ein_per_nucleon

    thick = int(thickness_eff)
    stop_pos = 0
    max_dE = 0

    for i in range(thick):
        if E <= 0:
            break

        dE_proton = s_Cr(E)
        if dE_proton < 0:
            break

        ratio = ion.stopping_power_ratio(E)
        dE_ion = dE_proton * ratio
        dE_per_nucleon = dE_ion / ion.A

        if dE_ion > max_dE:
            max_dE = dE_ion
            stop_pos = i

        E -= dE_per_nucleon
        if E < 0:
            E = 0
            break

    Eout = max(0.0, E)
    edep_total = (E_init - Eout) * ion.A

    return Eout, stop_pos, edep_total


# ============================================================================
# 离子版 RCF 探测器层 (Ion versions of RCF detector layers)
# ============================================================================

def EBT2_layer_ion(Ein_per_nucleon, ion=None, path_factor=1.0):
    """
    Calculate energy and deposition in EBT active layer for ion

    任意离子在 EBT 活性层中的能量沉积

    Args:
        Ein_per_nucleon: Input energy per nucleon (MeV/u)
        ion: Ion object (default: proton)
        path_factor: Path length multiplier

    Returns:
        tuple: (Eout_per_nucleon, stop_pos, edep_total)

    Note:
        对于重离子，由于更高的 LET（线性能量转移），
        RCF 的响应可能不是线性的。需要额外的校准数据。
    """
    _ensure_ion_module()

    if ion is None:
        ion = _PROTON

    # 对于质子，使用原有函数
    if ion is None or (ion.Z == 1 and ion.A == 1):
        return EBT2_layer(Ein_per_nucleon, path_factor)

    N_eff = max(1, int(round(EBT2_LAYERS * path_factor)))
    E_init = Ein_per_nucleon
    E = Ein_per_nucleon

    if E <= 0:
        return 0, 0, 0

    stop_pos = 0
    max_dE = 0

    for i in range(N_eff):
        if E <= 0:
            break

        # 选择合适的质子阻止本领函数
        if E >= 0.15:
            try:
                dE_proton = s_EBT2_1(E)
            except:
                break
        else:
            if E > 0:
                try:
                    dE_proton = s_EBT2_2(E)
                except:
                    break
            else:
                break

        if dE_proton <= 0:
            break

        # 缩放到离子
        ratio = ion.stopping_power_ratio(E)
        dE_ion = dE_proton * ratio
        dE_per_nucleon = dE_ion / ion.A

        if dE_ion > max_dE:
            max_dE = dE_ion
            stop_pos = i

        E -= dE_per_nucleon
        if E < 0:
            E = 0
            break

    Eout = max(0.0, E)
    edep_total = (E_init - Eout) * ion.A

    return Eout, stop_pos, edep_total


def HD1_layer_ion(Ein_per_nucleon, ion=None, path_factor=1.0):
    """
    Calculate energy and deposition in HD active layer for ion

    任意离子在 HD 活性层中的能量沉积

    Args:
        Ein_per_nucleon: Input energy per nucleon (MeV/u)
        ion: Ion object (default: proton)
        path_factor: Path length multiplier

    Returns:
        tuple: (Eout_per_nucleon, stop_pos, edep_total)
    """
    _ensure_ion_module()

    if ion is None:
        ion = _PROTON

    if ion is None or (ion.Z == 1 and ion.A == 1):
        return HD1_layer(Ein_per_nucleon, path_factor)

    N_eff = max(1, int(round(HD1_LAYERS * path_factor)))
    N_cutoff = int(round(HD1_CUTOFF_LAYER * path_factor))

    E_init = Ein_per_nucleon
    E = Ein_per_nucleon

    if E <= 0:
        return 0, 0, 0

    stop_pos = 0
    max_dE = 0
    E_at_cutoff = E

    for i in range(N_eff):
        if E <= 0:
            break

        # 选择合适的质子阻止本领函数
        try:
            if E >= 10:
                dE_proton = s_HD1_4(E)
            elif E > 1:
                dE_proton = s_HD1_3(E)
            elif E > 0.15:
                dE_proton = s_HD1_1(E)
            else:
                dE_proton = s_HD1_2(E)
        except:
            break

        if dE_proton <= 0:
            break

        ratio = ion.stopping_power_ratio(E)
        dE_ion = dE_proton * ratio
        dE_per_nucleon = dE_ion / ion.A

        if dE_ion > max_dE:
            max_dE = dE_ion
            stop_pos = i

        E -= dE_per_nucleon

        # 记录 cutoff 位置的能量
        if i == N_cutoff:
            E_at_cutoff = max(0, E)

        if E < 0:
            E = 0
            break

    # 使用 cutoff 位置的能量作为输出
    Eout = E_at_cutoff if len(range(N_eff)) > N_cutoff else max(0.0, E)
    edep_total = (E_init - Eout) * ion.A

    return Eout, stop_pos, edep_total


def EBT1_layer_ion(Ein_per_nucleon, ion=None, path_factor=1.0):
    """
    Calculate energy after ion passes through EBT protective layer

    任意离子穿过 EBT 保护层

    Args:
        Ein_per_nucleon: Input energy per nucleon (MeV/u)
        ion: Ion object (default: proton)
        path_factor: Path length multiplier

    Returns:
        Eout_per_nucleon: Output energy per nucleon (MeV/u)
    """
    _ensure_ion_module()

    if ion is None:
        ion = _PROTON

    if ion is None or (ion.Z == 1 and ion.A == 1):
        return EBT1_layer(Ein_per_nucleon, path_factor)

    N_eff = max(1, int(round(EBT1_LAYERS * path_factor)))
    E = Ein_per_nucleon

    for i in range(N_eff):
        if E <= 0:
            break

        if E > 0.125:
            dE_proton = s_EBT1_1(E)
        else:
            if E > 0:
                dE_proton = s_EBT1_2(E)
            else:
                break

        ratio = ion.stopping_power_ratio(E)
        dE_ion = dE_proton * ratio
        dE_per_nucleon = dE_ion / ion.A

        E -= dE_per_nucleon
        if E < 0:
            E = 0
            break

    return max(0.0, E)


def HD2_layer_ion(Ein_per_nucleon, ion=None, path_factor=1.0):
    """
    Calculate energy after ion passes through HD backing layer

    任意离子穿过 HD 衬底层

    Args:
        Ein_per_nucleon: Input energy per nucleon (MeV/u)
        ion: Ion object (default: proton)
        path_factor: Path length multiplier

    Returns:
        Eout_per_nucleon: Output energy per nucleon (MeV/u)
    """
    _ensure_ion_module()

    if ion is None:
        ion = _PROTON

    if ion is None or (ion.Z == 1 and ion.A == 1):
        return HD2_layer(Ein_per_nucleon, path_factor)

    N_eff = max(1, int(round(HD2_LAYERS * path_factor)))
    E = Ein_per_nucleon

    for i in range(N_eff):
        if E <= 0:
            break

        if E > 10:
            dE_proton = s_HD2_3(E)
        elif E >= 0.125:
            dE_proton = s_HD2_2(E)
        else:
            if E > 0:
                dE_proton = s_HD2_1(E)
            else:
                break

        ratio = ion.stopping_power_ratio(E)
        dE_ion = dE_proton * ratio
        dE_per_nucleon = dE_ion / ion.A

        E -= dE_per_nucleon
        if E < 0:
            E = 0
            break

    return max(0.0, E)


# ============================================================================
# 通用层调度函数 (Generic layer dispatch function)
# ============================================================================

def calculate_layer_ion(Ein_per_nucleon, layer_type, thickness, ion=None,
                        path_factor=1.0, material=None):
    """
    Calculate energy loss through any layer type for any ion

    通用层计算函数 - 支持任意离子穿过任意层类型

    Args:
        Ein_per_nucleon: Input energy per nucleon (MeV/u)
        layer_type: Layer type string ('Al', 'Cu', 'Cr', 'EBT', 'HD', or PSTAR material name)
        thickness: Layer thickness (μm), ignored for RCF layers
        ion: Ion object (default: proton)
        path_factor: Path length multiplier for oblique incidence
        material: Optional Material object for PSTAR materials

    Returns:
        tuple: (Eout_per_nucleon, stop_pos, edep_total)
            - For passive layers: returns energy loss info
            - For RCF layers: returns detector response info

    Example:
        >>> from physics.ion import CARBON12
        >>> result = calculate_layer_ion(100, 'Al', 500, CARBON12)
    """
    _ensure_ion_module()

    if ion is None:
        ion = _PROTON

    is_proton = (ion is None) or (ion.Z == 1 and ion.A == 1)

    # 被动材料层
    if layer_type == 'Al':
        Eout = Al_layer_ion(Ein_per_nucleon, thickness, ion, path_factor)
        edep = (Ein_per_nucleon - Eout) * (ion.A if ion else 1)
        return Eout, 0, edep

    elif layer_type == 'Cu':
        return Cu_layer_ion(Ein_per_nucleon, thickness, ion, path_factor)

    elif layer_type == 'Cr':
        return Cr_layer_ion(Ein_per_nucleon, thickness, ion, path_factor)

    # RCF 探测器层
    elif layer_type in ('EBT', 'EBT2'):
        Eout = EBT1_layer_ion(Ein_per_nucleon, ion, path_factor)
        return EBT2_layer_ion(Eout, ion, path_factor)

    elif layer_type in ('HD', 'HD1'):
        result = HD1_layer_ion(Ein_per_nucleon, ion, path_factor)
        Eout = HD2_layer_ion(result[0], ion, path_factor)
        return (Eout, result[1], result[2])

    # PSTAR 材料
    elif material is not None:
        return generic_passive_layer_ion(Ein_per_nucleon, thickness, material,
                                          ion, path_factor)

    # 尝试从注册表获取材料
    elif registry.exists(layer_type):
        mat = registry.get(layer_type)
        return generic_passive_layer_ion(Ein_per_nucleon, thickness, mat,
                                          ion, path_factor)

    else:
        raise ValueError(f"Unknown layer type: {layer_type}")
