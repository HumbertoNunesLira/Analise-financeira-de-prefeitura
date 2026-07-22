"""Paleta e helpers de formatação — mesmos valores validados usados em analise.ipynb
(Projeto 2), reaproveitados aqui para manter consistência visual entre o artigo
estático e o dashboard automatizado."""

import numpy as np

CAT_PALETTE = {
    "blue": "#2a78d6",
    "aqua": "#1baf7a",
    "yellow": "#eda100",
    "green": "#008300",
    "violet": "#4a3aa7",
    "red": "#e34948",
    "magenta": "#e87ba4",
    "orange": "#eb6834",
}
CAT_ORDER = list(CAT_PALETTE.values())

STATUS = {
    "good": "#0ca30c",
    "warning": "#fab219",
    "serious": "#ec835a",
    "critical": "#d03b3b",
}

INK = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRID = "#e1e0d9"
SURFACE = "#fcfcfb"


def hex_to_rgba(hex_color: str, alpha: float) -> str:
    """'#4a3aa7', 0.13 -> 'rgba(74,58,167,0.13)' — Plotly não aceita hex com alfa embutido."""
    hex_color = hex_color.lstrip("#")
    r, g, b = (int(hex_color[i : i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{alpha})"


def fmt_reais(valor: float) -> str:
    """Formata em R$ com separador de milhar; usado em rótulos diretos."""
    if valor is None or (isinstance(valor, float) and np.isnan(valor)):
        return "—"
    if abs(valor) >= 1_000_000:
        return f"R$ {valor/1_000_000:,.1f} mi".replace(",", "@").replace(".", ",").replace("@", ".")
    if abs(valor) >= 1_000:
        return f"R$ {valor/1_000:,.0f} mil".replace(",", ".")
    return f"R$ {valor:,.0f}".replace(",", ".")


def fmt_reais_full(valor: float) -> str:
    """Formata em R$ com centavos, formato brasileiro completo."""
    if valor is None or (isinstance(valor, float) and np.isnan(valor)):
        return "—"
    s = f"{valor:,.2f}"
    s = s.replace(",", "@").replace(".", ",").replace("@", ".")
    return f"R$ {s}"
