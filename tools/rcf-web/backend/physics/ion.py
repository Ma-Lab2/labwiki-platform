"""
Ion definitions for multi-particle transport calculations

Supports proton, carbon, and other ions commonly used in
hadron therapy and nuclear physics experiments.

物理原理:
- 重离子阻止本领与质子的关系: S_ion ≈ Z_eff² × S_proton (相同速度下)
- 有效电荷 Z_eff 在低能时小于核电荷 Z（电子俘获效应）
- 使用 Barkas 公式计算有效电荷

Author: Tan Song / Claude
Date: 2024
"""

import math
from dataclasses import dataclass
from typing import Tuple, Optional, Dict


@dataclass
class Ion:
    """
    Represents an ion species with its nuclear properties

    表示一个离子种类及其核物理属性

    Attributes:
        name: 离子名称 (e.g., 'proton', 'C12', 'He4')
        Z: 原子序数/电荷数
        A: 质量数
        mass: 静止质量 (MeV/c²)
        symbol: 化学符号 (可选)
    """
    name: str
    Z: int
    A: int
    mass: float  # MeV/c²
    symbol: str = ""

    def __post_init__(self):
        """验证参数并设置默认符号"""
        if self.Z <= 0:
            raise ValueError(f"原子序数 Z 必须为正整数，得到: {self.Z}")
        if self.A <= 0:
            raise ValueError(f"质量数 A 必须为正整数，得到: {self.A}")
        if self.mass <= 0:
            raise ValueError(f"质量必须为正数，得到: {self.mass}")

        if not self.symbol:
            self.symbol = self.name

    @classmethod
    def from_mass_number(cls, name: str, Z: int, A: int, symbol: str = "") -> 'Ion':
        """
        从质量数创建离子（自动计算质量）

        Args:
            name: 离子名称
            Z: 原子序数
            A: 质量数
            symbol: 化学符号

        Returns:
            Ion object
        """
        # 原子质量单位 u = 931.494 MeV/c²
        # 近似质量 = A × 931.494 MeV/c²
        # 更精确的计算需要考虑结合能
        AMU = 931.494  # MeV/c²
        mass = A * AMU
        return cls(name=name, Z=Z, A=A, mass=mass, symbol=symbol)

    def beta_gamma(self, E_kinetic_per_nucleon: float) -> Tuple[float, float, float]:
        """
        Calculate relativistic β and γ

        计算相对论参数 β (v/c) 和 γ (洛伦兹因子)

        Args:
            E_kinetic_per_nucleon: 每核子动能 (MeV/u)

        Returns:
            (beta, gamma, beta*gamma) 元组
        """
        if E_kinetic_per_nucleon <= 0:
            return 0.0, 1.0, 0.0

        # 总动能 = 每核子动能 × 质量数
        E_total_kinetic = E_kinetic_per_nucleon * self.A

        # γ = 1 + E_k / M_0 c²
        gamma = 1 + E_total_kinetic / self.mass

        # β = √(1 - 1/γ²)
        if gamma <= 1:
            return 0.0, 1.0, 0.0

        beta = math.sqrt(1 - 1 / (gamma ** 2))

        return beta, gamma, beta * gamma

    def velocity_from_energy(self, E_kinetic_per_nucleon: float) -> float:
        """
        计算离子速度 (单位: c)

        Args:
            E_kinetic_per_nucleon: 每核子动能 (MeV/u)

        Returns:
            β = v/c
        """
        beta, _, _ = self.beta_gamma(E_kinetic_per_nucleon)
        return beta

    def effective_charge(self, beta: float) -> float:
        """
        Calculate effective charge using Barkas formula

        使用 Barkas 公式计算有效电荷
        在低能时，离子未完全电离，有效电荷小于核电荷

        公式: Z_eff = Z × [1 - exp(-125 × β × Z^(-2/3))]

        Args:
            beta: 相对论速度 v/c

        Returns:
            Z_eff: 有效电荷
        """
        if beta <= 0:
            return 0.0

        if beta >= 0.99:
            # 高能极限：完全电离
            return float(self.Z)

        # Barkas formula
        exponent = -125.0 * beta * (self.Z ** (-2.0/3.0))

        # 防止数值溢出
        if exponent < -700:
            Z_eff = float(self.Z)
        else:
            Z_eff = self.Z * (1.0 - math.exp(exponent))

        return Z_eff

    def effective_charge_at_energy(self, E_kinetic_per_nucleon: float) -> float:
        """
        在给定能量下计算有效电荷

        Args:
            E_kinetic_per_nucleon: 每核子动能 (MeV/u)

        Returns:
            Z_eff: 有效电荷
        """
        beta = self.velocity_from_energy(E_kinetic_per_nucleon)
        return self.effective_charge(beta)

    def stopping_power_ratio(self, E_kinetic_per_nucleon: float) -> float:
        """
        Calculate S_ion / S_proton ratio at the same velocity

        计算相同速度下，离子阻止本领与质子阻止本领的比值

        基本关系: S_ion / S_proton ≈ Z_eff²

        Args:
            E_kinetic_per_nucleon: 每核子动能 (MeV/u)

        Returns:
            阻止本领比值 (无量纲)
        """
        Z_eff = self.effective_charge_at_energy(E_kinetic_per_nucleon)

        # 基本缩放关系: S ∝ Z_eff²
        ratio = Z_eff ** 2

        return ratio

    def range_scaling_factor(self, E_kinetic_per_nucleon: float) -> float:
        """
        计算射程缩放因子

        相同每核子能量下，离子射程与质子射程的比值
        R_ion / R_proton ≈ A / Z_eff²

        Args:
            E_kinetic_per_nucleon: 每核子动能 (MeV/u)

        Returns:
            射程比值
        """
        Z_eff = self.effective_charge_at_energy(E_kinetic_per_nucleon)

        if Z_eff <= 0:
            return float('inf')

        # R ∝ A / Z²
        return self.A / (Z_eff ** 2)

    def energy_per_nucleon_to_total(self, E_per_nucleon: float) -> float:
        """每核子能量转换为总动能"""
        return E_per_nucleon * self.A

    def total_energy_to_per_nucleon(self, E_total: float) -> float:
        """总动能转换为每核子能量"""
        return E_total / self.A

    def __str__(self) -> str:
        return f"{self.name} (Z={self.Z}, A={self.A}, M={self.mass:.3f} MeV/c²)"

    def __repr__(self) -> str:
        return f"Ion(name='{self.name}', Z={self.Z}, A={self.A}, mass={self.mass})"


# ============================================================================
# 预定义常用离子 (Predefined Common Ions)
# ============================================================================

# 氢同位素 (Hydrogen isotopes)
PROTON = Ion(
    name='proton',
    Z=1,
    A=1,
    mass=938.272,  # MeV/c²
    symbol='p'
)

DEUTERON = Ion(
    name='deuteron',
    Z=1,
    A=2,
    mass=1875.613,
    symbol='d'
)

TRITON = Ion(
    name='triton',
    Z=1,
    A=3,
    mass=2808.921,
    symbol='t'
)

# 氦同位素 (Helium isotopes)
HELIUM3 = Ion(
    name='He3',
    Z=2,
    A=3,
    mass=2808.391,
    symbol='³He'
)

HELIUM4 = Ion(
    name='He4',
    Z=2,
    A=4,
    mass=3727.379,
    symbol='α'
)
ALPHA = HELIUM4  # 别名

# 锂 (Lithium)
LITHIUM6 = Ion(
    name='Li6',
    Z=3,
    A=6,
    mass=5601.518,
    symbol='⁶Li'
)

LITHIUM7 = Ion(
    name='Li7',
    Z=3,
    A=7,
    mass=6533.833,
    symbol='⁷Li'
)

# 碳同位素 (Carbon isotopes) - 常用于重离子治疗
CARBON12 = Ion(
    name='C12',
    Z=6,
    A=12,
    mass=11177.929,
    symbol='¹²C'
)

CARBON13 = Ion(
    name='C13',
    Z=6,
    A=13,
    mass=12109.482,
    symbol='¹³C'
)

# 氮 (Nitrogen)
NITROGEN14 = Ion(
    name='N14',
    Z=7,
    A=14,
    mass=13040.203,
    symbol='¹⁴N'
)

# 氧 (Oxygen)
OXYGEN16 = Ion(
    name='O16',
    Z=8,
    A=16,
    mass=14895.079,
    symbol='¹⁶O'
)

OXYGEN18 = Ion(
    name='O18',
    Z=8,
    A=18,
    mass=16762.016,
    symbol='¹⁸O'
)

# 氖 (Neon)
NEON20 = Ion(
    name='Ne20',
    Z=10,
    A=20,
    mass=18617.728,
    symbol='²⁰Ne'
)

# 硅 (Silicon)
SILICON28 = Ion(
    name='Si28',
    Z=14,
    A=28,
    mass=26060.339,
    symbol='²⁸Si'
)

# 氩 (Argon)
ARGON40 = Ion(
    name='Ar40',
    Z=18,
    A=40,
    mass=37224.658,
    symbol='⁴⁰Ar'
)

# 铁 (Iron) - 宇宙射线研究常用
IRON56 = Ion(
    name='Fe56',
    Z=26,
    A=56,
    mass=52103.063,
    symbol='⁵⁶Fe'
)


# ============================================================================
# 离子目录 (Ion Catalog)
# ============================================================================

ION_CATALOG: Dict[str, Ion] = {
    # 氢
    'proton': PROTON,
    'p': PROTON,
    'H1': PROTON,
    'hydrogen': PROTON,

    'deuteron': DEUTERON,
    'd': DEUTERON,
    'H2': DEUTERON,

    'triton': TRITON,
    't': TRITON,
    'H3': TRITON,

    # 氦
    'He3': HELIUM3,
    'helium3': HELIUM3,

    'He4': HELIUM4,
    'helium4': HELIUM4,
    'alpha': HELIUM4,
    'α': HELIUM4,

    # 锂
    'Li6': LITHIUM6,
    'Li7': LITHIUM7,

    # 碳
    'C12': CARBON12,
    'carbon': CARBON12,
    'carbon12': CARBON12,

    'C13': CARBON13,

    # 氮
    'N14': NITROGEN14,
    'nitrogen': NITROGEN14,

    # 氧
    'O16': OXYGEN16,
    'oxygen': OXYGEN16,

    'O18': OXYGEN18,

    # 氖
    'Ne20': NEON20,
    'neon': NEON20,

    # 硅
    'Si28': SILICON28,
    'silicon': SILICON28,

    # 氩
    'Ar40': ARGON40,
    'argon': ARGON40,

    # 铁
    'Fe56': IRON56,
    'iron': IRON56,
}


def get_ion(name: str) -> Ion:
    """
    Get ion by name from catalog

    通过名称从目录获取离子

    Args:
        name: 离子名称 (如 'proton', 'C12', 'He4' 等)

    Returns:
        Ion object

    Raises:
        ValueError: 如果离子不在目录中

    Example:
        >>> carbon = get_ion('C12')
        >>> print(carbon.Z, carbon.A)
        6 12
    """
    if name in ION_CATALOG:
        return ION_CATALOG[name]

    # 尝试不区分大小写匹配
    name_lower = name.lower()
    for key, ion in ION_CATALOG.items():
        if key.lower() == name_lower:
            return ion

    available = sorted(set(ION_CATALOG.keys()))
    raise ValueError(
        f"未知离子: '{name}'\n"
        f"可用离子: {available}"
    )


def list_available_ions() -> list:
    """
    列出所有可用的离子名称

    Returns:
        离子名称列表
    """
    # 返回去重后的主要名称
    seen = set()
    result = []
    for name, ion in ION_CATALOG.items():
        if ion.name not in seen:
            seen.add(ion.name)
            result.append(ion.name)
    return sorted(result)


def create_custom_ion(name: str, Z: int, A: int, mass_MeV: float = None) -> Ion:
    """
    创建自定义离子

    Args:
        name: 离子名称
        Z: 原子序数
        A: 质量数
        mass_MeV: 质量 (MeV/c²)，如果为None则自动计算

    Returns:
        Ion object

    Example:
        >>> uranium = create_custom_ion('U238', Z=92, A=238)
    """
    if mass_MeV is None:
        return Ion.from_mass_number(name, Z, A)
    else:
        return Ion(name=name, Z=Z, A=A, mass=mass_MeV)


# ============================================================================
# GUI 辅助函数
# ============================================================================

def get_ion_display_list() -> list:
    """
    获取用于GUI显示的离子列表

    Returns:
        [(display_name, ion_key), ...] 格式的列表
    """
    return [
        ('质子 (proton)', 'proton'),
        ('氘核 (deuteron)', 'deuteron'),
        ('α粒子 (He4)', 'He4'),
        ('碳-12 (C12)', 'C12'),
        ('氮-14 (N14)', 'N14'),
        ('氧-16 (O16)', 'O16'),
        ('氖-20 (Ne20)', 'Ne20'),
        ('硅-28 (Si28)', 'Si28'),
        ('氩-40 (Ar40)', 'Ar40'),
        ('铁-56 (Fe56)', 'Fe56'),
    ]


# ============================================================================
# 测试代码
# ============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("离子物理参数测试 (Ion Physics Parameter Test)")
    print("=" * 70)

    # 测试能量
    test_energies = [1, 5, 10, 50, 100, 200]  # MeV/u

    # 测试离子
    test_ions = [PROTON, HELIUM4, CARBON12, OXYGEN16, IRON56]

    print(f"\n{'Ion':<12} {'E(MeV/u)':<10} {'β':<8} {'γ':<8} {'Z_eff':<8} {'S_ratio':<10}")
    print("-" * 70)

    for ion in test_ions:
        for E in test_energies:
            beta, gamma, _ = ion.beta_gamma(E)
            Z_eff = ion.effective_charge(beta)
            S_ratio = ion.stopping_power_ratio(E)

            print(f"{ion.name:<12} {E:<10} {beta:<8.4f} {gamma:<8.4f} {Z_eff:<8.2f} {S_ratio:<10.2f}")
        print()

    print("=" * 70)
    print("可用离子列表:")
    for name in list_available_ions():
        ion = get_ion(name)
        print(f"  {name}: Z={ion.Z}, A={ion.A}, M={ion.mass:.1f} MeV/c²")
