"""
Machine-learning pipeline for the XAI-IDS project.

This module is a direct, function-based port of the logic that used to
live inside `ExplainableIDS.py` (the original Tkinter desktop app):

    upload()        -> load_dataset() / label_distribution()
    preprocess()     -> preprocess_dataset()
    trainTestSplit() -> split_data()
    runLSTM()         -> train_or_load_lstm() + calculate_metrics()
    runTCN()          -> train_or_load_tcn()  + calculate_metrics()
    graph()           -> comparison_chart_data()
    predict()          -> predict_on_file()
    explanation()      -> explain_shap_summary()
    Violinexplanation()-> explain_shap_violin()

Same dataset (CIC-IDS2017.csv), same two algorithms (LSTM & TCN) and the
same SHAP based explainability. Matplotlib figures are rendered to
base64 PNGs instead of opening desktop pop-up windows, so they can be
embedded directly in the web page.
"""
import base64
import io
import os
import pickle

import matplotlib

matplotlib.use("Agg")  # headless rendering for the web server
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_curve,
)
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler

from tensorflow.keras.callbacks import ModelCheckpoint
from tensorflow.keras.layers import Dense, Dropout, LSTM
from tensorflow.keras.models import Sequential
from tensorflow.keras.utils import to_categorical

from tcn import compiled_tcn
import shap

from django.conf import settings

MODEL_DIR = settings.MODEL_DIR
DATASET_DIR = settings.DATASET_DIR

# Light, "colourful" plotting theme so the generated charts match the
# white paper-notebook page: white/near-white panels, dark ink text,
# saturated accent colours for the data itself.
PLOT_BG = "#ffffff"
PLOT_INK = "#171a2b"
PLOT_GRID = "#e0e4f0"
plt.rcParams["figure.facecolor"] = PLOT_BG
plt.rcParams["axes.facecolor"] = PLOT_BG
plt.rcParams["savefig.facecolor"] = PLOT_BG
CHART_PALETTE = ["#00b8d9", "#e0389a", "#d99a1b", "#7c4dff", "#0a9b6f"]


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def fig_to_base64(fig=None):
    """Render a matplotlib figure to a base64 PNG string and close it."""
    if fig is None:
        fig = plt.gcf()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", facecolor=fig.get_facecolor())
    buf.seek(0)
    encoded = base64.b64encode(buf.read()).decode("utf-8")
    plt.close(fig)
    return encoded


# ---------------------------------------------------------------------------
# upload()
# ---------------------------------------------------------------------------
def load_dataset(path):
    return pd.read_csv(path)


def label_distribution(df):
    counts = df.groupby("Label").size()
    labels = [str(x) for x in counts.index.tolist()]
    values = [int(v) for v in counts.values.tolist()]
    return labels, values


# ---------------------------------------------------------------------------
# preprocess()
# ---------------------------------------------------------------------------
def preprocess_dataset(df):
    df = df.copy()
    label_encoders = []
    columns = df.columns
    types = df.dtypes.values
    for j in range(len(types)):
        if types[j] == "object":
            le = LabelEncoder()
            df[columns[j]] = pd.Series(le.fit_transform(df[columns[j]].astype(str)))
            label_encoders.append((columns[j], le))

    df.fillna(0, inplace=True)
    df = df[np.isfinite(df).all(1)]

    perturb = df["FlowDuration"].to_numpy().ravel()
    Y = df["Label"].to_numpy().ravel()
    df = df.drop(["Label", "FlowDuration"], axis=1)
    features = list(df.columns)

    X = df.values.astype(np.float64)
    scaler = StandardScaler()
    X = scaler.fit_transform(X)
    Y_cat = to_categorical(Y)

    return X, Y_cat, label_encoders, scaler, features, perturb


# ---------------------------------------------------------------------------
# trainTestSplit()
# ---------------------------------------------------------------------------
def split_data(X, Y, perturb, test_size=0.2, random_state=42):
    X = np.reshape(X, (X.shape[0], X.shape[1], 1))
    X_train, X_test, y_train, y_test = train_test_split(
        X, Y, test_size=test_size, random_state=random_state
    )
    n = min(10, X_test.shape[0])
    for i in range(n):
        X_test[i, 0] = perturb[i]
    return X_train, X_test, y_train, y_test


# ---------------------------------------------------------------------------
# runLSTM()
# ---------------------------------------------------------------------------
def build_lstm(input_shape, num_classes):
    model = Sequential()
    model.add(LSTM(32, input_shape=input_shape))
    model.add(Dropout(0.3))
    model.add(Dense(32, activation="relu"))
    model.add(Dense(num_classes, activation="softmax"))
    model.compile(loss="categorical_crossentropy", optimizer="adam", metrics=["accuracy"])
    return model


def train_or_load_lstm(X_train, y_train, X_test, y_test, epochs=20):
    weights_path = os.path.join(MODEL_DIR, "lstm_weights.hdf5")
    history_path = os.path.join(MODEL_DIR, "lstm_history.pckl")
    model = build_lstm((X_train.shape[1], X_train.shape[2]), y_train.shape[1])
    trained_now = False
    if not os.path.exists(weights_path):
        checkpoint = ModelCheckpoint(
            filepath=weights_path, verbose=0, save_best_only=True, save_weights_only=True
        )
        hist = model.fit(
            X_train,
            y_train,
            batch_size=32,
            epochs=epochs,
            validation_data=(X_test, y_test),
            callbacks=[checkpoint],
            verbose=0,
        )
        with open(history_path, "wb") as f:
            pickle.dump(hist.history, f)
        trained_now = True
        # ModelCheckpoint already saved the *best* weights, reload them so
        # the in-memory model matches exactly what's stored on disk.
        model.load_weights(weights_path)
    else:
        model.load_weights(weights_path)
    return model, trained_now


# ---------------------------------------------------------------------------
# runTCN()
# ---------------------------------------------------------------------------
def build_tcn(train_len):
    return compiled_tcn(
        return_sequences=False,
        num_feat=1,
        num_classes=2,
        nb_filters=20,
        kernel_size=6,
        dilations=[2 ** i for i in range(9)],
        nb_stacks=1,
        max_len=train_len,
        use_skip_connections=True,
    )


def train_or_load_tcn(X_train, y_train, X_test, y_test, epochs=20):
    weights_path = os.path.join(MODEL_DIR, "tcn_weights.hdf5")
    history_path = os.path.join(MODEL_DIR, "tcn_history.pckl")
    model = build_tcn(X_train[0:1].shape[1])
    trained_now = False
    if not os.path.exists(weights_path):
        checkpoint = ModelCheckpoint(
            filepath=weights_path, verbose=0, save_best_only=True, save_weights_only=True
        )
        hist = model.fit(
            X_train,
            y_train.squeeze().argmax(axis=1),
            epochs=epochs,
            validation_data=(X_test, y_test.squeeze().argmax(axis=1)),
            callbacks=[checkpoint],
            verbose=0,
        )
        with open(history_path, "wb") as f:
            pickle.dump(hist.history, f)
        trained_now = True
        model.load_weights(weights_path)
    else:
        model.load_weights(weights_path)
    return model, trained_now


# ---------------------------------------------------------------------------
# calculateMetrics()
# ---------------------------------------------------------------------------
def calculate_metrics(algorithm, y_true, y_pred, labels):
    p = precision_score(y_true, y_pred, average="macro", zero_division=0) * 100
    r = recall_score(y_true, y_pred, average="macro", zero_division=0) * 100
    f = f1_score(y_true, y_pred, average="macro", zero_division=0) * 100
    a = accuracy_score(y_true, y_pred) * 100

    fig, axs = plt.subplots(1, 2, figsize=(11, 4.3))
    fig.patch.set_facecolor(PLOT_BG)

    cm = confusion_matrix(y_true, y_pred)
    sns.heatmap(
        cm,
        xticklabels=labels,
        yticklabels=labels,
        annot=True,
        cmap="PuBuGn",
        fmt="g",
        ax=axs[0],
        cbar=False,
        linewidths=1,
        linecolor=PLOT_BG,
        annot_kws={"color": PLOT_INK, "fontweight": "bold"},
    )
    axs[0].set_title(f"{algorithm} Confusion Matrix", color=PLOT_INK, fontweight="bold")
    axs[0].tick_params(colors=PLOT_INK)
    axs[0].set_facecolor(PLOT_BG)

    random_probs = [0 for _ in range(len(y_true))]
    p_fpr, p_tpr, _ = roc_curve(y_true, random_probs, pos_label=1)
    axs[1].plot(p_fpr, p_tpr, linestyle="--", color="#d99a1b", label="Baseline")
    ns_fpr, ns_tpr, _ = roc_curve(y_true, y_pred, pos_label=1)
    axs[1].plot(ns_fpr, ns_tpr, linestyle="-", color="#00b8d9", linewidth=2.4, label="Predicted")
    axs[1].set_title(f"{algorithm} ROC Curve", color=PLOT_INK, fontweight="bold")
    axs[1].set_xlabel("False Positive Rate", color=PLOT_INK)
    axs[1].set_ylabel("True Positive Rate", color=PLOT_INK)
    axs[1].tick_params(colors=PLOT_INK)
    axs[1].set_facecolor(PLOT_BG)
    axs[1].grid(color=PLOT_GRID, linewidth=0.8)
    legend = axs[1].legend(facecolor=PLOT_BG, edgecolor=PLOT_GRID)
    for text in legend.get_texts():
        text.set_color(PLOT_INK)
    for spine in list(axs[0].spines.values()) + list(axs[1].spines.values()):
        spine.set_color(PLOT_GRID)

    fig.tight_layout()
    image = fig_to_base64(fig)

    return {
        "accuracy": round(float(a), 2),
        "precision": round(float(p), 2),
        "recall": round(float(r), 2),
        "fscore": round(float(f), 2),
        "image": image,
    }


# ---------------------------------------------------------------------------
# predict()
# ---------------------------------------------------------------------------
def predict_on_file(path, model, scaler, label_encoders, labels):
    testdata = pd.read_csv(path)
    original = testdata.copy()

    # Same as the original app: apply every stored LabelEncoder EXCEPT the
    # last one, because the last encoder that was fitted during
    # preprocess_dataset() belongs to the target 'Label' column, which is
    # not present in a file to be predicted on.
    encoders_to_apply = label_encoders[:-1] if len(label_encoders) > 0 else []
    for name, le in encoders_to_apply:
        if name in testdata.columns:
            testdata[name] = pd.Series(le.transform(testdata[name].astype(str)))

    testdata.fillna(0, inplace=True)
    testdata = testdata[np.isfinite(testdata).all(1)]
    if "FlowDuration" in testdata.columns:
        testdata = testdata.drop(["FlowDuration"], axis=1)

    X = scaler.transform(testdata.values.astype(np.float64))
    X = np.reshape(X, (X.shape[0], X.shape[1], 1))
    predictions = model.predict(X, verbose=0)
    predictions = np.argmax(predictions, axis=1)

    results = []
    preview_cols = list(original.columns[:8])
    for i in range(len(predictions)):
        row_preview = {c: original.iloc[i][c] for c in preview_cols}
        results.append(
            {
                "index": i + 1,
                "row": row_preview,
                "prediction": str(labels[predictions[i]]),
            }
        )
    return results


# ---------------------------------------------------------------------------
# explanation() / Violinexplanation()
# ---------------------------------------------------------------------------
def explain_shap_summary(X_train, X_test, y_train, features, max_samples=200):
    X_train_2d = X_train.reshape(X_train.shape[0], -1)
    X_test_2d = X_test.reshape(X_test.shape[0], -1)
    if X_test_2d.shape[0] > max_samples:
        X_test_2d = X_test_2d[:max_samples]
    y_train_1d = np.argmax(y_train, axis=1)

    rf = RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1)
    rf.fit(X_train_2d, y_train_1d)

    explainer = shap.TreeExplainer(rf)
    shap_values = explainer.shap_values(X_test_2d, check_additivity=False)

    sv = _first_class_shap(shap_values)

    fig = plt.figure(figsize=(9, 7.5))
    shap.summary_plot(sv, X_test_2d, feature_names=features, show=False, plot_size=None)
    fig = plt.gcf()
    fig.patch.set_facecolor(PLOT_BG)
    for ax in fig.axes:
        ax.set_facecolor(PLOT_BG)
        ax.tick_params(colors=PLOT_INK)
        ax.title.set_color(PLOT_INK)
        ax.xaxis.label.set_color(PLOT_INK)
        ax.yaxis.label.set_color(PLOT_INK)
        for spine in ax.spines.values():
            spine.set_color(PLOT_GRID)
    image = fig_to_base64(fig)
    return image, shap_values, X_test_2d


def _first_class_shap(shap_values):
    """Normalise SHAP output across shap versions to a 2D (samples, features) array."""
    if isinstance(shap_values, list):
        return shap_values[0]
    if isinstance(shap_values, np.ndarray) and shap_values.ndim == 3:
        return shap_values[:, :, 0]
    return shap_values


def explain_shap_violin(shap_values, features):
    sv = _first_class_shap(shap_values)
    fig = plt.figure(figsize=(9, 7.5))
    try:
        shap.plots.violin(sv, feature_names=features, show=False)
    except Exception:
        # Older/newer shap APIs expose the violin plot differently.
        shap.summary_plot(sv, feature_names=features, plot_type="violin", show=False)
    fig = plt.gcf()
    fig.patch.set_facecolor(PLOT_BG)
    for ax in fig.axes:
        ax.set_facecolor(PLOT_BG)
        ax.tick_params(colors=PLOT_INK)
        ax.title.set_color(PLOT_INK)
        ax.xaxis.label.set_color(PLOT_INK)
        ax.yaxis.label.set_color(PLOT_INK)
        for spine in ax.spines.values():
            spine.set_color(PLOT_GRID)
    image = fig_to_base64(fig)
    return image


# ---------------------------------------------------------------------------
# graph()
# ---------------------------------------------------------------------------
def comparison_chart_data(metrics):
    """metrics: {"LSTM": {...}, "TCN": {...}} -> chart.js friendly structure."""
    algorithms = list(metrics.keys())
    series = {
        "Accuracy": [metrics[a]["accuracy"] for a in algorithms],
        "Precision": [metrics[a]["precision"] for a in algorithms],
        "Recall": [metrics[a]["recall"] for a in algorithms],
        "F1 Score": [metrics[a]["fscore"] for a in algorithms],
    }
    return {"labels": algorithms, "series": series}


def persist_preprocessing_artifacts(scaler, label_encoders, features, labels):
    """Store the fitted scaler/encoders/features/labels into the model/ folder
    so they can be reused for prediction without re-running preprocessing,
    exactly like the LSTM/TCN weight files are reused by the original app."""
    with open(os.path.join(MODEL_DIR, "scaler.pkl"), "wb") as f:
        pickle.dump(scaler, f)
    with open(os.path.join(MODEL_DIR, "label_encoders.pkl"), "wb") as f:
        pickle.dump(label_encoders, f)
    with open(os.path.join(MODEL_DIR, "features.pkl"), "wb") as f:
        pickle.dump(features, f)
    with open(os.path.join(MODEL_DIR, "labels.pkl"), "wb") as f:
        pickle.dump(labels, f)
