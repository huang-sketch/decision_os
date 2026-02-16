# Decision Engine Core v0.1

多智能体决策引擎原型：4 Agent 闭环（创意验证 → 市场分析 → 策略建议 → 反思）。支持 **Mock**（默认）与 **通义千问（Qwen）**，Qwen 失败自动回退 Mock；每次运行结果会保存到 `data/sessions/`。

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

## 会话持久化

- 每次点击运行并得到结果后，会自动创建目录 `data/sessions`（若不存在），并将本次完整 ctx（含 stages 与 reflection）保存为 JSON。
- 文件名格式：`2026-02-16T15-30-10_<短id>.json`（Windows 兼容，无冒号）。
- 无论使用 Mock 还是 Qwen，都会保存；保存成功后页面会显示路径并提供下载按钮。

**示例路径**：`data/sessions/2026-02-16T15-30-10_a1b2c3d4.json`

## 结构

- `core/`: 内核（DecisionContext、BaseAgent、Engine、schemas）；BaseAgent 支持 Mock / Qwen，失败回退 Mock。
- `agents/`: idea_validator、market_analyzer、strategy_advisor、reflector。
- `app/web_app.py`: Streamlit 演示与 session 保存、下载。
