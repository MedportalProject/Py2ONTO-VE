# _*_ coding:utf-8 _*_
# coding:unicode_escape
#########################################################################
# > File Name: py2onto.py
# > Author: WANG Zhe
# > Mail: py2onto@outlook.com
# > Py2ONTO is a Python Package to create owl format file base on owlready2
#########################################################################

import argparse
import json
import os
import types
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

import pandas as pd
from owlready2 import (
    AllDisjoint,
    AnnotationProperty,
    AsymmetricProperty,
    FunctionalProperty,
    InverseFunctionalProperty,
    IrreflexiveProperty,
    ObjectProperty,
    ReflexiveProperty,
    SymmetricProperty,
    Thing,
    TransitiveProperty,
    get_ontology,
    locstr,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MEDPORTAL_REST_URL = "http://medportal.bmicc.cn:8080"
MEDPORTAL_API_KEY = ""  # Set in config.json (medportal.api_key) or MEDPORTAL_API_KEY env var
BIOPORTAL_REST_URL = "http://data.bioontology.org"
BIOPORTAL_API_KEY = ""  # Set in config.json (bioportal.api_key) or BIOPORTAL_API_KEY env var


def _load_portal_config() -> dict:
    """Try to load MedPortal/BioPortal keys from a config.json file.

    Searches in the same directory as this module, then in a ``visual_py2onto``
    subdirectory.  Returns an empty dict on failure so the hardcoded defaults
    above are preserved as fallback values.
    """
    try:
        here = os.path.dirname(os.path.abspath(__file__))
        candidates = [
            os.path.join(here, "config.json"),
            os.path.join(here, "visual_py2onto", "config.json"),
        ]
        for cfg_path in candidates:
            if os.path.exists(cfg_path):
                with open(cfg_path, "r", encoding="utf-8") as f:
                    return json.load(f)
    except Exception:
        pass
    return {}


_portal_cfg = _load_portal_config()
if _portal_cfg:
    MEDPORTAL_REST_URL = _portal_cfg.get("medportal", {}).get("url") or MEDPORTAL_REST_URL
    MEDPORTAL_API_KEY = _portal_cfg.get("medportal", {}).get("api_key") or MEDPORTAL_API_KEY
    BIOPORTAL_REST_URL = _portal_cfg.get("bioportal", {}).get("url") or BIOPORTAL_REST_URL
    BIOPORTAL_API_KEY = _portal_cfg.get("bioportal", {}).get("api_key") or BIOPORTAL_API_KEY


# ---------------------------------------------------------------------------
# Main ontology builder class
# ---------------------------------------------------------------------------

class Py2ONTO(object):
    """Main class for building OWL ontologies programmatically or from CSV templates."""

    def __init__(self, onto_iri: str):
        self.onto = get_ontology(onto_iri)
        self.user_defined_iri = onto_iri
        assert self._is_legal_iri(onto_iri), (
            f"Invalid IRI '{onto_iri}' — must match pattern: "
            "http://example.com/your-ontology.owl#"
        )
        self.onto.base_iri = onto_iri
        self.Thing = Thing

        self._classes: Dict[str, Any] = {"Thing": self.Thing}
        self._class_iris: Dict[str, str] = {}
        self._class_sources: Dict[str, str] = {}
        self._individuals: Dict[str, Any] = {}
        self._object_properties: Dict[str, Any] = {}
        self._annotation_properties: Dict[str, Any] = {}

        self._class_object_properties: Dict[str, Dict[str, str]] = {}
        self._individual_object_properties: Dict[str, Dict[str, str]] = {}

        self._ap_template_values: Dict[str, Dict[str, str]] = {}
        self._ap_template_domains: Dict[str, str] = {}
        self._ap_template_ranges: Dict[str, str] = {}

        self._op_template_domains: Dict[str, str] = {}
        self._op_template_ranges: Dict[str, str] = {}
        self._op_equivalent_to: Dict[str, str] = {}
        self._op_subproperty_of: Dict[str, str] = {}
        self._op_inverse_of: Dict[str, str] = {}
        self._op_disjoint_with: Dict[str, str] = {}

        self.add_standard_ap()

    # -----------------------------------------------------------------------
    # Standard / cross-reference annotation properties
    # -----------------------------------------------------------------------

    def add_xref_ap(self, xref_uri: str, ap_id: str, ap_label: str) -> None:
        """Add a cross-reference annotation property from an external source."""
        self.onto.base_iri = xref_uri
        x_ap = self._create_annotation_property(ap_id)
        x_ap.label = ap_label
        self.onto.base_iri = self.user_defined_iri

    def add_standard_ap(self) -> None:
        """Add standard cross-reference annotation properties (e.g. from GO)."""
        self.add_xref_ap(
            "http://www.geneontology.org/formats/oboInOwl#",
            "hasDbXref",
            "database_cross_reference",
        )

    # -----------------------------------------------------------------------
    # Template file creation
    # -----------------------------------------------------------------------

    def create_template_file(self, save_path: str = "./") -> None:
        """Create empty CSV template files for all entity types."""
        ap_cols = ["ID", "label", "comment", "domain", "range", "*definition"]
        op_cols = [
            "ID", "label", "comment",
            "FunctionalProperty", "InverseFunctionalProperty",
            "TransitiveProperty", "SymmetricProperty", "AsymmetricProperty",
            "ReflexiveProperty", "IrreflexiveProperty",
            "equivalent_to", "subproperty_of", "inverse_of",
            "domain", "range", "disjoint_with", "*definition",
        ]
        class_cols = ["Parent_Class", "ID", "label", "IRI", "comment", "*definition"]
        individual_cols = ["Types", "relation", "ID", "label", "comment", "*definition"]

        pd.DataFrame(columns=ap_cols).to_csv(
            save_path + "templateAP.csv", index=False, encoding="utf-8"
        )
        pd.DataFrame(columns=op_cols).to_csv(
            save_path + "templateOP.csv", index=False, encoding="utf-8"
        )
        pd.DataFrame(columns=class_cols).to_csv(
            save_path + "templateCLASS.csv", index=False, encoding="utf-8"
        )
        pd.DataFrame(columns=individual_cols).to_csv(
            save_path + "templateINDIVIDUAL.csv", index=False, encoding="utf-8"
        )

    # -----------------------------------------------------------------------
    # Main workflow: init (classes) and build (individuals)
    # -----------------------------------------------------------------------

    def init(self, core_template_path: str) -> None:
        """Initialize ontology class structure from a CSV template.

        Supports two CSV formats:

        *New* (recommended): ``Parent_Class, ID, label, IRI, comment, *definition``
        *Old* (backward-compatible): ``Parent_Class, ID, label, comment, *definition``
        """
        ext = core_template_path.split(".")[-1] if "." in core_template_path else ""
        assert ext == "csv", (
            f"Unsupported file type '.{ext}' — only .csv files are accepted"
        )
        data = self._read_csv_with_encoding_fallback(core_template_path)
        assert len(data) > 0, "CSV file is empty — no data rows found"

        cols = list(data.keys())
        assert cols[0] == "Parent_Class", (
            f"CSV header mismatch in class template: "
            f"expected 'Parent_Class' in column 0, got '{cols[0]}'"
        )
        assert cols[1] == "ID", (
            f"CSV header mismatch in class template: "
            f"expected 'ID' in column 1, got '{cols[1]}'"
        )
        assert cols[2] == "label", (
            f"CSV header mismatch in class template: "
            f"expected 'label' in column 2, got '{cols[2]}'"
        )

        # Detect format: new format has IRI column, old format does not
        if "IRI" in cols:
            assert cols[3] == "IRI", (
                f"CSV header mismatch in class template: "
                f"expected 'IRI' in column 3, got '{cols[3]}'"
            )
            assert cols[4] == "comment", (
                f"CSV header mismatch in class template: "
                f"expected 'comment' in column 4, got '{cols[4]}'"
            )
            assert cols[5] == "*definition", (
                f"CSV header mismatch in class template: "
                f"expected '*definition' in column 5, got '{cols[5]}'"
            )
            rule_num = 5
        else:
            assert cols[3] == "comment", (
                f"CSV header mismatch in class template: "
                f"expected 'comment' in column 3, got '{cols[3]}'"
            )
            assert cols[4] == "*definition", (
                f"CSV header mismatch in class template: "
                f"expected '*definition' in column 4, got '{cols[4]}'"
            )
            rule_num = 4

        self._create_properties_from_columns(cols)
        self._build_class_hierarchy(self._clean_dataframe_values(data, rule_num), rule_num)

    def build(self, data_path: str) -> None:
        """Build individuals into the ontology from a CSV template."""
        ext = data_path.split(".")[-1] if "." in data_path else ""
        assert ext == "csv", (
            f"Unsupported file type '.{ext}' — only .csv files are accepted"
        )
        data = self._read_csv_with_encoding_fallback(data_path)
        assert len(data) > 0, "CSV file is empty — no data rows found"

        cols = list(data.keys())
        assert cols[0] == "Types", (
            f"CSV header mismatch in individual template: "
            f"expected 'Types' in column 0, got '{cols[0]}'"
        )
        assert cols[1] == "relation", (
            f"CSV header mismatch in individual template: "
            f"expected 'relation' in column 1, got '{cols[1]}'"
        )
        assert cols[2] == "ID", (
            f"CSV header mismatch in individual template: "
            f"expected 'ID' in column 2, got '{cols[2]}'"
        )
        assert cols[3] == "label", (
            f"CSV header mismatch in individual template: "
            f"expected 'label' in column 3, got '{cols[3]}'"
        )
        assert cols[4] == "comment", (
            f"CSV header mismatch in individual template: "
            f"expected 'comment' in column 4, got '{cols[4]}'"
        )
        assert cols[5] == "*definition", (
            f"CSV header mismatch in individual template: "
            f"expected '*definition' in column 5, got '{cols[5]}'"
        )

        self._create_properties_from_columns(cols)
        self._build_instances(self._clean_dataframe_values(data, 5), cols)

    # -----------------------------------------------------------------------
    # Search helpers
    # -----------------------------------------------------------------------

    def search_class_by_name(self, class_label: str) -> Optional[Any]:
        """Search for a class by its label in the ontology."""
        return self.onto.search_one(label=class_label)

    # -----------------------------------------------------------------------
    # Internal: class operations
    # -----------------------------------------------------------------------

    def _add_class(
        self,
        name: str,
        en_label: str,
        super_class: Any,
        comment_value: str = "",
        iri: str = "",
        source: str = "local",
        **kwargs: Any,
    ) -> Any:
        """Add a new class or extend an existing one with a super-class.

        When *iri* is non-empty, the class's IRI is explicitly set rather
        than being auto-derived from the ontology base IRI.  This is the
        mechanism for reusing classes from external ontologies (e.g. OLS).
        """
        if name in self._classes:
            self._classes[name].is_a.append(super_class)
            return self._classes[name]

        with self.onto:
            new_class = types.new_class(name, (super_class,))
            new_class.label = [locstr(en_label, lang="en")]
            if iri:
                new_class.iri = iri
            if comment_value:
                new_class.comment = comment_value
            if kwargs:
                new_ap_dict = kwargs.get("new_ap", {})
                for key, val in new_ap_dict.items():
                    if key in self._annotation_properties and val != "" and not pd.isna(val):
                        setattr(new_class, key, val)

        self._classes[name] = new_class
        self._class_iris[name] = iri
        self._class_sources[name] = source
        # owlready2 may derive a different .name from the IRI fragment
        # (e.g. table ID "NCIT_C2923" but IRI ".../Thesaurus.owl#C2923"
        #  gives cls.name == "C2923").  Store under both names so that
        # _build_tree (which iterates onto.classes() and uses cls.name)
        # can find the correct source/IRI badge.
        actual_name = new_class.name
        if actual_name != name:
            self._classes[actual_name] = new_class
            self._class_iris[actual_name] = iri
            self._class_sources[actual_name] = source
        return new_class

    def add_class(
        self,
        name: str,
        en_label: str,
        super_class: Any,
        comment_value: str = "",
        iri: str = "",
        source: str = "local",
        **kwargs: Any,
    ) -> Any:
        """Public: add a new class or extend an existing one."""
        return self._add_class(name, en_label, super_class, comment_value,
                               iri=iri, source=source, **kwargs)

    def build_reused_class(
        self,
        name: str,
        en_label: str,
        super_class: Any,
        iri: str,
        source: str = "OLS",
        comment_value: str = "",
    ) -> Any:
        """Build a class that reuses an external ontology term.

        This is the recommended way to incorporate standard ontology classes
        (e.g. from OLS, NCIT, SNOMED) into the local ontology.  The external
        IRI is preserved so OWL consumers understand that the class is the
        *same* entity, not a new local one.

        Args:
            name: Local short name (e.g. ``"DOID_1324"``).
            en_label: Human-readable label (e.g. ``"lung cancer"``).
            super_class: Parent class (owlready2 class or ``Thing``).
            iri: The canonical IRI of the reused class.
            source: Provenance label (default ``"OLS"``).
            comment_value: Optional description.

        Returns:
            The created (or extended) owlready2 class.
        """
        return self._add_class(
            name, en_label, super_class,
            comment_value=comment_value,
            iri=iri,
            source=source,
        )

    # -----------------------------------------------------------------------
    # Internal: object property operations
    # -----------------------------------------------------------------------

    def _set_object_property_values(self, itemA: Any, ob_name: Any, values: List[Any]) -> None:
        """Set object property values on an entity (replaces existing list)."""
        setattr(itemA, ob_name.__name__, values)

    def _add_object_property_relationship(self, itemA: Any, ob_name: Any, itemB: Any) -> None:
        """Add a single object property relationship: itemA --ob_name--> itemB.

        ``ob_name`` can be a string (looked up / created on the fly) or an
        owlready2 ObjectProperty class.
        """
        # Resolve ob_name to an ObjectProperty class
        if isinstance(ob_name, str):
            if ob_name in self._object_properties:
                ob = self._object_properties[ob_name]
            else:
                ob = self._create_object_property(ob_name)
        else:
            # Already an owlready2 property class (e.g. from $ column)
            ob = ob_name

        ob_list = getattr(itemA, ob.__name__)
        if ob_list is not None:
            if isinstance(ob_list, list):
                ob_list.append(itemB)
            else:
                ob_list = [ob_list, itemB]
            setattr(itemA, ob.__name__, ob_list)
        else:
            setattr(itemA, ob.__name__, [itemB])

    def _add_individual_object_property_relationship(
        self, itemA: Any, ob_name: Any, itemB: Any
    ) -> None:
        """Add a single object property relationship for an individual.

        Uses ``with self.onto`` block to work around owlready2 functional
        property quirks.

        ``ob_name`` can be a string (looked up / created on the fly) or an
        owlready2 ObjectProperty class.
        """
        # Resolve ob_name to an ObjectProperty class
        if isinstance(ob_name, str):
            if ob_name in self._object_properties:
                ob = self._object_properties[ob_name]
            else:
                ob = self._create_object_property(ob_name)
        else:
            ob = ob_name

        try:
            with self.onto:
                ob_list = getattr(itemA, ob.__name__)
            if ob_list is not None and len(ob_list) > 0:
                ob_list = list(ob_list)
                ob_list.append(itemB)
                setattr(itemA, ob.__name__, ob_list)
            else:
                setattr(itemA, ob.__name__, [itemB])
        except Exception as e:
            itemA_name = getattr(itemA, "name", str(itemA))
            ob_name_str = getattr(ob, "__name__", str(ob))
            print(
                f"[WARNING] Failed to add object property relationship: "
                f"{itemA_name} --{ob_name_str}--> {itemB}. "
                f"Error: {e}"
            )
            assert str(e) == "'list' object has no attribute 'storid'", (
                f"Object Property '{ob_name_str}' is incorrectly defined! "
                "Check its functional property characteristics."
            )

    # -----------------------------------------------------------------------
    # Internal: individual operations
    # -----------------------------------------------------------------------

    def _add_individual(
        self,
        class_name: str,
        name: str,
        en_label: str,
        comment_value: str = "",
        **kwargs: Any,
    ) -> Any:
        """Add a new individual (instance) of a class."""
        assert class_name != name, (
            f"Name conflict: individual '{name}' cannot have the same name as its class '{class_name}'"
        )
        assert class_name in self._classes, (
            f"Class '{class_name}' (referenced by individual '{name}') "
            f"is not defined — add it to the class table first"
        )

        if class_name.strip() in self._classes:
            father_class = self._classes[class_name]
        else:
            father_class = self.search_class_by_name(class_name.strip())
        assert father_class, (
            f"Parent class '{class_name}' not found — "
            f"add it to the class table before creating individuals of this type"
        )

        new_instance = father_class(name, namespace=self.onto)
        new_instance.label = [locstr(en_label, lang="en")]
        if comment_value:
            new_instance.comment = comment_value

        if kwargs:
            new_ap_dict = kwargs.get("new_ap", {})
            for key, val in new_ap_dict.items():
                if key in self._annotation_properties and val != "":
                    setattr(new_instance, key, val)

        self._individuals[name] = new_instance
        return new_instance

    def add_individual(
        self,
        classA: str,
        name: str,
        en_label: str,
        comment_value: str = "",
        **kwargs: Any,
    ) -> Any:
        """Public: add a new individual (instance) of a class."""
        return self._add_individual(classA, name, en_label, comment_value, **kwargs)

    # -----------------------------------------------------------------------
    # Object property creation (from CSV template)
    # -----------------------------------------------------------------------

    def _create_object_property_by_template(self, object_property_path: str) -> None:
        """Create object properties from a CSV template file."""
        ext = object_property_path.split(".")[-1] if "." in object_property_path else ""
        assert ext == "csv", (
            f"Unsupported file type '.{ext}' — only .csv files are accepted"
        )
        data = self._read_csv_with_encoding_fallback(object_property_path)
        assert len(data) > 0, "CSV file is empty — no data rows found"

        cols = list(data.keys())
        expected = [
            "ID", "label", "comment",
            "FunctionalProperty", "InverseFunctionalProperty",
            "TransitiveProperty", "SymmetricProperty", "AsymmetricProperty",
            "ReflexiveProperty", "IrreflexiveProperty",
            "equivalent_to", "subproperty_of", "inverse_of",
            "domain", "range", "disjoint_with", "*definition",
        ]
        for i, exp in enumerate(expected):
            assert i < len(cols) and cols[i] == exp, (
                f"CSV header mismatch in object property template: "
                f"expected '{exp}' in column {i}, got '{cols[i] if i < len(cols) else '<missing>'}'"
            )

        for _, row in data.iterrows():
            self._create_object_property_from_row(row, cols)

        self._apply_object_property_template_relationships()

    def _create_object_property_from_row(self, row: Any, col_keys: List[str]) -> None:
        """Parse one row of the object property template and create the property."""
        function_types = [
            FunctionalProperty, InverseFunctionalProperty, TransitiveProperty,
            SymmetricProperty, AsymmetricProperty, ReflexiveProperty, IrreflexiveProperty,
        ]
        name = row.iloc[0]
        label = row.iloc[1]
        comment_value = "" if pd.isna(row.iloc[2]) else row.iloc[2]

        func_na = [pd.isna(row.iloc[i]) for i in range(3, 10)]
        active_functions = [f for f, na in zip(function_types, func_na) if not na]

        domain = "" if pd.isna(row.iloc[13]) else row.iloc[13]
        range_ = "" if pd.isna(row.iloc[14]) else row.iloc[14]

        if not pd.isna(row.iloc[10]):
            self._op_equivalent_to[name] = row.iloc[10]
        if not pd.isna(row.iloc[11]):
            self._op_subproperty_of[name] = row.iloc[11]
        if not pd.isna(row.iloc[12]):
            self._op_inverse_of[name] = row.iloc[12]
        if not pd.isna(row.iloc[15]):
            self._op_disjoint_with[name] = row.iloc[15]

        if domain:
            self._op_template_domains[name] = domain
        if range_:
            self._op_template_ranges[name] = range_

        op = self._create_object_property(
            object_property_name=name,
            result_function_list=active_functions,
            label=label,
            comment_value=comment_value,
            domain=domain,
            range=range_,
        )

        # Handle user-defined annotation properties beyond the standard columns
        if len(col_keys) > 16:
            for col in col_keys[16:]:
                if col.startswith("*") and not pd.isna(row[col]):
                    ap_key = col[1:]
                    if ap_key in self._annotation_properties:
                        ap = self._annotation_properties[ap_key]
                    else:
                        ap = self._create_annotation_property(ap_key)
                    setattr(op, ap.__name__, row[col])

    def _apply_object_property_template_relationships(self) -> None:
        """Resolve and apply object property relationships (equivalent, inverse, etc.)."""
        for mapping_name, store in [
            ("equivalent_to", self._op_equivalent_to),
            ("subproperty_of", self._op_subproperty_of),
            ("inverse_of", self._op_inverse_of),
            ("disjoint_with", self._op_disjoint_with),
        ]:
            for key, val in store.items():
                if "&" in val:
                    for part in val.split("&"):
                        self._set_object_property_characteristics(key, mapping_name, part)
                else:
                    self._set_object_property_characteristics(key, mapping_name, val)

    def _set_object_property_characteristics(
        self, opA: Any, characteristic: str, opB: Any
    ) -> None:
        """Set a relationship between two object properties."""
        if not isinstance(opA, ObjectProperty):
            if opA in self._object_properties:
                opA = self._object_properties[opA]
            else:
                opA = self._create_object_property(opA)

        if not isinstance(opB, ObjectProperty):
            if opB in self._object_properties:
                opB = self._object_properties[opB]
            else:
                opB = self._create_object_property(opB)

        if characteristic == "equivalent_to":
            opA.equivalent_to.append(opB)
        elif characteristic == "subproperty_of":
            opA.is_a.append(opB)
        elif characteristic == "inverse_of":
            opA.inverse_property = opB
        elif characteristic == "disjoint_with":
            AllDisjoint([opA, opB])

    # -----------------------------------------------------------------------
    # Object property domain / range
    # -----------------------------------------------------------------------

    def _set_object_property_domains_from_template(self, key: str, domain_value: str) -> None:
        """Parse and set object property domains from template data."""
        if "&" in domain_value:
            for item in domain_value.split("&"):
                self._set_object_property_domain(key, item)
        else:
            self._set_object_property_domain(key, domain_value)

    def _set_object_property_domain(self, key: str, domain_class_name: str) -> None:
        """Set a single domain class for an object property."""
        assert domain_class_name in self._classes, (
            f"Domain class '{domain_class_name}' (used by object property '{key}') "
            f"is not defined — add it to the class table first"
        )
        op = self._object_properties[key]
        domain_class = self._classes[domain_class_name]
        op._domain.append(domain_class)

    def _set_object_property_ranges_from_template(self, key: str, range_value: str) -> None:
        """Parse and set object property ranges from template data."""
        if "&" in range_value:
            for item in range_value.split("&"):
                self._set_object_property_range(key, item)
        else:
            self._set_object_property_range(key, range_value)

    def _set_object_property_range(self, key: str, range_class_name: str) -> None:
        """Set a single range class for an object property."""
        assert range_class_name in self._classes, (
            f"Range class '{range_class_name}' (used by object property '{key}') "
            f"is not defined — add it to the class table first"
        )
        assert key != range_class_name, (
            f"Object property '{key}' has the same name as its range class — "
            f"consider renaming one of them"
        )
        op = self._object_properties[key]
        range_class = self._classes[range_class_name]
        op._range.append(range_class)

    # -----------------------------------------------------------------------
    # Object property creation (low-level)
    # -----------------------------------------------------------------------

    def _create_object_property(
        self,
        object_property_name: str,
        **kwargs: Any,
    ) -> Any:
        """Create a new object property in the ontology."""
        with self.onto:
            base = (ObjectProperty,)
            if kwargs.get("result_function_list"):
                base = base + tuple(kwargs["result_function_list"])
            new_op = types.new_class(object_property_name, base)

            if "label" in kwargs:
                new_op.label = [locstr(kwargs["label"])]

            comment = kwargs.get("comment_value")
            if comment:
                new_op.comment = comment

            # Always initialise domain/range so iterating them elsewhere
            # never hits a bare None (e.g. auto-created via $ column prefix).
            new_op.domain = []
            new_op.range = []

        self._object_properties[object_property_name] = new_op
        return new_op

    def create_object_property(self, object_property_name: str, **kwargs: Any) -> Any:
        """Public: create a new object property."""
        return self._create_object_property(object_property_name, **kwargs)

    # -----------------------------------------------------------------------
    # Object property creation (programmatic API)
    # -----------------------------------------------------------------------

    def create_op(
        self,
        object_property_name: str,
        label: str,
        comment_value: str = "",
        **kwargs: Any,
    ) -> Any:
        """Create an object property with full configuration.

        Supported keyword arguments:
            function_list : list of 0/1 flags for functional characteristics
            label, equ, sub, inv, domain, range, dis
            Any other key is treated as a user-defined annotation property.
        """
        with self.onto:
            function_types = [
                FunctionalProperty, InverseFunctionalProperty, TransitiveProperty,
                SymmetricProperty, AsymmetricProperty, ReflexiveProperty, IrreflexiveProperty,
            ]
            base = (ObjectProperty,)
            func_flags = kwargs.get("function_list")
            if func_flags is not None:
                assert isinstance(func_flags, list), (
                    f"Object property '{object_property_name}': "
                    f"function_list must be a list, got {type(func_flags).__name__}"
                )
                active = [f for f, flag in zip(function_types, func_flags) if flag == 1]
                if active:
                    base = base + tuple(active)

            new_op = types.new_class(object_property_name, base)
            if comment_value:
                new_op.comment = comment_value

            if kwargs:
                for item, val in kwargs.items():
                    if item == "function_list":
                        continue
                    elif item == "label":
                        new_op.label = [locstr(val)]
                    elif item == "equ":
                        self._set_object_property_characteristics(new_op, "equivalent_to", val)
                    elif item == "sub":
                        self._set_object_property_characteristics(new_op, "subproperty_of", val)
                    elif item == "inv":
                        self._set_object_property_characteristics(new_op, "inverse_of", val)
                    elif item == "domain":
                        new_op.domain = []
                        if "&" not in val:
                            self._set_annotation_property_domain_internal(new_op, val)
                        else:
                            for part in val.split("&"):
                                self._set_annotation_property_domain_internal(new_op, part)
                    elif item == "range":
                        new_op.range = []
                        if "&" not in val:
                            self._set_annotation_property_range_internal(new_op, val)
                        else:
                            for part in val.split("&"):
                                self._set_annotation_property_range_internal(new_op, part)
                    elif item == "dis":
                        self._set_object_property_characteristics(new_op, "disjoint_with", val)
                    else:
                        if item in self._annotation_properties:
                            ap = self._annotation_properties[item]
                        else:
                            ap = self._create_annotation_property(item, label=item)
                        setattr(new_op, ap.__name__, val)

        self._object_properties[object_property_name] = new_op
        return new_op

    # -----------------------------------------------------------------------
    # Annotation property creation (from CSV template)
    # -----------------------------------------------------------------------

    def _create_annotation_property_by_template(self, annotation_property_path: str) -> None:
        """Create annotation properties from a CSV template file."""
        ext = annotation_property_path.split(".")[-1] if "." in annotation_property_path else ""
        assert ext == "csv", (
            f"Unsupported file type '.{ext}' — only .csv files are accepted"
        )
        data = self._read_csv_with_encoding_fallback(annotation_property_path)
        assert len(data) > 0, "CSV file is empty — no data rows found"

        cols = list(data.keys())
        expected = ["ID", "label", "comment", "domain", "range", "*definition"]
        for i, exp in enumerate(expected):
            assert i < len(cols) and cols[i] == exp, (
                f"CSV header mismatch in annotation property template: "
                f"expected '{exp}' in column {i}, got '{cols[i] if i < len(cols) else '<missing>'}'"
            )

        for _, row in data.iterrows():
            self._create_annotation_property_from_row(row, cols)

        self._apply_annotation_property_values()

    def _create_annotation_property_from_row(self, row: Any, col_keys: List[str]) -> None:
        """Parse one row of the annotation property template."""
        name = row.iloc[0]
        label = row.iloc[1]
        comment_value = "" if pd.isna(row.iloc[2]) else row.iloc[2]
        domain = "" if pd.isna(row.iloc[3]) else row.iloc[3]
        range_ = "" if pd.isna(row.iloc[4]) else row.iloc[4]
        extra_ap = {}

        if domain:
            self._ap_template_domains[name] = domain
        if range_:
            self._ap_template_ranges[name] = range_

        for col in col_keys[5:]:
            if col.startswith("*") and not pd.isna(row[col]):
                extra_ap[col[1:]] = row[col]

        if extra_ap:
            self._ap_template_values[name] = extra_ap

        self._create_annotation_property(
            name, label=label, comment_value=comment_value, domain=domain, range=range_
        )

    def _apply_annotation_property_values(self) -> None:
        """Set annotation property values on other annotation properties."""
        for ap_name, ap_values in self._ap_template_values.items():
            ap = self._annotation_properties[ap_name]
            for target_ap_name, val in ap_values.items():
                if target_ap_name in self._annotation_properties:
                    target_ap = self._annotation_properties[target_ap_name]
                else:
                    target_ap = self._create_annotation_property(target_ap_name)
                setattr(ap, target_ap.__name__, val)

    # -----------------------------------------------------------------------
    # Annotation property domain / range
    # -----------------------------------------------------------------------

    def _set_annotation_property_domains_from_template(self, key: str, domain_value: str) -> None:
        """Parse and set annotation property domains from template data."""
        if "&" in domain_value:
            for item in domain_value.split("&"):
                self._set_annotation_property_domain_internal(key, item)
        else:
            self._set_annotation_property_domain_internal(key, domain_value)

    def _set_annotation_property_domain_internal(self, key: Any, domain_class_name: str) -> None:
        """Set a single domain class for an annotation (or object) property.

        Accepts both string keys and property objects for flexibility.
        """
        key_name = key if isinstance(key, str) else getattr(key, "__name__", str(key))
        assert domain_class_name in self._classes, (
            f"Domain class '{domain_class_name}' (used by property '{key_name}') "
            f"is not defined — add it to the class table first"
        )
        if isinstance(key, str):
            ap = self._annotation_properties[key]
        else:
            ap = key
        domain_class = self._classes[domain_class_name]
        ap._domain.append(domain_class)

    def _set_annotation_property_ranges_from_template(self, key: str, range_value: str) -> None:
        """Parse and set annotation property ranges from template data."""
        if "&" in range_value:
            for item in range_value.split("&"):
                self._set_annotation_property_range_internal(key, item)
        else:
            self._set_annotation_property_range_internal(key, range_value)

    def _set_annotation_property_range_internal(self, key: Any, range_class_name: str) -> None:
        """Set a single range class for an annotation (or object) property.

        Accepts both string keys and property objects for flexibility.
        """
        key_name = key if isinstance(key, str) else getattr(key, "__name__", str(key))
        assert range_class_name in self._classes, (
            f"Range class '{range_class_name}' (used by property '{key_name}') "
            f"is not defined — add it to the class table first"
        )
        assert key_name != range_class_name, (
            f"Property '{key_name}' has the same name as its range class — "
            f"consider renaming one of them"
        )
        if isinstance(key, str):
            ap = self._annotation_properties[key]
        else:
            ap = key
        range_class = self._classes[range_class_name]
        ap._range.append(range_class)

    # -----------------------------------------------------------------------
    # Annotation property creation (low-level)
    # -----------------------------------------------------------------------

    def _create_annotation_property(
        self,
        annotation_property_name: str,
        **kwargs: Any,
    ) -> Any:
        """Create a new annotation property in the ontology."""
        with self.onto:
            new_ap = types.new_class(annotation_property_name, (AnnotationProperty,))
            if kwargs.get("label"):
                new_ap.label = [locstr(kwargs["label"])]

            comment = kwargs.get("comment_value")
            if comment:
                new_ap.comment = comment

            # Always initialise domain/range so iterating them elsewhere
            # never hits a bare None (e.g. auto-created via * column prefix).
            new_ap.domain = []
            new_ap.range = []

        self._annotation_properties[annotation_property_name] = new_ap
        return new_ap

    def create_annotation_property(self, annotation_property_name: str) -> Any:
        """Public: create an annotation property."""
        with self.onto:
            new_ap = types.new_class(annotation_property_name, (AnnotationProperty,))
            new_ap._range = [str]
        self._annotation_properties[annotation_property_name] = new_ap
        return new_ap

    # -----------------------------------------------------------------------
    # Annotation property creation (programmatic API)
    # -----------------------------------------------------------------------

    def create_ap(
        self,
        ap_name: str,
        label: str,
        comment_value: str = "",
        **kwargs: Any,
    ) -> Any:
        """Create an annotation property with optional domain/range/user-APs."""
        with self.onto:
            new_ap = types.new_class(ap_name, (AnnotationProperty,))
            new_ap.label = [locstr(label)]
            if comment_value:
                new_ap.comment = comment_value

            if kwargs:
                for item, val in kwargs.items():
                    key = item.strip()
                    if key == "domain":
                        new_ap.domain = []
                        if "&" not in val:
                            self._set_annotation_property_domain_internal(new_ap, val)
                        else:
                            for part in val.split("&"):
                                self._set_annotation_property_domain_internal(new_ap, part)
                    elif key == "range":
                        new_ap.range = []
                        if "&" not in val:
                            self._set_annotation_property_range_internal(new_ap, val)
                        else:
                            for part in val.split("&"):
                                self._set_annotation_property_range_internal(new_ap, part)
                    else:
                        if item in self._annotation_properties:
                            ap = self._annotation_properties[item]
                        else:
                            ap = self._create_annotation_property(item, label=item)
                        setattr(new_ap, ap.__name__, val)

        self._annotation_properties[ap_name] = new_ap
        return new_ap

    # -----------------------------------------------------------------------
    # Save
    # -----------------------------------------------------------------------

    def save(self, path: str = "./new_onto.owl") -> None:
        """Save the ontology to a file in RDF/XML format."""
        self.onto.save(file=path, format="rdfxml")

    # -----------------------------------------------------------------------
    # Class hierarchy building
    # -----------------------------------------------------------------------

    def _build_class_hierarchy(self, class_data, rule_num: int = 4) -> None:
        """Build the class hierarchy from pre-processed template data."""
        keys = list(class_data.keys())
        temp_list = []

        for _, row in class_data.iterrows():
            if row.iloc[0] in self._classes:
                father_name, name, en_label, iri, source, comment, ap_dict, op_dict = (
                    self._parse_row_data(rule_num, row, keys)
                )
                father_class = self._classes[father_name]
                self._add_class(name, en_label, father_class, comment,
                                iri=iri, source=source, new_ap=ap_dict)
                if op_dict:
                    self._class_object_properties[name] = op_dict
            else:
                temp_list.append(row)

        if temp_list:
            self._build_class_hierarchy_with_retry(temp_list, keys, rule_num)
        else:
            if self._class_object_properties:
                self._apply_object_property_relationships("class")

    def _build_class_hierarchy_with_retry(
        self, temp_list: List[Any], keys: List[str], rule_num: int = 4,
    ) -> None:
        """Retry building unparented classes over multiple passes."""
        if len(temp_list) > 100:
            for _ in range(100):
                temp_list = self._resolve_unparented_classes(temp_list, keys, rule_num)
            if self._check_legal(temp_list) and self._class_object_properties:
                self._apply_object_property_relationships("class")
        else:
            for _ in range(50):
                temp_list = self._resolve_unparented_classes(temp_list, keys, rule_num)
            if self._check_legal(temp_list) and self._class_object_properties:
                self._apply_object_property_relationships("class")

    def _resolve_unparented_classes(
        self, temp_list: List[Any], keys: List[str], rule_num: int = 4,
    ) -> List[Any]:
        """Try to build classes whose parent was not ready yet."""
        no_father = []
        for item in temp_list:
            if item["Parent_Class"].strip() in self._classes:
                father_name, name, en_label, iri, source, comment, ap_dict, op_dict = (
                    self._parse_row_data(rule_num, item, keys)
                )
                father_class = self._classes[father_name]
                self._add_class(name, en_label, father_class, comment,
                                iri=iri, source=source, new_ap=ap_dict)
                if op_dict:
                    self._class_object_properties[name] = op_dict
            else:
                no_father.append(item)
        return no_father

    def _check_legal(self, temp_list: List[Any]) -> bool:
        """Check that no orphan classes remain after building."""
        error_info = self._format_error_list(temp_list) if temp_list else ""
        n = len(temp_list)
        assert n == 0, (
            f"{n} class(es) have unresolved parent classes — "
            f"check the Parent_Class column: {error_info}"
        )
        return len(temp_list) == 0

    # -----------------------------------------------------------------------
    # Instance building
    # -----------------------------------------------------------------------

    def _build_instances(self, instance_data, keys: List[str]) -> None:
        """Build individuals from pre-processed template data."""
        errors: list[str] = []
        for idx, row in instance_data.iterrows():
            relation = str(row["relation"]).strip() if pd.notna(row["relation"]) else ""

            if not relation:
                name = str(row["ID"]).strip() if pd.notna(row["ID"]) else f"row {idx}"
                errors.append(
                    f"Row {idx}: Individual '{name}' has an empty relation — "
                    f"must be 'has_individual'"
                )
                continue

            if relation != "has_individual":
                name = str(row["ID"]).strip() if pd.notna(row["ID"]) else f"row {idx}"
                errors.append(
                    f"Row {idx}: Individual '{name}' has invalid relation "
                    f"'{relation}' — must be 'has_individual'"
                )
                continue

            father_name = str(row["Types"]).strip() if pd.notna(row["Types"]) else ""
            name = str(row["ID"]).strip() if pd.notna(row["ID"]) else ""
            en_label = str(row["label"]).strip() if pd.notna(row["label"]) else ""

            if not father_name:
                errors.append(
                    f"Row {idx}: Individual '{name or f'row {idx}'}' "
                    f"has an empty Types field — specify a class name"
                )
                continue

            if not name:
                errors.append(
                    f"Row {idx}: Individual has an empty ID — specify a unique identifier"
                )
                continue

            # Parse extra columns (annotation / object properties)
            ap_dict: dict = {}
            op_dict: dict = {}
            if len(keys) > 5:
                for col in keys[5:]:
                    val = str(row[col]).strip() if pd.notna(row[col]) else ""
                    if col.startswith("*") and val:
                        ap_dict[col[1:]] = row[col]
                    if col.startswith("$") and val:
                        op_dict[col[1:]] = row[col]

            try:
                self._add_individual(father_name, name, en_label,
                                     str(row["comment"]).strip() if pd.notna(row["comment"]) else "",
                                     new_ap=ap_dict)
                if op_dict:
                    self._individual_object_properties[name] = op_dict
            except Exception as e:
                errors.append(
                    f"Row {idx}: Failed to create individual '{name}' "
                    f"of class '{father_name}': {e}"
                )

        if errors:
            raise ValueError(
                f"{len(errors)} individual(s) have errors:\n" +
                "\n".join(f"  - {e}" for e in errors)
            )

        if self._individual_object_properties:
            self._apply_object_property_relationships("individual")

    # -----------------------------------------------------------------------
    # Column-based property creation
    # -----------------------------------------------------------------------

    def _create_properties_from_columns(self, col_keys: List[str]) -> None:
        """Create annotation (*) and object ($) properties from CSV column names.

        Supports both plain column names (``$treats``) and dotted names
        (``$treats.Disease``).  For dotted names the base property
        (``treats``) is created automatically when it does not already
        exist, so that downstream relationship application can look it
        up by name.
        """
        for col in col_keys:
            if col.startswith("*"):
                ap_key = col[1:]
                if ap_key not in self._annotation_properties:
                    self._create_annotation_property(ap_key)
            if col.startswith("$"):
                op_key = col[1:]
                if "." in op_key:
                    # Dotted name: $treats.Disease → ensure base property "treats" exists
                    base_op_key = op_key.split(".")[0]
                    if base_op_key not in self._object_properties:
                        self._object_properties[base_op_key] = self._create_object_property(base_op_key)
                elif op_key not in self._object_properties:
                    self._object_properties[op_key] = self._create_object_property(op_key)

    # -----------------------------------------------------------------------
    # Row data parsing
    # -----------------------------------------------------------------------

    def _parse_row_data(self, rule_num: int, row: Any, keys: List[str]):
        """Parse a CSV row into structured components.

        For class data (rule_num=4, old format without IRI):
            returns (father_name, name, label, iri, source, comment, ap_dict, op_dict)
            iri is always "" and source is "local".

        For class data (rule_num=5, new format with IRI):
            returns (father_name, name, label, iri, source, comment, ap_dict, op_dict)
            iri comes from col[3]; source from the ``source`` extra column
            (default ``"local"``).

        For individual data (rule_num=5, old compat):
            returns (father_name, relation, name, label, iri, source, comment,
                     ap_dict, op_dict)
        """
        ap_dict = {}
        op_dict = {}

        if len(keys) > rule_num:
            for col in keys[rule_num:]:
                val = str(row[col]).strip()
                if col.startswith("*") and val:
                    ap_dict[col[1:]] = row[col]
                if col.startswith("$") and val:
                    op_dict[col[1:]] = row[col]

        # Extract iri and source from extra columns when present
        iri = ""
        source = "local"
        if "IRI" in keys:
            iri = str(row["IRI"]).strip() if pd.notna(row["IRI"]) else ""
        if "source" in keys:
            source = str(row["source"]).strip() if pd.notna(row["source"]) else "local"

        if rule_num == 4:
            return (
                row.iloc[0].strip(), row.iloc[1].strip(), row.iloc[2].strip(),
                iri, source, row.iloc[3].strip(), ap_dict, op_dict,
            )
        if rule_num == 5:
            # For classes with IRI: col[3] = IRI, col[4] = comment (if IRI in keys)
            # For individuals (no IRI): col[3] = label, col[4] = comment
            if "IRI" in keys:
                return (
                    row.iloc[0].strip(), row.iloc[1].strip(), row.iloc[2].strip(),
                    iri, source, row.iloc[4].strip(), ap_dict, op_dict,
                )
            else:
                return (
                    row.iloc[0].strip(), row.iloc[1].strip(), row.iloc[2].strip(),
                    row.iloc[3].strip(), iri, source, row.iloc[4].strip(), ap_dict, op_dict,
                )
        return ()

    # -----------------------------------------------------------------------
    # Object property relationship application
    # -----------------------------------------------------------------------

    def _apply_object_property_relationships(self, flag: str) -> None:
        """Apply stored object property relationships to classes or individuals."""
        if flag == "class":
            source = self._class_object_properties
            entity_dict = self._classes
            add_method = self._add_object_property_relationship
        else:
            source = self._individual_object_properties
            entity_dict = self._individuals
            add_method = self._add_individual_object_property_relationship

        for key, op_values in source.items():
            entity = entity_dict[key]
            for op_key, op_val in op_values.items():
                if not op_val:
                    continue

                # Split by & to support multiple targets (e.g. "Diarrhea&Fatigue&Nausea")
                targets = [t.strip() for t in str(op_val).split("&") if t.strip()]

                for target in targets:
                    assert target in entity_dict, (
                        f"Object property target '{target}' not found while "
                        f"processing '{key}.{op_key}' — "
                        f"check that '{target}' is defined in the class table"
                    )
                    if "." in op_key:
                        base_op_key = op_key.split(".")[0]
                        # Ensure the base property exists (may have been skipped by
                        # _create_properties_from_columns for dotted column names).
                        if base_op_key not in self._object_properties:
                            self._object_properties[base_op_key] = self._create_object_property(base_op_key)
                        add_method(
                            entity,
                            self._object_properties[base_op_key],
                            entity_dict[target],
                        )
                    else:
                        if op_key not in self._object_properties:
                            self._object_properties[op_key] = self._create_object_property(op_key)
                        add_method(
                            entity,
                            self._object_properties[op_key],
                            entity_dict[target],
                        )

    # -----------------------------------------------------------------------
    # Object property one-to-one (public API)
    # -----------------------------------------------------------------------

    def add_one_objectProperty(self, itemA: Any, ob_name: Any, itemB: Any) -> None:
        """Public: add a single object property relationship.

        ``ob_name`` can be a string (looked up / created on the fly) or an
        owlready2 ObjectProperty class.
        """
        # Resolve ob_name to an ObjectProperty class
        if isinstance(ob_name, str):
            if ob_name in self._object_properties:
                ob = self._object_properties[ob_name]
            else:
                ob = self._create_object_property(ob_name)
        else:
            ob = ob_name

        ob_list = getattr(itemA, ob.__name__)
        if ob_list is not None:
            if isinstance(ob_list, list):
                ob_list.append(itemB)
            else:
                ob_list = [ob_list, itemB]
            setattr(itemA, ob.__name__, ob_list)
        else:
            setattr(itemA, ob.__name__, [itemB])

    def add_object_property(self, itemA: Any, ob_name: Any, values: List[Any]) -> None:
        """Public: set object property values on an entity (replaces existing list)."""
        setattr(itemA, ob_name.__name__, values)

    # -----------------------------------------------------------------------
    # BioPortal / MedPortal search
    # -----------------------------------------------------------------------

    def _search_standard_ontologies(self, flag: str, onto_name: str) -> None:
        """Search BioPortal or MedPortal and store cross-references."""
        assert len(self._classes) > 1, (
            "No classes defined — create classes before searching external ontologies"
        )

        standard_ap = self._annotation_properties["hasDbXref"]
        for cls in self._classes.values():
            if cls == Thing:
                continue
            labels = cls.label
            if labels:
                label = labels[0]
                results = self._search_class(flag, str(label), onto_name)
                for ref in results:
                    setattr(cls, standard_ap.__name__, ref)

    def _get_json(self, url: str, api_key: str) -> Any:
        """Send an authenticated GET request and return parsed JSON."""
        opener = urllib.request.build_opener()
        opener.addheaders = [("Authorization", f"apikey token={api_key}")]
        return json.loads(opener.open(url).read())

    def _search_class(self, flag: str, term: str, onto_name: str) -> List[str]:
        """Search for a term in BioPortal or MedPortal."""
        if flag.lower().strip() == "bioportal":
            url = f"{BIOPORTAL_REST_URL}/search?q={urllib.parse.quote(term)}"
            collection = self._get_json(url, BIOPORTAL_API_KEY)["collection"]
        else:
            url = f"{MEDPORTAL_REST_URL}/search?q={urllib.parse.quote(term)}"
            collection = self._get_json(url, MEDPORTAL_API_KEY)["collection"]
        return self._parse_json([collection], term, onto_name)

    def _parse_json(self, collections: List[Any], term: str, onto_name: str) -> List[str]:
        """Parse portal JSON search results and extract matching identifiers."""
        results = []
        if collections and collections[0]:
            for item in collections[0]:
                onto = self._extract_ontology_name(item["links"]["ontology"])
                if onto_name.lower() == onto and term.lower() == item["prefLabel"].lower():
                    results.append(item["@id"])
        return results

    # -----------------------------------------------------------------------
    # Utilities
    # -----------------------------------------------------------------------

    def _is_legal_iri(self, iri: str) -> bool:
        """Check that an IRI matches the expected http://... .owl# format."""
        parts = iri.split("//")
        return parts[0] == "http:" and parts[1][-1] == "#"

    def _format_error_list(self, data: List[Any]) -> str:
        """Format unparented class entries into an error string."""
        parts = [
            f"{str(item['Parent_Class']).strip()} - {str(item['ID']).strip()}"
            for item in data
        ]
        return "[" + " , ".join(parts) + " — parent class not found]"

    def _read_csv_with_encoding_fallback(self, path: str):
        """Read a CSV file trying multiple encodings."""
        for encoding in ("gbk", "utf-8", "gb18030", "ansi"):
            try:
                data = pd.read_csv(path, encoding=encoding)
                return data
            except Exception:
                continue
        raise ValueError(
            f"Unable to read CSV file at '{path}' "
            f"with any supported encoding (gbk, utf-8, gb18030, ansi)"
        )

    def _clean_dataframe_values(self, df, rule_num: int):
        """Clean DataFrame: normalize NaN and type issues.

        The first ``rule_num`` columns are 'core' fields; the rest are
        user-defined annotation/object property columns.
        """
        keys = list(df.keys())
        rows = []
        for _, row in df.iterrows():
            before = []
            for col in keys[:rule_num]:
                val = row[col]
                if not isinstance(val, str):
                    before.append("" if pd.isna(val) else str(val).strip())
                else:
                    before.append(val.strip())

            after = []
            for col in keys[rule_num:]:
                val = row[col]
                if pd.isna(val):
                    after.append("")
                elif isinstance(val, str):
                    after.append(val.strip())
                else:
                    after.append(str(val).strip())

            rows.append(before + after)

        return pd.DataFrame(data=rows, columns=keys)

    @staticmethod
    def _extract_ontology_name(ontology_url: str) -> str:
        """Extract the ontology short name from a URL."""
        return ontology_url.split("/")[-1].lower()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

class Process(object):
    """CLI workflow orchestrator for Py2ONTO."""

    def __init__(self) -> None:
        pass

    def begin_parser(self) -> argparse.ArgumentParser:
        """Create and return the argument parser."""
        description = "Py2ONTO V1.0, a standard easy-use to generate owl file python tools"
        parser = argparse.ArgumentParser(
            formatter_class=argparse.RawDescriptionHelpFormatter,
            description=description,
        )
        parser.add_argument(
            "-i", "--base_iri", required=True, type=str,
            help="Base Ontology IRI to build",
        )
        parser.add_argument(
            "-c", "--save_generate_templates_path", type=str,
            help="Create the annotation, object, class and individual template in user defined path",
        )
        parser.add_argument(
            "-a", "--annotation_property", type=str,
            help="User defined annotation template",
        )
        parser.add_argument(
            "-o", "--object_property", type=str,
            help="User defined object template",
        )
        parser.add_argument(
            "-n", "--init", type=str,
            help="input ontology core class structure file path",
        )
        parser.add_argument(
            "-b", "--build", type=str,
            help="input individual file path",
        )
        parser.add_argument(
            "-s", "--standard", type=str,
            help="standard information supported",
        )
        parser.add_argument(
            "-q", "--ontology", type=str,
            help="search ontology name, e.g. go or hpo",
        )
        parser.add_argument(
            "-p", "--save_path", default="./new_onto.owl", type=str,
            help="new ontology save path",
        )
        return parser

    def run_parser(self, args: argparse.Namespace) -> None:
        """Execute the ontology building workflow based on parsed arguments."""
        print("Step 1: Creating empty ontology...")
        py2onto = Py2ONTO(args.base_iri)

        if args.save_generate_templates_path is not None:
            if not os.path.exists(args.save_generate_templates_path):
                os.makedirs(args.save_generate_templates_path)
            py2onto.create_template_file(args.save_generate_templates_path)
            print(f"Template files created in {args.save_generate_templates_path}")
            return

        if args.annotation_property is not None:
            print("Processing annotation property template...")
            py2onto._create_annotation_property_by_template(args.annotation_property)

        if args.object_property is not None:
            print("Processing object property template...")
            py2onto._create_object_property_by_template(args.object_property)

        if args.init is not None:
            print(f"Step 2: Loading class hierarchy from {args.init}...")
            py2onto.init(args.init)

            if py2onto._ap_template_domains:
                for key, val in py2onto._ap_template_domains.items():
                    py2onto._set_annotation_property_domains_from_template(key, val)
            if py2onto._ap_template_ranges:
                for key, val in py2onto._ap_template_ranges.items():
                    py2onto._set_annotation_property_ranges_from_template(key, val)
            if py2onto._op_template_domains:
                for key, val in py2onto._op_template_domains.items():
                    py2onto._set_object_property_domains_from_template(key, val)
            if py2onto._op_template_ranges:
                for key, val in py2onto._op_template_ranges.items():
                    py2onto._set_object_property_ranges_from_template(key, val)

            if args.build is not None:
                print(f"Step 3: Adding individuals from {args.build}...")
                py2onto.build(args.build)

            if args.standard is not None and args.ontology is not None:
                print(f"Step 4: Searching {args.standard} for standard terms...")
                py2onto._search_standard_ontologies(args.standard, args.ontology)

            # Build statistics summary
            n_classes = len(py2onto._classes) - 1  # exclude Thing
            n_individuals = len(py2onto._individuals)
            n_op = len(py2onto._object_properties)
            n_ap = len(py2onto._annotation_properties)
            summary_parts = [f"{n_classes} classes"]
            if n_individuals > 0:
                summary_parts.append(f"{n_individuals} individuals")
            summary_parts.append(f"{n_op} object properties")
            summary_parts.append(f"{n_ap} annotation properties")

            py2onto.save(args.save_path)
            print(
                f"Ontology saved to {args.save_path}\n"
                f"  Summary: {', '.join(summary_parts)}"
            )
        else:
            print(
                "Error: No class file provided. "
                "Use --init <path> to specify a class structure CSV file."
            )


def main() -> None:
    """CLI entry point."""
    p = Process()
    parser = p.begin_parser()
    args = parser.parse_args()
    p.run_parser(args)


if __name__ == "__main__":
    main()
