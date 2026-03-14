from imageio.v3 import imread
import numpy as np
import warnings

# 抑制tifffile的ASCII编码警告（不影响功能）
warnings.filterwarnings('ignore', message='.*coercing invalid ASCII.*')


def readImage(file):
    try:
        pic = imread(file)
    except:
        pic = np.zeros((1024, 1024))
    finally:

        pic = pic.astype(float)
        if np.max(pic) < 256:
            pic = pic * 256
            is8bit = True
        else:
            is8bit = False
        pic = pic.astype(np.uint16)  # 16 位深度的图像

        if len(pic.shape) == 3:
            R, G, B = pic[:, :, 0], pic[:, :, 1], pic[:, :, 2]
            greypic = 0.2989 * R + 0.5870 * G + 0.1140 * B
            return greypic, is8bit
        else:
            return pic, is8bit
