"""Deterministic D1 vision-to-named-action safety contract."""

from __future__ import annotations

import secrets
import threading
import time
from dataclasses import dataclass
from typing import Callable

from .core import SafetyError


PLAN_TTL_SECONDS = 300

SCENES = (
    {
        "id": "bench-a",
        "name": "工作台 A · 正常光源",
        "image": "/vision/bench-a.svg",
        "objects": (
            {"id": "red-cube", "label": "紅色方塊", "confidence": 0.97,
             "bbox": {"x": 16, "y": 43, "w": 19, "h": 28},
             "recipe": "pick-red-cube-to-left-bin"},
            {"id": "blue-cylinder", "label": "藍色圓柱", "confidence": 0.93,
             "bbox": {"x": 57, "y": 34, "w": 17, "h": 39},
             "recipe": "pick-blue-cylinder-to-right-bin"},
        ),
    },
    {
        "id": "bench-b",
        "name": "工作台 B · 遮擋測試",
        "image": "/vision/bench-b.svg",
        "objects": (
            {"id": "green-block", "label": "綠色積木", "confidence": 0.88,
             "bbox": {"x": 31, "y": 49, "w": 22, "h": 24},
             "recipe": "pick-green-block-to-left-bin"},
            {"id": "low-confidence-object", "label": "部分遮擋物件", "confidence": 0.54,
             "bbox": {"x": 70, "y": 45, "w": 15, "h": 27}, "recipe": None},
        ),
    },
)

RECIPES = {
    "pick-red-cube-to-left-bin": {
        "name": "Pick red cube → left bin",
        "destination": "左側收納盒",
        "steps": (
            {"label": "Pre-grasp", "joints": {"base": 68, "shoulder": 82, "elbow": 104, "gripper": 82}, "duration_ms": 1500},
            {"label": "Grasp", "joints": {"base": 68, "shoulder": 92, "elbow": 116, "gripper": 45}, "duration_ms": 1200},
            {"label": "Place", "joints": {"base": 128, "shoulder": 76, "elbow": 98, "gripper": 82}, "duration_ms": 1800},
        ),
    },
    "pick-blue-cylinder-to-right-bin": {
        "name": "Pick blue cylinder → right bin",
        "destination": "右側收納盒",
        "steps": (
            {"label": "Pre-grasp", "joints": {"base": 112, "shoulder": 78, "elbow": 108, "gripper": 86}, "duration_ms": 1500},
            {"label": "Grasp", "joints": {"base": 112, "shoulder": 90, "elbow": 119, "gripper": 42}, "duration_ms": 1200},
            {"label": "Place", "joints": {"base": 48, "shoulder": 74, "elbow": 96, "gripper": 86}, "duration_ms": 1800},
        ),
    },
    "pick-green-block-to-left-bin": {
        "name": "Pick green block → left bin",
        "destination": "左側收納盒",
        "steps": (
            {"label": "Pre-grasp", "joints": {"base": 84, "shoulder": 80, "elbow": 106, "gripper": 84}, "duration_ms": 1500},
            {"label": "Grasp", "joints": {"base": 84, "shoulder": 91, "elbow": 118, "gripper": 44}, "duration_ms": 1200},
            {"label": "Place", "joints": {"base": 130, "shoulder": 76, "elbow": 98, "gripper": 84}, "duration_ms": 1800},
        ),
    },
}


@dataclass
class PlanRecord:
    public: dict
    expires_at: float
    confirmed: bool = False
    executed: bool = False


class VisionFlow:
    def __init__(self, now: Callable[[], float] = time.monotonic):
        self.now = now
        self.plans: dict[str, PlanRecord] = {}
        self.lock = threading.Lock()

    def scenes(self) -> dict:
        return {"ok": True, "mode": "pre-recorded", "scenes": SCENES}

    def select(self, scene_id: str, object_id: str) -> dict:
        scene = next((item for item in SCENES if item["id"] == scene_id), None)
        if scene is None:
            raise SafetyError("unknown scene")
        detected = next((item for item in scene["objects"] if item["id"] == object_id), None)
        if detected is None:
            raise SafetyError("object is not present in the selected scene")
        if detected["confidence"] < 0.80 or not detected["recipe"]:
            raise SafetyError("object confidence is below the reviewed planning threshold")
        recipe = RECIPES[detected["recipe"]]
        plan_id = secrets.token_urlsafe(24)
        public = {
            "plan_id": plan_id,
            "scene_id": scene_id,
            "object": detected,
            "recipe": {
                "id": detected["recipe"], "name": recipe["name"],
                "destination": recipe["destination"], "steps": recipe["steps"],
            },
            "expires_in_seconds": PLAN_TTL_SECONDS,
            "confirmed": False,
            "executed": False,
        }
        with self.lock:
            self.plans[plan_id] = PlanRecord(public, self.now() + PLAN_TTL_SECONDS)
        return {"ok": True, "plan": public}

    def _get(self, plan_id: str) -> PlanRecord:
        record = self.plans.get(plan_id)
        if record is None:
            raise SafetyError("unknown vision plan")
        if record.expires_at <= self.now():
            self.plans.pop(plan_id, None)
            raise SafetyError("vision plan expired; select the object again")
        return record

    def confirm(self, plan_id: str, human_confirmed: bool) -> dict:
        if human_confirmed is not True:
            raise SafetyError("human_confirmed=true is required")
        with self.lock:
            record = self._get(plan_id)
            if record.executed:
                raise SafetyError("vision plan was already executed")
            record.confirmed = True
            record.public["confirmed"] = True
            return {"ok": True, "plan": record.public}

    def execute(
        self,
        plan_id: str,
        bridge_status: dict,
        send_command: Callable[[dict], dict],
    ) -> dict:
        with self.lock:
            record = self._get(plan_id)
            if not record.confirmed:
                raise SafetyError("vision plan requires separate human confirmation")
            if record.executed:
                raise SafetyError("vision plan is single-use and was already executed")
            if bridge_status.get("hardware", {}).get("mode") != "mock":
                raise SafetyError("D1 vision execution is mock-only; complete D2 calibration first")
            if not bridge_status.get("startup_ready") or not bridge_status.get("armed"):
                raise SafetyError("bridge must be startup-ready and armed before execution")
            record.executed = True
            record.public["executed"] = True
            steps = tuple(record.public["recipe"]["steps"])

        results = []
        try:
            for step in steps:
                result = send_command({
                    "command": "move", "joints": dict(step["joints"]),
                    "duration_ms": step["duration_ms"],
                })
                results.append({"label": step["label"], "result": result})
        except Exception:
            try:
                send_command({"command": "stop"})
            finally:
                raise
        return {"ok": True, "plan_id": plan_id, "recipe": record.public["recipe"]["id"], "steps": results}
