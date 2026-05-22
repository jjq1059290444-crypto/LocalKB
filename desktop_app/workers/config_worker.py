"""config_worker.py — QThread for testing API connectivity."""

from PySide6.QtCore import QThread, Signal


class ConfigWorker(QThread):
    """Test LLM API connectivity in a background thread.

    Emits translation key + args; the GUI layer translates.
    """

    ping_signal = Signal(bool, str, object)

    def __init__(self, api_base: str, api_key: str, model: str, parent=None):
        super().__init__(parent)
        self._api_base = api_base
        self._api_key = api_key
        self._model = model

    def run(self):
        try:
            from core.qa.openai_client import OpenAICompatibleClient
            client = OpenAICompatibleClient(
                api_base=self._api_base,
                api_key=self._api_key,
                model=self._model,
            )
            ok = client.ping()
            if ok:
                self.ping_signal.emit(
                    True, "config.connected", {"url": self._api_base}
                )
            else:
                self.ping_signal.emit(
                    False, "config.unexpected", {}
                )
        except Exception as e:
            self.ping_signal.emit(
                False, "config.error", {"detail": str(e)}
            )
