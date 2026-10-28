# 🔍 OmniGaze-Agent

> **Autonomous Spatial-Visual Infrastructure Inspector**
> *Cerebral Valley × Meta AI Developer Hackathon 2026*

OmniGaze-Agent pairs **zero-shot visual defect segmentation** (Meta SAM architecture) with **multimodal spatial reasoning** (Meta open-weight models — Muse Spark Open / Llama) to inspect physical infrastructure and trigger **closed-loop telemetry recovery actions**.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                  OmniGaze-Agent Pipeline                     │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────────┐  │
│  │   Ingest     │→ │   Segment    │→ │    Spatial        │  │
│  │  Telemetry   │  │   Defect     │  │   Reasoning       │  │
│  │  (sensors +  │  │  (SAM CV)    │  │  (Meta LLM)       │  │
│  │   visual)    │  │              │  │                    │  │
│  └──────────────┘  └──────────────┘  └────────┬──────────┘  │
│                                                │             │
│                         ┌──────────────────────▼──────────┐  │
│                         │      Dispatch Action            │  │
│                         │  (robotic mitigation)           │  │
│                         └──────────────┬─────────────────┘  │
│                                        │                     │
│                         ┌──────────────▼──────────────────┐  │
│                         │     Verify Recovery             │  │
│                         │  (post-action telemetry check)  │──┤→ retry?
│                         └─────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

## Quick Start

```bash
# 1. Clone & enter
git clone <repo-url> && cd omnigaze-agent

# 2. Create venv & install
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS / Linux
pip install -r requirements.txt

# 3. (Optional) Configure API keys
cp .env.example .env
# Edit .env with your Baseten / HuggingFace keys

# 4. Run the full pipeline
python main.py
```

## Project Structure

```
omnigaze-agent/
├── .env.example                   # Environment config template
├── README.md
├── requirements.txt
├── main.py                        # CLI entry point
├── core/
│   ├── __init__.py
│   ├── agent_graph.py             # LangGraph state machine (5 nodes)
│   ├── llm_client.py              # Meta LLM client (OpenAI-compatible)
│   └── vision_sam.py              # SAM segmentation module
└── mock_telemetry/
    ├── generate_synthetic_data.py  # Synthetic image + telemetry generator
    └── telemetry_log.json          # Generated telemetry payload
```

## Key Features

- **Zero-shot defect detection** — Classical CV pipeline (Canny edges + HSV thresholding) simulates SAM promptable segmentation, ready to swap in a real SAM endpoint.
- **Meta LLM spatial reasoning** — Pluggable client works with any OpenAI-compatible endpoint (Baseten, HuggingFace TGI, vLLM, Ollama). Falls back to deterministic mock for offline demos.
- **Closed-loop recovery** — The agent dispatches simulated robotic actions (valve adjustments, emergency lockdowns, drone repositioning) and re-checks telemetry for stability.
- **LangGraph state machine** — Type-safe Pydantic state with conditional retry edges for autonomous decision loops.
- **Fully offline-capable** — Runs end-to-end without any API keys using synthetic data and mock responses.

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Agent Orchestration | LangGraph + LangChain Core |
| Vision | OpenCV + Pillow (SAM-ready) |
| LLM | Meta Muse Spark Open / Llama (OpenAI-compatible) |
| State Management | Pydantic v2 |
| Config | python-dotenv |

## License

MIT — Built for the Cerebral Valley × Meta AI Hackathon.
