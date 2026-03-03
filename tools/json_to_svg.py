#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import os
from pathlib import Path


def json_to_svg(input_json, output_dir, svg_size=1024, stroke_width=10):
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    print(f"正在读取 {input_json}...")
    with open(input_json, 'r', encoding='utf-8') as f:
        data = json.load(f)

    print(f"找到 {len(data)} 个字符")

    success_count = 0
    error_count = 0

    for idx, strokes in data.items():
        try:
            code_point = int(idx.replace('U+', ''), 16)
            char = chr(code_point)

            if not strokes or len(strokes) == 0:
                continue

            path_elements = []
            for stroke in strokes:
                if not stroke or len(stroke) < 2:
                    continue

                points = ' '.join([
                    f"{x * svg_size:.2f},{y * svg_size:.2f}"
                    for x, y in stroke
                ])

                path_elements.append(
                    f'<polyline points="{points}" '
                    f'fill="none" stroke="black" stroke-width="{stroke_width}" '
                    f'stroke-linecap="round" stroke-linejoin="round"/>'
                )

            if not path_elements:
                continue

            svg_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" 
     width="{svg_size}" height="{svg_size}" 
     viewBox="0 0 {svg_size} {svg_size}">
{chr(10).join(f'  {elem}' for elem in path_elements)}
</svg>'''

            filename = os.path.join(output_dir, f"{code_point}.svg")

            with open(filename, 'w', encoding='utf-8') as f:
                f.write(svg_content)

            success_count += 1

            if success_count % 100 == 0:
                print(f"已处理 {success_count} 个字符...")

        except Exception as e:
            print(f"处理字符 {idx} 时出错: {e}")
            error_count += 1

    print(f"\n转换完成!")
    print(f"成功: {success_count} 个字符")
    print(f"失败: {error_count} 个字符")
    print(f"输出目录: {output_dir}")


def generate_manifest(input_json, output_dir):
    with open(input_json, 'r', encoding='utf-8') as f:
        data = json.load(f)

    manifest_file = os.path.join(output_dir, "manifest.txt")

    with open(manifest_file, 'w', encoding='utf-8') as f:
        f.write("# SVG 文件清单\n")
        f.write("# 格式: 码点, Unicode, SVG 文件名\n")
        f.write("=" * 60 + "\n")

        for idx in sorted(data.keys()):
            code_point = int(idx.replace('U+', ''), 16)
            try:
                char = chr(code_point)
            except:
                char = "?"

            svg_file = f"{code_point}.svg"

            if os.path.exists(os.path.join(output_dir, svg_file)):
                f.write(f"{code_point}, U+{idx.replace('U+', '')}, {char}, {svg_file}\n")

    print(f"已生成清单文件: {manifest_file}")


def main():
    config = {
        'input_json': 'you.json',
        'output_dir': 'svg_output',
        'svg_size': 1024,
        'stroke_width': 50
    }

    if not os.path.exists(config['input_json']):
        print(f"错误: 找不到输入文件 {config['input_json']}")
        print("请先生成 JSON 文件:")
        print(f"  py char2stroke.py build --first 0x3d000 --last 0x3d0ff font.ttf --output {config['input_json']}")
        return

    json_to_svg(
        input_json=config['input_json'],
        output_dir=config['output_dir'],
        svg_size=config['svg_size'],
        stroke_width=config['stroke_width']
    )

    generate_manifest(config['input_json'], config['output_dir'])


if __name__ == "__main__":
    main()
