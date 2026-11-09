import os

import numpy as np
from django.conf import settings
from django.contrib import messages
from django.shortcuts import redirect, render

from . import ml_utils as ml
from . import state as st


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------
def _available_datasets():
    files = []
    if os.path.isdir(settings.DATASET_DIR):
        for f in sorted(os.listdir(settings.DATASET_DIR)):
            if f.lower().endswith(".csv"):
                files.append(f)
    return files


# ---------------------------------------------------------------------------
# Home / overview page
# ---------------------------------------------------------------------------
def home_view(request):
    state = st.load_state(request)
    ctx = {
        "steps": state.get("steps", {}),
        "dataset_name": state.get("dataset_name"),
        "metrics": state.get("metrics", {}),
    }
    return render(request, "ids_app/home.html", ctx)


# ---------------------------------------------------------------------------
# 1. Upload Dataset
# ---------------------------------------------------------------------------
def upload_view(request):
    if request.method == "POST":
        uploaded = request.FILES.get("dataset_file")
        if uploaded:
            safe_name = "uploaded_" + uploaded.name.replace(" ", "_")
            path = os.path.join(settings.DATASET_DIR, safe_name)
            with open(path, "wb+") as dst:
                for chunk in uploaded.chunks():
                    dst.write(chunk)
            display_name = safe_name
        else:
            display_name = request.POST.get("dataset_choice", "CIC-IDS2017.csv")
            path = os.path.join(settings.DATASET_DIR, display_name)

        if not os.path.exists(path):
            messages.error(request, f"Dataset file not found: {display_name}")
            return redirect("upload")

        try:
            df = ml.load_dataset(path)
            chart_labels, chart_values = ml.label_distribution(df)
        except Exception as exc:
            messages.error(request, f"Could not read dataset: {exc}")
            return redirect("upload")

        # A fresh dataset invalidates every downstream step.
        st.clear_state(request)
        st.save_state(
            request,
            dataset_path=path,
            dataset_name=display_name,
            label_chart={"labels": chart_labels, "values": chart_values},
            unique_labels=sorted(chart_labels),
            steps={"upload": True},
            log=[],
        )
        st.append_log(request, f"Loaded dataset '{display_name}' -> {df.shape[0]} rows x {df.shape[1]} columns")
        st.append_log(
            request,
            f"Classes found: {', '.join(chart_labels)}  |  counts: {dict(zip(chart_labels, chart_values))}",
        )
        messages.success(request, f"Loaded '{display_name}' successfully.")
        return redirect("upload")

    state = st.load_state(request)
    label_chart = state.get("label_chart")
    ctx = {
        "datasets": _available_datasets(),
        "dataset_name": state.get("dataset_name"),
        "label_chart": label_chart,
        "label_chart_json": __import__("json").dumps(label_chart) if label_chart else "null",
    }
    return render(request, "ids_app/upload.html", ctx)


# ---------------------------------------------------------------------------
# 2. Preprocess Dataset
# ---------------------------------------------------------------------------
def preprocess_view(request):
    state = st.load_state(request)

    if request.method == "POST":
        if "dataset_path" not in state:
            messages.error(request, "Please upload a dataset first.")
            return redirect("upload")

        df = ml.load_dataset(state["dataset_path"])
        labels_sorted = sorted(df["Label"].astype(str).unique().tolist())
        X, Y, label_encoders, scaler, features, perturb = ml.preprocess_dataset(df)

        st.save_state(
            request,
            X=X,
            Y=Y,
            label_encoders=label_encoders,
            scaler=scaler,
            features=features,
            perturb=perturb,
            labels=labels_sorted,
            preprocess_info={
                "rows": int(X.shape[0]),
                "features": int(X.shape[1]),
                "encoders": len(label_encoders),
                "encoded_columns": [name for name, _ in label_encoders],
            },
        )
        ml.persist_preprocessing_artifacts(scaler, label_encoders, features, labels_sorted)

        st.mark_step(request, "preprocess")
        st.append_log(request, f"Preprocessing complete. Encoded {len(label_encoders)} categorical column(s) with LabelEncoder.")
        st.append_log(request, f"Dropped 'Label' & 'FlowDuration' from features -> {X.shape[1]} numeric features remain.")
        st.append_log(request, f"Feature matrix scaled with StandardScaler -> shape {X.shape}.")
        messages.success(request, "Preprocessing complete.")
        return redirect("preprocess")

    ctx = {
        "has_dataset": "dataset_path" in state,
        "dataset_name": state.get("dataset_name"),
        "info": state.get("preprocess_info"),
    }
    return render(request, "ids_app/preprocess.html", ctx)


# ---------------------------------------------------------------------------
# 3. Train / Test Split
# ---------------------------------------------------------------------------
def split_view(request):
    state = st.load_state(request)

    if request.method == "POST":
        if "X" not in state:
            messages.error(request, "Please preprocess the dataset first.")
            return redirect("preprocess")

        X_train, X_test, y_train, y_test = ml.split_data(state["X"], state["Y"], state["perturb"])
        st.save_state(
            request,
            X_train=X_train,
            X_test=X_test,
            y_train=y_train,
            y_test=y_test,
            split_info={
                "total": int(state["X"].shape[0]),
                "train": int(X_train.shape[0]),
                "test": int(X_test.shape[0]),
            },
        )
        st.mark_step(request, "split")
        st.append_log(request, f"Total records in dataset: {state['X'].shape[0]}")
        st.append_log(request, f"80% used for training: {X_train.shape[0]} records")
        st.append_log(request, f"20% used for testing: {X_test.shape[0]} records")
        messages.success(request, "Train/Test split complete.")
        return redirect("split")

    ctx = {
        "has_preprocessed": "X" in state,
        "info": state.get("split_info"),
    }
    return render(request, "ids_app/split.html", ctx)


# ---------------------------------------------------------------------------
# 4. Run LSTM Algorithm
# ---------------------------------------------------------------------------
def lstm_view(request):
    state = st.load_state(request)

    if request.method == "POST":
        if "X_train" not in state:
            messages.error(request, "Please complete the Train & Test Split step first.")
            return redirect("split")

        model, trained_now = ml.train_or_load_lstm(
            state["X_train"], state["y_train"], state["X_test"], state["y_test"]
        )
        predict = model.predict(state["X_test"], verbose=0)
        predict = np.argmax(predict, axis=1)
        y_test1 = np.argmax(state["y_test"], axis=1)
        result = ml.calculate_metrics("LSTM", y_test1, predict, state["labels"])

        st.set_metric(request, "LSTM", result)
        st.set_image(request, "lstm", result["image"])
        st.save_state(request, lstm_trained=True)
        st.mark_step(request, "lstm")

        tag = "Trained a new LSTM model and saved weights to model/lstm_weights.hdf5" \
            if trained_now else "Loaded cached weights from model/lstm_weights.hdf5"
        st.append_log(request, f"LSTM -> {tag}")
        st.append_log(
            request,
            "LSTM Accuracy: {accuracy}%  Precision: {precision}%  Recall: {recall}%  F1: {fscore}%".format(**result),
        )
        messages.success(request, "LSTM run complete.")
        return redirect("lstm")

    state_metrics = state.get("metrics", {})
    ctx = {
        "has_split": "X_train" in state,
        "metric": state_metrics.get("LSTM"),
        "image": state.get("images", {}).get("lstm"),
    }
    return render(request, "ids_app/lstm.html", ctx)


# ---------------------------------------------------------------------------
# 5. Run TCN Algorithm
# ---------------------------------------------------------------------------
def tcn_view(request):
    state = st.load_state(request)

    if request.method == "POST":
        if "X_train" not in state:
            messages.error(request, "Please complete the Train & Test Split step first.")
            return redirect("split")

        model, trained_now = ml.train_or_load_tcn(
            state["X_train"], state["y_train"], state["X_test"], state["y_test"]
        )
        predict = model.predict(state["X_test"], verbose=0)
        predict = np.argmax(predict, axis=1)
        y_test1 = np.argmax(state["y_test"], axis=1)
        result = ml.calculate_metrics("TCN", y_test1, predict, state["labels"])

        st.set_metric(request, "TCN", result)
        st.set_image(request, "tcn", result["image"])
        st.mark_step(request, "tcn")

        tag = "Trained a new TCN model and saved weights to model/tcn_weights.hdf5" \
            if trained_now else "Loaded cached weights from model/tcn_weights.hdf5"
        st.append_log(request, f"TCN -> {tag}")
        st.append_log(
            request,
            "TCN Accuracy: {accuracy}%  Precision: {precision}%  Recall: {recall}%  F1: {fscore}%".format(**result),
        )
        messages.success(request, "TCN run complete.")
        return redirect("tcn")

    state_metrics = state.get("metrics", {})
    ctx = {
        "has_split": "X_train" in state,
        "metric": state_metrics.get("TCN"),
        "image": state.get("images", {}).get("tcn"),
    }
    return render(request, "ids_app/tcn.html", ctx)


# ---------------------------------------------------------------------------
# 6. Comparison Graph
# ---------------------------------------------------------------------------
def compare_view(request):
    state = st.load_state(request)
    metrics = state.get("metrics", {})

    if request.method == "POST":
        if "LSTM" not in metrics or "TCN" not in metrics:
            messages.error(request, "Run both the LSTM and TCN algorithms first to compare them.")
            return redirect("compare")

        st.save_state(request, comparison=ml.comparison_chart_data(metrics))
        st.mark_step(request, "compare")
        st.append_log(request, "Generated LSTM vs TCN comparison graph (Accuracy / Precision / Recall / F1).")
        messages.success(request, "Comparison graph generated.")
        return redirect("compare")

    import json as _json
    comparison = state.get("comparison")
    ctx = {
        "ready": "LSTM" in metrics and "TCN" in metrics,
        "metrics": metrics,
        "comparison": comparison,
        "comparison_json": _json.dumps(comparison) if comparison else "null",
    }
    return render(request, "ids_app/compare.html", ctx)


# ---------------------------------------------------------------------------
# 7. Explainability (SHAP summary + violin)
# ---------------------------------------------------------------------------
def explain_view(request):
    state = st.load_state(request)
    ctx = {
        "has_split": "X_train" in state,
        "summary_image": state.get("images", {}).get("shap_summary"),
        "violin_image": state.get("images", {}).get("shap_violin"),
        "has_summary": bool(state.get("shap_values") is not None),
    }
    return render(request, "ids_app/explain.html", ctx)


def explain_summary_action(request):
    if request.method != "POST":
        return redirect("explain")
    state = st.load_state(request)
    if "X_train" not in state:
        messages.error(request, "Please complete the Train & Test Split step first.")
        return redirect("split")

    image, shap_values, _ = ml.explain_shap_summary(
        state["X_train"], state["X_test"], state["y_train"], state["features"]
    )
    st.save_state(request, shap_values=shap_values)
    st.set_image(request, "shap_summary", image)
    st.mark_step(request, "explain_summary")
    st.append_log(request, "Generated SHAP summary explanation (surrogate Random Forest + TreeExplainer).")
    messages.success(request, "SHAP summary explanation generated.")
    return redirect("explain")


def explain_violin_action(request):
    if request.method != "POST":
        return redirect("explain")
    state = st.load_state(request)
    if "shap_values" not in state:
        messages.error(request, "Please generate the Summary explanation first.")
        return redirect("explain")

    image = ml.explain_shap_violin(state["shap_values"], state["features"])
    st.set_image(request, "shap_violin", image)
    st.mark_step(request, "explain_violin")
    st.append_log(request, "Generated SHAP violin plot (spread of each feature's contribution).")
    messages.success(request, "SHAP violin explanation generated.")
    return redirect("explain")


# ---------------------------------------------------------------------------
# 8. Predict Attack from Test Data
# ---------------------------------------------------------------------------
def predict_view(request):
    state = st.load_state(request)

    if request.method == "POST":
        if "scaler" not in state:
            messages.error(request, "Please preprocess the dataset first.")
            return redirect("preprocess")
        if not state.get("lstm_trained"):
            messages.error(request, "Please run the LSTM algorithm first (it is used for prediction).")
            return redirect("lstm")

        uploaded = request.FILES.get("test_file")
        if uploaded:
            safe_name = "predict_" + uploaded.name.replace(" ", "_")
            path = os.path.join(settings.DATASET_DIR, safe_name)
            with open(path, "wb+") as dst:
                for chunk in uploaded.chunks():
                    dst.write(chunk)
            display_name = safe_name
        else:
            display_name = "testData.csv"
            path = os.path.join(settings.DATASET_DIR, display_name)

        if not os.path.exists(path):
            messages.error(request, f"Test file not found: {display_name}")
            return redirect("predict")

        model, _ = ml.train_or_load_lstm(
            state["X_train"], state["y_train"], state["X_test"], state["y_test"]
        )
        try:
            results = ml.predict_on_file(path, model, state["scaler"], state["label_encoders"], state["labels"])
        except Exception as exc:
            messages.error(request, f"Prediction failed: {exc}")
            return redirect("predict")

        st.save_state(request, predictions=results, predict_source=display_name)
        st.mark_step(request, "predict")
        st.append_log(request, f"Predicted {len(results)} record(s) from '{display_name}' using the trained LSTM model.")
        messages.success(request, f"Predicted {len(results)} record(s).")
        return redirect("predict")

    ctx = {
        "ready": state.get("lstm_trained", False),
        "predictions": state.get("predictions"),
        "predict_source": state.get("predict_source"),
    }
    return render(request, "ids_app/predict.html", ctx)


# ---------------------------------------------------------------------------
# Reset everything (start over, like restarting the Tkinter app)
# ---------------------------------------------------------------------------
def reset_view(request):
    st.clear_state(request)
    messages.success(request, "Session reset. Start again from Step 1 - Upload Dataset.")
    return redirect("home")
