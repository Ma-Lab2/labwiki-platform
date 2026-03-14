"""
NIST PSTAR/ASTAR/ESTAR格式解析器

支持解析NIST提供的标准格式停止本领数据：
- PSTAR: 质子停止本领
- ASTAR: α粒子停止本领
- ESTAR: 电子停止本领

Author: Tan Song / Claude
Date: 2025-11-19
"""

import re
import numpy as np
from typing import Dict, Tuple, Optional


class PSTARParser:
    """NIST PSTAR格式解析器"""

    # 支持的数据格式标识
    SUPPORTED_FORMATS = {
        'PSTAR': 'Proton',
        'ASTAR': 'Alpha',
        'ESTAR': 'Electron'
    }

    def __init__(self):
        self.format_type = None
        self.material_name = None
        self.data = {}

    def parse_file(self, filepath: str) -> Dict:
        """
        解析PSTAR格式文件

        Args:
            filepath: PSTAR数据文件路径

        Returns:
            {
                'format': 'PSTAR' | 'ASTAR' | 'ESTAR',
                'particle': 'Proton' | 'Alpha' | 'Electron',
                'material': str,  # 材料名（首字母大写）
                'energy': np.array,  # 能量（MeV）
                'stopping_power_total': np.array,  # 总停止本领（MeV cm²/g）
                'stopping_power_electron': np.array,  # 电子停止本领（可选）
                'stopping_power_nuclear': np.array,   # 核停止本领（可选）
                'data_points': int,  # 数据点数
                'energy_range': [min, max],  # 能量范围
            }

        Raises:
            ValueError: 文件格式不支持或解析失败
        """
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        # Step 1: 检测格式类型
        self.format_type = self._detect_format(lines)
        if not self.format_type:
            raise ValueError("无法识别文件格式，请确保是NIST PSTAR/ASTAR/ESTAR格式")

        # Step 2: 提取材料名
        self.material_name = self._extract_material_name(lines)

        # Step 3: 查找数据起始行
        data_start_line = self._find_data_start(lines)

        # Step 4: 解析数据
        energy = []
        sp_electron = []
        sp_nuclear = []
        sp_total = []

        for line in lines[data_start_line:]:
            line = line.strip()

            # 跳过空行和注释
            if not line or line.startswith('#') or line.startswith('!'):
                continue

            # 尝试解析数据行
            parsed = self._parse_data_line(line)
            if parsed:
                E, sp_e, sp_n, sp_t = parsed
                energy.append(E)
                sp_electron.append(sp_e)
                sp_nuclear.append(sp_n)
                sp_total.append(sp_t)

        # 转换为numpy数组
        energy = np.array(energy)
        sp_electron = np.array(sp_electron)
        sp_nuclear = np.array(sp_nuclear)
        sp_total = np.array(sp_total)

        # 验证数据
        if len(energy) == 0:
            raise ValueError("未能解析到任何数据点")

        # 返回结果
        result = {
            'format': self.format_type,
            'particle': self.SUPPORTED_FORMATS[self.format_type],
            'material': self.material_name,
            'energy': energy,
            'stopping_power_total': sp_total,
            'stopping_power_electron': sp_electron,
            'stopping_power_nuclear': sp_nuclear,
            'data_points': len(energy),
            'energy_range': [energy.min(), energy.max()],
        }

        return result

    def _detect_format(self, lines: list) -> Optional[str]:
        """
        检测文件格式类型

        Args:
            lines: 文件所有行

        Returns:
            'PSTAR' | 'ASTAR' | 'ESTAR' | None
        """
        # 检查前10行
        header = '\n'.join(lines[:10]).upper()

        if 'PSTAR' in header or 'PROTON' in header:
            return 'PSTAR'
        elif 'ASTAR' in header or 'ALPHA' in header:
            return 'ASTAR'
        elif 'ESTAR' in header or 'ELECTRON' in header:
            return 'ESTAR'
        else:
            # 通过列标题推断
            for line in lines[:20]:
                line_upper = line.upper()
                if 'KINETIC' in line_upper and 'ENERGY' in line_upper:
                    # 找到了能量列，判断是什么粒子
                    if 'ELECTRON' in header:
                        return 'ESTAR'
                    # 默认假设是PSTAR
                    return 'PSTAR'

        return None

    def _extract_material_name(self, lines: list) -> str:
        """
        从文件头提取材料名称

        Args:
            lines: 文件所有行

        Returns:
            材料名称（标准化格式，首字母大写）
        """
        # 通常材料名在前5行，可能格式：
        # - ALUMINUM
        # - Aluminum
        # - Material: Aluminum

        for line in lines[:10]:
            line = line.strip()

            # 跳过空行
            if not line:
                continue

            # 跳过明显的标题行
            if any(keyword in line.upper() for keyword in [
                'PSTAR', 'ASTAR', 'ESTAR', 'STOPPING', 'POWER',
                'RANGE', 'TABLE', 'KINETIC', 'ENERGY', 'MEV'
            ]):
                continue

            # 如果包含"Material:"
            if 'MATERIAL' in line.upper():
                match = re.search(r'MATERIAL\s*:?\s*(\w+)', line, re.IGNORECASE)
                if match:
                    return self._normalize_material_name(match.group(1))

            # 如果是单独一行材料名
            if line.upper() == line and len(line) > 2 and line.isalpha():
                return self._normalize_material_name(line)

            # 如果是首字母大写的单词
            if line[0].isupper() and line[1:].islower() and len(line) > 2:
                return self._normalize_material_name(line)

        # 未找到，返回默认
        return "Unknown"

    def _normalize_material_name(self, name: str) -> str:
        """
        标准化材料名称

        Args:
            name: 原始材料名

        Returns:
            标准化名称（首字母大写）

        Examples:
            "ALUMINUM" -> "Aluminum"
            "aluminum" -> "Aluminum"
            "Aluminum" -> "Aluminum"
        """
        name = name.strip()

        # 特殊处理化合物（保留大小写）
        if any(char.isdigit() for char in name):  # 包含数字，可能是化学式
            return name

        # 转换为首字母大写
        return name.capitalize()

    def _find_data_start(self, lines: list) -> int:
        """
        查找数据起始行号

        Args:
            lines: 文件所有行

        Returns:
            数据起始行号

        策略：
        1. 找到列标题行（Kinetic Energy, Stp. Pow.等）
        2. 跳过单位行（MeV, MeV cm2/g等）
        3. 下一个非空行即为数据起始
        """
        for i, line in enumerate(lines):
            line_upper = line.upper()

            # 找到列标题
            if 'KINETIC' in line_upper and 'ENERGY' in line_upper:
                # 从下一行开始搜索数据
                for j in range(i + 1, min(i + 10, len(lines))):
                    test_line = lines[j].strip()

                    # 跳过空行
                    if not test_line:
                        continue

                    # 跳过单位行（包含MeV, cm2等）
                    if 'MEV' in test_line.upper() or 'CM2' in test_line.upper():
                        continue

                    # 尝试解析为数据行
                    if self._is_data_line(test_line):
                        return j

        # 未找到明确标题，尝试直接找数据
        for i, line in enumerate(lines):
            if self._is_data_line(line.strip()):
                return i

        raise ValueError("未找到数据起始位置")

    def _is_data_line(self, line: str) -> bool:
        """
        判断是否是数据行

        Args:
            line: 待判断的行

        Returns:
            True if 是数据行
        """
        if not line:
            return False

        # 数据行特征：以科学计数法或数字开头
        # 例如：1.000E-03 或 1.000
        parts = line.split()
        if len(parts) < 2:  # 至少2列
            return False

        # 第一列应该是能量（数字）
        try:
            float(parts[0])
            return True
        except ValueError:
            return False

    def _parse_data_line(self, line: str) -> Optional[Tuple[float, float, float, float]]:
        """
        解析单行数据

        Args:
            line: 数据行

        Returns:
            (Energy, SP_electron, SP_nuclear, SP_total) 或 None

        格式示例：
            1.000E-03 9.238E+01 1.197E+01 1.043E+02
        """
        try:
            parts = line.split()

            if len(parts) < 4:
                return None

            energy = float(parts[0])
            sp_electron = float(parts[1])
            sp_nuclear = float(parts[2])
            sp_total = float(parts[3])

            return (energy, sp_electron, sp_nuclear, sp_total)

        except (ValueError, IndexError):
            return None


# 便捷函数
def parse_pstar_file(filepath: str) -> Dict:
    """
    解析PSTAR文件（便捷函数）

    Args:
        filepath: PSTAR文件路径

    Returns:
        解析结果字典

    Example:
        >>> data = parse_pstar_file('PSTAR_Al.txt')
        >>> print(data['material'])
        'Aluminum'
        >>> print(data['data_points'])
        124
    """
    parser = PSTARParser()
    return parser.parse_file(filepath)


if __name__ == '__main__':
    """测试解析器"""
    import sys

    if len(sys.argv) < 2:
        print("用法: python pstar_parser.py <PSTAR文件路径>")
        sys.exit(1)

    filepath = sys.argv[1]

    print("=" * 80)
    print("PSTAR文件解析测试")
    print("=" * 80)
    print()

    try:
        result = parse_pstar_file(filepath)

        print(f"✓ 解析成功！")
        print()
        print(f"格式类型:     {result['format']} ({result['particle']})")
        print(f"材料名称:     {result['material']}")
        print(f"数据点数:     {result['data_points']}")
        print(f"能量范围:     {result['energy_range'][0]:.6f} - {result['energy_range'][1]:.2f} MeV")
        print()

        # 显示前5个数据点
        print("前5个数据点:")
        print(f"{'Energy':>12} {'SP_Total':>15} {'SP_Electron':>15} {'SP_Nuclear':>15}")
        print(f"{'(MeV)':>12} {'(MeV cm²/g)':>15} {'(MeV cm²/g)':>15} {'(MeV cm²/g)':>15}")
        print("-" * 70)

        for i in range(min(5, len(result['energy']))):
            E = result['energy'][i]
            sp_t = result['stopping_power_total'][i]
            sp_e = result['stopping_power_electron'][i]
            sp_n = result['stopping_power_nuclear'][i]
            print(f"{E:12.6f} {sp_t:15.4f} {sp_e:15.4f} {sp_n:15.4f}")

        print()
        print("=" * 80)

    except Exception as e:
        print(f"❌ 解析失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
