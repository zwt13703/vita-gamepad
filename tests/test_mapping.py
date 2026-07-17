from pathlib import Path
import tempfile
import unittest

from vitapad.mapping import MappingManager
from vitapad.protocol import Buttons, InputState


class MappingManagerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.path = Path(self.temporary.name) / "settings.json"
        self.mapping = MappingManager(self.path)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_default_mapping_preserves_input(self) -> None:
        state = InputState(
            sequence=3,
            buttons=Buttons.A | Buttons.LEFT,
            lx=12,
            ry=240,
            lt=128,
        )
        self.assertEqual(self.mapping.apply(state, now=0), state)

    def test_remaps_button_and_trigger(self) -> None:
        config = self.mapping.describe()
        config["bindings"]["a"]["target"] = "y"
        config["bindings"]["lt"]["target"] = "b"
        self.mapping.update(config)
        output = self.mapping.apply(
            InputState(buttons=Buttons.A, lt=255), now=0
        )
        self.assertEqual(output.buttons, Buttons.Y | Buttons.B)
        self.assertEqual(output.lt, 0)
        self.assertTrue(self.path.exists())

    def test_turbo_uses_requested_frequency(self) -> None:
        config = self.mapping.describe()
        config["bindings"]["a"].update(
            {"target": "a", "turbo": True, "frequency": 10}
        )
        self.mapping.update(config)
        held = InputState(buttons=Buttons.A)
        self.assertTrue(self.mapping.apply(held, now=0).buttons & Buttons.A)
        self.assertFalse(self.mapping.apply(held, now=0.06).buttons & Buttons.A)
        self.assertTrue(self.mapping.apply(held, now=0.11).buttons & Buttons.A)

    def test_rejects_invalid_frequency(self) -> None:
        config = self.mapping.describe()
        config["bindings"]["a"]["frequency"] = 31
        with self.assertRaises(ValueError):
            self.mapping.update(config)


if __name__ == "__main__":
    unittest.main()
