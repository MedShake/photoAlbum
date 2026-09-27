"""The legend uses locale labels, MSB styling and device-independent geometry."""
import pytest
from PySide6.QtCore import QLocale, QRectF
from PySide6.QtGui import QColor, QFont, QImage, QPainter
from PySide6.QtWidgets import QApplication

from photoalbum.album import PageInstance
from photoalbum.i18n import Translator
from photoalbum.templates.msb.geographic_map.composition import (
    GeographicMap,
    GeographicMapMarker,
)
from photoalbum.templates.msb.geographic_map.geography import GeographicBounds
from photoalbum.templates.msb.geographic_map import painter as map_painter
from photoalbum.templates.msb.geographic_map.painter import (
    _month_legend_rect,
    _paint_month_legend,
)
from photoalbum.templates.msb.geographic_map.preview import GeographicMapPreviewBackend
from photoalbum.templates.msb.geographic_map.rendering import render_options
from photoalbum.templates.msb.theme import MsbTheme, pack_settings_with_msb_theme


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.mark.parametrize("language", ["fr", "en"])
def test_legend_uses_locale_abbreviations_and_pack_theme(language):
    theme = MsbTheme(default_font_family="DejaVu Serif")
    theme.month_colors[6] = (12, 34, 56)
    options = render_options({}, Translator(language), pack_settings_with_msb_theme({}, theme))
    locale = QLocale(language)
    assert options["month_labels"] == {
        month: locale.monthName(month, QLocale.FormatType.ShortFormat)
        for month in range(1, 13)
    }
    assert options["month_labels"][6] != options["month_labels"][7]
    assert options["month_colors"][6] == QColor(12, 34, 56)
    assert options["legend_font_family"] == "DejaVu Serif"


def test_legend_dpi_and_inherited_font_do_not_change_layout(app):
    options = render_options({}, Translator("fr"))

    def render(dpi, inherited_bold):
        image = QImage(1200, 80, QImage.Format.Format_ARGB32)
        image.setDotsPerMeterX(round(dpi / .0254))
        image.setDotsPerMeterY(round(dpi / .0254))
        image.fill(QColor("#eaf2f4"))
        painter = QPainter(image)
        font = QFont("DejaVu Sans", 30)
        font.setBold(inherited_bold)
        painter.setFont(font)
        try:
            _paint_month_legend(
                painter, QRectF(100, 18, 1000, 44),
                month_colors=options["month_colors"],
                month_labels=options["month_labels"],
                months=tuple(range(1, 13)),
                font_family=options["legend_font_family"],
            )
        finally:
            painter.end()
        # Compare pixels, excluding the intentionally different DPI metadata.
        return bytes(image.constBits())

    assert render(96, False) == render(300, True)


def test_pack_font_change_invalidates_map_preview():
    backend = GeographicMapPreviewBackend()
    instance = PageInstance(template_id="geographic-map")
    default = backend.render_settings_signature(instance)
    serif = pack_settings_with_msb_theme({}, MsbTheme(default_font_family="DejaVu Serif"))
    assert backend.render_settings_signature(instance, template_pack_settings=serif) != default


def _legend_test_composition(*months):
    markers = tuple(
        GeographicMapMarker(
            longitude=-1.5 + index * 0.1,
            latitude=47.0 + index * 0.1,
            x=0.5,
            y=0.5,
            month=month,
        )
        for index, month in enumerate(months)
    )

    return GeographicMap(
        bounds=GeographicBounds(
            minimum_longitude=-5.0,
            minimum_latitude=45.0,
            maximum_longitude=2.0,
            maximum_latitude=50.0,
        ),
        markers=markers,
    )


def test_month_legend_contains_only_months_present_in_markers(
    app,
    monkeypatch,
):
    options = render_options({}, Translator("fr"))
    captured = []

    def capture_legend(*args, **kwargs):
        captured.append(kwargs["months"])

    monkeypatch.setattr(
        map_painter,
        "_paint_month_legend",
        capture_legend,
    )

    image = QImage(
        1200,
        700,
        QImage.Format.Format_ARGB32,
    )
    image.fill(QColor("#eaf2f4"))

    painter = QPainter(image)

    try:
        map_painter.paint_geographic_map(
            painter,
            QRectF(0, 0, 1200, 700),
            _legend_test_composition(
                3,
                1,
                3,
                None,
                1,
            ),
            month_colors=options["month_colors"],
            month_labels=options["month_labels"],
            point_color_mode="month",
            show_month_legend=True,
            legend_font_family=options[
                "legend_font_family"
            ],
        )
    finally:
        painter.end()

    assert captured == [(1, 3)]


def test_month_legend_is_not_painted_without_dated_markers(
    app,
    monkeypatch,
):
    options = render_options({}, Translator("fr"))
    calls = []

    def capture_legend(*args, **kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(
        map_painter,
        "_paint_month_legend",
        capture_legend,
    )

    image = QImage(
        1200,
        700,
        QImage.Format.Format_ARGB32,
    )
    image.fill(QColor("#eaf2f4"))

    painter = QPainter(image)

    try:
        map_painter.paint_geographic_map(
            painter,
            QRectF(0, 0, 1200, 700),
            _legend_test_composition(
                None,
                None,
            ),
            month_colors=options["month_colors"],
            month_labels=options["month_labels"],
            point_color_mode="month",
            show_month_legend=True,
            legend_font_family=options[
                "legend_font_family"
            ],
        )
    finally:
        painter.end()

    assert calls == []


@pytest.mark.parametrize(
    "month_count",
    [1, 2, 3, 4, 5, 6, 11, 12],
)
def test_month_legend_keeps_fixed_cell_width(month_count):
    """Removing months removes cells without resizing the remaining cells."""
    rect = QRectF(0, 0, 1200, 800)

    full = _month_legend_rect(rect, 12)
    legend = _month_legend_rect(rect, month_count)

    expected_cell_width = full.width() / 12.0

    assert legend.width() == pytest.approx(
        expected_cell_width * month_count
    )
    assert legend.height() == pytest.approx(full.height())
    assert legend.center().x() == pytest.approx(
        rect.center().x()
    )
