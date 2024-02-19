from __future__ import annotations

import pytest

from settings import Settings
from settings import settings
from settings import settings as settings2


@pytest.mark.unit
class TestSingleton:
    def test_singleton(self) -> None:
        """Verify that the singleton pattern is implemented correctly."""

        assert settings is not None
        assert isinstance(settings, Settings)
        assert settings.time_delta_hours == 1
        print(f"\nsettings ID : {id(settings)}")
        new_settings: Settings = Settings()
        assert id(settings) == id(settings2)
        # point to the same object (in memory), so the same object
        assert settings is settings2
        assert id(settings) != id(new_settings)
        assert settings is not new_settings
        print(f"\nnew settings ID : {id(new_settings)}")
