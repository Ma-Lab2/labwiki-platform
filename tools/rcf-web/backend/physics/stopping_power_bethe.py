"""
Bethe-Bloch formula for charged particle stopping power

This module implements the Bethe-Bloch formula for:
1. Protons in aluminum (original functionality)
2. Arbitrary ions in any material (new multi-ion support)

物理原理:
- 对于重离子，阻止本领与 Z_eff² 成正比
- 有效电荷 Z_eff 在低能时小于核电荷（电子俘获效应）
- 包含 Barkas 修正和 Bloch 修正用于重离子

Note: PSTAR uses Bethe formula + corrections for E > 1 MeV, so this gives
      similar results to PSTAR in that range.

Author: Based on standard physics formulas
Extended: Multi-ion support added 2024
"""

import math

# Physical constants
ELECTRON_MASS = 0.511  # MeV/c²
PROTON_MASS = 938.272  # MeV/c²
AVOGADRO = 6.022e23  # mol⁻¹
CLASSICAL_ELECTRON_RADIUS = 2.818e-13  # cm
FINE_STRUCTURE_CONSTANT = 1/137.036

# Aluminum properties
AL_Z = 13  # Atomic number
AL_A = 26.982  # Atomic mass (g/mol)
AL_DENSITY = 2.702  # g/cm³
AL_MEAN_EXCITATION = 166e-6  # I in MeV (166 eV)


def beta_gamma(E_kinetic):
    """
    Calculate relativistic β and γ from kinetic energy

    Args:
        E_kinetic: Kinetic energy in MeV

    Returns:
        (beta, gamma, beta_gamma)
    """
    gamma = 1 + E_kinetic / PROTON_MASS
    beta = math.sqrt(1 - 1/gamma**2)
    bg = beta * gamma
    return beta, gamma, bg


def bethe_bloch_simple(E_kinetic):
    """
    Simplified Bethe-Bloch formula for protons in aluminum

    Valid for E > 1 MeV (where relativistic corrections matter less)

    Formula:
        -dE/dx = K * (Z/A) * (1/β²) * [ln(2*me*c²*β²*γ²/I) - β²]

    where K = 4π*NA*re²*me*c²

    Args:
        E_kinetic: Proton kinetic energy in MeV

    Returns:
        Stopping power in MeV/μm
    """
    beta, gamma, bg = beta_gamma(E_kinetic)

    # Bethe constant K = 4π * NA * re² * me * c² (in MeV·cm²/mol)
    K = 0.307075  # MeV·cm²/mol (standard value)

    # Tmax: maximum energy transfer in single collision
    # Tmax = (2*me*c²*β²*γ²) / (1 + 2*γ*me/M + (me/M)²)
    # For protons (M >> me), approximately: Tmax ≈ 2*me*c²*β²*γ²

    beta2 = beta**2
    Tmax = 2 * ELECTRON_MASS * beta2 * gamma**2

    # Bethe formula (without density correction for now)
    term1 = (K * AL_Z / AL_A) * (1 / beta2)
    term2 = math.log(Tmax / AL_MEAN_EXCITATION) - beta2

    # Result in MeV·cm²/g
    dEdx_mass = term1 * term2

    # Convert to MeV/μm: multiply by density and convert units
    # MeV/μm = (MeV·cm²/g) × (g/cm³) × (1 cm / 10^4 μm)
    dEdx = dEdx_mass * AL_DENSITY * 1e-4

    return dEdx


def bethe_bloch_generic(E_kinetic, Z, A, I_eV, density, warn_low_energy=True):
    """
    通用Bethe-Bloch公式，支持任意材料

    Args:
        E_kinetic: 质子动能 (MeV)
        Z: 原子序数
        A: 原子质量 (g/mol)
        I_eV: 平均激发能 (eV)
        density: 材料密度 (g/cm³)
        warn_low_energy: 是否对低能量发出警告

    Returns:
        S/ρ 质量阻止本领 (MeV·cm²/g)
    """
    if E_kinetic < 1.0 and warn_low_energy:
        import warnings
        warnings.warn(
            f"Energy {E_kinetic} MeV is below recommended range (>1 MeV) for Bethe formula. "
            f"Consider using PSTAR data or empirical formulas.",
            RuntimeWarning
        )

    beta, gamma, bg = beta_gamma(E_kinetic)
    beta2 = beta**2

    K = 0.307075  # MeV·cm²/mol
    I_MeV = I_eV * 1e-6  # 转换eV到MeV

    # 最大能量转移
    Tmax = 2 * ELECTRON_MASS * beta2 * gamma**2

    # 主要Bethe项
    term1 = (K * Z / A) * (1 / beta2)
    term2 = 0.5 * math.log(2 * ELECTRON_MASS * beta2 * gamma**2 * Tmax / I_MeV**2) - beta2

    # 壳层修正（低能重要）
    shell_correction = 0  # 简化：E > 1 MeV时 C/Z ≈ 0

    # 密度效应修正（高能重要）
    # 使用简化的Sternheimer参数化
    if bg < 0.1:
        delta = 0
    elif bg < 10:
        X = math.log10(bg)
        # 简化的密度修正参数（适用于大多数材料）
        X0, X1 = 0.2, 3.0
        C_param = 3.0 + 2 * math.log(I_eV)
        a = 0.1
        m = 3.0

        if X < X0:
            delta = 0
        elif X < X1:
            delta = 2 * math.log(10) * X - C_param + a * (X1 - X)**m
        else:
            delta = 2 * math.log(10) * X - C_param
    else:
        # 高能近似
        delta = 2 * math.log(bg) - 0.1

    # 结果为MeV·cm²/g
    S_rho = term1 * (term2 - delta/2 - shell_correction/Z)

    return S_rho


def bethe_bloch_with_corrections(E_kinetic):
    """
    Bethe-Bloch formula with shell and density corrections

    This is closer to what PSTAR uses for E > 1 MeV

    Args:
        E_kinetic: Proton kinetic energy in MeV

    Returns:
        Stopping power in MeV/μm
    """
    beta, gamma, bg = beta_gamma(E_kinetic)
    beta2 = beta**2

    K = 0.307075  # MeV·cm²/mol

    # Maximum energy transfer
    Tmax = 2 * ELECTRON_MASS * beta2 * gamma**2

    # Main Bethe term
    term1 = (K * AL_Z / AL_A) * (1 / beta2)
    term2 = 0.5 * math.log(2 * ELECTRON_MASS * beta2 * gamma**2 * Tmax / AL_MEAN_EXCITATION**2) - beta2

    # Shell correction (important at low energies)
    # Simplified: C/Z ≈ 0 for E > 1 MeV
    shell_correction = 0

    # Density effect correction (important at high energies)
    # For aluminum, becomes significant above ~100 MeV
    if bg < 0.1:
        delta = 0
    elif bg < 10:
        # Simplified Sternheimer parameterization
        # For Al: δ₀ = 0.12, C = 4.24, a = 0.08, m = 3.0, X₀ = 0.17, X₁ = 3.0
        X = math.log10(bg)
        if X < 0.17:
            delta = 0
        elif X < 3.0:
            delta = 4.24 * (X - 0.17)**3.0 + 2 * math.log(10) * X - 0.12
        else:
            delta = 4.24 * (X - 0.17)**3.0 + 2 * math.log(10) * X - 0.12
    else:
        # High energy approximation
        delta = 2 * math.log(bg) - 0.12

    # Result in MeV·cm²/g
    dEdx_mass = term1 * (term2 - delta/2 - shell_correction/AL_Z)

    # Convert to MeV/μm
    dEdx = dEdx_mass * AL_DENSITY * 1e-4

    return dEdx


def s_AL_bethe(E_kinetic, use_corrections=False):
    """
    Aluminum stopping power using Bethe-Bloch formula

    Args:
        E_kinetic: Proton kinetic energy in MeV
        use_corrections: Include shell and density corrections (slower but more accurate)

    Returns:
        Stopping power in MeV/μm

    Valid range: E > 1 MeV (below this, need experimental data)

    Example:
        >>> sp = s_AL_bethe(10.0)
        >>> print(f"10 MeV: {sp:.6f} MeV/μm")
    """
    if E_kinetic < 1.0:
        # Below 1 MeV, Bethe formula becomes inaccurate
        # Should use empirical formulas based on experimental data
        import warnings
        warnings.warn(
            f"Energy {E_kinetic} MeV is below recommended range (>1 MeV) for Bethe formula. "
            f"Consider using PSTAR data or empirical formulas.",
            RuntimeWarning
        )

    if use_corrections:
        return bethe_bloch_with_corrections(E_kinetic)
    else:
        return bethe_bloch_simple(E_kinetic)


# Alias for convenience
s_Al_Bethe = s_AL_bethe


def compare_methods(E_kinetic):
    """
    Compare different calculation methods

    Args:
        E_kinetic: Energy in MeV

    Returns:
        dict with different method results
    """
    result = {
        'energy': E_kinetic,
        'bethe_simple': bethe_bloch_simple(E_kinetic),
        'bethe_corrected': bethe_bloch_with_corrections(E_kinetic),
    }

    # Try to get old function value
    try:
        from .stopping_power import s_AL1, s_AL2, s_AL3
        if E_kinetic > 1.0:
            result['old_function'] = s_AL1(E_kinetic)
        elif E_kinetic > 0.1:
            result['old_function'] = s_AL2(E_kinetic)
        else:
            result['old_function'] = s_AL3(E_kinetic)
    except:
        result['old_function'] = None

    # Try to get PSTAR value
    try:
        from .stopping_power_pstar import s_Al_PSTAR
        result['pstar'] = s_Al_PSTAR(E_kinetic)
    except:
        result['pstar'] = None

    return result


if __name__ == "__main__":
    """Test and comparison"""
    print("Bethe-Bloch Formula for Protons in Aluminum")
    print("=" * 80)
    print()

    # Test energies
    test_energies = [1, 2, 5, 10, 20, 30, 50, 100]

    print(f"{'Energy':>8} {'Bethe':>12} {'Bethe+Corr':>12} {'Old Func':>12} {'PSTAR':>12}")
    print(f"{'(MeV)':>8} {'(MeV/μm)':>12} {'(MeV/μm)':>12} {'(MeV/μm)':>12} {'(MeV/μm)':>12}")
    print("-" * 80)

    for E in test_energies:
        comp = compare_methods(E)
        print(f"{E:8.1f} {comp['bethe_simple']:12.6f} {comp['bethe_corrected']:12.6f} ", end="")
        if comp['old_function'] is not None:
            print(f"{comp['old_function']:12.6f} ", end="")
        else:
            print(f"{'N/A':>12} ", end="")
        if comp['pstar'] is not None:
            print(f"{comp['pstar']:12.6f}")
        else:
            print(f"{'N/A':>12}")

    print("=" * 80)
    print()
    print("Notes:")
    print("- Bethe: Simple Bethe-Bloch formula")
    print("- Bethe+Corr: With density effect correction")
    print("- Old Func: Your project's empirical fitting functions")
    print("- PSTAR: NIST data (uses Bethe + corrections for E>1 MeV)")


# ============================================================================
# 多离子支持 (Multi-Ion Support)
# ============================================================================

def beta_gamma_ion(E_per_nucleon, ion_mass, ion_A):
    """
    Calculate relativistic β and γ for arbitrary ion

    Args:
        E_per_nucleon: Kinetic energy per nucleon (MeV/u)
        ion_mass: Ion rest mass (MeV/c²)
        ion_A: Ion mass number

    Returns:
        (beta, gamma, beta*gamma)
    """
    if E_per_nucleon <= 0:
        return 0.0, 1.0, 0.0

    # Total kinetic energy
    E_total = E_per_nucleon * ion_A

    # Lorentz factor
    gamma = 1 + E_total / ion_mass

    if gamma <= 1:
        return 0.0, 1.0, 0.0

    beta = math.sqrt(1 - 1 / (gamma ** 2))

    return beta, gamma, beta * gamma


def effective_charge_barkas(Z_ion, beta):
    """
    Calculate effective charge using Barkas formula

    有效电荷计算 - 使用 Barkas 公式
    在低能时离子未完全电离，有效电荷小于核电荷

    .. deprecated::
        Use Ion.effective_charge(beta) from physics.ion module instead.
        此函数已弃用，请使用 physics.ion 模块中的 Ion.effective_charge() 方法。

    Args:
        Z_ion: Ion atomic number
        beta: Relativistic velocity (v/c)

    Returns:
        Z_eff: Effective charge
    """
    import warnings
    warnings.warn(
        "effective_charge_barkas() is deprecated. "
        "Use Ion.effective_charge(beta) from physics.ion module instead.",
        DeprecationWarning,
        stacklevel=2
    )

    # Delegate to ion module implementation
    if beta <= 0:
        return 0.0

    if beta >= 0.99:
        return float(Z_ion)

    # Barkas formula: Z_eff = Z × [1 - exp(-125 × β × Z^(-2/3))]
    exponent = -125.0 * beta * (Z_ion ** (-2.0/3.0))

    # Prevent overflow
    if exponent < -700:
        return float(Z_ion)

    Z_eff = Z_ion * (1.0 - math.exp(exponent))

    return Z_eff


def shell_correction_ion(beta, Z_target):
    """
    Shell correction for stopping power

    壳层修正 - 在低能时重要

    Args:
        beta: Relativistic velocity
        Z_target: Target atomic number

    Returns:
        Shell correction term C/Z
    """
    if beta <= 0.01:
        return 0.0

    # Simplified shell correction
    # More accurate would use Bichsel's tables
    eta = beta * 137.036  # β × c / (α × c) = β / α

    if eta > 10:
        return 0.0

    # Approximate shell correction
    C_over_Z = 0.422377 * eta**(-2) + 0.0304043 * eta**(-4) - 0.00038106 * eta**(-6)

    return max(0.0, C_over_Z)


def density_effect_correction(beta_gamma, I_eV):
    """
    Density effect correction (Sternheimer parameterization)

    密度效应修正 - 在高能时重要

    Args:
        beta_gamma: β × γ
        I_eV: Mean excitation energy in eV

    Returns:
        δ: Density correction term
    """
    if beta_gamma < 0.1:
        return 0.0

    X = math.log10(beta_gamma)

    # Simplified Sternheimer parameterization
    # More accurate would use material-specific parameters
    X0 = 0.2
    X1 = 3.0
    C_param = 3.0 + 2 * math.log(I_eV)
    a = 0.1
    m = 3.0

    if X < X0:
        delta = 0
    elif X < X1:
        delta = 2 * math.log(10) * X - C_param + a * (X1 - X)**m
    else:
        delta = 2 * math.log(10) * X - C_param

    return max(0.0, delta)


def bloch_correction(Z_eff, beta):
    """
    Bloch correction for heavy ions

    Bloch 修正 - 对 Z > 2 的重离子在中等能量时重要

    Args:
        Z_eff: Effective charge
        beta: Relativistic velocity

    Returns:
        Bloch correction term
    """
    if beta < 0.001 or Z_eff < 0.1:
        return 0.0

    alpha = 1/137.036  # Fine structure constant
    y = alpha * Z_eff / beta

    # Lindhard-Sørensen Bloch correction
    # Simplified first-order approximation
    if y < 0.5:
        # Expansion for small y
        return y**2 * (1.202 - 0.5 * y**2)
    else:
        # Numerical approximation for larger y
        # Real(ψ(1 + iy) - ψ(1)) where ψ is digamma function
        # Approximate using series
        correction = 0.0
        for n in range(1, 100):
            term = y**2 / (n * (n**2 + y**2))
            if abs(term) < 1e-10:
                break
            correction += term

        return correction


def barkas_correction(Z_eff, beta, Z_target):
    """
    Barkas correction (Z³ effect)

    Barkas 修正 - 正负粒子阻止本领差异

    Args:
        Z_eff: Effective charge of projectile
        beta: Relativistic velocity
        Z_target: Target atomic number

    Returns:
        Barkas correction term
    """
    if beta < 0.01:
        return 0.0

    # Simplified Barkas correction
    # L_1 ≈ 1.29 × Z_eff / (Z_target^(1/2) × β)
    L1 = 1.29 * Z_eff / (math.sqrt(Z_target) * beta)

    return L1 * 0.001  # Small correction


def bethe_bloch_ion(E_per_nucleon, ion, Z_target, A_target, I_eV, density,
                   include_corrections=True):
    """
    Bethe-Bloch formula for arbitrary ions in any material

    任意离子在任意材料中的 Bethe-Bloch 公式

    Args:
        E_per_nucleon: Kinetic energy per nucleon (MeV/u)
        ion: Ion object from physics.ion module
        Z_target: Target atomic number
        A_target: Target atomic mass (g/mol)
        I_eV: Mean excitation energy (eV)
        density: Target density (g/cm³)
        include_corrections: Include shell, density, Bloch corrections

    Returns:
        Stopping power in MeV/μm

    Example:
        >>> from physics.ion import CARBON12
        >>> sp = bethe_bloch_ion(100, CARBON12, 13, 26.982, 166, 2.702)
    """
    # 早期输入验证 / Early input validation
    if E_per_nucleon <= 0:
        return 0.0

    # 低能量警告 / Low energy warning
    if E_per_nucleon < 0.1:
        import warnings
        warnings.warn(
            f"Energy {E_per_nucleon:.4f} MeV/u is very low. "
            f"Bethe-Bloch formula may be inaccurate below 0.1 MeV/u. "
            f"Consider using PSTAR data instead.",
            RuntimeWarning
        )

    # Get relativistic parameters
    beta, gamma, bg = ion.beta_gamma(E_per_nucleon)

    if beta <= 0 or beta >= 1:
        return 0.0

    beta2 = beta ** 2

    # Effective charge
    Z_eff = ion.effective_charge(beta)

    if Z_eff <= 0:
        return 0.0

    # Constants
    K = 0.307075  # MeV·cm²/mol
    m_e = ELECTRON_MASS  # MeV/c²
    I_MeV = I_eV * 1e-6

    # Maximum energy transfer (exact formula for finite projectile mass)
    M = ion.mass
    Tmax_denom = 1 + 2 * gamma * m_e / M + (m_e / M)**2
    Tmax = (2 * m_e * beta2 * gamma**2) / Tmax_denom

    # Prevent log of non-positive number
    if Tmax <= 0 or I_MeV <= 0:
        return 0.0

    log_arg = 2 * m_e * beta2 * gamma**2 * Tmax / (I_MeV ** 2)
    if log_arg <= 0:
        return 0.0

    # Main Bethe term with Z_eff² factor
    term1 = (K * Z_target / A_target) * (Z_eff**2 / beta2)
    term2 = 0.5 * math.log(log_arg) - beta2

    # Corrections
    if include_corrections:
        delta = density_effect_correction(bg, I_eV)
        shell_corr = shell_correction_ion(beta, Z_target)
        bloch_corr = bloch_correction(Z_eff, beta)
        barkas_corr = barkas_correction(Z_eff, beta, Z_target)
    else:
        delta = 0.0
        shell_corr = 0.0
        bloch_corr = 0.0
        barkas_corr = 0.0

    # Mass stopping power (MeV·cm²/g)
    S_rho = term1 * (term2 - delta/2 - shell_corr - bloch_corr - barkas_corr)

    # Ensure non-negative
    S_rho = max(0.0, S_rho)

    # Convert to MeV/μm
    dEdx = S_rho * density * 1e-4

    return dEdx


def stopping_power_ion_in_material(E_per_nucleon, ion, material,
                                   include_corrections=True):
    """
    Calculate stopping power for ion in a Material object

    使用 Material 对象计算离子阻止本领

    Args:
        E_per_nucleon: Energy per nucleon (MeV/u)
        ion: Ion object
        material: Material object from material_registry
        include_corrections: Include corrections

    Returns:
        Stopping power in MeV/μm
    """
    # For proton, use PSTAR data directly if available
    if ion.Z == 1 and ion.A == 1:
        return material.dE_per_um(E_per_nucleon)

    # For other ions, scale from proton stopping power
    # S_ion = Z_eff² × S_proton (at same velocity)
    S_proton = material.dE_per_um(E_per_nucleon)

    # Get effective charge at this energy
    ratio = ion.stopping_power_ratio(E_per_nucleon)

    S_ion = S_proton * ratio

    return S_ion


def stopping_power_ion_simple(E_per_nucleon, ion, S_proton_func,
                              include_corrections=True):
    """
    Simple ion stopping power from proton stopping power function

    从质子阻止本领函数计算离子阻止本领（简化版）

    Args:
        E_per_nucleon: Energy per nucleon (MeV/u)
        ion: Ion object
        S_proton_func: Function S(E) returning proton stopping power at energy E
        include_corrections: Include corrections

    Returns:
        Stopping power in MeV/μm

    Example:
        >>> from physics.ion import CARBON12
        >>> from physics.stopping_power import s_Cu
        >>> S_C = stopping_power_ion_simple(10, CARBON12, s_Cu)
    """
    # Get proton stopping power at same velocity (same E/A)
    S_proton = S_proton_func(E_per_nucleon)

    # Scale by Z_eff²
    ratio = ion.stopping_power_ratio(E_per_nucleon)

    S_ion = S_proton * ratio

    return S_ion


# ============================================================================
# 便捷函数 - 常用材料
# ============================================================================

def s_Al_ion(E_per_nucleon, ion, use_corrections=True):
    """
    Aluminum stopping power for arbitrary ion

    任意离子在铝中的阻止本领

    Args:
        E_per_nucleon: Energy per nucleon (MeV/u)
        ion: Ion object
        use_corrections: Include corrections

    Returns:
        Stopping power in MeV/μm

    Example:
        >>> from physics.ion import CARBON12, PROTON
        >>> s_p = s_Al_ion(10, PROTON)   # Proton at 10 MeV
        >>> s_C = s_Al_ion(10, CARBON12)  # C12 at 10 MeV/u (120 MeV total)
    """
    return bethe_bloch_ion(
        E_per_nucleon=E_per_nucleon,
        ion=ion,
        Z_target=AL_Z,
        A_target=AL_A,
        I_eV=166,  # Mean excitation energy for Al
        density=AL_DENSITY,
        include_corrections=use_corrections
    )


# ============================================================================
# 测试多离子功能
# ============================================================================

def test_multi_ion():
    """Test multi-ion stopping power calculations"""
    try:
        from physics.ion import PROTON, HELIUM4, CARBON12, OXYGEN16, IRON56
    except ImportError:
        print("Warning: physics.ion module not found, skipping ion tests")
        return

    print("\n" + "=" * 80)
    print("Multi-Ion Stopping Power Test (多离子阻止本领测试)")
    print("Material: Aluminum (铝)")
    print("=" * 80)

    test_ions = [PROTON, HELIUM4, CARBON12, OXYGEN16]
    test_energies = [1, 5, 10, 50, 100]  # MeV/u

    print(f"\n{'Ion':<10} {'E(MeV/u)':<12} {'Z_eff':<10} {'S(MeV/μm)':<15} {'S/S_p ratio':<12}")
    print("-" * 80)

    for ion in test_ions:
        for E in test_energies:
            S = s_Al_ion(E, ion)
            S_p = s_Al_ion(E, PROTON)
            Z_eff = ion.effective_charge_at_energy(E)
            ratio = S / S_p if S_p > 0 else 0

            print(f"{ion.name:<10} {E:<12} {Z_eff:<10.2f} {S:<15.6f} {ratio:<12.2f}")
        print()

    print("=" * 80)
    print("Note: S/S_p ratio should approximately equal Z_eff² at high energies")
    print("=" * 80)
