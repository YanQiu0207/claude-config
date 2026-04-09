# Skill Rename - Skill 改名工具

用于安全、完整地改名 skill 并更新所有依赖关系的工具。

## 快速开始

```bash
# 基本用法：改名 skill 并重命名目录
python scripts/rename_skill.py old_name new_name

# 只改 name 字段，不重命名目录
python scripts/rename_skill.py old_name new_name --no-rename-dir
```

### 示例

```bash
# 把 md-image-localize 改名为 image-localizer
python scripts/rename_skill.py md-image-localize image-localizer

# 把 markdown-cn 改名为 chinese-typography，但不重命名目录
python scripts/rename_skill.py markdown-cn chinese-typography --no-rename-dir
```

## 功能

✅ **自动扫描依赖** — 识别所有其他 skill 中对该 skill 的引用

✅ **支持多种引用形式**：
- 反引号：`` `skill-name` ``
- YAML 字段：`requires: [skill-name]`, `depends_on: [skill-name]`
- 注释：`# depends on skill-name`, `# 需要调用 skill-name`
- 链接和路径：`[skill-name](../skill-name/)`, `../skill-name/`

✅ **自动备份** — 修改前为所有文件创建备份，失败时完全恢复

✅ **YAML 验证** — 确保修改后的 frontmatter 有效

✅ **详细报告** — 输出所有修改的文件和位置

## 工作流程

```
1. 验证输入
   ↓
2. 查找所有引用
   ↓
3. 创建备份
   ↓
4. 更新引用和 name 字段
   ↓
5. 重命名目录（可选）
   ↓
6. 验证 YAML
   ↓
7. 生成报告
```

## 如何恢复

如果改名后出现问题，可以通过备份文件恢复：

脚本会自动生成恢复说明，包含所有备份文件的路径。

也可以手动恢复：

```bash
# Windows
move /Y "C:\...\SKILL.md.backup" "C:\...\SKILL.md"
move /Y "C:\...\other_skill\SKILL.md.backup" "C:\...\other_skill\SKILL.md"

# Linux/Mac
mv backup/SKILL.md.backup SKILL.md
mv backup/other_skill/SKILL.md.backup other_skill/SKILL.md
```

## 文件结构

```
skill-rename/
├── SKILL.md                # Skill 定义和文档
├── README.md              # 本文件
├── scripts/
│   └── rename_skill.py    # 改名脚本
└── evals/
    └── evals.json         # 测试用例
```

## 技术细节

### 搜索模式

脚本使用多种正则表达式模式来查找引用：

| 形式 | 正则表达式 | 示例 |
|------|-----------|------|
| 反引号 | `` `name` `` | `` `md-image-localize` `` |
| YAML requires | `requires: [name]` | `requires: [md-image-localize]` |
| YAML depends_on | `depends_on: [name]` | `depends_on: [md-image-localize]` |
| 英文注释 | `# depends on name` | `# depends on md-image-localize` |
| 中文注释 | `# 需要调用 name` | `# 需要调用 md-image-localize` |
| 链接 | `[name](../name/)` | `[md-image-localize](../md-image-localize/)` |
| 路径 | `../name/` | `../md-image-localize/` |

### 备份策略

- 每个将被修改的文件都获得一个 `.backup` 备份
- 备份文件保存在原文件所在目录
- 如果改名失败，自动恢复所有备份
- 改名成功后，备份文件保留以便日后恢复

### 安全保障

1. **验证** — 改名前检查老 skill 是否存在、新 skill 是否已被使用
2. **原子性** — 所有修改都在 YAML 验证后进行，失败则全部回滚
3. **可追溯** — 详细的日志和报告记录所有改动
4. **可恢复** — 备份文件和恢复说明

## 常见问题

**Q: 能同时改多个 skill 的名称吗？**
A: 不行，每次只能改一个。如果需要改多个，请逐个执行脚本。

**Q: 脚本会修改其他目录（如 plugins）中的 skill 吗？**
A: 不会，脚本只在 `C:\Users\YanQi\.claude\skills\` 目录中操作。

**Q: 为什么有些引用没有被更新？**
A: 可能是因为那些引用不匹配任何已知的模式。可以手动编辑或提交建议以添加新的搜索模式。

**Q: 改名后，description 字段需要更新吗？**
A: 不一定。如果 description 中包含 skill 名称，可能需要手动更新，但脚本不会自动修改 description。

## 依赖

- Python 3.6+
- PyYAML (`pip install pyyaml`)

## 调试

如果出现问题，查看：
1. 脚本的控制台输出（会显示每一步的进度）
2. `.backup` 文件（确认备份已创建）
3. 最后的报告（显示所有修改的文件）

## 许可证

与 skill-rename skill 相同。
