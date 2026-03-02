#!/usr/bin/env python3
"""
Usage :
    fontforge -script convert_font.py "PlangothicTest-Regular.ttf" -f woff2
"""

import os
import sys
import argparse
import time
import logging
import fontforge
from typing import Dict, Optional, Tuple, Any, List
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

SUPPORTED_FORMATS = {
    'ttf': 'TrueType 字体 (.ttf)',
    'otf': 'OpenType 字体 (.otf)',
    'woff': 'Web Open Font Format (.woff)',
    'woff2': 'Web Open Font Format 2 (.woff2)',
    'eot': 'Embedded OpenType (.eot)',
    'svg': 'SVG 字体 (.svg)'
}

FORMAT_FLAGS = {
    'otf': ('opentype', 'round', 'dummy-dsig', 'apple'),
    'ttf': ('opentype', 'round', 'dummy-dsig', 'apple', 'short-post', 'old-kern'),
    'woff2': ('opentype', 'round', 'dummy-dsig', 'no-flex', 'short-post', 'omit-instructions'),
}


class FontConverter:
    def __init__(self, input_path: str, output_path: Optional[str] = None, 
                 format_type: str = 'woff2', family_name: Optional[str] = None, 
                 version: Optional[str] = None):

        self.input_path = input_path
        self.format_type = format_type
        self.family_name = family_name
        self.version = version

        if not output_path:
            base_name = Path(input_path).stem
            self.output_path = f"{base_name}.{format_type}"
        else:
            self.output_path = output_path

        self.font = None

    def setup_font_properties(self) -> None:
        if not self.font:
            return
            
        try:
            if self.family_name:
                self.font.familyname = self.family_name
                self.font.fontname = self.family_name.replace(' ', '')
                self.font.fullname = self.family_name

            if self.version:
                self.font.version = self.version

            self._apply_optimization_settings()
                
        except Exception as e:
            logger.warning(f"设置字体属性时出现问题：{str(e)}")
    
    def _apply_optimization_settings(self) -> None:
        try:
            self.font.head_optimized_for_cleartype = True
        except Exception:
            pass

        try:
            self.font.os2_typoascent = self.font.ascent
            self.font.os2_typodescent = -self.font.descent
            self.font.os2_typolinegap = 0
            self.font.hhea_ascent = self.font.ascent
            self.font.hhea_descent = -self.font.descent
            self.font.hhea_linegap = 0
        except Exception:
            pass

        try:
            self.font.gasp = {
                8: ('gridfit', 'antialias', 'symmetric-smoothing'),
                16: ('gridfit', 'antialias', 'symmetric-smoothing'),
                65535: ('gridfit', 'antialias', 'symmetric-smoothing')
            }
        except Exception:
            pass

    def convert(self) -> bool:
        if fontforge is None:
            logger.error("FontForge 模块未加载，无法进行转换")
            return False
        try:
            start_time = time.time()

            if not os.path.exists(self.input_path):
                raise FileNotFoundError(f"未找到字体文件：{self.input_path}")

            logger.info(f"正在加载字体：{self.input_path}")
            self.font = fontforge.open(self.input_path)
            self.setup_font_properties()
            logger.info(f"正在转换字体到 {self.format_type} 格式...")

            flags = FORMAT_FLAGS.get(self.format_type, ())
            self.font.generate(self.output_path, flags=flags)
            self._show_conversion_stats(start_time)
            
            return True
            
        except Exception as e:
            logger.error(f"转换过程中出现问题：{str(e)}")
            return False
        finally:
            if self.font:
                try:
                    self.font.close()
                except Exception:
                    pass
    
    def _show_conversion_stats(self, start_time: float) -> None:
        end_time = time.time()
        if not os.path.exists(self.output_path):
            logger.warning("无法找到输出文件，无法显示统计信息")
            return

        input_size = os.path.getsize(self.input_path) / 1024  # KB
        output_size = os.path.getsize(self.output_path) / 1024  # KB

        logger.info("\n转换完成：")
        logger.info(f"处理时间：{end_time - start_time:.2f} 秒")
        logger.info(f"源文件：{input_size:.2f} KB")
        logger.info(f"转换后：{output_size:.2f} KB")
        logger.info(f"大小变化：{((output_size/input_size)-1)*100:+.1f}%")

        logger.info(f"✓ 字体已保存为 {self.output_path}")


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='字体格式转换工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='\n'.join([
            "支持的格式：",
            *[f"  {fmt:<6} - {desc}" for fmt, desc in SUPPORTED_FORMATS.items()],
            "\n使用示例：",
            f"  fontforge -script {Path(__file__).name} input.ttf -o output.woff2 -f woff2"
        ])
    )

    parser.add_argument('input_font', help='输入字体文件路径')
    parser.add_argument('-o', '--output', help='输出字体文件路径（可选）')
    parser.add_argument(
        '-f', '--format',
        choices=list(SUPPORTED_FORMATS.keys()),
        default='woff2',
        help='输出字体格式（默认：woff2）'
    )
    parser.add_argument('--family-name', help='设置字体族名称')
    parser.add_argument('--version', help='设置字体版本号')

    return parser.parse_args()


def main() -> int:
    args = parse_arguments()
    
    if not args.input_font:
        return 1
        
    converter = FontConverter(
        args.input_font,
        args.output,
        args.format,
        args.family_name,
        args.version
    )
    
    success = converter.convert()

    if sys.stdin.isatty():
        input("\n按回车键退出...")
        
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
