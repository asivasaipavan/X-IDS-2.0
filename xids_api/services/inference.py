"""Lazy loader for the project's original LSTM and TCN weights."""
import os
import pickle
import threading

import numpy as np
from django.conf import settings


class IDSModelEngine:
    def __init__(self):
        self._lock = threading.Lock()
        self._loaded = False
        self._errors = []
        self.features = []
        self.labels = ["Attack", "Normal"]
        self.scaler = None
        self.lstm = None
        self.tcn = None
        self.anomaly_model = None
        self._anomaly_loaded = False
        self._anomaly_error = None

    def _load(self):
        with self._lock:
            if self._loaded:
                return
            model_dir = settings.MODEL_DIR
            try:
                with open(os.path.join(model_dir, "features.pkl"), "rb") as f:
                    self.features = pickle.load(f)
                with open(os.path.join(model_dir, "labels.pkl"), "rb") as f:
                    self.labels = list(pickle.load(f))
                with open(os.path.join(model_dir, "scaler.pkl"), "rb") as f:
                    self.scaler = pickle.load(f)
            except Exception as exc:
                self._errors.append(f"Preprocessing artifacts could not be loaded: {exc}")
                self._loaded = True
                return
            if not self.features or not self.scaler:
                self._errors.append("Feature/scaler artifacts are missing or empty.")
                self._loaded = True
                return
            try:
                from ids_app.ml_utils import build_lstm
                self.lstm = build_lstm((len(self.features), 1), len(self.labels))
                self.lstm.load_weights(os.path.join(model_dir, "lstm_weights.hdf5"))
            except Exception as exc:
                self.lstm = None
                self._errors.append(f"LSTM weights unavailable: {exc}")
            try:
                from tcn import compiled_tcn
                self.tcn = compiled_tcn(
                    return_sequences=False, num_feat=1, num_classes=len(self.labels), nb_filters=20,
                    kernel_size=6, dilations=[2 ** i for i in range(9)], nb_stacks=1,
                    max_len=len(self.features), use_skip_connections=True,
                )
                self.tcn.load_weights(os.path.join(model_dir, "tcn_weights.hdf5"))
            except Exception as exc:
                self.tcn = None
                self._errors.append(f"TCN weights unavailable: {exc}")
            self._loaded = True

    def status(self):
        self._load()
        return {
            "features": len(self.features), "labels": self.labels,
            "lstm_ready": self.lstm is not None, "tcn_ready": self.tcn is not None,
            "ready": self.lstm is not None or self.tcn is not None,
            "errors": self._errors,
            "live_feature_note": "Live packet aggregation estimates some CIC flow fields; validate against CICFlowMeter before operational use.",
        }

    def _raw_row(self, feature_map):
        return np.asarray([[float(feature_map.get(name, 0.0) or 0.0) for name in self.features]], dtype=np.float64)

    def _predict_raw(self, raw):
        self._load()
        if self.scaler is None:
            raise RuntimeError("Model scaler is unavailable. Check model/scaler.pkl.")
        scaled = self.scaler.transform(raw).astype(np.float32)
        sequence = scaled.reshape((scaled.shape[0], scaled.shape[1], 1))
        probabilities = []
        details = {}
        for name, model in (("LSTM", self.lstm), ("TCN", self.tcn)):
            if model is None:
                continue
            pred = np.asarray(model.predict(sequence, verbose=0))
            pred = pred.reshape((len(raw), -1))
            if pred.shape[1] != len(self.labels):
                continue
            pred = np.clip(pred, 0, None)
            denom = pred.sum(axis=1, keepdims=True)
            pred = np.divide(pred, denom, out=np.full_like(pred, 1 / pred.shape[1]), where=denom > 0)
            probabilities.append(pred)
            details[name] = {"prediction": self.labels[int(np.argmax(pred[0]))], "confidence": float(np.max(pred[0]))}
        if not probabilities:
            raise RuntimeError("Neither LSTM nor TCN could be loaded. " + " | ".join(self._errors))
        mean_prob = np.mean(probabilities, axis=0)
        return mean_prob, details

    def _anomaly_result(self, raw):
        if not self._anomaly_loaded:
            self._anomaly_loaded = True
            try:
                import pandas as pd
                from sklearn.ensemble import IsolationForest
                path = os.path.join(settings.DATASET_DIR, "CIC-IDS2017.csv")
                frame = pd.read_csv(path, usecols=lambda c: c in set(self.features) | {"Label"})
                labels = frame["Label"].astype(str).str.lower()
                normal = frame.loc[labels.isin(["normal", "benign"])].reindex(columns=self.features)
                normal = normal.replace([np.inf, -np.inf], np.nan).fillna(0)
                if len(normal) < 20:
                    raise RuntimeError("Not enough Normal baseline rows to fit anomaly detection.")
                baseline = normal.sample(n=min(1500, len(normal)), random_state=42).to_numpy(dtype=np.float64)
                scaled = self.scaler.transform(baseline)
                self.anomaly_model = IsolationForest(n_estimators=100, contamination=0.03, random_state=42, n_jobs=-1)
                self.anomaly_model.fit(scaled)
            except Exception as exc:
                self._anomaly_error = str(exc)
        if self.anomaly_model is None:
            return False, 0.0
        scaled_row = self.scaler.transform(raw)
        flag = int(self.anomaly_model.predict(scaled_row)[0]) == -1
        score = float(-self.anomaly_model.decision_function(scaled_row)[0])
        return flag, score

    def predict(self, feature_map):
        try:
            raw = self._raw_row(feature_map)
            probs, details = self._predict_raw(raw)
            index = int(np.argmax(probs))
            label = self.labels[index]
            anomaly_flag, anomaly_score = self._anomaly_result(raw)
            details["isolation_forest"] = {"available": self.anomaly_model is not None, "anomaly": anomaly_flag, "score": anomaly_score, "error": self._anomaly_error}
            return {
                "prediction": str(label), "confidence": float(probs[index]),
                "probabilities": {str(label): float(probs[i]) for i, label in enumerate(self.labels)},
                "model_details": details, "scorable": True,
                "anomaly_flag": anomaly_flag, "anomaly_score": anomaly_score,
            }
        except Exception as exc:
            return {
                "prediction": "UNSCORABLE", "confidence": 0.0, "probabilities": {},
                "model_details": {"error": str(exc)}, "scorable": False,
                "anomaly_flag": False, "anomaly_score": 0.0,
            }

    def explain(self, feature_map):
        """Return per-event SHAP (LSTM gradient explanation) and LIME explanations."""
        self._load()
        if self.lstm is None or self.scaler is None:
            raise RuntimeError("LSTM/scaler are required for explanations. " + " | ".join(self._errors))
        import pandas as pd
        dataset_path = os.path.join(settings.DATASET_DIR, "CIC-IDS2017.csv")
        if not os.path.exists(dataset_path):
            raise RuntimeError("CIC-IDS2017.csv is required as the explanation background dataset.")
        df = pd.read_csv(dataset_path, usecols=lambda c: c in set(self.features))
        df = df.reindex(columns=self.features).replace([np.inf, -np.inf], np.nan).fillna(0)
        background_raw = df.sample(n=min(40, len(df)), random_state=7).to_numpy(dtype=np.float64)
        target_raw = self._raw_row(feature_map)
        sample_raw = background_raw
        # def predict_fn(rows):
        #     rows = np.asarray(rows, dtype=np.float64)
        #     probs, _ = self._predict_raw(rows)
        #     probs = np.asarray(probs, dtype=np.float64)

        #     if probs.ndim == 1:
        #         probs = probs.reshape(1, -1)

        #     # Convert scores to probabilities if needed
        #     if np.any(probs < 0) or np.any(probs > 1):
        #         probs = np.exp(probs - np.max(probs, axis=1, keepdims=True))
        #         probs = probs / probs.sum(axis=1, keepdims=True)
        #     else:
        #         probs = np.clip(probs, 0, 1)
        #         probs = probs / probs.sum(axis=1, keepdims=True)

        #     return probs
        def predict_fn(rows):
            rows = np.asarray(rows, dtype=np.float64)
            probs, _ = self._predict_raw(rows)
            probs = np.asarray(probs, dtype=np.float64)

            if probs.ndim == 1:
                probs = probs.reshape(1, -1)

            if probs.shape[0] != rows.shape[0]:
                raise ValueError(
                    f"Prediction count mismatch: input={rows.shape[0]}, output={probs.shape}"
                )

            probs = np.clip(probs, 0, None)
            row_sums = probs.sum(axis=1, keepdims=True)
            probs = np.divide(
                probs, row_sums,
                out=np.zeros_like(probs),
                where=row_sums != 0
            )

            return probs
        # def predict_fn(rows):
        #     return self._predict_raw(np.asarray(rows, dtype=np.float64))[0:1][0] if len(rows) == 1 else self._predict_raw(np.asarray(rows, dtype=np.float64))[0]
        # LIME uses the same ensemble probabilities as live inference.
        from lime.lime_tabular import LimeTabularExplainer
        lime_explainer = LimeTabularExplainer(
            training_data=sample_raw, feature_names=self.features, class_names=self.labels,
            mode="classification", discretize_continuous=True, random_state=7,
        )
        lime_exp = lime_explainer.explain_instance(
            target_raw[0], predict_fn, num_features=12, num_samples=500,
        )
        lime_items = [{"feature": name, "weight": float(weight)} for name, weight in lime_exp.as_list()]

        # SHAP GradientExplainer explains the loaded LSTM directly (rather than a separate surrogate).
        import shap
        background_scaled = self.scaler.transform(background_raw).astype(np.float32).reshape((-1, len(self.features), 1))
        target_scaled = self.scaler.transform(target_raw).astype(np.float32).reshape((1, len(self.features), 1))
        explainer = shap.GradientExplainer(self.lstm, background_scaled[:20])
        values = explainer.shap_values(target_scaled)
        predicted_class = int(np.argmax(self._predict_raw(target_raw)[0]))
        if isinstance(values, list):
            values = values[min(predicted_class, len(values) - 1)]
        values = np.asarray(values)
        # SHAP versions differ: some return one array per class, others put
        # the output/class axis at the end of a single ndarray.
        if values.ndim >= 2 and values.shape[-1] == len(self.labels):
            values = np.take(values, predicted_class, axis=-1)
        values = np.squeeze(values)
        if values.size != len(self.features):
            values = values.reshape((-1, len(self.features))).mean(axis=0)
        shap_items = sorted(
            [{"feature": name, "value": float(value), "importance": abs(float(value))} for name, value in zip(self.features, values)],
            key=lambda item: item["importance"], reverse=True,
        )[:15]
        return {"shap": shap_items, "lime": lime_items, "model": "LSTM GradientExplainer + LIME ensemble prediction", "explained_class": self.labels[predicted_class]}


engine = IDSModelEngine()
