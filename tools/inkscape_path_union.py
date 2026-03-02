import os
from pathlib import Path

svg_dir = Path("svg_output")
output_dir = Path("svg_processed")
output_dir.mkdir(exist_ok=True)

svg_files = sorted(svg_dir.glob("*.svg"))
print(f"找到 {len(svg_files)} 个SVG文件")

actions_file = Path("batch_actions.txt")
with open(actions_file, "w", encoding="utf-8") as f:
    for i, svg_file in enumerate(svg_files, 1):
        output_path = output_dir / f"{svg_file.stem}.svg"

        f.write(f"file-open:{svg_file.absolute()};\n")
        f.write(f"select-all;\n")
        f.write(f"path-union;\n")
        f.write(f"export-filename:{output_path.absolute()};\n")
        f.write(f"export-do;\n")
        f.write(f"file-close;\n")

        if i % 100 == 0:
            print(f"已生成 {i}/{len(svg_files)} 个处理命令")

print(f"Actions文件已生成: {actions_file}")
print("开始批处理...")

import subprocess
result = subprocess.run(
    ["inkscape", "--shell", "--actions-file", str(actions_file)],
    capture_output=True,
    text=True
)

print("处理完成！")
print(result.stdout if result.stdout else "")
if result.stderr:
    print("错误信息:", result.stderr)

# actions_file.unlink()
