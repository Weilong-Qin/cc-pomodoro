# AI CLI 原生番茄钟（cc-pomodoro）

> Grilling 日志见：[`.grill/cc-pomodoro.md`](../../../.grill/cc-pomodoro.md)（13 轮讨论的收口结论）

## Goal

做一个**面向 AI CLI 的原生番茄钟应用**，首批支持 Claude Code 和 Codex CLI（双 P0），后续可扩展 Gemini CLI / Copilot CLI。

用户向 AI 发送一条指令的瞬间，自动开启一个专注周期。周期内：
- 屏蔽 AI 的完工信号（不弹通知、不显示输出涌出、不显示"完成"状态）
- 阻塞 AI 中间的授权请求与反问（延迟到周期结束统一处理）
- CLI 内只显示倒计时，其他全部隐藏
- 用户可随时手动早结束（Y/N 软确认）

**核心问题**：切断「AI 一回复就立刻刷过去看 → 给下一条指令 → 切回深度工作 → 上下文丢失」这一条**反应式焦虑反射弧**。

**核心价值（差异化壁垒）**：**"CLI 原生的 Pomodoro 交互整合"** 这一整套机制——这是 Forest + 关终端通知**做不到**的，是这工具的存在合理性。stats 是次要附带。

## What I already know

- 双平台双 P0：Claude Code + Codex CLI
- 实现路径已锁：**两套各自原生 hook 集成 + 统一 stats schema**（grill log Q9 决议为 D 方案）
- 周期内 UI 极简：只有倒计时，所有 AI 状态全屏蔽（grill log Q8/Q13）
- AI 在周期内完全空转可接受（grill log Q8："以人为核心，AI 空转可接受"）
- 不锁用户输入（grill log Q4 决议：不 cover 终端、不拦截键盘）
- 不让 AI 自治续命（grill log Q3 决议：完工即停，简单可控）
- 早结束用软确认（grill log Q6.2 决议：Y/N 弹窗，不上 Forest 式惩罚）

### 研究已确认（2026-05-15，4 份独立报告）

| 需求 | Claude Code | Codex CLI |
|------|-------------|-----------|
| R1 dispatch 触发 | ✅ UserPromptSubmit hook | ✅ UserPromptSubmit hook |
| R3 阻塞授权/反问 | ✅ PreToolUse → `allow` 全自动放行 | ✅ PreToolUse → `allow` |
| R5 阻止周期内新 prompt | ✅ UserPromptSubmit → `block` | ✅ 同 Claude Code |
| **R2/R4 屏蔽完工输出** | ❌ **hook 无法拦截终端输出**（Stop hook 在输出渲染后才触发） | ✅ 有 `suppressOutput` flag + `last_assistant_message` |
| 倒计时显示 | ⚠️ 需额外方案 | ⚠️ 需额外方案 |

**关键不对称**：Codex CLI 原生支持输出隐藏，Claude Code 的 hook 系统做不到。Claude Code 上 R2 需要进一步调研替代方案（stdout redirect / PTY / 其他）。

Stats 数据模型：JSONL，10 字段 MVP schema（详见 `research/pomodoro-stats-schemas.md`）。

## Architecture Decision（ADR-lite，2026-05-15）

**Context**：研究确认双平台 R2 能力不对称——Codex 原生 `suppressOutput`，Claude Code Stop hook 在输出渲染后才触发。

**Decision**：接受不对称。Codex 走原生 suppressOutput 路径做完整 R2。Claude Code 上先做到"关 bell + 无 OS 通知 + 阻塞授权/反问"，用户靠「切到别的窗口不看终端」实现 R2。**同步对 Claude Code 做进一步调研**，寻找原生输出隐藏的替代方案（stdout redirect 等，但不退回全 PTY wrapper）。

**Consequences**：
- Claude Code MVP 体验打折（R2 靠用户自律兜底）→ AC8 主观评分是关键验证点
- 如果 2 周验证后发现自律不够，必须有回退方案（加轻量 stdout redirect）
- 不阻塞 Codex 端的完整实现

## Assumptions (temporary, to validate)

- **Claude Code 存在某种未发现的输出拦截机制** ← 需要进一步调研（用户已指令）
- **CLI 内可以稳定显示倒计时** ← CLI countdown display agent 推荐了 DECSTBM scroll region + pipe wrapper 模式，两平台具体方案待定
- **本地 JSONL 存储 stats 够用** ← pomodoro-stats agent 推荐 JSONL，本地文件，不强求云同步）

## Requirements (evolving)

### MVP P0
- **R1 dispatch 触发**：用户向 AI 发送 prompt 的瞬间自动启动专注周期（可在配置中设默认开/关）。周期时长：**预设默认 + 可临时覆盖**（`/pomodoro start 25` 覆盖本次），不每次弹时长选择破坏 dispatch 流畅度。默认值 TBD（提议 50 分钟匹配"读一篇论文"场景）
- **R2 屏蔽完工信号**：AI 完成 turn 后，不在 CLI 显示输出、不弹通知、不响铃，直到周期结束才一次性揭示。**Codex CLI：原生 `suppressOutput` 实现。Claude Code：先做到关 bell + 无通知 + 用户自律（切走不看终端），同步进一步调研替代方案**
- **R8 周期内阻止新 prompt**：番茄钟期间，UserPromptSubmit hook 返回 `block`，提示"Pomodoro 进行中，还剩 X:XX。`/pomodoro stop` 可提前结束。" 保护 one-task-per-cycle 承诺
- **R9 周期结束后的默认行为**：周期结束 → 揭示输出 → **回到普通模式**。下一条 prompt 不自动启动新番茄钟。用户主动决定下一轮要不要专注（`/pomodoro start`），工具不自动替用户承诺
- **R10 配置方式**：配置文件 `~/.config/cc-pomodoro/config.json` + slash command 双入口。Slash command 前缀 `/pomodoro` 不抠掉，直接和用户 prompt 一起传给 LLM（LLM 自行忽略前缀处理正文）。配置类命令（`/pomodoro config`、`/pomodoro stop`）hook 返回 `block` 拦截，不需要 Claude 处理

### Slash Commands
| 命令 | 作用 | 是否传给 LLM |
|------|------|-------------|
| `/pomodoro start [分钟] <prompt>` | 启动番茄钟 + 发送 prompt | ✅ 传（LLM 自行理解前缀） |
| `/pomodoro stop` | 提前结束番茄钟 | ❌ hook 拦截 |
| `/pomodoro status` | 显示剩余时间 | ❌ hook 拦截 |
| `/pomodoro stats [筛选]` | 查询统计 | ❌ hook 拦截 |
| `/pomodoro config [set key value]` | 读/改配置 | ❌ hook 拦截 |
- **R3 阻塞授权/反问**：周期内 AI 触发的所有 tool-use 授权、clarification 问题被工具 hold，延迟到周期结束
- **R4 周期内 UI**：仅倒计时可见，无 spinner / progress / status bar / "AI 在干活" 等任何 AI 状态信号
- **R5 软早结束**：用户按热键触发 `还剩 X 分钟，确定结束？[y/N]`，y 立即揭示全部 buffered 输出
- **R6 双平台同步**：Claude Code 和 Codex CLI 都能跑通 R1-R5（双平台代码分别原生实现）
- **R7 最小 stats**：本地记录每次 session 的核心字段（见 Open Question stats schema），命令行 query 即可

### MVP P1
- 周期长度可配置（配置文件改 `duration`，默认 50 分钟）
- 周期到点后的衔接行为可配置（可切换为自动续杯模式）
- Stats 查询：`/pomodoro stats` 打格式化表格（今日/本周汇总 + 按 app 分列 + 最近 session 列表），`--json` 出 JSONL 原始数据

### P2+（明确不在 MVP）
- Gemini CLI / Copilot CLI 支持
- 跨设备/云同步 stats
- 可视化 dashboard（CLI 输出表格作为最小可行；web dashboard 是后期）

## Acceptance Criteria (evolving)

- [ ] AC1：在 Claude Code 中发送任一 prompt，周期自动启动（或用户已配置自动启动）；周期内 AI 完成 turn 但终端不显示任何输出，仅显示倒计时
- [ ] AC2：在 Codex CLI 中同样能做到 AC1（机制可能不同但效果一致）
- [ ] AC3：周期内 AI 触发 tool-use 授权（如执行 shell 命令）时，授权请求被 hold，AI 进入等待状态，但用户终端不显示任何提示
- [ ] AC4：用户按热键（如 Ctrl+E）触发结束确认 `还剩 X 分钟，确定结束？[y/N]`，输入 y 立即揭示完整 buffered 输出
- [ ] AC5：周期自然结束时（倒计时到 0）自动揭示完整 buffered 输出 + 提示音/视觉提醒
- [ ] AC6：每完成或中止一个 session，stats 文件追加一条记录，包含至少 {start_at, end_at, app, duration_planned, duration_actual, ended_by, blocking_requests_queued} 字段
- [ ] AC7：`/pomodoro stats` 能输出近 7 天的 session 列表 + 总专注时长
- [ ] AC8：作者自己用 2 周后，主观评分 ≥4/5 觉得"真的帮我减少了反应式焦虑"（pre-mortem (a) 验证）

## Definition of Done

- 双平台 hook 集成测试可手动复现 AC1-AC5
- stats 数据模型有单元测试
- README 写明安装、配置、3 种典型使用流
- 在本人 + 阿龙 + 至少 1 个额外早期用户的真实工作流中各试用 ≥3 天
- 公开仓库设了 issue 模板、PR 模板、basic CI（lint/test）

## Out of Scope

源自 grill log 的明确排除：

- 解决"AI 闲下来 = 我亏了"愧疚（grill Q3 用户否认存在此心结）
- AI 在隐瞒期间自治续命（grill Q3 决议）
- 锁用户输入 / 全屏遮罩 / 强制隐藏终端（grill Q4 决议）
- 显示 AI runtime 状态（"AI 在干活"/"AI 在等你"）（grill Q7 矛盾检验决议）
- 重摩擦早结束（长按 ESC / 敲数字 / 连胜惩罚）（grill Q6.2 决议）
- CLI wrapper 实现路径（grill Q9 决议）
- 终端层插件实现路径（grill Q9 决议）
- MVP 阶段不含 Gemini CLI / Copilot CLI
- Stats 不进 P0 核心卖点（必须有最小可用版本，但不是主菜）
- 复杂可视化（图表/趋势/堆积条等）—— 后期再说

## Open Questions

全部已收口（brainstorm 2026-05-15）。剩余行动项：
- **Claude Code R2 输出隐藏**：需要进一步调研替代方案（用户已指令，不阻塞 MVP 启动）
- **倒计时终端显示**：两平台具体方案待定（研究推荐 DECSTBM / OSC 终端标题 / ANSI 清屏重印）
- **默认时长**：50 分钟（用户可配置覆盖）

## Pre-mortem 风险（grilling 收口锁定）

- **(a) 自我验证窗口**：MVP 上线 2 周内作者必须老实评估"自己是否真的每天用 ≥3 次"——若否，整个项目的存在合理性需重审。AC8 是这一条的硬验收。
- **(b) Codex hook 不存在或形态差异巨大**：这是 D 方案的命门，**写代码前必须先做 Codex hook 调研**（已列入 Open Question 1）。
- **(c) 唯一真实用户是作者**：阿龙是第二个画像，但**写代码前先做 15 分钟需求验证访谈**——确认 TA 真的会装 hook 工具到 TA 的 CLI 配置里。
- **(d) 抽象层过早**：建议 **先 Claude Code 走通 R1-R5**，跑通后再用已锁定的接口反推 Codex 适配层，避免空中楼阁。

## Research References

- [`research/claude-code-hooks.md`](research/claude-code-hooks.md) — R1/R3 ✅, R2 ❌（输出渲染后才触发 Stop hook）
- [`research/codex-cli-hooks.md`](research/codex-cli-hooks.md) — 全 R1-R5 ✅（有 `suppressOutput` flag，比 Claude Code 完整）
- [`research/cli-countdown-display.md`](research/cli-countdown-display.md) — 推荐 DECSTBM scroll region 或 OSC 终端标题
- [`research/pomodoro-stats-schemas.md`](research/pomodoro-stats-schemas.md) — JSONL MVP schema: 10 字段，零依赖

## Technical Approach

### Architecture: Hook Scripts + File-backed State + Lightweight Timer Process

```
用户敲 "/pomodoro start 25 重构 auth"
  ↓
UserPromptSubmit hook（shell 脚本）:
  1. 写 state.json → {active: true, started_at: ..., end_at: ..., duration: 25}
  2. 后台启动计时进程: python -m cc_pomodoro.timer --duration 25 &
  3. 返回 continue:true（prompt 传给 LLM，前缀 /pomodoro 不抠掉）
  ↓
PreToolUse hook:
  读 state.json → active? → stdout: {"permissionDecision": "allow"}
  ↓
Stop hook:
  读 state.json → active? → stdout: {"decision": "block"}
  ↓
25 分钟到 → 计时进程唤醒:
  → OS 桌面通知 "Pomodoro 完成"
  → 写 state.json active=false
  → 追加 sessions.jsonl 一条记录
```

**零外部依赖，文件做状态交换，无 HTTP daemon。**

### Tech Stack
- **语言**: Python 3.10+（跨平台 Win/Mac/Linux，零外部依赖）
- **状态**: JSON 文件 (`~/.config/cc-pomodoro/state.json`)
- **统计**: JSONL append (`sessions.jsonl`)
- **配置**: JSON (`config.json`)
- **OS 通知**: `notify-send` (Linux) / `osascript` (macOS) / PowerShell Toast (Windows)
- **Hook 脚本**: Bash（Linux/macOS）/ Batch 或 PowerShell（Windows），薄壳调 Python

### Package Structure
```
cc_pomodoro/
  __init__.py
  timer.py       # 计时进程：sleep → notify → write state
  state.py       # state.json 读写
  stats.py       # sessions.jsonl 追加 & 查询
  config.py      # config.json 管理
  notify.py      # 跨平台 OS 通知适配
  cli.py         # 用户命令入口

hooks/
  claude-code/
    user_prompt_submit.sh
    pre_tool_use.sh
    stop.sh
  codex-cli/
    user_prompt_submit.sh
    pre_tool_use.sh
    stop.sh
```
