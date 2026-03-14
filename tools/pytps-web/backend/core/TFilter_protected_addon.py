#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TFilter_protected_addon.py - 轨迹保护滤波扩展
新增选择性滤波功能，保护TPS理论轨迹区域

作者：Claude Code
日期：2025-11-13
"""

import numpy as np
from scipy.ndimage import median_filter, grey_opening

# 这个文件包含要添加到TFilter.py的新函数
# 添加位置：在 validateParams() 函数之后，测试代码之前（约第889行）

# ========================================================================
# 轨迹保护滤波（新增于2025-11-13）
# ========================================================================

def generateTrajectoryMask(img_shape, X0, Y0, A, Z, Emin, Emax, dY, TPS, protectionWidth):
    """
    生成TPS抛物线轨迹掩膜

    根据物理参数计算理论抛物线轨迹，生成保护区域掩膜

    Parameters:
    -----------
    img_shape : tuple
        图像形状 (height, width)
    X0, Y0 : float
        坐标原点（像素）
    A, Z : int
        粒子质量数和电荷数
    Emin, Emax : float
        能量范围（MeV）
    dY : int
        积分窗口半宽（像素）
    TPS : object
        TPS参数对象（包含B, U, L, D等物理参数）
    protectionWidth : int
        保护区域宽度（像素，默认dY*3）

    Returns:
    --------
    mask : ndarray (bool)
        轨迹掩膜，True=轨迹区域（需要保护），False=背景区域（可激进滤波）
    """
    print(f"[TFilter] 生成轨迹掩膜: X0={X0}, Y0={Y0}, A={A}, Z={Z}, Emin={Emin}, Emax={Emax}")
    print(f"[TFilter]   保护宽度={protectionWidth}px (dY={dY})")

    height, width = img_shape
    mask = np.zeros((height, width), dtype=bool)

    # 计算偏转系数（复制自 SolveSpectrum.py:22-27）
    LB = (TPS.L / 2 + TPS.D) * TPS.L
    TB = Z * TPS.B * LB * 0.00998115  # 磁偏转系数
    LE1 = (TPS.L1 * TPS.D1 + TPS.L1 * TPS.L2 + TPS.L1 ** 2 / 2) / TPS.d
    LE2 = (np.log((TPS.L2 + TPS.L3) / TPS.L3) * (TPS.L2 + TPS.L3 + TPS.D1) - TPS.L2) / TPS.theta
    LE = (LE1 + LE2) / 2
    TE = TPS.U * Z * LE / 1000000  # 电偏转系数

    # 计算X范围（复制自 SolveSpectrum.py:33-40）
    if Emin == 0:
        Xmax = width - 1
    else:
        Xmax = int(np.ceil(X0 + TB / np.sqrt(2 * A * Emin) / TPS.Res))
        Xmax = min(Xmax, width - 1)

    Xmin = int(np.floor(X0 + TB / np.sqrt(2 * A * Emax) / TPS.Res))
    Xmin = max(Xmin, 0)

    if Xmin >= Xmax:
        print(f"[TFilter] 警告：X范围无效 (Xmin={Xmin}, Xmax={Xmax})，返回空掩膜")
        return mask

    X = np.arange(Xmin, Xmax + 1, dtype=int)

    # 计算能量（复制自 SolveSpectrum.py:41）
    E = (TB / ((X - X0) * TPS.Res)) ** 2 / (2 * A)

    # 计算Y范围（复制自 SolveSpectrum.py:43, 49）
    Y_center = Y0 + TE / (E * TPS.Res)  # 理论轨迹中心线
    Ymax = np.ceil(Y_center + protectionWidth).astype(int)
    Ymin = np.floor(Y_center - protectionWidth).astype(int)

    # 裁剪到图像范围
    Ymax = np.clip(Ymax, 0, height - 1)
    Ymin = np.clip(Ymin, 0, height - 1)

    # 填充掩膜
    count = 0
    for i, x in enumerate(X):
        if 0 <= x < width:
            y_min = Ymin[i]
            y_max = Ymax[i]
            mask[y_min:y_max+1, x] = True
            count += (y_max - y_min + 1)

    protection_ratio = 100.0 * count / (height * width)
    print(f"[TFilter] 轨迹掩膜生成完成: 保护区域={count}像素 ({protection_ratio:.2f}%)")

    return mask


def protectedFilter(img, X0, Y0, A, Z, Emin, Emax, dY, TPS,
                   protectionWidth, aggressiveSize, gentleSize, rollingBallRadius=0):
    """
    轨迹保护滤波（Trajectory-Protected Filtering）

    算法流程：
    1. 生成轨迹掩膜（标识信号区域）
    2. 在轨迹外区域应用激进滤波（大窗口中值，去除X射线大颗粒噪点）
    3. 在轨迹内区域应用温和滤波（小窗口形态学，保护信号）
    4. 可选：全局滚球法背景减除（去除平滑背景）

    这种方法的优势：
    - 避免滤波"吃掉"真实信号
    - 对轨迹外的X射线噪点、宇宙线等可以激进处理
    - 对轨迹内的质子散射信号温和保护

    Parameters:
    -----------
    img : ndarray
        输入图像（uint16或float64）
    X0, Y0, A, Z, Emin, Emax, dY, TPS :
        TPS物理参数（见generateTrajectoryMask）
    protectionWidth : int
        轨迹保护宽度（像素）
    aggressiveSize : int
        轨迹外激进滤波窗口（11-25，推荐15）
    gentleSize : int
        轨迹内温和滤波窗口（3-7，推荐5）
    rollingBallRadius : int
        可选滚球法半径（0=不使用，>0=应用背景减除）

    Returns:
    --------
    filtered : ndarray
        滤波后的图像
    """
    print(f"[TFilter.protectedFilter] 开始轨迹保护滤波")
    print(f"[TFilter]   轨迹外激进窗口={aggressiveSize}, 轨迹内温和窗口={gentleSize}")

    # 保存原始数据类型
    original_dtype = img.dtype
    img_float = img.astype(np.float64)

    # Step 1: 生成轨迹掩膜
    print(f"[TFilter] Step 1/4: 生成轨迹掩膜...")
    mask = generateTrajectoryMask(img.shape, X0, Y0, A, Z, Emin, Emax, dY, TPS, protectionWidth)

    # Step 2: 轨迹外区域 - 激进滤波（大窗口中值，去除X射线大颗粒）
    print(f"[TFilter] Step 2/4: 轨迹外激进滤波（窗口={aggressiveSize}）...")
    # 确保窗口为奇数
    if aggressiveSize % 2 == 0:
        aggressiveSize += 1

    # 对轨迹外区域应用大窗口中值滤波
    img_aggressive = median_filter(img_float, size=aggressiveSize)

    # Step 3: 轨迹内区域 - 温和滤波（小窗口形态学，保护信号）
    print(f"[TFilter] Step 3/4: 轨迹内温和滤波（窗口={gentleSize}）...")
    # 确保窗口为奇数
    if gentleSize % 2 == 0:
        gentleSize += 1

    # 对轨迹内区域应用小窗口形态学去噪（保留信号峰值）
    img_gentle = grey_opening(img_float, size=gentleSize)

    # 合并：轨迹内用温和滤波，轨迹外用激进滤波
    img_filtered = np.where(mask, img_gentle, img_aggressive)

    # Step 4: 可选 - 全局滚球法背景减除
    if rollingBallRadius > 0:
        print(f"[TFilter] Step 4/4: 全局背景减除（滚球半径={rollingBallRadius}）...")
        # 需要导入 rollingBallBackground_auto_select 函数（这个已在 TFilter.py 中定义）
        # 这里假设调用者已经从TFilter模块导入
        from TFilter import rollingBallBackground_auto_select
        background = rollingBallBackground_auto_select(img_filtered, rollingBallRadius)
        img_filtered = img_filtered - background
        img_filtered[img_filtered < 0] = 0
    else:
        print(f"[TFilter] Step 4/4: 跳过背景减除（rollingBallRadius=0）")

    # 转换回原始数据类型
    if original_dtype == np.uint16:
        img_filtered = np.clip(img_filtered, 0, 65535).astype(np.uint16)
    else:
        img_filtered = img_filtered.astype(original_dtype)

    print(f"[TFilter.protectedFilter] 轨迹保护滤波完成")
    return img_filtered
