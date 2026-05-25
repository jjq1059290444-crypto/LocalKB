"""main.py — desktop app entry point."""

import os
import sys
from pathlib import Path


os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
os.environ.setdefault("OMP_NUM_THREADS", "4")
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

# Locate project root (supports PyInstaller)
if getattr(sys, 'frozen', False):
    PROJECT_ROOT = Path(sys.executable).parent
else:
    PROJECT_ROOT = Path(__file__).resolve().parent.parent

try:
    os.chdir(str(PROJECT_ROOT))
except OSError:
    pass
sys.path.insert(0, str(PROJECT_ROOT))


def main():
    import time as _time
    _t0 = _time.perf_counter()
    def _tick(label):
        elapsed = _time.perf_counter() - _t0
        print(f"[STARTUP {elapsed:7.3f}s] {label}", flush=True)
        return elapsed

    _tick("main() begin")

    from PySide6.QtWidgets import QApplication, QWizard
    from PySide6.QtCore import QTranslator
    _tick("import PySide6")

    from theme import apply_theme
    from main_window import MainWindow
    _tick("import main_window")

    from utils.i18n import I18nManager
    from utils.model_download import download_model_if_needed
    _tick("import i18n + model_download")

    from config.manager import ConfigManager
    from core.paths import CONFIG_FILE, VECTOR_DB_DIR, QA_HISTORY_FILE
    _tick("import config + paths")

    from config.presets import EMBED_MODELS, get_embed_model_path
    _tick("import presets")

    # ── QApplication ──
    app = QApplication(sys.argv)
    app.setApplicationName("LocalKB")
    app.setApplicationVersion("1.0.0")
    _tick("QApplication created")

    apply_theme(app)
    _tick("theme applied")

    # ── Load config ──
    config_mgr = ConfigManager(CONFIG_FILE)
    config = config_mgr.load()
    _tick("config loaded")

    # ── First-launch wizard ──
    if not config.get("setup_complete", False):
        _tick("first-launch wizard...")
        from pages.wizard_page import SetupWizard
        wizard = SetupWizard(config_mgr)
        if wizard.exec() != QWizard.Accepted:
            sys.exit(0)  # user cancelled
        # Reload config after wizard saves it
        config = config_mgr.load()

        # ── Download embed model if needed ──
        embed_key = config.get("embed_model", "bge-small-zh-v1.5")
        if embed_key != "text-embedding-3-small":  # cloud model, no download
            info = EMBED_MODELS.get(embed_key, {})
            model_name = info.get("name", "")
            if model_name:
                download_model_if_needed(model_name)

    # ── Init i18n ──
    locales_dir = Path(__file__).resolve().parent / "locales"
    lang = config.get("language", "zh")
    i18n = I18nManager(locales_dir, default_language=lang)
    _tick("i18n loaded")

    # Attempt Qt translator load for built-in button labels (QMessageBox etc.)
    try:
        translator = QTranslator()
        qt_translations_dir = (
            Path(sys.prefix) / "share" / "PySide6" / "translations"
        )
        if lang == "zh":
            for trans_file in ("qtbase_zh_CN.qm", "qt_zh_CN.qm"):
                trans_path = qt_translations_dir / trans_file
                if trans_path.exists():
                    translator.load(str(trans_path))
                    app.installTranslator(translator)
                    break
    except Exception:
        pass
    _tick("Qt translator")

    # ── Determine embed model params (needed by StartupWorker + MainWindow) ──
    embed_key = config.get("embed_model", "bge-small-zh-v1.5")
    embed_info = EMBED_MODELS.get(embed_key, EMBED_MODELS["bge-small-zh-v1.5"])
    embed_model_name = get_embed_model_path(embed_key)
    use_sparse = embed_info.get("sparse", False)
    matryoshka_dim = config.get("matryoshka_dim", 0)
    vector_size = min(matryoshka_dim, embed_info["dim"]) if matryoshka_dim else embed_info["dim"]
    _tick(f"embed model: {embed_key} (sparse={use_sparse})")

    # ── Create window immediately (no blocking init) ──
    window = MainWindow(
        qa_chain=None,
        vector_store=None,
        config_manager=config_mgr,
        i18n=i18n,
        embed_model_name=embed_model_name,
        use_sparse=use_sparse,
    )
    _tick("MainWindow created (qa_chain=None)")

    window.show()
    _tick("window.show() — visible!")

    # ── Start background init (Qdrant + QAChain) ──
    from workers.startup_worker import StartupWorker
    _tick("import startup_worker")

    startup = StartupWorker(
        config=config,
        vector_db_dir=VECTOR_DB_DIR,
        vector_size=vector_size,
        use_sparse=use_sparse,
        embed_model_name=embed_model_name,
        history_file=QA_HISTORY_FILE,
    )
    startup.status_signal.connect(window.set_status)
    startup.ready_signal.connect(window._on_startup_ready)
    startup.error_signal.connect(window._on_startup_error)
    startup.start()
    _tick("StartupWorker started")

    # ── Start model warmup IN PARALLEL with Qdrant init ──
    if embed_model_name:
        from workers.warmup_worker import WarmupWorker
        warmup = WarmupWorker(embed_model_name)
        warmup.ready.connect(window._on_warmup_ready)
        warmup.error.connect(window._on_warmup_error)
        warmup.start()
        _tick("WarmupWorker started (parallel)")

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
