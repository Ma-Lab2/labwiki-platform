# 输入： data-照片对应的ndarray，以左下角为坐标原点，开口向上的抛物线。
#       X0,Y0,Emin,Emax,dY-打靶位置参数；A,Z-解谱粒子的质量数和电荷数：具体可参考MATTPS程序
#       MCPFileName：MCP效率信息，传入MCP效率数据的txt文档路径，默认效率数据尚未录入
#       TPS：在main中创建一个TPS类的实例即可，默认不输入参数即为MATTPS程序中提供的默认TPS参数，可传入一个txt文档路径
#           txt文档的格式见TSettings.py中TPS类的定义
# 
# 返回值：ndarray，2行n列的数组，第一行为横坐标E，第二行为纵坐标dNdE，可直接绘图


# 全文翻译自 徐诗睿：MATTPS V3.0
# 由MATLAB r2017翻译至Python 3.9
# 因为我也不太懂，所以没有注释，感谢NumPy和MATLAB相近的语法结构：）
# 感谢徐诗睿师兄
# 张予嘉，2022.8.3


import numpy as np
from . import TSettings


def SolveSpectrum(data, X0, Y0, A, Z, Emin, Emax, dY, MCPFileName, TPS, is8bit):
    LB = (TPS.L / 2 + TPS.D) * TPS.L
    TB = Z * TPS.B * LB * 0.00998115
    LE1 = (TPS.L1 * TPS.D1 + TPS.L1 * TPS.L2 + TPS.L1 ** 2 / 2) / TPS.d
    LE2 = (np.log((TPS.L2 + TPS.L3) / TPS.L3) * (TPS.L2 + TPS.L3 + TPS.D1) - TPS.L2) / TPS.theta
    LE = (LE1 + LE2) / 2
    TE = TPS.U * Z * LE / 1000000
    Received_angle = (TPS.S1 / 2) ** 2 * np.pi / TPS.L0 ** 2
    dYmax_theoretical = np.ceil((TPS.S1 / 2) / TPS.L0 * (TPS.L0 + TPS.D + TPS.L) / TPS.Res)

    Received_angle = Received_angle * min(1, (2 * dY) / (2 * dYmax_theoretical))

    if Emin == 0:
        Xmax = data.shape[1]
    else:
        Xmax = np.ceil(X0 + TB / np.sqrt(2 * A * Emin) / TPS.Res)
        Xmax = min(Xmax, data.shape[1])

    Xmin = np.floor(X0 + TB / np.sqrt(2 * A * Emax) / TPS.Res)
    X = np.arange(Xmin, Xmax + 1, dtype=int)
    E = (TB / ((X - X0) * TPS.Res)) ** 2 / (2 * A)

    Ymax = np.ceil(Y0 + TE / (E * TPS.Res) + dY)

    for i in np.nditer(np.arange(Ymax.shape[0])):
        if Ymax[i] > data.shape[0]:
            Ymax[i] = data.shape[0]

    Ymin = np.floor(Y0 + TE / (E * TPS.Res) - dY)

    X_temp = X - 0.5
    X_temp = np.append(X_temp, X_temp[-1] + 1)
    E_temp = (TB / ((X_temp - X0) * TPS.Res)) ** 2 / (2 * A)

    dE = E_temp[0:-1] - E_temp[1:]
    dNdE = np.zeros(E.shape[0])
    dNdE_noise = np.zeros(E.shape[0])

    MCPData = TSettings.LoadMCPData(MCPFileName)
    MCP_Energy = MCPData[..., 0]
    MCP_Efficiency = MCPData[..., 1]

    for i in np.nditer(np.arange(X.shape[0])):
        if A == 1 and Z == 1:
            Noise = np.mean(
                data[int(Ymin[i] - 2 * dYmax_theoretical - 1):int(Ymin[i] - 1 * dYmax_theoretical), X[i] - 1].astype(
                    float))
        else:
            Noise = np.mean(data[Y0 - 2 * dY - 1:Y0 - 1 * dY, X[i] - 1].astype(float))

        Count_net = np.sum(data[int(Ymin[i] - 1):int(Ymax[i]), X[i] - 1].astype(float) - Noise)

        if is8bit == False:
            Count_net = max(Count_net, Noise) / (TPS.EMGain * TPS.QE)
            Noise = Noise / (TPS.EMGain * TPS.QE)
        else:
            Count_net = max(Count_net, Noise / 3) / (TPS.EMGain * TPS.QE)
            Noise = (Noise / 3) / (TPS.EMGain * TPS.QE)

        if E[i] > np.max(MCP_Energy):
            index = MCP_Energy.argmax()
            dNdE[i] = Count_net / (MCP_Efficiency[index] * dE[i] * Received_angle)
            dNdE_noise[i] = Noise / (MCP_Efficiency[index] * dE[i] * Received_angle)
        elif E[i] < np.min(MCP_Energy):
            index = MCP_Energy.argmin()
            dNdE[i] = Count_net / (MCP_Efficiency[index] * dE[i] * Received_angle)
            dNdE_noise[i] = Noise / (MCP_Efficiency[index] * dE[i] * Received_angle)
        else:
            index = np.argsort(abs(MCP_Energy - E[i]))
            n1 = index[0]
            n2 = index[1]
            E1 = MCP_Energy[n1]
            E2 = MCP_Energy[n2]
            MCPEff1 = MCP_Efficiency[n1]
            MCPEff2 = MCP_Efficiency[n2]
            MCPEff = MCPEff1 + (MCPEff2 - MCPEff1) / (E2 - E1) * (E[i] - E1)
            dNdE[i] = Count_net / (MCPEff * dE[i] * Received_angle)
            dNdE_noise[i] = Noise / (MCPEff * dE[i] * Received_angle)

    spectrum = np.array([E, dNdE])
    specnoise = np.array([E, dNdE_noise])
    return spectrum, specnoise
