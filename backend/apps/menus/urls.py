from rest_framework.routers import SimpleRouter

from .views import DishViewSet, MenuViewSet

router = SimpleRouter()
router.register("dishes", DishViewSet, basename="dishes")
router.register("menus", MenuViewSet, basename="menus")

urlpatterns = router.urls
