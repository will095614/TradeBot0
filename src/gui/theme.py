import dearpygui.dearpygui as dpg


def apply_terminal_theme() -> None:
    """
    Applies the Anthropic frontend-design institutional dark theme guidelines.
    TradingView / Bloomberg inspired carbon-obsidian palette (#0B0E14 & #131722)
    with crisp borders, balanced spacing, and zero visual clutter.
    """
    with dpg.theme() as global_theme:
        with dpg.theme_component(dpg.mvAll):
            # Window & Panel Surfaces (Ultra-Deep Obsidian High-Contrast)
            dpg.add_theme_color(dpg.mvThemeCol_WindowBg, (8, 9, 12, 255))            # #08090C Obsidian Void
            dpg.add_theme_color(dpg.mvThemeCol_ChildBg, (14, 17, 24, 255))           # #0E1118 Deep Charcoal
            dpg.add_theme_color(dpg.mvThemeCol_Border, (28, 35, 51, 255))            # #1C2333 Crisp hairline border
            dpg.add_theme_color(dpg.mvThemeCol_PopupBg, (14, 17, 24, 255))
            dpg.add_theme_color(dpg.mvThemeCol_FrameBg, (22, 26, 36, 255))

            # Table & Headers
            dpg.add_theme_color(dpg.mvThemeCol_Header, (30, 36, 51, 255))
            dpg.add_theme_color(dpg.mvThemeCol_HeaderHovered, (42, 52, 74, 255))
            dpg.add_theme_color(dpg.mvThemeCol_HeaderActive, (255, 107, 53, 255))
            dpg.add_theme_color(dpg.mvThemeCol_TableHeaderBg, (19, 23, 34, 255))
            dpg.add_theme_color(dpg.mvThemeCol_TableBorderStrong, (40, 49, 68, 255))
            dpg.add_theme_color(dpg.mvThemeCol_TableBorderLight, (28, 35, 51, 255))

            # Buttons & Interactive Controls
            dpg.add_theme_color(dpg.mvThemeCol_Button, (25, 31, 44, 255))
            dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (38, 48, 68, 255))
            dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (255, 107, 53, 255))

            # Plot Surfaces
            dpg.add_theme_color(dpg.mvPlotCol_PlotBg, (8, 9, 12, 255))
            dpg.add_theme_color(dpg.mvPlotCol_FrameBg, (14, 17, 24, 255))

            # Typography: Razor Sharp Pure White
            dpg.add_theme_color(dpg.mvThemeCol_Text, (255, 255, 255, 255))
            dpg.add_theme_color(dpg.mvThemeCol_TextDisabled, (131, 145, 167, 255))

            # Geometry & Spacing
            dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 5.0)
            dpg.add_theme_style(dpg.mvStyleVar_WindowRounding, 6.0)
            dpg.add_theme_style(dpg.mvStyleVar_ChildRounding, 6.0)
            dpg.add_theme_style(dpg.mvStyleVar_FramePadding, 8.0, 5.0)
            dpg.add_theme_style(dpg.mvStyleVar_ItemSpacing, 8.0, 6.0)

    dpg.bind_theme(global_theme)


def create_series_theme(color: tuple[int, int, int, int], weight: float = 2.0) -> int:
    """
    Creates a dedicated GPU plot line series theme with explicit RGBA color and stroke thickness.
    """
    with dpg.theme() as series_theme:
        with dpg.theme_component(dpg.mvLineSeries):
            dpg.add_theme_color(dpg.mvPlotCol_Line, color, category=dpg.mvThemeCat_Plots)
            dpg.add_theme_style(dpg.mvPlotStyleVar_LineWeight, weight, category=dpg.mvThemeCat_Plots)
    return series_theme


# High-Contrast Electric Equity Curve & Indicator Palette
PALETTE = {
    "comp_agg": (255, 184, 0, 255),      # Electric Amber Gold #FFB800
    "comp_cons": (0, 210, 255, 255),     # Vivid Cyan Sky Blue #00D2FF
    "comp_atr": (168, 85, 247, 255),     # Electric Neon Purple #A855F7
    "comp_trail": (255, 46, 147, 255),   # Vibrant Electric Magenta #FF2E93
    "baseline": (131, 145, 167, 180),    # Slate Reference
    "eth_price": (255, 255, 255, 255),   # Pure Crisp White
    "ema_fast": (0, 210, 255, 230),      # Fast EMA Vivid Cyan
    "ema_slow": (255, 184, 0, 230),      # Slow EMA Amber Gold
    "bullish": (0, 230, 118, 255),       # Neon Emerald Green #00E676
    "bearish": (255, 51, 75, 255),       # Vibrant Crimson Red #FF334B
}
