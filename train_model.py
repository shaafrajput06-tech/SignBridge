"""Compare and save SVM and Random Forest sign classifiers honestly."""

from __future__ import annotations

import csv
import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, confusion_matrix
from sklearn.model_selection import GroupKFold, StratifiedKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

from collect_data import CSV_HEADER, DATA_PATH, FEATURE_COLUMNS, METADATA_COLUMNS
from signbridge_common import MODEL_DIR, VOCABULARY

MIN_CLASS_EXAMPLES = max(2, int(os.environ.get("SIGNBRIDGE_MIN_CLASS_EXAMPLES", "5")))
REPORT_PATH = Path(__file__).resolve().parent / "reports" / "training_report.txt"
MATRIX_PATH = Path(__file__).resolve().parent / "reports" / "confusion_matrix.csv"
METADATA_PATH = MODEL_DIR / "model_metadata.json"


def load_data(path: Path = DATA_PATH):
    if not path.exists():
        raise FileNotFoundError("No training CSV exists yet. Record examples with python collect_data.py first.")
    rows = []
    valid_labels = {item["id"] for item in VOCABULARY}
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.reader(stream)
        header = next(reader, None)
        if header != CSV_HEADER:
            raise ValueError(f"{path.name} does not match the current SignBridge data schema.")
        for number, row in enumerate(reader, 2):
            try:
                if len(row) != len(CSV_HEADER) or row[0] not in valid_labels:
                    raise ValueError("wrong columns or unknown label")
                features = [float(value) for value in row[len(METADATA_COLUMNS):]]
                if not all(np.isfinite(features)):
                    raise ValueError("non-finite feature")
                rows.append((row[0], row[1], row[2], features))
            except (ValueError, TypeError):
                print(f"Skipping malformed row {number}.")
    if not rows:
        raise ValueError("The CSV has no valid landmark examples.")
    return rows


def augment_training(X: np.ndarray, y: np.ndarray, copies: int = 2, seed: int = 41):
    rng = np.random.default_rng(seed)
    points = X.reshape(-1, 21, 3)
    features = [X]
    labels = [y]
    for _ in range(copies):
        angle = np.deg2rad(rng.uniform(-9, 9, size=len(X)))
        cosine, sine = np.cos(angle)[:, None], np.sin(angle)[:, None]
        transformed = points.copy()
        transformed[:, :, 0] = points[:, :, 0] * cosine - points[:, :, 1] * sine
        transformed[:, :, 1] = points[:, :, 0] * sine + points[:, :, 1] * cosine
        transformed += rng.normal(0, 0.008, size=transformed.shape)
        features.append(transformed.reshape(len(X), -1))
        labels.append(y)
    return np.vstack(features), np.concatenate(labels)


def model_factories():
    return {
        "SVM (RBF)": lambda: make_pipeline(StandardScaler(), SVC(C=8.0, gamma="scale", probability=False, class_weight="balanced")),
        "Random Forest": lambda: make_pipeline(StandardScaler(), RandomForestClassifier(n_estimators=300, min_samples_leaf=2, class_weight="balanced_subsample", random_state=41, n_jobs=-1)),
    }


def evaluation_splits(X, y, participants, sessions):
    unique_people = sorted(set(participants))
    unique_sessions = sorted(set(sessions))
    def groups_cover(groups):
        return all(len(set(groups[y == label])) >= 2 for label in set(y))
    if len(unique_people) >= 2 and groups_cover(participants):
        n_splits = min(5, len(unique_people))
        folds = list(GroupKFold(n_splits=n_splits).split(X, y, participants))
        return folds, f"person-grouped cross-validation ({n_splits} folds); estimates new-participant performance"
    if len(unique_sessions) >= 2 and groups_cover(sessions):
        n_splits = min(5, len(unique_sessions))
        folds = list(GroupKFold(n_splits=n_splits).split(X, y, sessions))
        return folds, f"session-grouped cross-validation ({n_splits} folds); estimates new-session performance for recorded participants"
    counts = Counter(y)
    if min(counts.values()) >= 2:
        folds_count = min(5, min(counts.values()))
        folds = list(StratifiedKFold(n_splits=folds_count, shuffle=True, random_state=41).split(X, y))
        return folds, "stratified frame-level cross-validation; weaker because frames from a recording may be in both train and validation folds"
    return [], "not evaluated: too few examples per class for a held-out split"


def _validate_each_fold(y, folds):
    labels = set(y)
    for train, test in folds:
        if set(y[train]) != labels or len(test) == 0:
            return False
    return bool(folds)


def main() -> None:
    rows = load_data()
    counts = Counter(label for label, *_ in rows)
    name_by_id = {item["id"]: item["english"] for item in VOCABULARY}
    missing = [item["english"] for item in VOCABULARY if item["id"] not in counts]
    insufficient = {label: count for label, count in counts.items() if count < MIN_CLASS_EXAMPLES}
    for item in VOCABULARY:
        count = counts.get(item["id"], 0)
        if count == 0:
            print(f"No examples: {item['english']}")
        elif count < MIN_CLASS_EXAMPLES:
            print(f"Not enough examples for trained recognition: {item['english']} has {count}; need at least {MIN_CLASS_EXAMPLES}.")

    supported = {label for label, count in counts.items() if count >= MIN_CLASS_EXAMPLES}
    training_rows = [row for row in rows if row[0] in supported]
    if len(supported) < 2:
        raise ValueError(f"At least two vocabulary items need {MIN_CLASS_EXAMPLES} examples each. Demo Recognition Mode remains available.")
    X = np.asarray([row[3] for row in training_rows], dtype=np.float32)
    y = np.asarray([row[0] for row in training_rows])
    people = np.asarray([row[1] for row in training_rows])
    sessions = np.asarray([row[2] for row in training_rows])
    folds, evaluation_method = evaluation_splits(X, y, people, sessions)
    if folds and not _validate_each_fold(y, folds):
        folds = []
        evaluation_method = "not evaluated: validation folds did not contain every trained class"

    factories = model_factories()
    comparison: dict[str, tuple[float, np.ndarray, np.ndarray]] = {}
    if folds:
        for model_name, factory in factories.items():
            predictions = np.empty(len(y), dtype=object)
            for train_index, test_index in folds:
                train_X, train_y = augment_training(X[train_index], y[train_index])
                fold_model = factory()
                fold_model.fit(train_X, train_y)
                predictions[test_index] = fold_model.predict(X[test_index])
            comparison[model_name] = (float(accuracy_score(y, predictions)), y, predictions)
    else:
        # A model can still be fitted for exploration, but no accuracy is
        # published when the data cannot be evaluated safely.
        print("No measured validation accuracy will be reported for this dataset.")

    if comparison:
        best_name = max(comparison, key=lambda model: comparison[model][0])
    else:
        best_name = "Random Forest"
    final_X, final_y = augment_training(X, y, copies=2)
    final_model = factories[best_name]()
    if best_name == "SVM (RBF)":
        final_model = make_pipeline(StandardScaler(), SVC(C=8.0, gamma="scale", probability=True, class_weight="balanced", random_state=41))
    final_model.fit(final_X, final_y)
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    accuracy = comparison[best_name][0] if comparison else None
    trained_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    bundle = {
        "model": final_model,
        "feature_version": "v1",
        "classes": [str(label) for label in final_model.classes_],
        "model_name": best_name,
        "accuracy": accuracy,
        "evaluation_method": evaluation_method,
        "trained_at": trained_at,
        "n_examples": len(training_rows),
        "class_counts": dict(Counter(y)),
        "vocabulary_ids": sorted(supported),
        "has_calibrated_probabilities": best_name == "SVM (RBF)",
        "minimum_class_examples": MIN_CLASS_EXAMPLES,
    }
    joblib.dump(bundle, MODEL_DIR / "sign_classifier.joblib")
    metadata = {key: value for key, value in bundle.items() if key != "model"}
    METADATA_PATH.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    report = [
        "SignBridge training report",
        f"Trained at: {trained_at}",
        f"Examples used: {len(training_rows)}; excluded as below class minimum: {len(rows) - len(training_rows)}",
        f"Evaluation: {evaluation_method}",
        f"Minimum examples per class for trained recognition: {MIN_CLASS_EXAMPLES}",
        "",
        "Vocabulary data counts:",
    ]
    report.extend(f"  {name_by_id[item['id']]:<28} {counts.get(item['id'], 0):>6}" for item in VOCABULARY)
    report.extend(["", "Model comparison:"])
    if comparison:
        report.extend(f"  {name}: measured validation accuracy {score:.4f}" for name, (score, _, _) in comparison.items())
        report.extend(["", f"Selected model: {best_name}", "Per-class accuracy:"])
        y_test, y_pred = comparison[best_name][1:]
        report.extend(f"  {name_by_id[label]:<28} {int(np.sum((y_test == label) & (y_pred == label))):>5}/{int(np.sum(y_test == label)):<5} = {100 * np.mean(y_pred[y_test == label] == label):5.1f}%" for label in sorted(set(y)))
        labels = sorted(set(y))
        matrix = confusion_matrix(y_test, y_pred, labels=labels)
        with MATRIX_PATH.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(["actual/predicted"] + [name_by_id[label] for label in labels])
            for label, row in zip(labels, matrix):
                writer.writerow([name_by_id[label]] + row.tolist())
    else:
        report.extend(["  No accuracy published: the dataset did not support a defensible holdout evaluation.", f"Selected model for future data collection: {best_name}"])
        with MATRIX_PATH.open("w", encoding="utf-8", newline="") as stream:
            csv.writer(stream).writerow(["Confusion matrix unavailable: validation data was insufficient"])
    report.extend(["", "No accuracy claim is made for classes below the minimum example count.", "Add recordings from different participants and sessions to improve evaluation reliability."])
    REPORT_PATH.write_text("\n".join(report) + "\n", encoding="utf-8")
    print(f"Saved classifier: {MODEL_DIR / 'sign_classifier.joblib'}")
    print(f"Saved report: {REPORT_PATH}")
    if accuracy is not None:
        print(f"Measured validation accuracy: {accuracy:.1%} ({evaluation_method})")
    else:
        print("Validation accuracy: not available for this dataset")
    print(f"Classes ready for trained recognition: {len(supported)}")


if __name__ == "__main__":
    try:
        main()
    except (FileNotFoundError, ValueError) as error:
        print(error, file=sys.stderr)
        raise SystemExit(2)
