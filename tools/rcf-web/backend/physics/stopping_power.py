"""
Stopping power functions for various materials

These functions return energy loss per micron (MeV/μm) for protons
at different energy ranges. Functions are segmented by energy range
with different fitting formulas for accuracy.

Author: Tan Song
"""

import math as mt
from config import DENSITY_AL, DENSITY_CU, DENSITY_CR


# ============================================================================
# Aluminum (Al) Stopping Power Functions
# ============================================================================

def s_AL1(x):
    """Aluminum stopping power for E > 1 MeV"""
    a = 91.74
    b = 0.2347
    c = 31.92
    d = -0.02571
    e = 199.9
    f = 1.106
    SP_Al_1 = (a * mt.exp(-b * x) + c * mt.exp(d * x) + e * mt.exp(-f * x)) * DENSITY_AL * 1e-4
    return SP_Al_1


def s_AL2(x):
    """Aluminum stopping power for 0.1 < E <= 1 MeV"""
    a1 = 39.41
    b1 = -0.0124
    c1 = 0.1257
    a2 = 1.412e+04
    b2 = -2.595
    c2 = 1.289
    a3 = 0
    b3 = 0.3347
    c3 = 0.002344
    a4 = 918.5
    b4 = -5.89
    c4 = 5.269

    SP_Al_2 = (a1 * mt.exp(-((x - b1) / c1) ** 2) + a2 * mt.exp(-((x - b2) / c2) ** 2) +
               a3 * mt.exp(-((x - b3) / c3) ** 2) + a4 * mt.exp(-((x - b4) / c4) ** 2)) * DENSITY_AL * 1e-4
    return SP_Al_2


def s_AL3(x):
    """Aluminum stopping power for E <= 0.1 MeV"""
    a1 = 134.7
    b1 = 0.04364
    c1 = 0.01518
    a2 = 295.5
    b2 = 0.05888
    c2 = 0.0261
    a3 = 272
    b3 = 0.02691
    c3 = 0.01482
    a4 = 423
    b4 = 0.102
    c4 = 0.03953
    a5 = 168
    b5 = 0.01383
    c5 = 0.0104
    a6 = 95.19
    b6 = 0.005557
    c6 = 0.00687
    SP_Al_3 = (a1 * mt.exp(-((x - b1) / c1) ** 2) + a2 * mt.exp(-((x - b2) / c2) ** 2) +
               a3 * mt.exp(-((x - b3) / c3) ** 2) + a4 * mt.exp(-((x - b4) / c4) ** 2) +
               a5 * mt.exp(-((x - b5) / c5) ** 2) + a6 * mt.exp(-((x - b6) / c6) ** 2)) * DENSITY_AL * 1e-4
    return SP_Al_3


def s_Alpk_1(x):
    """Aluminum Bragg peak stopping power for 1-50 MeV"""
    p1 = -2.981e-11
    p2 = 5.408e-09
    p3 = -3.63e-07
    p4 = 9.633e-06
    p5 = 3.257e-05
    p6 = -0.007735
    p7 = 0.1808
    p8 = -1.982
    p9 = 13.49
    SP_Alpk_1 = (p1 * x ** 8 + p2 * x ** 7 + p3 * x ** 6 + p4 * x ** 5 +
                 p5 * x ** 4 + p6 * x ** 3 + p7 * x ** 2 + p8 * x + p9) * 1e-2
    return SP_Alpk_1


# ============================================================================
# Copper (Cu) Stopping Power Functions
# ============================================================================

def s_Cu_1(x):
    """Copper stopping power for E <= 0.1 MeV"""
    a = -370415.196010732732248
    b = -269.597085178781413
    c = 2070638.962329559260979
    d = -0.193568272183496
    e = -1450742.809091369388625
    f = -44.718016719241263
    SP_Cu_1 = (a * mt.exp(b * x) + c * mt.exp(-d * x) + e * mt.exp(f * x)) * 1e-8 * DENSITY_CU
    return SP_Cu_1


def s_Cu_2(x):
    """Copper stopping power for 0.1 < E <= 1 MeV"""
    a1 = 460567.536087448475882
    b1 = 0.030515796157933
    c1 = 0.227300554854422
    a2 = 864204.572108658147044
    b2 = 0.148805209364264
    c2 = 0.437956703445314
    a3 = 0.000000000000000
    b3 = 3.256803103575694
    c3 = 0.004746910322783
    a4 = 4271835849.657982826232910
    b4 = 9.737972389288361
    c4 = 2.793524455289794
    a5 = 1141967.295154073974118
    b5 = 0.610417152546741
    c5 = 0.845830345941075

    term1 = a1 * mt.exp(-((x - b1) / c1) ** 2)
    term2 = a2 * mt.exp(-((x - b2) / c2) ** 2)
    term3 = a3 * mt.exp(-((x - b3) / c3) ** 2)
    term4 = a4 * mt.exp(-((x - b4) / c4) ** 2)
    term5 = a5 * mt.exp(-((x - b5) / c5) ** 2)

    SP_Cu_2 = (term1 + term2 + term3 + term4 + term5) * 1e-8 * DENSITY_CU
    return SP_Cu_2


def s_Cu_3(x):
    """Copper stopping power for 1 < E <= 50 MeV"""
    a1 = 930004032.579748034477234
    b1 = -14.304748831716582
    c1 = 5.651619867098793
    a2 = 123892.886345805847668
    b2 = 2.160735319714213
    c2 = 2.981483015215053
    a3 = 440191.624546557897702
    b3 = -6.687027329079715
    c3 = 15.865802179329915
    a4 = -13869.699194475662807
    b4 = 11.724992918021689
    c4 = 3.591855279438446
    a5 = 56168.044842054419860
    b5 = 38.691031849910360
    c5 = 56.037072549642659
    a6 = 1439.602233120179108
    b6 = 26.297686637472903
    c6 = 5.208689576440276
    a7 = 48862.753499984995869
    b7 = -143.745339170657530
    c7 = 220.298016100771662
    a8 = 63974.197195003049274
    b8 = 12.052057194090224
    c8 = 23.277705568797483

    term1 = a1 * mt.exp(-((x - b1) / c1) ** 2)
    term2 = a2 * mt.exp(-((x - b2) / c2) ** 2)
    term3 = a3 * mt.exp(-((x - b3) / c3) ** 2)
    term4 = a4 * mt.exp(-((x - b4) / c4) ** 2)
    term5 = a5 * mt.exp(-((x - b5) / c5) ** 2)
    term6 = a6 * mt.exp(-((x - b6) / c6) ** 2)
    term7 = a7 * mt.exp(-((x - b7) / c7) ** 2)
    term8 = a8 * mt.exp(-((x - b8) / c8) ** 2)

    SP_Cu_3 = (term1 + term2 + term3 + term4 + term5 + term6 + term7 + term8) * 1e-8 * DENSITY_CU
    return SP_Cu_3


def s_Cu_4(x):
    """Copper stopping power for E > 50 MeV"""
    a1 = 245035.365437585802283
    b1 = -75.233680306523894
    c1 = 88.156963413719112
    a2 = 3227.459654680594667
    b2 = 98.929669421272763
    c2 = 48.472844450093035
    a3 = -7604.198617682505756
    b3 = 242.744786250318896
    c3 = 266.064673331901815
    a4 = 4817.080484510907809
    b4 = 694.484607024491538
    c4 = 600.111105587235443
    a5 = 530397047700942208.000000000000000
    b5 = -26034.932426252136793
    c5 = 4763.021423543584206

    term1 = a1 * mt.exp(-((x - b1) / c1) ** 2)
    term2 = a2 * mt.exp(-((x - b2) / c2) ** 2)
    term3 = a3 * mt.exp(-((x - b3) / c3) ** 2)
    term4 = a4 * mt.exp(-((x - b4) / c4) ** 2)
    term5 = a5 * mt.exp(-((x - b5) / c5) ** 2)

    SP_Cu_4 = (term1 + term2 + term3 + term4 + term5) * 1e-8 * DENSITY_CU
    return SP_Cu_4


def s_Cu(x):
    """Combined copper stopping power function"""
    if x < 0:
        return -1
    if x <= 0.1:
        return s_Cu_1(x)
    elif x <= 1:
        return s_Cu_2(x)
    elif x <= 50:
        return s_Cu_3(x)
    else:
        return s_Cu_4(x)


# ============================================================================
# Chromium (Cr) Stopping Power Functions
# ============================================================================

def s_Cr_1(x):
    """Chromium stopping power for E <= 0.15 MeV"""
    a1 = 33908966.472232572734356
    b1 = 0.182340838128152
    c1 = 0.472000310202790
    a2 = -107423598.944632351398468
    b2 = -3.471810354703690
    c2 = 3.045523959625969
    a3 = 24708.055596975209482
    b3 = 0.084913474821710
    c3 = 0.007994589623216
    a4 = 1577115.909105263417587
    b4 = 0.107238159557529
    c4 = 0.039764908147027
    a5 = 472390.150985726155341
    b5 = 0.055677102641883
    c5 = 0.039339283629137
    x = float(x)

    if x <= 1e-3:
        SP_Cr_1 = x
    else:
        SP_Cr_1 = (a1 * mt.exp(-((x - b1) / c1) ** 2) + a2 * mt.exp(-((x - b2) / c2) ** 2) +
                   a3 * mt.exp(-((x - b3) / c3) ** 2) + a4 * mt.exp(-((x - b4) / c4) ** 2) +
                   a5 * mt.exp(-((x - b5) / c5) ** 2)) * 1e-8 * DENSITY_CR
    return SP_Cr_1


def s_Cr_2(x):
    """Chromium stopping power for 0.15 < E <= 1 MeV"""
    a1 = 564993.449578065890819
    b1 = 0.150411548700745
    c1 = 0.068337419780915
    a2 = 945416.603915845509619
    b2 = 0.126655633668358
    c2 = 0.176429364701422
    a3 = 147592731042477.031250000000000
    b3 = -15.513651657184754
    c3 = 3.794441948189948
    a4 = 0.000000000000000
    b4 = 0.472650293876315
    c4 = 0.001969102162711
    a5 = 1637879.419605107512325
    b5 = 1.212412582185841
    c5 = 1.226491815063007
    SP_Cr_2 = (a1 * mt.exp(-((x - b1) / c1) ** 2) + a2 * mt.exp(-((x - b2) / c2) ** 2) +
               a3 * mt.exp(-((x - b3) / c3) ** 2) + a4 * mt.exp(-((x - b4) / c4) ** 2) +
               a5 * mt.exp(-((x - b5) / c5) ** 2)) * 1e-8 * DENSITY_CR
    return SP_Cr_2


def s_Cr_3(x):
    """Chromium stopping power for 1 < E <= 15 MeV"""
    a = 79006.542884689362836
    b = -1.005357140347132
    c = 0.636071097797615
    d = 6282763.992295897565782
    SP_Cr_3 = (d + (a - d) / (1 + (x / c) ** b)) * 1e-8 * DENSITY_CR
    return SP_Cr_3


def s_Cr_4(x):
    """Chromium stopping power for E > 15 MeV"""
    a1 = 4342250436.385002136230469
    b1 = -53.269387361866031
    c1 = 19.936681640254871
    a2 = 217543240.254118502140045
    b2 = -232.003917555180834
    c2 = 91.844966504934021
    a3 = -31081.365320871096628
    b3 = 94.353998516359113
    c3 = 146.610064954483022
    a4 = -1265.045689596615375
    b4 = 100.471819594384371
    c4 = 10.165499978240579
    a5 = 23135830441291488.000000000000000
    b5 = -10402.460398609386175
    c5 = 2053.799906931835267
    SP_Cr_4 = (a1 * mt.exp(-((x - b1) / c1) ** 2) + a2 * mt.exp(-((x - b2) / c2) ** 2) +
               a3 * mt.exp(-((x - b3) / c3) ** 2) + a4 * mt.exp(-((x - b4) / c4) ** 2) +
               a5 * mt.exp(-((x - b5) / c5) ** 2)) * 1e-8 * DENSITY_CR
    return SP_Cr_4


def s_Cr(x):
    """Combined chromium stopping power function"""
    if x <= 0:
        return -1
    if x <= 0.15:
        return s_Cr_1(x)
    elif x <= 1:
        return s_Cr_2(x)
    elif x <= 15:
        return s_Cr_3(x)
    else:
        return s_Cr_4(x)


# ============================================================================
# HD (Radiochromic Film) Stopping Power Functions
# ============================================================================

def s_HD1_1(x):
    """HD active layer 1 stopping power for 0.15 < E <= 1 MeV"""
    a1 = 0.9276
    b1 = 0.1553
    c1 = 0.08081
    a2 = 8.29
    b2 = -0.1937
    c2 = 0.4069
    a3 = 1.456e+07
    b3 = -38.9
    c3 = 10.19
    SP_HD1_1 = (a1 * mt.exp(-((x - b1) / c1) ** 2) + a2 * mt.exp(-((x - b2) / c2) ** 2) +
                a3 * mt.exp(-((x - b3) / c3) ** 2)) * 1e-2
    return SP_HD1_1


def s_HD1_2(x):
    """HD active layer 1 stopping power for E <= 0.15 MeV (Fourier series)"""
    a0 = 4.521
    a1 = -3.656
    b1 = 4.882
    a2 = -0.2719
    b2 = -0.5595
    w = 15.84
    SP_HD1_2 = (a0 + a1 * mt.cos(x * w) + b1 * mt.sin(x * w) +
                a2 * mt.cos(2 * x * w) + b2 * mt.sin(2 * x * w)) * 1e-2
    return SP_HD1_2


def s_HD1_3(x):
    """HD active layer 1 stopping power for 1 < E < 10 MeV"""
    a = 4.307
    b = -0.8915
    c = -312.3
    d = 18.3
    e = 1.65
    f = 0.1079
    SP_HD1_3 = (a * mt.exp(b * x) + c * mt.exp(-d * x) + e * mt.exp(-f * x)) * 1e-2
    return SP_HD1_3


def s_HD1_4(x):
    """HD active layer 1 stopping power for E >= 10 MeV"""
    a = 1.053
    b = -0.1366
    c = 0.3612
    d = -0.01698
    SP_HD1_4 = (a * mt.exp(b * x) + c * mt.exp(d * x)) * 1e-2
    return SP_HD1_4


def s_HD1pk_1(x):
    """HD Bragg peak stopping power"""
    a1 = 2.712
    b1 = 0.2314
    c1 = 2.507
    a2 = 1.174e+13
    b2 = -317.2
    c2 = 59.48
    a3 = 0.5194
    b3 = 2.573
    c3 = 6.991
    a4 = 660.5
    b4 = -555.2
    c4 = 238.6
    SP_HD1pk_1 = (a1 * mt.exp(-((x - b1) / c1) ** 2) + a2 * mt.exp(-((x - b2) / c2) ** 2) +
                  a3 * mt.exp(-((x - b3) / c3) ** 2) + a4 * mt.exp(-((x - b4) / c4) ** 2)) * 1e-2
    return SP_HD1pk_1


def s_HD2_1(x):
    """HD backing layer 2 stopping power for E <= 0.125 MeV"""
    p1 = 3.075e+07
    p2 = -1.166e+07
    p3 = 1.643e+06
    p4 = -1.102e+05
    p5 = 3675
    p6 = 43.19
    p7 = 0.2474
    if x <= 1e-3:
        SP_HD2_1 = x
    else:
        SP_HD2_1 = (p1 * x ** 6 + p2 * x ** 5 + p3 * x ** 4 + p4 * x ** 3 +
                    p5 * x ** 2 + p6 * x + p7) * 1e-2
    return SP_HD2_1


def s_HD2_2(x):
    """HD backing layer 2 stopping power for 0.125 < E <= 10 MeV"""
    a1 = 1.788
    b1 = 0.1336
    c1 = 0.09899
    a2 = 2.095
    b2 = 0.1155
    c2 = 0.2736
    a3 = 7.422
    b3 = -0.9959
    c3 = 1.21
    a4 = 2.866
    b4 = -1.512
    c4 = 3.32
    a5 = 0
    b5 = 1.879
    c5 = 0.01521
    a6 = 1.159
    b6 = -1.067
    c6 = 12.96

    SP_HD2_2 = (a1 * mt.exp(-((x - b1) / c1) ** 2) + a2 * mt.exp(-((x - b2) / c2) ** 2) +
                a3 * mt.exp(-((x - b3) / c3) ** 2) + a4 * mt.exp(-((x - b4) / c4) ** 2) +
                a5 * mt.exp(-((x - b5) / c5) ** 2) + a6 * mt.exp(-((x - b6) / c6) ** 2)) * 1e-2
    return SP_HD2_2


def s_HD2_3(x):
    """HD backing layer 2 stopping power for E > 10 MeV"""
    a = 1.015
    b = -0.1269
    c = 0.3449
    d = -0.01573
    SP_HD2_3 = (a * mt.exp(b * x) + c * mt.exp(d * x)) * 1e-2
    return SP_HD2_3


def s_HD2pk_1(x):
    """HD layer 2 Bragg peak stopping power for 1-50 MeV"""
    a = 8.008
    b = -0.2393
    c = 3.51
    d = -0.0238
    SP_HD2pk_1 = (a * mt.exp(b * x) + c * mt.exp(d * x)) * 1e-2
    return SP_HD2pk_1


# ============================================================================
# EBT (Radiochromic Film) Stopping Power Functions
# ============================================================================

def s_EBT1_1(x):
    """EBT protective layer 1 stopping power for E > 0.125 MeV (rational function)"""
    p1 = 0.05045
    p2 = 5.885
    p3 = 0.7713
    p4 = -0.01928
    q1 = 1.208
    q2 = -0.1501
    q3 = 0.01425
    SP_EBT1_1 = ((p1 * x ** 3 + p2 * x ** 2 + p3 * x + p4) /
                 (x ** 3 + q1 * x ** 2 + q2 * x + q3)) * 1e-2
    return SP_EBT1_1


def s_EBT1_2(x):
    """EBT protective layer 1 stopping power for E <= 0.125 MeV"""
    a1 = 0
    b1 = 19.88
    c1 = 3.174
    a2 = 0
    b2 = 6.395
    c2 = 0.01818
    a3 = 10.13
    b3 = 0.1425
    c3 = 0.07332
    a4 = 3.241
    b4 = 0.06817
    c4 = 0.05023
    if x <= 1e-3:
        SP_EBT1_2 = x
    else:
        SP_EBT1_2 = (a1 * mt.exp(-((x - b1) / c1) ** 2) + a2 * mt.exp(-((x - b2) / c2) ** 2) +
                     a3 * mt.exp(-((x - b3) / c3) ** 2) + a4 * mt.exp(-((x - b4) / c4) ** 2)) * 1e-2
    return SP_EBT1_2


def s_EBT2_1(x):
    """EBT active layer 2 stopping power for E >= 0.15 MeV (rational function)"""
    p1 = 0.05314
    p2 = 5.809
    p3 = 0.4177
    p4 = 0.08663
    q1 = 1.087
    q2 = -0.1358
    q3 = 0.01976
    SP_EBT2_1 = ((p1 * x ** 3 + p2 * x ** 2 + p3 * x + p4) /
                 (x ** 3 + q1 * x ** 2 + q2 * x + q3)) * 1e-2
    return SP_EBT2_1


def s_EBT2_2(x):
    """EBT active layer 2 stopping power for E < 0.15 MeV"""
    a1 = 0
    b1 = 1.859
    c1 = 0.01431
    a2 = -80.95
    b2 = 2.185
    c2 = 1.412
    a3 = 21.75
    b3 = 0.1513
    c3 = 0.1459
    a4 = -0.4435
    b4 = 0.07167
    c4 = 0.03081
    SP_EBT2_2 = (a1 * mt.exp(-((x - b1) / c1) ** 2) + a2 * mt.exp(-((x - b2) / c2) ** 2) +
                 a3 * mt.exp(-((x - b3) / c3) ** 2) + a4 * mt.exp(-((x - b4) / c4) ** 2)) * 1e-2
    return SP_EBT2_2
