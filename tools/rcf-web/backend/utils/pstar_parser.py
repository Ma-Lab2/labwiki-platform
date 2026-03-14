"""
PSTAR数据处理工具
将从NIST网站手动下载的数据转换为项目可用格式
"""

import numpy as np
import re
from pathlib import Path


def parse_pstar_text_file(input_file, density, material_name):
    """
    解析从NIST PSTAR手动下载的文本文件

    Parameters:
    -----------
    input_file : str
        下载的PSTAR文本文件路径
    density : float
        材料密度 (g/cm³)
    material_name : str
        材料名称

    Returns:
    --------
    tuple : (energies, stopping_powers)
    """
    print(f"正在处理 {material_name} 数据...")
    print(f"输入文件: {input_file}")
    print(f"密度: {density} g/cm³")

    with open(input_file, 'r') as f:
        content = f.read()

    lines = content.split('\n')

    energies = []
    sp_total = []
    sp_electronic = []
    sp_nuclear = []
    csda_range = []

    # 解析数据行
    for line in lines:
        line = line.strip()

        # 跳过空行和注释
        if not line or line.startswith('#') or line.startswith('PSTAR'):
            continue

        # 跳过表头
        if 'Kinetic' in line or 'Energy' in line or 'MeV' in line:
            continue
        if '------' in line or '======' in line:
            continue

        # 尝试解析数据
        # PSTAR典型格式:
        # Kinetic   Total   CSDA    Projected   Detour
        # Energy  Stp. Pow.  Range     Range     Factor
        #  MeV   MeV cm2/g  g/cm2     g/cm2

        parts = line.split()
        if len(parts) >= 2:
            try:
                energy = float(parts[0])  # MeV

                # 第二列通常是总阻止本领 (MeV cm²/g)
                sp_raw = float(parts[1])

                # 转换为 MeV/μm: (MeV cm²/g) × (g/cm³) / 10000
                sp_mev_um = sp_raw * density / 10000.0

                energies.append(energy)
                sp_total.append(sp_mev_um)

                # 可选：CSDA射程
                if len(parts) >= 3:
                    csda_range.append(float(parts[2]))  # g/cm²

            except ValueError:
                continue

    if not energies:
        raise ValueError("未能从文件中解析出数据！请检查文件格式")

    energies = np.array(energies)
    sp_total = np.array(sp_total)

    print(f"成功解析 {len(energies)} 个数据点")
    print(f"能量范围: {energies.min():.3e} - {energies.max():.3e} MeV")
    print(f"阻止本领范围: {sp_total.min():.3e} - {sp_total.max():.3e} MeV/μm")

    return energies, sp_total


def generate_python_function(energies, sp_data, material_name, output_file=None):
    """
    生成Python函数代码（可直接用于stopping_power.py）
    """

    if output_file is None:
        output_file = f"pstar_data/s_{material_name.lower()}_generated.py"

    Path("pstar_data").mkdir(exist_ok=True)

    # 对数空间插值数据
    log_E = np.log10(energies)
    log_SP = np.log10(sp_data)

    code = f'''def s_{material_name}(E):
    """
    {material_name}中质子的阻止本领 (MeV/μm)
    基于NIST PSTAR数据 (对数插值)

    Parameters:
    -----------
    E : float
        质子动能 (MeV)

    Returns:
    --------
    float : 阻止本领 (MeV/μm)
    """
    import numpy as np

    if E <= 0:
        return 0.0

    # 对数插值表 (log10)
    log_E_table = np.array({log_E.tolist()})

    log_SP_table = np.array({log_SP.tolist()})

    log_E_input = np.log10(E)

    # 边界外推
    if log_E_input <= log_E_table[0]:
        return 10**log_SP_table[0]
    if log_E_input >= log_E_table[-1]:
        return 10**log_SP_table[-1]

    # 对数线性插值
    return 10**np.interp(log_E_input, log_E_table, log_SP_table)


# 测试代码
if __name__ == "__main__":
    test_energies = [0.1, 0.5, 1.0, 5.0, 10.0, 50.0]
    print(f"{{material_name}} 阻止本领测试:")
    for E in test_energies:
        print(f"  E = {{E:6.2f}} MeV  ->  SP = {{s_{material_name}(E):.6f}} MeV/μm")
'''

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(code)

    print(f"\nPython函数已生成: {output_file}")
    print("可以复制到 physics/stopping_power.py 中使用")

    return code


def save_data_table(energies, sp_data, material_name, density):
    """
    保存为简洁的数据表格文件
    """
    output_file = f"pstar_data/{material_name.lower()}_data.txt"
    Path("pstar_data").mkdir(exist_ok=True)

    header = f"{material_name} Stopping Power Data\n"
    header += f"Density: {density} g/cm³\n"
    header += f"Source: NIST PSTAR\n"
    header += f"Units: Energy (MeV), Stopping Power (MeV/μm)\n"
    header += "-" * 50

    np.savetxt(output_file,
               np.column_stack([energies, sp_data]),
               header=header,
               fmt=['%12.6e', '%12.6e'],
               delimiter='  ',
               comments='# ')

    print(f"数据表已保存: {output_file}")


def main():
    """
    示例使用流程
    """
    print("="*70)
    print(" PSTAR数据处理工具")
    print("="*70)

    print("\n【使用说明】")
    print("1. 访问 https://physics.nist.gov/PhysRefData/Star/Text/PSTAR.html")
    print("2. 点击材料链接（如'Aluminum'）或输入化学式")
    print("3. 保存数据到 pstar_data/ 目录（如 aluminum_raw.txt）")
    print("4. 运行此脚本处理数据\n")

    # 示例：处理手动下载的数据
    examples = [
        ("pstar_data/aluminum_pstar.txt", 2.70, "Aluminum"),
        ("pstar_data/copper_pstar.txt", 8.96, "Copper"),
        ("pstar_data/chromium_pstar.txt", 7.19, "Chromium"),
    ]

    print("="*70)
    print("准备处理以下文件:")
    for file, density, name in examples:
        print(f"  - {file} ({name}, ρ={density} g/cm³)")

    print("\n请确保文件存在，然后修改下方代码调用相应函数")
    print("="*70)

    # 取消注释以下代码来处理实际文件：
    """
    for input_file, density, name in examples:
        if Path(input_file).exists():
            try:
                E, SP = parse_pstar_text_file(input_file, density, name)
                save_data_table(E, SP, name, density)
                generate_python_function(E, SP, name)
                print()
            except Exception as e:
                print(f"处理 {name} 失败: {e}\n")
        else:
            print(f"文件不存在: {input_file}\n")
    """


if __name__ == "__main__":
    main()
