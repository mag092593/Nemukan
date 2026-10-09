"""Download immutable, checksummed reference models during the external build."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import urllib.request
import zipfile


def selected_models(manifest, faceid):
    return [model for model in manifest["models"] if not model.get("profile") or faceid]


def install_model(root, model):
    target = root / model["target"]
    if not target.resolve().is_relative_to((root / "models").resolve()):
        raise ValueError("Model target escapes the model directory")
    target.parent.mkdir(parents=True, exist_ok=True)
    url = f'https://huggingface.co/{model["repo"]}/resolve/{model["revision"]}/{model["file"]}'
    temporary = target.with_suffix(target.suffix + ".part")
    digest = hashlib.sha256()
    total = 0
    try:
        with urllib.request.urlopen(url, timeout=120) as source, temporary.open("wb") as output:
            while chunk := source.read(1024 * 1024):
                total += len(chunk)
                if total > model["size"]:
                    raise ValueError(f'Unexpected model size: {target.name}')
                digest.update(chunk)
                output.write(chunk)
        if total != model["size"] or digest.hexdigest() != model["sha256"]:
            raise ValueError(f'Model checksum/size mismatch: {target.name}')
        temporary.replace(target)
        print(f"Verified model: {target.name} ({total} bytes)", flush=True)
    finally:
        temporary.unlink(missing_ok=True)


def install_insightface(root):
    # This pinned official release is only fetched by an explicitly licensed profile.
    destination = root / "models/insightface/models/buffalo_l"
    destination.mkdir(parents=True, exist_ok=True)
    archive = destination / "buffalo_l.zip"
    allowed = {"1k3d68.onnx", "2d106det.onnx", "det_10g.onnx", "genderage.onnx", "w600k_r50.onnx"}
    try:
        with urllib.request.urlopen(
            "https://github.com/deepinsight/insightface/releases/download/v0.7/buffalo_l.zip",
            timeout=120,
        ) as source, archive.open("wb") as output:
            total = 0
            while chunk := source.read(1024 * 1024):
                total += len(chunk)
                if total > 512 * 1024 * 1024:
                    raise ValueError("Unexpected InsightFace archive size")
                output.write(chunk)
        with zipfile.ZipFile(archive) as package:
            found = set()
            for entry in package.infolist():
                name = Path(entry.filename).name
                if name in allowed and not entry.is_dir():
                    if name in found or entry.file_size > 512 * 1024 * 1024:
                        raise ValueError("Unexpected InsightFace archive member")
                    with package.open(entry) as source, (destination / name).open("wb") as output:
                        shutil.copyfileobj(source, output)
                    found.add(name)
            if found != allowed:
                raise ValueError("InsightFace archive is missing required model files")
    finally:
        archive.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads(Path(__file__).with_name("models.json").read_text())
    faceid = os.environ.get("REFERENCE_FACEID_ENABLED") == "1"
    models = selected_models(manifest, faceid)
    required_space = sum(model["size"] for model in models) + 1024 ** 3
    if shutil.disk_usage(args.root).free < required_space:
        raise RuntimeError(f"At least {required_space} free bytes are needed for reference models")
    for model in models:
        install_model(args.root, model)
    if faceid:
        install_insightface(args.root)


if __name__ == "__main__":
    main()
