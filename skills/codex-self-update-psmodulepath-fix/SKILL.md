---
name: codex-self-update-psmodulepath-fix
description: 排查与修复 Codex CLI Windows 自更新（codex update / install.ps1）报「Get-FileHash 无法识别」的故障 —— 根因是商店版 PowerShell 7 启动时把 WindowsApps 路径注入 PSModulePath 环境变量，破坏了子进程 powershell.exe 5.1 的模块自动发现；修法是清 PSModulePath 后重跑官方安装脚本。含 Git Bash 环境下 MSYS tar 抢占导致解包失败的连带坑。当用户执行 codex update / codex 自更新报 CommandNotFoundException、或问「为什么 PowerShell 5.1 找不到内置 cmdlet / PSModulePath 被污染」时加载。
---

# Codex 自更新 Get-FileHash 报错修复（PSModulePath 污染）

## 问题现象

在 PowerShell 7（pwsh）终端里执行 `codex update`（或 Codex 内部拉起
`powershell -ExecutionPolicy Bypass -c '...irm https://chatgpt.com/codex/install.ps1 | iex'`），
报：

```
iex : 无法将"Get-FileHash"项识别为 cmdlet、函数、脚本文件或可运行程序的名称。
```

## 根因（2026-09-25 实测定位）

商店版 PowerShell 7（WindowsApps，如 7.6.6）启动时会把自身模块目录注入
`PSModulePath` **进程环境变量**并传给所有子进程：

```
C:\Users\YanQi\Documents\PowerShell\Modules;
C:\Program Files\PowerShell\Modules;
c:\program files\windowsapps\microsoft.powershell_7.6.6.0_x64__8wekyb3d8bbwe\Modules;   ← 毒源
C:\Program Files\WindowsPowerShell\Modules;
C:\WINDOWS\system32\WindowsPowerShell\v1.0\Modules
```

powershell.exe（5.1）按路径顺序做模块自动发现时，先撞上 WindowsApps 里
PS7 专用的 `Microsoft.PowerShell.Utility`，加载失败后 `Get-FileHash` 就
「消失」。模块文件本身完好（显式 `Import-Module Microsoft.PowerShell.Utility`
能成功）。

排除项（排查时别走弯路）：

- **不是 VS Code 配置**：`powershell -NoProfile` 干净子进程照样失败。
- **不是持久化污染**：User / Machine 作用域的 `PSModulePath` 都是空的。
- **5.1 自身没坏**：`system32\WindowsPowerShell\v1.0\Modules\Microsoft.PowerShell.Utility`
  目录与 psd1 完好，显式导入成功。

## 二分定位法（可复用）

对 `PSModulePath` 链逐段做 A/B 测试（Git Bash 示例）：

```bash
BASE='C:\Program Files\WindowsPowerShell\Modules;C:\WINDOWS\system32\WindowsPowerShell\v1.0\Modules'
# 逐段往前拼，哪段拼上就从 True 变 False，哪段就是毒源
PSModulePath="C:\Users\YanQi\Documents\PowerShell\Modules;$BASE" \
  powershell -NoProfile -Command "(Get-Command Get-FileHash -ErrorAction SilentlyContinue) -ne \$null"
```

## 修复

### PowerShell 7 终端里（用户日常场景）

```powershell
Remove-Item Env:\PSModulePath -ErrorAction SilentlyContinue; $env:CODEX_NON_INTERACTIVE=1; irm https://chatgpt.com/codex/install.ps1 | iex
```

### Claude Code（Git Bash）里代跑

清掉 PSModulePath 之外，还要把 `C:\Windows\System32` 提到 PATH 最前，
防止脚本内部的 `tar` 命中 Git 自带 MSYS tar（MSYS tar 把 `C:\...` 当
`远程主机:路径` 解析，报 `Cannot connect to C: resolve failed`）：

```bash
PATH="/c/Windows/System32:$PATH" env -u PSModulePath CODEX_NON_INTERACTIVE=1 \
  powershell -ExecutionPolicy Bypass -Command "irm https://chatgpt.com/codex/install.ps1 | iex"
```

装完验证：`codex --version`（应输出 `codex-cli <新版本号>`）。

## 关联

- 泛化规则：任何「PS 5.1 子进程找不到内置 cmdlet」先查 `PSModulePath`
  是否被 PS7 的 WindowsApps 路径污染，再谈重装系统模块。
- 本机 Codex 安装位置：`C:\Users\YanQi\AppData\Local\Programs\OpenAI\Codex\bin\codex.exe`。
