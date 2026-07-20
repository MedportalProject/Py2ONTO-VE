# Py2ONTO Visual Editor

A web-based visual ontology editor for building OWL ontologies from CSV templates and natural language descriptions. Powered by [owlready2](https://github.com/pypa/owlready2) with AI-assisted extraction from multiple LLM providers.

## Features

- **Visual ontology tree** — real-time preview of class hierarchy, object properties, and annotation properties
- **CSV-driven editing** — import/export ontology elements as CSV tables (classes, object properties, annotation properties, individuals)
- **AI-assisted extraction** — describe your domain in natural language and have an LLM extract structured ontology elements
- **Multi-provider LLM support** — DeepSeek, ChatGLM (ZhipuAI), Google Gemini, Anthropic Claude, and Ollama (local)
- **Ontology term search** — search EBI OLS and BioPortal for standard ontology terms and incorporate them into your ontology
- **OWL generation** — save compliant RDF/XML OWL files with companion metadata reports

## Quick Start

### 1. Clone and install dependencies

```bash
git clone <repo-url>
cd py2onto-oss

# Create a virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# Install Python dependencies
pip install -r requirements.txt
```

### 2. Configure API keys

Copy the example config and fill in your keys:

```bash
cp config.example.json config.json
```

Edit `config.json` and set the API keys for the services you plan to use. See [Configuration](#configuration) below for details on each key.

### 3. Launch the web editor

```bash
python app.py
```

Open http://127.0.0.1:5001 in your browser.

## Configuration

All settings live in `config.json` (created from `config.example.json`). The application also supports environment variables as fallbacks for API keys.

### LLM providers (for AI-assisted extraction)

Choose one provider by setting `llm.provider`, then fill in its API key:

| Provider | Config path | Environment variable | Sign-up URL |
|---|---|---|---|
| DeepSeek | `llm.deepseek.api_key` | `DEEPSEEK_API_KEY` | https://platform.deepseek.com |
| ChatGLM (ZhipuAI) | `llm.chatglm.api_key` | `CHATGLM_API_KEY` | https://open.bigmodel.cn |
| Google Gemini | `llm.gemini.api_key` | `GEMINI_API_KEY` | https://aistudio.google.com/apikey |
| Anthropic Claude | `llm.anthropic.api_key` | `ANTHROPIC_API_KEY` | https://console.anthropic.com |
| Ollama (local) | `llm.ollama.api_key` | `OLLAMA_API_KEY` | Install locally: https://ollama.com |

Example `config.json` for DeepSeek:

```json
{
  "llm": {
    "provider": "deepseek",
    "deepseek": {
      "api_key": "sk-your-deepseek-api-key",
      "model": "deepseek-chat",
      "base_url": "https://api.deepseek.com/v1"
    }
  }
}
```

### Ontology portal APIs (for term search)

| Portal | Config path | Environment variable | Sign-up URL |
|---|---|---|---|
| BioPortal | `bioportal.api_key` | `BIOPORTAL_API_KEY` | https://bioportal.bioontology.org/account |
| MedPortal | `medportal.api_key` | `MEDPORTAL_API_KEY` | Internal service |

OLS (EBI Ontology Lookup Service) is also available and requires **no API key**.

### System and task prompts

- `system_prompt` — an optional custom system prompt that overrides the built-in extraction rules. Leave empty to use the default.
- `task_prompt` — per-extraction instructions appended to the system prompt (e.g., naming conventions, scope limits).

## Project Structure

```
├── app.py                  # Flask web application (backend routes)
├── py2onto.py              # Core ontology builder (Py2ONTO class)
├── onto_extractor.py       # LLM-powered ontology extraction
├── config.py               # Configuration loader (reads config.json + env vars)
├── config.example.json     # Example configuration template
├── requirements.txt        # Python dependencies
├── templates/
│   └── index.html         # Web UI
├── static/
│   ├── css/style.css      # Styles
│   └── js/app.js          # Frontend logic
├── ibd_example/             # IBD ontology example (CSV + prompt)
├── MANUAL_en.md            # English user manual
├── MANUAL_zh.md            # Chinese user manual
└── APPLICATION_NOTE_*.md   # Application notes (academic)
```

## Example: Inflammatory Bowel Disease (IBD) Ontology

The `ibd_example/` folder contains a complete example ontology for Inflammatory Bowel Disease and its management:

- 29 classes across IBD subtypes, symptoms, disease phases, complications, mental health, medications, and treatments
- 8 object properties with characteristics (affects, hasSymptom, hasPhase, leadsTo, etc.)
- Class-level relationships via $-prefixed columns (e.g., `$hasSymptom`, `$isSymptomOf`, `$isGIComplicationOf`)

You can load it via CSV upload or paste the `ai_assist_prompt.txt` into the AI Assist tab.

## License

[Choose a license — e.g., MIT, Apache 2.0, GPLv3]

## Authors

- **WANG Zhe** — py2onto@outlook.com

## Citation

If you use Py2ONTO in academic work, please cite the project. See `APPLICATION_NOTE_en.md` for details.
