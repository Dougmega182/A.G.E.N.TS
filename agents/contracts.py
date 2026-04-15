from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Tuple


CONTRACTS_DIR = Path(__file__).parent.parent / "contracts"


@dataclass(frozen=True)
class ContractValidationResult:
    ok: bool
    reason: Optional[str] = None


def load_contract(contract_id: str) -> Dict[str, Any]:
    path = CONTRACTS_DIR / f"{contract_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"Contract not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _is_nonempty_string(x: Any) -> bool:
    return isinstance(x, str) and len(x.strip()) > 0


def _validate_schema(obj: Any, schema: Mapping[str, Any], *, _path: str = "$", _depth: int = 0) -> ContractValidationResult:
    if _depth > 12:
        return ContractValidationResult(ok=False, reason=f"schema_depth_exceeded:{_path}")

    schema_type = schema.get("type")
    if schema_type == "object":
        if not isinstance(obj, dict):
            return ContractValidationResult(ok=False, reason=f"not_object:{_path}")

        required = schema.get("required", [])
        for k in required:
            if k not in obj:
                return ContractValidationResult(ok=False, reason=f"missing_required:{_path}.{k}")

        props = schema.get("properties", {})
        for k, rules in props.items():
            if k not in obj:
                continue
            v = obj[k]
            t = rules.get("type")
            if t == "string":
                if not _is_nonempty_string(v):
                    return ContractValidationResult(ok=False, reason=f"type_error:{_path}.{k}")
                min_len = rules.get("minLength")
                if isinstance(min_len, int) and len(v.strip()) < min_len:
                    return ContractValidationResult(ok=False, reason=f"minLength_error:{_path}.{k}")
            elif t == "array":
                if not isinstance(v, list):
                    return ContractValidationResult(ok=False, reason=f"type_error:{_path}.{k}")
                min_items = rules.get("minItems")
                max_items = rules.get("maxItems")
                if isinstance(min_items, int) and len(v) < min_items:
                    return ContractValidationResult(ok=False, reason=f"minItems_error:{_path}.{k}")
                if isinstance(max_items, int) and len(v) > max_items:
                    return ContractValidationResult(ok=False, reason=f"maxItems_error:{_path}.{k}")
                item_rules = rules.get("items", {})
                if item_rules:
                    for idx, item in enumerate(v):
                        child = _validate_schema(item, item_rules, _path=f"{_path}.{k}[{idx}]", _depth=_depth + 1)
                        if not child.ok:
                            return child
            elif t == "object":
                # If properties/required omitted, accept any object mapping (used for arbitrary arguments).
                if not isinstance(v, dict):
                    return ContractValidationResult(ok=False, reason=f"type_error:{_path}.{k}")
                if "properties" in rules or "required" in rules:
                    child = _validate_schema(v, rules, _path=f"{_path}.{k}", _depth=_depth + 1)
                    if not child.ok:
                        return child
            else:
                return ContractValidationResult(ok=False, reason=f"unsupported_property_type:{_path}.{k}")

        return ContractValidationResult(ok=True)

    if schema_type == "string":
        if not _is_nonempty_string(obj):
            return ContractValidationResult(ok=False, reason=f"type_error:{_path}")
        min_len = schema.get("minLength")
        if isinstance(min_len, int) and len(obj.strip()) < min_len:
            return ContractValidationResult(ok=False, reason=f"minLength_error:{_path}")
        return ContractValidationResult(ok=True)

    if schema_type == "array":
        if not isinstance(obj, list):
            return ContractValidationResult(ok=False, reason=f"type_error:{_path}")
        min_items = schema.get("minItems")
        max_items = schema.get("maxItems")
        if isinstance(min_items, int) and len(obj) < min_items:
            return ContractValidationResult(ok=False, reason=f"minItems_error:{_path}")
        if isinstance(max_items, int) and len(obj) > max_items:
            return ContractValidationResult(ok=False, reason=f"maxItems_error:{_path}")
        item_rules = schema.get("items", {})
        if item_rules:
            for idx, item in enumerate(obj):
                child = _validate_schema(item, item_rules, _path=f"{_path}[{idx}]", _depth=_depth + 1)
                if not child.ok:
                    return child
        return ContractValidationResult(ok=True)

    return ContractValidationResult(ok=False, reason=f"unsupported_schema_type:{schema_type}:{_path}")



def validate_against_contract(obj: Any, contract_id: str) -> ContractValidationResult:
    schema = load_contract(contract_id)
    return _validate_schema(obj, schema)

