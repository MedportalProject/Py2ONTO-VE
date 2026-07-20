"""LLM-powered ontology extraction from natural language text.

Supports multiple LLM providers: DeepSeek, ChatGLM (ZhipuAI), Gemini,
and Anthropic Claude.

Usage::

    from onto_extractor import extract_ontology_from_text

    data, warnings = extract_ontology_from_text(
        "Heart Disease is a subclass of Disease. Beta Blockers treat Heart Disease.",
        provider="deepseek",
        model="deepseek-chat",
        api_key="sk-...",
        base_url="https://api.deepseek.com/v1",
    )
"""

import json
from typing import Any


# ---------------------------------------------------------------------------
# Extraction system prompt (shared by all providers)
# ---------------------------------------------------------------------------

EXTRACTION_SYSTEM_PROMPT = """\
You are an ontology engineer specializing in OWL ontology extraction from natural language. Your task is to read a domain description and output a structured JSON representation that can populate an ontology editor.

## Output Schema

Return ONLY a JSON object with these four keys. Every key MUST be present, even if its array is empty.

```json
{
  "classes": [
    {
      "parent_class": "Thing",
      "id": "<ClassID>",
      "label": "<Class Label>",
      "iri": "<BaseOntologyIRI><ClassID>",
      "source": "local",
      "comment": "",
      "definition": ""
    }
  ],
  "aps": [
    {
      "id": "<AnnotationPropertyID>",
      "label": "<Annotation Property Label>",
      "comment": "",
      "domain": "Thing",
      "range": "Thing",
      "definition": ""
    }
  ],
  "ops": [
    {
      "id": "<ObjectPropertyID>",
      "label": "<Object Property Label>",
      "comment": "",
      "FunctionalProperty": "",
      "InverseFunctionalProperty": "",
      "TransitiveProperty": "",
      "SymmetricProperty": "",
      "AsymmetricProperty": "",
      "ReflexiveProperty": "",
      "IrreflexiveProperty": "",
      "equivalent_to": "",
      "subproperty_of": "",
      "inverse_of": "",
      "domain": "<ClassID>",
      "range": "<ClassID>",
      "disjoint_with": "",
      "definition": ""
    }
  ],
  "individuals": [
    {
      "types": "<ClassID>",
      "relation": "has_individual",
      "id": "<IndividualID>",
      "label": "<Individual Label>",
      "comment": "",
      "definition": ""
    }
  ]
}
```

## Rules

### Classes

* `parent_class`: The superclass. Use `"Thing"` for top-level classes. Must reference a class `id` that exists in the extracted classes or `"Thing"`.
* `id`: CamelCase alphanumeric string, unique within classes. Must NOT be `"Thing"`.
* `label`: Human-readable name.
* `iri`: Full IRI of the class, constructed as `<BaseOntologyIRI><ClassID>`. For local classes, this is the ontology's base IRI + the class ID. For externally sourced classes, use the canonical IRI.
* `source`: Always `"local"` for classes extracted from the user's description. Use `"OLS"` or other values only for classes imported from external ontologies.
* `comment`: Concise natural-language description. Can be `""`.
* `definition`: Formal definition text. Can be `""`.
* `$<op_id>`: OPTIONAL. When the text states that THIS SPECIFIC class relates to specific other classes via an object property, add a field prefixed with `$` followed by the object property `id`. Value is the target class `id`(s) joined with `&` (e.g. `"$hasSymptom": "Diarrhea&Fatigue&Nausea"`). Only add when the text explicitly links a named class to named target classes — do NOT add for relationships stated only at the domain/range schema level.

### Annotation Properties (aps)

* `id`: Lowercase_with_underscores or camelCase identifier.
* `label`: Human-readable label.
* `comment`: Description. Can be `""`.
* `domain`, `range`: Class `id` values (or `"Thing"`). Multiple classes joined with `"&"` if explicitly stated.
* `definition`: Can be `""`.

### Object Properties (ops)

* `id`: Lowercase_with_underscores or camelCase identifier.
* `label`: Human-readable label.
* `comment`: Description. Can be `""`.
* `FunctionalProperty` through `IrreflexiveProperty`: Use `"True"` only if explicitly stated in the source text; otherwise use `""`.
* `equivalent_to`, `subproperty_of`, `inverse_of`: Other object property `id` values or `""`.
* `domain`, `range`: Class `id` values. Multiple classes joined with `"&"` only when explicitly supported by the text.
* `disjoint_with`: Other object property `id` value or `""`.
* `definition`: Can be `""`.

### Individuals

* `types`: Class `id` instantiated by the individual. Must exist in extracted classes.
* `relation`: ALWAYS `"has_individual"`.
* `id`: Unique identifier.
* `label`: Human-readable label.
* `comment`: Description. Can be `""`.
* `definition`: Can be `""`.

## General Guidelines
## Extraction Strategy

You MUST analyse the input text through these three passes before outputting any JSON:

### Pass 1 — Identify all candidate classes

Scan the text for EVERY noun phrase that refers to a category of things in the domain.  Ask yourself:

* What is the text ABOUT?  (the main topic → top-level classes)
* What subtypes, variants, or specific forms are mentioned?  (→ subclasses)
* What attributes, features, or characteristics are described as belonging to those things?  (→ attribute classes)
* What other categories are mentioned in relation to the main topic?  (→ sibling or related classes)

For EVERY candidate class, decide:
- Is it a standalone top-level concept? → parent_class = "Thing"
- Is it a specific kind of some broader category mentioned in the text? → parent_class = the broader category
- Could it be BOTH a subclass of something AND a parent of something else? → model both levels

### Pass 2 — Identify implicit and explicit hierarchies

Determine the parent_class for each class using the text's OWN language.  Look for ANY phrase that signals a hierarchical relationship:

| Text pattern | Interpretation |
|---|---|
| "X is a Y" / "X is an Y" | X subclassOf Y |
| "X is a type/form/kind/variant of Y" | X subclassOf Y |
| "Y includes X" / "Y consists of X" | X subclassOf Y |
| "types/categories/forms of Y include X₁, X₂, …" | each Xᵢ subclassOf Y |
| "Y is an umbrella term for X₁, X₂, …" | each Xᵢ subclassOf Y |
| "Y can be divided/classified into X₁, X₂, …" | each Xᵢ subclassOf Y |
| "Y, including X₁ and X₂" / "Y such as X" | X subclassOf Y (or instance of Y) |
| "there are N types of Y: X₁, X₂, …" | each Xᵢ subclassOf Y |
| "Y most commonly affects Z" | Y → affects → Z (object property) |

If the text groups several items under a category name (e.g. lists symptoms under "Symptoms include…"), create the category as a class and each item as its subclass.  Do NOT skip implicit categories — if the text says "Symptoms include X, Y, Z", you MUST create a Symptom class (or use the text's own term for that category) with X, Y, Z as subclasses.

### Pass 3 — Identify relationships (object properties)

For every verb or relational phrase that links two classes, create an object property.  Derive the property name from the verb in the text:

| Text says | Create property |
|---|---|
| "X causes Y" / "X leads to Y" | causes |
| "X affects Y" / "X involves Y" | affects or involves |
| "X is characterised by Y" / "X presents with Y" | hasFeature or hasFinding |
| "symptoms of X include Y" / "X manifests as Y" | hasSymptom |
| "X is treated with Y" / "treatment includes Y" | treatedBy |
| "X is diagnosed by/with Y" | diagnosedBy |
| "X occurs in Y" / "X is found in Y" | occursIn or locatedIn |
| "X increases risk of Y" / "X predisposes to Y" | predisposesTo |
| "X complicates Y" / "X is a complication of Y" | complicates |
| "X is associated with Y" | associatedWith |
| "X protects against Y" | protectsAgainst |

Set the domain to the most specific class that the text says the property applies to.  Set the range to the most specific class that the text says is the target.  If the text implies the property applies to a broader class (e.g. "IBD affects the colon" but the property logically applies to any Disease→AnatomicalSite), use the broader class as domain.

### Pass 4 — Populate class-level object property relationships

After extracting classes and object properties, go back and identify EVERY specific class-to-class relationship stated in the text.  For each relationship where the text names a SPECIFIC source class AND specific target class(es) linked by an object property, add a `$`-prefixed field to the SOURCE class object:

| Text says | Action on the source class object |
|---|---|
| "CrohnsDisease has symptoms Diarrhea, Fatigue, and Nausea" | Add to CrohnsDisease: `"$hasSymptom": "Diarrhea&Fatigue&Nausea"` |
| "Aspirin treats Headache and Migraine" | Add to Aspirin: `"$treats": "Headache&Migraine"` |
| "Metformin reduces HbA1c" | Add to Metformin: `"$reduces": "HbA1c"` |
| "Hypertension is diagnosed by BloodPressure" | Add to Hypertension: `"$diagnosedBy": "BloodPressure"` |

The `$` field key is the object property `id` with a `$` prefix.  The value is one or more target class `id`s joined with `&`.  Each target class MUST exist in the extracted classes list.  If a relationship is already captured by domain/range at the schema level but the text ALSO gives a specific example with named classes, STILL add the `$` field — this makes the relationship explicit in the class hierarchy.

## Binding Rules

1. Extract ONLY what the text explicitly states or directly implies.  Do NOT invent.
2. Every class mentioned in the text MUST appear in the output — even if it seems minor.
3. `id`: CamelCase alphanumeric, unique within classes.  Derive from the label.
4. `label`: Use the EXACT phrasing from the text where possible.
5. `iri`: Set to `""` unless the text specifies an external ontology IRI.
6. `source`: Always `"local"` unless the class is explicitly from an external ontology.
7. `comment`: Use a direct quote or close paraphrase from the text as the description.  Can be `""`.
8. `definition`: Can be `""`.
9. `domain` and `range` must reference class `id` values that exist in the extracted class list or `"Thing"`.
10. `relation` for individuals must ALWAYS be `"has_individual"`.
11. Do NOT set object property characteristics (FunctionalProperty etc.) to `"True"` unless the text explicitly states the characteristic.
12. For `$`-prefixed fields on class objects: the key format is `$<op_id>`.  The value is target class `id`(s) joined with `&`.  Every target MUST exist in the `classes` list.
13. Output valid JSON only — no markdown, no explanations, no surrounding text.
14. Every top-level key (`classes`, `aps`, `ops`, `individuals`) MUST be present, even if empty.

Now, extract ontology elements from the following user description.

Output ONLY the JSON object and nothing else.
"""


# ---------------------------------------------------------------------------
# JSON parsing (shared)
# ---------------------------------------------------------------------------

def _parse_json_response(raw_text: str) -> dict:
    """Parse LLM response text into a JSON dict, with fallback extraction."""
    import re
    import sys

    # Debug: log the raw LLM output so we can diagnose parsing failures
    preview = raw_text[:500] if raw_text else "(empty)"
    print(f"[DEBUG] _parse_json_response: raw_text length={len(raw_text)}, "
          f"preview={preview!r}", file=sys.stderr)

    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        pass

    # Fallback 1: extract JSON from markdown code block (```json ... ```)
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw_text)
    if m:
        block = m.group(1).strip()
        try:
            return json.loads(block)
        except json.JSONDecodeError:
            pass

    # Fallback 2: extract JSON between first { and last }
    start = raw_text.find("{")
    end = raw_text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(raw_text[start:end + 1])
        except json.JSONDecodeError:
            pass

    raise json.JSONDecodeError(
        "Could not parse LLM output as JSON",
        raw_text,
        0,
    ) from None


# ---------------------------------------------------------------------------
# Output validation (shared by all providers)
# ---------------------------------------------------------------------------

_CLASS_FIELDS = ["parent_class", "id", "label", "iri", "source", "comment", "definition"]
_AP_FIELDS = ["id", "label", "comment", "domain", "range", "definition"]
_OP_FIELDS = [
    "id", "label", "comment",
    "FunctionalProperty", "InverseFunctionalProperty",
    "TransitiveProperty", "SymmetricProperty", "AsymmetricProperty",
    "ReflexiveProperty", "IrreflexiveProperty",
    "equivalent_to", "subproperty_of", "inverse_of",
    "domain", "range", "disjoint_with", "definition",
]
_IND_FIELDS = ["types", "relation", "id", "label", "comment", "definition"]

_OP_BOOLEAN_FIELDS = [
    "FunctionalProperty", "InverseFunctionalProperty",
    "TransitiveProperty", "SymmetricProperty", "AsymmetricProperty",
    "ReflexiveProperty", "IrreflexiveProperty",
]


def validate_extracted_ontology(data: dict) -> list[str]:
    """Validate the structure of LLM-extracted ontology JSON.

    Returns a list of warning/error strings (empty list = valid).
    """
    warnings: list[str] = []

    # --- top-level keys ---
    for key in ("classes", "aps", "ops", "individuals"):
        if key not in data:
            warnings.append(f"Missing top-level key: '{key}' — added empty list")
            data[key] = []

    for key in data:
        if key not in ("classes", "aps", "ops", "individuals"):
            warnings.append(f"Unexpected top-level key: '{key}' — ignored")

    # --- collect class IDs for reference checks ---
    class_ids: set[str] = {"Thing"}
    for cls in data.get("classes", []):
        if isinstance(cls, dict) and cls.get("id"):
            cid = str(cls["id"]).strip()
            if cid and cid != "Thing":
                if cid in class_ids:
                    warnings.append(f"Duplicate class ID: '{cid}'")
                class_ids.add(cid)

    # --- validate each entity type ---
    def _check_rows(rows: list, required_fields: list, entity_type: str) -> None:
        if not isinstance(rows, list):
            warnings.append(
                f"'{entity_type}' should be a list, got {type(rows).__name__}"
            )
            return
        for i, row in enumerate(rows):
            if not isinstance(row, dict):
                warnings.append(f"{entity_type}[{i}] is not an object — skipped")
                continue
            for f in required_fields:
                if f not in row:
                    row[f] = ""
                    warnings.append(
                        f"{entity_type}[{i}] missing field '{f}' — set to \"\""
                    )
            # Normalise boolean fields for ops
            if entity_type == "ops":
                for bf in _OP_BOOLEAN_FIELDS:
                    val = str(row.get(bf, "")).strip()
                    if val.lower() in ("true", "yes", "1"):
                        row[bf] = "True"
                    else:
                        row[bf] = ""

    _check_rows(data.get("classes", []), _CLASS_FIELDS, "classes")
    _check_rows(data.get("aps", []), _AP_FIELDS, "aps")
    _check_rows(data.get("ops", []), _OP_FIELDS, "ops")
    _check_rows(data.get("individuals", []), _IND_FIELDS, "individuals")

    # Ensure source defaults to "local" for classes (not empty string)
    for cls in data.get("classes", []):
        if isinstance(cls, dict) and not cls.get("source"):
            cls["source"] = "local"

    # --- reference integrity ---
    for i, cls in enumerate(data.get("classes", [])):
        if not isinstance(cls, dict):
            continue
        pc = str(cls.get("parent_class", "")).strip()
        if pc and pc not in class_ids:
            warnings.append(
                f"classes[{i}] parent_class '{pc}' not found in extracted classes"
            )

    for i, ind in enumerate(data.get("individuals", [])):
        if not isinstance(ind, dict):
            continue
        types_val = str(ind.get("types", "")).strip()
        if types_val and types_val not in class_ids:
            warnings.append(
                f"individuals[{i}] types '{types_val}' not found in extracted classes"
            )
        rel = str(ind.get("relation", "")).strip()
        if rel and rel != "has_individual":
            warnings.append(
                f"individuals[{i}] relation is '{rel}' — expected 'has_individual'"
            )

    # --- deduplicate by ID within each category ---
    _deduplicate_ontology(data, warnings)

    return warnings


def _deduplicate_ontology(data: dict, warnings: list[str]) -> None:
    """Remove duplicate entries within each category (classes/aps/ops/individuals)
    based on the ``id`` field, keeping the first occurrence.

    This handles both LLM-generated duplicates within a single extraction and
    protects downstream consumers (the frontend tables, Py2ONTO) from
    duplicate-ID errors.
    """
    for category in ("classes", "aps", "ops", "individuals"):
        rows = data.get(category, [])
        if not isinstance(rows, list):
            continue
        seen: set[str] = set()
        deduped: list[dict] = []
        removed = 0
        for row in rows:
            if not isinstance(row, dict):
                deduped.append(row)
                continue
            rid = str(row.get("id", "")).strip()
            if not rid:
                # Rows without an ID are kept as-is (they'll be caught by
                # validation warnings, but we can't deduplicate them).
                deduped.append(row)
                continue
            if rid in seen:
                removed += 1
                continue
            seen.add(rid)
            deduped.append(row)
        if removed > 0:
            warnings.append(
                f"Deduplicated {category}: removed {removed} duplicate(s) by ID"
            )
        data[category] = deduped


# ---------------------------------------------------------------------------
# Provider implementations
# ---------------------------------------------------------------------------

def _extract_openai_compatible(
    user_text: str,
    model: str,
    api_key: str,
    base_url: str,
    system_prompt: str = "",
    provider: str = "deepseek",
) -> tuple[dict, list[str]]:
    """Extract using OpenAI-compatible API (DeepSeek, ChatGLM / ZhipuAI).

    Provider-specific notes
    -----------------------
    **DeepSeek**
    - ``deepseek-chat`` (V3): 64K context, supports temperature/top_p.
      Recommended ``max_tokens``: 8K–16K.
    - ``deepseek-reasoner`` (R1): reasoning model.  ``max_tokens`` covers
      **both** ``reasoning_content`` + ``content`` combined (default 32K,
      max 64K).  Reasoning CANNOT be disabled for this model.

    **ChatGLM / ZhipuAI** (``glm-4-flash``, ``glm-4-flashx``, etc.)
    - 128K context window, but **``max_tokens`` is capped at 4095**
      (default 1024!).  Values above 4095 are rejected with a 400 error.
    - Does NOT return ``reasoning_content``; no ``thinking`` toggle needed.
    - ``temperature`` is supported (default 0.95).
    """
    import sys

    try:
        from openai import OpenAI
    except ImportError:
        raise RuntimeError(
            "The 'openai' package is required for DeepSeek / ChatGLM. "
            "Install with: pip install openai"
        )

    is_chatglm = provider == "chatglm"
    is_ollama = provider == "ollama"
    is_reasoner = "reasoner" in model.lower()
    input_len = len(user_text)

    # ---- choose max_tokens based on provider, model type and input size ----
    if is_chatglm:
        # ChatGLM API caps max_tokens at 4095; default is only 1024.
        # For long-text ontology extraction we always push to the limit.
        max_tokens = 4095
    elif is_reasoner:
        # DeepSeek-R1: reasoning tokens + output JSON share one budget.
        max_tokens = 32768  # DeepSeek default for reasoner
    elif input_len > 3000:
        max_tokens = 16384
    elif input_len > 1000:
        max_tokens = 8192
    else:
        max_tokens = 4096

    print(f"[DEBUG] _extract_openai_compatible: provider={provider}, "
          f"model={model}, is_reasoner={is_reasoner}, "
          f"is_chatglm={is_chatglm}, is_ollama={is_ollama}, "
          f"input_len={input_len}, max_tokens={max_tokens}", file=sys.stderr)

    # ---- build API parameters ----
    api_kwargs: dict = {
        "model": model,
        "max_tokens": max_tokens,
        "timeout": 120.0,
        "messages": [
            {"role": "system", "content": system_prompt or EXTRACTION_SYSTEM_PROMPT},
            {"role": "user", "content": user_text},
        ],
    }

    if is_reasoner:
        # deepseek-reasoner ignores temperature/top_p; omit them.
        pass
    elif is_chatglm:
        # ChatGLM supports temperature (default 0.95).  Set to 0 for
        # deterministic JSON output.  Enable JSON mode so the model is
        # forced to produce valid JSON — critical for ontology extraction
        # where the output must be machine-parseable.
        api_kwargs["temperature"] = 0
        api_kwargs["response_format"] = {"type": "json_object"}
    elif is_ollama:
        # Ollama: temperature=0, no DeepSeek-specific extra_body.
        # JSON mode via response_format if the model supports it.
        api_kwargs["temperature"] = 0
    else:
        # deepseek-chat: disable thinking so the model returns only the
        # final answer with no reasoning overhead.
        api_kwargs["temperature"] = 0
        api_kwargs["extra_body"] = {"thinking": {"type": "disabled"}}

    client = OpenAI(api_key=api_key, base_url=base_url, timeout=120.0)

    try:
        response = client.chat.completions.create(**api_kwargs)
    except Exception as e:
        raise RuntimeError(f"OpenAI-compatible API error: {e}") from e

    choice = response.choices[0]

    # Check for truncation (finish_reason == "length" means max_tokens hit).
    finish = getattr(choice, "finish_reason", None)
    if finish == "length":
        print(
            f"[WARNING] LLM response truncated (finish_reason='length'). "
            f"max_tokens={max_tokens} was too small for the output. "
            f"Consider increasing max_tokens or splitting the input.",
            file=sys.stderr,
        )

    # ---- extract the response text ----
    raw_text = ""

    # DeepSeek-R1 returns reasoning_content separately; ChatGLM does not.
    if hasattr(choice, "message"):
        msg = choice.message
        raw_text = msg.content or ""
        reasoning_len = len(getattr(msg, "reasoning_content", "") or "")
        if reasoning_len > 0:
            print(
                f"[DEBUG] R1 reasoning_content length={reasoning_len}, "
                f"content length={len(raw_text)}",
                file=sys.stderr,
            )
    else:
        raw_text = getattr(choice, "text", "") or ""

    if not raw_text or not raw_text.strip():
        print(f"[DEBUG] LLM returned empty content. Model: {model}", file=sys.stderr)
        print(f"[DEBUG] finish_reason={finish}", file=sys.stderr)
        print(f"[DEBUG] Full response: {response}", file=sys.stderr)
        if finish == "length":
            raise RuntimeError(
                "LLM response was truncated because max_tokens was too small. "
                "The input text may be too long — try splitting it into smaller "
                "sections, or increase max_tokens in the code."
            )
        if is_reasoner and finish == "stop":
            raise RuntimeError(
                "DeepSeek-R1 returned empty content. "
                "This usually means the reasoning (CoT) consumed the entire "
                "max_tokens budget before the model could write the final JSON. "
                "Increase max_tokens (currently 32768), or switch to "
                "'deepseek-chat' which produces only the final answer "
                "without reasoning overhead."
            )
        raise RuntimeError(
            "LLM returned empty content. "
            "This may happen if the API key is invalid or the model refused to answer. "
            "Check your API key in config.json or environment variables."
        )

    data = _parse_json_response(raw_text)
    warnings = validate_extracted_ontology(data)
    return data, warnings


def _extract_gemini(
    user_text: str,
    model: str,
    api_key: str,
    system_prompt: str = "",
) -> tuple[dict, list[str]]:
    """Extract using Google Gemini API.

    Tries the new ``google.genai`` SDK first, then falls back to the
    deprecated ``google.generativeai`` package.

    Gemini model families and their limits
    --------------------------------------
    - **Gemini 2.0 Flash** (``gemini-2.0-flash``): 1M context,
      ``max_output_tokens`` capped at **8,192**.  No thinking mode.
    - **Gemini 2.5 Flash/Pro**: 1M context, ``max_output_tokens`` up to
      **65,536**.  Supports thinking via ``thinking_budget`` (token count).
      Thinking tokens are billed as output AND consume the
      ``max_output_tokens`` budget — if thinking exhausts it, the final
      answer comes back empty (a known footgun; see googleapis/python-genai
      issue #782).
    - **Gemini 3 Flash/Pro**: 1M context, ``max_output_tokens`` up to
      65,536.  Uses ``thinking_level`` ("minimal" / "low" / "high")
      instead of ``thinking_budget``.  ``"minimal"`` disables thinking
      on Flash models for lowest latency.

    All models support ``response_mime_type: "application/json"`` for
    structured JSON output (added in Gemini 1.5).
    """
    import sys

    prompt = system_prompt or EXTRACTION_SYSTEM_PROMPT
    input_len = len(user_text)

    # ---- detect model family and set caps ----
    model_lower = model.lower()
    is_gemini_3 = "gemini-3" in model_lower or "gemini-3." in model_lower
    is_gemini_25 = "gemini-2.5" in model_lower
    is_gemini_20 = "gemini-2.0" in model_lower

    if is_gemini_20:
        # Gemini 2.0 Flash: output capped at 8192
        max_out = 8192
    elif is_gemini_25 or is_gemini_3:
        # 2.5 / 3: output up to 65536; use generous but safe values
        max_out = 32768 if input_len > 3000 else 16384
    else:
        # Unknown / future models — conservative
        max_out = 8192 if input_len > 1000 else 4096

    print(f"[DEBUG] _extract_gemini: model={model}, input_len={input_len}, "
          f"max_out={max_out}, family={'3' if is_gemini_3 else '2.5' if is_gemini_25 else '2.0' if is_gemini_20 else 'unknown'}",  # noqa: E501
          file=sys.stderr)

    # ---- Try new google.genai SDK (recommended) ----
    try:
        from google import genai
    except ImportError:
        genai = None  # type: ignore[assignment]

    if genai is not None:
        try:
            from google.genai import types as genai_types

            client = genai.Client(api_key=api_key,
                                  http_options={"timeout": 180000})

            # Build GenerateContentConfig
            config_dict: dict = {
                "system_instruction": prompt,
                "temperature": 0,
                "max_output_tokens": max_out,
                # JSON mode: force model to produce valid JSON.
                # Supported since Gemini 1.5 — critical for ontology
                # extraction where output must be machine-parseable.
                "response_mime_type": "application/json",
            }

            # ---- thinking config for 2.5+ models ----
            # Disable or minimise thinking so reasoning tokens don't
            # consume the max_output_tokens budget.  For ontology
            # extraction we want the final JSON, not a CoT trace.
            if is_gemini_25:
                # 2.5 models: thinking_budget=0 disables thinking
                config_dict["thinking_config"] = genai_types.ThinkingConfig(
                    thinking_budget=0,
                )
            elif is_gemini_3:
                # 3.x models: thinking_level="minimal" (Flash only —
                # Pro models may ignore this).
                config_dict["thinking_config"] = genai_types.ThinkingConfig(
                    thinking_level="minimal",
                )

            response = client.models.generate_content(
                model=model,
                contents=user_text,
                config=config_dict,
            )

            raw_text = response.text or ""
            if not raw_text.strip():
                # Check if the model thought instead of answering
                thought_len = 0
                try:
                    for part in (response.candidates or [None])[0].content.parts if response.candidates else []:  # type: ignore[union-attr]
                        if getattr(part, "thought", False):
                            thought_len += len(part.text or "")
                except Exception:
                    pass
                print(f"[DEBUG] Gemini returned empty text. "
                      f"thought_chars={thought_len}", file=sys.stderr)
                if thought_len > 0:
                    raise RuntimeError(
                        "Gemini returned empty content — thinking consumed "
                        "the entire max_output_tokens budget. "
                        "Increase max_output_tokens or disable thinking "
                        "(set thinking_budget=0 or thinking_level='minimal')."
                    )
                raise RuntimeError(
                    "Gemini returned empty content. "
                    "Check your API key in config.json or the "
                    "GEMINI_API_KEY environment variable."
                )
            data = _parse_json_response(raw_text)
            warnings = validate_extracted_ontology(data)
            return data, warnings
        except Exception as e:
            raise RuntimeError(f"Gemini API error: {e}") from e

    # ---- Fall back to deprecated google-generativeai ----
    try:
        import google.generativeai as legacy_genai
    except ImportError:
        raise RuntimeError(
            "No Gemini SDK available. Install one of:\n"
            "  pip install google-genai         (recommended)\n"
            "  pip install google-generativeai  (legacy)"
        )

    legacy_genai.configure(api_key=api_key)
    try:
        gemini_model = legacy_genai.GenerativeModel(model)
        # The legacy SDK has no native system-message role
        full_prompt = f"{prompt}\n\n---\n\nUser description:\n{user_text}"
        response = gemini_model.generate_content(
            full_prompt,
            generation_config={
                "temperature": 0,
                "max_output_tokens": max_out,
                "response_mime_type": "application/json",
            },
            request_options={"timeout": 180000},
        )
    except Exception as e:
        raise RuntimeError(f"Gemini API error: {e}") from e

    raw_text = response.text or ""
    if not raw_text or not raw_text.strip():
        import sys
        print(f"[DEBUG] Gemini (legacy SDK) returned empty content. "
              f"Model: {model}", file=sys.stderr)
        raise RuntimeError(
            "Gemini returned empty content. "
            "Check your API key in config.json or the "
            "GEMINI_API_KEY environment variable."
        )
    data = _parse_json_response(raw_text)
    warnings = validate_extracted_ontology(data)
    return data, warnings


def _extract_anthropic(
    user_text: str,
    model: str,
    api_key: str,
    system_prompt: str = "",
) -> tuple[dict, list[str]]:
    """Extract using Anthropic Claude API."""
    try:
        import anthropic
    except ImportError:
        raise RuntimeError(
            "The 'anthropic' package is required for Claude. "
            "Install with: pip install anthropic"
        )

    client = anthropic.Anthropic(api_key=api_key, timeout=120.0)

    # Scale max_tokens with input size — long inputs produce large ontologies.
    input_len = len(user_text)
    if input_len > 3000:
        max_tokens = 16384
    elif input_len > 1000:
        max_tokens = 8192
    else:
        max_tokens = 4096

    try:
        message = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=0,
            system=system_prompt or EXTRACTION_SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": user_text},
            ],
        )
    except anthropic.APIError as e:
        raise RuntimeError(f"Anthropic API error: {e}") from e
    except anthropic.APIConnectionError as e:
        raise RuntimeError(
            f"Could not connect to Anthropic API. Check your network: {e}"
        ) from e

    raw_text = message.content[0].text
    if not raw_text or not raw_text.strip():
        import sys
        print(f"[DEBUG] Claude returned empty content. Model: {model}", file=sys.stderr)
        raise RuntimeError(
            "Claude returned empty content. "
            "Check your API key in config.json or the ANTHROPIC_API_KEY environment variable."
        )
    data = _parse_json_response(raw_text)
    warnings = validate_extracted_ontology(data)
    return data, warnings


# ---------------------------------------------------------------------------
# Main entry point — routes to the correct provider
# ---------------------------------------------------------------------------

def extract_ontology_from_text(
    user_text: str,
    provider: str = "deepseek",
    model: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    system_prompt: str = "",
) -> tuple[dict, list[str]]:
    """Extract ontology elements from natural language using an LLM.

    Args:
        user_text: Natural language domain description.
        provider: One of ``"deepseek"``, ``"chatglm"``, ``"anthropic"``.
        model: Model ID. Provider-specific (e.g. ``"deepseek-chat"``,
               ``"glm-4-flash"``).
        api_key: API key for the provider. Required.
        base_url: Base URL for OpenAI-compatible providers (DeepSeek, ChatGLM).
        system_prompt: Custom system prompt. Falls back to the built-in
                       ``EXTRACTION_SYSTEM_PROMPT`` if empty.

    Returns:
        Tuple of ``(extracted_data, warnings)``.

    Raises:
        ValueError: If ``api_key`` is missing or ``provider`` is unknown.
        RuntimeError: If the LLM call fails.
        json.JSONDecodeError: If the LLM output cannot be parsed as JSON.
    """
    if not api_key:
        raise ValueError(
            f"API key is required for provider '{provider}'. "
            f"Set it in config.json or the {provider.upper()}_API_KEY "
            f"environment variable."
        )

    if model is None:
        raise ValueError(
            f"Model ID is required for provider '{provider}'. "
            f"Set it in config.json or pass it explicitly."
        )

    provider = provider.lower().strip()

    if provider in ("deepseek", "chatglm", "ollama"):
        if not base_url:
            raise ValueError(
                f"base_url is required for '{provider}'. "
                f"Set it in config.json."
            )
        return _extract_openai_compatible(
            user_text, model, api_key, base_url, system_prompt, provider=provider,
        )
    elif provider == "gemini":
        return _extract_gemini(user_text, model, api_key, system_prompt)
    elif provider == "anthropic":
        return _extract_anthropic(user_text, model, api_key, system_prompt)
    else:
        raise ValueError(
            f"Unknown provider: '{provider}'. "
            f"Supported: deepseek, chatglm, gemini, anthropic, ollama."
        )
