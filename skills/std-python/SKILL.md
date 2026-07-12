---
name: std-python
description: 提供 Python 编码规范（基于 Google Python Style Guide）。当编写或 review Python 代码（.py 文件）时使用。
---

> 输出一行：`Using std-python`

# Python 编码规范

> 基于 [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html)，类型注解规则参考 [PEP 484](https://peps.python.org/pep-0484/) 和 [PEP 585](https://peps.python.org/pep-0585/)。默认兼容 Python 3.8+；项目明确要求更高版本时，按项目版本使用对应语法。

## 规范等级定义

| 等级 | 定义 |
|------|------|
| **必须（Mandatory）** | 必须采用，代码扫描工具视为错误 |
| **推荐（Preferable）** | 理应采用，特殊情况可例外 |
| **可选（Optional）** | 自行决定是否采用 |

## 核心规则速查

| 类别 | 必须遵守 |
|------|----------|
| **格式化** | 使用 `black` 格式化，行长 80 字符 |
| **import** | 分三组：标准库 → 第三方 → 本地，使用 `isort` 管理 |
| **类型注解** | 所有公开函数/方法必须有完整类型注解，并匹配项目 Python 版本 |
| **docstring** | 所有公开模块/类/函数必须有 Google 风格 docstring |
| **异常** | 禁止裸 `except:`，自定义异常继承自 `Exception` |
| **命名** | 类 `PascalCase`，函数/变量 `snake_case`，常量 `UPPER_CASE` |
| **可变默认值** | 禁止使用可变对象（list/dict/set）作为默认参数 |
| **测试** | 测试文件以 `test_` 开头，默认 `pytest`；零依赖工具类项目可用标准库 `unittest`，项目规则优先 |

## 完整规范

详见 [reference/full-standards.md](reference/full-standards.md)，包含：
- 代码风格（格式化、import、引号、空格）
- 类型注解规范（PEP 484/526）
- Docstring 格式（Google 风格）
- 命名规范（模块、包、类、函数、变量、常量）
- 异常处理（类型体系、捕获范围、上下文管理器）
- 函数与类设计（默认参数、属性访问、单一职责）
- 现代 Python 特性（f-string、dataclass、Enum、pathlib）
- 测试规范（pytest、测试结构、覆盖要求）
- 工具链（black、isort、mypy、ruff）
