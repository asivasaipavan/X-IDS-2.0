from django.contrib import admin
from django.urls import path, include
from django.http import HttpResponseRedirect
from django.conf import settings
from django.conf.urls.static import static


def frontend_redirect(request):
    return HttpResponseRedirect("http://127.0.0.1:5173/")

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("xids_api.urls")),
    path("research/", include("ids_app.urls")),
    path("", frontend_redirect, name="frontend"),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
