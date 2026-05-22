"""about_page.py — app info page."""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QScrollArea, QFrame,
)
from PySide6.QtCore import Qt


class AboutPage(QWidget):
    """About page: app name, version, license, tech stack."""

    def __init__(self, i18n, parent=None):
        super().__init__(parent)
        self._i18n = i18n

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(20)

        self._title_lbl = QLabel()
        self._title_lbl.setStyleSheet("font-size: 22px; font-weight: 700; color: #2D3436;")
        layout.addWidget(self._title_lbl)

        # App info card
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background: #FFFFFF;
                border: 1px solid #DFE6E9;
                border-radius: 12px;
            }
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(24, 20, 24, 20)
        card_layout.setSpacing(12)

        self._info_labels = []
        info_keys = [
            ("about.app_name", "about.app_name_val"),
            ("about.version", "about.version_val"),
            ("about.license", "about.license_val"),
            ("about.author", "about.author_val"),
        ]
        for label_key, value_key in info_keys:
            lbl = QLabel()
            lbl.setStyleSheet("font-size: 14px; color: #2D3436; border: none; background: transparent;")
            card_layout.addWidget(lbl)
            self._info_labels.append((lbl, label_key, value_key))

        layout.addWidget(card)

        # Tech stack
        self._tech_title = QLabel()
        self._tech_title.setStyleSheet("font-size: 16px; font-weight: 600; color: #2D3436;")
        layout.addWidget(self._tech_title)

        tech_card = QFrame()
        tech_card.setStyleSheet("""
            QFrame {
                background: #FFFFFF;
                border: 1px solid #DFE6E9;
                border-radius: 12px;
            }
        """)
        tech_layout = QVBoxLayout(tech_card)
        tech_layout.setContentsMargins(24, 20, 24, 20)
        tech_layout.setSpacing(8)

        self._tech_labels = []
        tech_key_list = [
            "about.tech_gui", "about.tech_vector", "about.tech_llm",
            "about.tech_embed", "about.tech_bm25", "about.tech_rrf",
        ]
        for key in tech_key_list:
            lbl = QLabel()
            lbl.setWordWrap(True)
            lbl.setStyleSheet("font-size: 13px; color: #636E72; border: none; background: transparent;")
            tech_layout.addWidget(lbl)
            self._tech_labels.append((lbl, key))

        layout.addWidget(tech_card)

        # License text
        self._license_title = QLabel()
        self._license_title.setStyleSheet("font-size: 16px; font-weight: 600; color: #2D3436;")
        layout.addWidget(self._license_title)

        license_text = (
            "Permission is hereby granted, free of charge, to any person obtaining a copy "
            "of this software and associated documentation files (the \"Software\"), to deal "
            "in the Software without restriction, including without limitation the rights "
            "to use, copy, modify, merge, publish, distribute, sublicense, and/or sell "
            "copies of the Software, and to permit persons to whom the Software is "
            "furnished to do so, subject to the following conditions:\n\n"
            "THE SOFTWARE IS PROVIDED \"AS IS\", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR "
            "IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, "
            "FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT."
        )

        license_lbl = QLabel(license_text)
        license_lbl.setWordWrap(True)
        license_lbl.setStyleSheet("font-size: 12px; color: #636E72; padding: 12px;")

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        scroll.setWidget(license_lbl)
        scroll.setMaximumHeight(120)
        layout.addWidget(scroll)

        layout.addStretch()

        self.retranslate()

    def retranslate(self):
        self._title_lbl.setText(self._i18n.t("about.title"))
        for lbl, label_key, value_key in self._info_labels:
            lbl.setText(
                f"{self._i18n.t(label_key)}: {self._i18n.t(value_key)}"
            )
        self._tech_title.setText(self._i18n.t("about.tech_stack"))
        for lbl, key in self._tech_labels:
            lbl.setText("• " + self._i18n.t(key))
        self._license_title.setText(self._i18n.t("about.license_title"))
