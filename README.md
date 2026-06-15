  <img width="1921" height="819" alt="Py2ONTO-VE logo" src="https://github.com/user-attachments/assets/d4043142-b75c-4ae9-bc8e-2fdc9f0ec4cb" />
  
# Py2ONTO-VE
 A web-based ontology editor supporting manual table editing, CSV import/export, and AI-powered natural language extraction, producing standard OWL format files.
 
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
7. [AI-Assisted Extraction](#ai-assisted-extraction)
   - [Configure API Keys](#configure-api-keys)
   - [Using AI Extraction](#using-ai-extraction)
   - [Custom System Prompt](#custom-system-prompt)
   - [Supported LLM Providers](#supported-llm-providers)
8. [Ontology Tree Visualization](#ontology-tree-visualization)
9. [Configuration File Reference](#configuration-file-reference)
10. [Output File Formats](#output-file-formats)
11. [FAQ](#faq)

---
## Quick Start

### 1. Install Dependencies

```bash
cd py2onto_ve
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
