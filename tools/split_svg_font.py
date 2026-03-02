import os
import re
from lxml import etree

def get_unicode_decimal(unicode_str):
    match = re.search(r'&#x([0-9a-fA-F]+);', unicode_str)
    if match:
        return int(match.group(1), 16)

    if len(unicode_str) > 0:
        try:
            return ord(unicode_str)
        except TypeError:
            pass
    return None

def split_svg_file(input_file, output_dir):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    tree = etree.parse(input_file)
    root = tree.getroot()

    nsmap = root.nsmap
    svg_ns = nsmap.get(None)

    if svg_ns:
        paths = root.xpath('//svg:path', namespaces={'svg': svg_ns})
    else:
        paths = root.xpath('//path')

    print(f"找到 {len(paths)} 个 path 元素")

    xml_declaration = '<?xml version="1.0" encoding="UTF-8"?>\n'

    for path in paths:
        unicode_val = path.get('unicode')

        if not unicode_val:
            continue

        decimal_val = get_unicode_decimal(unicode_val)

        if decimal_val is None:
            print(f"警告: 无法解析 unicode '{unicode_str}'，跳过。")
            continue

        new_svg = etree.Element('{%s}svg' % svg_ns if svg_ns else 'svg', nsmap=nsmap)
        new_svg.set('width', '1024')
        new_svg.set('height', '1024')
        new_svg.set('viewBox', '0 -1024 1024 1024')

        new_path = etree.SubElement(new_svg, '{%s}path' % svg_ns if svg_ns else 'path')
        for attr in path.keys():
            new_path.set(attr, path.get(attr))

        filename = f"{decimal_val}.svg"
        filepath = os.path.join(output_dir, filename)

        xml_content = etree.tostring(new_svg, pretty_print=True, encoding='unicode')

        final_output = xml_declaration + xml_content

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(final_output)

    print("处理完成。")

if __name__ == "__main__":
    input_filename = 'you.svg'
    output_directory = 'svg_output'

    if os.path.exists(input_filename):
        split_svg_file(input_filename, output_directory)
    else:
        print(f"错误: 在当前目录下未找到文件 '{input_filename}'")
