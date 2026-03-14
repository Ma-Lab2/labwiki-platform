"""
材料数据库管理器

管理PSTAR材料数据的持久化存储、加载和使用
支持两种模式：
- 混合模式（Hybrid）：低能用PSTAR，高能用Bethe-Bloch
- 纯PSTAR模式（PSTAR Only）：全能量范围用PSTAR表格

Author: Tan Song / Claude
Date: 2025-11-19
"""

import os
import json
import shutil
from datetime import datetime
from typing import Dict, List, Optional
import numpy as np

from physics.pstar_parser import parse_pstar_file
from physics.material_registry import Material, registry, make_tabulated_sp
from physics.stopping_power_bethe import bethe_bloch_with_corrections


class MaterialDatabase:
    """材料数据库管理器"""

    def __init__(self, db_dir: str = "materials_db"):
        """
        初始化材料数据库

        Args:
            db_dir: 数据库根目录
        """
        self.db_dir = db_dir
        self.index_file = os.path.join(db_dir, "materials_index.json")
        self.common_materials_file = "utils/common_materials.json"

        # 确保目录存在
        os.makedirs(db_dir, exist_ok=True)

        # 加载索引
        self.index = self._load_index()

        # 加载常用材料数据库
        self.common_materials = self._load_common_materials()

    def _load_index(self) -> Dict:
        """加载材料索引"""
        if os.path.exists(self.index_file):
            try:
                with open(self.index_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"⚠️ 加载索引失败: {e}，创建新索引")

        # 创建新索引
        return {
            "version": "1.0",
            "last_updated": datetime.now().isoformat(),
            "materials": {}
        }

    def _save_index(self):
        """保存材料索引"""
        self.index["last_updated"] = datetime.now().isoformat()
        with open(self.index_file, 'w', encoding='utf-8') as f:
            json.dump(self.index, f, indent=2, ensure_ascii=False)

    def _load_common_materials(self) -> Dict:
        """加载常用材料物理参数数据库"""
        if os.path.exists(self.common_materials_file):
            try:
                with open(self.common_materials_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get('materials', {})
            except Exception as e:
                print(f"⚠️ 加载常用材料数据库失败: {e}")

        return {}

    def get_material_params(self, material_name: str) -> Optional[Dict]:
        """
        获取材料物理参数（从常用材料数据库）

        Args:
            material_name: 材料名称

        Returns:
            材料参数字典，包含density, Z, A, I_eV等
        """
        return self.common_materials.get(material_name)

    def add_material(self,
                     name: str,
                     pstar_file: str,
                     density: float,
                     mode: str = "pstar_only",
                     transition_energy: float = 1.0,
                     bethe_params: Optional[Dict] = None,
                     metadata: Optional[Dict] = None) -> bool:
        """
        添加新材料到数据库

        Args:
            name: 材料名称（标准化后的，如"Aluminum"）
            pstar_file: PSTAR数据文件路径（支持.txt和.csv）
            density: 材料密度（g/cm³）
            mode: "hybrid" | "pstar_only"
            transition_energy: 混合模式的过渡能量（MeV），默认1.0
            bethe_params: Bethe-Bloch参数 {"Z": int, "A": float, "I_eV": float}
            metadata: 额外的元数据

        Returns:
            True if 成功，False if 失败
        """
        try:
            # 1. 验证文件存在
            if not os.path.exists(pstar_file):
                raise FileNotFoundError(f"PSTAR文件不存在: {pstar_file}")

            print(f"正在导入PSTAR文件: {pstar_file}")

            # 2. 创建材料目录
            material_dir = os.path.join(self.db_dir, name)
            os.makedirs(material_dir, exist_ok=True)

            # 3. 复制PSTAR文件到材料目录（保留原始扩展名）
            file_ext = os.path.splitext(pstar_file)[1]  # .txt 或 .csv
            dest_file = os.path.join(material_dir, f"PSTAR_{name}{file_ext}")
            shutil.copy2(pstar_file, dest_file)

            # 4. 读取数据文件信息（数据点数、能量范围）
            data_info = self._read_data_info(dest_file)

            # 5. 创建停止本领函数
            if mode == "hybrid":
                # 混合模式
                if not bethe_params:
                    raise ValueError("混合模式需要提供bethe_params参数")

                sp_func = self._create_hybrid_sp(
                    dest_file,
                    density,
                    transition_energy,
                    bethe_params
                )
            else:
                # 纯PSTAR模式
                sp_func = make_tabulated_sp(
                    dest_file,
                    E_col=0,
                    SP_col=4,  # CSV格式：列4是Total_SP_Mass (MeV·cm²/g)
                    skip_header=self._count_header_lines(dest_file)
                )

            # 6. 创建Material对象
            material = Material(name=name, density=density, sp_func=sp_func)

            # 7. 注册到registry
            registry.register(material, dest_file)

            # 8. 保存元数据
            material_metadata = {
                "name": name,
                "source": "NIST PSTAR",
                "particle_type": "proton",
                "density": density,
                "density_unit": "g/cm³",
                "mode": mode,
                "imported_date": datetime.now().isoformat(),
                "data_points": data_info['data_points'],
                "energy_range_MeV": data_info['energy_range'],
                "pstar_file": dest_file,
            }

            # 混合模式额外信息
            if mode == "hybrid":
                material_metadata["transition_energy"] = transition_energy
                material_metadata["bethe_params"] = bethe_params

            # 用户提供的额外元数据
            if metadata:
                material_metadata.update(metadata)

            # 保存元数据文件
            metadata_file = os.path.join(material_dir, "metadata.json")
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(material_metadata, f, indent=2, ensure_ascii=False)

            # 9. 更新索引
            self.index["materials"][name] = {
                "name": name,
                "display_name": metadata.get("display_name", name) if metadata else name,
                "density": density,
                "particle_type": "proton",
                "data_format": "csv" if file_ext == ".csv" else "pstar",
                "mode": mode,
                "file_path": dest_file,
                "metadata_path": metadata_file,
                "imported_date": datetime.now().isoformat(),
                "energy_range": data_info['energy_range'],
                "data_points": data_info['data_points'],
                "enabled": True
            }

            self._save_index()

            print(f"✓ 材料已添加: {name}")
            print(f"  模式: {mode}")
            print(f"  密度: {density} g/cm³")
            print(f"  数据点数: {data_info['data_points']}")
            print(f"  能量范围: {data_info['energy_range'][0]} - {data_info['energy_range'][1]} MeV")

            return True

        except Exception as e:
            print(f"❌ 添加材料失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _read_data_info(self, filepath: str) -> Dict:
        """读取数据文件的基本信息"""
        skip_lines = self._count_header_lines(filepath)
        energies = []

        with open(filepath, 'r') as f:
            # 跳过标题行
            for _ in range(skip_lines):
                next(f)

            # 读取数据行
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                parts = line.split(',')
                if len(parts) > 0:
                    try:
                        energy = float(parts[0])
                        energies.append(energy)
                    except:
                        continue

        return {
            'data_points': len(energies),
            'energy_range': [min(energies), max(energies)] if energies else [0, 0]
        }


    def _create_hybrid_sp(self,
                          pstar_file: str,
                          density: float,
                          transition_energy: float,
                          bethe_params: Dict):
        """
        创建混合停止本领函数

        Args:
            pstar_file: PSTAR数据文件
            density: 材料密度
            transition_energy: 过渡能量（MeV）
            bethe_params: Bethe-Bloch参数 {"Z": int, "A": float, "I_eV": float}

        Returns:
            混合停止本领函数 S/ρ(E) -> MeV·cm²/g
        """
        # 加载PSTAR表格
        pstar_sp = make_tabulated_sp(
            pstar_file,
            E_col=0,
            SP_col=4,  # CSV格式：列4是Total_SP_Mass (MeV·cm²/g)
            skip_header=self._count_header_lines(pstar_file)
        )

        # Bethe-Bloch参数
        Z = bethe_params['Z']
        A = bethe_params['A']
        I_eV = bethe_params.get('I_eV', 166.0)  # 默认值

        # 导入通用Bethe-Bloch函数
        from physics.stopping_power_bethe import bethe_bloch_generic

        def hybrid_sp(E):
            """混合停止本领函数"""
            if E < transition_energy:
                # 低能：PSTAR表格
                return pstar_sp(E)
            else:
                # 高能：Bethe-Bloch（通用公式，禁用警告）
                S_rho = bethe_bloch_generic(
                    E, Z, A, I_eV, density,
                    warn_low_energy=False  # 禁用警告，因为低能已用PSTAR
                )
                return S_rho

        return hybrid_sp

    def _count_header_lines(self, filepath: str) -> int:
        """计算PSTAR文件的标题行数"""
        with open(filepath, 'r') as f:
            for i, line in enumerate(f):
                line = line.strip()
                if not line:
                    continue

                # 尝试解析为数据行
                parts = line.split()
                if len(parts) >= 4:
                    try:
                        float(parts[0])
                        return i
                    except ValueError:
                        continue

        return 0

    def remove_material(self, name: str) -> bool:
        """
        从数据库删除材料

        Args:
            name: 材料名称

        Returns:
            True if 成功
        """
        try:
            if name not in self.index["materials"]:
                print(f"⚠️ 材料不存在: {name}")
                return False

            # 从registry注销
            if registry.exists(name):
                registry.remove(name)

            # 删除文件目录
            material_dir = os.path.join(self.db_dir, name)
            if os.path.exists(material_dir):
                shutil.rmtree(material_dir)

            # 从索引删除
            del self.index["materials"][name]
            self._save_index()

            print(f"✓ 材料已删除: {name}")
            return True

        except Exception as e:
            print(f"❌ 删除材料失败: {e}")
            return False

    def get_material(self, name: str) -> Optional[Material]:
        """
        从registry获取材料对象

        Args:
            name: 材料名称

        Returns:
            Material对象，或None
        """
        return registry.get(name)

    def list_materials(self) -> List[Dict]:
        """
        列出所有材料

        Returns:
            材料信息列表
        """
        return list(self.index["materials"].values())

    def load_all_materials(self) -> int:
        """
        加载所有材料到registry

        Returns:
            成功加载的材料数量
        """
        loaded_count = 0

        # 材料别名映射（用于兼容旧代码）
        MATERIAL_ALIASES = {
            "Aluminum": ["Al"],
            "Copper": ["Cu"],
            "Chromium": ["Cr"],
            "Titanium": ["Ti"],
            "Silicon": ["Si"],
            "Gold": ["Au"],
            "Silver": ["Ag"],
            "Lead": ["Pb"],
            "Iron": ["Fe"],
            "Tungsten": ["W"],
            "Beryllium": ["Be"],
        }

        print("=" * 70)
        print("从材料数据库加载材料...")
        print("=" * 70)
        print()

        for name, info in self.index["materials"].items():
            if not info.get("enabled", True):
                continue

            # 跳过已加载的
            if registry.exists(name):
                print(f"⊙ {name} 已在registry中，跳过")
                continue

            try:
                # 读取元数据
                metadata_path = info.get("metadata_path")
                if metadata_path and os.path.exists(metadata_path):
                    with open(metadata_path, 'r', encoding='utf-8') as f:
                        metadata = json.load(f)
                else:
                    metadata = {}

                # 获取参数
                density = info["density"]
                mode = info.get("mode", "pstar_only")
                pstar_file = info["file_path"]

                # 创建停止本领函数
                if mode == "hybrid":
                    transition_energy = metadata.get("transition_energy", 1.0)
                    bethe_params = metadata.get("bethe_params")

                    if not bethe_params:
                        print(f"⚠️ {name}: 混合模式缺少bethe_params，使用纯PSTAR模式")
                        mode = "pstar_only"

                if mode == "hybrid":
                    sp_func = self._create_hybrid_sp(
                        pstar_file,
                        density,
                        transition_energy,
                        bethe_params
                    )
                else:
                    sp_func = make_tabulated_sp(
                        pstar_file,
                        E_col=0,
                        SP_col=4,  # CSV格式：列4是Total_SP_Mass
                        skip_header=self._count_header_lines(pstar_file)
                    )

                # 创建并注册材料
                material = Material(name=name, density=density, sp_func=sp_func)
                registry.register(material, pstar_file)

                # 注册别名（直接操作registry字典）
                aliases = MATERIAL_ALIASES.get(name, [])
                for alias in aliases:
                    if not registry.exists(alias):
                        registry.materials[alias] = material
                        registry.csv_paths[alias] = pstar_file

                print(f"✓ {name} ({mode}, {density} g/cm³)")
                loaded_count += 1

            except Exception as e:
                print(f"❌ 加载 {name} 失败: {e}")

        print()
        print(f"✓ 共加载 {loaded_count} 个材料")
        print("=" * 70)
        print()

        return loaded_count

    def get_statistics(self) -> Dict:
        """获取数据库统计信息"""
        total = len(self.index["materials"])
        enabled = sum(1 for m in self.index["materials"].values() if m.get("enabled", True))
        hybrid_count = sum(1 for m in self.index["materials"].values() if m.get("mode") == "hybrid")
        pstar_count = total - hybrid_count

        return {
            "total": total,
            "enabled": enabled,
            "hybrid_mode": hybrid_count,
            "pstar_only": pstar_count
        }


# 全局实例
material_db = MaterialDatabase()


if __name__ == '__main__':
    """测试材料数据库"""
    print("材料数据库测试")
    print("=" * 80)
    print()

    # 显示统计信息
    stats = material_db.get_statistics()
    print(f"数据库统计:")
    print(f"  总材料数: {stats['total']}")
    print(f"  启用材料: {stats['enabled']}")
    print(f"  混合模式: {stats['hybrid_mode']}")
    print(f"  纯PSTAR:  {stats['pstar_only']}")
    print()

    # 列出所有材料
    materials = material_db.list_materials()
    if materials:
        print("已导入材料:")
        for mat in materials:
            print(f"  - {mat['name']:20s} ({mat['mode']}, {mat['density']:.3f} g/cm³)")
    else:
        print("数据库为空")

    print()
    print("=" * 80)
