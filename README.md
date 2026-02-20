# Decision Engine Core v0.3

多智能体决策引擎原型：4 Agent 闭环（创意验证 → 市场分析 → 策略建议 → 反思）。支持 **Mock**（默认）与 **通义千问（Qwen）**，Qwen 失败自动回退 Mock；每次运行结果会保存到 `data/sessions/`。v0.3 新增 **决策指数（Decision Metrics）**：综合分 0–100、等级 A/B/C/D、建议与风险 KPI，以及 Markdown 报告中的指数章节。

## 运行

### 1. 虚拟环境与依赖

```bash
cd decision_os
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
# source .venv/bin/activate
pip install -r requirements.txt
```

### 2. 环境变量（可选）

- 复制示例并按需填写：
  ```bash
  cp .env.example .env
  ```
- 使用 **Mock**（默认）：无需配置，不填 `DASHSCOPE_API_KEY` 即可运行。
- 使用 **通义千问**：在 `.env` 中设置：
  - `LLM_PROVIDER=qwen`
  - `DASHSCOPE_API_KEY=你的 API Key`（在 [DashScope 控制台](https://dashscope.console.aliyun.com/) 创建）
  - 可选：`QWEN_MODEL=qwen-plus`（默认即为 qwen-plus）

### 3. 启动应用

```bash
streamlit run app/web_app.py
```

浏览器打开提示的 URL，输入问题后点击「运行决策引擎」即可看到 3 个 stage 输出与 Reflection；界面会提示会话已保存，并可使用「下载本次会话 JSON」下载当前运行的完整 ctx。

## v0.2 新功能

### 顶部运行状态栏

页面顶部显示：
- **Provider**：当前使用的 LLM 提供商（mock / qwen）
- **Qwen 模型**：若使用 Qwen，显示模型名称
- **调用次数**：当前运行调用次数（占位显示）
- **Token 消耗**：Token 使用量（占位显示：估算中）
- **运行耗时**：本次运行耗时（秒）

### 历史会话管理

- 左侧边栏提供「历史会话」功能
- 自动读取 `data/sessions/` 下的 JSON 文件
- 按时间倒序显示最近 20 条会话
- 选择会话后点击「加载会话」即可查看历史结果
- 加载的会话会直接展示，无需重新运行引擎

**使用方式**：
1. 在左侧边栏选择历史会话（显示格式：`2026-02-16 15:30:10 (xxx)`）
2. 点击「加载会话」按钮
3. 页面会展示该会话的完整内容

### Markdown 报告导出

每次运行后，除了 JSON 下载，还提供「下载 Markdown 报告」功能：

- 报告包含：
  - 用户输入（问题、背景）
  - 决策阶段（问题解析、市场分析、策略建议）
  - 反思总结
- 格式清晰，使用标准 Markdown 标题
- 文件名包含时间戳：`decision_report_2026-02-16T15-30-10.md`

**使用方式**：
1. 运行决策引擎后，在结果区域找到「下载 Markdown 报告」按钮
2. 点击下载即可获得格式化的决策报告

## v0.3 决策指数（Decision Metrics）

- **综合分**：0–100，由可行性、市场、风险、资源四项各 0–25 规则汇总，可解释、可复现（不依赖 LLM）。
- **等级**：A（≥80）、B（60–79）、C（40–59）、D（<40）。
- **建议**：做 / 谨慎 / 暂缓 / 不建议（来自策略阶段 verdict）。
- **风险**：低 / 中 / 高（来自策略阶段 overall_risk_level）。
- 结果写入 `ctx.extra["decision_metrics"]`；UI 顶部在状态栏下方展示 KPI。
- Markdown 报告新增「决策指数（v0.3）」章节：综合分、分项分、关键不确定性、下一步验证清单。
- 缺字段时优雅降级（默认中等分并说明缺失），不报错。

## 会话持久化

- 每次点击运行并得到结果后，会自动创建目录 `data/sessions`（若不存在），并将本次完整 ctx（含 stages 与 reflection）保存为 JSON。
- 文件名格式：`2026-02-16T15-30-10_<短id>.json`（Windows 兼容，无冒号）。
- 无论使用 Mock 还是 Qwen，都会保存；保存成功后页面会显示路径并提供下载按钮。

**示例路径**：`data/sessions/2026-02-16T15-30-10_a1b2c3d4.json`

## 结构

- `core/`: 内核（DecisionContext、BaseAgent、Engine、schemas）；BaseAgent 支持 Mock / Qwen，失败回退 Mock。
- `agents/`: idea_validator、market_analyzer、strategy_advisor、reflector。
- `app/web_app.py`: Streamlit 演示与 session 保存、下载、KPI 展示。
- `app/session_store.py`: 历史会话管理（v0.2）。
- `app/decision_metrics.py`: 决策指数计算（v0.3）。