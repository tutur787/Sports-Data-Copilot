from __future__ import annotations

import re

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
from rapidfuzz import fuzz, process

import backend.mappings.fbref_mapping as fbm


# ---------------------------------------------------------------------------
# Design constants
# ---------------------------------------------------------------------------

# One fixed color per entity slot (team / player).  Colors chosen for high
# contrast against each other AND against a white chart background.
_ENTITY_COLORS = [
    "#e63946",  # vivid red
    "#2176ae",  # royal blue
    "#f4a623",  # amber
    "#2ca58d",  # teal / accent
    "#9b5de5",  # violet
    "#f15bb5",  # pink
    "#00bbf9",  # sky blue
    "#fee440",  # yellow
    "#606c38",  # olive
    "#d62828",  # dark red
]

# Different dash patterns, one per metric.
_DASH_STYLES = ["solid", "dash", "dot", "dashdot", "longdash", "longdashdot"]

# Light fill versions of the entity colors (used for bar + radar fills).
_ENTITY_COLORS_ALPHA = [
    "rgba(230,57,70,0.18)",
    "rgba(33,118,174,0.18)",
    "rgba(244,166,35,0.18)",
    "rgba(44,165,141,0.18)",
    "rgba(155,93,229,0.18)",
    "rgba(241,91,181,0.18)",
    "rgba(0,187,249,0.18)",
    "rgba(254,228,64,0.18)",
    "rgba(96,108,56,0.18)",
    "rgba(214,40,40,0.18)",
]

# Accent color that matches the app theme
_ACCENT = "#0f9d8d"
_HEADER_COLOR = "#0f9d8d"
_HEADER_FONT = "#ffffff"
_ROW_A = "#f8fcfd"
_ROW_B = "#ffffff"


class Visualization:
    def __init__(self, parsed: dict):
        self.parsed = parsed
        self.team = parsed.get("team")
        self.league = parsed.get("league") or "ENG-Premier League"
        self.metric = parsed.get("metric")
        self.player = parsed.get("player")
        self.stat_type = parsed.get("stat_type") or "standard"
        self.top_n: int | None = parsed.get("top_n")
        self.top_n_ascending: bool = bool(parsed.get("top_n_ascending", False))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create_graph(self, df: pd.DataFrame) -> list[str]:
        """
        Build Plotly chart(s) from *df* and the parsed query context.
        Always returns a list of Plotly JSON strings.
        """
        chart_type = (self.parsed.get("chart_type") or "table").lower()

        if df is None or df.empty:
            raise ValueError("DataFrame is empty or None — cannot create a graph.")

        # Flatten MultiIndex columns produced by soccerdata / pandas groupby.
        if isinstance(df.columns, pd.MultiIndex):
            df = df.copy()
            seen: dict[str, int] = {}
            flat: list[str] = []
            for col in df.columns:
                parts = [str(c) for c in col if str(c).strip()]
                name = "_".join(parts) if parts else "col"
                if name in seen:
                    seen[name] += 1
                    name = f"{name}_{seen[name]}"
                else:
                    seen[name] = 0
                flat.append(name)
            df.columns = flat

        metrics = self.metric if isinstance(self.metric, list) else [self.metric]
        metrics = [m for m in metrics if m]
        if not metrics:
            metrics = ["all"]

        mapped_metrics = [fbm.get_fbref_metric(m) or m for m in metrics]
        mapped_metrics = list(dict.fromkeys(mapped_metrics))  # deduplicate

        # Build a clean title: join list values with " vs " instead of repr
        def _fmt(val):
            if isinstance(val, list):
                return " vs ".join(str(v) for v in val)
            return str(val) if val else ""

        entity_label = _fmt(self.team) or _fmt(self.player) or _fmt(self.league)
        title = f"{entity_label} — {self.stat_type.capitalize()} Stats"

        metric_to_cols = self._map_metrics_to_columns(mapped_metrics, df.columns.tolist())

        dispatch = {
            "bar": self._bar,
            "line": self._line,
            "scatter": self._scatter,
            "pie": self._pie,
            "heatmap": self._heatmap,
            "radar": self._radar,
            "table": self._table,
        }
        handler = dispatch.get(chart_type, self._table)
        return handler(df, mapped_metrics, metric_to_cols, title)

    # ------------------------------------------------------------------
    # Column-matching helper
    # ------------------------------------------------------------------

    @staticmethod
    def _map_metrics_to_columns(
        metric_keys: list[str], columns: list[str]
    ) -> dict[str, list[str]]:
        """
        Map each FBref abbreviation / phrase to matching DataFrame columns.

        Strategy (in priority order):
        1. Exact full-token match after splitting column on '_' and spaces.
        2. Case-insensitive substring match (≥3-char keys only).
        3. RapidFuzz fuzzy fallback (≥80 score).
        """
        cols_lower = {col.lower(): col for col in columns}

        mapped: dict[str, list[str]] = {}
        for metric in metric_keys:
            ml = metric.lower().strip()
            matched: list[str] = []

            for col in columns:
                tokens = [t.lower() for t in re.split(r"[_\s]", col) if t]
                if ml in tokens or ml == col.lower():
                    matched.append(col)
                elif len(ml) >= 3 and ml in col.lower():
                    matched.append(col)

            if not matched:
                hit = process.extractOne(ml, list(cols_lower.keys()), scorer=fuzz.WRatio)
                if hit and hit[1] >= 80:
                    matched.append(cols_lower[hit[0]])

            mapped[metric] = list(dict.fromkeys(matched))
        return mapped

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _entity_color(index: int) -> str:
        return _ENTITY_COLORS[index % len(_ENTITY_COLORS)]

    @staticmethod
    def _entity_color_alpha(index: int) -> str:
        return _ENTITY_COLORS_ALPHA[index % len(_ENTITY_COLORS_ALPHA)]

    @staticmethod
    def _dash_style(index: int) -> str:
        return _DASH_STYLES[index % len(_DASH_STYLES)]

    # Generic FBref category prefixes that add no useful meaning when shown alone.
    # When a column has one of these as its *only* non-trivial segment we still
    # keep it, but we never strip the sub-category that follows it.
    _GENERIC_PREFIXES = frozenset({
        "performance", "expected", "progression", "per90", "per 90 minutes",
        "sca types", "gca types",
    })

    @classmethod
    def _clean_col_label(cls, col: str) -> str:
        """
        Return a human-readable, context-rich column label.

        Rules:
        - Split on '_'.
        - Drop leading segments that are pure FBref category noise
          (e.g. "Performance", "Expected").
        - Keep the last **two** meaningful segments so sub-variants are
          distinguishable:  "Short_Cmp%" → "Short Cmp%",
                            "Total_Cmp%"  → "Total Cmp%",
                            "Performance_Gls" → "Performance Gls" (kept — no
                            better alternative without the prefix).
        - Single-segment columns (e.g. "season", "Ast") are returned as-is
          after title-casing.
        """
        parts = [p for p in col.split("_") if p.strip()]
        if not parts:
            return col.title()

        # Filter out pure-noise leading prefixes, but only when ≥2 parts remain
        cleaned = [
            p for p in parts
            if p.lower() not in cls._GENERIC_PREFIXES
        ]
        if not cleaned:
            cleaned = parts  # fallback: keep everything

        # Use last two segments to distinguish sub-variants (Short vs Medium…)
        label_parts = cleaned[-2:] if len(cleaned) >= 2 else cleaned
        return " ".join(label_parts).title()

    @staticmethod
    def _apply_base_layout(fig: go.Figure, title: str) -> None:
        """Apply consistent base styling to every figure."""
        fig.update_layout(
            title=dict(text=title, x=0.5, font=dict(size=16)),
            font=dict(family="Space Grotesk, Avenir Next, Segoe UI, sans-serif", size=13),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(249,252,253,1)",
            margin=dict(l=40, r=30, t=60, b=40),
            legend=dict(
                bgcolor="rgba(255,255,255,0.85)",
                bordercolor="#d8e6eb",
                borderwidth=1,
                font=dict(size=12),
            ),
        )
        fig.update_xaxes(
            gridcolor="#e8f0f3",
            linecolor="#d8e6eb",
            showline=True,
            zeroline=False,
        )
        fig.update_yaxes(
            gridcolor="#e8f0f3",
            linecolor="#d8e6eb",
            showline=True,
            zeroline=False,
        )

    def _apply_top_n(
        self,
        df: pd.DataFrame,
        sort_col: str | None = None,
    ) -> pd.DataFrame:
        """
        Sort *df* by *sort_col* and return the first self.top_n rows.

        - If self.top_n is None, the full DataFrame is returned unchanged.
        - self.top_n_ascending = False  → highest values first  (top N)
        - self.top_n_ascending = True   → lowest values first   (bottom N)
        - If sort_col is missing or non-numeric, the DataFrame is sliced
          without re-sorting so the caller's sort order is preserved.
        """
        if not self.top_n:
            return df

        if (
            sort_col
            and sort_col in df.columns
            and pd.api.types.is_numeric_dtype(df[sort_col])
        ):
            df = df.sort_values(sort_col, ascending=self.top_n_ascending)

        return df.head(self.top_n)

    # ------------------------------------------------------------------
    # Chart handlers — each returns list[str] (Plotly JSON strings)
    # ------------------------------------------------------------------

    # ── LINE ──────────────────────────────────────────────────────────────

    # Maximum separate line-chart panels to produce (guards against 20+ charts
    # when a broad metric like "passing" matches dozens of columns).
    _MAX_LINE_PANELS = 8

    def _line(
        self,
        df: pd.DataFrame,
        mapped_metrics: list[str],
        metric_to_cols: dict[str, list[str]],
        title: str,
    ) -> list[str]:
        """
        One figure per stat column — each panel shows only one specific metric
        (e.g. "Short Cmp%") so the chart is never overcrowded.

        Within each panel, one colored line per entity (team / player).  The
        legend therefore only needs to name the entity — the chart title already
        tells you which stat you are looking at.

        Color  →  team / player  (consistent across all panels)
        Panel  →  one specific stat column
        """
        entity_col = (
            "team" if "team" in df.columns
            else "player" if "player" in df.columns
            else None
        )
        x_col = "season" if "season" in df.columns else None

        entities: list = sorted(df[entity_col].unique().tolist()) if entity_col else [None]
        entity_color = {e: self._entity_color(i) for i, e in enumerate(entities)}

        # Collect all unique columns across every requested metric, preserving
        # the order metrics were requested in.
        ordered_cols: list[tuple[str, str]] = []  # (metric_key, column_name)
        seen_cols: set[str] = set()
        for metric in mapped_metrics:
            for col in metric_to_cols.get(metric, []):
                if col not in seen_cols:
                    ordered_cols.append((metric, col))
                    seen_cols.add(col)

        # Cap to avoid flooding the UI with dozens of charts
        ordered_cols = ordered_cols[: self._MAX_LINE_PANELS]

        figs: list[go.Figure] = []

        for metric_key, col in ordered_cols:
            col_label = self._clean_col_label(col)
            chart_title = f"{title} — {col_label}"

            fig = go.Figure()

            for entity in entities:
                subset = df[df[entity_col] == entity] if entity_col else df
                if col not in subset.columns:
                    continue

                color = entity_color.get(entity, _ENTITY_COLORS[0])
                x_vals = subset[x_col] if x_col else subset.index
                name = str(entity) if entity else col_label

                fig.add_trace(
                    go.Scatter(
                        x=x_vals,
                        y=subset[col],
                        mode="lines+markers",
                        name=name,
                        line=dict(color=color, width=2.5),
                        marker=dict(size=8, color=color,
                                    line=dict(color="white", width=1.5)),
                        hovertemplate=(
                            f"<b>{name}</b><br>"
                            "Season: %{x}<br>"
                            f"{col_label}: %{{y:.2f}}<extra></extra>"
                        ),
                    )
                )

            self._apply_base_layout(fig, chart_title)
            fig.update_layout(
                xaxis_title="Season",
                yaxis_title=col_label,
                hovermode="x unified",
                # Show legend only when there is more than one entity
                showlegend=len(entities) > 1,
            )
            figs.append(fig)

        if not figs:
            return self._table(df, mapped_metrics, metric_to_cols, title)

        return [pio.to_json(fig) for fig in figs]

    # ── BAR ───────────────────────────────────────────────────────────────

    # When there are more than this many entities it is a league-wide ranking
    # chart: render horizontal + sorted instead of grouped vertical bars.
    _RANKING_BAR_THRESHOLD = 6

    def _bar(
        self,
        df: pd.DataFrame,
        mapped_metrics: list[str],
        metric_to_cols: dict[str, list[str]],
        title: str,
    ) -> list[str]:
        """
        Two bar modes depending on entity count:

        Comparison mode (≤6 entities):
            Vertical grouped bars, one color per team/player, x-axis = season.
            Best for "Compare Arsenal and Chelsea goals past 3 seasons".

        Ranking mode (>6 entities, i.e. league-wide):
            Horizontal bars sorted descending, accent-gradient coloring, one
            bar per team/player.  Best for "Top scorers Premier League 2024".
            One figure per metric so each chart stays clean.
        """
        entity_col = next(
            (c for c in ["team", "player"] if c in df.columns), None
        )
        x_col = "season" if "season" in df.columns else entity_col

        # Collect all matched columns
        cols_to_use: list[str] = []
        for metric in mapped_metrics:
            cols_to_use.extend(metric_to_cols.get(metric, []))
        cols_to_use = list(dict.fromkeys(cols_to_use))

        if not cols_to_use:
            return self._table(df, mapped_metrics, metric_to_cols, title)

        entities: list[str] = sorted(df[entity_col].unique().tolist()) if entity_col else []
        n_entities = len(entities)
        ranking_mode = n_entities > self._RANKING_BAR_THRESHOLD

        figs: list[go.Figure] = []

        for metric in mapped_metrics:
            m_cols = metric_to_cols.get(metric, [])
            if not m_cols:
                continue
            primary_col = m_cols[0]
            col_label = self._clean_col_label(primary_col)

            fig = go.Figure()

            if ranking_mode:
                # ── Ranking mode: horizontal bars sorted by value ─────────
                # Aggregate: mean across seasons if season column exists
                if entity_col:
                    agg = (
                        df[[entity_col, primary_col]]
                        .groupby(entity_col)[primary_col]
                        .mean()
                        # Sort descending first so top_n slices the best teams,
                        # then reverse to ascending for the horizontal bar layout
                        # (Plotly draws bottom→top, so last item appears at top).
                        .sort_values(ascending=False)
                    )
                    # Apply top_n limit — keep the N highest (or lowest) teams
                    if self.top_n:
                        if self.top_n_ascending:
                            agg = agg.iloc[-self.top_n:]  # worst N
                        else:
                            agg = agg.iloc[: self.top_n]  # best N
                    # Reverse so the highest value ends up at the top of the chart
                    agg = agg.sort_values(ascending=True)
                    bar_labels = agg.index.tolist()
                    bar_values = agg.values.tolist()
                else:
                    bar_labels = df.index.astype(str).tolist()
                    bar_values = df[primary_col].tolist()

                # Accent gradient: lighter for low, darker for high
                n = len(bar_values)
                bar_colors = [
                    f"rgba(15,157,141,{0.35 + 0.65 * (i / max(n - 1, 1))})"
                    for i in range(n)
                ]

                fig.add_trace(
                    go.Bar(
                        x=bar_values,
                        y=bar_labels,
                        orientation="h",
                        marker=dict(
                            color=bar_colors,
                            line=dict(color="rgba(255,255,255,0.3)", width=0.5),
                        ),
                        hovertemplate=(
                            "<b>%{y}</b><br>"
                            f"{col_label}: %{{x:.2f}}<extra></extra>"
                        ),
                        showlegend=False,
                    )
                )
                self._apply_base_layout(fig, f"{title} — {col_label}")
                fig.update_layout(
                    xaxis_title=col_label,
                    yaxis_title="",
                    yaxis=dict(tickfont=dict(size=11)),
                    height=max(400, len(bar_labels) * 26),  # scale height with entity count
                    margin=dict(l=140, r=30, t=60, b=40),
                )

            elif n_entities > 1:
                # ── Comparison mode: vertical grouped bars ────────────────
                for ei, entity in enumerate(entities):
                    edf = df[df[entity_col] == entity]
                    x_vals = edf[x_col] if x_col and x_col in edf.columns else edf.index
                    fig.add_trace(
                        go.Bar(
                            name=str(entity),
                            x=x_vals,
                            y=edf[primary_col],
                            marker_color=self._entity_color(ei),
                            hovertemplate=(
                                f"<b>{entity}</b><br>"
                                "%{x}<br>"
                                f"{col_label}: %{{y:.2f}}<extra></extra>"
                            ),
                        )
                    )
                fig.update_layout(barmode="group")
                self._apply_base_layout(fig, f"{title} — {col_label}")
                fig.update_layout(
                    xaxis_title=x_col.title() if x_col else "",
                    yaxis_title=col_label,
                )

            else:
                # ── Single entity: bars colored by metric column ──────────
                x_vals = df[x_col] if x_col and x_col in df.columns else df.index
                for mi, col in enumerate(m_cols):
                    fig.add_trace(
                        go.Bar(
                            name=self._clean_col_label(col),
                            x=x_vals,
                            y=df[col],
                            marker_color=self._entity_color(mi),
                            hovertemplate=(
                                f"{self._clean_col_label(col)}: %{{y:.2f}}<extra></extra>"
                            ),
                        )
                    )
                fig.update_layout(barmode="group")
                self._apply_base_layout(fig, f"{title} — {col_label}")
                fig.update_layout(
                    xaxis_title=x_col.title() if x_col else "",
                    yaxis_title=col_label,
                )

            figs.append(fig)

        if not figs:
            return self._table(df, mapped_metrics, metric_to_cols, title)

        return [pio.to_json(fig) for fig in figs]

    # ── SCATTER ───────────────────────────────────────────────────────────

    # Above this many entities, on-chart text labels overlap — use hover only.
    _SCATTER_LABEL_THRESHOLD = 8

    def _scatter(
        self,
        df: pd.DataFrame,
        mapped_metrics: list[str],
        metric_to_cols: dict[str, list[str]],
        title: str,
    ) -> list[str]:
        """
        Scatter plot where each entity (team / player) is a dot.

        Label strategy:
          ≤8 entities  → labels printed directly on the chart (self-annotating)
          >8 entities  → hover-only labels (avoids a pile-up of overlapping text)

        An OLS trend line is always drawn so the correlation is immediately
        visible without the user having to mentally fit a line through the dots.
        """
        if len(mapped_metrics) < 2:
            raise ValueError("Scatter plot requires at least two metrics.")

        x_cols = metric_to_cols.get(mapped_metrics[0], [])
        y_cols = metric_to_cols.get(mapped_metrics[1], [])
        if not x_cols or not y_cols:
            raise ValueError(
                "Scatter plot requires both metrics to have matching columns."
            )

        x_col, y_col = x_cols[0], y_cols[0]
        x_label = self._clean_col_label(x_col)
        y_label = self._clean_col_label(y_col)

        entity_col = next(
            (c for c in ["team", "player"] if c in df.columns), None
        )

        # Drop rows where either axis is NaN
        plot_df = df[[x_col, y_col] + ([entity_col] if entity_col else [])].dropna()

        # Apply top_n: keep only the N entities ranked by the x-axis metric.
        # ("Top 10 teams goals vs xG" → show only the 10 highest-scoring teams.)
        if self.top_n and entity_col and x_col in plot_df.columns:
            ranked = (
                plot_df.groupby(entity_col)[x_col]
                .mean()
                .sort_values(ascending=self.top_n_ascending)
                .head(self.top_n)
                .index
            )
            plot_df = plot_df[plot_df[entity_col].isin(ranked)]

        entities = sorted(plot_df[entity_col].unique().tolist()) if entity_col else [None]
        n_entities = len(entities)
        many_entities = n_entities > self._SCATTER_LABEL_THRESHOLD

        # For many entities use a single accent colour — there are too many
        # dots to assign meaningful individual colours.
        if many_entities:
            entity_color_map = {e: _ACCENT for e in entities}
        else:
            entity_color_map = {e: self._entity_color(i) for i, e in enumerate(entities)}

        fig = go.Figure()

        # ── Data points ──────────────────────────────────────────────────
        if many_entities:
            # One trace for all points — cleaner hover, no legend clutter
            labels = plot_df[entity_col].astype(str) if entity_col else plot_df.index.astype(str)
            fig.add_trace(
                go.Scatter(
                    x=plot_df[x_col],
                    y=plot_df[y_col],
                    mode="markers",
                    name="",
                    text=labels,
                    marker=dict(
                        color=_ACCENT,
                        size=10,
                        opacity=0.8,
                        line=dict(color="white", width=1.2),
                    ),
                    hovertemplate=(
                        "<b>%{text}</b><br>"
                        f"{x_label}: %{{x:.2f}}<br>"
                        f"{y_label}: %{{y:.2f}}<extra></extra>"
                    ),
                    showlegend=False,
                )
            )
        else:
            # One trace per entity with individual colour + on-chart label
            for entity in entities:
                subset = plot_df[plot_df[entity_col] == entity] if entity_col else plot_df
                color = entity_color_map[entity]
                label_text = subset[entity_col].astype(str) if entity_col else subset.index.astype(str)
                fig.add_trace(
                    go.Scatter(
                        x=subset[x_col],
                        y=subset[y_col],
                        mode="markers+text",
                        name=str(entity) if entity else "Data",
                        text=label_text,
                        textposition="top center",
                        textfont=dict(size=11),
                        marker=dict(
                            color=color,
                            size=11,
                            line=dict(color="white", width=1.5),
                        ),
                        hovertemplate=(
                            f"<b>%{{text}}</b><br>"
                            f"{x_label}: %{{x:.2f}}<br>"
                            f"{y_label}: %{{y:.2f}}<extra></extra>"
                        ),
                    )
                )

        # ── OLS trend line ────────────────────────────────────────────────
        # Fit a simple linear regression through all plotted points so the
        # correlation is immediately readable without mental effort.
        try:
            x_vals = pd.to_numeric(plot_df[x_col], errors="coerce").dropna()
            y_vals = pd.to_numeric(plot_df[y_col], errors="coerce").dropna()
            common_idx = x_vals.index.intersection(y_vals.index)
            if len(common_idx) >= 3:
                xv = x_vals.loc[common_idx].values
                yv = y_vals.loc[common_idx].values
                coeffs = np.polyfit(xv, yv, 1)
                x_range = np.linspace(xv.min(), xv.max(), 100)
                y_trend = np.polyval(coeffs, x_range)
                # Correlation coefficient for the legend label
                r = float(np.corrcoef(xv, yv)[0, 1])
                trend_label = f"Trend (r = {r:+.2f})"
                fig.add_trace(
                    go.Scatter(
                        x=x_range,
                        y=y_trend,
                        mode="lines",
                        name=trend_label,
                        line=dict(color="#e63946", dash="dash", width=2),
                        hoverinfo="skip",
                    )
                )
        except Exception:
            pass  # Trend line is nice-to-have; never crash for it

        self._apply_base_layout(fig, title)
        fig.update_layout(
            xaxis_title=x_label,
            yaxis_title=y_label,
            showlegend=not many_entities,
        )
        return [pio.to_json(fig)]

    # ── PIE ───────────────────────────────────────────────────────────────

    def _pie(
        self,
        df: pd.DataFrame,
        mapped_metrics: list[str],
        metric_to_cols: dict[str, list[str]],
        title: str,
    ) -> list[str]:
        """
        Donut chart with percentage + label displayed inside each slice.
        Slices are sorted largest-first and colored with the entity palette.
        """
        metric = mapped_metrics[0]
        cols = metric_to_cols.get(metric, [])
        if not cols:
            raise ValueError(f"Metric '{metric}' not found in DataFrame.")

        metric_col = cols[0]
        group_col = next(
            (c for c in ["team", "player"] if c in df.columns), None
        )

        if group_col:
            pie_data = (
                df.groupby(group_col)[metric_col]
                .sum()
                .sort_values(ascending=False)
            )
            labels = pie_data.index.astype(str).tolist()
            values = pie_data.values.tolist()
        else:
            series = df[metric_col].sort_values(ascending=False)
            labels = series.index.astype(str).tolist()
            values = series.tolist()

        colors = [self._entity_color(i) for i in range(len(labels))]

        fig = go.Figure(
            data=go.Pie(
                labels=labels,
                values=values,
                hole=0.38,                          # donut for readability
                textinfo="label+percent",
                textposition="auto",
                marker=dict(
                    colors=colors,
                    line=dict(color="white", width=2),
                ),
                hovertemplate=(
                    "<b>%{label}</b><br>"
                    f"{self._clean_col_label(metric_col)}: %{{value:.2f}}<br>"
                    "Share: %{percent}<extra></extra>"
                ),
                sort=False,                         # already sorted
            )
        )
        fig.update_layout(
            title=dict(text=f"{title} — {metric.title()}", x=0.5, font=dict(size=16)),
            font=dict(family="Space Grotesk, Avenir Next, Segoe UI, sans-serif", size=13),
            paper_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=20, r=20, t=60, b=20),
            legend=dict(
                bgcolor="rgba(255,255,255,0.85)",
                bordercolor="#d8e6eb",
                borderwidth=1,
            ),
        )
        return [pio.to_json(fig)]

    # ── HEATMAP ───────────────────────────────────────────────────────────

    def _heatmap(
        self,
        df: pd.DataFrame,
        mapped_metrics: list[str],
        metric_to_cols: dict[str, list[str]],
        title: str,
    ) -> list[str]:
        """
        Two modes depending on data shape:

        Mode A — Teams × Seasons  (when season column has >1 unique value AND
                  a single primary metric is requested):
            Rows = teams, Columns = seasons.
            Best for "Premier League goal trends past 5 seasons" — you instantly
            see which team improved / regressed each year.
            One figure per matched metric column.

        Mode B — Teams × Metrics  (everything else):
            Rows = teams / players, Columns = stat columns.
            Best for "compare all Premier League teams shooting passing defense".
        """
        entity_col = next(
            (c for c in ["team", "player"] if c in df.columns), None
        )
        has_season = "season" in df.columns
        multi_season = has_season and df["season"].nunique() > 1

        # Collect metric columns
        metric_cols: list[str] = []
        for metric in mapped_metrics:
            metric_cols.extend(metric_to_cols.get(metric, []))
        metric_cols = list(dict.fromkeys(metric_cols))

        if not metric_cols:
            metric_cols = df.select_dtypes(include="number").columns.tolist()[:10]
        if not metric_cols:
            raise ValueError("No numeric columns available for heatmap.")

        figs: list[go.Figure] = []

        if multi_season and entity_col:
            # ── Mode A: one heatmap per metric, rows=teams, cols=seasons ──
            for mcol in metric_cols[:6]:   # cap at 6 panels
                try:
                    pivot = (
                        df[[entity_col, "season", mcol]]
                        .groupby([entity_col, "season"])[mcol]
                        .mean()
                        .unstack("season")   # columns become seasons
                    )
                except Exception:
                    continue

                # Sort teams by their mean across seasons (best teams at top)
                pivot = pivot.loc[pivot.mean(axis=1).sort_values(ascending=False).index]

                col_labels = [str(c) for c in pivot.columns]
                row_labels = pivot.index.astype(str).tolist()
                z_values = pivot.values.tolist()
                col_label = self._clean_col_label(mcol)

                fig = self._build_heatmap_figure(
                    z_values, col_labels, row_labels,
                    colorbar_title=col_label,
                    chart_title=f"{title} — {col_label} by Season",
                    annotate=len(row_labels) <= 12,   # skip annotation on very large grids
                )
                figs.append(fig)

        else:
            # ── Mode B: one heatmap, rows=teams, cols=metrics ──────────────
            if entity_col:
                pivot = (
                    df[[entity_col] + metric_cols]
                    .groupby(entity_col)[metric_cols]
                    .mean()
                )
                # Sort by sum of all metrics so top-performing teams are first
                pivot = pivot.loc[pivot.sum(axis=1).sort_values(ascending=False).index]
            else:
                pivot = df[metric_cols].select_dtypes(include="number")

            # Apply top_n: slice to the first N rows (already sorted by
            # sum-of-metrics descending, so this keeps the strongest teams).
            if self.top_n:
                if self.top_n_ascending:
                    pivot = pivot.iloc[-self.top_n :]   # worst N (bottom rows)
                else:
                    pivot = pivot.iloc[: self.top_n]    # best N (top rows)

            col_labels = [self._clean_col_label(c) for c in pivot.columns]
            row_labels = pivot.index.astype(str).tolist()
            z_values = pivot.values.tolist()

            fig = self._build_heatmap_figure(
                z_values, col_labels, row_labels,
                colorbar_title="Value",
                chart_title=title,
                annotate=len(row_labels) <= 12,
            )
            figs.append(fig)

        if not figs:
            return self._table(df, mapped_metrics, metric_to_cols, title)
        return [pio.to_json(f) for f in figs]

    @staticmethod
    def _build_heatmap_figure(
        z_values: list,
        col_labels: list[str],
        row_labels: list[str],
        colorbar_title: str,
        chart_title: str,
        annotate: bool = True,
    ) -> go.Figure:
        """Shared figure builder for both heatmap modes."""
        annotations: list[dict] = []
        if annotate:
            for ri, row in enumerate(z_values):
                for ci, val in enumerate(row):
                    try:
                        text = f"{float(val):.1f}" if val is not None else ""
                    except (TypeError, ValueError):
                        text = str(val)
                    annotations.append(dict(
                        x=col_labels[ci],
                        y=row_labels[ri],
                        text=text,
                        font=dict(size=10, color="white"),
                        showarrow=False,
                    ))

        fig = go.Figure(
            data=go.Heatmap(
                z=z_values,
                x=col_labels,
                y=row_labels,
                colorscale=[
                    [0.0, "#d8f3ee"],
                    [0.5, "#0f9d8d"],
                    [1.0, "#063d36"],
                ],
                colorbar=dict(title=colorbar_title, tickfont=dict(size=11)),
                hovertemplate="<b>%{y}</b><br>%{x}: %{z:.2f}<extra></extra>",
            )
        )
        fig.update_layout(
            title=dict(text=chart_title, x=0.5, font=dict(size=16)),
            font=dict(family="Space Grotesk, Avenir Next, Segoe UI, sans-serif", size=13),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=120, r=30, t=60, b=60),
            annotations=annotations,
        )
        return fig

    # ── RADAR ─────────────────────────────────────────────────────────────

    def _radar(
        self,
        df: pd.DataFrame,
        mapped_metrics: list[str],
        metric_to_cols: dict[str, list[str]],
        title: str,
    ) -> list[str]:
        """
        One Scatterpolar trace per team/player, each with a distinct color and
        a semi-transparent fill.  All axes are normalized 0–100 so metrics with
        very different scales are visually comparable.
        """
        valid = [
            (m, metric_to_cols[m])
            for m in mapped_metrics
            if metric_to_cols.get(m)
        ]
        if not valid:
            raise ValueError(
                "Radar chart requires at least one valid metric column."
            )

        metric_labels = [self._clean_col_label(cols[0]) for m, cols in valid]
        entity_col = next(
            (c for c in ["team", "player"] if c in df.columns), None
        )
        entities = sorted(df[entity_col].unique().tolist()) if entity_col else [None]

        # Compute mean value per entity × metric
        entity_values: dict = {}
        for entity in entities:
            subset = df[df[entity_col] == entity] if entity_col else df
            vals = []
            for _, cols in valid:
                col_vals = subset[cols[0]] if cols[0] in subset.columns else pd.Series([0])
                vals.append(float(col_vals.mean()))
            entity_values[entity] = vals

        # Normalize each metric to 0–100 across all entities
        n_metrics = len(valid)
        all_vals_per_metric = [
            [entity_values[e][mi] for e in entities]
            for mi in range(n_metrics)
        ]
        min_per_metric = [min(v) for v in all_vals_per_metric]
        max_per_metric = [
            max(v) if max(v) != min(v) else max(v) + 1
            for v in all_vals_per_metric
        ]

        fig = go.Figure()

        for ei, entity in enumerate(entities):
            raw = entity_values[entity]
            normalized = [
                100 * (raw[mi] - min_per_metric[mi]) / (max_per_metric[mi] - min_per_metric[mi])
                for mi in range(n_metrics)
            ]
            # Close the polygon
            labels_closed  = metric_labels + [metric_labels[0]]
            values_closed  = normalized + [normalized[0]]

            color = self._entity_color(ei)
            fill_color = self._entity_color_alpha(ei)

            hover_text = [
                f"{metric_labels[mi]}: {entity_values[entity][mi]:.2f} (norm {normalized[mi]:.0f}/100)"
                for mi in range(n_metrics)
            ] + [f"{metric_labels[0]}: {entity_values[entity][0]:.2f}"]

            fig.add_trace(
                go.Scatterpolar(
                    r=values_closed,
                    theta=labels_closed,
                    fill="toself",
                    fillcolor=fill_color,
                    line=dict(color=color, width=2.5),
                    name=str(entity) if entity else title,
                    text=hover_text,
                    hovertemplate="<b>%{theta}</b><br>%{text}<extra></extra>",
                )
            )

        fig.update_layout(
            polar=dict(
                radialaxis=dict(
                    visible=True,
                    range=[0, 110],
                    tickfont=dict(size=10),
                    gridcolor="#d8e6eb",
                    linecolor="#d8e6eb",
                ),
                angularaxis=dict(
                    tickfont=dict(size=12),
                    linecolor="#d8e6eb",
                ),
                bgcolor="rgba(248,252,253,1)",
            ),
            showlegend=len(entities) > 1,
            legend=dict(
                bgcolor="rgba(255,255,255,0.85)",
                bordercolor="#d8e6eb",
                borderwidth=1,
            ),
            title=dict(text=title, x=0.5, font=dict(size=16)),
            font=dict(family="Space Grotesk, Avenir Next, Segoe UI, sans-serif", size=13),
            paper_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=50, r=50, t=70, b=50),
        )
        return [pio.to_json(fig)]

    # ── TABLE ─────────────────────────────────────────────────────────────

    def _table(
        self,
        df: pd.DataFrame,
        mapped_metrics: list[str],
        metric_to_cols: dict[str, list[str]],
        title: str,
    ) -> list[str]:
        """
        Clean data table with accent-colored headers, alternating row shading,
        and human-readable column labels (MultiIndex prefixes stripped).
        """
        cols_to_display: list[str] = []
        for metric in mapped_metrics:
            cols_to_display.extend(metric_to_cols.get(metric, []))
        cols_to_display = [c for c in dict.fromkeys(cols_to_display) if c in df.columns]

        # Fallback: show all numeric columns when metric matching found nothing
        if not cols_to_display:
            cols_to_display = df.select_dtypes(include="number").columns.tolist()

        # Prepend identity columns
        for id_col in reversed(["season", "team", "player"]):
            if id_col in df.columns and id_col not in cols_to_display:
                cols_to_display.insert(0, id_col)

        if not cols_to_display:
            raise ValueError("No displayable columns found in DataFrame.")

        df_display = df[cols_to_display].copy()

        # Sort by the first matched metric column so rankings are immediately
        # readable, then apply any top_n limit from the parsed query.
        sort_candidates = [c for c in cols_to_display if c not in ("season", "team", "player")]
        if sort_candidates and pd.api.types.is_numeric_dtype(df_display[sort_candidates[0]]):
            df_display = df_display.sort_values(
                sort_candidates[0], ascending=self.top_n_ascending
            )

        # Slice to top_n rows if requested ("top 10 scorers", "worst 5 teams", …)
        if self.top_n:
            df_display = df_display.head(self.top_n)

        df_display = df_display.reset_index(drop=True)
        display_headers = [self._clean_col_label(col) for col in cols_to_display]

        # Format numeric cells to 2 dp; keep strings as-is
        cell_values = []
        for col in cols_to_display:
            series = df_display[col]
            if pd.api.types.is_numeric_dtype(series):
                cell_values.append(series.map(lambda v: f"{v:.2f}" if pd.notna(v) else "—").tolist())
            else:
                cell_values.append(series.astype(str).tolist())

        n_rows = len(df_display)
        # Alternating row fill: even rows slightly tinted
        fill_colors = [
            [_ROW_A if r % 2 == 0 else _ROW_B for r in range(n_rows)]
            for _ in cols_to_display
        ]

        fig = go.Figure(
            data=[
                go.Table(
                    header=dict(
                        values=[f"<b>{h}</b>" for h in display_headers],
                        fill_color=_HEADER_COLOR,
                        align="center",
                        font=dict(color=_HEADER_FONT, size=13, family="Space Grotesk, sans-serif"),
                        height=36,
                        line_color="rgba(255,255,255,0.3)",
                    ),
                    cells=dict(
                        values=cell_values,
                        fill_color=fill_colors,
                        align="center",
                        font=dict(color="#102532", size=12, family="Space Grotesk, sans-serif"),
                        height=30,
                        line_color="#e8f0f3",
                    ),
                )
            ]
        )
        fig.update_layout(
            title=dict(text=title, x=0.5, font=dict(size=16)),
            font=dict(family="Space Grotesk, Avenir Next, Segoe UI, sans-serif", size=13),
            paper_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=20, r=20, t=55, b=20),
        )
        return [pio.to_json(fig)]
