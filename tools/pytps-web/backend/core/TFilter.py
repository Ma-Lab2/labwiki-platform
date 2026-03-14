#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TFilter.py - 图像滤波模块
用于去除椒盐噪声和背景，改善Thomson谱仪图像质量

作者：基于filter.py改造
日期：2025-10-23
"""

import numpy as np
from scipy.ndimage import median_filter, minimum_filter, maximum_filter, gaussian_filter, grey_erosion, grey_opening, grey_closing
from scipy.ndimage import binary_dilation, distance_transform_edt, label, percentile_filter, rank_filter
from skimage.morphology import disk, opening
from skimage.measure import regionprops
from skimage.restoration import denoise_nl_means, estimate_sigma

# Numba加速（可选）
try:
    from numba import jit
    NUMBA_AVAILABLE = True
    print("[TFilter] Numba可用，将启用加速功能")
except ImportError:
    NUMBA_AVAILABLE = False
    print("[TFilter] Numba不可用，使用标准实现")
    # 创建空装饰器，使代码可以运行
    def jit(*args, **kwargs):
        def decorator(func):
            return func
        return decorator


def applyFilter(img, filterMode, params):
    """
    应用图像滤波

    Parameters:
    -----------
    img : ndarray
        输入图像（uint16或float64）
    filterMode : str
        滤波模式：
        - "none": 无滤波
        - "median": 中值滤波
        - "morphological": 形态学去噪（推荐！保留信号最好）
        - "rolling_ball": 滚球法背景减除 + 中值滤波
        - "protected": 轨迹保护滤波（需要TPS参数）
        - "soft_mask": 多轨迹软掩膜滤波（新！所有粒子+原点，软边界羽化）
    params : dict
        滤波参数字典：
        - medianSize: 中值滤波窗口大小（奇数，默认5，范围3-15）
        - medianIterations: 中值滤波迭代次数（默认1，范围1-5）
        - morphologicalSize: 形态学结构元素大小（默认3，范围3-7）
        - rollingBallRadius: 滚球法半径（默认20，范围5-50）
        - protectionWidth: 轨迹保护宽度（默认为dY*3，范围dY-dY*5）
        - aggressiveSize: 轨迹外区域激进滤波窗口（默认15，范围11-25）
        - gentleSize: 轨迹内区域温和滤波窗口（默认5，范围3-7）
        - fadeRadius: 软掩膜羽化半径（默认20，范围10-50）
        - TPS参数（用于protected/soft_mask模式）: X0, Y0, A, Z, Emin, Emax, dY, TPS

    Returns:
    --------
    filtered_img : ndarray
        滤波后的图像（与输入相同数据类型）
    """
    print(f"[TFilter.applyFilter] 开始滤波: mode={filterMode}")

    if filterMode == "none":
        print("[TFilter] 无滤波模式，直接返回原图")
        return noFilter(img)
    elif filterMode == "median":
        medianSize = params.get('medianSize', 5)
        medianIterations = params.get('medianIterations', 1)
        print(f"[TFilter] 中值滤波模式，窗口={medianSize}, 迭代={medianIterations}")
        return medianFilter(img, medianSize, medianIterations)
    elif filterMode == "morphological":
        morphologicalSize = params.get('morphologicalSize', 3)
        print(f"[TFilter] 形态学去噪模式，size={morphologicalSize}")
        return morphologicalDenoise(img, morphologicalSize)
    elif filterMode == "rolling_ball":
        rollingBallRadius = params.get('rollingBallRadius', 20)
        medianSize = params.get('medianSize', 5)
        medianIterations = params.get('medianIterations', 1)
        print(f"[TFilter] 滚球法模式，半径={rollingBallRadius}, 中值窗口={medianSize}, 迭代={medianIterations}")
        return rollingBallFilter(img, rollingBallRadius, medianSize, medianIterations)
    elif filterMode == "protected":
        # 检查是否有TPS参数（虽然简化版不需要TPS，但保留兼容性）
        thresholdValue = params.get('thresholdValue', 500)
        morphKernelSize = params.get('morphKernelSize', 3)
        showMask = params.get('showSegmentationMask', False)

        print(f"[TFilter] 形态学分割模式，阈值={thresholdValue}, kernel={morphKernelSize}")
        return protectedFilter(img, thresholdValue, morphKernelSize, showMask)
    elif filterMode == "soft_mask":
        # 多轨迹软掩膜滤波（需要TPS参数）
        X0 = params.get('X0')
        Y0 = params.get('Y0')
        Emin = params.get('Emin')
        Emax = params.get('Emax')
        dY = params.get('dY')
        TPS = params.get('TPS')
        fadeRadius = params.get('fadeRadius', 20)
        rollingBallRadius = params.get('rollingBallRadius', 40)

        if None in [X0, Y0, Emin, Emax, dY, TPS]:
            print(f"[TFilter] 错误：soft_mask模式需要TPS参数，返回原图")
            return noFilter(img)

        print(f"[TFilter] 多轨迹软掩膜模式，羽化半径={fadeRadius}, 滚球半径={rollingBallRadius}")
        return softMaskMultiTrajectory(img, X0, Y0, Emin, Emax, dY, TPS, fadeRadius, rollingBallRadius)
    else:
        # 未知模式，返回原图
        print(f"[TFilter] 警告：未知滤波模式 '{filterMode}'，返回原图")
        return noFilter(img)


def noFilter(img):
    """
    无滤波，直接返回原图

    Parameters:
    -----------
    img : ndarray
        输入图像

    Returns:
    --------
    img : ndarray
        原图
    """
    return img


def medianFilter(img, size=5, iterations=1):
    """
    中值滤波去除椒盐噪声

    Parameters:
    -----------
    img : ndarray
        输入图像
    size : int
        滤波窗口大小（奇数，建议3-15）
    iterations : int
        迭代次数（默认1，可设置2-3以增强去噪）

    Returns:
    --------
    filtered_img : ndarray
        滤波后的图像
    """
    # 参数验证
    if size < 3:
        size = 3
    if size > 15:  # 增大最大窗口
        size = 15
    if size % 2 == 0:  # 确保为奇数
        size += 1

    if iterations < 1:
        iterations = 1
    if iterations > 5:
        print(f"[TFilter] 警告：迭代次数{iterations}过多，限制为5")
        iterations = 5

    # 保存原始数据类型
    original_dtype = img.dtype

    # 转换为float64进行计算
    img_float = img.astype(np.float64)

    # 迭代应用中值滤波（增强去噪）
    filtered = img_float
    for i in range(iterations):
        if iterations > 1:
            print(f"[TFilter]   中值滤波迭代 {i+1}/{iterations}...")
        filtered = median_filter(filtered, size=size)

    # 转换回原始数据类型
    if original_dtype == np.uint16:
        filtered = np.clip(filtered, 0, 65535).astype(np.uint16)
    else:
        filtered = filtered.astype(original_dtype)

    return filtered


def morphologicalDenoise(img, size=3):
    """
    形态学去噪（针对椒盐噪声）

    使用灰度形态学的开闭运算去除椒盐噪声
    - 闭运算：去除黑色噪声点（椒噪声）
    - 开运算：去除白色噪声点（盐噪声）

    优势：
    - 极好地保留信号（99.8%+）
    - 不会模糊图像边缘
    - 速度极快（比迭代中值快20倍）

    Parameters:
    -----------
    img : ndarray
        输入图像
    size : int
        结构元素大小（默认3，范围3-7）

    Returns:
    --------
    denoised : ndarray
        去噪后的图像
    """
    print(f"[TFilter] 形态学去噪: size={size}")

    # 保存原始数据类型
    original_dtype = img.dtype

    # 转换为float64
    img_float = img.astype(np.float64)

    # 闭运算：填充黑色噪声（椒噪声）
    img_closed = grey_closing(img_float, size=size)

    # 开运算：去除白色噪声（盐噪声）
    img_denoised = grey_opening(img_closed, size=size)

    # 转换回原始数据类型
    if original_dtype == np.uint16:
        img_denoised = np.clip(img_denoised, 0, 65535).astype(np.uint16)
    else:
        img_denoised = img_denoised.astype(original_dtype)

    return img_denoised


def rollingBallFilter(img, radius=20, medianSize=5, medianIterations=1):
    """
    滚球法背景减除 + 增强中值滤波
    先去除背景，再去除椒盐噪声

    Parameters:
    -----------
    img : ndarray
        输入图像
    radius : int
        滚球半径（建议10-30，超过30会很慢！）
    medianSize : int
        中值滤波窗口大小（奇数，建议5-11）
    medianIterations : int
        中值滤波迭代次数（默认1，可设2-3增强去噪）

    Returns:
    --------
    filtered_img : ndarray
        滤波后的图像
    """
    # 参数验证和警告
    if radius < 5:
        radius = 5
    if radius > 50:
        print(f"[TFilter] 警告：滚球半径 {radius} 过大，处理会很慢！建议使用10-30")
        print(f"[TFilter] 自动限制半径为50")
        radius = 50

    # 保存原始数据类型
    original_dtype = img.dtype

    # 转换为float64进行计算
    img_float = img.astype(np.float64)

    print(f"[TFilter] 滚球法处理开始... 半径={radius}, 图像形状={img.shape}")
    print(f"[TFilter] 提示：半径越大越慢，请耐心等待或使用更小的半径")

    # Step 1: 滚球法背景减除（自动选择最优实现）
    background = rollingBallBackground_auto_select(img_float, radius)
    img_bg_removed = img_float - background
    img_bg_removed[img_bg_removed < 0] = 0  # 裁剪负值

    print(f"[TFilter] 背景减除完成")

    # Step 2: 增强中值滤波去噪（支持迭代）
    if medianIterations > 1:
        print(f"[TFilter] 应用{medianIterations}次迭代中值滤波（窗口={medianSize}）...")
    filtered = medianFilter(img_bg_removed.astype(original_dtype), medianSize, medianIterations)

    print(f"[TFilter] 滚球法处理完成")

    return filtered


def rollingBallBackground(img, radius):
    """
    滚球法背景估计（使用形态学开运算近似）

    ⚠️ 警告：此方法对大半径很慢，建议使用 rollingBallBackground_fast()

    Parameters:
    -----------
    img : ndarray
        输入图像（float64）
    radius : int
        滚球半径

    Returns:
    --------
    background : ndarray
        估计的背景
    """
    # 使用形态学开运算近似Rolling Ball
    # opening = erosion + dilation，可以去除比结构元素小的亮结构
    print(f"[TFilter] 警告：使用原始滚球法，可能很慢...")
    selem = disk(radius)
    background = opening(img, selem)

    return background


def rollingBallBackground_fast(img, radius):
    """
    快速滚球法背景估计（使用最小值滤波近似）

    比原始版本快10-100倍，效果略有差异但足够好

    Parameters:
    -----------
    img : ndarray
        输入图像（float64）
    radius : int
        滚球半径

    Returns:
    --------
    background : ndarray
        估计的背景
    """
    # 方法：使用最小值滤波近似形态学腐蚀，再用最大值滤波近似膨胀
    # 这等效于 opening 操作，但速度快得多

    # Step 1: 最小值滤波（近似腐蚀）
    print(f"[TFilter] 步骤1/2: 最小值滤波...")
    eroded = minimum_filter(img, size=2*radius+1)

    # Step 2: 最大值滤波（近似膨胀）
    print(f"[TFilter] 步骤2/2: 最大值滤波...")
    background = maximum_filter(eroded, size=2*radius+1)

    return background


def rollingBallBackground_gaussian(img, radius):
    """
    高斯模糊近似滚球法背景（最快，但精度较低）

    适合快速预览，不推荐用于最终分析

    Parameters:
    -----------
    img : ndarray
        输入图像（float64）
    radius : int
        滚球半径

    Returns:
    --------
    background : ndarray
        估计的背景
    """
    # 使用高斯模糊近似背景，sigma ≈ radius/2
    sigma = radius / 2.0
    print(f"[TFilter] 使用高斯模糊近似背景，sigma={sigma:.1f}")
    background = gaussian_filter(img, sigma=sigma)

    return background


def create_ball_kernel(radius):
    """
    创建球形（非平坦）结构元素

    模拟3D半球：z = sqrt(r² - x² - y²)
    这是真正rolling ball算法的核心

    Parameters:
    -----------
    radius : int
        球的半径

    Returns:
    --------
    ball : ndarray
        球形结构元素（带高度信息）
    """
    diameter = 2 * radius + 1
    ball = np.zeros((diameter, diameter), dtype=np.float64)

    center = radius
    r_squared = radius * radius

    for i in range(diameter):
        for j in range(diameter):
            x = i - center
            y = j - center
            dist_squared = x * x + y * y

            if dist_squared <= r_squared:
                # 球面方程: z = sqrt(r² - x² - y²)
                # 球是向上凸起的半球（正值表示高度）
                ball[i, j] = np.sqrt(r_squared - dist_squared)
            else:
                # 球外的点设为负无穷（不参与计算）
                ball[i, j] = -np.inf

    return ball


def rollingBallBackground_true(img, radius, shrink_factor=1):
    """
    真正的Rolling Ball背景估计（ImageJ风格）

    使用球形（非平坦）结构元素进行灰度形态学腐蚀
    更准确地模拟"球在图像表面下滚动"

    优势：
    - 对强峰值的背景估计更准确
    - 不会"吃掉"真实信号
    - 与ImageJ结果更接近

    Parameters:
    -----------
    img : ndarray
        输入图像（float64）
    radius : int
        滚球半径
    shrink_factor : int
        下采样因子（1=不下采样，2=缩小2倍加速）

    Returns:
    --------
    background : ndarray
        估计的背景
    """
    print(f"[TFilter] 使用真正的Rolling Ball算法（球形SE，半径={radius}）")

    # 下采样加速（可选）
    if shrink_factor > 1:
        print(f"[TFilter]   下采样因子={shrink_factor}（加速处理）")
        original_shape = img.shape
        img_small = img[::shrink_factor, ::shrink_factor]
        radius_small = max(1, radius // shrink_factor)
    else:
        img_small = img
        radius_small = radius

    # 创建球形结构元素
    print(f"[TFilter]   创建球形结构元素...")
    ball = create_ball_kernel(radius_small)

    # 灰度形态学腐蚀（模拟球滚动）
    # grey_erosion(img, structure) = min{img(x+i,y+j) - structure(i,j)}
    # 相当于：在每个点放置球底部，找能升到的最高位置（仍在图像下方）
    print(f"[TFilter]   执行灰度腐蚀（Rolling Ball）...")

    # 使用球形SE进行灰度腐蚀
    # footprint定义球的形状区域
    footprint = (ball > -np.inf).astype(np.uint8)
    # structure定义球面高度
    background_small = grey_erosion(img_small, footprint=footprint, structure=ball)

    # 上采样回原始尺寸
    if shrink_factor > 1:
        print(f"[TFilter]   上采样到原始尺寸...")
        from scipy.ndimage import zoom
        background = zoom(background_small, shrink_factor, order=1)

        # 裁剪到原始尺寸（处理shrink导致的尺寸不匹配）
        background = background[:original_shape[0], :original_shape[1]]
    else:
        background = background_small

    print(f"[TFilter] 真正的Rolling Ball完成")
    return background


def rollingBallBackground_auto_select(img, radius):
    """
    自动选择最优的Rolling Ball实现

    根据半径大小和图像尺寸自动选择：
    - 小半径（<15）：真正的球形SE（准确）
    - 中半径（15-30）：快速近似（平衡）
    - 大半径（>30）：快速近似+下采样（速度优先）

    Parameters:
    -----------
    img : ndarray
        输入图像（float64）
    radius : int
        滚球半径

    Returns:
    --------
    background : ndarray
        估计的背景
    """
    img_size = img.shape[0] * img.shape[1]

    # 小半径：使用真正的球形SE（准确）
    if radius < 15:
        print(f"[TFilter] 半径{radius}较小，使用真正的Rolling Ball（球形SE）")
        return rollingBallBackground_true(img, radius, shrink_factor=1)

    # 中半径：快速近似（平衡）
    elif radius < 30:
        print(f"[TFilter] 半径{radius}，使用快速近似（平坦SE）")
        return rollingBallBackground_fast(img, radius)

    # 大半径：快速近似（速度优先）
    else:
        print(f"[TFilter] 半径{radius}较大，使用快速近似")
        return rollingBallBackground_fast(img, radius)


# ========================================================================
# 轨迹保护滤波（新增于2025-11-13）
# ========================================================================

def generateMultiTrajectoryMask(img_shape, X0, Y0, Emin, Emax, dY, TPS, protectionWidth,
                                particle_list=None):
    """
    生成多条TPS抛物线轨迹的联合掩膜（支持H1, C6, O7, C5, C1等）

    Parameters:
    -----------
    img_shape : tuple
        图像形状 (height, width)
    X0, Y0 : float
        坐标原点（像素，**Y0是翻转后的坐标**）
    Emin, Emax : float
        能量范围（MeV）
    dY : int
        积分窗口半宽（像素）
    TPS : object
        TPS参数对象（包含B, U, L, D等物理参数）
    protectionWidth : int
        保护区域宽度（像素）
    particle_list : list of tuples, optional
        粒子列表 [(A1, Z1, name1), (A2, Z2, name2), ...]
        默认为常见离子：H1, C6, O7, C5, C1

    Returns:
    --------
    mask : ndarray (bool)
        联合轨迹掩膜，True=任意轨迹区域，False=背景区域
    """
    # 默认粒子列表：常见离子
    if particle_list is None:
        particle_list = [
            (1, 1, 'H1'),      # 质子
            (12, 6, 'C6'),     # C6+
            (16, 7, 'O7'),     # O7+
            (12, 5, 'C5'),     # C5+
            (12, 1, 'C1'),     # C+
        ]

    height, width = img_shape
    mask_combined = np.zeros((height, width), dtype=bool)

    print(f"[TFilter] 生成多轨迹联合掩膜（保护宽度={protectionWidth}px）:")

    for A, Z, name in particle_list:
        # 生成单条轨迹掩膜
        mask_single = generateTrajectoryMask(img_shape, X0, Y0, A, Z, Emin, Emax, dY, TPS, protectionWidth)

        # 合并到联合掩膜
        n_pixels_added = np.sum(mask_single & ~mask_combined)
        mask_combined |= mask_single

        print(f"[TFilter]   - {name} (A={A}, Z={Z}): 新增保护区域={n_pixels_added}像素")

    total_protected = np.sum(mask_combined)
    protection_ratio = 100.0 * total_protected / (height * width)
    print(f"[TFilter]   >>> 总保护区域={total_protected}像素 ({protection_ratio:.2f}%)")

    return mask_combined


def generateTrajectoryMask(img_shape, X0, Y0, A, Z, Emin, Emax, dY, TPS, protectionWidth):
    """
    生成TPS抛物线轨迹掩膜

    根据物理参数计算理论抛物线轨迹，生成保护区域掩膜

    **重要**：此函数在图像翻转之前调用，但Y0是翻转后的坐标，需要转换！

    Parameters:
    -----------
    img_shape : tuple
        图像形状 (height, width)
    X0, Y0 : float
        坐标原点（像素，**Y0是翻转后的坐标**）
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
    height, width = img_shape

    # **测试两种坐标理解**
    # 假设1：Y0是翻转后坐标，需要转换
    Y0_flip_assumption = height - 1 - Y0
    # 假设2：Y0本来就是原始坐标，不需要转换
    Y0_no_flip_assumption = Y0

    print(f"[TFilter] 生成轨迹掩膜调试:")
    print(f"[TFilter]   输入参数: X0={X0}, Y0={Y0}, 图像={img_shape}")
    print(f"[TFilter]   假设1(需翻转): Y0_before={Y0_flip_assumption}")
    print(f"[TFilter]   假设2(不翻转): Y0_before={Y0_no_flip_assumption}")
    print(f"[TFilter]   保护宽度={protectionWidth}px (dY={dY})")

    # **使用假设1：Y0是翻转后的物理坐标，需要转换为原始图像坐标**
    Y0_before_flip = Y0_flip_assumption

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

    # 计算Y范围（使用翻转前的Y0坐标）
    # 注意：翻转前Y轴向下（Y=0在顶部），翻转后Y轴向上（Y=0在底部）
    # 所以电偏转公式需要反号
    Y_center = Y0_before_flip - TE / (E * TPS.Res)  # 理论轨迹中心线（翻转前坐标）
    Ymax = np.ceil(Y_center + protectionWidth).astype(int)
    Ymin = np.floor(Y_center - protectionWidth).astype(int)

    # 裁剪到图像范围
    Ymax = np.clip(Ymax, 0, height - 1)
    Ymin = np.clip(Ymin, 0, height - 1)

    # 填充掩膜
    count = 0
    y_positions = []  # 记录所有Y位置用于调试
    for i, x in enumerate(X):
        if 0 <= x < width:
            y_min = Ymin[i]
            y_max = Ymax[i]
            mask[y_min:y_max+1, x] = True
            count += (y_max - y_min + 1)
            if i % (len(X) // 5) == 0:  # 记录5个采样点
                y_positions.append((x, y_min, y_max, Y_center[i]))

    protection_ratio = 100.0 * count / (height * width)
    print(f"[TFilter] 轨迹掩膜生成完成: 保护区域={count}像素 ({protection_ratio:.2f}%)")
    print(f"[TFilter]   Y范围示例（翻转前坐标）:")
    for x, ymin, ymax, ycenter in y_positions:
        print(f"[TFilter]     X={x}: Y_center={ycenter:.1f}, Y保护范围=[{ymin}, {ymax}]")

    # 计算翻转后的Y坐标（仅用于调试显示）
    if len(y_positions) > 0:
        print(f"[TFilter]   对应翻转后坐标（物理坐标）:")
        for x, ymin, ymax, ycenter in y_positions:
            ymin_after = height - 1 - ymax
            ymax_after = height - 1 - ymin
            ycenter_after = height - 1 - ycenter
            print(f"[TFilter]     X={x}: Y_center={ycenter_after:.1f}, Y保护范围=[{ymin_after}, {ymax_after}]")

    return mask


def protectedFilter(img, thresholdValue, morphKernelSize, showMask=False):
    """
    形态学分割滤波（Morphological Segmentation Filtering）

    算法流程：
    1. 灰度阈值二值化 - 将图像分为信号和背景
    2. 形态学开运算 - 去除小的孤立点（芝麻），保留连续结构（轨迹）
    3. 可选显示mask - 用于调试和调节阈值
    4. 基于mask处理 - 保留轨迹区域，背景区域去噪

    Parameters:
    -----------
    img : ndarray
        输入图像（uint16或uint8）
    thresholdValue : int
        灰度阈值（0-65535 for 16-bit, 0-255 for 8-bit）
    morphKernelSize : int
        形态学kernel大小（奇数，3-15）
    showMask : bool
        是否返回mask用于调试（默认False）

    Returns:
    --------
    filtered_img : ndarray
        滤波后的图像（与输入相同数据类型）
        如果showMask=True，返回mask（bool数组）
    """
    print(f"[TFilter.protectedFilter] 形态学分割滤波")
    print(f"[TFilter]   参数：阈值={thresholdValue}, kernel={morphKernelSize}, 显示mask={showMask}")

    # 保存原始数据类型
    original_dtype = img.dtype
    img_float = img.astype(np.float64)

    # Step 1: 灰度阈值二值化
    print(f"[TFilter] Step 1: 灰度阈值二值化（阈值={thresholdValue}）...")
    binary_mask = img > thresholdValue
    num_above_threshold = np.sum(binary_mask)
    total_pixels = binary_mask.size
    print(f"[TFilter]   - 超过阈值的像素：{num_above_threshold} / {total_pixels} ({100*num_above_threshold/total_pixels:.2f}%)")

    # Step 2: 形态学开运算（去除小点，保留大结构）
    print(f"[TFilter] Step 2: 形态学开运算（kernel={morphKernelSize}x{morphKernelSize}）...")
    from skimage.morphology import opening, disk
    # 创建圆形结构元素
    selem = disk(morphKernelSize // 2)
    # 开运算 = 腐蚀 + 膨胀（去除小于kernel的孤立点）
    mask_opened = opening(binary_mask, selem)
    num_after_opening = np.sum(mask_opened)
    num_removed = num_above_threshold - num_after_opening
    print(f"[TFilter]   - 开运算后剩余：{num_after_opening} 像素")
    print(f"[TFilter]   - 去除了 {num_removed} 个小点（芝麻）({100*num_removed/num_above_threshold:.2f}%）")

    # Step 3: 如果需要显示mask，直接返回
    if showMask:
        print(f"[TFilter] 返回分割mask（调试模式）")
        # 将mask转换为图像格式（白色=轨迹，黑色=背景）
        if original_dtype == np.uint16:
            mask_img = (mask_opened.astype(np.uint16) * 65535)
        else:
            mask_img = (mask_opened.astype(np.uint8) * 255)
        return mask_img

    # Step 4: 基于mask处理图像
    print(f"[TFilter] Step 3: 基于mask处理图像...")

    # 4.1 轨迹区域：保持原样
    # 4.2 背景区域：应用中值滤波去噪
    from scipy.ndimage import median_filter as median_filter_scipy
    bg_filtered = median_filter_scipy(img_float, size=5)

    # 4.3 合成最终图像
    img_out = img_float.copy()
    # 背景区域用滤波后的
    img_out[~mask_opened] = bg_filtered[~mask_opened]
    # 轨迹区域保持原样（已经是img_float了）

    num_protected = np.sum(mask_opened)
    num_filtered = total_pixels - num_protected
    print(f"[TFilter]   - 保护区域（轨迹）：{num_protected} 像素（保持原样）")
    print(f"[TFilter]   - 背景区域：{num_filtered} 像素（中值滤波去噪）")

    # 转换回原始数据类型
    if original_dtype == np.uint16:
        img_out = np.clip(img_out, 0, 65535).astype(np.uint16)
    else:
        img_out = img_out.astype(original_dtype)

    print(f"[TFilter.protectedFilter] 形态学分割滤波完成")
    print(f"[TFilter]   关键成果：")
    print(f"[TFilter]   - 通过阈值分离轨迹和背景")
    print(f"[TFilter]   - 开运算去除{num_removed}个芝麻点")
    print(f"[TFilter]   - 轨迹区域完全保护，背景区域去噪")

    return img_out


def softMaskMultiTrajectory(img, X0, Y0, Emin, Emax, dY, TPS,
                            protection_width=None, fade_radius=20, rolling_ball_radius=40):
    """
    多条轨迹软掩膜滤波 + 均匀背景羽化

    核心思路（简洁方案）：
    1. 为所有常见粒子（H-1, C-4/5/6, O-6/7/8等）生成轨迹掩膜
    2. 加上原点保护区域
    3. 合并成一个大掩膜，用距离变换生成软边界（羽化）
    4. 估计均匀背景：
       4a. 轨迹掩膜内置0 - 不污染背景估计
       4b. 掩膜外采样 - 取较暗60%的中位数作为背景值
       4c. 生成均匀背景 - 全图填充该背景值
    5. 软掩膜混合：I_final = B + W * (I - B)
       - 掩膜内：保留原图结构
       - 掩膜外：通过羽化平滑过渡到均匀背景
    6. 弱平滑：消除残余硬边

    Parameters:
    -----------
    img : ndarray
        输入图像
    X0, Y0 : int
        原点坐标
    Emin, Emax : float
        能量范围
    dY : int
        积分窗口半宽
    TPS : TPS参数对象
    protection_width : int, optional
        轨迹保护宽度（像素），每条轨迹周围保护多宽，默认为dY*3
    fade_radius : int
        羽化半径（像素），从掩膜边缘往外平滑衰减的距离
    rolling_ball_radius : int
        （本方案中未使用，保留参数兼容性）

    Returns:
    --------
    img_cleaned : ndarray
        软掩膜滤波后的图像

    优势（解决泡泡问题）：
    - 轨迹置0：避免轨迹污染背景估计
    - 均匀背景：无滚球的圆形结构元阴影，无泡泡
    - 软掩膜羽化：边缘平滑过渡，视觉自然
    """
    print(f"[TFilter.softMaskMultiTrajectory] 开始多轨迹软掩膜滤波")

    # 默认轨迹保护宽度
    if protection_width is None:
        protection_width = int(dY * 3)

    print(f"[TFilter]   参数：protection_width={protection_width}, fade_radius={fade_radius}, rolling_ball_radius={rolling_ball_radius}")

    height, width = img.shape
    img_float = img.astype(np.float64)

    # Step 1: 生成所有粒子轨迹的掩膜
    print(f"[TFilter] Step 1: 生成多条轨迹掩膜...")

    # 常见粒子列表 (A, Z, name)
    particles = [
        (1, 1, "H-1"),     # 质子
        (12, 4, "C-4"),    # C4+
        (12, 5, "C-5"),    # C5+
        (12, 6, "C-6"),    # C6+ (完全电离)
        (16, 6, "O-6"),    # O6+
        (16, 7, "O-7"),    # O7+
        (16, 8, "O-8"),    # O8+ (完全电离)
        (1, 1, "H1"),      # H1+ (与质子相同)
    ]

    # 合并所有轨迹掩膜
    mask_all = np.zeros((height, width), dtype=bool)

    for A, Z, name in particles:
        mask_single = generateTrajectoryMask(
            img.shape, X0, Y0, A, Z, Emin, Emax, dY, TPS, protection_width
        )
        mask_all |= mask_single
        count = np.sum(mask_single)
        print(f"[TFilter]   - {name} (A={A}, Z={Z}): {count} 像素")

    # Step 2: 加上原点保护区域（圆形，使用相同的protection_width作为半径）
    print(f"[TFilter] Step 2: 添加原点保护区域...")
    origin_radius = protection_width
    Y0_before_flip = height - 1 - Y0  # Y0是翻转后坐标

    yy, xx = np.ogrid[:height, :width]
    dist_to_origin = np.sqrt((xx - X0)**2 + (yy - Y0_before_flip)**2)
    mask_origin = dist_to_origin <= origin_radius
    mask_all |= mask_origin

    origin_count = np.sum(mask_origin)
    print(f"[TFilter]   - 原点区域: {origin_count} 像素 (半径={origin_radius})")

    total_protected = np.sum(mask_all)
    protection_ratio = 100.0 * total_protected / (height * width)
    print(f"[TFilter]   - 总保护区域: {total_protected} 像素 ({protection_ratio:.2f}%)")

    # Step 3: 生成软掩膜（距离变换 + 羽化）
    print(f"[TFilter] Step 3: 生成软掩膜（protection_width={protection_width}, fade_radius={fade_radius}）...")

    from scipy.ndimage import distance_transform_edt

    # 到掩膜的距离（外部为正，内部为负）
    D_outside = distance_transform_edt(~mask_all)  # 掩膜外到边界的距离
    D_inside = distance_transform_edt(mask_all)    # 掩膜内到边界的距离

    # 合并：掩膜内为负，掩膜外为正
    D = np.where(mask_all, -D_inside, D_outside)

    # 生成软掩膜 W：
    # - 掩膜内完全保留 (W=1)
    # - fade_radius外完全抛弃 (W=0)
    # - 中间羽化过渡
    W = np.ones((height, width), dtype=np.float64)

    # 掩膜内完全保留
    W[D <= 0] = 1.0

    # 掩膜外fade_radius之外完全抛弃
    W[D >= fade_radius] = 0.0

    # 中间过渡区：用 cos^2 平滑衰减（比线性好看）
    # 注意：这里0到fade_radius是过渡区
    transition_mask = (D > 0) & (D < fade_radius)
    t = D[transition_mask] / fade_radius  # 0~1
    W[transition_mask] = np.cos(0.5 * np.pi * t) ** 2  # 1→0 平滑

    print(f"[TFilter]   - 完全保留区域(W=1): {np.sum(W >= 0.99):.0f} 像素")
    print(f"[TFilter]   - 羽化过渡区域: {np.sum((W > 0.01) & (W < 0.99)):.0f} 像素")
    print(f"[TFilter]   - 完全抑制区域(W=0): {np.sum(W <= 0.01):.0f} 像素")
    print(f"[TFilter]   - 总影响范围: 轨迹宽度(2*{protection_width}+1={2*protection_width+1}px) + 上下羽化(2*{fade_radius}={2*fade_radius}px) = 总共{2*protection_width+1+2*fade_radius}像素")

    # Step 4: 估计均匀背景（简洁方案：轨迹置0，远离区域采样）
    print(f"[TFilter] Step 4: 估计均匀背景（轨迹置0，掩膜外采样）...")

    # Step 4a: 把轨迹区域置0，不参与背景估计
    I_for_bg = img_float.copy()
    I_for_bg[mask_all] = 0

    # Step 4b: 只用掩膜外的像素估计背景（取较暗的60%作为背景样本）
    bg_candidates = I_for_bg[~mask_all]
    bg_candidates = bg_candidates[bg_candidates > 0]  # 去除0值

    if len(bg_candidates) > 0:
        # 取较暗的60%作为纯背景
        p60 = np.percentile(bg_candidates, 60)
        bg_samples = bg_candidates[bg_candidates <= p60]

        if len(bg_samples) > 0:
            bg_level = np.median(bg_samples)  # 均匀背景值
        else:
            bg_level = np.median(bg_candidates)
    else:
        bg_level = np.median(img_float[img_float > 0])

    # Step 4c: 生成均匀背景
    B = np.full_like(img_float, bg_level)

    print(f"[TFilter]   - 背景样本数: {len(bg_samples) if len(bg_candidates) > 0 else 0}")
    print(f"[TFilter]   - 均匀背景值: {bg_level:.1f}")

    # Step 5: 混合：原图和均匀背景羽化过渡
    print(f"[TFilter] Step 5: 软掩膜混合（原图和均匀背景羽化过渡）...")

    # I_final = B + W * (I - B)
    # 掩膜内：保留原图结构
    # 掩膜外：渐变到均匀背景
    img_cleaned = B + W * (img_float - B)

    # 统计去除效果
    signal_removed = np.sum(img_float * (1 - W))
    total_signal = np.sum(img_float)

    print(f"[TFilter]   - 原始总信号：{total_signal:.0f}")
    print(f"[TFilter]   - 压制信号：{signal_removed:.0f} ({100*signal_removed/total_signal:.1f}%)")

    # Step 6: 可选的弱平滑（统一气质，消除硬边）
    # 只在有羽化时才需要弱平滑，fade_radius=0时跳过
    if fade_radius > 0:
        print(f"[TFilter] Step 6: 整体弱平滑（消除硬边，sigma=0.7）...")
        from scipy.ndimage import gaussian_filter
        img_cleaned = gaussian_filter(img_cleaned, sigma=0.7)
    else:
        print(f"[TFilter] Step 6: 跳过弱平滑（fade_radius=0，保持硬边）")

    # 转换回原始数据类型
    if img.dtype == np.uint16:
        img_cleaned = np.clip(img_cleaned, 0, 65535).astype(np.uint16)
    else:
        img_cleaned = img_cleaned.astype(img.dtype)

    print(f"[TFilter.softMaskMultiTrajectory] 完成")
    print(f"[TFilter]   核心思路：")
    print(f"[TFilter]     1. 轨迹置0：不污染背景估计")
    print(f"[TFilter]     2. 掩膜外采样：估计均匀背景（取较暗60%的中位数）")
    print(f"[TFilter]     3. 软掩膜羽化：原图和均匀背景平滑过渡")
    print(f"[TFilter]   参数说明：")
    print(f"[TFilter]     - 保护宽度={protection_width}：从轨迹中心线向上下各{protection_width}像素（总宽度={2*protection_width+1}px）")
    print(f"[TFilter]     - 羽化半径={fade_radius}：从保护边缘往外再过渡{fade_radius}像素（上下共{2*fade_radius}px）")
    print(f"[TFilter]     - 总影响范围={2*protection_width+1+2*fade_radius}像素")
    if fade_radius == 0:
        print(f"[TFilter]     注意：fade_radius=0时为硬切边缘，无羽化，无平滑")

    return img_cleaned


def trajectoryCoordinateBackgroundSubtraction(img, X0, Y0, A, Z, Emin, Emax, dY, TPS,
                                             envelope_width=20, core_width=3):
    """
    轨迹坐标背景减除：物理驱动的散射背景去除

    核心思路：
    1. 把理论轨迹转换到(s,t)坐标系：s=沿轨迹，t=垂直轨迹
    2. 在t方向统计估计散射背景轮廓B(t)
    3. 从每个剖面减去B(t)，只留下轨迹窄峰

    物理假设：
    - 准直孔散射在t上形状大体不随s变化
    - 真正的质子轨迹在t上是很窄的峰，在s上持续存在

    Parameters:
    -----------
    img : ndarray
        输入图像
    X0, Y0, A, Z, Emin, Emax, dY, TPS : TPS物理参数
    envelope_width : int
        条带半宽（像素），覆盖散射光晕范围
    core_width : int
        核心带半宽（像素），真正信号的半宽

    Returns:
    --------
    img_cleaned : ndarray
        背景减除后的图像
    """
    print(f"[TFilter.trajectoryCoordinateBackgroundSubtraction] 开始轨迹坐标背景减除")
    print(f"[TFilter]   参数：envelope_width={envelope_width}, core_width={core_width}")

    height, width = img.shape
    img_float = img.astype(np.float64)

    # Step 1: 参数化理论轨迹
    print(f"[TFilter] Step 1: 参数化理论轨迹...")

    # 沿X方向均匀采样
    Ns = 800  # 沿轨迹采样点数
    x_min = max(X0 - 100, 0)
    x_max = min(X0 + 400, width - 1)
    x_s = np.linspace(x_min, x_max, Ns)

    # 计算理论轨迹Y坐标（使用generateTrajectoryMask中相同的物理公式）
    # 使用正确的偏转系数公式（复制自 SolveSpectrum.py）
    LB = (TPS.L / 2 + TPS.D) * TPS.L
    TB = Z * TPS.B * LB * 0.00998115  # 磁偏转系数
    LE1 = (TPS.L1 * TPS.D1 + TPS.L1 * TPS.L2 + TPS.L1 ** 2 / 2) / TPS.d
    LE2 = (np.log((TPS.L2 + TPS.L3) / TPS.L3) * (TPS.L2 + TPS.L3 + TPS.D1) - TPS.L2) / TPS.theta
    LE = (LE1 + LE2) / 2
    TE = TPS.U * Z * LE / 1000000  # 电偏转系数

    print(f"[TFilter]   - 偏转系数：TB={TB:.3e}, TE={TE:.3e}")

    # 处理Y0坐标翻转（Y0是翻转后坐标，需要转换为翻转前坐标）
    Y0_before_flip = height - 1 - Y0

    # 创建输出图像
    img_cleaned = np.zeros_like(img_float)

    # 计算X范围和能量（与generateTrajectoryMask相同的方法）
    if Emin == 0:
        Xmax_calc = width - 1
    else:
        Xmax_calc = int(np.ceil(X0 + TB / np.sqrt(2 * A * Emin) / TPS.Res))
        Xmax_calc = min(Xmax_calc, width - 1)

    Xmin_calc = int(np.floor(X0 + TB / np.sqrt(2 * A * Emax) / TPS.Res))
    Xmin_calc = max(Xmin_calc, 0)

    # 调整采样范围为计算出的有效X范围
    x_min = max(Xmin_calc, 0)
    x_max = min(Xmax_calc, width - 1)
    x_s = np.linspace(x_min, x_max, Ns)

    # 对每个x，计算对应的y和能量
    y_s = np.zeros(Ns)
    valid_mask = np.zeros(Ns, dtype=bool)

    for i, x in enumerate(x_s):
        # 从X坐标反推能量E（与generateTrajectoryMask相同的公式）
        delta_x = x - X0
        if abs(delta_x) > 0.1:  # 避免除零
            E = (TB / (delta_x * TPS.Res)) ** 2 / (2 * A)

            if Emin <= E <= Emax:
                # 计算Y坐标（使用翻转前坐标，与generateTrajectoryMask相同）
                y_theory = Y0_before_flip - TE / (E * TPS.Res)

                if 0 <= y_theory < height:
                    y_s[i] = y_theory
                    valid_mask[i] = True

    if not np.any(valid_mask):
        print("[TFilter] 警告：无法计算有效轨迹，返回原图")
        return img

    # 只保留有效部分
    x_s = x_s[valid_mask]
    y_s = y_s[valid_mask]
    Ns = len(x_s)

    print(f"[TFilter]   - 轨迹有效采样点：{Ns}")

    # Step 2: 计算切向量和法向量
    print(f"[TFilter] Step 2: 计算切向量和法向量...")

    dx = np.gradient(x_s)
    dy = np.gradient(y_s)
    L = np.hypot(dx, dy)

    # 切向量
    tx = dx / L
    ty = dy / L

    # 法向量（垂直于切向量）
    nx = -ty
    ny = tx

    # Step 3: 提取条带并映射到(s,t)坐标
    print(f"[TFilter] Step 3: 提取条带（宽度±{envelope_width}像素）...")

    t_samples = np.arange(-envelope_width, envelope_width + 1)
    Nt = len(t_samples)

    # 构建条带坐标
    I_band = np.zeros((Nt, Ns))

    from scipy.interpolate import RegularGridInterpolator
    # 创建插值器
    yy = np.arange(height)
    xx = np.arange(width)
    interpolator = RegularGridInterpolator((yy, xx), img_float,
                                          method='linear', bounds_error=False, fill_value=0)

    for i, s_idx in enumerate(range(Ns)):
        for j, t in enumerate(t_samples):
            # 计算采样点坐标
            x_sample = x_s[s_idx] + t * nx[s_idx]
            y_sample = y_s[s_idx] + t * ny[s_idx]

            # 插值
            if 0 <= y_sample < height and 0 <= x_sample < width:
                I_band[j, i] = interpolator([y_sample, x_sample])[0]

    print(f"[TFilter]   - 条带大小：{I_band.shape} (Nt×Ns)")

    # Step 4: 估计散射背景轮廓B(t)
    print(f"[TFilter] Step 4: 估计散射背景轮廓B(t)...")

    B_t = np.zeros(Nt)

    # 核心带索引（|t| <= core_width）
    center_idx = np.where(np.abs(t_samples) <= core_width)[0]

    for it in range(Nt):
        vals = I_band[it, :]

        # 去除极端值（保留中间80%）
        vals_sorted = np.sort(vals[vals > 0])
        if len(vals_sorted) > 0:
            m = len(vals_sorted)
            trim_start = int(0.1 * m)
            trim_end = int(0.9 * m)
            if trim_end > trim_start:
                vals_trimmed = vals_sorted[trim_start:trim_end]
                B_t[it] = np.median(vals_trimmed)

    # 平滑B_t
    from scipy.signal import savgol_filter
    if Nt >= 7:
        B_t_smooth = savgol_filter(B_t, window_length=7, polyorder=2)
    else:
        B_t_smooth = B_t

    print(f"[TFilter]   - 背景轮廓B(t)估计完成")
    print(f"[TFilter]   - B(t)范围：{B_t_smooth.min():.1f} - {B_t_smooth.max():.1f}")

    # Step 5: 从条带减去背景
    print(f"[TFilter] Step 5: 减除背景...")

    I_clean_band = I_band - B_t_smooth[:, np.newaxis]
    I_clean_band[I_clean_band < 0] = 0

    # 统计去除效果
    total_signal = np.sum(I_band)
    removed_signal = np.sum(B_t_smooth[:, np.newaxis])
    remaining_signal = np.sum(I_clean_band)

    print(f"[TFilter]   - 原始信号：{total_signal:.0f}")
    print(f"[TFilter]   - 去除背景：{removed_signal:.0f} ({100*removed_signal/total_signal:.1f}%)")
    print(f"[TFilter]   - 剩余信号：{remaining_signal:.0f} ({100*remaining_signal/total_signal:.1f}%)")

    # Step 6: 写回原图
    print(f"[TFilter] Step 6: 写回原图...")

    img_cleaned = img_float.copy()

    # 将清洁后的条带写回原图
    for i, s_idx in enumerate(range(Ns)):
        for j, t in enumerate(t_samples):
            x_sample = x_s[s_idx] + t * nx[s_idx]
            y_sample = y_s[s_idx] + t * ny[s_idx]

            xi = int(round(x_sample))
            yi = int(round(y_sample))

            if 0 <= yi < height and 0 <= xi < width:
                img_cleaned[yi, xi] = I_clean_band[j, i]

    # 转换回原始数据类型
    if img.dtype == np.uint16:
        img_cleaned = np.clip(img_cleaned, 0, 65535).astype(np.uint16)
    else:
        img_cleaned = img_cleaned.astype(img.dtype)

    print(f"[TFilter.trajectoryCoordinateBackgroundSubtraction] 完成")
    print(f"[TFilter]   核心优势：利用理论轨迹，统计估计散射背景并精确减除")

    return img_cleaned


# ========================================================================
# Numba加速版本（可选）
# ========================================================================

@jit(nopython=True, cache=True)
def _minimum_filter_1d_numba(arr, size):
    """
    Numba优化的1D最小值滤波

    使用滑动窗口实现，复杂度O(n*size)
    """
    n = len(arr)
    result = np.empty(n, dtype=arr.dtype)
    half = size // 2

    for i in range(n):
        left = max(0, i - half)
        right = min(n, i + half + 1)
        result[i] = np.min(arr[left:right])

    return result


@jit(nopython=True, cache=True)
def _maximum_filter_1d_numba(arr, size):
    """
    Numba优化的1D最大值滤波
    """
    n = len(arr)
    result = np.empty(n, dtype=arr.dtype)
    half = size // 2

    for i in range(n):
        left = max(0, i - half)
        right = min(n, i + half + 1)
        result[i] = np.max(arr[left:right])

    return result


def _minimum_filter_separable_numba(img, size):
    """
    分离式最小值滤波（先横向后纵向）

    复杂度：O(N*M*size) vs O(N*M*size²)
    对于大size，速度提升显著
    """
    rows, cols = img.shape

    # 横向滤波
    temp = np.empty_like(img)
    for i in range(rows):
        temp[i, :] = _minimum_filter_1d_numba(img[i, :], size)

    # 纵向滤波
    result = np.empty_like(img)
    for j in range(cols):
        result[:, j] = _minimum_filter_1d_numba(temp[:, j], size)

    return result


def _maximum_filter_separable_numba(img, size):
    """
    分离式最大值滤波（先横向后纵向）
    """
    rows, cols = img.shape

    # 横向滤波
    temp = np.empty_like(img)
    for i in range(rows):
        temp[i, :] = _maximum_filter_1d_numba(img[i, :], size)

    # 纵向滤波
    result = np.empty_like(img)
    for j in range(cols):
        result[:, j] = _maximum_filter_1d_numba(temp[:, j], size)

    return result


def rollingBallBackground_numba(img, radius):
    """
    Numba加速版滚球法背景估计

    使用分离式滤波器，对大半径有显著加速

    Parameters:
    -----------
    img : ndarray
        输入图像（float64）
    radius : int
        滚球半径

    Returns:
    --------
    background : ndarray
        估计的背景
    """
    if not NUMBA_AVAILABLE:
        print("[TFilter] Numba不可用，回退到scipy实现")
        return rollingBallBackground_fast(img, radius)

    size = 2 * radius + 1

    print(f"[TFilter] 步骤1/2: 最小值滤波 (Numba加速)...")
    eroded = _minimum_filter_separable_numba(img, size)

    print(f"[TFilter] 步骤2/2: 最大值滤波 (Numba加速)...")
    background = _maximum_filter_separable_numba(eroded, size)

    return background


def rollingBallBackground_auto(img, radius):
    """
    自动选择最优实现

    根据图像大小和半径选择：
    - 小半径（<20）：scipy更快
    - 大半径（>=20）且有Numba：Numba更快
    - 无Numba：总是使用scipy

    Parameters:
    -----------
    img : ndarray
        输入图像（float64）
    radius : int
        滚球半径

    Returns:
    --------
    background : ndarray
        估计的背景
    """
    # 小半径直接用scipy（已经足够快）
    if radius < 20:
        print(f"[TFilter] 半径{radius}较小，使用scipy实现")
        return rollingBallBackground_fast(img, radius)

    # 大半径且有Numba，使用Numba
    if NUMBA_AVAILABLE:
        print(f"[TFilter] 半径{radius}较大，使用Numba加速实现")
        return rollingBallBackground_numba(img, radius)

    # 回退到scipy
    print(f"[TFilter] 使用scipy实现（半径={radius}）")
    return rollingBallBackground_fast(img, radius)


# 测试代码
if __name__ == "__main__":
    # 创建测试图像：1024x1024，16位，带椒盐噪声
    print("="*60)
    print("TFilter模块测试")
    print("="*60)

    # 生成测试图像
    img_test = np.random.randint(1000, 2000, (1024, 1024), dtype=np.uint16)

    # 添加椒盐噪声
    noise_ratio = 0.01
    noise_coords = np.random.choice(img_test.size, int(img_test.size * noise_ratio), replace=False)
    noise_coords_2d = np.unravel_index(noise_coords, img_test.shape)
    img_test[noise_coords_2d] = np.random.choice([0, 65535], len(noise_coords))

    print(f"\n原始图像统计：")
    print(f"  形状: {img_test.shape}")
    print(f"  数据类型: {img_test.dtype}")
    print(f"  最小值: {np.min(img_test)}")
    print(f"  最大值: {np.max(img_test)}")
    print(f"  平均值: {np.mean(img_test):.2f}")

    # 测试1: 无滤波
    print("\n测试1: 无滤波")
    params_none = {}
    img_none = applyFilter(img_test, "none", params_none)
    print(f"  处理后平均值: {np.mean(img_none):.2f}")

    # 测试2: 中值滤波
    print("\n测试2: 中值滤波 (size=5)")
    params_median = {'medianSize': 5}
    img_median = applyFilter(img_test, "median", params_median)
    print(f"  处理后平均值: {np.mean(img_median):.2f}")
    print(f"  数据类型: {img_median.dtype}")

    # 测试3: 滚球法
    print("\n测试3: 滚球法 (radius=50, medianSize=5)")
    params_rolling = {'rollingBallRadius': 50, 'medianSize': 5}
    img_rolling = applyFilter(img_test, "rolling_ball", params_rolling)
    print(f"  处理后平均值: {np.mean(img_rolling):.2f}")
    print(f"  数据类型: {img_rolling.dtype}")

    # 测试4: 参数验证
    print("\n测试4: 参数验证")
    valid, msg = validateParams("median", {'medianSize': 5})
    print(f"  有效参数: {valid}")
    valid, msg = validateParams("median", {'medianSize': 15})
    print(f"  无效参数: {valid}, 错误信息: {msg}")

    print("\n"+"="*60)
    print("测试完成")
    print("="*60)
