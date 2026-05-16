# TypeScript 重写：npm 发布

## Goal

将 cc-pomodoro 从 Python 重写为 TypeScript，通过 npm 发布。架构、设计决策、功能需求不变（继承原 PRD）。纯语言迁移。

## Scope

- 所有 Python 模块 → TypeScript（Node.js 22+ stdlib，零外部生产依赖）
- 测试框架：pytest → vitest
- 包管理：pip/setuptools → npm
- Hook 脚本：`python -m cc_pomodoro.hooks` → `npx cc-pomodoro-hooks` 或 `node node_modules/cc-pomodoro/dist/hooks.mjs`
- CLI: `cc-pomodoro` → `npx cc-pomodoro` 或全局安装

## 不变

- 架构：Hook Scripts + File-backed State + Timer Process
- 设计决策：零外部依赖、原子写入、auto_start 默认 false、双平台不对称等
- 文件格式：state.json / config.json / sessions.jsonl 不变
- Hook 脚本契约：stdin JSON → stdout JSON，exit code 语义不变

## 技术栈

- TypeScript 5.x + Node.js 22+
- 构建：`tsc` 编译到 `dist/`
- 测试：vitest
- CLI 入口：`bin` 字段指向编译后的 `dist/cli.mjs`

## Out of Scope

- 架构变更
- 新功能
- 设计决策重审
