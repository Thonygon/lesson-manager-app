from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd
from PIL import Image, ImageDraw


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _lang(lang: str | None) -> str:
    safe = _clean_text(lang).lower()
    return safe if safe in {"en", "es", "tr"} else "en"


def _copy(lang: str, key: str) -> str:
    strings = {
        "en": {
            "label_balance": "Label balance",
            "telemetry_surface": "Telemetry coverage by surface",
            "decision_urgency": "Prioritized decisions by urgency",
            "component_maturity": "Component maturity distribution",
            "class_distribution": "Class distribution",
            "split_timeline": "Chronological split timeline",
            "model_metrics": "Model comparison snapshot",
            "feature_missingness": "Feature missingness snapshot",
            "runtime": "Runtime comparison",
            "roc": "ROC curves",
            "pr": "Precision-recall curves",
            "calibration": "Calibration curves",
            "probability": "Predicted probability distribution",
            "confusion": "Confusion matrix",
            "unavailable_curve": "Curve unavailable from stored predictions",
            "count": "Count",
            "share": "Share",
            "rate": "Rate",
            "score": "Score",
            "seconds": "Seconds",
            "probability_axis": "Predicted probability",
            "timeline_axis": "Assigned at",
        },
        "es": {
            "label_balance": "Balance de etiquetas",
            "telemetry_surface": "Cobertura de telemetría por superficie",
            "decision_urgency": "Decisiones priorizadas por urgencia",
            "component_maturity": "Distribución de madurez de componentes",
            "class_distribution": "Distribución de clases",
            "split_timeline": "Línea temporal del corte cronológico",
            "model_metrics": "Resumen de comparación de modelos",
            "feature_missingness": "Resumen de valores faltantes por variable",
            "runtime": "Comparación de tiempos de ejecución",
            "roc": "Curvas ROC",
            "pr": "Curvas de precisión-recall",
            "calibration": "Curvas de calibración",
            "probability": "Distribución de probabilidades predichas",
            "confusion": "Matriz de confusión",
            "unavailable_curve": "Curva no disponible con las predicciones almacenadas",
            "count": "Conteo",
            "share": "Proporción",
            "rate": "Tasa",
            "score": "Puntuación",
            "seconds": "Segundos",
            "probability_axis": "Probabilidad predicha",
            "timeline_axis": "Fecha de asignación",
        },
        "tr": {
            "label_balance": "Etiket dengesi",
            "telemetry_surface": "Yüzeye göre telemetri kapsamı",
            "decision_urgency": "Aciliyete göre öncelikli kararlar",
            "component_maturity": "Bileşen olgunluk dağılımı",
            "class_distribution": "Sınıf dağılımı",
            "split_timeline": "Kronolojik ayrım zaman çizelgesi",
            "model_metrics": "Model karşılaştırma özeti",
            "feature_missingness": "Özellik eksiklik özeti",
            "runtime": "Çalışma süresi karşılaştırması",
            "roc": "ROC eğrileri",
            "pr": "Precision-recall eğrileri",
            "calibration": "Kalibrasyon eğrileri",
            "probability": "Tahmin edilen olasılık dağılımı",
            "confusion": "Karışıklık matrisi",
            "unavailable_curve": "Kayıtlı tahminlerden eğri üretilemedi",
            "count": "Sayı",
            "share": "Pay",
            "rate": "Oran",
            "score": "Skor",
            "seconds": "Saniye",
            "probability_axis": "Tahmin olasılığı",
            "timeline_axis": "Atama zamanı",
        },
    }
    return strings[_lang(lang)].get(key, key)


def _artifact_checksum(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted({Path(item) for item in paths if Path(item).exists()}):
        digest.update(path.name.encode("utf-8"))
        try:
            digest.update(path.read_bytes())
        except Exception:
            digest.update(str(path.stat().st_mtime_ns).encode("utf-8"))
    return digest.hexdigest()[:10] or "nochecksum"


def _chart_path(output_dir: Path, chart_type: str, checksum: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir / f"{chart_type}_{checksum}.png"


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _humanize_identifier(value: Any) -> str:
    safe = " ".join(str(value or "").split()).strip()
    if not safe:
        return "No data"
    tokens = safe.replace(".", " ").replace("_", " ").replace("-", " ").split()
    words: list[str] = []
    for token in tokens:
        lower = token.lower()
        if lower in {"id", "json", "csv", "md", "pdf", "docx", "roc", "auc", "f1"}:
            words.append(token.upper())
        elif lower.startswith("v") and lower[1:].isdigit():
            words.append(token.upper())
        else:
            words.append(token.capitalize())
    return " ".join(words)


def _build_palette() -> dict[str, str]:
    return {
        "navy": "#1F3A5F",
        "blue": "#2E74B5",
        "teal": "#17807E",
        "green": "#2F855A",
        "gold": "#B7791F",
        "red": "#C53030",
        "gray": "#718096",
        "light": "#EDF2F7",
    }


def _get_plt():
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        return plt
    except Exception:
        return None


def _placeholder_chart(path: Path, title: str, rows: list[str]) -> None:
    image = Image.new("RGB", (1400, 900), "white")
    draw = ImageDraw.Draw(image)
    draw.text((70, 48), title, fill="#102A43")
    y = 140
    for row in rows[:14]:
        draw.text((100, y), row, fill="#334155")
        y += 44
    image.save(path)


def _draw_pil_bar_chart(path: Path, title: str, labels: list[str], values: list[float], *, horizontal: bool = False, ylabel: str = "") -> None:
    width, height = 1400, 900
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    palette = list(_build_palette().values())
    draw.text((70, 48), title, fill="#102A43")
    if ylabel:
        draw.text((70, 95), ylabel, fill="#486581")
    left, top, right, bottom = 120, 150, width - 90, height - 120
    draw.rectangle((left, top, right, bottom), outline="#D9E2EC", width=2)
    if not labels or not values:
        _placeholder_chart(path, title, ["No data"])
        return
    max_value = max(max(values), 1.0)
    if horizontal:
        step = (bottom - top) / max(len(labels), 1)
        for idx, (label, value) in enumerate(zip(labels, values)):
            y = top + idx * step + 10
            bar_len = (right - left - 180) * (max(value, 0.0) / max_value)
            draw.text((left + 10, y), str(label)[:28], fill="#243B53")
            draw.rectangle((left + 220, y + 10, left + 220 + bar_len, y + 40), fill=palette[idx % len(palette)])
            draw.text((left + 230 + bar_len, y + 8), f"{round(value, 3)}", fill="#486581")
    else:
        step = (right - left) / max(len(labels), 1)
        for idx, (label, value) in enumerate(zip(labels, values)):
            x = left + idx * step + 25
            bar_height = (bottom - top - 120) * (max(value, 0.0) / max_value)
            draw.rectangle((x, bottom - 60 - bar_height, x + 70, bottom - 60), fill=palette[idx % len(palette)])
            draw.text((x, bottom - 42), str(label)[:12], fill="#243B53")
            draw.text((x, bottom - 85 - bar_height), f"{round(value, 3)}", fill="#486581")
    image.save(path)


def _draw_pil_curve_chart(path: Path, title: str, curve_rows: list[tuple[str, list[float], list[float]]], *, diagonal: bool = False) -> None:
    width, height = 1400, 900
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    draw.text((70, 48), title, fill="#102A43")
    left, top, right, bottom = 120, 140, width - 120, height - 140
    draw.rectangle((left, top, right, bottom), outline="#D9E2EC", width=2)
    if diagonal:
        draw.line((left, bottom, right, top), fill="#9FB3C8", width=2)
    palette = list(_build_palette().values())
    if not curve_rows:
        _placeholder_chart(path, title, ["No stored curve data"])
        return
    for idx, (label, xs, ys) in enumerate(curve_rows):
        points = []
        for x_value, y_value in zip(xs, ys):
            x = left + (right - left) * max(0.0, min(1.0, float(x_value)))
            y = bottom - (bottom - top) * max(0.0, min(1.0, float(y_value)))
            points.append((x, y))
        if len(points) >= 2:
            draw.line(points, fill=palette[idx % len(palette)], width=4)
        draw.text((right - 220, top + 24 + idx * 34), str(label)[:28], fill=palette[idx % len(palette)])
    image.save(path)


def _draw_pil_confusion_chart(path: Path, title: str, matrix: list[list[int]]) -> None:
    width, height = 900, 900
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    draw.text((70, 48), title, fill="#102A43")
    left, top, size = 160, 180, 240
    colors = ["#DCE6F4", "#B8CCE4", "#9FBAD7", "#7EA6CA"]
    flat = [matrix[0][0], matrix[0][1], matrix[1][0], matrix[1][1]]
    max_value = max(max(flat), 1)
    idx = 0
    for row in range(2):
        for col in range(2):
            value = matrix[row][col]
            intensity = int((value / max_value) * 3)
            x1 = left + col * size
            y1 = top + row * size
            draw.rectangle((x1, y1, x1 + size, y1 + size), fill=colors[min(intensity, 3)], outline="#486581", width=3)
            draw.text((x1 + 90, y1 + 100), str(value), fill="#102A43")
            idx += 1
    draw.text((left + 75, top - 40), "Pred 0", fill="#243B53")
    draw.text((left + size + 75, top - 40), "Pred 1", fill="#243B53")
    draw.text((left - 80, top + 100), "Actual 0", fill="#243B53")
    draw.text((left - 80, top + size + 100), "Actual 1", fill="#243B53")
    image.save(path)


def _draw_pil_timeline_chart(path: Path, title: str, labels: list[str], cutoff: str) -> None:
    width, height = 1400, 520
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    draw.text((70, 48), title, fill="#102A43")
    left, right, y = 120, width - 120, 280
    draw.line((left, y, right, y), fill="#BCCCDC", width=4)
    if labels:
        step = (right - left) / max(len(labels) - 1, 1)
        for idx, label in enumerate(labels[:20]):
            x = left + idx * step
            draw.ellipse((x - 10, y - 10, x + 10, y + 10), fill="#2E74B5")
        cutoff_x = left + ((right - left) * 0.6)
        draw.line((cutoff_x, y - 80, cutoff_x, y + 80), fill="#C53030", width=4)
        draw.text((cutoff_x - 30, y - 110), "Cutoff", fill="#C53030")
    draw.text((70, 420), f"Stored cutoff: {cutoff}", fill="#486581")
    image.save(path)


def _draw_pil_histogram(path: Path, title: str, rows: list[tuple[str, list[float]]], xlabel: str) -> None:
    width, height = 1400, 900
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    palette = list(_build_palette().values())
    draw.text((70, 48), title, fill="#102A43")
    draw.text((70, 95), xlabel, fill="#486581")
    left, top, right, bottom = 120, 160, width - 120, height - 140
    draw.rectangle((left, top, right, bottom), outline="#D9E2EC", width=2)
    if not rows:
        _placeholder_chart(path, title, ["No stored scores"])
        return
    bar_width = 36
    gap = 10
    for group_idx, (label, values) in enumerate(rows[:3]):
        bins = [0] * 10
        for value in values:
            bucket = min(9, max(0, int(float(value) * 10)))
            bins[bucket] += 1
        max_bin = max(max(bins), 1)
        base_x = left + group_idx * 360 + 20
        draw.text((base_x, top + 10), str(label)[:24], fill=palette[group_idx % len(palette)])
        for idx, count in enumerate(bins):
            x = base_x + idx * (bar_width + gap)
            bar_height = (bottom - top - 120) * (count / max_bin)
            draw.rectangle((x, bottom - 40 - bar_height, x + bar_width, bottom - 40), fill=palette[group_idx % len(palette)])
    image.save(path)


def _save_current(path: Path) -> None:
    plt = _get_plt()
    if plt is None:
        _placeholder_chart(path, path.stem.replace("_", " ").title(), [])
        return
    plt.tight_layout()
    plt.savefig(path, dpi=220, bbox_inches="tight")
    plt.close()


def _plot_bar(path: Path, title: str, labels: list[str], values: list[float], *, horizontal: bool = False, ylabel: str = "") -> None:
    plt = _get_plt()
    if plt is None:
        _draw_pil_bar_chart(path, title, labels, values, horizontal=horizontal, ylabel=ylabel)
        return
    colors = list(_build_palette().values())
    plt.figure(figsize=(7.2, 4.4))
    if horizontal:
        plt.barh(labels, values, color=colors[: len(labels)])
    else:
        plt.bar(labels, values, color=colors[: len(labels)])
    plt.title(title, fontsize=12, pad=10)
    if ylabel:
        plt.ylabel(ylabel)
    plt.grid(axis="y" if not horizontal else "x", linestyle="--", alpha=0.25)
    _save_current(path)


def _plot_timeline(path: Path, title: str, assigned_at: pd.Series, cutoff: str, *, ylabel: str) -> None:
    plt = _get_plt()
    if plt is None:
        labels = assigned_at.dropna().astype(str).head(20).tolist()
        _draw_pil_timeline_chart(path, title, labels, cutoff)
        return
    dates = pd.to_datetime(assigned_at, errors="coerce", utc=True).dropna().sort_values()
    plt.figure(figsize=(7.4, 2.6))
    if dates.empty:
        plt.text(0.5, 0.5, "No stored timeline data", ha="center", va="center")
        plt.axis("off")
        _save_current(path)
        return
    y = [1] * len(dates)
    plt.scatter(dates, y, c=_build_palette()["blue"], s=28)
    cutoff_dt = pd.to_datetime(cutoff, errors="coerce", utc=True)
    if pd.notna(cutoff_dt):
        plt.axvline(cutoff_dt, color=_build_palette()["red"], linestyle="--", linewidth=1.6)
    plt.yticks([])
    plt.xlabel(ylabel)
    plt.title(title, fontsize=12, pad=10)
    _save_current(path)


def _plot_confusion(path: Path, title: str, matrix: list[list[int]]) -> None:
    plt = _get_plt()
    if plt is None:
        _draw_pil_confusion_chart(path, title, matrix)
        return
    plt.figure(figsize=(4.3, 4.0))
    plt.imshow(matrix, cmap="Blues")
    plt.title(title, fontsize=12, pad=10)
    plt.xticks([0, 1], ["Pred 0", "Pred 1"])
    plt.yticks([0, 1], ["Actual 0", "Actual 1"])
    for row_idx, row in enumerate(matrix):
        for col_idx, value in enumerate(row):
            plt.text(col_idx, row_idx, str(int(value)), ha="center", va="center", color="black")
    _save_current(path)


def _plot_curve(path: Path, title: str, curve_rows: list[tuple[str, list[float], list[float]]], *, xlabel: str, ylabel: str, diagonal: bool = False) -> None:
    plt = _get_plt()
    if plt is None:
        _draw_pil_curve_chart(path, title, curve_rows, diagonal=diagonal)
        return
    plt.figure(figsize=(6.8, 4.5))
    if diagonal:
        plt.plot([0, 1], [0, 1], linestyle="--", color=_build_palette()["gray"], linewidth=1)
    if not curve_rows:
        plt.text(0.5, 0.5, title, ha="center", va="center")
        plt.text(0.5, 0.42, "No stored curve data", ha="center", va="center", color=_build_palette()["gray"])
        plt.axis("off")
        _save_current(path)
        return
    for idx, (label, xs, ys) in enumerate(curve_rows):
        plt.plot(xs, ys, linewidth=2.0, label=label, color=list(_build_palette().values())[idx % 6])
    plt.title(title, fontsize=12, pad=10)
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.legend(fontsize=8, frameon=False)
    plt.grid(alpha=0.2, linestyle="--")
    _save_current(path)


def _plot_probability_distribution(path: Path, title: str, rows: list[tuple[str, list[float]]], xlabel: str) -> None:
    plt = _get_plt()
    if plt is None:
        _draw_pil_histogram(path, title, rows, xlabel)
        return
    plt.figure(figsize=(6.8, 4.4))
    if not rows:
        plt.text(0.5, 0.5, title, ha="center", va="center")
        plt.axis("off")
        _save_current(path)
        return
    for idx, (label, values) in enumerate(rows):
        if not values:
            continue
        plt.hist(values, bins=10, alpha=0.5, label=label, color=list(_build_palette().values())[idx % 6])
    plt.title(title, fontsize=12, pad=10)
    plt.xlabel(xlabel)
    plt.ylabel(_copy("en", "count"))
    plt.legend(fontsize=8, frameon=False)
    plt.grid(axis="y", alpha=0.2, linestyle="--")
    _save_current(path)


def _parse_confusion(value: Any) -> list[list[int]]:
    text = _clean_text(value)
    if not text:
        return [[0, 0], [0, 0]]
    try:
        parsed = json.loads(text)
    except Exception:
        return [[0, 0], [0, 0]]
    if not isinstance(parsed, list) or len(parsed) != 2:
        return [[0, 0], [0, 0]]
    return [[int(item or 0) for item in row[:2]] for row in parsed[:2]]


def _prediction_frame(artifacts: dict[str, Path]) -> pd.DataFrame:
    path = artifacts.get("holdout_predictions_csv")
    if not path or not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def _feature_frame(artifacts: dict[str, Path]) -> pd.DataFrame:
    path = artifacts.get("feature_audit_csv")
    if not path or not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def _model_rows(context: dict[str, Any], artifacts: dict[str, Path]) -> list[dict[str, Any]]:
    path = artifacts.get("model_comparison_csv")
    if path and path.exists():
        try:
            df = pd.read_csv(path)
            return df.fillna("").to_dict("records")
        except Exception:
            pass
    return list((context.get("detail", {}).get("model_results") or {}).get("models_compared") or [])


def build_report_charts(
    report_type: str,
    run_id: str,
    language: str,
    context: dict[str, Any],
    artifacts: dict[str, Path],
    output_dir: Path,
) -> dict[str, Path]:
    lang = _lang(language)
    checksum = _artifact_checksum(list(artifacts.values()))
    charts: dict[str, Path] = {}
    telemetry = context.get("telemetry") or {}
    run_summary = context.get("run_summary") or {}
    evaluation = run_summary.get("evaluation") or {}
    dataset_summary = context.get("dataset_summary") or {}
    model_rows = _model_rows(context, artifacts)
    predictions = _prediction_frame(artifacts)
    feature_df = _feature_frame(artifacts)
    palette = _build_palette()

    if report_type in {"executive_docx", "academic_docx", "technical_docx"}:
        path = _chart_path(output_dir, "label_balance", checksum)
        if not path.exists():
            positive = int((run_summary.get("dataset") or dataset_summary).get("positive_count") or context.get("detail", {}).get("positive_label_count") or 0)
            negative = int((run_summary.get("dataset") or dataset_summary).get("negative_count") or context.get("detail", {}).get("negative_label_count") or 0)
            _plot_bar(path, _copy(lang, "label_balance"), ["Positive", "Negative"], [positive, negative], ylabel=_copy(lang, "count"))
        charts["label_balance"] = path

    if report_type == "executive_docx":
        path = _chart_path(output_dir, "component_maturity", checksum)
        if not path.exists():
            counts: dict[str, int] = {}
            for row in context.get("portfolio") or []:
                label = _clean_text(row.get("data_maturity") or "unknown").replace("_", " ").title()
                counts[label] = counts.get(label, 0) + 1
            _plot_bar(path, _copy(lang, "component_maturity"), list(counts.keys()) or ["No data"], list(counts.values()) or [0], ylabel=_copy(lang, "count"))
        charts["component_maturity"] = path

        path = _chart_path(output_dir, "telemetry_surface", checksum)
        if not path.exists():
            surfaces = telemetry.get("by_surface") or []
            labels = [_humanize_identifier(row.get("surface") or "unknown") for row in surfaces] or ["No data"]
            values = [round(_float(row.get("matched_opens")) / max(_float(row.get("exposures")), 1.0), 3) for row in surfaces] or [0.0]
            _plot_bar(path, _copy(lang, "telemetry_surface"), labels, values, ylabel=_copy(lang, "rate"))
        charts["telemetry_surface"] = path

        path = _chart_path(output_dir, "decision_urgency", checksum)
        if not path.exists():
            urgency_counts: dict[str, int] = {}
            for row in context.get("decisions") or []:
                urgency = _clean_text(row.get("urgency") or "unknown").title()
                urgency_counts[urgency] = urgency_counts.get(urgency, 0) + 1
            _plot_bar(path, _copy(lang, "decision_urgency"), list(urgency_counts.keys()) or ["No data"], list(urgency_counts.values()) or [0], ylabel=_copy(lang, "count"))
        charts["decision_urgency"] = path

    if report_type in {"academic_docx", "technical_docx"}:
        path = _chart_path(output_dir, "split_timeline", checksum)
        if not path.exists():
            assigned = predictions.get("assigned_at") if "assigned_at" in predictions.columns else pd.Series(dtype=str)
            _plot_timeline(
                path,
                _copy(lang, "split_timeline"),
                assigned,
                _clean_text(evaluation.get("cutoff_timestamp") or context.get("academic", {}).get("train_holdout_split", {}).get("chronological_cutoff")),
                ylabel=_copy(lang, "timeline_axis"),
            )
        charts["split_timeline"] = path

        path = _chart_path(output_dir, "model_metrics", checksum)
        if not path.exists():
            labels = [str(row.get("model_name") or "model") for row in model_rows[:8]]
            values = [_float(row.get("roc_auc")) for row in model_rows[:8]]
            _plot_bar(path, _copy(lang, "model_metrics"), labels or ["No data"], values or [0], horizontal=True, ylabel=_copy(lang, "score"))
        charts["model_metrics"] = path

    if report_type == "technical_docx":
        path = _chart_path(output_dir, "feature_missingness", checksum)
        if not path.exists():
            top_missing = feature_df.sort_values("missing_percentage", ascending=False).head(10) if not feature_df.empty else pd.DataFrame()
            labels = top_missing.get("feature", pd.Series(dtype=str)).astype(str).tolist() or ["No data"]
            values = top_missing.get("missing_percentage", pd.Series(dtype=float)).astype(float).tolist() or [0.0]
            _plot_bar(path, _copy(lang, "feature_missingness"), labels, values, horizontal=True, ylabel="%")
        charts["feature_missingness"] = path

        path = _chart_path(output_dir, "runtime", checksum)
        if not path.exists():
            labels = [str(row.get("model_name") or "model") for row in model_rows[:8]]
            values = [_float(row.get("train_duration_seconds")) for row in model_rows[:8]]
            _plot_bar(path, _copy(lang, "runtime"), labels or ["No data"], values or [0], horizontal=True, ylabel=_copy(lang, "seconds"))
        charts["runtime"] = path

    if report_type in {"academic_docx", "technical_docx"} and not predictions.empty:
        leader = _clean_text(evaluation.get("primary_metric_leader") or context.get("detail", {}).get("primary_metric_leader"))
        threshold_leader = _clean_text(evaluation.get("best_thresholded_classifier") or leader)
        baseline = "DummyClassifier"
        curve_models = [name for name in [leader, threshold_leader, baseline] if name]

        try:
            from sklearn.calibration import calibration_curve
            from sklearn.metrics import precision_recall_curve, roc_curve
        except Exception:
            calibration_curve = None
            precision_recall_curve = None
            roc_curve = None

        roc_rows: list[tuple[str, list[float], list[float]]] = []
        pr_rows: list[tuple[str, list[float], list[float]]] = []
        calibration_rows: list[tuple[str, list[float], list[float]]] = []
        probability_rows: list[tuple[str, list[float]]] = []
        seen: set[str] = set()
        for model_name in curve_models:
            if model_name in seen:
                continue
            seen.add(model_name)
            subset = predictions[predictions.get("model_name", pd.Series(dtype=str)).astype(str) == model_name]
            if subset.empty:
                continue
            y_true = subset.get("actual_label", pd.Series(dtype=float)).astype(float).tolist()
            y_score = subset.get("predicted_probability", pd.Series(dtype=float)).astype(float).tolist()
            probability_rows.append((model_name, y_score))
            if roc_curve is not None and len(set(y_true)) > 1:
                fpr, tpr, _ = roc_curve(y_true, y_score)
                roc_rows.append((model_name, list(fpr), list(tpr)))
            if precision_recall_curve is not None and len(set(y_true)) > 1:
                precision, recall, _ = precision_recall_curve(y_true, y_score)
                pr_rows.append((model_name, list(recall), list(precision)))
            if calibration_curve is not None and len(set(y_true)) > 1:
                frac_pos, mean_pred = calibration_curve(y_true, y_score, n_bins=min(5, max(3, len(y_true) // 4)))
                calibration_rows.append((model_name, list(mean_pred), list(frac_pos)))

        path = _chart_path(output_dir, "roc_curves", checksum)
        if not path.exists():
            _plot_curve(path, _copy(lang, "roc"), roc_rows, xlabel="False positive rate", ylabel="True positive rate", diagonal=True)
        charts["roc_curves"] = path

        path = _chart_path(output_dir, "pr_curves", checksum)
        if not path.exists():
            _plot_curve(path, _copy(lang, "pr"), pr_rows, xlabel="Recall", ylabel="Precision")
        charts["pr_curves"] = path

        path = _chart_path(output_dir, "calibration_curves", checksum)
        if not path.exists():
            _plot_curve(path, _copy(lang, "calibration"), calibration_rows, xlabel="Mean predicted value", ylabel="Fraction of positives", diagonal=True)
        charts["calibration_curves"] = path

        path = _chart_path(output_dir, "probability_distribution", checksum)
        if not path.exists():
            _plot_probability_distribution(path, _copy(lang, "probability"), probability_rows, _copy(lang, "probability_axis"))
        charts["probability_distribution"] = path

        confusion_targets = {
            "leader_confusion": leader,
            "threshold_confusion": threshold_leader,
            "baseline_confusion": baseline,
        }
        for chart_key, model_name in confusion_targets.items():
            row = next((item for item in model_rows if _clean_text(item.get("model_name")) == model_name), {})
            path = _chart_path(output_dir, chart_key, checksum)
            if not path.exists():
                _plot_confusion(path, f"{_copy(lang, 'confusion')}: {model_name or 'model'}", _parse_confusion(row.get("confusion_matrix")))
            charts[chart_key] = path

    return charts
