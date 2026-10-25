"""FR-29 dish photos: checked, shrunk to 1200 px JPEG, shown on menus."""
import io
import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image
from rest_framework.test import APIClient

from apps.core import clock
from apps.core.exceptions import DomainError
from apps.core.tests import factories as f
from apps.menus import images, services
from apps.menus.models import Menu
from apps.menus.serializers import MenuSerializer

MEDIA = tempfile.mkdtemp()


def png(width: int, height: int) -> SimpleUploadedFile:
    out = io.BytesIO()
    Image.new("RGBA", (width, height), (200, 120, 40, 255)).save(out, "PNG")
    return SimpleUploadedFile("plat.png", out.getvalue(), content_type="image/png")


@override_settings(MEDIA_ROOT=MEDIA)
class DishPhotoTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(MEDIA, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.chef = f.user(role="chef")

    def test_big_photo_is_resized_to_jpeg(self):
        dish = services.create_dish(by=self.chef, name="Couscous", category="main", photo=png(3000, 2000))
        self.assertTrue(dish.photo.name.startswith("dishes/") and dish.photo.name.endswith(".jpg"))
        with Image.open(dish.photo.path) as stored:
            self.assertEqual((stored.format, max(stored.size)), ("JPEG", 1200))

    def test_not_an_image_is_refused(self):
        fake = SimpleUploadedFile("plat.png", b"not an image", content_type="image/png")
        with self.assertRaises(DomainError) as ctx:
            images.prepare_dish_photo(fake)
        self.assertEqual(ctx.exception.code, "photo_invalid")

    def test_over_5_mb_is_refused(self):
        big = SimpleUploadedFile("plat.jpg", b"0" * (images.MAX_UPLOAD_BYTES + 1), content_type="image/jpeg")
        with self.assertRaises(DomainError) as ctx:
            images.prepare_dish_photo(big)
        self.assertEqual(ctx.exception.code, "photo_too_large")

    def test_upload_through_the_api(self):
        client = APIClient()
        client.force_authenticate(self.chef)
        response = client.post("/api/v1/dishes/", {"name": "Ojja", "category": "main", "photo": png(800, 600)})
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.json()["photo"].startswith("/media/dishes/"))

    def test_menu_items_expose_the_photo_url(self):
        dish = services.create_dish(by=self.chef, name="Couscous", category="main", photo=png(400, 300))
        menu = f.menu(f.at(2026, 11, 2).date(), status=Menu.Status.DRAFT)
        with clock.frozen(f.at(2026, 10, 29, 10)):
            services.set_items(menu, [dish.pk], by=self.chef)
        item = MenuSerializer(menu).data["items"][0]
        self.assertEqual(item["photo_url"], f"/media/{dish.photo.name}")
