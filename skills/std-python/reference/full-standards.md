# Python 编码规范 - 完整版

> 本规范基于 [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html)，结合实际工程经验进行了补充。类型注解规则参考 [PEP 484](https://peps.python.org/pep-0484/) 和 [PEP 585](https://peps.python.org/pep-0585/)。默认兼容 Python 3.8+；项目明确要求更高版本时，按项目版本使用对应语法。
>
> 规范落地工具：black、isort、mypy、ruff

---

## 1. 规范等级定义

| 等级 | 定义 | 工具行为 |
|------|------|----------|
| **必须（Mandatory）** | 必须采用 | 代码扫描工具视为错误 |
| **推荐（Preferable）** | 理应采用，特殊情况可例外 | 不视为错误 |
| **可选（Optional）** | 自行决定 | 不检查 |

---

## 2. 代码风格

### 2.1 【必须】格式化

使用 `black` 格式化代码，行长限制 **80 字符**：

```toml
# pyproject.toml
[tool.black]
line-length = 80
target-version = ["py38"]  # 按项目最低 Python 版本调整
```

### 2.2 【必须】引号

优先使用双引号 `"`，`black` 会自动统一。

### 2.3 【必须】分号

**禁止使用分号**，不要在行尾加分号，也不要用分号将两条语句写在同一行。

```python
# 错误
x = 1; y = 2

# 正确
x = 1
y = 2
```

### 2.4 【必须】括号

不要在返回语句或条件语句中添加不必要的括号：

```python
# 错误
if (x == 1):
    return (x)

# 正确
if x == 1:
    return x
```

隐式行续接（implicit line joining）优先于显式续行符 `\`：

```python
# 推荐：用括号换行
result = (some_long_function_name(argument_one, argument_two,
                                  argument_three))

# 不推荐：反斜杠续行
result = some_long_function_name(argument_one, argument_two, \
                                 argument_three)
```

### 2.5 【必须】import 规范

- 每个 import 单独一行
- 使用 `isort` 自动管理，分三组，组间空一行：
  1. 标准库
  2. 第三方库
  3. 本地模块
- **禁止** `from module import *`
- **禁止**相对路径导入（除非在包内部明确需要）

```python
# 错误
import os, sys
from module import *

# 正确
import os
import sys

import requests
from flask import Flask

from myproject.models import User
from myproject.utils import helper
```

别名只在名称冲突或名称过长时使用，且别名要有意义：

```python
import numpy as np         # 约定俗成的别名，可接受
import tensorflow as tf    # 约定俗成的别名，可接受
```

---

## 3. 类型注解

### 3.1 【必须】公开函数必须有类型注解

所有公开函数和方法的参数及返回值必须标注类型（[PEP 484](https://peps.python.org/pep-0484/)）：

```python
from typing import Dict, List, Optional

def get_user(user_id: int) -> Optional[User]:
    ...

def process_items(items: List[str], max_count: int = 10) -> Dict[str, int]:
    ...
```

**例外**：`self` 和 `cls` 不注解。

### 3.2 【推荐】局部变量注解

复杂类型的局部变量建议注解，简单赋值可省略：

```python
# 推荐注解
mapping: Dict[str, List[int]] = {}

# 可省略，类型显而易见
name = "Alice"
count = 0
```

### 3.3 【必须】Optional 写法

Python 3.10+ 以下用 `Optional`，不用 `Union[T, None]`：

```python
from typing import Optional

# 正确（3.8/3.9）
def find(key: str) -> Optional[str]:
    ...

# 正确（3.10+）
def find(key: str) -> str | None:
    ...

# 错误
def find(key: str) -> Union[str, None]:
    ...
```

### 3.4 【推荐】使用 TypeVar 和 Generic

泛型容器在 Python 3.9+ 项目中优先用 `list`、`dict`、`tuple`（[PEP 585](https://peps.python.org/pep-0585/)），Python 3.8 项目使用 `List`、`Dict`：

```python
# Python 3.9+
def merge(a: list[int], b: list[int]) -> list[int]:
    ...

# Python 3.8（必须用 typing）
from typing import List
def merge(a: List[int], b: List[int]) -> List[int]:
    ...
```

### 3.5 【必须】类型检查工具

使用 `mypy` 进行静态类型检查：

```toml
# pyproject.toml
[tool.mypy]
python_version = "3.8"
strict = true
```

---

## 4. Docstring（Google 风格）

### 4.1 【必须】覆盖范围

以下情况**必须**有 docstring：
- 所有公开的模块（module）
- 所有公开的类（class）
- 所有公开的函数和方法

以下情况**可以省略**：
- 私有方法（`_` 前缀），但复杂逻辑建议写
- 明显的单行函数（如 `def double(x): return x * 2`）

### 4.2 【必须】Google 风格格式

```python
def fetch_data(url: str, timeout: int = 30) -> Dict[str, Any]:
    """从指定 URL 获取 JSON 数据。

    Args:
        url: 请求的目标 URL。
        timeout: 请求超时时间（秒），默认 30 秒。

    Returns:
        解析后的 JSON 数据字典。

    Raises:
        ValueError: URL 格式非法时。
        requests.HTTPError: HTTP 请求返回 4xx/5xx 时。
    """
    ...
```

**格式规则**：
- 首行是一句话摘要，句号结尾
- 如有详细说明，空一行后展开
- `Args:`、`Returns:`、`Raises:` 各自独占一块，有内容时才写

```python
class UserService:
    """管理用户账户的服务层。

    提供用户的增删改查操作，所有写操作会触发审计日志。

    Attributes:
        db: 数据库连接实例。
        audit_logger: 审计日志记录器。
    """

    def __init__(self, db: Database, audit_logger: Logger) -> None:
        self.db = db
        self.audit_logger = audit_logger
```

---

## 5. 命名规范

### 5.1 【必须】各类型命名规则

| 类型 | 规则 | 示例 |
|------|------|------|
| 模块 | `snake_case` | `user_service.py` |
| 包 | `lowercase`（无下划线） | `mypackage/` |
| 类 | `PascalCase` | `UserService` |
| 异常 | `PascalCase`，以 `Error` 结尾 | `InvalidTokenError` |
| 函数/方法 | `snake_case` | `get_user_by_id` |
| 变量 | `snake_case` | `user_count` |
| 常量 | `UPPER_CASE` | `MAX_RETRY_COUNT` |
| 类型变量（TypeVar） | `PascalCase`（单字母或短名） | `T`、`UserT` |

### 5.2 【必须】私有命名

- 单下划线前缀 `_name`：模块/类内部使用，不对外公开
- 双下划线前缀 `__name`：触发 name mangling，用于防止子类意外覆盖

```python
class Base:
    def __init__(self) -> None:
        self._internal = 1      # 内部用，子类可访问
        self.__private = 2      # name mangling，子类访问需用 _Base__private
```

### 5.3 【推荐】避免歧义命名

- **禁止**用单字母 `l`（小写 L）、`O`（大写 O）、`I`（大写 i）作变量名
- 避免与内置函数同名：`list`、`dict`、`type`、`id`、`input`、`filter`

---

## 6. 异常处理

### 6.1 【必须】禁止裸 except

```python
# 错误：捕获一切，包括 KeyboardInterrupt、SystemExit
try:
    ...
except:
    pass

# 错误：捕获范围仍然过宽
try:
    ...
except Exception:
    pass

# 正确：明确指定异常类型
try:
    data = json.loads(text)
except json.JSONDecodeError as e:
    logger.error("JSON 解析失败: %s", e)
    raise
```

### 6.2 【必须】自定义异常继承 Exception

```python
# 错误
class MyError(BaseException):
    ...

# 正确
class InvalidConfigError(Exception):
    """配置格式非法。"""

class ServiceUnavailableError(RuntimeError):
    """下游服务不可用。"""
```

### 6.3 【必须】异常链保留上下文

```python
try:
    raw = fetch_raw_data()
except requests.RequestException as e:
    raise DataFetchError("获取数据失败") from e  # 保留原始异常链
```

### 6.4 【必须】上下文管理器管理资源

```python
# 错误
f = open("data.txt")
data = f.read()
f.close()

# 正确
with open("data.txt") as f:
    data = f.read()
```

### 6.5 【推荐】不要用异常控制正常流程

```python
# 不推荐：用异常做流程控制
try:
    value = d[key]
except KeyError:
    value = default

# 推荐：用 .get()
value = d.get(key, default)
```

---

## 7. 函数与类

### 7.1 【必须】禁止可变默认参数

```python
# 错误：所有调用共享同一个 list 对象
def append_to(element, to=[]):
    to.append(element)
    return to

# 正确
def append_to(element, to=None):
    if to is None:
        to = []
    to.append(element)
    return to
```

### 7.2 【必须】使用 @property 代替 getter/setter

```python
# 错误
class Circle:
    def get_radius(self): return self._radius
    def set_radius(self, r): self._radius = r

# 正确
class Circle:
    @property
    def radius(self) -> float:
        return self._radius

    @radius.setter
    def radius(self, value: float) -> None:
        if value < 0:
            raise ValueError("radius 不能为负数")
        self._radius = value
```

### 7.3 【推荐】函数长度

- 函数不超过 **50 行**（不含 docstring 和空行）
- 超过时考虑拆分为多个私有方法

### 7.4 【推荐】参数数量

- 参数不超过 **5 个**
- 超过时考虑将参数封装为 dataclass 或 TypedDict

```python
# 不推荐
def create_user(name, email, age, role, department, manager_id, is_active):
    ...

# 推荐
@dataclass
class CreateUserRequest:
    name: str
    email: str
    age: int
    role: str
    department: str
    manager_id: int
    is_active: bool = True

def create_user(request: CreateUserRequest) -> User:
    ...
```

### 7.5 【必须】嵌套深度

嵌套深度不超过 **4 层**，超过时抽取为独立函数。

---

## 8. 现代 Python 特性

### 8.1 【必须】f-string 格式化

Python 3.6+ 优先使用 f-string，不用 `%` 格式化或 `.format()`：

```python
# 不推荐
name = "Alice"
msg = "Hello, %s!" % name
msg = "Hello, {}!".format(name)

# 正确
msg = f"Hello, {name}!"
```

### 8.2 【推荐】dataclass 替代样板类

```python
from dataclasses import dataclass, field
from typing import List

@dataclass
class Point:
    x: float
    y: float
    tags: List[str] = field(default_factory=list)

    def distance_to(self, other: "Point") -> float:
        return ((self.x - other.x) ** 2 + (self.y - other.y) ** 2) ** 0.5
```

### 8.3 【推荐】Enum 替代字符串常量

```python
from enum import Enum, auto

# 不推荐
STATUS_PENDING = "pending"
STATUS_RUNNING = "running"
STATUS_DONE = "done"

# 推荐
class TaskStatus(Enum):
    PENDING = auto()
    RUNNING = auto()
    DONE = auto()
```

### 8.4 【推荐】pathlib 替代 os.path

```python
from pathlib import Path

# 不推荐
import os
config_path = os.path.join(os.path.dirname(__file__), "config.yaml")

# 推荐
config_path = Path(__file__).parent / "config.yaml"
```

### 8.5 【推荐】walrus operator（Python 3.8+）

在避免重复计算时使用 `:=`，不要为了使用而使用：

```python
# 有益的使用
while chunk := f.read(8192):
    process(chunk)

# 不要为了「简洁」滥用
# 正常的 if 更可读时，就不要用
```

---

## 9. 测试规范

### 9.1 【推荐】默认使用 pytest

应用 / 服务类项目默认 pytest。例外：零依赖工具类项目（脚本须在裸 Python 环境直接运行、不引入第三方包）可用标准库 `unittest`；pytest 可直接收集 unittest 用例，后续需要其工具链时无须改写。项目规则（AGENTS.md / CLAUDE.md）对框架另有约定时以项目规则为准。

```toml
# pyproject.toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_functions = ["test_*"]
```

### 9.2 【必须】测试文件结构

```
tests/
├── conftest.py          # 共享 fixture
├── unit/
│   └── test_user_service.py
├── integration/
│   └── test_api.py
└── performance/
    └── test_throughput.py
```

测试函数命名：`test_<被测对象>_<场景>_<期望结果>`

```python
def test_get_user_with_valid_id_returns_user():
    ...

def test_get_user_with_invalid_id_raises_not_found():
    ...
```

### 9.3 【必须】三段式结构（Arrange-Act-Assert）

```python
def test_user_service_creates_user():
    # Arrange
    db = FakeDatabase()
    service = UserService(db)
    request = CreateUserRequest(name="Alice", email="alice@example.com")

    # Act
    user = service.create(request)

    # Assert
    assert user.id is not None
    assert user.name == "Alice"
    assert db.get(user.id) == user
```

### 9.4 【推荐】覆盖要求

- 每个公开函数至少有一个正常路径测试
- 边界条件、异常路径显式覆盖
- 目标行覆盖率：**80%+**

---

## 10. 工具链

| 工具 | 用途 | 配置文件 |
|------|------|---------|
| `black` | 代码格式化（自动修复） | `pyproject.toml` |
| `isort` | import 排序（自动修复） | `pyproject.toml` |
| `mypy` | 静态类型检查 | `pyproject.toml` |
| `ruff` | 综合 lint（含 flake8 规则子集） | `pyproject.toml` |
| `pytest` | 测试框架 | `pyproject.toml` |

推荐 `pyproject.toml` 最小配置：

```toml
[tool.black]
line-length = 80
target-version = ["py38"]  # 按项目最低 Python 版本调整

[tool.isort]
profile = "black"
line_length = 80

[tool.mypy]
python_version = "3.8"
strict = true
ignore_missing_imports = true

[tool.ruff]
line-length = 80
select = ["E", "F", "W", "I"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```
