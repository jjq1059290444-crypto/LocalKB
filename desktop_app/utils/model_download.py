"""model_download.py — reusable model download dialog.

Used by both the first-launch wizard (main.py) and the settings page.
"""

from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar, QPushButton,
)
from PySide6.QtCore import Qt, QTimer, QEventLoop

from core.paths import MODELS_DIR


def model_is_complete(local_dir: Path) -> bool:
    """Check if a model directory has actual weight files (not just config.json)."""
    if not local_dir.exists():
        return False
    has_weights = any(local_dir.glob("*.safetensors")) or \
                  (local_dir / "pytorch_model.bin").exists()
    has_config = (local_dir / "config.json").exists()
    has_tokenizer = (local_dir / "tokenizer_config.json").exists()
    return has_config and has_weights and has_tokenizer


def hf_cache_is_complete(model_name: str) -> Path | None:
    """Check if model is fully cached in HuggingFace cache.

    Returns the snapshot directory path if complete, None otherwise.
    """
    try:
        from huggingface_hub import try_to_load_from_cache
    except ImportError:
        return None

    config = try_to_load_from_cache(repo_id=model_name, filename="config.json")
    tokenizer = try_to_load_from_cache(
        repo_id=model_name, filename="tokenizer_config.json"
    )

    model_file = try_to_load_from_cache(repo_id=model_name, filename="model.safetensors")
    if not model_file:
        model_file = try_to_load_from_cache(
            repo_id=model_name, filename="model-00001-of-00002.safetensors"
        )
    if not model_file:
        model_file = try_to_load_from_cache(repo_id=model_name, filename="pytorch_model.bin")

    if config and model_file and tokenizer:
        return Path(config).parent

    return None


def download_model_if_needed(model_name: str, parent=None) -> bool:
    """Check if model is cached; if not, show a progress dialog.

    Downloads from ModelScope (primary) with HuggingFace mirror fallback.
    Saves a copy to models/ for offline use.

    Args:
        model_name: HF model ID, e.g. "BAAI/bge-m3".
        parent: Parent widget for the dialog.

    Returns:
        True if model is ready, False if download failed or cancelled.
    """
    local_name = model_name.replace("/", "_")
    local_dir = MODELS_DIR / local_name

    # Already fully cached locally
    if model_is_complete(local_dir):
        return True

    from workers.model_download_worker import ModelDownloadWorker

    cache_path = hf_cache_is_complete(model_name)

    title_text = (
        f"Preparing {local_name} from cache..."
        if cache_path
        else f"Downloading {model_name}..."
    )

    # ── Build dialog ──
    dlg = QDialog(parent)
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
    progress.setMaximum(0)
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

    # ── Worker + event loop ──
    worker = ModelDownloadWorker(model_name, local_dir, cache_path=cache_path)
    loop = QEventLoop()
    success = False

    def _on_progress(current, total):
        if total > 0:
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

    def _on_done(_success, msg):
        nonlocal success
        success = _success
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

    return success
