import json
import tempfile
from datetime import timedelta
from pathlib import Path
from unittest import mock

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.core import clock
from apps.core.tests import factories as f


class DevClockTests(TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / ".dev_clock"
        self.path.write_text(json.dumps({"offset_seconds": 2 * 86400}))
        patcher = mock.patch.object(clock, "dev_clock_file", return_value=self.path)
        patcher.start()
        self.addCleanup(patcher.stop)
        clock._dev_cache.update(mtime=None, offset=timedelta(0))

    @override_settings(DEBUG=True)
    def test_shift_applies_in_debug(self):
        self.assertAlmostEqual((clock.now() - timezone.now()).total_seconds(), 2 * 86400, delta=5)

    @override_settings(DEBUG=False)
    def test_shift_ignored_outside_debug(self):
        self.assertLess(abs((clock.now() - timezone.now()).total_seconds()), 5)

    @override_settings(DEBUG=True)
    def test_frozen_wins_over_shift(self):
        at = f.at(2026, 11, 2, 12, 0)
        with clock.frozen(at):
            self.assertEqual(clock.now(), at)
