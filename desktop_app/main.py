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
    from utils.model_download import download_model_if_needed

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
                download_model_if_needed(model_name)

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
    vector_store = None
    try:
        vector_store = VectorStore(
            VECTOR_DB_DIR,
            collection_name="local_kb",
            vector_size=vector_size,
            use_sparse=use_sparse,
        )
    except Exception as e:
        from PySide6.QtWidgets import QMessageBox
        msg = str(e)
        if "already accessed" in msg or "AlreadyLocked" in msg or "Permission denied" in msg:
            QMessageBox.critical(
                None,
                i18n.t("status.vector_db_locked_title"),
                i18n.t("status.vector_db_locked_msg", path=str(VECTOR_DB_DIR)),
            )
        else:
            QMessageBox.critical(
                None,
                i18n.t("status.init_error_title"),
                i18n.t("status.init_error", error=msg),
            )
        sys.exit(1)

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


if __name__ == "__main__":
    main()
