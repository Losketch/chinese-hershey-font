# -*- coding: utf-8 -*-
from PIL import Image, ImageFont, ImageDraw
import math
import random
import json
import time
import sys
import os
import numpy as np
from util import *
import argparse
from concurrent.futures import ProcessPoolExecutor

try:
    rust_lib_path = os.path.join(os.path.dirname(__file__), 'target', 'release')
    if os.path.exists(rust_lib_path):
        sys.path.insert(0, rust_lib_path)
        import char2stroke_rs
        USE_RUST = True
    else:
        USE_RUST = False
except ImportError:
    USE_RUST = False

CH0 = 0x4e00 # unicode <CJK Ideograph, First>
CH1 = 0x9fef # unicode <CJK Ideograph, Last>


def im2mtx(im):
    w, h = im.size
    data = np.array(im.getdata(), dtype=np.float32)
    mtx = (data > 250).astype(np.uint8).reshape((h, w))
    return mtx


def mtx2im(mtx, n=255):
    h, w = mtx.shape
    data = (mtx * n).astype(np.uint8)
    im = Image.fromarray(data, mode='L')
    return im


def rastBox(l, w=100, h=100, f='Heiti.ttc'):
    def getbound_fast(arr):
        mask = arr > 128
        if not np.any(mask):
            return int(w * 0.25), int(h * 0.25), int(w * 0.75), int(h * 0.75)
        rows = np.any(mask, axis=1)
        cols = np.any(mask, axis=0)
        ymin, ymax = np.where(rows)[0][[0, -1]]
        xmin, xmax = np.where(cols)[0][[0, -1]]
        return xmin, ymin, xmax, ymax

    font = ImageFont.truetype(f, h)
    im0 = Image.new('L', (int(w * 1.5), int(h * 1.5)))
    dr0 = ImageDraw.Draw(im0)
    dr0.text((int(w * 0.1), int(h * 0.1)), l, 255, font=font)

    arr = np.array(im0)
    xmin, ymin, xmax, ymax = getbound_fast(arr)
    xmin = min(xmin, int(w * 0.25))
    xmax = max(xmax, int(w * 0.75))
    ymin = min(ymin, int(h * 0.25))
    ymax = max(ymax, int(h * 0.75))

    im = Image.new('L', (w, h))
    im.paste(im0, box=(-xmin, -ymin))
    new_w = int(w ** 2 * 1.0 / (xmax - xmin))
    new_h = int(h ** 2 * 1.0 / (ymax - ymin))
    im = im.resize((new_w, new_h), resample=Image.BILINEAR)
    im = im.crop((0, 0, w, h))
    return im2mtx(im)


def scanRast(mtx, strw=10, ngradient=2):
    global perf
    if USE_RUST:
        mtx_list = mtx.tolist()
        result = char2stroke_rs.scan_rast(mtx_list, float(strw), int(ngradient))
        return [[[float(x), float(y)] for x, y in seg] for seg in result]

    h, w = mtx.shape
    segs = []

    steptypes = [
        (0, 1), (1, 0),
        (1, 1), (-1, 1),
        (1, 2), (2, 1), (-1, 2), (-2, 1),
        (1, 3), (3, 1), (-1, 3), (-3, 1),
        (1, 4), (4, 1), (-1, 4), (-4, 1),
    ][:ngradient * 4]

    t0 = time.time()
    for step in steptypes:
        dx, dy = step

        if dx == 0:
            for y in range(h):
                row = mtx[y, :]
                transitions = np.where(np.diff(row.astype(np.int8)))[0]
                starts = np.concatenate([[0], transitions + 1])
                ends = np.concatenate([transitions + 1, [w]])
                for i in range(len(starts)):
                    if row[starts[i]] == 1:
                        segs.append([(starts[i], y), (ends[i], y)])
        elif dy == 0:
            for x in range(w):
                col = mtx[:, x]
                transitions = np.where(np.diff(col.astype(np.int8)))[0]
                starts = np.concatenate([[0], transitions + 1])
                ends = np.concatenate([transitions + 1, [h]])
                for i in range(len(starts)):
                    if col[starts[i]] == 1:
                        segs.append([(x, starts[i]), (x, ends[i])])
        else:
            if dx > 0 and dy > 0:
                for start_y in range(h):
                    x, y = 0, start_y
                    line_vals = []
                    line_coords = []
                    while x < w and y < h:
                        line_vals.append(mtx[y, x])
                        line_coords.append((x, y))
                        x += dx
                        y += dy
                    if len(line_vals) > 1:
                        arr = np.array(line_vals, dtype=np.int8)
                        transitions = np.where(np.diff(arr))[0]
                        for i in range(0, len(transitions), 2):
                            if i + 1 < len(transitions):
                                start_idx = transitions[i] + 1
                                end_idx = transitions[i + 1] + 1
                                if arr[start_idx] == 1:
                                    segs.append([line_coords[start_idx], line_coords[end_idx]])
                for start_x in range(1, w):
                    x, y = start_x, 0
                    line_vals = []
                    line_coords = []
                    while x < w and y < h:
                        line_vals.append(mtx[y, x])
                        line_coords.append((x, y))
                        x += dx
                        y += dy
                    if len(line_vals) > 1:
                        arr = np.array(line_vals, dtype=np.int8)
                        transitions = np.where(np.diff(arr))[0]
                        for i in range(0, len(transitions), 2):
                            if i + 1 < len(transitions):
                                start_idx = transitions[i] + 1
                                end_idx = transitions[i + 1] + 1
                                if arr[start_idx] == 1:
                                    segs.append([line_coords[start_idx], line_coords[end_idx]])
            elif dx < 0 and dy > 0:
                for start_y in range(h):
                    x, y = w - 1, start_y
                    line_vals = []
                    line_coords = []
                    while x >= 0 and y < h:
                        line_vals.append(mtx[y, x])
                        line_coords.append((x, y))
                        x += dx
                        y += dy
                    if len(line_vals) > 1:
                        arr = np.array(line_vals, dtype=np.int8)
                        transitions = np.where(np.diff(arr))[0]
                        for i in range(0, len(transitions), 2):
                            if i + 1 < len(transitions):
                                start_idx = transitions[i] + 1
                                end_idx = transitions[i + 1] + 1
                                if arr[start_idx] == 1:
                                    segs.append([line_coords[start_idx], line_coords[end_idx]])
                for start_x in range(w - 1):
                    x, y = start_x, 0
                    line_vals = []
                    line_coords = []
                    while x >= 0 and y < h:
                        line_vals.append(mtx[y, x])
                        line_coords.append((x, y))
                        x += dx
                        y += dy
                    if len(line_vals) > 1:
                        arr = np.array(line_vals, dtype=np.int8)
                        transitions = np.where(np.diff(arr))[0]
                        for i in range(0, len(transitions), 2):
                            if i + 1 < len(transitions):
                                start_idx = transitions[i] + 1
                                end_idx = transitions[i + 1] + 1
                                if arr[start_idx] == 1:
                                    segs.append([line_coords[start_idx], line_coords[end_idx]])
            elif dx > 0 and dy < 0:
                for start_y in range(h):
                    x, y = 0, start_y
                    line_vals = []
                    line_coords = []
                    while x < w and y >= 0:
                        line_vals.append(mtx[y, x])
                        line_coords.append((x, y))
                        x += dx
                        y += dy
                    if len(line_vals) > 1:
                        arr = np.array(line_vals, dtype=np.int8)
                        transitions = np.where(np.diff(arr))[0]
                        for i in range(0, len(transitions), 2):
                            if i + 1 < len(transitions):
                                start_idx = transitions[i] + 1
                                end_idx = transitions[i + 1] + 1
                                if arr[start_idx] == 1:
                                    segs.append([line_coords[start_idx], line_coords[end_idx]])
                for start_x in range(1, w):
                    x, y = start_x, h - 1
                    line_vals = []
                    line_coords = []
                    while x < w and y >= 0:
                        line_vals.append(mtx[y, x])
                        line_coords.append((x, y))
                        x += dx
                        y += dy
                    if len(line_vals) > 1:
                        arr = np.array(line_vals, dtype=np.int8)
                        transitions = np.where(np.diff(arr))[0]
                        for i in range(0, len(transitions), 2):
                            if i + 1 < len(transitions):
                                start_idx = transitions[i] + 1
                                end_idx = transitions[i + 1] + 1
                                if arr[start_idx] == 1:
                                    segs.append([line_coords[start_idx], line_coords[end_idx]])
            else:
                for start_y in range(h):
                    x, y = w - 1, start_y
                    line_vals = []
                    line_coords = []
                    while x >= 0 and y >= 0:
                        line_vals.append(mtx[y, x])
                        line_coords.append((x, y))
                        x += dx
                        y += dy
                    if len(line_vals) > 1:
                        arr = np.array(line_vals, dtype=np.int8)
                        transitions = np.where(np.diff(arr))[0]
                        for i in range(0, len(transitions), 2):
                            if i + 1 < len(transitions):
                                start_idx = transitions[i] + 1
                                end_idx = transitions[i + 1] + 1
                                if arr[start_idx] == 1:
                                    segs.append([line_coords[start_idx], line_coords[end_idx]])
                for start_x in range(w - 1):
                    x, y = start_x, h - 1
                    line_vals = []
                    line_coords = []
                    while x >= 0 and y >= 0:
                        line_vals.append(mtx[y, x])
                        line_coords.append((x, y))
                        x += dx
                        y += dy
                    if len(line_vals) > 1:
                        arr = np.array(line_vals, dtype=np.int8)
                        transitions = np.where(np.diff(arr))[0]
                        for i in range(0, len(transitions), 2):
                            if i + 1 < len(transitions):
                                start_idx = transitions[i] + 1
                                end_idx = transitions[i + 1] + 1
                                if arr[start_idx] == 1:
                                    segs.append([line_coords[start_idx], line_coords[end_idx]])
    t1 = time.time()
    perf.record('scanRast:scanlines', t1 - t0)

    def near(seg0, seg1):
        return distance(seg0[0], seg1[0]) < strw \
            and distance(seg0[1], seg1[1]) < strw

    def scal(seg, s):
        return [(seg[0][0] * s, seg[0][1] * s),
                (seg[1][0] * s, seg[1][1] * s)]

    def adds(seg0, seg1):
        return [(seg0[0][0] + seg1[0][0], seg0[0][1] + seg1[0][1]),
                (seg0[1][0] + seg1[1][0], seg0[1][1] + seg1[1][1])]

    segs = [s for s in segs if len(s) >= 2 and distance(s[0], s[1]) > strw * 0.5]

    t0 = time.time()
    if len(segs) > 0:
        segs_array = np.array([[[seg[0][0], seg[0][1]], [seg[1][0], seg[1][1]]] for seg in segs], dtype=np.float32)
        seg_lengths = np.sqrt((segs_array[:, 1, 0] - segs_array[:, 0, 0])**2 + (segs_array[:, 1, 1] - segs_array[:, 0, 1])**2)

        gp_means0 = []
        gp_means1 = []
        gp_counts = []
        gp_maxs = []

        for i in range(len(segs)):
            seg = segs[i]
            x0, y0 = seg[0][0], seg[0][1]
            x1, y1 = seg[1][0], seg[1][1]
            d = seg_lengths[i]
            grouped = False

            for j in range(len(gp_means0)):
                dx0 = abs(x0 - gp_means0[j][0])
                dy0 = abs(y0 - gp_means0[j][1])
                dx1 = abs(x1 - gp_means1[j][0])
                dy1 = abs(y1 - gp_means1[j][1])
                if dx0 < strw and dy0 < strw and dx1 < strw and dy1 < strw:
                    cnt = gp_counts[j]
                    gp_counts[j] = cnt + 1
                    gp_means0[j][0] = (gp_means0[j][0] * cnt + x0) / (cnt + 1)
                    gp_means0[j][1] = (gp_means0[j][1] * cnt + y0) / (cnt + 1)
                    gp_means1[j][0] = (gp_means1[j][0] * cnt + x1) / (cnt + 1)
                    gp_means1[j][1] = (gp_means1[j][1] * cnt + y1) / (cnt + 1)
                    if d > gp_maxs[j][1]:
                        gp_maxs[j] = (seg, d)
                    grouped = True
                    break

            if not grouped:
                gp_means0.append([x0, y0])
                gp_means1.append([x1, y1])
                gp_counts.append(1)
                gp_maxs.append((seg, d))

        ssegs = [gp_maxs[j][0] for j in range(len(gp_counts))]
    else:
        ssegs = []
    t1 = time.time()
    perf.record('scanRast:clustering', t1 - t0)

    # PASS 1
    t0 = time.time()
    to_remove = set()
    for i in range(len(ssegs)):
        if i in to_remove:
            continue
        seg_i = ssegs[i]
        len_i = distance(seg_i[0], seg_i[1])
        for j in range(len(ssegs)):
            if i == j or j in to_remove:
                continue
            seg_j = ssegs[j]
            len_j = distance(seg_j[0], seg_j[1])
            if len_i < len_j:
                (lx0, ly0), d0, b0 = pt2seg(seg_i[0], seg_j)
                (lx1, ly1), d1, b1 = pt2seg(seg_i[1], seg_j)
                m = 1
                if d0 < strw * m and d1 < strw * m and (b0 < strw * m and b1 < strw * m):
                    to_remove.add(i)
                    break
    ssegs = [s for idx, s in enumerate(ssegs) if idx not in to_remove]
    t1 = time.time()
    perf.record('scanRast:PASS1', t1 - t0)

    # PASS 2
    t0 = time.time()
    to_remove = set()
    for i in range(len(ssegs)):
        if i in to_remove:
            continue
        seg_i = ssegs[i]
        for j in range(len(ssegs)):
            if i == j or j in to_remove:
                continue
            seg_j = ssegs[j]
            d0 = distance(seg_i[0], seg_j[0])
            d1 = distance(seg_i[1], seg_j[1])
            m = 1
            if d0 < strw * m and d1 < strw * m:
                to_remove.add(i)
                break
    ssegs = [s for idx, s in enumerate(ssegs) if idx not in to_remove]
    t1 = time.time()
    perf.record('scanRast:PASS2', t1 - t0)

    # PASS 3
    t0 = time.time()
    to_remove = set()
    for i in range(len(ssegs)):
        if i in to_remove:
            continue
        seg_i = ssegs[i]
        for j in range(len(ssegs)):
            if i == j or j in to_remove:
                continue
            seg_j = ssegs[j]
            seg0 = seg_i[-2:] if len(seg_i) >= 2 else seg_i
            seg1 = seg_j[:2] if len(seg_j) >= 2 else seg_j

            ir = intersect(seg0, seg1)
            if ir is not None:
                (x, y), (od0, od1) = ir
            ang = vecang(seg0, seg1)

            d = distance(seg_i[-1], seg_j[0])
            if d < strw or (ir is not None and od0 == od1 == 0) or ang < math.pi / 4:
                (lx0, ly0), d0, b0 = pt2seg(seg_i[-1], seg1)
                (lx1, ly1), d1, b1 = pt2seg(seg_j[0], seg0)
                m = 1
                if d0 < strw * m and d1 < strw * m and (b0 < 1 and b1 < 1):
                    ssegs[j] = seg_i[:-1] \
                        + [lerp(seg_i[-1], seg_j[0], 0.5)] \
                        + seg_j[1:]
                    to_remove.add(i)
                    break

    ssegs = [s for idx, s in enumerate(ssegs) if idx not in to_remove]
    t1 = time.time()
    perf.record('scanRast:PASS3', t1 - t0)

    return ssegs


def visualize(mtx, ssegs):
    im = mtx2im(mtx, n=80).convert('RGB')
    dr = ImageDraw.Draw(im)
    for s in ssegs:
        dr.line(s, fill=(255, 255, 255), width=1)
        dr.ellipse((s[0][0] - 2, s[0][1] - 2, s[0][0] + 2, s[0][1] + 2), outline=(255, 255, 0))
        dr.ellipse((s[-1][0] - 2, s[-1][1] - 2, s[-1][0] + 2, s[-1][1] + 2), outline=(255, 0, 0))
        dr.text((s[0][0], s[0][1]), str(ssegs.index(s)))
    return im


class build_params:
    width = 100
    height = 100
    strw = 10
    ngradient = 2
    output = ''
    first = CH0
    last = CH1
    workers = 1
    scale_x = 1.0
    scale_y = 1.0


def print_progress_bar(current, total, unicode_code='', suffix='Complete', length=50, fill='█'):
    percent = '{0:.1f}'.format(100 * (current / float(total)))
    filled_length = int(length * current // total)
    bar = fill * filled_length + '-' * (length - filled_length)
    if unicode_code:
        prefix = 'Processing U+{0}'.format(unicode_code)
    else:
        prefix = 'Progress'
    sys.stdout.write('\r{0} |{1}| {2}% {3}'.format(prefix, bar, percent, suffix))
    sys.stdout.flush()


class PerformanceAnalyzer:
    def __init__(self):
        self.timings = {}
        self.counts = {}

    def record(self, name, duration):
        if name not in self.timings:
            self.timings[name] = 0
            self.counts[name] = 0
        self.timings[name] += duration
        self.counts[name] += 1

    def report(self):
        print("\n" + "=" * 60)
        print("(Performance Profiling Report)")
        print("=" * 60)
        total_time = sum(self.timings.values())
        sorted_timings = sorted(self.timings.items(), key=lambda x: x[1], reverse=True)
        for name, duration in sorted_timings:
            count = self.counts[name]
            avg_time = duration / count if count > 0 else 0
            percent = (duration / total_time * 100) if total_time > 0 else 0
            print(f"{name:30s} | {duration:8.3f}s | {count:5d}per | {avg_time*1000:7.2f}ms/per | {percent:5.1f}%")
        print("=" * 60)
        print(f"{'Total':30s} | {total_time:8.3f}s")
        print()


perf = PerformanceAnalyzer()


def process_single_char(args):
    code_point, font_file, w, h, strw, ngradient = args
    try:
        t0 = time.time()
        ch = chr(code_point)
        t1 = time.time()
        perf.record('chr()', t1 - t0)

        t0 = time.time()
        mtx = rastBox(ch, w=w, h=h, f=font_file)
        t1 = time.time()
        perf.record('rastBox()', t1 - t0)

        t0 = time.time()
        ssegs = scanRast(mtx, strw=strw, ngradient=ngradient)
        t1 = time.time()
        perf.record('scanRast()', t1 - t0)

        ind = 'U+' + hex(code_point)[2:].upper()
        return ind, ssegs, True, code_point
    except Exception as e:
        ind = 'U+' + hex(code_point)[2:].upper()
        return ind, [], False, code_point


def build(font='fonts/Heiti.ttc'):
    w, h = build_params.width, build_params.height
    strw = build_params.strw
    ngradient = build_params.ngradient
    first = build_params.first
    last = build_params.last
    output_file = build_params.output
    workers = build_params.workers
    scale_x = build_params.scale_x
    scale_y = build_params.scale_y

    total_chars = last - first + 1
    code_points = list(range(first, last + 1))

    result_dict = {}

    start_time = time.time()

    def perc(x):
        return float('%.3f' % x)

    if workers > 1:
        task_args = [(cp, font, w, h, strw, ngradient) for cp in code_points]

        completed = 0
        with ProcessPoolExecutor(max_workers=workers) as executor:
            for result in executor.map(process_single_char, task_args):
                ind, ssegs, success, code_point = result
                if success:
                    normalized = []
                    for seg in ssegs:
                        normalized.append([(perc(x[0] / float(w) * scale_x), perc(x[1] / float(h) * scale_y)) for x in seg])
                    result_dict[ind] = normalized
                completed += 1
                unicode_code = hex(code_point)[2:].upper()
                print_progress_bar(completed, total_chars, unicode_code=unicode_code)
    else:
        if not output_file:
            print('{')
        for idx, code_point in enumerate(code_points):
            t0 = time.time()
            ch = chr(code_point)
            t1 = time.time()
            perf.record('chr()', t1 - t0)

            try:
                t0 = time.time()
                mtx = rastBox(ch, w=w, h=h, f=font)
                t1 = time.time()
                perf.record('rastBox()', t1 - t0)

                t0 = time.time()
                ssegs = scanRast(mtx, strw=strw, ngradient=ngradient)
                t1 = time.time()
                perf.record('scanRast()', t1 - t0)

                ind = 'U+' + hex(code_point)[2:].upper()
                normalized = []
                for seg in ssegs:
                    normalized.append([(perc(x[0] / float(w) * scale_x), perc(x[1] / float(h) * scale_y)) for x in seg])
                if output_file:
                    result_dict[ind] = normalized
                else:
                    entry = '  "' + ind + '":' + json.dumps(normalized)
                    if idx != len(code_points) - 1:
                        entry += ','
                    print(entry)
            except Exception as e:
                pass
            unicode_code = hex(code_point)[2:].upper()
            print_progress_bar(idx + 1, total_chars, unicode_code=unicode_code)

    print()

    elapsed_time = time.time() - start_time
    print('Completed in {0:.2f} seconds'.format(elapsed_time))

    perf.report()

    if output_file:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result_dict, f, ensure_ascii=False)
    elif workers <= 1:
        print('}')

    return json.dumps(result_dict)


class test_params:
    width = 100
    height = 100
    strw = 10
    ngradient = 2
    nsample = 8
    corpus = ''

def test(fonts = ["C:\Windows\Fonts\simsun.ttc"]):
    w, h = test_params.width, test_params.height
    corpus = test_params.corpus if len(test_params.corpus) else open(
        "teststrings.txt",'r', encoding='utf-8').readlines()[-1]
    IM = Image.new('RGB', (w * test_params.nsample, h * len(fonts)))
    DR = ImageDraw.Draw(IM)
    randidx = random.randrange(0, len(corpus) // test_params.nsample + 1)
    for i in range(0, test_params.nsample):
        ch = corpus[(randidx * test_params.nsample + i) % len(corpus)]
        for j in range(0, len(fonts)):
            rbox = rastBox(ch, f=fonts[j], w=w, h=h)
            im = visualize(rbox, scanRast(
                rbox,
                strw=test_params.strw,
                ngradient=test_params.ngradient
            ))
            IM.paste(im, (i * w, j * h))
            if i == 0:
                DR.text((0, j * h), fonts[j], (255, 255, 255))
    IM.show()
    return IM


if __name__ == '__main__':
    if len(sys.argv) == 1:
        test()
        exit()

    parser = argparse.ArgumentParser(description='Convert Chinese font to strokes.')
    parser.add_argument('mode')

    def autoparse(params):
        arglist = [k for k in dir(params) if not k.startswith('_')]
        for k in arglist:
            parser.add_argument('--' + k, dest=k,
                                default=getattr(params, k), action='store', nargs='?', type=str)
        args = parser.parse_args()
        for k in arglist:
            typ = type(getattr(params, k))
            val = getattr(args, k)
            if typ == int and not isinstance(val, int):
                val = int(val, 0)
            elif not isinstance(val, typ):
                val = typ(val)
            setattr(params, k, val)
        return args

    if sys.argv[1] == 'build':
        parser.add_argument('input')
        args = autoparse(build_params)
        build(args.input)

    elif sys.argv[1] == 'test':
        parser.add_argument('fonts', metavar='input', type=str, nargs='+', action='store')
        args = autoparse(test_params)
        test(args.fonts)



