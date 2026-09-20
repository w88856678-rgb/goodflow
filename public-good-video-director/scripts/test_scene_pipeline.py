import json
from pathlib import Path
import sys
import tempfile
import unittest

import yaml
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "assets" / "runtime" / "src"))
from scene_pipeline import calculate_changes, compile_plan, index_sources
from hyperframes_builder import build_hyperframes_project
from pg_video import make_timeline


def write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


class ScenePipelineTests(unittest.TestCase):
    def make_project(self, root: Path) -> Path:
        project = root / "project"
        source = project / "assets" / "source"
        source.mkdir(parents=True)
        Image.new("RGB", (640, 960), "#d9543f").save(source / "cover.png")
        Image.new("RGB", (960, 640), "#2d6b55").save(source / "activity.png")
        write_json(project / "project.json", {
            "project_name": "测试公益片",
            "source_text": "这是一段足够长的公益项目测试文字，用来验证声明式场景计划。",
            "duration": 20,
            "aspect": "9:16",
            "tone": "温暖松弛",
            "source_media": [
                {"path": "assets/source/cover.png", "type": "image", "caption": "封面", "rights": "authorized"},
                {"path": "assets/source/activity.png", "type": "image", "caption": "活动", "rights": "authorized"},
            ],
            "rendering": {"engine": "hyperframes"},
            "assets": {"keyframes": ["assets/source/cover.png"]},
        })
        write_json(project / "workflow" / "approved-script.json", {
            "approved": True,
            "narration": "一件小事，也能抵达真正需要它的地方。",
        })
        return project

    def plan(self, project: Path, manifest: dict, *, fit="contain", narration=None) -> Path:
        assets = manifest["assets"]
        value = {
            "version": 1,
            "defaults": {"fit": "contain", "transition": "paper_wipe"},
            "scenes": [
                {"id": "cover", "narration": "", "layout": "static_complete",
                 "media": [{"asset": assets[0]["id"], "role": "cover", "at": 0}],
                 "events": []},
                {"id": "story", "narration": narration or "一件小事，也能抵达真正需要它的地方。",
                 "layout": "single_landscape", "fit": fit,
                 "media": [{"asset": assets[1]["id"], "role": "hero", "at": 0}],
                 "events": [
                     {"type": "paper_label", "at": .08, "text": "一件小事"},
                     {"type": "fact_stack", "at": .4, "items": ["行动", "抵达"]},
                     {"type": "underline", "at": .72, "text": "真正需要"},
                 ]},
            ],
        }
        path = project / "workflow" / "scene-plan.yaml"
        path.write_text(yaml.safe_dump(value, allow_unicode=True, sort_keys=False), encoding="utf-8")
        return path

    def test_index_compile_and_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            project = self.make_project(Path(directory))
            manifest = index_sources(project)
            self.assertEqual(len(manifest["assets"]), 2)
            compiled = compile_plan(project, self.plan(project, manifest))
            self.assertEqual(compiled["scenes"][1]["layout_id"], "single_landscape")
            self.assertEqual(compiled["scenes"][1]["fit"], "contain")
            project_doc = json.loads((project / "project.json").read_text(encoding="utf-8"))
            write_json(project / "workflow" / "facts.json", {})
            write_json(project / "workflow" / "timeline.json", make_timeline(
                "一件小事，也能抵达真正需要它的地方。", 20, project_doc["assets"]["keyframes"]
            ))
            build_dir = build_hyperframes_project(project)
            html = (build_dir / "index.html").read_text(encoding="utf-8")
            self.assertIn("layout-single_landscape", html)
            self.assertIn("assets/media/02/01.png", html)
            first = calculate_changes(project)
            self.assertEqual(first["dirty_scenes"], ["cover", "story"])
            calculate_changes(project, commit=True)
            second = calculate_changes(project)
            self.assertEqual(second["dirty_scenes"], [])
            self.assertEqual(second["reusable_scenes"], ["cover", "story"])

    def test_source_cover_crop_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            project = self.make_project(Path(directory))
            manifest = index_sources(project)
            with self.assertRaisesRegex(ValueError, "只有 layered_story 可使用 cover"):
                compile_plan(project, self.plan(project, manifest, fit="cover"))

    def test_approved_narration_drift_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            project = self.make_project(Path(directory))
            manifest = index_sources(project)
            with self.assertRaisesRegex(ValueError, "与已确认旁白不一致"):
                compile_plan(project, self.plan(project, manifest, narration="擅自修改后的旁白。"))


if __name__ == "__main__":
    unittest.main()
