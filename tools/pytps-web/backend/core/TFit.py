# 能谱拟合模块
# 实现类热分布模型的非线性拟合
# 张予嘉，2025.11.22

import numpy as np
from scipy.optimize import curve_fit


def ThermalModel(E, N0, kT):
    """
    类热分布模型函数
    
    dN/dE = N0 / sqrt(2 * E * kT) * exp(-sqrt(2 * E / kT))
    
    输入参数：
        E: numpy数组，能量（MeV）
        N0: float, 归一化系数
        kT: float, 温度参数（MeV）
    
    返回值：
        dNdE: numpy数组，与E形状相同的能谱值
    """
    # 防止除零和sqrt负数
    E = np.asarray(E)
    E_safe = np.where(E > 0, E, 1e-10)  # 将E≤0的点替换为极小值
    
    sqrt_term = np.sqrt(2 * E_safe / kT)
    dNdE = N0 / np.sqrt(2 * E_safe * kT) * np.exp(-sqrt_term)
    
    return dNdE


def FitSpectrum(specData, Efit_min, Efit_max):
    """
    对能谱数据进行温度拟合
    
    输入参数：
        specData: numpy数组，2行n列
                  specData[0] = E (MeV)
                  specData[1] = dN/dE
        Efit_min: float, 拟合能量下限（MeV）
        Efit_max: float, 拟合能量上限（MeV）
    
    返回值：
        fitResult: dict，包含以下键值：
            'success': bool, 拟合是否成功
            'N0': float, 拟合得到的归一化系数
            'kT': float, 拟合得到的温度参数（MeV）
            'sigma_N0': float, N0的标准偏差
            'sigma_kT': float, kT的标准偏差
            'R2': float, 拟合优度（0-1）
            'E_fit': array, 拟合使用的能量点
            'Y_fit': array, 拟合使用的能谱值
            'Y_model': array, 拟合曲线的模型值
            'message': str, 错误或成功信息
    
    如果拟合失败，返回：
        {'success': False, 'message': 错误描述}
    """
    
    # 1. 数据验证
    if specData.shape[0] != 2:
        return {'success': False, 'message': '能谱数据格式错误，需要2行n列的数组'}
    
    if Efit_min >= Efit_max:
        return {'success': False, 'message': '拟合能量下限必须小于上限'}
    
    # 2. 提取拟合范围内的数据点
    mask = (specData[0] >= Efit_min) & (specData[0] <= Efit_max)
    E_fit = specData[0][mask]
    Y_fit = specData[1][mask]
    
    # 3. 数据有效性检查
    if len(E_fit) < 3:
        return {'success': False, 'message': f'拟合范围内数据点不足（仅{len(E_fit)}个点，需要≥3）'}
    
    if np.any(E_fit <= 0):
        return {'success': False, 'message': '拟合范围内存在E≤0的数据点'}
    
    # 4. 过滤非正值（对数坐标拟合需要）
    mask_positive = Y_fit > 0
    if not np.all(mask_positive):
        print(f"[TFit] 警告：过滤掉 {np.sum(~mask_positive)} 个非正值数据点")
        E_fit = E_fit[mask_positive]
        Y_fit = Y_fit[mask_positive]
        
        if len(E_fit) < 3:
            return {'success': False, 'message': '过滤非正值后数据点不足（<3）'}
    
    # 5. 初值估计
    try:
        # N0初值：基于最大值和典型能量估计
        E_median = np.median(E_fit)
        N0_init = np.max(Y_fit) * np.sqrt(2 * E_median * 1.0)
        
        # kT初值：能量加权估计
        # 方法1：简单取中值能量的一半
        kT_init = E_median / 2.0
        
        # 方法2（备选）：从高能段斜率估计
        # 取能量最高的30%数据点，用对数拟合估计kT
        if len(E_fit) > 10:
            high_E_idx = int(len(E_fit) * 0.7)
            E_high = E_fit[high_E_idx:]
            Y_high = Y_fit[high_E_idx:]
            
            # 在高能段，log(Y) ≈ -sqrt(2E/kT) + const
            # 用线性拟合 log(Y) vs sqrt(E) 来估计kT
            try:
                sqrt_E_high = np.sqrt(E_high)
                log_Y_high = np.log(Y_high)
                
                # 线性拟合
                p = np.polyfit(sqrt_E_high, log_Y_high, 1)
                slope = p[0]  # 斜率 ≈ -sqrt(2/kT)
                
                if slope < 0:
                    kT_from_slope = -2.0 / (slope ** 2)
                    # 确保kT_from_slope在合理范围内
                    if 0.1 < kT_from_slope < 100:
                        # 取两种估计的几何平均
                        kT_init = np.sqrt(kT_init * kT_from_slope)
            except:
                pass  # 如果高能段拟合失败，保持原kT_init
        
        # 确保初值在合理范围
        N0_init = max(N0_init, 1e6)
        kT_init = np.clip(kT_init, 0.1, 50.0)
        
        print(f"[TFit] 初值估计: N0={N0_init:.2e}, kT={kT_init:.3f} MeV")
        
    except Exception as e:
        return {'success': False, 'message': f'初值估计失败: {str(e)}'}
    
    # 6. 执行非线性拟合
    try:
        popt, pcov = curve_fit(
            ThermalModel,
            E_fit,
            Y_fit,
            p0=[N0_init, kT_init],
            bounds=([0, 0.01], [np.inf, 100.0]),  # N0>0, 0.01<kT<100 MeV
            maxfev=10000
        )
        
        N0_fit, kT_fit = popt
        
        # 提取参数不确定度
        try:
            sigma_N0, sigma_kT = np.sqrt(np.diag(pcov))
        except:
            sigma_N0, sigma_kT = 0.0, 0.0
        
        # 物理合理性检查
        if kT_fit <= 0:
            return {'success': False, 'message': f'拟合得到的kT={kT_fit:.3f} MeV为非物理值（≤0）'}
        
        if kT_fit > 100:
            return {'success': False, 'message': f'拟合得到的kT={kT_fit:.3f} MeV过大（>100 MeV），可能不合理'}
        
        # 7. 计算拟合优度R²
        Y_model = ThermalModel(E_fit, N0_fit, kT_fit)
        ss_res = np.sum((Y_fit - Y_model) ** 2)
        ss_tot = np.sum((Y_fit - np.mean(Y_fit)) ** 2)
        
        if ss_tot > 0:
            R2 = 1 - ss_res / ss_tot
        else:
            R2 = 0.0
        
        print(f"[TFit] 拟合成功: N0={N0_fit:.2e}, kT={kT_fit:.3f}±{sigma_kT:.3f} MeV, R²={R2:.4f}")
        
        return {
            'success': True,
            'N0': N0_fit,
            'kT': kT_fit,
            'sigma_N0': sigma_N0,
            'sigma_kT': sigma_kT,
            'R2': R2,
            'E_fit': E_fit,
            'Y_fit': Y_fit,
            'Y_model': Y_model,
            'message': '拟合成功'
        }
        
    except RuntimeError as e:
        return {'success': False, 'message': f'拟合未收敛: {str(e)}\n建议调整拟合范围或检查数据质量'}
    
    except Exception as e:
        return {'success': False, 'message': f'拟合失败: {str(e)}'}
