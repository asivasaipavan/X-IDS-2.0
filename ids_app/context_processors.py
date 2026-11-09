"""
Makes the pipeline navigation bar, dataset name, and console log available
to every template automatically, so each step page doesn't need to build
this boilerplate itself.
"""
from django.urls import reverse

from . import state as st

# (url_name, short label, step-flag key in state["steps"])
NAV_ITEMS = [
    ("upload", "Upload", "upload"),
    ("preprocess", "Preprocess", "preprocess"),
    ("split", "Split", "split"),
    ("lstm", "LSTM", "lstm"),
    ("tcn", "TCN", "tcn"),
    ("compare", "Compare", "compare"),
    ("explain", "Explain", "explain"),
    ("predict", "Predict", "predict"),
]


def pipeline(request):
    state = st.load_state(request)
    steps = state.get("steps", {})
    current = request.resolver_match.url_name if request.resolver_match else None

    nav_items = []
    for url_name, label, flag_key in NAV_ITEMS:
        if flag_key == "explain":
            done = bool(steps.get("explain_summary") or steps.get("explain_violin"))
        else:
            done = bool(steps.get(flag_key))
        nav_items.append(
            {
                "url": reverse(url_name),
                "label": label,
                "done": done,
                "active": current == url_name,
            }
        )

    return {
        "nav_items": nav_items,
        "pipeline_steps": steps,
        "pipeline_dataset_name": state.get("dataset_name"),
        "pipeline_log": state.get("log", []),
    }
