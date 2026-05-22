"""theme.py — 晴空蓝 + 米白柔和配色主题"""

from PySide6.QtGui import QPalette, QColor, QFont


BG_PAGE      = "#F5F3EE"
BG_CARD      = "#FFFFFF"
BG_SIDEBAR   = "#F9F9F9"
ACCENT       = "#4A90D9"
ACCENT_LIGHT = "#DCE8F5"
TEXT_MAIN    = "#2D3436"
TEXT_SUB     = "#636E72"
BORDER       = "#DFE6E9"
SUCCESS      = "#00B894"
HOVER_ROW    = "#F0F4F8"


def apply_theme(app):
    palette = QPalette()
    CR = QPalette.ColorRole
    CG = QPalette.ColorGroup
    palette.setColor(CR.Window, QColor(BG_PAGE))
    palette.setColor(CR.WindowText, QColor(TEXT_MAIN))
    palette.setColor(CR.Base, QColor(BG_CARD))
    palette.setColor(CR.AlternateBase, QColor(BG_SIDEBAR))
    palette.setColor(CR.Text, QColor(TEXT_MAIN))
    palette.setColor(CR.BrightText, QColor(SUCCESS))
    palette.setColor(CR.Button, QColor(BG_CARD))
    palette.setColor(CR.ButtonText, QColor(TEXT_MAIN))
    palette.setColor(CR.Link, QColor(ACCENT))
    palette.setColor(CR.Highlight, QColor(ACCENT))
    palette.setColor(CR.HighlightedText, QColor(BG_CARD))
    palette.setColor(CG.Disabled, CR.Text, QColor("#B2BEC3"))
    palette.setColor(CG.Disabled, CR.ButtonText, QColor("#B2BEC3"))
    app.setPalette(palette)

    font = QFont("Microsoft YaHei UI", 10)
    app.setFont(font)

    css = (
        "QScrollBar:vertical, QScrollBar:horizontal { width: 0px; height: 0px; background: transparent; }"
        "QScrollBar::handle:vertical, QScrollBar::handle:horizontal { background: transparent; }"
        "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,"
        "QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0px; height: 0px; }"
        "QToolTip { background: " + BG_CARD + "; color: " + TEXT_MAIN + "; border: 1px solid " + BORDER + "; padding: 8px 12px; border-radius: 8px; }"
        "QSplitter::handle { background: " + BORDER + "; }"
        "QSplitter::handle:horizontal { width: 1px; }"
        "QLineEdit, QTextEdit, QPlainTextEdit {"
        "  background: " + BG_CARD + "; color: " + TEXT_MAIN + ";"
        "  border-top: 1px solid #E8EBF0; border-left: 1px solid #E8EBF0;"
        "  border-right: 1px solid #D0D5DD; border-bottom: 2px solid #C8CDD5;"
        "  border-radius: 10px; padding: 10px 14px;"
        "  selection-background-color: " + ACCENT_LIGHT + ";"
        "}"
        "QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {"
        "  border-top: 1px solid #C5D9F0; border-left: 1px solid #C5D9F0;"
        "  border-right: 1px solid " + ACCENT + "; border-bottom: 2px solid " + ACCENT + ";"
        "}"
        "QPushButton {"
        "  background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #FCFCFD, stop:1 #F0F2F5);"
        "  color: " + TEXT_MAIN + ";"
        "  border-top: 1px solid #E8EBF0; border-left: 1px solid #E8EBF0;"
        "  border-right: 1px solid #D0D5DD; border-bottom: 2px solid #C0C8D0;"
        "  border-radius: 10px; padding: 10px 22px; font-weight: 500;"
        "}"
        "QPushButton:hover {"
        "  background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #FFFFFF, stop:1 #E8EEF6);"
        "  border-bottom: 2px solid " + ACCENT + ";"
        "}"
        "QPushButton:pressed {"
        "  background: " + ACCENT_LIGHT + "; border-top: 2px solid #C0C8D0;"
        "  border-left: 1px solid #D0D5DD; border-right: 1px solid #E8EBF0; border-bottom: 1px solid #E8EBF0;"
        "}"
        "QPushButton:disabled { color: #B2BEC3; background: #F0F0F0; border: 1px solid " + BORDER + "; }"
        "QPushButton[cssClass=\"primary\"] {"
        "  background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4A90D9, stop:1 #6DB9E8);"
        "  color: white; border: none; border-bottom: 3px solid #3570B8; font-weight: 600;"
        "}"
        "QPushButton[cssClass=\"primary\"]:hover {"
        "  background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #3A7BC8, stop:1 #5DA8D9);"
        "  border-bottom: 3px solid #2D5FA0;"
        "}"
        "QPushButton[cssClass=\"primary\"]:pressed { background: #3570B8; border-bottom: 1px solid #2D5FA0; }"
        "QListWidget, QListView, QTreeView, QTableView {"
        "  background: " + BG_CARD + "; color: " + TEXT_MAIN + ";"
        "  border-top: 1px solid #E8EBF0; border-left: 1px solid #E8EBF0;"
        "  border-right: 1px solid #D0D5DD; border-bottom: 2px solid #C8CDD5;"
        "  border-radius: 12px; outline: none;"
        "}"
        "QListWidget::item:hover, QListView::item:hover, QTreeView::item:hover, QTableView::item:hover {"
        "  background: " + HOVER_ROW + "; border-radius: 6px;"
        "}"
        "QListWidget::item:selected, QListView::item:selected, QTreeView::item:selected, QTableView::item:selected {"
        "  background: " + ACCENT_LIGHT + "; color: " + TEXT_MAIN + "; border-radius: 6px;"
        "}"
        "QSlider::groove:horizontal { background: #D0D8E0; height: 6px; border-radius: 3px; }"
        "QSlider::handle:horizontal {"
        "  background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #6DB9E8, stop:1 #4A90D9);"
        "  width: 18px; height: 18px; margin: -6px 0; border-radius: 9px; border-bottom: 2px solid #3570B8;"
        "}"
        "QSlider::handle:horizontal:hover {"
        "  background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #7DC9F0, stop:1 #3A7BC8);"
        "}"
        "QGroupBox {"
        "  background: " + BG_CARD + ";"
        "  border-top: 1px solid #E8EBF0; border-left: 1px solid #E8EBF0;"
        "  border-right: 1px solid #D0D5DD; border-bottom: 2px solid #C8CDD5;"
        "  border-radius: 14px; margin-top: 18px; padding: 22px 18px 18px 18px; font-weight: 600;"
        "}"
        "QGroupBox::title { subcontrol-origin: margin; left: 16px; padding: 0 10px; color: " + ACCENT + "; font-size: 13px; }"
        "QTabWidget::pane { border: none; background: " + BG_PAGE + "; }"
        "QHeaderView::section {"
        "  background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #F8FAFB, stop:1 #EEF1F5);"
        "  color: " + ACCENT + "; font-weight: 600; border: none;"
        "  border-bottom: 2px solid " + ACCENT_LIGHT + "; padding: 10px 12px;"
        "}"
        "QComboBox {"
        "  background: " + BG_CARD + "; color: " + TEXT_MAIN + ";"
        "  border-top: 1px solid #E8EBF0; border-left: 1px solid #E8EBF0;"
        "  border-right: 1px solid #D0D5DD; border-bottom: 2px solid #C8CDD5;"
        "  border-radius: 10px; padding: 8px 14px;"
        "}"
        "QComboBox:hover { border-bottom: 2px solid " + ACCENT + "; }"
        "QComboBox::drop-down { border: none; width: 28px; }"
        "QComboBox QAbstractItemView {"
        "  background: " + BG_CARD + "; border: 1px solid " + BORDER + ";"
        "  border-radius: 10px; selection-background-color: " + ACCENT_LIGHT + ";"
        "}"
    )
    app.setStyleSheet(css)
