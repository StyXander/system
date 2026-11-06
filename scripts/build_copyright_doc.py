# -*- coding: utf-8 -*-
"""
生成中国版权保护中心（CPCC）标准的计算机软件著作权登记 60 页源代码鉴别材料。
软件名称：审迹智链跨报告证据链追踪与可持续信息智能鉴证系统
版本号：V1.0
规范要求：
1. 连续 60 页（前 30 页 + 后 30 页）
2. 每页严格 50 行，总计 3000 行
3. 页眉左侧：软件全称及版本号；页眉右侧：页码（第 X 页 共 60 页）
4. 第 1 页为系统程序启动/路由入口；第 60 页为系统核心鉴证报告交付出口
"""

import os
import sys
from pathlib import Path
import docx
from docx.shared import Cm, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

def add_header_field(paragraph, text):
    run = paragraph.add_run()
    fldChar1 = OxmlElement('w:fldChar')
    fldChar1.set(qn('w:fldCharType'), 'begin')
    instrText = OxmlElement('w:instrText')
    instrText.set(qn('xml:space'), 'preserve')
    instrText.text = text
    fldChar2 = OxmlElement('w:fldChar')
    fldChar2.set(qn('w:fldCharType'), 'separate')
    fldChar3 = OxmlElement('w:fldChar')
    fldChar3.set(qn('w:fldCharType'), 'end')
    r = run._r
    r.append(fldChar1)
    r.append(instrText)
    r.append(fldChar2)
    r.append(fldChar3)

def read_source_file_lines(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        raw_lines = f.readlines()
    cleaned = []
    prev_blank = False
    for line in raw_lines:
        s = line.rstrip('\r\n').replace('\t', '    ')
        if not s.strip():
            if not prev_blank:
                cleaned.append('')
                prev_blank = True
        else:
            prev_blank = False
            cleaned.append(s)
    return cleaned

def assemble_part1(repo_app_dir):
    """
    前 30 页（第 1 ~ 30 页，共 1500 行）
    模块构成：
    1. connectivity_app.py (应用启动入口、中间件、安全头、路由注入) - 72 行
    2. connectivity_api.py (核心 REST API 控制器、事项分析路由、核验端点) - 805 行
    3. connectivity_matter_pipeline.py (五智能体流水线协同调度器) - 521 行
    4. connectivity_matter_agents.py (智能体角色 Prompt 与多智能体设定) - 102 行
    共计严格 1500 行，以 prompt+=str(payload.get("role_extension", "")) 完满收尾。
    """
    app_lines = read_source_file_lines(os.path.join(repo_app_dir, 'connectivity_app.py'))
    api_lines = read_source_file_lines(os.path.join(repo_app_dir, 'connectivity_api.py'))
    pipe_lines = read_source_file_lines(os.path.join(repo_app_dir, 'connectivity_matter_pipeline.py'))
    agent_lines = read_source_file_lines(os.path.join(repo_app_dir, 'connectivity_matter_agents.py'))

    # 在 agent_lines 中截取到 role_extension 所在行
    role_ext_idx = None
    for idx, line in enumerate(agent_lines):
        if 'role_extension' in line:
            role_ext_idx = idx
            break
    if role_ext_idx is None:
        raise ValueError("Cannot find role_extension in agent_lines")
    agent_slice = agent_lines[:role_ext_idx + 1]

    # 计算需要的 api_lines 数量以达到严格 1500 行
    target_api_count = 1500 - len(app_lines) - len(pipe_lines) - len(agent_slice)
    # 微调 api_lines 的空白行达到 target_api_count
    if len(api_lines) > target_api_count:
        excess = len(api_lines) - target_api_count
        # 从末尾往前移除多余的纯空行
        new_api = []
        trimmed = 0
        for l in api_lines:
            if not l.strip() and trimmed < excess:
                trimmed += 1
                continue
            new_api.append(l)
        api_lines = new_api

    part1_pool = []
    part1_pool.extend(app_lines)
    part1_pool.extend(api_lines)
    part1_pool.extend(pipe_lines)
    part1_pool.extend(agent_slice)

    if len(part1_pool) != 1500:
        raise ValueError(f"Part 1 line count mismatch: {len(part1_pool)} != 1500")

    return part1_pool

def assemble_part2(repo_app_dir):
    """
    后 30 页（第 31 ~ 60 页，共 1500 行）
    模块构成：
    1. 模块导言（3 行清晰界定后 30 页起排）
    2. connectivity_engine.py (从 def _divide_interval 开始，包含区间运算、边界提取、残差计算与公差校验) - 633 行
    3. connectivity_matters.py (重大事项矩阵归集、多源证据裁决与缺失事实研判) - 311 行
    4. connectivity_delivery.py (全量：鉴证意见书生成、SHA-256防篡改存证与Word/PDF报告输出) - 553 行
    共计严格 1500 行，以 final return stream.getvalue() 完满结束。
    """
    engine_lines = read_source_file_lines(os.path.join(repo_app_dir, 'connectivity_engine.py'))
    matters_lines = read_source_file_lines(os.path.join(repo_app_dir, 'connectivity_matters.py'))
    delivery_lines = read_source_file_lines(os.path.join(repo_app_dir, 'connectivity_delivery.py'))

    # 寻找 def _divide_interval 起始索引
    div_idx = None
    for idx, line in enumerate(engine_lines):
        if line.startswith('def _divide_interval('):
            div_idx = idx
            break
    if div_idx is None:
        raise ValueError("Cannot find def _divide_interval in engine_lines")

    engine_slice = engine_lines[div_idx:]

    header_lines = [
        '# ==============================================================================',
        '# 审迹智链 (AuditTrace) - 后30页：核心比对引擎、事项风险研判与交付存证系统',
        '# =============================================================================='
    ]

    part2_pool = []
    part2_pool.extend(header_lines)
    part2_pool.extend(engine_slice)
    part2_pool.extend(matters_lines)
    part2_pool.extend(delivery_lines)

    if len(part2_pool) != 1500:
        raise ValueError(f"Part 2 line count mismatch: {len(part2_pool)} != 1500")

    return part2_pool

def build_docx_and_txt(output_docx_path, output_txt_path, repo_app_dir):
    print("[1/4] 读取并组装源代码...")
    part1 = assemble_part1(repo_app_dir)
    part2 = assemble_part2(repo_app_dir)

    assert len(part1) == 1500, f"Part 1 should be 1500 lines, got {len(part1)}"
    assert len(part2) == 1500, f"Part 2 should be 1500 lines, got {len(part2)}"

    all_lines = part1 + part2
    assert len(all_lines) == 3000, f"Total lines should be 3000, got {len(all_lines)}"
    print(f"      Part 1 (前30页): {len(part1)} 行 (第 1 页 至 第 30 页)")
    print(f"      Part 2 (后30页): {len(part2)} 行 (第 31 页 至 第 60 页)")
    print(f"      总计行数: {len(all_lines)} 行 (严格 60 页，每页 50 行)")

    print("[2/4] 输出纯文本备份文件 (.txt)...")
    os.makedirs(os.path.dirname(os.path.abspath(output_txt_path)), exist_ok=True)
    with open(output_txt_path, 'w', encoding='utf-8') as f:
        for page_idx in range(60):
            page_start = page_idx * 50
            page_end = page_start + 50
            f.write(f"// ==============================================================================\n")
            f.write(f"// 审迹智链跨报告证据链追踪与可持续信息智能鉴证系统 V1.0 - 第 {page_idx + 1} 页 / 共 60 页\n")
            f.write(f"// ==============================================================================\n")
            for line_idx in range(page_start, page_end):
                f.write(f"{all_lines[line_idx]}\n")
            f.write("\n\n")

    print("[3/4] 初始化 Word (.docx) 排版格式...")
    doc = docx.Document()
    section = doc.sections[0]

    # 设置 A4 纸张尺寸
    section.page_width = Cm(21.0)
    section.page_height = Cm(29.7)

    # 规范页边距：左边留出 2.5cm 装订线，其余各 2.0cm
    section.top_margin = Cm(2.0)
    section.bottom_margin = Cm(2.0)
    section.left_margin = Cm(2.5)
    section.right_margin = Cm(2.0)

    # 页眉设置
    header = section.header
    header_p = header.paragraphs[0]
    header_p.alignment = WD_ALIGN_PARAGRAPH.RIGHT

    # 添加页眉文字与动态页码域
    h_title = header_p.add_run('审迹智链跨报告证据链追踪与可持续信息智能鉴证系统 V1.0          ')
    h_title.font.name = '宋体'
    h_title.font.size = Pt(9)
    h_title.font.color.rgb = RGBColor(100, 100, 100)

    h_page_prefix = header_p.add_run('第 ')
    h_page_prefix.font.name = '宋体'
    h_page_prefix.font.size = Pt(9)
    h_page_prefix.font.color.rgb = RGBColor(100, 100, 100)

    add_header_field(header_p, 'PAGE')

    h_mid = header_p.add_run(' 页 共 ')
    h_mid.font.name = '宋体'
    h_mid.font.size = Pt(9)
    h_mid.font.color.rgb = RGBColor(100, 100, 100)

    add_header_field(header_p, 'NUMPAGES')

    h_page_suffix = header_p.add_run(' 页')
    h_page_suffix.font.name = '宋体'
    h_page_suffix.font.size = Pt(9)
    h_page_suffix.font.color.rgb = RGBColor(100, 100, 100)

    print("[4/4] 逐页写入 3000 行源代码并嵌入硬分页符...")
    for page_idx in range(60):
        page_start = page_idx * 50
        page_end = page_start + 50
        for line_idx in range(page_start, page_end):
            code_line = all_lines[line_idx]
            text_to_write = code_line if code_line.strip() else ' '
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(0)
            p.paragraph_format.space_after = Pt(0)
            p.paragraph_format.line_spacing = Pt(13.5)  # 严格 13.5 磅行高，确保一页 50 行完美排满
            
            run = p.add_run(text_to_write)
            run.font.name = 'Consolas'
            run.font.size = Pt(8.5)
            # 设置中文字体
            rPr = run._r.get_or_add_rPr()
            rFonts = OxmlElement('w:rFonts')
            rFonts.set(qn('w:ascii'), 'Consolas')
            rFonts.set(qn('w:hAnsi'), 'Consolas')
            rFonts.set(qn('w:eastAsia'), '宋体')
            rPr.append(rFonts)

        # 每 50 行插入分页符（除最后一页外）
        if page_idx < 59:
            doc.add_page_break()

    os.makedirs(os.path.dirname(os.path.abspath(output_docx_path)), exist_ok=True)
    doc.save(output_docx_path)
    print(f"      [完成] Word 源代码文档已生成: {output_docx_path}")
    print(f"      [完成] 文本格式备份已生成: {output_txt_path}")

if __name__ == '__main__':
    repo_app = r'C:\Users\86135\.gemini\antigravity\brain\ecb8230c-706f-4ddc-82a8-948138719092\scratch\system\backend\app'
    out_docx = r'C:\Users\86135\.gemini\antigravity\brain\ecb8230c-706f-4ddc-82a8-948138719092\scratch\system\docs\copyright\审迹智链AuditTrace_软件著作权源程序60页文档.docx'
    out_txt = r'C:\Users\86135\.gemini\antigravity\brain\ecb8230c-706f-4ddc-82a8-948138719092\scratch\system\docs\copyright\审迹智链AuditTrace_软件著作权源程序60页文档.txt'
    build_docx_and_txt(out_docx, out_txt, repo_app)
