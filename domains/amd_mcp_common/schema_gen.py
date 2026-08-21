"""Schema generator: emit JSON Schemas per AMD action.

Two input modes, locked by F0.D3:

1. **WSDL mode** (`generate_from_wsdl`). Parses an AMD WSDL via lxml,
   walks every `<wsdl:operation>`, resolves the input message's
   complex type, and emits one JSON Schema (Draft 2020-12) per
   action. Type mapping is locked in `_XSD_TO_JSON_TYPE`.

2. **Catalog mode** (`generate_from_catalog`). Reads
   `action-catalog.data.json` — a hand-curated catalog used as the
   fallback when WSDL is unusable (F1's UNUSABLE verdict). Each
   catalog entry already carries a JSON Schema fragment; this mode
   normalizes it, validates it, and writes it.

Both modes write to `schemas/generated/<domain>/<action>.json`.
Idempotent: re-running on the same input produces byte-identical
output.

The generator NEVER deletes existing files unless `prune=True` is
passed; the curated knowledge layer at
`knowledge/integrations/amd/<domain>/` is never touched.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from jsonschema import Draft202012Validator


# -- locked type mapping -----------------------------------------------------

_XSD_TO_JSON_TYPE: dict[str, dict[str, Any]] = {
    "string": {"type": "string"},
    "normalizedString": {"type": "string"},
    "token": {"type": "string"},
    "integer": {"type": "integer"},
    "int": {"type": "integer"},
    "long": {"type": "integer"},
    "short": {"type": "integer"},
    "byte": {"type": "integer"},
    "unsignedInt": {"type": "integer", "minimum": 0},
    "unsignedLong": {"type": "integer", "minimum": 0},
    "decimal": {"type": "number"},
    "float": {"type": "number"},
    "double": {"type": "number"},
    "boolean": {"type": "boolean"},
    "date": {"type": "string", "format": "date"},
    "dateTime": {"type": "string", "format": "date-time"},
    "time": {"type": "string", "format": "time"},
    "base64Binary": {"type": "string", "contentEncoding": "base64"},
    "anyURI": {"type": "string", "format": "uri"},
    "anyType": {"description": "opaque AMD field; unconstrained"},
}

_XSD_NS = "http://www.w3.org/2001/XMLSchema"
_WSDL_NS = "http://schemas.xmlsoap.org/wsdl/"

# JSON schema header for emitted files.
_JSON_SCHEMA_HEADER = "https://json-schema.org/draft/2020-12/schema"


# -- WSDL parsing dataclasses ------------------------------------------------


@dataclass
class Operation:
    name: str
    input_type_qname: str | None
    doc_string: str = ""


@dataclass
class ParsedWSDL:
    operations: list[Operation] = field(default_factory=list)
    schema_root: Any = None  # lxml Element of the embedded xs:schema
    namespaces: dict[str, str] = field(default_factory=dict)


# -- WSDL parsing -----------------------------------------------------------


def parse_wsdl(path: Path) -> ParsedWSDL:
    """Parse a WSDL file into operation + schema root.

    `path` must point at a complete WSDL document (xs:schema either
    embedded or imported; for foundation we expect embedded).
    """
    from lxml import etree  # local import keeps the module light on
                            # systems where lxml is heavyweight at import.
    tree = etree.parse(str(path))
    root = tree.getroot()
    ns = {k: v for k, v in root.nsmap.items() if k}

    # Build a message-name -> part-type-local map so we can dereference
    # `<wsdl:operation>`'s `<wsdl:input message="tns:Foo"/>` to the
    # actual complex-type local name.
    msg_to_type: dict[str, str] = {}
    for msg in root.findall(f".//{{{_WSDL_NS}}}message"):
        msg_name = msg.get("name")
        if not msg_name:
            continue
        part = msg.find(f"{{{_WSDL_NS}}}part")
        if part is None:
            continue
        t = part.get("type") or part.get("element")
        if t:
            msg_to_type[msg_name] = _local_name(t)

    # Find every wsdl:operation in a portType.
    ops_xml = root.findall(f".//{{{_WSDL_NS}}}operation")
    if not ops_xml:
        ops_xml = root.findall(".//{*}operation")
    operations: list[Operation] = []
    for op in ops_xml:
        name = op.get("name")
        if not name:
            continue
        # Input message reference; in WSDL 1.1 this lives in a child
        # <wsdl:input message="tns:..." /> or via portType.
        inp = op.find(f"{{{_WSDL_NS}}}input")
        if inp is None:
            inp = op.find("{*}input")
        msg_qname = inp.get("message") if inp is not None else None
        # Resolve message -> type.
        input_type = None
        if msg_qname:
            msg_local = _local_name(msg_qname)
            input_type = msg_to_type.get(msg_local)
        doc = op.find(f"{{{_WSDL_NS}}}documentation")
        doc_text = (doc.text or "").strip() if doc is not None else ""
        operations.append(
            Operation(name=name, input_type_qname=input_type, doc_string=doc_text)
        )

    # Embedded xs:schema(s) — collect them.
    schemas = root.findall(f".//{{{_XSD_NS}}}schema")
    schema_root = schemas[0] if schemas else None
    return ParsedWSDL(
        operations=operations, schema_root=schema_root, namespaces=ns
    )


def resolve_complex_type(
    type_qname: str,
    schema_root: Any,
    *,
    seen: set[str] | None = None,
    definitions: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Walk an xs:complexType into a JSON Schema object node.

    Recursive; emits $ref to a definitions block for cycles.

    `type_qname` is the local-name (we resolve in the embedded schema).
    """
    if seen is None:
        seen = set()
    if definitions is None:
        definitions = {}

    local = _local_name(type_qname)

    # Built-in xs:* type? Direct mapping.
    if type_qname.startswith(f"{{{_XSD_NS}}}") or _looks_like_xsd_builtin(local):
        return dict(_XSD_TO_JSON_TYPE.get(local, _XSD_TO_JSON_TYPE["anyType"]))

    if local in seen:
        # Cycle detected; emit a $ref to the definitions block.
        return {"$ref": f"#/$defs/{local}"}

    seen = seen | {local}

    if schema_root is None:
        return {"description": "no schema root; unresolved", "type": "object"}

    from lxml import etree
    ct = None
    for candidate in schema_root.findall(f"{{{_XSD_NS}}}complexType"):
        if candidate.get("name") == local:
            ct = candidate
            break
    if ct is None:
        # Try xs:simpleType (enum etc.).
        for st in schema_root.findall(f"{{{_XSD_NS}}}simpleType"):
            if st.get("name") == local:
                return _resolve_simple_type(st)
        return {"description": f"type {local!r} not found in schema",
                "type": "object"}

    return _resolve_complex_type_element(ct, schema_root, seen, definitions, local)


def _local_name(qname: str) -> str:
    if "}" in qname:
        return qname.split("}", 1)[1]
    if ":" in qname:
        return qname.split(":", 1)[1]
    return qname


def _looks_like_xsd_builtin(local: str) -> bool:
    return local in _XSD_TO_JSON_TYPE


def _resolve_simple_type(st: Any) -> dict[str, Any]:
    """xs:simpleType -> {type, enum?} mapping."""
    restriction = st.find(f"{{{_XSD_NS}}}restriction")
    if restriction is None:
        return {"type": "string"}
    base_qname = restriction.get("base", "xs:string")
    base_local = _local_name(base_qname)
    base = dict(_XSD_TO_JSON_TYPE.get(base_local, {"type": "string"}))
    enums = restriction.findall(f"{{{_XSD_NS}}}enumeration")
    if enums:
        base["enum"] = [e.get("value") for e in enums if e.get("value")]
    return base


def _resolve_complex_type_element(
    ct: Any, schema_root: Any, seen: set[str],
    definitions: dict[str, dict[str, Any]], local: str,
) -> dict[str, Any]:
    """Inner helper: handles xs:sequence / xs:choice / xs:any."""
    out: dict[str, Any] = {"type": "object", "properties": {}}
    required: list[str] = []

    # xs:choice -> oneOf
    choice = ct.find(f"{{{_XSD_NS}}}choice") or ct.find(f"{{{_XSD_NS}}}sequence/{{{_XSD_NS}}}choice")
    sequence = ct.find(f"{{{_XSD_NS}}}sequence")
    if choice is not None and sequence is None:
        options: list[dict[str, Any]] = []
        for elem in choice.findall(f"{{{_XSD_NS}}}element"):
            options.append(_resolve_element(elem, schema_root, seen, definitions))
        out = {"oneOf": options}
        if definitions:
            out["$defs"] = definitions
        return out

    if sequence is not None:
        for elem in sequence.findall(f"{{{_XSD_NS}}}element"):
            name = elem.get("name") or elem.get("ref")
            if not name:
                continue
            name = _local_name(name)
            min_occurs = elem.get("minOccurs", "1")
            max_occurs = elem.get("maxOccurs", "1")
            schema = _resolve_element(elem, schema_root, seen, definitions)
            if max_occurs == "unbounded" or (max_occurs != "1" and max_occurs != "0"):
                schema = {"type": "array", "items": schema}
            out["properties"][name] = schema
            if min_occurs != "0":
                required.append(name)
        # xs:any inside sequence (opaque blob)
        any_el = sequence.find(f"{{{_XSD_NS}}}any")
        if any_el is not None:
            out["additionalProperties"] = True
            out["description"] = "opaque AMD payload; xs:any wildcard"

    if required:
        out["required"] = required

    if definitions:
        out["$defs"] = definitions
    return out


def _resolve_element(
    elem: Any, schema_root: Any, seen: set[str],
    definitions: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Resolve an xs:element to its schema node."""
    # Inline type?
    inline_ct = elem.find(f"{{{_XSD_NS}}}complexType")
    if inline_ct is not None:
        return _resolve_complex_type_element(inline_ct, schema_root, seen, definitions, "<inline>")
    inline_st = elem.find(f"{{{_XSD_NS}}}simpleType")
    if inline_st is not None:
        return _resolve_simple_type(inline_st)
    type_qname = elem.get("type", "xs:string")
    return resolve_complex_type(type_qname, schema_root, seen=seen, definitions=definitions)


# -- WSDL generate-all -------------------------------------------------------


def generate_from_wsdl(
    input_path: Path,
    output_dir: Path,
    domain_mapping: dict[str, list[str]],
    *,
    prune: bool = False,
) -> dict[str, list[str]]:
    """Walk WSDL operations, emit one JSON Schema per action.

    Returns dict {domain: [actions written]}. Idempotent.
    """
    wsdl = parse_wsdl(input_path)
    return _emit_for_operations(
        operations=[
            (op.name, _wsdl_input_schema(op, wsdl), op.doc_string)
            for op in wsdl.operations
        ],
        output_dir=output_dir,
        domain_mapping=domain_mapping,
        prune=prune,
    )


def _wsdl_input_schema(op: Operation, wsdl: ParsedWSDL) -> dict[str, Any]:
    """Resolve an operation's input message type to a JSON Schema object."""
    if op.input_type_qname is None or wsdl.schema_root is None:
        return {"type": "object", "properties": {}}
    local = _local_name(op.input_type_qname)
    return resolve_complex_type(local, wsdl.schema_root)


# -- Catalog generate-all (F1 fallback path) ---------------------------------


def generate_from_catalog(
    catalog_path: Path,
    output_dir: Path,
    domain_mapping: dict[str, list[str]],
    *,
    prune: bool = False,
) -> dict[str, list[str]]:
    """Read action-catalog.data.json and emit schemas.

    The catalog already carries JSON Schema fragments; this generator
    validates and writes them. Each catalog entry must include:
    `name`, `domain`, `tier`, `write` (bool), `input` (JSON Schema),
    optional `doc`.
    """
    raw = json.loads(catalog_path.read_text(encoding="utf-8"))
    entries = raw.get("actions") or []
    ops: list[tuple[str, dict[str, Any], str]] = []
    for entry in entries:
        name = entry["name"]
        input_schema = entry["input"]
        # Inject metadata at the top level so each schema is queryable
        # via jq for filter-by-domain / filter-by-write / filter-by-tier.
        out_schema: dict[str, Any] = {
            "$schema": _JSON_SCHEMA_HEADER,
            "$id": f"amd-mcp/schemas/{entry['domain']}/{name}",
            "title": f"AMD action: {name}",
            "x-amd-action": {
                "name": name,
                "domain": entry["domain"],
                "key": entry.get("key", name),
                "class_": entry.get("class_"),
                "tier": entry.get("tier", 2),
                "write": entry.get("write", False),
                "phi_touching": True,  # default true; policy file refines
            },
            "description": entry.get("doc", "").strip() or f"AMD action {name}",
            **input_schema,
        }
        # Strip None class_
        if out_schema["x-amd-action"].get("class_") is None:
            out_schema["x-amd-action"].pop("class_", None)
        ops.append((name, out_schema, entry.get("doc", "")))
    return _emit_for_operations(
        operations=ops,
        output_dir=output_dir,
        domain_mapping=domain_mapping,
        prune=prune,
        already_full_schemas=True,
    )


# -- Common writer -----------------------------------------------------------


def _emit_for_operations(
    operations: Iterable[tuple[str, dict[str, Any], str]],
    output_dir: Path,
    domain_mapping: dict[str, list[str]],
    *,
    prune: bool = False,
    already_full_schemas: bool = False,
) -> dict[str, list[str]]:
    """Write each operation's schema. Common path for WSDL and catalog."""
    # Reverse domain mapping: action -> domain.
    action_to_domain: dict[str, str] = {}
    for domain, actions in domain_mapping.items():
        for action in actions:
            action_to_domain[action] = domain
    output_dir.mkdir(parents=True, exist_ok=True)

    written_by_domain: dict[str, list[str]] = {}
    written_paths: set[Path] = set()

    for action_name, input_schema, doc in operations:
        domain = action_to_domain.get(action_name)
        if domain is None:
            raise ValueError(
                f"action {action_name!r} not in domain-mapping; "
                "add it to domain-mapping.data.json or remove from catalog."
            )
        if already_full_schemas:
            payload = input_schema
        else:
            payload = {
                "$schema": _JSON_SCHEMA_HEADER,
                "$id": f"amd-mcp/schemas/{domain}/{action_name}",
                "title": f"AMD action: {action_name}",
                "x-amd-action": {
                    "name": action_name,
                    "domain": domain,
                    "tier": 2,
                    "write": action_name.startswith("save")
                    or action_name.startswith("upd")
                    or action_name.startswith("del"),
                    "phi_touching": True,
                },
                "description": (doc or "").strip() or f"AMD action {action_name}",
                **input_schema,
            }
        Draft202012Validator.check_schema(payload)
        target_dir = output_dir / domain
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / f"{action_name}.json"
        rendered = _render_json_stable(payload)
        # Idempotent write: skip if byte-equal.
        if target.exists() and target.read_text(encoding="utf-8") == rendered:
            written_by_domain.setdefault(domain, []).append(action_name)
            written_paths.add(target)
            continue
        target.write_text(rendered, encoding="utf-8")
        written_by_domain.setdefault(domain, []).append(action_name)
        written_paths.add(target)

    if prune:
        # Delete any .json files under output_dir not just written.
        for sub in output_dir.iterdir():
            if not sub.is_dir():
                continue
            for f in sub.glob("*.json"):
                if f not in written_paths:
                    f.unlink()

    return written_by_domain


def _render_json_stable(obj: Any) -> str:
    """JSON dump with stable key ordering + 2-space indent + trailing newline.

    Keys ordered alphabetically EXCEPT we float well-known meta-keys to
    the top for queryability: $schema, $id, title, x-amd-action,
    description, then the rest alphabetical.
    """
    return json.dumps(_stable_order(obj), indent=2, sort_keys=False) + "\n"


_META_KEY_ORDER = [
    "$schema", "$id", "title", "x-amd-action", "description",
    "type", "required", "anyOf", "oneOf", "allOf",
    "properties", "additionalProperties",
    "items", "minItems", "maxItems",
    "minimum", "maximum", "minLength", "maxLength",
    "enum", "default", "format", "pattern",
]


def _stable_order(node: Any) -> Any:
    if isinstance(node, dict):
        ordered = OrderedDict()
        # Meta keys in fixed order first.
        for k in _META_KEY_ORDER:
            if k in node:
                ordered[k] = _stable_order(node[k])
        # Then anything else alphabetical.
        for k in sorted(node.keys()):
            if k in ordered:
                continue
            ordered[k] = _stable_order(node[k])
        return ordered
    if isinstance(node, list):
        return [_stable_order(x) for x in node]
    return node


def validate_generated(schema_dict: dict[str, Any]) -> None:
    """Run jsonschema.check_schema; raise on malformed."""
    Draft202012Validator.check_schema(schema_dict)


# -- CLI --------------------------------------------------------------------


def _cli(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="amd_mcp_common.schema_gen")
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--wsdl", type=Path, help="WSDL XML input")
    src.add_argument("--catalog", type=Path, help="action-catalog.data.json input")
    p.add_argument("--out", type=Path, required=True, help="output dir (schemas/generated/)")
    p.add_argument("--mapping", type=Path, required=True, help="domain-mapping.data.json")
    p.add_argument("--prune", action="store_true")
    args = p.parse_args(argv)

    mapping = json.loads(args.mapping.read_text(encoding="utf-8"))["mapping"]
    if args.wsdl:
        result = generate_from_wsdl(args.wsdl, args.out, mapping, prune=args.prune)
    else:
        result = generate_from_catalog(args.catalog, args.out, mapping, prune=args.prune)

    total = sum(len(v) for v in result.values())
    print(f"Wrote {total} schemas across {len(result)} domains.")
    for domain, actions in sorted(result.items()):
        print(f"  {domain}: {len(actions)} ({', '.join(sorted(actions))})")
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
