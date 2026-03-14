import numpy as np
import matplotlib.colors as mclr
from matplotlib import cm


jet=cm.get_cmap('jet')

particals_data=np.ones((255,4))
particals_data[0:25,0]=np.linspace(1,0,25)
particals_data[0:25,1]=np.linspace(1,0,25)
particals_data[0:25,2]=np.linspace(1,0.5,25)
particals_data[25:,0]=jet(np.linspace(0,1,230))[:,0]
particals_data[25:,1]=jet(np.linspace(0,1,230))[:,1]
particals_data[25:,2]=jet(np.linspace(0,1,230))[:,2]

particals=mclr.ListedColormap(particals_data)

field_data=np.ones((255,4))
field_data[:,0]=np.append(np.linspace(0,1,127),np.linspace(1,1,128))
field_data[:,1]=np.append(np.linspace(0,1,127),np.linspace(1,0,128))
field_data[:,2]=np.append(np.linspace(1,1,127),np.linspace(1,0,128))

field=mclr.ListedColormap(field_data)