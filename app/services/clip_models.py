from __future__ import annotations

import importlib.util
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import numpy as np

ArchName = Literal["stack3_mobilenet", "video_x3d", "video_vmae", "twostream"]
ARCHES: tuple[ArchName, ...] = ("stack3_mobilenet", "video_x3d", "video_vmae", "twostream")
LABEL_TO_INDEX = {"refute": 0, "assert": 1, 0: 0, 1: 1, False: 0, True: 1}
LOGGER = logging.getLogger(__name__)
VIDEOMAE_MODEL_NAME = "MCG-NJU/videomae-base"
TORCHVISION_VIDEO_BACKBONE = "r3d_18"


@dataclass(frozen=True)
class ArchAvailability:
    arch: str
    available: bool
    reason: str | None = None


def arch_availability() -> dict[str, ArchAvailability]:
    torch_ok = _has_module("torch")
    torchvision_ok = _has_module("torchvision")
    statuses = {
        "stack3_mobilenet": ArchAvailability(
            "stack3_mobilenet",
            torch_ok and torchvision_ok,
            None if torch_ok and torchvision_ok else "requires torch and torchvision",
        ),
        "video_x3d": ArchAvailability(
            "video_x3d",
            torch_ok and torchvision_ok,
            None if torch_ok and torchvision_ok else "requires torch and torchvision video models",
        ),
        "video_vmae": ArchAvailability(
            "video_vmae",
            torch_ok and _has_module("transformers") and _has_module("timm"),
            None if torch_ok and _has_module("transformers") and _has_module("timm") else "requires transformers and timm",
        ),
        "twostream": ArchAvailability(
            "twostream",
            torch_ok and torchvision_ok,
            None if torch_ok and torchvision_ok else "requires torch and torchvision",
        ),
    }
    return statuses


def available_arch_names() -> list[str]:
    return [name for name, status in arch_availability().items() if status.available]


def create_model(
    arch: str,
    *,
    flow_channels: int = 30,
    pretrained: bool = False,
) -> Any:
    status = arch_availability().get(arch)
    if status is None:
        raise ValueError(f"unsupported arch: {arch}")
    if not status.available:
        raise RuntimeError(status.reason or f"{arch} is unavailable")
    if arch == "stack3_mobilenet":
        return create_mobilenet_classifier(input_channels=9, pretrained=pretrained)
    if arch == "twostream":
        return TwoStreamMobileNet(flow_channels=flow_channels, pretrained=pretrained)
    if arch == "video_x3d":
        return create_torchvision_video_classifier(pretrained=pretrained)
    if arch == "video_vmae":
        return create_videomae_classifier(pretrained=pretrained)
    raise ValueError(f"unsupported arch: {arch}")


def create_mobilenet_classifier(*, input_channels: int, pretrained: bool = False) -> Any:
    import torch
    from torchvision.models import MobileNet_V3_Small_Weights, mobilenet_v3_small

    weights = None
    if pretrained:
        try:
            weights = MobileNet_V3_Small_Weights.DEFAULT
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("stack3_mobilenet pretrained weights unavailable; using random init: %s", exc)
            weights = None
    model = mobilenet_v3_small(weights=weights)
    first_conv = model.features[0][0]
    replacement = torch.nn.Conv2d(
        input_channels,
        first_conv.out_channels,
        kernel_size=first_conv.kernel_size,
        stride=first_conv.stride,
        padding=first_conv.padding,
        bias=first_conv.bias is not None,
    )
    with torch.no_grad():
        if first_conv.weight.shape[1] == 3 and input_channels % 3 == 0:
            repeated = first_conv.weight.repeat(1, input_channels // 3, 1, 1) / float(input_channels // 3)
            replacement.weight.copy_(repeated[:, :input_channels])
        else:
            torch.nn.init.kaiming_normal_(replacement.weight, mode="fan_out")
        if replacement.bias is not None:
            replacement.bias.zero_()
    model.features[0][0] = replacement
    last_linear = model.classifier[-1]
    model.classifier[-1] = torch.nn.Linear(last_linear.in_features, 2)
    freeze_backbone_except_head(model)
    return model


def freeze_backbone_except_head(model: Any) -> None:
    for parameter in model.parameters():
        parameter.requires_grad = False
    for parameter in model.classifier.parameters():
        parameter.requires_grad = True
    for parameter in model.features[-1].parameters():
        parameter.requires_grad = True


class TwoStreamMobileNet:
    def __init__(self, *, flow_channels: int, pretrained: bool = False) -> None:
        import torch

        self.torch = torch
        self.rgb = create_feature_branch(input_channels=9, pretrained=pretrained)
        self.flow = create_feature_branch(input_channels=flow_channels, pretrained=pretrained)
        self.classifier = torch.nn.Linear(2048, 2)

    def __call__(self, inputs: Any) -> Any:
        return self.forward(inputs)

    def parameters(self) -> Any:
        return list(self.rgb.parameters()) + list(self.flow.parameters()) + list(self.classifier.parameters())

    def state_dict(self) -> dict[str, Any]:
        return {"rgb": self.rgb.state_dict(), "flow": self.flow.state_dict(), "classifier": self.classifier.state_dict()}

    def load_state_dict(self, state: dict[str, Any]) -> None:
        self.rgb.load_state_dict(state["rgb"])
        self.flow.load_state_dict(state["flow"])
        self.classifier.load_state_dict(state["classifier"])

    def train(self, mode: bool = True) -> "TwoStreamMobileNet":
        self.rgb.train(mode)
        self.flow.train(mode)
        self.classifier.train(mode)
        return self

    def eval(self) -> "TwoStreamMobileNet":
        return self.train(False)

    def to(self, device: str) -> "TwoStreamMobileNet":
        self.rgb.to(device)
        self.flow.to(device)
        self.classifier.to(device)
        return self

    def forward(self, inputs: Any) -> Any:
        rgb, flow = inputs
        features = self.torch.cat([self.rgb(rgb), self.flow(flow)], dim=1)
        return self.classifier(features)


def create_feature_branch(*, input_channels: int, pretrained: bool = False) -> Any:
    import torch

    model = create_mobilenet_classifier(input_channels=input_channels, pretrained=pretrained)
    model.classifier[-1] = torch.nn.Identity()
    return model


def create_torchvision_video_classifier(*, pretrained: bool = False) -> Any:
    import torch
    from torchvision.models.video import R3D_18_Weights, r3d_18

    weights = None
    if pretrained:
        try:
            weights = R3D_18_Weights.DEFAULT
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("%s pretrained weights unavailable; using random init: %s", TORCHVISION_VIDEO_BACKBONE, exc)
            weights = None
    model = r3d_18(weights=weights)
    model.fc = torch.nn.Linear(model.fc.in_features, 2)
    freeze_torchvision_video_except_head(model)
    return model


def freeze_torchvision_video_except_head(model: Any) -> None:
    for parameter in model.parameters():
        parameter.requires_grad = False
    for parameter in model.layer4.parameters():
        parameter.requires_grad = True
    for parameter in model.fc.parameters():
        parameter.requires_grad = True


def create_videomae_classifier(*, pretrained: bool = False) -> Any:
    from transformers import VideoMAEConfig, VideoMAEForVideoClassification

    config = VideoMAEConfig(
        name_or_path=VIDEOMAE_MODEL_NAME,
        num_labels=2,
        image_size=224,
        num_frames=16,
        patch_size=16,
        tubelet_size=2,
        hidden_size=768,
        num_hidden_layers=12,
        num_attention_heads=12,
        intermediate_size=3072,
        id2label={0: "refute", 1: "assert"},
        label2id={"refute": 0, "assert": 1},
    )
    if pretrained:
        try:
            model = VideoMAEForVideoClassification.from_pretrained(
                VIDEOMAE_MODEL_NAME,
                config=config,
                ignore_mismatched_sizes=True,
            )
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("%s pretrained weights unavailable; using random init: %s", VIDEOMAE_MODEL_NAME, exc)
            model = VideoMAEForVideoClassification(config)
    else:
        model = VideoMAEForVideoClassification(config)
    freeze_videomae_except_head(model)
    return model


def freeze_videomae_except_head(model: Any) -> None:
    for parameter in model.parameters():
        parameter.requires_grad = False
    encoder_layers = getattr(getattr(getattr(model, "videomae", None), "encoder", None), "layer", None)
    if encoder_layers:
        for parameter in encoder_layers[-1].parameters():
            parameter.requires_grad = True
    for parameter in model.classifier.parameters():
        parameter.requires_grad = True


class ClipManifestDataset:
    def __init__(self, *, rows: list[dict[str, Any]], arch: str) -> None:
        self.rows = rows
        self.arch = arch

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, index: int) -> tuple[Any, int]:
        row = self.rows[index]
        label = label_to_index(row.get("label"))
        if self.arch == "twostream":
            return (load_stack3_tensor(row), load_flow_tensor(row)), label
        if self.arch == "stack3_mobilenet":
            return load_stack3_tensor(row), label
        if self.arch in {"video_x3d", "video_vmae"}:
            return load_clip_tensor(row), label
        raise ValueError(f"unsupported arch: {self.arch}")


def train_student(
    *,
    manifest_path: Path,
    arch: str,
    out_dir: Path,
    epochs: int = 1,
    batch_size: int = 2,
    device: str = "cpu",
    pretrained: bool = False,
) -> dict[str, Any]:
    statuses = arch_availability()
    status = statuses.get(arch)
    if status is None:
        raise ValueError(f"unsupported arch: {arch}")
    if not status.available:
        LOGGER.warning("Skipping %s: %s", arch, status.reason)
        return {"arch": arch, "status": "skipped", "reason": status.reason}
    rows = labeled_rows(manifest_path)
    train_rows, val_rows = time_block_split(rows)
    if not train_rows or not val_rows:
        raise ValueError("labeled manifest must include enough samples for a time-block train/validation split")
    import torch
    from torch.utils.data import DataLoader

    flow_channels = infer_flow_channels(rows)
    model = create_model(arch, flow_channels=flow_channels, pretrained=pretrained).to(device)
    optimizer = torch.optim.Adam([p for p in model.parameters() if p.requires_grad], lr=1e-3)
    loss_fn = torch.nn.CrossEntropyLoss()
    train_loader = DataLoader(
        ClipManifestDataset(rows=train_rows, arch=arch),
        batch_size=batch_size,
        shuffle=False,
        drop_last=len(train_rows) > batch_size,
    )
    for _epoch in range(epochs):
        model.train()
        for features, labels in train_loader:
            features = move_features(features, device)
            labels = labels.to(device)
            optimizer.zero_grad()
            logits = model_logits(model, features, arch)
            loss = loss_fn(logits, labels)
            loss.backward()
            optimizer.step()
    metrics = evaluate_student(model=model, rows=val_rows, arch=arch, batch_size=batch_size, device=device)
    out_dir.mkdir(parents=True, exist_ok=True)
    model_path = out_dir / f"{arch}.pt"
    torch.save(
        {
            "arch": arch,
            "state_dict": model.state_dict(),
            "flow_channels": flow_channels,
            "pretrained": pretrained,
        },
        model_path,
    )
    return {"arch": arch, "status": "trained", "model_path": str(model_path), "metrics": metrics}


def train_arch_selection(
    *,
    manifest_path: Path,
    arch: str,
    out_dir: Path,
    epochs: int = 1,
    batch_size: int = 2,
    device: str = "cpu",
    pretrained: bool = False,
) -> list[dict[str, Any]]:
    archs = list(ARCHES) if arch == "all" else [arch]
    results = []
    for item in archs:
        results.append(
            train_student(
                manifest_path=manifest_path,
                arch=item,
                out_dir=out_dir,
                epochs=epochs,
                batch_size=batch_size,
                device=device,
                pretrained=pretrained,
            )
        )
    write_comparison_table(out_dir / "comparison_table.md", results)
    return results


def evaluate_student(*, model: Any, rows: list[dict[str, Any]], arch: str, batch_size: int, device: str) -> dict[str, Any]:
    import torch
    from torch.utils.data import DataLoader

    loader = DataLoader(ClipManifestDataset(rows=rows, arch=arch), batch_size=batch_size, shuffle=False)
    correct = 0
    total = 0
    model.eval()
    with torch.no_grad():
        for features, labels in loader:
            features = move_features(features, device)
            labels = labels.to(device)
            logits = model_logits(model, features, arch)
            predictions = torch.argmax(logits, dim=1)
            correct += int((predictions == labels).sum().item())
            total += int(labels.numel())
    return {"accuracy": 0.0 if total == 0 else correct / total, "validation_samples": total}


def load_student_judge(*, model_path: Path, arch: str) -> Any:
    import torch

    checkpoint = torch.load(model_path, map_location="cpu")
    model = create_model(arch, flow_channels=int(checkpoint.get("flow_channels", 30)), pretrained=False)
    model.load_state_dict(checkpoint["state_dict"])
    model.eval()

    def judge(candidate: dict[str, Any]) -> dict[str, Any]:
        row = candidate if "paths" in candidate else {"paths": candidate.get("paths", {})}
        if arch == "twostream":
            features = (load_stack3_tensor(row).unsqueeze(0), load_flow_tensor(row).unsqueeze(0))
        elif arch == "stack3_mobilenet":
            features = load_stack3_tensor(row).unsqueeze(0)
        else:
            features = load_clip_tensor(row).unsqueeze(0)
        with torch.no_grad():
            logits = model_logits(model, features, arch)
            probs = torch.softmax(logits, dim=1)[0]
        score = float(probs[1].item())
        return {"decision": "assert" if score >= 0.5 else "refute", "score": score}

    return judge


def load_stack3_tensor(row: dict[str, Any]) -> Any:
    import torch

    path = Path(str(row["paths"]["stack3"]))
    array = np.load(path)["data"].astype(np.float32) / 255.0
    if array.shape[0] != 3 or array.shape[-1] != 3:
        raise ValueError("stack3 encoding must have shape 3,H,W,3")
    chw = array.transpose(0, 3, 1, 2).reshape(9, array.shape[1], array.shape[2])
    return torch.from_numpy(chw)


def load_clip_tensor(row: dict[str, Any]) -> Any:
    import torch

    path = Path(str(row["paths"]["clip"]))
    array = np.load(path)["data"].astype(np.float32) / 255.0
    if array.ndim != 4 or array.shape[-1] != 3:
        raise ValueError("clip encoding must have shape T,H,W,3")
    tensor = array.transpose(3, 0, 1, 2)
    return torch.from_numpy(tensor)


def load_flow_tensor(row: dict[str, Any]) -> Any:
    import torch

    path = Path(str(row["paths"]["flow"]))
    array = np.load(path)["data"].astype(np.float32)
    if array.ndim != 4 or array.shape[-1] != 2:
        raise ValueError("flow encoding must have shape T,H,W,2")
    tensor = array.transpose(0, 3, 1, 2).reshape(array.shape[0] * 2, array.shape[1], array.shape[2])
    return torch.from_numpy(tensor)


def label_to_index(label: Any) -> int:
    if label in LABEL_TO_INDEX:
        return int(LABEL_TO_INDEX[label])
    raise ValueError(f"unsupported label: {label}")


def labeled_rows(manifest_path: Path) -> list[dict[str, Any]]:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    rows = [row for row in payload.get("samples", []) if row.get("label") is not None]
    if not rows:
        raise ValueError("manifest has no labeled samples")
    return rows


def time_block_split(rows: list[dict[str, Any]], *, val_fraction: float = 0.25) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if len(rows) < 2:
        return rows, []
    ordered = sorted(rows, key=lambda row: (str(row.get("source", "")), float(row.get("center_sec", 0.0))))
    val_count = max(1, int(round(len(ordered) * val_fraction)))
    val_count = min(val_count, len(ordered) - 1)
    return ordered[:-val_count], ordered[-val_count:]


def infer_flow_channels(rows: list[dict[str, Any]]) -> int:
    for row in rows:
        paths = row.get("paths") or {}
        if "flow" in paths:
            array = np.load(Path(str(paths["flow"])))["data"]
            return int(array.shape[0] * 2)
    return 30


def move_features(features: Any, device: str) -> Any:
    if isinstance(features, (list, tuple)):
        return tuple(item.to(device) for item in features)
    return features.to(device)


def model_logits(model: Any, features: Any, arch: str) -> Any:
    if arch == "video_vmae":
        import torch.nn.functional as F
        # VideoMAE expects B,T,C,H,W at 224x224; the shared clip tensor is B,C,T,H,W
        # at the native zone-crop size, so resize each frame to the model input.
        vid = features.permute(0, 2, 1, 3, 4)
        b, t, c, h, w = vid.shape
        if (h, w) != (224, 224):
            vid = F.interpolate(
                vid.reshape(b * t, c, h, w), size=(224, 224), mode="bilinear", align_corners=False
            ).reshape(b, t, c, 224, 224)
        result = model(pixel_values=vid)
    else:
        result = model(features)
    return result.logits if hasattr(result, "logits") else result


def write_comparison_table(path: Path, results: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["| arch | status | accuracy | reason |", "| --- | --- | ---: | --- |"]
    for result in results:
        metrics = result.get("metrics") or {}
        accuracy = metrics.get("accuracy")
        lines.append(
            f"| {result.get('arch')} | {result.get('status')} | "
            f"{'' if accuracy is None else round(float(accuracy), 4)} | {result.get('reason') or ''} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_synthetic_clip_manifest(path: Path, *, sample_count: int = 6, image_size: int = 32) -> dict[str, Any]:
    rows = []
    asset_dir = path.parent / "synthetic_assets"
    asset_dir.mkdir(parents=True, exist_ok=True)
    for index in range(sample_count):
        label = "assert" if index % 2 == 0 else "refute"
        rng = np.random.default_rng(index)
        stack3 = rng.integers(0, 255, size=(3, image_size, image_size, 3), dtype=np.uint8)
        clip = rng.integers(0, 255, size=(16, image_size, image_size, 3), dtype=np.uint8)
        flow = rng.normal(0, 0.1, size=(15, image_size, image_size, 2)).astype(np.float32)
        if label == "assert":
            stack3[:, image_size // 3 : image_size // 3 + 2, :, :] = 255
            clip[:, image_size // 3 : image_size // 3 + 2, :, :] = 255
            flow[:, image_size // 3 : image_size // 3 + 2, :, 0] += 1.0
        paths = {}
        for name, array in {"stack3": stack3, "clip": clip, "flow": flow}.items():
            asset_path = asset_dir / f"sample-{index:03d}.{name}.npz"
            np.savez_compressed(asset_path, data=array)
            paths[name] = str(asset_path)
        rows.append(
            {
                "candidate_id": f"synthetic-{index:03d}",
                "source": "synthetic",
                "center_sec": float(index),
                "start_sec": float(index),
                "end_sec": float(index + 1),
                "paths": paths,
                "label": label,
            }
        )
    manifest = {"schema_version": "factory-vision-clip-dataset-v1", "samples": rows}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def _has_module(name: str) -> bool:
    return importlib.util.find_spec(name) is not None
