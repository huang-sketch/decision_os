# AI Decision OS

A structured decision support system built on multi-agent architecture, designed for early-stage entrepreneurial scenarios. The system combines LLM-driven analysis with rule-based guardrails to produce explainable, actionable outputs.

## Project Vision

Decision-making under uncertainty is often degraded by cognitive bias, information overload, and emotional impulse. AI Decision OS explores a practical middle ground: use multi-agent orchestration for structured analysis, and layer deterministic guardrails on top to keep recommendations grounded and explainable.

This is a working prototype — not a production system. It demonstrates how agent collaboration, rule-based scoring, and behavioral calibration can be composed into a coherent decision pipeline.

## Capabilities

**Multi-Agent Analysis Pipeline**

Four specialized agents run in sequence — idea validation, market analysis, strategy advising, and reflective consistency checking. Each agent produces schema-constrained JSON output. A final reflection pass cross-checks inter-agent consistency.

**Decision Index (Rule-Based Scoring)**

A composite score (0–100) derived from four dimensions — feasibility, market, risk, and resource — using deterministic rules against agent outputs. No LLM is involved in scoring. Results are fully reproducible.

**Calmness Guardrail**

A lightweight behavioral questionnaire (4 questions, rule engine, no LLM call) quantifies the decision-maker's current cognitive state. When calmness is low, the system automatically downgrades action recommendations and injects specific counter-impulsivity prescriptions into the output.

Scoring formula: `final_index = base_score × 0.85 + calm_score × 0.15`

**Scenario Expansion**

From a single input, the system generates three variants — conservative, current, and aggressive — by adjusting seven dimensions (time, budget, validation window, output frequency, risk exposure, success criteria, constraint compliance). Results are compared side-by-side with overlaid radar charts.

**Structured Export**

JSON archive and Markdown report. No data is persisted server-side.

## Architecture

```
decision_os/
├── core/                       # Kernel (UI-independent)
│   ├── context.py              # DecisionContext — unified data container
│   ├── engine.py               # Sequential dispatch + reflection loop
│   ├── orchestrator.py         # Entry points: run_decision, run_decision_space_expand
│   ├── schemas.py              # JSON Schema definitions for agent outputs
│   ├── base_agent.py           # BaseAgent with pluggable LLM backend
│   └── variants.py             # Rule-based variant generation
│
├── agents/                     # Agent implementations
│   ├── idea_validator.py       # Idea clarity and completeness check
│   ├── market_analyzer.py      # Market size, trend, competition analysis
│   ├── strategy_advisor.py     # Strategy + risk + resource assessment
│   ├── reflector.py            # Cross-agent consistency verification
│   └── calm_evaluator.py       # Behavioral calmness scoring (rule engine)
│
├── app/                        # Streamlit frontend
│   ├── web_app.py              # Main application
│   ├── decision_metrics.py     # Scoring engine + chart generation
│   └── usage.py                # LLM usage estimation
│
└── .env.example                # Environment variable template
```

**Design Decisions**

- **LLM is pluggable.** Default mode uses mock responses (zero cost, offline). Configuring a DashScope API key switches to Qwen. Failures fall back to mock automatically.
- **Scoring is deterministic.** The decision index uses rule mappings over structured agent output — no LLM in the scoring path.
- **Calmness is independent.** The guardrail module is a pure rule engine with zero latency and no external calls.

## Getting Started

```bash
cd decision_os
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux
pip install -r requirements.txt
```

Optionally configure LLM access:

```bash
cp .env.example .env
# Edit .env:
#   LLM_PROVIDER=qwen
#   DASHSCOPE_API_KEY=<your key>
#   QWEN_MODEL=qwen-plus        (default)
```

Run:

```bash
streamlit run app/web_app.py
```

The application runs in mock mode by default — no API key required.

## Roadmap

- Additional LLM backends (OpenAI, Anthropic, local models)
- Multi-round decision tracking with delta comparison
- Team mode with multi-stakeholder input and divergence visualization
- Domain knowledge injection for vertical scenarios

## License

MIT
