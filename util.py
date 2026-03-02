import math
import numpy as np


def mapval(value, istart, istop, ostart, ostop):
    return ostart + (ostop - ostart) * ((value - istart) * 1.0 / (istop - istart))


def midpt(*args):
    if len(args) == 0:
        return 0.0, 0.0
    arr = np.array(args)
    return float(arr[:, 0].mean()), float(arr[:, 1].mean())


def distsum(*args):
    if len(args) < 2:
        return 0.0
    arr = np.array(args)
    diffs = arr[1:] - arr[:-1]
    dists = np.sqrt((diffs ** 2).sum(axis=1))
    return float(dists.sum())


def distance(p0, p1):
    dx = p0[0] - p1[0]
    dy = p0[1] - p1[1]
    return math.sqrt(dx * dx + dy * dy)


def lerp(p0, p1, t):
    return (p0[0] * (1 - t) + p1[0] * t, p0[1] * (1 - t) + p1[1] * t)


def eqline(p0, p1):
    return float(p1[1] - p0[1]), \
           float(p0[0] - p1[0]), \
           float(p1[0] * p0[1] - p1[1] * p0[0])


def vecang(seg0, seg1):
    u = np.array([seg0[1][0] - seg0[0][0], seg0[1][1] - seg0[0][1]], dtype=np.float64)
    v = np.array([seg1[1][0] - seg1[0][0], seg1[1][1] - seg1[0][1]], dtype=np.float64)
    dot_product = np.dot(u, v)
    norm_u = np.linalg.norm(u)
    norm_v = np.linalg.norm(v)
    if norm_u == 0 or norm_v == 0:
        return math.pi / 2
    angcos = dot_product / (norm_u * norm_v)
    angcos = np.clip(angcos, -1.0, 1.0)
    try:
        return float(math.acos(angcos))
    except:
        return math.pi / 2


def intersect(seg0, seg1):
    a, b, c = eqline(seg0[0], seg0[1])
    d, e, f = eqline(seg1[0], seg1[1])
    det = d * b - a * e
    if det == 0:
        return None
    y = float(f * a - c * d) / det
    if a != 0:
        x = (-b * y - c) / float(a)
    else:
        x = (-e * y - f) / float(d)
    od0 = online((x, y), seg0[0], seg0[1])
    od1 = online((x, y), seg1[0], seg1[1])
    return ((x, y), (od0, od1))


def online(p0, p1, p2):
    od = 0
    ep = 1
    d0 = distance(p1, p2)
    d1 = distance(p0, p1)
    d2 = distance(p0, p2)
    if abs(d0 + d1 - d2) < ep:
        od = d1
    elif abs(d0 + d2 - d1) < ep:
        od = d2
    elif abs(d1 + d2 - d0) < ep:
        od = 0
    return od


def pt2seg(p0, seg):
    p1, p2 = seg
    a, b, c = eqline(p1, p2)
    x0, y0 = p0
    a2b2 = a ** 2 + b ** 2
    if a2b2 == 0:
        return (p1, 0.0, 0.0)
    d = abs(a * x0 + b * y0 + c) / math.sqrt(a2b2)
    x = (b * (b * x0 - a * y0) - a * c) / (a2b2)
    y = (a * (-b * x0 + a * y0) - b * c) / (a2b2)
    return ((x, y), d, online((x, y), p1, p2))
