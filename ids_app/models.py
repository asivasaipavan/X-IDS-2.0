# This app does not need database models.
#
# All the "state" that the original Tkinter app kept in global variables
# (dataset, X, Y, X_train, X_test, scaler, label encoders, trained models,
# SHAP values, ...) is kept per browser-session using the helper functions
# in ids_app/state.py, which pickle the heavy objects to
# media/state/<session_key>.pkl. Trained neural network weights are always
# persisted to the project-level `model/` folder (lstm_weights.hdf5,
# tcn_weights.hdf5), exactly like the original desktop app.
from django.db import models  # noqa: F401
