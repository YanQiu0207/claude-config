#!/usr/bin/env python3
"""
Skill Rename Script - Rename a skill and update all dependencies
"""

import os
import sys
import re
import shutil
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple
import yaml

SKILLS_DIR = r"C:\Users\YanQi\.claude\skills"

class SkillRenamer:
    def __init__(self, old_name: str, new_name: str, rename_directory: bool = True):
        self.old_name = old_name
        self.new_name = new_name
        self.rename_directory = rename_directory
        self.skills_dir = Path(SKILLS_DIR)
        self.changes = []
        self.backups = []
        self.errors = []

    def validate_inputs(self) -> bool:
        """验证输入参数的有效性"""
        print(f"[验证] 检查输入参数...")

        # 检查老名称和新名称是否相同
        if self.old_name == self.new_name:
            self.errors.append("错误：老名称和新名称相同")
            return False

        # 检查老 skill 目录是否存在
        old_dir = self.skills_dir / self.old_name
        if not old_dir.exists():
            self.errors.append(f"错误：找不到 skill 目录 {old_dir}")
            return False

        # 检查老 SKILL.md 文件
        old_skill_file = old_dir / "SKILL.md"
        if not old_skill_file.exists():
            self.errors.append(f"错误：找不到 {old_skill_file}")
            return False

        # 验证 SKILL.md 中的 name 字段
        try:
            with open(old_skill_file, 'r', encoding='utf-8') as f:
                content = f.read()
                match = re.search(r'^name:\s*(\S+)', content, re.MULTILINE)
                if match:
                    actual_name = match.group(1)
                    if actual_name != self.old_name:
                        print(f"[警告] SKILL.md 中的 name 字段是 '{actual_name}'，而不是 '{self.old_name}'")
                        print(f"[信息] 将使用 SKILL.md 中的实际名称进行改名")
                        self.old_name = actual_name
        except Exception as e:
            self.errors.append(f"错误：读取 {old_skill_file} 失败: {e}")
            return False

        # 检查新 skill 名称是否已存在
        new_dir = self.skills_dir / self.new_name
        if new_dir.exists():
            self.errors.append(f"错误：新 skill 名称 '{self.new_name}' 已存在")
            return False

        print(f"✓ 验证通过")
        return True

    def find_references(self) -> Dict[Path, List[Tuple[int, str, str]]]:
        """
        在所有 SKILL.md 文件中查找对老 skill 的引用
        返回 {文件路径: [(行号, 原文本, 替换后文本)]}
        """
        print(f"\n[搜索] 查找对 '{self.old_name}' 的引用...")
        references = {}

        # 定义多种引用模式
        patterns = [
            (r'`' + re.escape(self.old_name) + r'`', f'`{self.new_name}`', '反引号形式'),
            (r'requires:\s*\[\s*' + re.escape(self.old_name) + r'\s*\]', f'requires: [{self.new_name}]', 'YAML requires 字段'),
            (r'depends_on:\s*\[\s*' + re.escape(self.old_name) + r'\s*\]', f'depends_on: [{self.new_name}]', 'YAML depends_on 字段'),
            (r'#\s*depends?\s+on\s+' + re.escape(self.old_name), f'# depends on {self.new_name}', '注释形式'),
            (r'#\s*需要调用\s+' + re.escape(self.old_name), f'# 需要调用 {self.new_name}', '中文注释形式'),
            (r'\[' + re.escape(self.old_name) + r'\]\(\.\./' + re.escape(self.old_name) + r'/', f'[{self.new_name}](../{self.new_name}/', '链接形式'),
            (r'\.\./' + re.escape(self.old_name) + r'/', f'../{self.new_name}/', '路径引用形式'),
        ]

        # 遍历所有 skill 目录
        for skill_dir in self.skills_dir.iterdir():
            if not skill_dir.is_dir() or skill_dir.name == self.old_name:
                continue

            skill_file = skill_dir / "SKILL.md"
            if not skill_file.exists():
                continue

            try:
                with open(skill_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()

                file_references = []
                for line_no, line in enumerate(lines, 1):
                    for pattern, replacement, pattern_name in patterns:
                        if re.search(pattern, line):
                            new_line = re.sub(pattern, replacement, line)
                            if new_line != line:
                                file_references.append((line_no, line.rstrip(), new_line.rstrip()))
                                print(f"  ✓ {skill_file.name} 第 {line_no} 行: {pattern_name}")

                if file_references:
                    references[skill_file] = file_references

            except Exception as e:
                self.errors.append(f"错误：读取 {skill_file} 失败: {e}")

        if not references:
            print(f"  (未找到引用)")

        return references

    def backup_files(self, files_to_backup: List[Path]) -> bool:
        """为所有将要修改的文件创建备份"""
        print(f"\n[备份] 为 {len(files_to_backup) + 1} 个文件创建备份...")

        try:
            # 备份目标 skill 的 SKILL.md
            old_skill_file = self.skills_dir / self.old_name / "SKILL.md"
            backup_file = Path(str(old_skill_file) + ".backup")
            shutil.copy2(old_skill_file, backup_file)
            self.backups.append((old_skill_file, backup_file))
            print(f"  ✓ {old_skill_file.name} -> {backup_file.name}")

            # 备份所有依赖文件
            for file_path in files_to_backup:
                backup_file = Path(str(file_path) + ".backup")
                shutil.copy2(file_path, backup_file)
                self.backups.append((file_path, backup_file))
                print(f"  ✓ {file_path.name} -> {backup_file.name}")

            return True
        except Exception as e:
            self.errors.append(f"错误：备份失败: {e}")
            return False

    def update_files(self, references: Dict[Path, List[Tuple[int, str, str]]]) -> bool:
        """更新所有引用"""
        print(f"\n[更新] 修改 {len(references)} 个文件...")

        try:
            # 更新依赖文件
            for file_path, file_references in references.items():
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                # 应用所有替换
                for line_no, old_line, new_line in file_references:
                    content = content.replace(old_line, new_line, 1)

                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)

                self.changes.append({
                    'file': str(file_path),
                    'type': 'reference_update',
                    'count': len(file_references)
                })
                print(f"  ✓ {file_path.parent.name}/SKILL.md ({len(file_references)} 处更改)")

            # 更新目标 skill 的 SKILL.md
            old_skill_file = self.skills_dir / self.old_name / "SKILL.md"
            with open(old_skill_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # 更新 name 字段
            content = re.sub(
                r'^name:\s*' + re.escape(self.old_name) + r'$',
                f'name: {self.new_name}',
                content,
                flags=re.MULTILINE
            )

            with open(old_skill_file, 'w', encoding='utf-8') as f:
                f.write(content)

            self.changes.append({
                'file': str(old_skill_file),
                'type': 'name_update',
                'from': self.old_name,
                'to': self.new_name
            })
            print(f"  ✓ {old_skill_file.parent.name}/SKILL.md (name 字段更新)")

            return True
        except Exception as e:
            self.errors.append(f"错误：更新文件失败: {e}")
            return False

    def rename_directory(self) -> bool:
        """重命名 skill 目录"""
        if not self.rename_directory:
            return True

        print(f"\n[重命名] 重命名目录...")
        try:
            old_dir = self.skills_dir / self.old_name
            new_dir = self.skills_dir / self.new_name

            old_dir.rename(new_dir)
            self.changes.append({
                'file': str(old_dir),
                'type': 'directory_rename',
                'to': str(new_dir)
            })
            print(f"  ✓ {self.old_name}/ -> {self.new_name}/")
            return True
        except Exception as e:
            self.errors.append(f"错误：重命名目录失败: {e}")
            return False

    def validate_yaml(self) -> bool:
        """验证所有修改后的 SKILL.md 的 YAML frontmatter"""
        print(f"\n[验证] 检查 YAML 有效性...")

        try:
            # 获取新的 skill 目录位置
            skill_dir = self.skills_dir / self.new_name if self.rename_directory else self.skills_dir / self.old_name
            skill_file = skill_dir / "SKILL.md"

            with open(skill_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # 提取 frontmatter
            match = re.match(r'^---\n(.*?)\n---', content, re.DOTALL)
            if not match:
                self.errors.append(f"错误：{skill_file} 没有有效的 frontmatter")
                return False

            # 解析 YAML
            try:
                frontmatter = yaml.safe_load(match.group(1))
            except yaml.YAMLError as e:
                self.errors.append(f"错误：YAML 解析失败: {e}")
                return False

            # 检查必需字段
            if 'name' not in frontmatter:
                self.errors.append(f"错误：{skill_file} 缺少 'name' 字段")
                return False

            if frontmatter['name'] != self.new_name:
                self.errors.append(f"错误：name 字段不匹配 (期望: {self.new_name}, 实际: {frontmatter['name']})")
                return False

            if 'description' not in frontmatter:
                self.errors.append(f"错误：{skill_file} 缺少 'description' 字段")
                return False

            print(f"  ✓ YAML 格式有效")
            print(f"  ✓ name: {frontmatter['name']}")
            print(f"  ✓ description 字段存在")
            return True

        except Exception as e:
            self.errors.append(f"错误：YAML 验证失败: {e}")
            return False

    def generate_report(self) -> str:
        """生成改名报告"""
        report = []
        report.append("=" * 60)
        report.append("Skill 改名报告")
        report.append("=" * 60)
        report.append("")

        report.append("【基本信息】")
        report.append(f"  旧名称：{self.old_name}")
        report.append(f"  新名称：{self.new_name}")
        report.append(f"  目录重命名：{'是' if self.rename_directory else '否'}")
        report.append(f"  状态：{'✓ 成功' if not self.errors else '✗ 失败'}")
        report.append("")

        if self.changes:
            report.append("【修改文件】")
            for i, change in enumerate(self.changes, 1):
                if change['type'] == 'name_update':
                    report.append(f"  {i}. {Path(change['file']).parent.name}/SKILL.md")
                    report.append(f"     - name: {change['from']} → {change['to']}")
                elif change['type'] == 'reference_update':
                    report.append(f"  {i}. {Path(change['file']).parent.name}/SKILL.md")
                    report.append(f"     - 更新了 {change['count']} 处引用")
                elif change['type'] == 'directory_rename':
                    report.append(f"  {i}. 目录重命名")
                    report.append(f"     - {Path(change['file']).name}/ → {Path(change['to']).name}/")
            report.append("")

        if self.backups:
            report.append("【备份文件】")
            for original, backup in self.backups:
                report.append(f"  ✓ {backup}")
            report.append("")

        if self.errors:
            report.append("【错误信息】")
            for error in self.errors:
                report.append(f"  ✗ {error}")
            report.append("")

        report.append("【恢复说明】")
        if self.backups:
            report.append("  如需恢复，执行以下命令：")
            for original, backup in self.backups:
                report.append(f"  move /Y \"{backup}\" \"{original}\"")
            if self.rename_directory:
                new_dir = self.skills_dir / self.new_name
                old_dir = self.skills_dir / self.old_name
                report.append(f"  move /Y \"{new_dir}\" \"{old_dir}\"")
        report.append("")

        report.append("=" * 60)

        return "\n".join(report)

    def execute(self) -> bool:
        """执行改名操作"""
        print(f"\n{'='*60}")
        print(f"Skill Rename - 改名 '{self.old_name}' → '{self.new_name}'")
        print(f"{'='*60}")

        # Step 1: 验证输入
        if not self.validate_inputs():
            print("\n".join(f"  ✗ {e}" for e in self.errors))
            return False

        # Step 2: 查找引用
        references = self.find_references()
        files_to_backup = list(references.keys())

        # Step 3: 备份文件
        if not self.backup_files(files_to_backup):
            print("\n".join(f"  ✗ {e}" for e in self.errors))
            return False

        # Step 4: 更新文件
        if not self.update_files(references):
            # 恢复备份
            print(f"\n[恢复] 发现错误，恢复备份...")
            for original, backup in self.backups:
                try:
                    shutil.move(str(backup), str(original))
                    print(f"  ✓ 恢复 {original}")
                except:
                    pass
            print("\n".join(f"  ✗ {e}" for e in self.errors))
            return False

        # Step 5: 重命名目录
        if not self.rename_directory_safe():
            # 恢复所有更改
            print(f"\n[恢复] 发现错误，恢复备份...")
            for original, backup in self.backups:
                try:
                    shutil.move(str(backup), str(original))
                    print(f"  ✓ 恢复 {original}")
                except:
                    pass
            print("\n".join(f"  ✗ {e}" for e in self.errors))
            return False

        # Step 6: 验证 YAML
        if not self.validate_yaml():
            print("\n".join(f"  ✗ {e}" for e in self.errors))
            return False

        # Step 7: 生成报告
        print(f"\n{self.generate_report()}")

        return True

    def rename_directory_safe(self) -> bool:
        """安全地重命名目录"""
        if not self.rename_directory:
            return True
        return self.rename_directory()


def main():
    if len(sys.argv) < 3:
        print("使用方法：python rename_skill.py <old_name> <new_name> [--no-rename-dir]")
        print("示例：python rename_skill.py md-image-localize image-localizer")
        sys.exit(1)

    old_name = sys.argv[1]
    new_name = sys.argv[2]
    rename_dir = "--no-rename-dir" not in sys.argv

    renamer = SkillRenamer(old_name, new_name, rename_dir)
    success = renamer.execute()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
