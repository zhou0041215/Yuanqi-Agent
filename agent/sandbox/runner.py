import json
import math
import runpy
from pathlib import Path


def normalize(value):
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {str(key): normalize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [normalize(item) for item in value]
    if hasattr(value, "to_dict"):
        return normalize(value.to_dict())
    if hasattr(value, "tolist"):
        return normalize(value.tolist())
    return str(value)


input_path = Path("/workspace/input.json")
input_data = json.loads(input_path.read_text(encoding="utf-8")) if input_path.exists() else []
namespace = runpy.run_path(
    "/workspace/analysis.py",
    init_globals={"input_data": input_data},
    run_name="__analysis__",
)
payload = {
    "result": normalize(namespace.get("result")),
    "chart": normalize(namespace.get("chart")),
}
Path("/tmp/result.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
print(json.dumps(payload, ensure_ascii=False))
