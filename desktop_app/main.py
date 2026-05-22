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
    from PySide6.QtWidgets import QApplication, QWizard
    from PySide6.QtCore import QTranslator

    from theme import apply_theme
    from main_window import MainWindow
    from utils.i18n import I18nManager

    from config.manager import ConfigManager
    from core.paths import CONFIG_FILE, VECTOR_DB_DIR, CHROMA_DIR, \
        CHROMA_COLLECTION, QA_HISTORY_FILE
    from core.qa.openai_client import OpenAICompatibleClient
    from core.retrieval.vector_store import VectorStore
    from core.retrieval.hybrid import HybridRetriever
    from core.qa.chain import QAChain
    from config.presets import EMBED_MODELS, get_embed_model_path

    app = QApplication(sys.argv)
    app.setApplicationName("LocalKB")
    app.setApplicationVersion("1.0.0")

    apply_theme(app)

    # ── Load config ──
    config_mgr = ConfigManager(CONFIG_FILE)
    config = config_mgr.load()

    # ── First-launch wizard ──
    if not config.get("setup_complete", False):
        from pages.wizard_page import SetupWizard
        wizard = SetupWizard(config_mgr)
        if wizard.exec() != QWizard.Accepted:
            sys.exit(0)  # user cancelled
        # Reload config after wizard saves it
        config = config_mgr.load()

        # ── Download embed model if needed ──
        embed_key = config.get("embed_model", "bge-small-zh-v1.5")
        if embed_key != "text-embedding-3-small":  # cloud model, no download
            from config.presets import EMBED_MODELS, get_embed_model_path
            info = EMBED_MODELS.get(embed_key, {})
            model_name = info.get("name", "")
            if model_name:
                _download_model_if_needed(model_name)

    # ── Init i18n ──
    locales_dir = Path(__file__).resolve().parent / "locales"
    lang = config.get("language", "zh")
    i18n = I18nManager(locales_dir, default_language=lang)

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

    # ── Determine embed model ──
    embed_key = config.get("embed_model", "bge-small-zh-v1.5")
    embed_info = EMBED_MODELS.get(embed_key, EMBED_MODELS["bge-small-zh-v1.5"])
    embed_model_name = get_embed_model_path(embed_key)
    use_sparse = embed_info.get("sparse", False)
    matryoshka_dim = config.get("matryoshka_dim", 0)
    vector_size = min(matryoshka_dim, embed_info["dim"]) if matryoshka_dim else embed_info["dim"]

    # ── Init Vector Store (Qdrant Embedded) ──
    vector_store = VectorStore(
        VECTOR_DB_DIR,
        collection_name="local_kb",
        vector_size=vector_size,
        use_sparse=use_sparse,
    )

    # ── Optional: run ChromaDB → Qdrant migration ──
    from core.retrieval.migration import needs_migration, run_migration
    if needs_migration(VECTOR_DB_DIR):
        print("Migrating ChromaDB → Qdrant...", flush=True)
        try:
            migrated = run_migration(
                CHROMA_DIR,
                vector_store,
                embed_fn=None,  # embedder called internally
                embed_model_name=embed_model_name,
                use_sparse=use_sparse,
            )
            print(f"Migration complete: {migrated} chunks", flush=True)
        except Exception as e:
            print(f"Migration error (non-fatal): {e}", flush=True)

    # ── Init QA Chain (lazy — embedding model loaded on first search) ──
    qa_chain = None
    error_msg = ""

    try:
        api_key = config.get("api_key", "")
        api_base = config.get("api_base", "https://api.deepseek.com")
        model = config.get("model", "deepseek-chat")
        system_prompt = config.get("system_prompt", "")
        temperature = config.get("temperature", 0.3)
        top_k = config.get("top_k", 10)

        llm = OpenAICompatibleClient(
            api_base=api_base,
            api_key=api_key,
            model=model,
            temperature=temperature,
        )

        retriever = HybridRetriever(
            vector_store=vector_store,
            use_reranker=config.get("use_reranker", False),
            reranker_model=config.get("reranker_model", "BAAI/bge-reranker-v2-m3"),
        )
        retriever.embed_model_name = embed_model_name

        qa_chain = QAChain(
            retriever=retriever,
            llm=llm,
            system_prompt=system_prompt,
            top_k=top_k,
            history_file=QA_HISTORY_FILE,
            use_hyde=config.get("hyde_enabled", False),
        )
    except Exception as e:
        error_msg = str(e)
        print(f"QA chain init error: {error_msg}", flush=True)

    # ── Show window ──
    window = MainWindow(
        qa_chain=qa_chain,
        vector_store=vector_store,
        config_manager=config_mgr,
        i18n=i18n,
        embed_model_name=embed_model_name,
        use_sparse=use_sparse,
    )

    if qa_chain:
        window.set_status(
            i18n.t("status.ready_with_model",
                   model=config.get("model", "deepseek-chat"),
                   api_base=config.get("api_base", ""))
        )
    elif error_msg:
        window.set_status(i18n.t("status.init_error", error=error_msg))
    else:
        window.set_status(i18n.t("status.not_configured"))

    window.show()
    sys.exit(app.exec())


def _model_is_complete(local_dir: Path) -> bool:
    """Check if a model directory has actual weight files (not just config.json)."""
    if not local_dir.exists():
        return False
    # Sentence-transformers models have .safetensors or pytorch_model.bin weights
    has_weights = any(local_dir.glob("*.safetensors")) or \
                  (local_dir / "pytorch_model.bin").exists()
    has_config = (local_dir / "config.json").exists()
    has_tokenizer = (local_dir / "tokenizer_config.json").exists()
    return has_config and has_weights and has_tokenizer


def _hf_cache_is_complete(model_name: str) -> Path | None:
    """Check if model is fully cached in HuggingFace cache.

    Returns the snapshot directory path if complete, None otherwise.
    This prevents the progress dialog from flashing by when
    snapshot_download would return instantly (all files cached).
    """
    try:
        from huggingface_hub import try_to_load_from_cache
    except ImportError:
        return None

    # Check for key files that indicate a complete model download
    config = try_to_load_from_cache(repo_id=model_name, filename="config.json")
    tokenizer = try_to_load_from_cache(repo_id=model_name, filename="tokenizer_config.json")

    # Check for weights — may be single file or sharded
    model_file = try_to_load_from_cache(repo_id=model_name, filename="model.safetensors")
    if not model_file:
        model_file = try_to_load_from_cache(
            repo_id=model_name, filename="model-00001-of-00002.safetensors"
        )
    if not model_file:
        model_file = try_to_load_from_cache(repo_id=model_name, filename="pytorch_model.bin")

    if config and model_file and tokenizer:
        return Path(config).parent  # snapshot directory

    return None


def _download_model_if_needed(model_name: str):
    """Check if model is cached; if not, show a progress dialog while downloading.

    Downloads from HuggingFace Hub; saves a copy to models/ for offline use.

    The dialog stays visible until download completes (auto-close after 3 s on
    success) or until the user dismisses it on error.
    """
    from PySide6.QtWidgets import (QDialog, QVBoxLayout, QProgressBar,
                                    QLabel, QPushButton, QHBoxLayout)
    from PySide6.QtCore import QEventLoop, QTimer, Qt

    local_name = model_name.replace("/", "_")
    local_dir = PROJECT_ROOT / "models" / local_name

    # Already fully cached locally — nothing to do
    if _model_is_complete(local_dir):
        return

    from workers.model_download_worker import ModelDownloadWorker

    cache_path = _hf_cache_is_complete(model_name)

    title_text = (
        f"Preparing {local_name} from cache..."
        if cache_path
        else f"Downloading {model_name}..."
    )

    # ── Build custom dialog ──
    dlg = QDialog()
    dlg.setWindowTitle("Model Setup")
    dlg.setMinimumWidth(500)
    dlg.setWindowFlags(dlg.windowFlags() & ~Qt.WindowContextHelpButtonHint)
    dlg.setModal(True)

    layout = QVBoxLayout(dlg)
    layout.setSpacing(12)
    layout.setContentsMargins(20, 16, 20, 16)

    title_label = QLabel(title_text)
    title_label.setWordWrap(True)
    title_label.setStyleSheet("font-size: 13px; font-weight: bold;")
    layout.addWidget(title_label)

    progress = QProgressBar()
    progress.setMinimum(0)
    progress.setMaximum(0)  # indeterminate until total is known
    progress.setTextVisible(True)
    layout.addWidget(progress)

    detail_label = QLabel("")
    detail_label.setWordWrap(True)
    detail_label.setMinimumHeight(36)
    detail_label.setStyleSheet("font-size: 11px; color: #636E72;")
    layout.addWidget(detail_label)

    button_layout = QHBoxLayout()
    button_layout.addStretch()
    close_btn = QPushButton("Close")
    close_btn.setVisible(False)
    close_btn.setMinimumWidth(80)
    button_layout.addWidget(close_btn)
    layout.addLayout(button_layout)

    dlg.show()

    # ── Worker ──
    worker = ModelDownloadWorker(model_name, local_dir, cache_path=cache_path)
    loop = QEventLoop()

    def _on_progress(current, total):
        if total > 0:
            # Convert to MB — QProgressBar uses 32-bit int internally
            cur_mb = int(current) // (1024 * 1024)
            tot_mb = int(total) // (1024 * 1024)
            progress.setMaximum(tot_mb)
            progress.setValue(cur_mb)
            detail_label.setText(
                f"{int(current) / (1024**2):.0f} MB"
                + (f" / {int(total) / (1024**2):.0f} MB" if total > 0 else "")
            )

    def _on_status(msg: str):
        detail_label.setText(msg.replace("\n", " "))

    def _on_done(success, msg):
        progress.setMaximum(100)
        progress.setValue(100)
        title_label.setText("Model Ready")
        title_label.setStyleSheet(
            "font-size: 13px; font-weight: bold; color: #27AE60;")
        detail_label.setText(msg)
        QTimer.singleShot(3000, lambda: (dlg.accept(), loop.quit()))

    def _on_error(msg: str):
        progress.setMaximum(100)
        progress.setValue(0)
        title_label.setText("Download Failed")
        title_label.setStyleSheet(
            "font-size: 13px; font-weight: bold; color: #E74C3C;")
        detail_label.setText(msg)
        detail_label.setStyleSheet("font-size: 11px; color: #E74C3C;")
        close_btn.setVisible(True)
        close_btn.clicked.connect(lambda: (dlg.reject(), loop.quit()))

    worker.progress_signal.connect(_on_progress)
    worker.status_signal.connect(_on_status)
    worker.finished_signal.connect(_on_done)
    worker.error_signal.connect(_on_error)
    worker.start()
    loop.exec()


if __name__ == "__main__":
    main()
