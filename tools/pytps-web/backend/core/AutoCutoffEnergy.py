#输入：能谱曲线
#输出：截止能量(MeV)
#算法：将能谱曲线取log10，再用SavGol算法（窗口53，阶数3）将曲线平滑，再求其一阶数值导数。
#   寻找其导数的所有极小值，从高能端开始寻找，找到一阶导数的第一个较大的低谷，即能谱曲线开始显著上升处。
#   此处即可视为截止能量处。对于不同的能谱，判断“较大低谷”的标准不同，越“干净”的能谱曲线，标准越宽松。

#本算法较为简陋，但应该够用。对于大多数的能谱曲线，可以给出偏差可以接受的截止能量。
#对于粒子数密度相对很低的，图像不清晰的谱线，截止能量一般会偏差较大。
#进一步的改进，暂时做不到了，摆了摆了：）
#（凑合用呗，要啥自行车啊

#张予嘉，2022.8.28

#v1.1更新：
#增加了对于8位图的优化处理，8位图的毛刺更少，相应的信息本身也更弱，用更密的区间来处理8位图，（应该）会让结果更好（吧）


import numpy as np


def CutoffEnergy(line,noise,Emin,Emax,window):
    for i in np.nditer(np.arange(line[0].shape[0])):
        E0=line[0][i]
        isCutoffList=[]
        if E0+window/2>=Emax:
            highEIndex=np.min(np.where(line[0]<=Emax))
            lowEIndex=np.max(np.where(line[0]>=Emax-window))
        elif E0-window/2<=Emin:
            lowEIndex=np.max(np.where(line[0]>=Emin))
            highEIndex=np.min(np.where(line[0]<=Emin+window))
        else:
            lowEIndex=np.max(np.where(line[0]>=E0-window/2))
            highEIndex=np.min(np.where(line[0]<=E0+window/2))
        for j in np.nditer(np.arange(highEIndex,lowEIndex+1)):
            if line[1][j]-noise[1][j]<=0:
                isCutoffList.append(False)
            else:
                isCutoffList.append(True)
        if np.all(isCutoffList):
            cutoffEnergy=line[0][highEIndex]
            break
    if not('cutoffEnergy' in locals()):
        cutoffEnergy="寻找截止能量失败"
    else:
        cutoffEnergy=np.round(cutoffEnergy,2)#保留两位小数（反正再多的位数也都没意义）

    
    return cutoffEnergy
