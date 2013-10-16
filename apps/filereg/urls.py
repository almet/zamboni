from rest_framework.routers import DefaultRouter

from filereg.views import NonAMOAddonViewSet, HashViewSet


router = DefaultRouter()
router.register(r'addons', NonAMOAddonViewSet, base_name='nonamo-addon')
router.register(r'hashes', HashViewSet, base_name='nonamo-hash')
urlpatterns = router.urls
