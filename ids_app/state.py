"""
Per-session state store.

The original Tkinter app (ExplainableIDS.py) relied on module level global
variables (dataset, X, Y, X_train, X_test, scaler, label_encoder, features,
perturb, labels, lstm_model, tcn_model, shap_values, ...) that stayed alive
for the lifetime of the desktop process.

A Django web app can be hit by many users/tabs at once, so instead of
globals we pickle ALL of that state -- both "heavy" python objects (numpy
arrays, sklearn/keras objects, SHAP values) and "light" data (log lines,
which steps are completed, metric numbers, base64 chart images, prediction
rows) -- to one file per browser session under
`media/state/<session_key>.pkl`.

Only the bare Django session key itself travels in the browser cookie
(using Django's default, secure JSON session serializer, unmodified);
everything else stays on the server.
"""
import os
import pickle

from django.conf import settings


def _ensure_session(request):
    if not request.session.session_key:
        request.session.save()
    return request.session.session_key


def _path(session_key):
    return os.path.join(settings.STATE_DIR, f"{session_key}.pkl")


def load_state(request):
    session_key = _ensure_session(request)
    path = _path(session_key)
    if os.path.exists(path):
        try:
            with open(path, "rb") as f:
                return pickle.load(f)
        except Exception:
            return {}
    return {}


def save_state(request, **kwargs):
    session_key = _ensure_session(request)
    state = load_state(request)
    state.update(kwargs)
    with open(_path(session_key), "wb") as f:
        pickle.dump(state, f)
    return state


def clear_state(request):
    session_key = _ensure_session(request)
    path = _path(session_key)
    if os.path.exists(path):
        os.remove(path)


# ---------------------------------------------------------------------------
# convenience helpers used throughout views.py
# ---------------------------------------------------------------------------
def append_log(request, text):
    state = load_state(request)
    log = state.get("log", [])
    log.append(text)
    save_state(request, log=log[-300:])


def mark_step(request, name, done=True):
    state = load_state(request)
    steps = state.get("steps", {})
    steps[name] = done
    save_state(request, steps=steps)


def set_metric(request, algorithm, result):
    """Store a {'accuracy', 'precision', 'recall', 'fscore'} dict (no image) for one algorithm."""
    state = load_state(request)
    metrics = state.get("metrics", {})
    metrics[algorithm] = {k: v for k, v in result.items() if k != "image"}
    save_state(request, metrics=metrics)


def set_image(request, key, base64_png):
    state = load_state(request)
    images = state.get("images", {})
    images[key] = base64_png
    save_state(request, images=images)
