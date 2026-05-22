"""model_download_worker.py — QThread for downloading/preparing embedding models."""

import os
from pathlib import Path
import shutil

from PySide6.QtCore import QThread, Signal


class ModelDownloadWorker(QThread):
    """Download or prepare an embedding model with progress reporting.

    Two modes:
      - cache_path given: model already in HF cache → copy to local_dir
        with per-file byte progress (much faster than re-downloading)
      - cache_path None: full download via snapshot_download (console tqdm),
        then copy to local_dir with byte progress

    After copy/download, loads the model once to verify integrity.
    """

    progress_signal = Signal(object, object)  # (current, total) — use object to avoid 32-bit int overflow for large models
    status_signal = Signal(str)           # human-readable status
    finished_signal = Signal(bool, str)   # (success, message)
    error_signal = Signal(str)

    def __init__(self, model_name: str, local_dir: Path = None,
                 cache_path: Path = None, parent=None):
        super().__init__(parent)
        self._model_name = model_name
        self._local_dir = local_dir
        self._cache_path = cache_path

    def run(self):
        try:
            if self._cache_path:
                # ── Cache-hit path: copy from HF cache to models/ ──
                self._prepare_from_cache()
            else:
                # ── Cache-miss path: full download ──
                self._download_full()

            # Verify model loads correctly — use local path if available
            self.status_signal.emit("Verifying model integrity...")
            from sentence_transformers import SentenceTransformer
            verify_path = str(self._local_dir) if self._local_dir and self._local_dir.exists() else self._model_name
            SentenceTransformer(verify_path)

            self.finished_signal.emit(True, "Model ready — restart to apply")

        except Exception as e:
            self.error_signal.emit(str(e))

    def _prepare_from_cache(self):
        """Copy model from HF cache to local models/ dir with file progress."""
        if self._local_dir and self._local_dir.exists():
            self.status_signal.emit("Model already saved locally")
            return

        self.status_signal.emit("Found in cache — copying to local storage...")

        # Calculate total size for progress tracking
        total_bytes = _dir_size(self._cache_path)
        copied_bytes = 0

        self._local_dir.mkdir(parents=True, exist_ok=True)
        self.progress_signal.emit(0, total_bytes)

        for item in sorted(self._cache_path.iterdir()):
            if item.name == ".cache":
                continue
            dst = self._local_dir / item.name

            if item.is_symlink():
                real = item.resolve()
                if real.is_file():
                    shutil.copy2(real, dst)
                    copied_bytes += dst.stat().st_size
                elif real.is_dir():
                    copied_bytes += _copy_tree(real, dst)
            elif item.is_file():
                shutil.copy2(item, dst)
                copied_bytes += dst.stat().st_size
            elif item.is_dir():
                copied_bytes += _copy_tree(item, dst)

            self.progress_signal.emit(copied_bytes, total_bytes)

    def _download_full(self):
        """Download model — ModelScope first, then HF mirror as fallback.

        Progress is shown during the copy-to-local phase; the download
        itself uses tqdm on stderr.
        """
        errors: list[str] = []

        # 1) Try ModelScope (fast for mainland China, optional dependency)
        downloaded_path, ms_err = self._try_modelscope_download()
        if downloaded_path is not None:
            source = "ModelScope"
        else:
            if ms_err:
                errors.append(f"ModelScope: {ms_err}")
            # 2) Fall back to HuggingFace (with HF_ENDPOINT mirror set at startup)
            downloaded_path, hf_err = self._try_hf_download()
            if downloaded_path is not None:
                source = "HuggingFace"
            else:
                if hf_err:
                    errors.append(f"HuggingFace: {hf_err}")
                raise RuntimeError(
                    f"Failed to download {self._model_name}.\n"
                    + "\n".join(errors)
                )

        # Copy to local models/ dir for offline use with progress
        if self._local_dir:
            # Remove any stale partial copy so the directory isn't incomplete
            if self._local_dir.exists():
                shutil.rmtree(self._local_dir)
            self.status_signal.emit(
                f"Copying from {source} cache to local storage..."
            )
            src = Path(downloaded_path)
            total_bytes = _dir_size(src)
            self._local_dir.mkdir(parents=True, exist_ok=True)
            copied = 0
            self.progress_signal.emit(0, total_bytes)

            for item in sorted(src.iterdir()):
                if item.name == ".cache":
                    continue
                dst = self._local_dir / item.name
                if item.is_file():
                    shutil.copy2(item, dst)
                    copied += dst.stat().st_size
                elif item.is_dir():
                    copied += _copy_tree(item, dst)
                self.progress_signal.emit(copied, total_bytes)

    def _try_modelscope_download(self) -> tuple:
        """Try downloading via ModelScope (fast in mainland China).

        Returns (path, None) on success, or (None, error_msg) on failure.
        """
        try:
            from modelscope import snapshot_download
        except ImportError:
            return None, "modelscope not installed"

        self.status_signal.emit(
            f"Downloading from ModelScope...\n{self._model_name}"
        )
        try:
            return snapshot_download(self._model_name), None
        except Exception as e:
            msg = str(e)
            self.status_signal.emit(f"ModelScope failed, trying HF mirror...")
            return None, msg

    def _try_hf_download(self) -> tuple:
        """Try downloading via HuggingFace Hub.

        Returns (path, None) on success, or (None, error_msg) on failure.
        """
        from huggingface_hub import snapshot_download

        self.status_signal.emit(
            f"Downloading from HuggingFace...\n{self._model_name}"
        )
        try:
            return snapshot_download(
                repo_id=self._model_name,
                resume_download=True,
            ), None
        except Exception as e:
            return None, str(e)


# ── helpers ──────────────────────────────────────────────────────────────

def _dir_size(path: Path) -> int:
    """Total size of all files in a directory tree (follows symlinks)."""
    total = 0
    for root, dirs, files in os.walk(path):
        for f in files:
            fp = Path(root) / f
            try:
                if fp.is_symlink():
                    total += fp.resolve().stat().st_size
                else:
                    total += fp.stat().st_size
            except OSError:
                pass
    return total


def _copy_tree(src: Path, dst: Path) -> int:
    """Recursively copy a directory tree. Returns bytes copied."""
    dst.mkdir(parents=True, exist_ok=True)
    copied = 0
    for item in src.iterdir():
        if item.name == ".cache":
            continue
        target = dst / item.name
        if item.is_symlink():
            real = item.resolve()
            if real.is_file():
                shutil.copy2(real, target)
                copied += target.stat().st_size
            elif real.is_dir():
                copied += _copy_tree(real, target)
        elif item.is_file():
            shutil.copy2(item, target)
            copied += target.stat().st_size
        elif item.is_dir():
            copied += _copy_tree(item, target)
    return copied


def _copy_dir(src: Path, dst: Path):
    """Copy a directory tree, skipping .cache and resolving symlinks."""
    _copy_tree(src, dst)
