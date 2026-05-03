---
name: google-cpp-naming
description: |
  【知识库】Google C++ 命名规范。生成、修改、审查或解释 C++ 代码时，如用户要求 Google C++ 风格，或需要统一 class、struct、变量、成员、常量、函数、namespace、enum、template 参数、macro 的命名风格时启用。
user-invocable: false
---

# Google C++ 命名规范

## 执行原则

生成、修改或审查 C++ 代码时，默认按本技能中的命名规则输出代码。除非用户要求解释规范，否则不要在最终回答里额外说明「已使用本技能」。

优先级：

1. 项目已有更具体、更一致的本地命名风格时，优先保持本地一致性。
2. 用户明确要求 Google C++ 风格时，按本技能执行。
3. 若本技能与当前仓库规范冲突，先指出冲突，再按用户目标或本地规范处理。

## 命名速查

| 对象 | 规则 | 示例 |
|---|---|---|
| 文件名 | 全小写；可用 `_` 或 `-`；无本地惯例时优先 `_` | `foo_bar.cc`、`foo_bar.h` |
| C++ 源文件扩展名 | 源文件用 `.cc`；头文件用 `.h`；文本包含片段用 `.inc` | `http_server_logs.cc` |
| 类型名 | `PascalCase`；适用于 class、struct、enum、type alias、type template parameter、concept | `UrlTable`、`UrlTableError` |
| 普通变量与参数 | `snake_case` | `table_name`、`num_entries` |
| class 数据成员 | `snake_case_`，末尾加 `_`；静态常量成员按常量规则 | `table_name_`、`pool_`、`kTableVersion` |
| struct 数据成员 | `snake_case`，不加尾 `_` | `name`、`num_entries` |
| 常量 | 固定值的 `constexpr` 或 `const` 用 `k` + `PascalCase`；静态存储期常量必须这样命名 | `kDaysInAWeek`、`kAndroid8_0_0` |
| 函数 | 通常用 `PascalCase` | `AddTableEntry()`、`OpenFileOrDie()` |
| getter / setter | 可以用变量风格 `snake_case` | `count()`、`set_count(int count)` |
| namespace | `snake_case`；顶层 namespace 应全局唯一且可识别 | `my_project` |
| enum 枚举值 | 常量风格，使用 `kEnumName`，不要用宏风格 | `kOk`、`kOutOfMemory` |
| template 参数 | 类型模板参数按类型名规则；非类型模板参数按变量或常量规则 | `typename ValueType`、`int max_count` |
| macro | 尽量不用；必要时用全大写 + `_`，并带项目特定前缀 | `MYPROJECT_ROUND(x)` |

## 生成代码时的检查清单

- 新增 class 私有成员时，使用尾下划线，例如 `cache_size_`。
- 新增 struct 字段时，不加尾下划线，例如 `cache_size`。
- 新增常量时，判断它的值是否在程序生命周期内固定；若固定且为静态存储期，使用 `kName`。
- 新增 enum 值时，使用 `kName`，不要使用 `ALL_CAPS`。
- 新增 getter / setter 时，优先使用 `name()` 和 `set_name(...)`。
- 遇到缩写时，把缩写当作普通单词处理，例如 `StartRpc()`，不要写成 `StartRPC()`。
- 命名长度与作用域匹配：作用域越广，名字越需要描述性；局部循环变量可以短。

## 示例

```cpp
class TableInfo {
 public:
  static const int kTableVersion = 3;

  int count() const;
  void set_count(int count);

 private:
  std::string table_name_;
  Pool<TableInfo>* pool_;
};

struct UrlTableProperties {
  std::string name;
  int num_entries;
};

enum class UrlTableError {
  kOk = 0,
  kOutOfMemory,
  kMalformedInput,
};
```

## 来源

- [Google C++ Style Guide：Naming](https://google.github.io/styleguide/cppguide.html#Naming)
- [Google C++ Style Guide：File Names](https://google.github.io/styleguide/cppguide.html#File_Names)
- [Google C++ Style Guide：Type Names](https://google.github.io/styleguide/cppguide.html#Type_Names)
- [Google C++ Style Guide：Variable Names](https://google.github.io/styleguide/cppguide.html#Variable_Names)
- [Google C++ Style Guide：Constant Names](https://google.github.io/styleguide/cppguide.html#Constant_Names)
- [Google C++ Style Guide：Function Names](https://google.github.io/styleguide/cppguide.html#Function_Names)
- [Google C++ Style Guide：Enumerator Names](https://google.github.io/styleguide/cppguide.html#Enumerator_Names)
