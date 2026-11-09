from django.urls import path

from . import views

urlpatterns = [
    path("", views.home_view, name="home"),
    path("upload/", views.upload_view, name="upload"),
    path("preprocess/", views.preprocess_view, name="preprocess"),
    path("split/", views.split_view, name="split"),
    path("lstm/", views.lstm_view, name="lstm"),
    path("tcn/", views.tcn_view, name="tcn"),
    path("compare/", views.compare_view, name="compare"),
    path("explain/", views.explain_view, name="explain"),
    path("explain/summary/", views.explain_summary_action, name="explain_summary_action"),
    path("explain/violin/", views.explain_violin_action, name="explain_violin_action"),
    path("predict/", views.predict_view, name="predict"),
    path("reset/", views.reset_view, name="reset"),
]
