"""Py2ONTO Visual Editor - Web-based ontology builder with real-time visualization."""

import csv
import io
import json
import os
import sys
import tempfile
import traceback
from datetime import datetime, timezone

import requests

from flask import Flask, jsonify, render_template, request
from owlready2 import (
    AsymmetricProperty,
    destroy_entity,
    FunctionalProperty,
    InverseFunctionalProperty,
    IrreflexiveProperty,
    ReflexiveProperty,
    SymmetricProperty,
    TransitiveProperty,
)

from py2onto import Py2ONTO

app = Flask(__name__)
_last_onto: dict = {}


# ---------------------------------------------------------------------------
# Tree building
# ---------------------------------------------------------------------------

def _clean_ontology(onto: Py2ONTO) -> None:
    """Destroy all entities from a cached ontology so we start fresh each build.

    owlready2's ``get_ontology(iri)`` returns the same object for the same IRI.
    Without this cleanup, subsequent Builds would accumulate stale classes,
    properties and individuals from every previous run.
    """
    # owlready2's destroy_entity can raise when user-defined annotation
    # properties (set via setattr) reference classes — wrap in try/except.
    def _safe_destroy(entity):
        try:
            destroy_entity(entity)
        except Exception:
            pass

    # Destroy in dependency order: individuals → object properties →
    # annotation properties → classes (except Thing).
    for ind in list(onto.onto.individuals()):
        _safe_destroy(ind)
    for prop in list(onto.onto.object_properties()):
        _safe_destroy(prop)
    for prop in list(onto.onto.annotation_properties()):
        _safe_destroy(prop)
    for cls in list(onto.onto.classes()):
        if cls.name != "Thing":
            _safe_destroy(cls)

    # Also clear Py2ONTO's internal tracking dicts so the next build starts
    # with a truly clean slate (prevents stale references to destroyed entities).
    onto._classes = {"Thing": onto.Thing}
    onto._class_iris = {}
    onto._class_sources = {}
    onto._individuals = {}
    onto._object_properties = {}
    onto._annotation_properties = {}
    onto._class_object_properties = {}
    onto._individual_object_properties = {}
    onto._ap_template_values = {}
    onto._ap_template_domains = {}
    onto._ap_template_ranges = {}
    onto._op_template_domains = {}
    onto._op_template_ranges = {}
    onto._op_equivalent_to = {}
    onto._op_subproperty_of = {}
    onto._op_inverse_of = {}
    onto._op_disjoint_with = {}


def _build_tree(onto: Py2ONTO) -> dict:
    """Build a nested tree representing the full ontology hierarchy."""
    children_map = {}
    node_info = {}

    # Collect class hierarchy from owlready2
    for cls in onto.onto.classes():
        name = cls.name
        if name == "Thing":
            continue
        label = cls.label[0] if cls.label else name
        iri = onto._class_iris.get(name, "")
        source = onto._class_sources.get(name, "local")
        node_info[name] = {"id": name, "label": label, "iri": iri,
                           "source": source, "type": "class", "children": []}
        for parent in cls.is_a:
            if hasattr(parent, "name"):
                pname = parent.name
                children_map.setdefault(pname, []).append(name)

    # Pre-build class-name → individuals mapping (robust against owlready2 is_a quirks)
    class_individuals: dict[str, list[dict]] = {}
    for ind_name, ind in onto._individuals.items():
        ilabel = ind.label[0] if ind.label else ind_name
        for cls_ref in ind.is_a:
            cls_name = getattr(cls_ref, "name", None)
            if cls_name and cls_name != "Thing":
                class_individuals.setdefault(cls_name, []).append({
                    "id": ind_name,
                    "label": ilabel,
                })

    # Build tree recursively under "Thing"
    def _recurse(parent_name):
        nodes = []
        for cid in children_map.get(parent_name, []):
            entry = node_info[cid]
            entry["children"] = _recurse(cid)

            # Append individuals that belong to this class
            for ind in class_individuals.get(cid, []):
                entry["children"].append({
                    "id": ind["id"],
                    "label": ind["label"],
                    "type": "individual",
                    "children": [],
                })
            nodes.append(entry)
        return nodes

    tree = {
        "id": "Thing",
        "label": "Thing",
        "type": "class_root",
        "children": _recurse("Thing"),
    }

    # Collect object properties as a separate list
    ops = []
    for op_name, op in onto._object_properties.items():
        op_label = op.label[0] if op.label else op_name
        domains = [d.name for d in (op._domain or []) if hasattr(d, "name")]
        ranges = [r.name for r in (op._range or []) if hasattr(r, "name")]
        ops.append({
            "id": op_name,
            "label": op_label,
            "domain": domains,
            "range": ranges,
        })

    # Collect annotation properties
    aps = []
    for ap_name, ap in onto._annotation_properties.items():
        ap_label = ap.label[0] if ap.label else ap_name
        aps.append({"id": ap_name, "label": ap_label})

    return {"class_tree": tree, "object_properties": ops, "annotation_properties": aps}


# ---------------------------------------------------------------------------
# Metadata report builder
# ---------------------------------------------------------------------------

_CHARACTERISTIC_CHECKS = [
    ("Functional", FunctionalProperty),
    ("InverseFunctional", InverseFunctionalProperty),
    ("Transitive", TransitiveProperty),
    ("Symmetric", SymmetricProperty),
    ("Asymmetric", AsymmetricProperty),
    ("Reflexive", ReflexiveProperty),
    ("Irreflexive", IrreflexiveProperty),
]


def _build_metadata_report(onto: Py2ONTO, tree: dict, iri: str, save_path: str) -> str:
    """Generate a structured plain-text metadata report for the ontology.

    The report includes IRI, generation timestamp, statistics, class hierarchy
    (ASCII tree), object property details with characteristics, annotation
    properties, and software environment information — suitable for academic
    documentation and reproducibility.
    """
    now = datetime.now(timezone.utc).astimezone()
    timestamp = now.strftime("%Y-%m-%d %H:%M:%S %Z (UTC%z)")

    # ----- statistics -----
    def _count_tree(node: dict):
        classes, inds = 0, 0

        def walk(n: dict):
            nonlocal classes, inds
            if n["type"] in ("class", "class_root"):
                classes += 1
            elif n["type"] == "individual":
                inds += 1
            for c in n.get("children", []):
                walk(c)

        walk(node)
        return classes, inds

    class_count, ind_count = _count_tree(tree["class_tree"])
    # Exclude owl:Thing from the classes figure shown in Statistics
    stats_class_count = class_count - 1
    op_count = len(tree.get("object_properties", []))
    ap_count = len(tree.get("annotation_properties", []))

    W = 72
    lines: list[str] = []

    # ----- helpers -----
    def hr(char: str = "=") -> None:
        lines.append(char * W)

    def section(title: str) -> None:
        lines.append("")
        hr("=")
        lines.append(f"  {title}")
        hr("=")
        lines.append("")

    def kv(key: str, value: str) -> None:
        lines.append(f"  {key:<24s} {value}")

    def _render_tree(node: dict, prefix: str = "", is_last: bool = True, is_root: bool = False) -> None:
        if is_root:
            connector = ""
            branch = ""
        else:
            connector = "└── " if is_last else "├── "
            branch = "    " if is_last else "│   "

        label = node.get("label") or node["id"]
        ntype = node["type"]

        if ntype == "class_root":
            lines.append(f"{prefix}{connector}{label} [root]")
        elif ntype == "individual":
            lines.append(f"{prefix}{connector}◆ {label}")
        else:
            lines.append(f"{prefix}{connector}{label}")

        children = node.get("children", [])
        for i, child in enumerate(children):
            _render_tree(child, prefix + branch, i == len(children) - 1)

    # ===== 1. Header =====
    hr("=")
    lines.append("  ONTOLOGY GENERATION REPORT")
    hr("=")
    lines.append("")
    kv("Ontology IRI", iri)
    kv("Generated by", "Py2ONTO Visual Editor")
    kv("Generation time", timestamp)
    kv("Output file", os.path.basename(save_path))

    # ===== 2. Statistics =====
    section("STATISTICS")
    kv("Classes", str(stats_class_count))
    kv("Individuals", str(ind_count))
    kv("Object Properties", str(op_count))
    kv("Annotation Properties", str(ap_count))

    # ===== 3. Class Hierarchy =====
    section("CLASS HIERARCHY")
    _render_tree(tree["class_tree"], is_root=True)

    # ===== 4. Object Properties =====
    if tree.get("object_properties"):
        section("OBJECT PROPERTIES")
        for op_info in tree["object_properties"]:
            op_id = op_info["id"]
            op_label = op_info.get("label") or op_id
            lines.append(f"  [{op_id}]")
            if op_label != op_id:
                kv("  Label", op_label)
            if op_info.get("domain"):
                kv("  Domain", ", ".join(op_info["domain"]))
            if op_info.get("range"):
                kv("  Range", ", ".join(op_info["range"]))

            # Query owlready2 entity for property characteristics
            op_entity = onto._object_properties.get(op_id)
            if op_entity is not None:
                chars: list[str] = []
                for ch_name, ch_cls in _CHARACTERISTIC_CHECKS:
                    try:
                        if issubclass(op_entity, ch_cls):
                            chars.append(ch_name)
                    except Exception:
                        pass
                if chars:
                    kv("  Characteristics", ", ".join(chars))
            lines.append("")

    # ===== 5. Annotation Properties =====
    if tree.get("annotation_properties"):
        section("ANNOTATION PROPERTIES")
        for ap_info in tree["annotation_properties"]:
            ap_id = ap_info["id"]
            ap_label = ap_info.get("label") or ap_id
            if ap_label != ap_id:
                lines.append(f"  {ap_id}  ({ap_label})")
            else:
                lines.append(f"  {ap_id}")

    # ===== 6. Footer =====
    section("METADATA")
    kv("Generator", "Py2ONTO")
    try:
        import owlready2 as _or2

        kv("Powered by", f"owlready2 {_or2.__version__}")
    except Exception:
        kv("Powered by", "owlready2")
    kv("Python", sys.version.split()[0])
    kv("Report generated", timestamp)
    lines.append("")
    hr("=")

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# CSV writer helper
# ---------------------------------------------------------------------------

def _write_csv(cols: list, rows: list[dict], col_map: dict) -> str:
    # Auto-detect extra columns from row data (e.g. user-added * / $ prefixed
    # columns for annotation/object properties).
    all_cols = list(cols)
    all_cm = dict(col_map)
    for row in rows:
        for key, val in row.items():
            if key not in all_cm and val:
                all_cm[key] = key
                all_cols.append(key)

    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(all_cols)
    for row in rows:
        w.writerow([row.get(k, "") for k in all_cm])
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8")
    f.write(buf.getvalue())
    p = f.name
    f.close()
    return p


# ---------------------------------------------------------------------------
# Default annotation properties (always included in every ontology build)
# ---------------------------------------------------------------------------

_DEFAULT_APS = [
    {"id": "definition", "label": "definition",
     "comment": "The authoritative definition of an ontology term",
     "domain": "Thing", "range": "Thing", "definition": ""},
    {"id": "hasDbXref", "label": "has dbxref",
     "comment": "Database cross-reference to an external resource (e.g., SNOMED CT, MeSH, NCIT)",
     "domain": "Thing", "range": "Thing", "definition": ""},
]


def _ensure_default_aps(ap_data: list[dict]) -> list[dict]:
    """Ensure the built-in default annotation properties are always present.

    If ``definition`` or ``hasDbXref`` are missing from *ap_data*, prepend
    them so every generated ontology includes these standard properties.
    Existing user-configured entries (by ID) are preserved unchanged.
    """
    existing_ids = {row.get("id", "").strip() for row in ap_data if row.get("id")}
    result = list(ap_data)
    for default_ap in reversed(_DEFAULT_APS):
        if default_ap["id"] not in existing_ids:
            result.insert(0, default_ap)
    return result


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/preview", methods=["POST"])
def preview():
    global _last_onto
    data = request.json or {}
    iri = data.get("iri", "http://example.com/onto.owl#")
    ap_data = _ensure_default_aps(data.get("aps", []))
    op_data = data.get("ops", [])
    class_data = data.get("classes", [])
    ind_data = data.get("individuals", [])
    tmp = []

    try:
        onto = Py2ONTO(iri)
        _clean_ontology(onto)  # wipe stale entities from a previous build

        if ap_data:
            cols = ["ID", "label", "comment", "domain", "range", "*definition"]
            cm = {"id": "ID", "label": "label", "comment": "comment",
                  "domain": "domain", "range": "range", "definition": "*definition"}
            p = _write_csv(cols, ap_data, cm); tmp.append(p)
            onto._create_annotation_property_by_template(p)

        if op_data:
            cols = ["ID", "label", "comment",
                    "FunctionalProperty", "InverseFunctionalProperty",
                    "TransitiveProperty", "SymmetricProperty", "AsymmetricProperty",
                    "ReflexiveProperty", "IrreflexiveProperty",
                    "equivalent_to", "subproperty_of", "inverse_of",
                    "domain", "range", "disjoint_with", "*definition"]
            cm = {"id": "ID", "label": "label", "comment": "comment",
                  "FunctionalProperty": "FunctionalProperty",
                  "InverseFunctionalProperty": "InverseFunctionalProperty",
                  "TransitiveProperty": "TransitiveProperty",
                  "SymmetricProperty": "SymmetricProperty",
                  "AsymmetricProperty": "AsymmetricProperty",
                  "ReflexiveProperty": "ReflexiveProperty",
                  "IrreflexiveProperty": "IrreflexiveProperty",
                  "equivalent_to": "equivalent_to", "subproperty_of": "subproperty_of",
                  "inverse_of": "inverse_of",
                  "domain": "domain", "range": "range",
                  "disjoint_with": "disjoint_with", "definition": "*definition"}
            p = _write_csv(cols, op_data, cm); tmp.append(p)
            onto._create_object_property_by_template(p)

        if class_data:
            cols = ["Parent_Class", "ID", "label", "IRI", "comment", "*definition"]
            cm = {"parent_class": "Parent_Class", "id": "ID", "label": "label",
                  "iri": "IRI", "comment": "comment", "definition": "*definition"}
            p = _write_csv(cols, class_data, cm); tmp.append(p)
            onto.init(p)

            if onto._ap_template_domains:
                for k, v in onto._ap_template_domains.items():
                    onto._set_annotation_property_domains_from_template(k, v)
            if onto._ap_template_ranges:
                for k, v in onto._ap_template_ranges.items():
                    onto._set_annotation_property_ranges_from_template(k, v)
            if onto._op_template_domains:
                for k, v in onto._op_template_domains.items():
                    onto._set_object_property_domains_from_template(k, v)
            if onto._op_template_ranges:
                for k, v in onto._op_template_ranges.items():
                    onto._set_object_property_ranges_from_template(k, v)

        if class_data and ind_data:
            cols = ["Types", "relation", "ID", "label", "comment", "*definition"]
            cm = {"types": "Types", "relation": "relation", "id": "ID",
                  "label": "label", "comment": "comment", "definition": "*definition"}
            p = _write_csv(cols, ind_data, cm); tmp.append(p)
            onto.build(p)

        for p in tmp:
            try:
                os.unlink(p)
            except OSError:
                pass

        tree = _build_tree(onto)
        _last_onto = {"iri": iri, "onto": onto}
        return jsonify({"success": True, "tree": tree})

    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 400


@app.route("/api/generate", methods=["POST"])
def generate():
    global _last_onto
    data = request.json or {}
    iri = data.get("iri", _last_onto.get("iri", "http://example.com/onto.owl#"))
    save_path = data.get("save_path", "./new_onto.owl")
    ap_data = _ensure_default_aps(data.get("aps", []))
    op_data = data.get("ops", [])
    class_data = data.get("classes", [])
    ind_data = data.get("individuals", [])
    tmp = []

    try:
        onto = Py2ONTO(iri)
        _clean_ontology(onto)  # wipe stale entities from a previous build

        if ap_data:
            cols = ["ID", "label", "comment", "domain", "range", "*definition"]
            cm = {"id": "ID", "label": "label", "comment": "comment",
                  "domain": "domain", "range": "range", "definition": "*definition"}
            p = _write_csv(cols, ap_data, cm); tmp.append(p)
            onto._create_annotation_property_by_template(p)

        if op_data:
            cols = ["ID", "label", "comment",
                    "FunctionalProperty", "InverseFunctionalProperty",
                    "TransitiveProperty", "SymmetricProperty", "AsymmetricProperty",
                    "ReflexiveProperty", "IrreflexiveProperty",
                    "equivalent_to", "subproperty_of", "inverse_of",
                    "domain", "range", "disjoint_with", "*definition"]
            cm = {"id": "ID", "label": "label", "comment": "comment",
                  "FunctionalProperty": "FunctionalProperty",
                  "InverseFunctionalProperty": "InverseFunctionalProperty",
                  "TransitiveProperty": "TransitiveProperty",
                  "SymmetricProperty": "SymmetricProperty",
                  "AsymmetricProperty": "AsymmetricProperty",
                  "ReflexiveProperty": "ReflexiveProperty",
                  "IrreflexiveProperty": "IrreflexiveProperty",
                  "equivalent_to": "equivalent_to", "subproperty_of": "subproperty_of",
                  "inverse_of": "inverse_of",
                  "domain": "domain", "range": "range",
                  "disjoint_with": "disjoint_with", "definition": "*definition"}
            p = _write_csv(cols, op_data, cm); tmp.append(p)
            onto._create_object_property_by_template(p)

        if class_data:
            cols = ["Parent_Class", "ID", "label", "IRI", "comment", "*definition"]
            cm = {"parent_class": "Parent_Class", "id": "ID", "label": "label",
                  "iri": "IRI", "comment": "comment", "definition": "*definition"}
            p = _write_csv(cols, class_data, cm); tmp.append(p)
            onto.init(p)

            if onto._ap_template_domains:
                for k, v in onto._ap_template_domains.items():
                    onto._set_annotation_property_domains_from_template(k, v)
            if onto._ap_template_ranges:
                for k, v in onto._ap_template_ranges.items():
                    onto._set_annotation_property_ranges_from_template(k, v)
            if onto._op_template_domains:
                for k, v in onto._op_template_domains.items():
                    onto._set_object_property_domains_from_template(k, v)
            if onto._op_template_ranges:
                for k, v in onto._op_template_ranges.items():
                    onto._set_object_property_ranges_from_template(k, v)

        if class_data and ind_data:
            cols = ["Types", "relation", "ID", "label", "comment", "*definition"]
            cm = {"types": "Types", "relation": "relation", "id": "ID",
                  "label": "label", "comment": "comment", "definition": "*definition"}
            p = _write_csv(cols, ind_data, cm); tmp.append(p)
            onto.build(p)

        for p in tmp:
            try:
                os.unlink(p)
            except OSError:
                pass

        onto.save(save_path)
        _last_onto = {"iri": iri, "onto": onto}
        tree = _build_tree(onto)

        # Generate companion metadata report (.txt) alongside the OWL file
        report = _build_metadata_report(onto, tree, iri, save_path)
        txt_path = os.path.splitext(save_path)[0] + ".txt"
        with open(txt_path, "w", encoding="utf-8") as fh:
            fh.write(report)

        # Read back the saved OWL content so the frontend can trigger a
        # browser download without a second request.
        with open(save_path, "r", encoding="utf-8") as fh:
            owl_content = fh.read()

        # Use the base name of the user's chosen save path as the download
        # filename (e.g. "my_onto.owl").
        download_name = os.path.basename(save_path)

        return jsonify({
            "success": True,
            "message": f"Ontology saved to {save_path}",
            "tree": tree,
            "owl_content": owl_content,
            "filename": download_name,
            "metadata_content": report,
            "metadata_filename": os.path.basename(txt_path),
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 400


@app.route("/api/clear", methods=["POST"])
def clear():
    """Reset the cached ontology so the next Build starts from a clean slate."""
    global _last_onto
    _last_onto = {}
    return jsonify({"success": True, "message": "Cache cleared"})


@app.route("/api/ai-extract", methods=["POST"])
def ai_extract():
    """Extract ontology elements from natural language text using an LLM."""
    data = request.json or {}
    user_text = (data.get("text") or "").strip()
    provider = (data.get("provider") or "deepseek").strip().lower()
    model = (data.get("model") or "").strip()
    task_prompt = (data.get("task_prompt") or "").strip()

    if not user_text:
        return jsonify({"success": False, "error": "No input text provided."}), 400

    try:
        # Lazy imports so the app still starts without all LLM SDKs installed
        from config import get_llm_config, get_system_prompt
        from onto_extractor import EXTRACTION_SYSTEM_PROMPT, extract_ontology_from_text

        llm_cfg = get_llm_config(provider)
        api_key = llm_cfg["api_key"]
        if not api_key and provider != "ollama":
            env_var = {
                "deepseek": "DEEPSEEK_API_KEY",
                "chatglm": "CHATGLM_API_KEY",
                "gemini": "GEMINI_API_KEY",
                "anthropic": "ANTHROPIC_API_KEY",
            }.get(provider, f"{provider.upper()}_API_KEY")
            return jsonify({
                "success": False,
                "error": (
                    f"No API key configured for '{provider}'. "
                    f"Set it in config.json (llm.{provider}.api_key) "
                    f"or the {env_var} environment variable."
                ),
            }), 400

        # Ollama needs a dummy key for the OpenAI client but no real auth
        if provider == "ollama":
            api_key = api_key or "ollama"
            base_url = llm_cfg.get("base_url", "") or "http://localhost:11434/v1"
        else:
            base_url = llm_cfg.get("base_url", "")

        model = model or llm_cfg["model"]

        # Use user-supplied prompt if provided, else config prompt, else built-in default
        custom_prompt = (data.get("system_prompt") or "").strip()
        if not custom_prompt:
            custom_prompt = get_system_prompt()
        if not custom_prompt:
            custom_prompt = EXTRACTION_SYSTEM_PROMPT

        # Append task prompt (instructions) to the system prompt
        if task_prompt:
            custom_prompt = custom_prompt + "\n\n## Instructions\n\n" + task_prompt
            custom_prompt = EXTRACTION_SYSTEM_PROMPT

        extracted, warnings = extract_ontology_from_text(
            user_text,
            provider=provider,
            model=model,
            api_key=api_key,
            base_url=base_url,
            system_prompt=custom_prompt,
        )
        return jsonify({
            "success": True,
            "data": extracted,
            "warnings": warnings,
        })
    except json.JSONDecodeError as e:
        return jsonify({
            "success": False,
            "error": (
                "LLM returned unparseable output. "
                "The model may have responded with text instead of JSON. "
                "Try rephrasing your description or use a different model."
            ),
            "detail": str(e),
        }), 400
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": f"AI extraction failed: {str(e)}"}), 500


@app.route("/api/prompt", methods=["GET"])
def get_prompt():
    """Return the current system prompt (config value or built-in default)."""
    from config import get_system_prompt
    from onto_extractor import EXTRACTION_SYSTEM_PROMPT

    custom = get_system_prompt()
    return jsonify({
        "success": True,
        "prompt": custom if custom else EXTRACTION_SYSTEM_PROMPT,
        "is_custom": bool(custom),
    })


@app.route("/api/prompt", methods=["POST"])
def save_prompt():
    """Save a custom system prompt to config.json."""
    data = request.json or {}
    prompt = (data.get("prompt") or "").strip()
    from config import save_system_prompt  # noqa: F811

    save_system_prompt(prompt)
    return jsonify({"success": True, "message": "Prompt saved to config.json"})


@app.route("/api/prompt/reset", methods=["POST"])
def reset_prompt():
    """Reset the system prompt to the built-in default."""
    from config import save_system_prompt

    save_system_prompt("")
    return jsonify({"success": True, "message": "Prompt reset to built-in default"})


@app.route("/api/task-prompt", methods=["GET"])
def get_task_prompt():
    """Return the current task prompt from config.json."""
    from config import get_task_prompt as _gtp

    prompt = _gtp()
    return jsonify({
        "success": True,
        "prompt": prompt,
    })


@app.route("/api/task-prompt", methods=["POST"])
def save_task_prompt():
    """Save the task prompt to config.json."""
    data = request.json or {}
    prompt = (data.get("prompt") or "").strip()
    from config import save_task_prompt as _stp

    _stp(prompt)
    return jsonify({"success": True, "message": "Task prompt saved to config.json"})


@app.route("/api/task-prompt/reset", methods=["POST"])
def reset_task_prompt():
    """Reset the task prompt to empty."""
    from config import save_task_prompt as _stp

    _stp("")
    return jsonify({"success": True, "message": "Task prompt cleared"})


@app.route("/api/ollama-models", methods=["GET"])
def ollama_models():
    """List locally available Ollama models via the Ollama API."""
    try:
        resp = requests.get("http://localhost:11434/api/tags", timeout=5)
        resp.raise_for_status()
        models = [m["name"] for m in resp.json().get("models", [])]
        return jsonify({"success": True, "models": models})
    except requests.exceptions.ConnectionError:
        return jsonify({
            "success": False,
            "error": "Cannot connect to Ollama. Make sure 'ollama serve' is running.",
        }), 503
    except requests.exceptions.RequestException as e:
        return jsonify({
            "success": False,
            "error": f"Ollama API error: {e}",
        }), 503


OLS_SEARCH_URL = "https://www.ebi.ac.uk/ols4/api/search"
OLS_SEARCH_TIMEOUT = 10  # seconds
OLS_PAGE_SIZE = 100  # results per page


@app.route("/api/ols-search", methods=["GET"])
def ols_search():
    """Search the Ontology Lookup Service (OLS) for ontology terms."""
    q = (request.args.get("q") or "").strip()
    if not q:
        return jsonify({
            "success": False,
            "error": "Please enter a search keyword.",
            "error_type": "empty_query",
        }), 400
    if len(q) < 2:
        return jsonify({
            "success": False,
            "error": "Search keyword must be at least 2 characters long.",
            "error_type": "query_too_short",
        }), 400

    page = request.args.get("page", 1, type=int)
    if page < 1:
        page = 1
    start = (page - 1) * OLS_PAGE_SIZE
    ontologies = (request.args.get("ontologies") or "").strip()

    ols_params: dict = {"q": q, "start": start, "rows": OLS_PAGE_SIZE}
    if ontologies:
        # OLS4 only accepts a single ontology ID (e.g. "efo", "go")
        ols_params["ontology"] = ontologies

    try:
        resp = requests.get(
            OLS_SEARCH_URL,
            params=ols_params,
            headers={"Accept": "application/json"},
            timeout=OLS_SEARCH_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.SSLError as e:
        print(f"[OLS] SSL error: {e}")
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": (
                "SSL certificate verification failed while connecting to EBI OLS. "
                "This usually means the server's CA certificates are missing or outdated. "
                "Try: apt-get install ca-certificates (Debian/Ubuntu) "
                "or: yum install ca-certificates (RHEL/CentOS)."
            ),
            "error_type": "ssl_error",
        }), 502
    except requests.exceptions.ProxyError as e:
        print(f"[OLS] Proxy error: {e}")
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": (
                f"Cannot connect through the configured proxy: {e}. "
                f"Check your HTTPS_PROXY / HTTP_PROXY environment variables, "
                f"or unset them if no proxy is needed."
            ),
            "error_type": "proxy_error",
        }), 502
    except requests.exceptions.ConnectTimeout as e:
        print(f"[OLS] Connect timeout ({OLS_SEARCH_TIMEOUT}s): {e}")
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": (
                f"Connection to EBI OLS timed out after {OLS_SEARCH_TIMEOUT}s. "
                f"The server might be behind a firewall that blocks outbound HTTPS (port 443), "
                f"or the EBI server is unreachable from this network. "
                f"Try: curl -v https://www.ebi.ac.uk to test connectivity."
            ),
            "error_type": "connect_timeout",
        }), 502
    except requests.exceptions.ReadTimeout as e:
        print(f"[OLS] Read timeout ({OLS_SEARCH_TIMEOUT}s): {e}")
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": (
                f"EBI OLS did not respond within {OLS_SEARCH_TIMEOUT}s. "
                f"The service might be under heavy load. Please try again later."
            ),
            "error_type": "read_timeout",
        }), 502
    except requests.exceptions.ConnectionError as e:
        print(f"[OLS] Connection error: {e}")
        traceback.print_exc()
        # Try to give a more specific hint based on the underlying error
        inner = str(e)
        if "Name or service not known" in inner or "getaddrinfo" in inner.lower():
            hint = (
                "DNS resolution failed — the server cannot resolve www.ebi.ac.uk. "
                "Check /etc/resolv.conf or the server's DNS configuration."
            )
        elif "Connection refused" in inner:
            hint = (
                "Connection refused by the remote server. "
                "A firewall may be blocking outbound HTTPS (port 443)."
            )
        elif "No route to host" in inner:
            hint = "Network unreachable — check the server's routing table and firewall rules."
        else:
            hint = (
                "The server cannot reach www.ebi.ac.uk. "
                "Check DNS, firewall rules, and outbound HTTPS connectivity."
            )
        return jsonify({
            "success": False,
            "error": f"Unable to connect to EBI OLS: {hint}",
            "error_type": "connection_error",
        }), 502
    except requests.exceptions.HTTPError as e:
        status = resp.status_code
        print(f"[OLS] HTTP {status}: {resp.text[:500]}")
        traceback.print_exc()
        if status == 429:
            hint = "EBI OLS rate-limited this server (HTTP 429). Please wait and try again in a minute."
        elif status == 503:
            hint = "EBI OLS is temporarily unavailable (HTTP 503). The service may be down for maintenance."
        elif status == 404:
            hint = "EBI OLS search endpoint not found (HTTP 404). The API URL may have changed."
        elif status >= 500:
            hint = f"EBI OLS server error (HTTP {status}). This is a problem on the OLS side — try again later."
        else:
            hint = f"EBI OLS returned HTTP {status}. Please try again later."
        return jsonify({
            "success": False,
            "error": hint,
            "error_type": f"http_{status}",
        }), 502
    except requests.exceptions.TooManyRedirects as e:
        print(f"[OLS] Too many redirects: {e}")
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": "EBI OLS redirected too many times. The API endpoint may have moved.",
            "error_type": "too_many_redirects",
        }), 502
    except json.JSONDecodeError:
        print(f"[OLS] JSON decode error — raw body (first 500 chars): {resp.text[:500]}")
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": "EBI OLS returned a malformed response. This is a transient issue — please try again.",
            "error_type": "bad_json",
        }), 502
    except Exception as e:
        print(f"[OLS] Unexpected error: {e}")
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": f"An unexpected error occurred while searching OLS: {str(e)}",
            "error_type": "unknown",
        }), 500

    results: list[dict] = []
    for doc in data.get("response", {}).get("docs", []):
        raw_id = doc.get("obo_id", doc.get("short_form", ""))
        # owlready2 derives .name from the IRI tail, which uses underscores
        # (e.g. DOID_1324), but OLS returns CURIE-style IDs with colons
        # (e.g. DOID:1324). Normalise to underscores so table ↔ tree match.
        normalised_id = raw_id.replace(":", "_")
        results.append({
            "id": normalised_id,
            "label": doc.get("label", ""),
            "iri": doc.get("iri", ""),
            "ontology": doc.get("ontology_name", doc.get("ontology_prefix", "")),
        })

    num_found = data.get("response", {}).get("numFound", len(results))
    page_count = max(1, -(-num_found // OLS_PAGE_SIZE))  # ceil division
    return jsonify({
        "success": True,
        "results": results,
        "numFound": num_found,
        "page": page,
        "pageCount": page_count,
    })


# ---------------------------------------------------------------------------
# BioPortal search
# ---------------------------------------------------------------------------

BIOPORTAL_SEARCH_URL = "http://data.bioontology.org/search"
BIOPORTAL_SEARCH_TIMEOUT = 10  # seconds
BIOPORTAL_PAGE_SIZE = 100  # results per page


@app.route("/api/bioportal-search", methods=["GET"])
def bioportal_search():
    """Search BioPortal for ontology terms."""
    q = (request.args.get("q") or "").strip()
    if not q:
        return jsonify({
            "success": False,
            "error": "Please enter a search keyword.",
            "error_type": "empty_query",
        }), 400
    if len(q) < 2:
        return jsonify({
            "success": False,
            "error": "Search keyword must be at least 2 characters long.",
            "error_type": "query_too_short",
        }), 400

    page = request.args.get("page", 1, type=int)
    ontologies = (request.args.get("ontologies") or "").strip()

    # Resolve API key from config.json or environment variable
    from config import get_portal_config  # lazy import
    portal_cfg = get_portal_config()
    api_key = portal_cfg["bioportal_api_key"] or os.environ.get("BIOPORTAL_API_KEY", "")
    if not api_key:
        return jsonify({
            "success": False,
            "error": (
                "No BioPortal API key configured. "
                "Set it in config.json (bioportal.api_key) "
                "or the BIOPORTAL_API_KEY environment variable. "
                "Get a key at https://bioportal.bioontology.org/account"
            ),
            "error_type": "no_api_key",
        }), 400

    params: dict = {
        "q": q,
        "pagesize": BIOPORTAL_PAGE_SIZE,
        "page": page,
        "include": "prefLabel,definition,notation",
    }
    if ontologies:
        params["ontologies"] = ontologies

    try:
        resp = requests.get(
            BIOPORTAL_SEARCH_URL,
            params=params,
            headers={
                "Accept": "application/json",
                "Authorization": f"apikey token={api_key}",
            },
            timeout=BIOPORTAL_SEARCH_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.SSLError as e:
        print(f"[BioPortal] SSL error: {e}")
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": (
                "SSL certificate verification failed while connecting to BioPortal. "
                "This usually means the server's CA certificates are missing or outdated."
            ),
            "error_type": "ssl_error",
        }), 502
    except requests.exceptions.ProxyError as e:
        print(f"[BioPortal] Proxy error: {e}")
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": (
                f"Cannot connect through the configured proxy: {e}. "
                f"Check your HTTPS_PROXY / HTTP_PROXY environment variables."
            ),
            "error_type": "proxy_error",
        }), 502
    except requests.exceptions.ConnectTimeout as e:
        print(f"[BioPortal] Connect timeout ({BIOPORTAL_SEARCH_TIMEOUT}s): {e}")
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": (
                f"Connection to BioPortal timed out after {BIOPORTAL_SEARCH_TIMEOUT}s. "
                f"The server might be behind a firewall that blocks outbound HTTP (port 80)."
            ),
            "error_type": "connect_timeout",
        }), 502
    except requests.exceptions.ReadTimeout as e:
        print(f"[BioPortal] Read timeout ({BIOPORTAL_SEARCH_TIMEOUT}s): {e}")
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": (
                f"BioPortal did not respond within {BIOPORTAL_SEARCH_TIMEOUT}s. "
                f"The service might be under heavy load. Please try again later."
            ),
            "error_type": "read_timeout",
        }), 502
    except requests.exceptions.ConnectionError as e:
        print(f"[BioPortal] Connection error: {e}")
        traceback.print_exc()
        inner = str(e)
        if "Name or service not known" in inner or "getaddrinfo" in inner.lower():
            hint = (
                "DNS resolution failed — the server cannot resolve data.bioontology.org. "
                "Check /etc/resolv.conf or the server's DNS configuration."
            )
        elif "Connection refused" in inner:
            hint = "Connection refused by BioPortal. A firewall may be blocking outbound HTTP (port 80)."
        elif "No route to host" in inner:
            hint = "Network unreachable — check the server's routing table and firewall rules."
        else:
            hint = (
                "The server cannot reach data.bioontology.org. "
                "Check DNS, firewall rules, and outbound HTTP connectivity."
            )
        return jsonify({
            "success": False,
            "error": f"Unable to connect to BioPortal: {hint}",
            "error_type": "connection_error",
        }), 502
    except requests.exceptions.HTTPError as e:
        status = resp.status_code
        print(f"[BioPortal] HTTP {status}: {resp.text[:500]}")
        traceback.print_exc()
        if status == 401:
            hint = "BioPortal rejected the API key (HTTP 401). Check that your API key is valid."
        elif status == 429:
            hint = "BioPortal rate-limited this server (HTTP 429). Please wait and try again in a minute."
        elif status == 503:
            hint = "BioPortal is temporarily unavailable (HTTP 503). The service may be down for maintenance."
        elif status >= 500:
            hint = f"BioPortal server error (HTTP {status}). This is a problem on the BioPortal side — try again later."
        else:
            hint = f"BioPortal returned HTTP {status}. Please try again later."
        return jsonify({
            "success": False,
            "error": hint,
            "error_type": f"http_{status}",
        }), 502
    except requests.exceptions.TooManyRedirects as e:
        print(f"[BioPortal] Too many redirects: {e}")
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": "BioPortal redirected too many times. The API endpoint may have moved.",
            "error_type": "too_many_redirects",
        }), 502
    except json.JSONDecodeError:
        print(f"[BioPortal] JSON decode error — raw body (first 500 chars): {resp.text[:500]}")
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": "BioPortal returned a malformed response. This is a transient issue — please try again.",
            "error_type": "bad_json",
        }), 502
    except Exception as e:
        print(f"[BioPortal] Unexpected error: {e}")
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": f"An unexpected error occurred while searching BioPortal: {str(e)}",
            "error_type": "unknown",
        }), 500

    # Normalize results to the same format as OLS search
    results: list[dict] = []
    collection = data.get("collection", [])
    for item in collection:
        # ID: prefer notation (CURIE-style), fall back to @id last segment
        raw_id = item.get("notation", "")
        if not raw_id:
            raw_id = item.get("@id", "").split("/")[-1]
        # Normalise colon to underscore (matching OLS convention)
        normalised_id = raw_id.replace(":", "_") if raw_id else ""

        # Ontology acronym from links.ontology
        ontology_url = ""
        if "links" in item and "ontology" in item["links"]:
            ontology_url = item["links"]["ontology"]
        ontology_acronym = ontology_url.split("/")[-1] if ontology_url else ""

        results.append({
            "id": normalised_id,
            "label": item.get("prefLabel", ""),
            "iri": item.get("@id", ""),
            "ontology": ontology_acronym,
        })

    total_count = data.get("totalCount", len(results))
    page_count = data.get("pageCount", 1)
    current_page = data.get("page", page)

    return jsonify({
        "success": True,
        "results": results,
        "numFound": total_count,
        "page": current_page,
        "pageCount": page_count,
    })


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5001)
