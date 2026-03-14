import numpy as np


def Parabola(TPS, E, X0, Y0, A, Z, boundary):
    LB = (TPS.L / 2 + TPS.D) * TPS.L
    TB = Z * TPS.B * LB * 0.00998115
    LE1 = (TPS.L1 * TPS.D1 + TPS.L1 * TPS.L2 + TPS.L1 ** 2 / 2) / TPS.d
    LE2 = (np.log((TPS.L2 + TPS.L3) / TPS.L3) * (TPS.L2 + TPS.L3 + TPS.D1) - TPS.L2) / TPS.theta
    LE = (LE1 + LE2) / 2
    TE = TPS.U * Z * LE / 1000000

    X = X0 + TB / np.sqrt(2 * A * E) / TPS.Res

    Y = Y0 + TE / (E * TPS.Res)

    del_index = np.where(X >= boundary - 1)
    line = np.array([np.delete(X, del_index), np.delete(Y, del_index)])

    return line


def ZoomPara(line, area, newBoundary):
    xmax_index = np.where(line[0] >= area[3])
    tempxmax = np.array([np.delete(line[0], xmax_index), np.delete(line[1], xmax_index)])
    xmin_index = np.where(tempxmax[0] <= area[1])
    tempxmin = np.array([np.delete(tempxmax[0], xmin_index), np.delete(tempxmax[1], xmin_index)])
    ymax_index = np.where(tempxmin[1] >= area[2])
    tempymax = np.array([np.delete(tempxmin[0], ymax_index), np.delete(tempxmin[1], ymax_index)])
    ymin_index = np.where(tempymax[1] <= area[0])
    tempymin = np.array([np.delete(tempymax[0], ymin_index), np.delete(tempymax[1], ymin_index)])
    tempymin[0] = tempymin[0] - area[1]
    tempymin[1] = tempymin[1] - area[0]

    del_index = np.where(tempymin[0] >= newBoundary - 1)
    zoomPara = np.array([np.delete(tempymin[0], del_index), np.delete(tempymin[1], del_index)])

    return zoomPara


def CutoffLine(TPS, CutoffEnergy, X0, A, Z):
    if isinstance(CutoffEnergy, str):
        X = None
        return X

    LB = (TPS.L / 2 + TPS.D) * TPS.L
    TB = Z * TPS.B * LB * 0.00998115
    LE1 = (TPS.L1 * TPS.D1 + TPS.L1 * TPS.L2 + TPS.L1 ** 2 / 2) / TPS.d
    LE2 = (np.log((TPS.L2 + TPS.L3) / TPS.L3) * (TPS.L2 + TPS.L3 + TPS.D1) - TPS.L2) / TPS.theta
    LE = (LE1 + LE2) / 2

    X = X0 + TB / np.sqrt(2 * A * CutoffEnergy) / TPS.Res

    return X


def zoomCutoffLine(X, area):
    if X == None:
        return X
    zoomX = X - area[1]
    return zoomX
