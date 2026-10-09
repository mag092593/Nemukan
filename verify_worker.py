"""CPU build check against actual ComfyUI node schemas. Never queues sampling."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import urllib.request


def validate_workflow(workflow, info):
    for node_id, node in workflow.items():
        kind = node["class_type"]
        if kind not in info:
            raise ValueError(f"Missing node {kind} at {node_id}")
        schema = info[kind]
        required = schema["input"].get("required", {})
        optional = schema["input"].get("optional", {})
        inputs = node["inputs"]
        missing = set(required) - set(inputs)
        if missing:
            raise ValueError(f"{kind} is missing required inputs: {sorted(missing)}")
        unknown = set(inputs) - set(required) - set(optional)
        if unknown:
            raise ValueError(f"{kind} has unknown inputs: {sorted(unknown)}")
        for name, value in inputs.items():
            specification = (required | optional)[name]
            expected_type = specification[0]
            is_link = isinstance(value, list) and len(value) == 2 and isinstance(value[0], str)
            if is_link:
                source_id, index = value
                if source_id not in workflow or not isinstance(index, int):
                    raise ValueError(f"{kind}.{name} has a broken link")
                outputs = info[workflow[source_id]["class_type"]]["output"]
                if index < 0 or index >= len(outputs) or outputs[index] != expected_type:
                    raise ValueError(f"{kind}.{name} has an incompatible output link")
            elif isinstance(expected_type, list):
                # Uploaded reference image names are not present at image-build time.
                if kind != "LoadImage" and value not in expected_type:
                    raise ValueError(f"{kind}.{name} has an unavailable choice: {value}")
            elif expected_type == "INT" and (type(value) is not int):
                raise ValueError(f"{kind}.{name} requires an integer")
            elif expected_type == "FLOAT" and type(value) not in (float, int):
                raise ValueError(f"{kind}.{name} requires a number")
            elif expected_type == "STRING" and not isinstance(value, str):
                raise ValueError(f"{kind}.{name} requires text")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    faceid = os.environ.get("REFERENCE_FACEID_ENABLED") == "1"
    if faceid:
        import insightface  # noqa: F401 -- fail build, not first user's paid job
        import onnxruntime
        if "CUDAExecutionProvider" not in onnxruntime.get_available_providers():
            raise RuntimeError("The FaceID profile requires GPU-capable ONNX Runtime")
    fixtures = json.loads(Path(__file__).with_name("contract-workflows.json").read_text())
    with tempfile.TemporaryFile(mode="w+") as logs:
        server = subprocess.Popen(
            [sys.executable, str(args.root / "main.py"), "--cpu", "--listen", "127.0.0.1", "--port", "8188"],
            cwd=args.root, stdout=logs, stderr=subprocess.STDOUT,
        )
        try:
            deadline = time.monotonic() + 180
            info = None
            while time.monotonic() < deadline:
                if server.poll() is not None:
                    raise RuntimeError("ComfyUI exited before its node schemas were available")
                try:
                    with urllib.request.urlopen("http://127.0.0.1:8188/object_info", timeout=5) as response:
                        info = json.load(response)
                    break
                except (OSError, ValueError):
                    time.sleep(2)
            if info is None:
                raise RuntimeError("ComfyUI did not start within 180 seconds")
            checked = []
            for name, workflow in fixtures.items():
                if name == "faceid" and not faceid:
                    continue
                validate_workflow(workflow, info)
                checked.append(name)
            report = {
                "schema_checks": checked, "sampling_performed": False,
                "faceid_enabled": faceid,
                "checkpoint": "sd_xl_base_1.0.safetensors",
                "runtime_gpu_validation": "not_performed",
            }
            (args.root / "reference-worker-report.json").write_text(json.dumps(report, indent=2))
            print("REFERENCE_WORKER_BUILD_CHECK=" + json.dumps(report), flush=True)
        except Exception:
            logs.seek(0)
            print(logs.read()[-16000:], file=sys.stderr)
            raise
        finally:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait()


if __name__ == "__main__":
    main()
