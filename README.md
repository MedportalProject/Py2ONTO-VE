  <img width="1921" height="819" alt="Py2ONTO-VE logo" src="https://github.com/user-attachments/assets/d4043142-b75c-4ae9-bc8e-2fdc9f0ec4cb" />
  
# Py2ONTO-VE
 A web-based ontology editor supporting manual table editing, CSV import/export, and AI-powered natural language extraction with human-in-the-loop validation, enabling domain experts to review, refine, and approve ontology elements before generating standard OWL format files.
 
 <h1 align="center">
  <a href="">
    <img src="https://img.shields.io/badge/releases-v1.0-red" />
  </a>
  <a href="">
    <img src="https://img.shields.io/badge/docs-v1.0-yellow" />
  </a>
  <a href="">
    <img src="https://img.shields.io/badge/Ontology-Construction-blue" />
  </a>
  <a href="">
    <img src="https://img.shields.io/badge/LICENSE-LGPL 3-brightgreen" />
  </a>
  <a href="">
    <img src="https://img.shields.io/badge/Python-snow?logo=python&logoColor=3776AB" alt="" />
  </a>
   <a href="">
     <img src="https://img.shields.io/badge/required-Flask&Owlready2-orange" alt="" />
   </a>
</h1>

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Interface Overview](#interface-overview)
3. [Editing the Ontology](#editing-the-ontology)
   - [Classes](#classes)
   - [Annotation Properties](#annotation-properties)
   - [Object Properties](#object-properties)
   - [Individuals](#individuals)
   - [Custom Columns](#custom-columns)
4. [Build & Preview](#build--preview)
5. [Generate & Download OWL](#generate--download-owl)
6. [CSV Import & Export](#csv-import--export)
   - [Download CSV Templates](#download-csv-templates)
   - [Upload CSV Files](#upload-csv-files)
7. [Ontology Class Search (OLS & BioPortal)](#ontology-class-search-ols--bioportal)
8. [AI-Assisted Extraction](#ai-assisted-extraction)
   - [Configure API Keys](#configure-api-keys)
   - [Using AI Extraction](#using-ai-extraction)
   - [Ontology Term Mapping](#ontology-term-mapping)
   - [Custom System Prompt](#custom-system-prompt)
   - [Custom Task Prompt](#custom-task-prompt)
   - [Supported LLM Providers](#supported-llm-providers)
9. [Ontology Tree Visualization](#ontology-tree-visualization)
10. [Configuration File Reference](#configuration-file-reference)
11. [Output File Formats](#output-file-formats)
12. [IBD Example](#ibd-example)
13. [Ollama Local Deployment](#ollama-local-deployment)
14. [FAQ](#faq)

---

## Quick Start

> **Prerequisite**: Python 3.10 or later.

### 1. Install Dependencies

```bash
cd py2onto-ve-oss
pip install -r requirements.txt
```

### 2. Configure API Keys (optional, for AI extraction only)

Edit `config.json` and fill in the API key for your chosen LLM provider.

### 3. Launch the Server

```bash
python app.py
```

The server starts at `http://127.0.0.1:5001`. Open this URL in your browser.

---

## Interface Overview

The interface is divided into three main areas:

```
┌──────────────────────────────────────────────────────────────────┐
│  Toolbar: [IRI input]  [Build] [Generate OWL] [Clear]            │
├───────────────────────────┬──────────────────────────────────────┤
│  Left Panel (6 tabs)      │  Right Panel (tree view)              │
│  ┌──────────────────────┐ │  ┌──────────────────────────────────┐│
│  │ Classes              │ │  │   Thing [root]                   ││
│  │ Annotation Props     │ │  │   ├── Disease                    ││
│  │ Object Props         │ │  │   │   ├── Hypertension           ││
│  │ Individuals          │ │  │   │   └── CAD                    ││
│  │ Ontology Class Search│ │  │   └── Drug                       ││
│  │ AI Assist            │ │  │       ├── Aspirin                ││
│  └──────────────────────┘ │  │       └── ◆ aspirin_01           ││
│                           │  └──────────────────────────────────┘│
└───────────────────────────┴──────────────────────────────────────┘
```

- **Toolbar**: Set the ontology IRI, trigger a build preview, generate and download the OWL file, or clear all data.
- **Left Panel**: 6 tabs for editing Classes, Annotation Properties, Object Properties, Individuals, searching ontology terms from OLS and BioPortal, and AI-assisted extraction (supporting DeepSeek, ChatGLM, Gemini, and Ollama).
- **Right Panel**: Hierarchical ontology tree. Clicking a node navigates to the corresponding table row.

---

## Editing the Ontology

### Classes

The Classes table contains the following columns:

| Column | Description | Example |
|--------|-------------|---------|
| `Parent_Class` | Superclass ID; use `Thing` for top-level classes | `Disease` |
| `ID` | Unique class identifier (CamelCase recommended) | `CardiovascularDisease` |
| `label` | Human-readable label | `Cardiovascular Disease` |
| `IRI` | Full IRI of the class. Auto-generated from the base IRI + ID when you type an ID; read-only (not manually editable). | `http://example.org/onto.owl#CardiovascularDisease` |
| `comment` | Descriptive annotation | `A disease affecting the heart or blood vessels` |
| `definition` | Formal definition text | (optional) |

**IRI Auto-generation**: The `IRI` field is read-only — it is automatically generated as `<base ontology IRI><ID>`. When you edit the `ID` field or change the base IRI in the toolbar, all local class IRIs are automatically synced. Externally-sourced classes (from OLS/BioPortal) retain their canonical IRIs and are unaffected by base IRI changes.

**Source Badges**: Classes can display a source badge next to their label:
- `local` (default, no badge shown) — defined locally in this ontology.
- `OLS` (orange badge) — imported from the Ontology Lookup Service (see [Ontology Class Search](#ontology-class-search-ols--bioportal)).
- `BioPortal` (green badge) — imported from BioPortal.
- Other source identifiers may appear for externally sourced classes.

**Actions**:
- **+ Row**: Append an empty row.
- **− Row**: Delete all checked rows (select via the checkbox column).
- Edit values directly in the table cells.

**Class Name Suggestions**: When editing `Parent_Class`, `Types` (in Individuals), or `domain`/`range` (in properties), an autocomplete dropdown suggests existing class IDs (`Thing` is always available). The suggestion list updates automatically as classes are added or removed.

### Annotation Properties

Define metadata properties that attach descriptive information to ontology entities, such as `hasDbXref`, `definition`, or `hasSynonym`. Unlike object properties, annotation properties do not participate in OWL DL reasoning — their `domain` and `range` serve as documentation only.

| Column | Description |
|--------|-------------|
| `ID` | Property identifier (lowercase_with_underscores or camelCase) |
| `label` | Human-readable label |
| `comment` | Descriptive annotation |
| `domain` | Class(es) this annotation is intended for; join multiple classes with `&` |
| `range` | Expected value type(s); join multiple with `&` |
| `definition` | Formal definition (optional) |

### Object Properties

Define relationships between classes, such as `treats`, `causes`, or `hasPart`.

| Column | Description |
|--------|-------------|
| `ID` | Property identifier |
| `label` | Human-readable label |
| `comment` | Descriptive annotation |
| `FunctionalProperty` – `IrreflexiveProperty` | Property characteristics; set to `True` to enable |
| `equivalent_to` | Equivalent property |
| `subproperty_of` | Parent property |
| `inverse_of` | Inverse property |
| `domain` | Domain class(es) — the subject; join multiple with `&` |
| `range` | Range class(es) — the object; join multiple with `&` |
| `disjoint_with` | Disjoint property |
| `definition` | Formal definition (optional) |

**Characteristic Reference**:

| Characteristic | Meaning |
|---------------|---------|
| `FunctionalProperty` | Functional |
| `InverseFunctionalProperty` | Inverse functional |
| `TransitiveProperty` | Transitive |
| `SymmetricProperty` | Symmetric |
| `AsymmetricProperty` | Asymmetric |
| `ReflexiveProperty` | Reflexive |
| `IrreflexiveProperty` | Irreflexive |

### Individuals

Define specific instances (individuals) of classes.

| Column | Description |
|--------|-------------|
| `Types` | ID of the class this individual instantiates |
| `relation` | Always `has_individual` (the literal required string) |
| `ID` | Unique instance identifier |
| `label` | Human-readable label |
| `comment` | Descriptive annotation |
| `definition` | Formal definition (optional) |

### Custom Columns

Click **+ Col** to add custom columns to any table. Column name conventions:

- Names prefixed with `*` are treated as **annotation property** values (e.g. `*hasSynonym`).
- Names prefixed with `$` are treated as **object property** relationships, following the pattern `$<property>.<rangeClass>` (e.g. `$treats.Disease`).

Click **− Col** to remove a custom column. You will be prompted to type the exact column name.

---

## Build & Preview

Click the **Build** button in the toolbar to:
- Construct the ontology from the current table data.
- Display the ontology hierarchy tree in the right panel.
- This operation does **not** save any file.

> **Tip**: You can click Build even when all tables are empty — it will produce a tree with only the `Thing` root node.

---

## Generate & Download OWL

Click the **Generate OWL** button to:

1. A dialog prompts for the output filename (default: `new_onto.owl`).
2. The backend builds the ontology and saves it as an RDF/XML `.owl` file.
3. A companion `.txt` **metadata report** is generated alongside the OWL file (same base name, same directory).
4. The browser automatically triggers two file downloads — the `.owl` file and the `.txt` report.
5. An elapsed-time counter is shown on the button and stats label during generation.

**The metadata report includes**:
- Ontology IRI, generation timestamp, output file path
- Statistics (class count, individual count, object/annotation property counts)
- ASCII-formatted class hierarchy tree
- Detailed object property information with characteristics
- Annotation property listing
- Software environment (Python version, Py2ONTO version, owlready2 version)

---

## CSV Import & Export

### Download CSV Templates

Each table tab has a **Download** button:
- Exports the current table as a CSV file.
- File name format: `<tableId>_template.csv` (e.g. `classes_template.csv`).
- When the table is empty, it still downloads a **header-only template** — ideal for offline editing.

### Upload CSV Files

Each table tab has an **Upload** button:
- Select a CSV file to import.
- The first row **must** be the header row (matching the downloaded template format).
- Imported data **replaces** the current table content.
- Custom columns present in the CSV header but not in the built-in columns are automatically added as extra columns.

**Example CSV format** (classes):

```csv
Parent_Class,ID,label,IRI,comment,definition
Thing,Disease,Disease,http://example.org/onto.owl#Disease,A pathological condition of a living organism,
Disease,Hypertension,Hypertension,http://example.org/onto.owl#Hypertension,Persistently elevated blood pressure,
```

---

## Ontology Class Search (OLS & BioPortal)

The **Ontology Class Search** tab provides a built-in interface to search both the [EBI Ontology Lookup Service (OLS)](https://www.ebi.ac.uk/ols) and [BioPortal](https://bioportal.bioontology.org/) for standard ontology terms.

### Source Selection

At the top of the search tab, use the radio buttons to toggle between search sources:

- **OLS (EBI)** (default): Searches the EBI Ontology Lookup Service, covering the full OBO Foundry collection (>200 ontologies) including GO, DO, HPO, EFO, and more.
- **BioPortal**: Searches the BioPortal ontology repository (>900 ontologies) including SNOMED CT, NCIt, MedDRA, and more. Requires an API key configured in `config.json` (see [Configuration File Reference](#configuration-file-reference)).

Next to the source toggle, an **ontology filter** input allows you to restrict searches to a specific ontology:
- For OLS: enter a single ontology prefix (e.g. `efo`, `go`, `hp`, `doid`).
- For BioPortal: enter one or more ontology acronyms, comma-separated (e.g. `SNOMEDCT,NCIT`).

### Searching

1. Switch to the **Ontology Class Search** tab.
2. Type a search query (e.g. `lung cancer`, `diabetes`, `hypertension`) — minimum 2 characters.
3. Press **Enter** or click **Search**.
4. Results appear in a table with columns: Select, ID, Label, IRI, Ontology (source ontology name).

### Inserting a Class

1. Select a result by clicking its radio button.
2. Click **Insert Selected Class**.
3. The class is added to the Classes table with:
   - `ID`, `label`, and `IRI` pre-filled from the search result.
   - An orange `OLS` or `BioPortal` badge next to the label indicating the external source.
   - IRI uses the external ontology's canonical IRI (read-only, unaffected by base IRI changes).
4. Duplicate checking prevents inserting a class with an ID or IRI that already exists in the table.

### Clearing the Search

Click **Clear** to reset the search input, results, and status.

---

## AI-Assisted Extraction

The **AI Assist** tab lets you describe domain knowledge in natural language and have an LLM automatically extract ontology elements (classes, annotation properties, object properties, and individuals).

### Configure API Keys

Edit `config.json` in the project root and fill in your API key(s) under the `llm` section:

```json
{
  "llm": {
    "deepseek": {
      "api_key": "sk-your-deepseek-key",
      "model": "deepseek-chat",
      "base_url": "https://api.deepseek.com/v1"
    }
  }
}
```

Alternatively, use environment variables (no config file changes needed):

| Provider | Environment Variable |
|----------|---------------------|
| DeepSeek | `DEEPSEEK_API_KEY` |
| ChatGLM | `CHATGLM_API_KEY` |
| Gemini | `GEMINI_API_KEY` |

### Using AI Extraction

1. Switch to the **AI Assist** tab.
2. Select a **Provider** (LLM service) and **Model**. The model dropdown updates dynamically based on the selected provider.
3. Describe your domain in natural language in the text area. A placeholder example (cardiovascular pharmacology) is shown in the textarea. You can also click **Clear text** to reset the input area.

   > 💡 **Tip:** You can customize how the AI extracts your ontology by editing the **System prompt** (extraction rules, JSON schema, output format) and **Task prompt** (domain scope, naming conventions, per-task constraints) using the buttons above the textarea.

4. Choose a **Population mode**:
   - **Merge** (default): Append extracted results to existing data. Duplicate IDs (those already present in the table) are automatically skipped.
   - **Replace**: Clear existing data before populating with extracted results.
5. Click **Extract Ontology**.
6. Review the extraction summary. Any warnings appear in a yellow info box.
7. Click **Populate Tables** to fill the results into the editor tables. The view automatically switches to the Classes tab.
8. Optionally, click **Map to Ontology Terms** to align extracted classes with standard ontology terms from OLS or BioPortal (see [Ontology Term Mapping](#ontology-term-mapping)).

> **Note**: Click **Clear text** to reset the input area. The **Dismiss** button hides the result panel without clearing the extracted data cache — you can still populate tables until the next extraction.

### Ontology Term Mapping

After a successful AI extraction that includes classes, a **Map to Ontology Terms** button appears. This feature lets you align the extracted classes with standard ontology terms from OLS (EBI) and BioPortal.

1. Click **Map to Ontology Terms** to open the Ontology Term Mapping modal.
2. At the top of the modal, select a search source: **OLS (EBI)**, **BioPortal**, or **All Sources**. You can optionally specify an ontology filter for each source.
3. Click **Begin Search** to search each extracted class label against the selected knowledge portal(s).
4. The modal has two panels:
   - **Left panel**: Lists all extracted classes. Each class shows a badge (`pending` → `local` or `OLS` / `BioPortal`).
   - **Right panel**: Shows candidates for the selected class, including a **Keep Local** option (default) and search results from the selected source.
5. Click a class on the left to view its candidates.
6. For each class, choose:
   - **Keep Local** — keeps the class as-is with the AI-generated ID, label, and IRI.
   - A **candidate term** — replaces the class ID, label, and IRI with the standard ontology term. The class gets an `OLS` or `BioPortal` source badge.
7. The badge on the left updates to reflect your choice (`local`, `OLS`, or `BioPortal`).
8. When all classes are reviewed, click **Insert Selected Classes**.
9. Classes are added to the Classes table. Parent-child relationships are automatically remapped when a replacement changes a class ID.
10. Duplicate classes (already existing in the table) are skipped with a notification.

### Custom System Prompt

Click **✎ Edit Prompt** to open the prompt editor modal:
- View and edit the full system prompt sent to the LLM.
- **↺ Reset to Default**: Restore the built-in default prompt (after confirmation).
- **Save & Close**: Persist the edited prompt to `config.json` for future sessions.
- The current prompt status is shown in the modal footer ("Built-in default loaded" or "Custom prompt loaded").
- The custom prompt is also sent with each extraction request (if the editor has been modified without saving).

### Custom Task Prompt

Click **✎ Task prompt** (next to the System prompt button above the input textarea) to open the task prompt editor modal:

- The **task prompt** is a set of per-extraction instructions appended to the system prompt. Use it to constrain the scope of a specific extraction — for example, setting top-level classes, limiting hierarchy depth, or providing naming conventions for this particular domain description.
- The editor modal allows you to view, edit, save, or clear the task prompt.
- **Save & Close**: Persist the edited task prompt to `config.json` for future sessions.
- **Clear**: Remove the task prompt so no extra instructions are appended to the next extraction.
- Unlike the system prompt (which defines the general extraction rules and JSON schema), the task prompt is meant to be task-specific — you can change it for each extraction depending on the domain you are modelling.

> 💡 **Tip:** A reminder is shown below the input textarea in the AI Assist tab, with clickable links to open both the System prompt and Task prompt editors — so you can quickly adjust extraction behaviour before each run.

### Supported LLM Providers

| Provider | Available Models | API Type |
|----------|-----------------|----------|
| **DeepSeek** | `deepseek-chat` (DeepSeek-V3), `deepseek-reasoner` (DeepSeek-R1) | OpenAI-compatible |
| **ChatGLM (ZhipuAI)** | `glm-4-flash` (fast), `glm-4`, `glm-4-plus` (most capable) | OpenAI-compatible |
| **Gemini (Google)** | `gemini-2.5-flash` (recommended), `gemini-2.5-pro` (complex ontologies) | Google Generative AI SDK |
| **Ollama (Local)** | Any locally pulled model (e.g. `llama3`, `mistral`, `qwen2.5`) — models are auto-detected from the Ollama server | OpenAI-compatible (localhost:11434) |

> **Note**: For Ollama, make sure `ollama serve` is running locally — available models are automatically listed in the model dropdown.

---

## Ontology Tree Visualization

The right panel displays the constructed ontology hierarchy:

- **Class hierarchy**: An expandable/collapsible tree with `Thing` as the root.
  - `●` Class node: click to jump to the corresponding row in the Classes table.
  - `◆` Individual node: click to jump to the corresponding row in the Individuals table.
  - `[OLS]` badge: shown inline for classes sourced from OLS or other external ontologies.
- **Object Properties**: Marked with `↦`, showing domain and range.
- **Annotation Properties**: Marked with `@`.
- **Stats bar** at the top: class count · individual count · object property count · annotation property count.

---

## Configuration File Reference

Structure of `config.json`:

```json
{
  "medportal": {
    "url": "http://medportal.bmicc.cn:8080",
    "api_key": ""
  },
  "bioportal": {
    "url": "http://data.bioontology.org",
    "api_key": ""
  },
  "system_prompt": "",
  "task_prompt": "",
  "llm": {
    "provider": "deepseek",
    "deepseek": { "api_key": "", "model": "deepseek-chat", "base_url": "https://api.deepseek.com/v1" },
    "chatglm":  { "api_key": "", "model": "glm-4-flash", "base_url": "https://open.bigmodel.cn/api/paas/v4" },
    "gemini":   { "api_key": "", "model": "gemini-2.5-flash" },
    "ollama":   { "api_key": "", "model": "", "base_url": "http://localhost:11434/v1" }
  }
}
```

- `medportal` / `bioportal`: Configuration for MedPortal / BioPortal ontology services (used by the py2onto core engine and the Ontology Class Search tab for external term lookups).
- `system_prompt`: Custom LLM system prompt (edited via AI Assist → ✎ System prompt).
- `task_prompt`: Custom per-extraction task instructions (edited via AI Assist → ✎ Task prompt).
- `llm.provider`: Default LLM provider identifier.
- `llm.<provider>`: API key, model, and base URL (if applicable) for each LLM provider.
- `llm.ollama`: No API key is required — use a dummy value (e.g. `"ollama"`). The `base_url` defaults to `http://localhost:11434/v1`. The model dropdown auto-detects locally available models.

---

## Output File Formats

### OWL File (`.owl`)

The generated `.owl` file uses **RDF/XML** format conforming to the OWL 2 standard. It can be opened in:

- [Protégé](https://protege.stanford.edu/)
- [WebProtégé](https://webprotege.stanford.edu/)
- Any OWL-compatible ontology editor or reasoner.

### Metadata Report (`.txt`)

A plain-text companion report containing:

```
======================================================================
  ONTOLOGY GENERATION REPORT
======================================================================

  Ontology IRI          http://example.com/onto.owl#
  Generated by          Py2ONTO Visual Editor
  Generation time       2026-06-14 10:30:00 CST (UTC+0800)
  Output file           my_onto.owl

======================================================================
  STATISTICS
======================================================================

  Classes                6
  Individuals            1
  Object Properties      1
  Annotation Properties  2

======================================================================
  CLASS HIERARCHY
======================================================================

Thing [root]
├── Disease
│   ├── Hypertension
│   └── CoronaryArteryDisease
└── Drug
    ├── BetaBlocker
    │   └── ◆ Atenolol 50mg
    └── ACEInhibitor

======================================================================
  OBJECT PROPERTIES
======================================================================

  [treats]
    Domain        Drug
    Range         Disease

======================================================================
  METADATA
======================================================================

  Generator             Py2ONTO
  Powered by            owlready2 0.47
  Python                3.12.0
======================================================================
```

---

## IBD Example

A complete worked example — an **Inflammatory Bowel Disease (IBD) Ontology** — is included in the `ibd_example/` directory. It models IBD subtypes, symptoms, disease phases, complications (both GI and extraintestinal), mental health impacts, medications, and treatments. You can use it to learn the tool's workflow or as a starting template for your own ontology project.

### Ontology Design

**37 classes** across eight top-level branches (including 1 external reference class `disease`/MONDO):

```
Thing
├── Symptom
│   ├── Diarrhea
│   ├── StomachPain
│   ├── Fatigue
│   ├── Nausea
│   └── WeightLoss
├── DiseasePhase
│   ├── Remission
│   └── FlareUp
├── Complication
│   ├── GastrointestinalComplication
│   │   ├── Dehydration
│   │   ├── Malabsorption
│   │   └── IncreasedCancerRisk
│   └── ExtraintestinalManifestation
│       ├── Anemia
│       ├── ReducedBoneDensity
│       ├── JointPain
│       ├── SkinChanges
│       ├── EyeIrritation
│       └── DelayedGrowth
├── MentalHealthChallenge
│   ├── Depression
│   ├── Anxiety
│   ├── Distress
│   └── OtherMentalDisorder
├── Medication
│   ├── Aminosalicylate
│   ├── Corticosteroid
│   ├── Immunomodulator
│   └── Biologic
├── Treatment
│   └── Surgery
└── disease (external ref: MONDO)
    └── InflammatoryBowelDisease
        ├── UlcerativeColitis
        └── CrohnsDisease
```

**8 object properties** covering disease-symptom, disease-phase, disease-complication, and disease-treatment relationships:

| Property | Domain | Range | Features |
|---|---|---|---|
| `affects` | InflammatoryBowelDisease | Thing | — |
| `hasSymptom` | InflammatoryBowelDisease | Symptom | — |
| `hasPhase` | InflammatoryBowelDisease | DiseasePhase | — |
| `leadsTo` | InflammatoryBowelDisease | Complication | — |
| `increasesRiskOf` | InflammatoryBowelDisease | MentalHealthChallenge | — |
| `treatedBy` | InflammatoryBowelDisease | Thing | — |
| `isSymptomOf` | (inferred) | (inferred) | `inverse_of: hasSymptom` |
| `isGIComplicationOf` | (inferred) | (inferred) | — |

### Files

| File | Description |
|------|-------------|
| `ibd_example/README.md` | Full example documentation |
| `ibd_example/classes.csv` | 37 class definitions |
| `ibd_example/object_properties.csv` | 8 object property definitions |
| `ibd_example/ai_assist_prompt.txt` | Natural-language prompt for AI extraction |
| `ibd_example/task_prompt.txt` | Task-specific instructions for AI extraction |
| `ibd_example/IBD_py2ontove.owl` | Pre-built OWL ontology (ready for Protégé) |
| `ibd_example/IBD_py2ontove.txt` | Auto-generated metadata report |

### Ways to Use the Example

**Method A — CSV Upload** (deterministic):

1. Open the editor and set the IRI to `http://bmicc.cn/IBD_py2ontove.owl#`
2. On each tab, click **Upload** and select the corresponding CSV file — import in order: OPs → Classes
3. Click **Build** → inspect the tree → click **Generate OWL**

**Method B — AI Assist** (natural language, demonstrates LLM extraction):

1. Switch to the **AI Assist** tab and select your LLM provider
2. Copy the entire content of `ibd_example/ai_assist_prompt.txt` into the text area
3. Click **Extract Ontology** → review warnings → click **Populate Tables**
4. Click **Build** to verify the hierarchy matches the CSV-import version

**Method C — AI Assist with Task Prompt** (guided extraction):

1. Copy `ibd_example/ai_assist_prompt.txt` into the AI input area
2. Click **Task prompt** and paste the content of `ibd_example/task_prompt.txt`
3. Select your LLM provider and click **Extract Ontology** — the task prompt guides the LLM to follow IBD-specific conventions

**Method D — Command Line** (programmatic use):

```bash
python -c "
from py2onto import Py2ONTO
onto = Py2ONTO('http://bmicc.cn/IBD_py2ontove.owl#')
onto._create_object_property_by_template('ibd_example/object_properties.csv')
onto.init('ibd_example/classes.csv')
onto.save('./ibd_ontology.owl')
"
```

These methods produce the same ontology.

---

## Ollama Local Deployment

[Ollama](https://ollama.com) allows you to run LLMs entirely on your local machine — no cloud API keys or internet access required. Py2ONTO supports Ollama as a first-class AI extraction provider.

### 1. Install Ollama

**Linux / WSL:**

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

**macOS:** Download from [ollama.com](https://ollama.com) or use `brew install ollama`.

**Windows:** Download the installer from [ollama.com](https://ollama.com).

### 2. Start the Ollama Server

```bash
ollama serve
```

The server listens at `http://localhost:11434`. Keep this terminal running.

### 3. Pull a Model

Choose a model suitable for structured JSON extraction. Recommended models:

```bash
# General-purpose (good balance of speed and quality)
ollama pull llama3.1:8b          # ~4.7 GB
ollama pull qwen2.5:14b          # ~8.5 GB

# Larger models (better quality, require more RAM)
ollama pull qwen2.5:32b          # ~19 GB
ollama pull llama3.1:70b         # ~40 GB

# Smaller models (faster, lower quality)
ollama pull qwen2.5:7b           # ~4.4 GB
ollama pull mistral:7b           # ~4.1 GB
```

Verify available models:

```bash
ollama list
```

### 4. Configure Py2ONTO for Ollama

Edit `config.json`:

```json
{
  "llm": {
    "provider": "ollama",
    "ollama": {
      "api_key": "",
      "model": "qwen2.5:14b",
      "base_url": "http://localhost:11434/v1"
    }
  }
}
```

- `api_key`: Not needed for local Ollama — the application uses a dummy value automatically. Leave empty.
- `model`: Any model you have pulled (e.g. `llama3.1:8b`, `qwen2.5:14b`, `mistral:7b`).
- `base_url`: Default is `http://localhost:11434/v1`. Change only if Ollama runs on a different host or port.

> **Note**: You can also set `OLLAMA_API_KEY` as an environment variable (optional — not required for local Ollama).

### 5. Use Ollama in the Editor

1. Start the editor: `python app.py`
2. Switch to the **AI Assist** tab
3. Select **Ollama (Local)** from the Provider dropdown
4. The Model dropdown automatically detects models available on your Ollama server (requires `ollama serve` to be running)
5. If the dropdown is empty or shows an error, check that:
   - `ollama serve` is running (`curl http://localhost:11434/api/tags` should return JSON)
   - The model has been pulled (`ollama list`)

### 6. Hardware Requirements

| Model Size | Minimum RAM | Recommended RAM |
|------------|-------------|-----------------|
| 7B–8B | 8 GB | 16 GB |
| 14B | 16 GB | 32 GB |
| 32B–70B | 32 GB | 64 GB+ |

- A GPU is **not required** but significantly improves speed. Ollama automatically uses NVIDIA/CUDA, AMD/ROCm, or Apple Metal if available.
- CPU-only inference works for 7B–14B models but is slower for extraction tasks (expect 30–120 seconds per extraction).

### 7. Troubleshooting

| Problem | Solution |
|---------|----------|
| "Cannot connect to Ollama" | Run `ollama serve` in another terminal |
| Model not appearing in dropdown | Run `ollama pull <model>` then refresh |
| Extraction returns malformed JSON | Try a larger/higher-quality model (e.g. `qwen2.5:14b` instead of `qwen2.5:7b`) |
| Out of memory | Use a smaller model or add RAM/swap space |
| Ollama slow on CPU | Reduce model size; 7B–8B models are usable on CPU |

---

### Q: Can I generate an OWL file without any data?

Yes. Clicking **Generate OWL** with empty tables produces a minimal (empty) ontology file containing only the IRI. This can serve as a starting template.

### Q: How do I edit data offline?

Click the **Download** button on any tab to export a CSV template. Edit it in Excel or any spreadsheet tool, then import it back using the **Upload** button.

### Q: What if AI extraction fails?

1. Verify the API key in `config.json` is correct.
2. Check that your network can reach the LLM provider's API endpoint.
3. Try providing a more detailed natural language description.
4. Review the yellow warning box for specific errors (e.g. JSON parse failures).
5. Try a different LLM provider.

### Q: How do I specify multiple domains/ranges?

Use `&` to join multiple class IDs in the `domain` or `range` field. For example: `Drug&Device`.

### Q: Where are the generated files saved?

Files are saved to the project root directory (the `save_path` parameter). The browser also automatically triggers a download of both the `.owl` and `.txt` files.

### Q: What Python versions are supported?

Python 3.10 or later.

### Q: How do I use standard ontology terms from external sources?

Use the **Ontology Class Search** tab to search the EBI Ontology Lookup Service (OLS) or BioPortal. Select and insert matching terms — they appear in the Classes table with an `OLS` or `BioPortal` badge. Alternatively, after AI extraction, use the **Map to Ontology Terms** feature to match extracted classes against standard terms from OLS and BioPortal.

### Q: How does the IRI auto-generation work?

The `IRI` field is read-only — it is automatically generated as `<base ontology IRI><ID>`. When you edit the `ID` field or change the base IRI in the toolbar, all local class IRIs are automatically synced. OLS/BioPortal-inserted classes retain their canonical IRIs and are unaffected by base IRI changes.

### Q: What happens to duplicate IDs when merging AI-extracted data?

In **Merge** mode, the `Populate Tables` function automatically skips rows whose `ID` already exists in the target table. A toast notification shows how many duplicates were skipped.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend framework | Flask |
| Ontology engine | Py2ONTO, owlready2 |
| Data processing | pandas |
| Frontend | Vanilla HTML / CSS / JavaScript |
| LLM integration | OpenAI SDK / Google Generative AI SDK |
| External terminology | EBI Ontology Lookup Service (OLS), BioPortal |

---

## Project Structure

```
py2onto-ve-oss/
├── app.py                # Flask application (routes, tree builder, report generator)
├── onto_extractor.py     # LLM ontology extraction module
├── config.py             # Configuration loader
├── config.json           # User configuration file (API keys, etc.)
├── config.example.json   # Configuration file template
├── py2onto.py            # Core ontology builder engine
├── requirements.txt      # Python dependencies
├── templates/
│   └── index.html        # Single-page frontend
├── static/
│   ├── css/style.css     # Stylesheet
│   └── js/app.js         # Frontend application logic
├── ibd_example/          # IBD ontology example (CSV templates + AI prompt)
│   ├── README.md
│   ├── classes.csv
│   ├── object_properties.csv
│   ├── ai_assist_prompt.txt
│   ├── task_prompt.txt
│   ├── IBD_py2ontove.owl
│   ├── Inflammatory Bowel Disease (IBD) Basics Information (CDC.gov).md
│   └── IBD_py2ontove.txt
├── MANUAL_en.md          # English user manual (this file)
└── MANUAL_zh.md          # Chinese user manual
```

