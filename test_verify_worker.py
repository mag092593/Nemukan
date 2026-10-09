"""Cheap checks for the verifier/downloader; no ComfyUI or model downloads."""
import copy
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from install_models import install_model, selected_models
from verify_worker import validate_workflow


class WorkerChecks(unittest.TestCase):
    def setUp(self):
        self.workflow = {
            "1": {"class_type": "Loader", "inputs": {"file": "model.safetensors"}},
            "2": {"class_type": "Apply", "inputs": {"model": ["1", 0], "weight": 0.3}},
        }
        self.info = {
            "Loader": {"input": {"required": {"file": [["model.safetensors"]]}}, "output": ["MODEL"]},
            "Apply": {"input": {"required": {"model": ["MODEL"], "weight": ["FLOAT"]}}, "output": ["MODEL"]},
        }

    def test_valid_graph(self):
        validate_workflow(self.workflow, self.info)

    def test_missing_node_input_enum_and_link(self):
        for mutate in (
            lambda graph: graph["2"].update(class_type="Missing"),
            lambda graph: graph["2"]["inputs"].pop("weight"),
            lambda graph: graph["1"]["inputs"].update(file="wrong.safetensors"),
            lambda graph: graph["2"]["inputs"].update(model=["1", 3]),
            lambda graph: graph["2"]["inputs"].update(model=["absent", 0]),
            lambda graph: graph["2"]["inputs"].update(image_negative=None),
        ):
            graph = copy.deepcopy(self.workflow)
            mutate(graph)
            with self.assertRaises(ValueError):
                validate_workflow(graph, self.info)

    def test_immutable_models_have_matching_manifest_hashes(self):
        manifest = json.loads(Path(__file__).with_name("models.json").read_text())
        self.assertEqual(len(selected_models(manifest, False)), 4)
        self.assertEqual(len(selected_models(manifest, True)), 6)
        for model in manifest["models"]:
            self.assertEqual(len(model["revision"]), 40)
            self.assertEqual(len(model["sha256"]), 64)

    def test_checksum_verified_atomic_download_and_corruption_rejected(self):
        data = b"fixture bytes, not model weights"
        model = {"target": "models/ipadapter/fixture.bin", "repo": "fixture/model",
                 "revision": "a" * 40, "file": "fixture.bin",
                 "sha256": hashlib.sha256(data).hexdigest(), "size": len(data)}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch("urllib.request.urlopen", return_value=io.BytesIO(data)):
                install_model(root, model)
            self.assertEqual((root / model["target"]).read_bytes(), data)
            bad = {**model, "sha256": "0" * 64}
            with patch("urllib.request.urlopen", return_value=io.BytesIO(data)):
                with self.assertRaises(ValueError):
                    install_model(root, bad)
            self.assertEqual((root / model["target"]).read_bytes(), data)
            self.assertFalse((root / (model["target"] + ".part")).exists())


if __name__ == "__main__":
    unittest.main()
