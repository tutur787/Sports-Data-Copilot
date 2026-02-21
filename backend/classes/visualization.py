import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio

import backend.mappings.fbref_mapping as fbm


class Visualization:
    def __init__(self, parsed: dict):
        """
        Initialize visualization context from parsed query fields.
        """
        self.parsed = parsed
        self.team = parsed.get("team")
        self.league = parsed.get("league") or "ENG-Premier League"
        self.metric = parsed.get("metric")
        self.player = parsed.get("player")
        self.stat_type = parsed.get("stat_type") or "standard"

    def create_graph(self, df: pd.DataFrame):
        """
        Creates a graph based on the parsed chart_type and metric(s).
        Supported chart types: bar, line, scatter, pie, table, heatmap, radar
        """
        chart_type = (self.parsed.get("chart_type") or "table").lower()
        print(f"Creating chart of type: {self.parsed.get('chart_type')}")

        metrics = self.metric if isinstance(self.metric, list) else [self.metric]
        metrics = [m for m in metrics if m]
        if not metrics:
            metrics = ["all"]

        mapped_metrics = [fbm.get_fbref_metric(metric) or metric for metric in metrics]
        title = f"{self.team or self.player or self.league} - {self.stat_type.capitalize()} Stats"

        if df is None or df.empty:
            raise ValueError("DataFrame is empty or None — cannot create a graph.")

        # Flatten MultiIndex columns if present
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = ["_".join([str(c) for c in col if c]) for col in df.columns]

        # Helper: map metrics to matching df columns (case-insensitive, contains)
        def map_metrics_to_columns(metric_keys, columns):
            mapped = {}
            for metric in metric_keys:
                metric_lower = metric.lower().strip()
                matched_cols = []
                for col in columns:
                    tokens = [t.lower() for t in col.split("_")]
                    if metric_lower in tokens:  # only match full token
                        matched_cols.append(col)
                mapped[metric] = matched_cols
            return mapped

        metric_to_cols = map_metrics_to_columns(mapped_metrics, df.columns)
        print(f"Metric to columns mapping: {metric_to_cols}")

        figs = []

        # --- BAR CHART ---
        if chart_type == "bar":
            mapped_metrics = list(dict.fromkeys(mapped_metrics))
            print(f"Mapped metrics for bar chart: {mapped_metrics}")
            multiple_teams = isinstance(self.team, list) and len(self.team) > 1
            for metric in mapped_metrics:
                cols_to_use = metric_to_cols.get(metric, [])
                print(f"Columns to use for metric '{metric}': {cols_to_use}")
                print(multiple_teams)
                if not cols_to_use:
                    continue
                if multiple_teams and len(cols_to_use) == 1:
                    metric_col = cols_to_use[0]
                    pie_data = df.groupby("team")[metric_col].sum()
                    fig = px.pie(names=pie_data.index, values=pie_data.values, title=f"{title} — {metric} Comparison")
                    figs.append(fig)
                    continue
                # Split into percentage and absolute columns
                percent_cols = [col for col in cols_to_use if "%" in col]
                abs_cols = [col for col in cols_to_use if "%" not in col]
                # Plot absolute columns if more than one
                if len(abs_cols) > 1:
                    if "team" in df.columns:
                        df_plot_abs = df[["team"] + abs_cols]
                    else:
                        df_plot_abs = df[abs_cols].assign(team=self.team if not isinstance(self.team, list) else None)
                    df_melted_abs = df_plot_abs.melt(id_vars="team", var_name="metric", value_name="value")
                    if multiple_teams and "team" in df_melted_abs.columns:
                        fig_abs = px.bar(
                            df_melted_abs,
                            x="metric",
                            y="value",
                            color="team",
                            barmode="group",
                            title=f"{title} — {metric} (Absolute)",
                        )
                    else:
                        fig_abs = px.bar(
                            df_melted_abs,
                            x="metric",
                            y="value",
                            color="metric",
                            title=f"{title} — {metric} (Absolute)",
                            barmode="group",
                        )
                    figs.append(fig_abs)
                # Plot percentage columns if more than one
                if len(percent_cols) > 1:
                    if "team" in df.columns:
                        df_plot_pct = df[["team"] + percent_cols]
                    else:
                        df_plot_pct = df[percent_cols].assign(team=self.team if not isinstance(self.team, list) else None)
                    df_melted_pct = df_plot_pct.melt(id_vars="team", var_name="metric", value_name="value")
                    if multiple_teams and "team" in df_melted_pct.columns:
                        fig_pct = px.bar(
                            df_melted_pct,
                            x="metric",
                            y="value",
                            color="team",
                            barmode="group",
                            title=f"{title} — {metric} (Percentage)",
                        )
                    else:
                        fig_pct = px.bar(
                            df_melted_pct,
                            x="metric",
                            y="value",
                            color="metric",
                            title=f"{title} — {metric} (Percentage)",
                            barmode="group",
                        )
                    figs.append(fig_pct)
            if not figs:
                raise ValueError("No matching metric columns found in DataFrame or no metric with multiple columns for bar chart.")
            return [pio.to_json(fig) for fig in figs]

        # --- LINE CHART ---
        elif chart_type == "line":
            dash_styles = ["solid", "dash", "dot", "dashdot"]
            mapped_metrics = list(dict.fromkeys(mapped_metrics))
            print(f"Mapped metrics for line chart: {mapped_metrics}")
            for metric in mapped_metrics:
                cols_to_use = metric_to_cols.get(metric, [])
                if not cols_to_use:
                    continue
                fig = go.Figure()
                multiple_teams = isinstance(self.team, list) or ("team" in df.columns)
                for i, col in enumerate(cols_to_use):
                    dash = dash_styles[i % len(dash_styles)]
                    name = col
                    if multiple_teams and "team" in df.columns:
                        teams = df["team"].unique()
                        for team in teams:
                            team_df = df[df["team"] == team]
                            fig.add_trace(
                                go.Scatter(
                                    x=team_df["season"] if "season" in team_df.columns else team_df.index,
                                    y=team_df[col],
                                    mode="lines",
                                    name=f"{team} - {name}",
                                    line=dict(dash=dash),
                                )
                            )
                    else:
                        fig.add_trace(
                            go.Scatter(
                                x=df["season"] if "season" in df.columns else df.index,
                                y=df[col],
                                mode="lines",
                                name=name,
                                line=dict(dash=dash),
                            )
                        )
                fig.update_layout(title=f"{title} — {metric}", xaxis_title="Season", yaxis_title=metric)
                figs.append(fig)
            if not figs:
                raise ValueError("No matching metric columns found in DataFrame.")
            return [pio.to_json(fig) for fig in figs]

        # --- SCATTER ---
        elif chart_type == "scatter":
            if len(mapped_metrics) < 2:
                raise ValueError("Scatter plot requires at least two numeric metrics.")
            x_cols = metric_to_cols.get(mapped_metrics[0], [])
            y_cols = metric_to_cols.get(mapped_metrics[1], [])
            if not x_cols or not y_cols:
                raise ValueError("Scatter plot requires at least two numeric metrics with matching columns.")
            fig = px.scatter(df, x=x_cols[0], y=y_cols[0], title=title)
            return pio.to_json(fig)

        # --- PIE ---
        elif chart_type == "pie":
            metric = mapped_metrics[0]
            cols = metric_to_cols.get(metric, [])
            if not cols:
                raise ValueError(f"Metric '{metric}' not found in DataFrame.")
            metric_col = cols[0]
            group_key = self.team or self.player or df.index
            if group_key == df.index:
                pie_data = df[metric_col].groupby(df.index).sum()
                labels = pie_data.index.astype(str)
                values = pie_data.values
            else:
                pie_data = df.groupby(group_key)[metric_col].sum()
                labels = pie_data.index.astype(str)
                values = pie_data.values
            fig = px.pie(names=labels, values=values, title=title)
            return pio.to_json(fig)

        # --- HEATMAP ---
        elif chart_type == "heatmap":
            corr = df.corr(numeric_only=True)
            fig = go.Figure(
                data=go.Heatmap(
                    z=corr.values,
                    x=corr.columns,
                    y=corr.index,
                    colorscale="RdBu",
                    zmid=0,
                    colorbar=dict(title="Correlation"),
                )
            )
            fig.update_layout(title=f"Correlation Heatmap - {title}")
            return pio.to_json(fig)

        # --- RADAR ---
        elif chart_type == "radar":
            # Check all metrics have matching columns
            for metric in mapped_metrics:
                if not metric_to_cols.get(metric):
                    raise ValueError("Radar chart requires valid numeric metrics in the DataFrame.")

            # For radar, take mean of all matching columns per metric and average them
            values = []
            for metric in mapped_metrics:
                cols = metric_to_cols.get(metric, [])
                if cols:
                    values.append(df[cols].mean(axis=1).mean())
                else:
                    values.append(0)
            values += values[:1]
            angles = metrics + [metrics[0]]

            fig = go.Figure(
                data=go.Scatterpolar(
                    r=values,
                    theta=angles,
                    fill="toself",
                    name=title,
                )
            )
            fig.update_layout(
                polar=dict(
                    radialaxis=dict(
                        visible=True,
                        range=[0, max(values) * 1.1],
                    )
                ),
                showlegend=False,
                title=title,
            )
            return pio.to_json(fig)

        elif chart_type == "table":
            mapped_metrics = list(dict.fromkeys(mapped_metrics))
            print(f"Mapped metrics for table chart: {mapped_metrics}")
            cols_to_display = []
            for metric in mapped_metrics:
                cols = metric_to_cols.get(metric, [])
                cols_to_display.extend(cols)
            cols_to_display = [c for c in dict.fromkeys(cols_to_display) if c in df.columns]

            for id_col in ["season", "team", "player"]:
                if id_col in df.columns and id_col not in cols_to_display:
                    cols_to_display.insert(0, id_col)

            if not cols_to_display:
                raise ValueError("No valid metric columns found for table display.")

            display_headers = [col.split("_")[-1] for col in cols_to_display]
            df_display = df[cols_to_display].copy().reset_index(drop=True)

            # Convert all cell values to lists for safe serialization
            cell_values = [df_display[col].astype(str).tolist() for col in cols_to_display]

            fig = go.Figure(
                data=[
                    go.Table(
                        header=dict(
                            values=display_headers,
                            fill_color="lightblue",
                            align="center",
                            font=dict(color="black", size=13),
                        ),
                        cells=dict(
                            values=cell_values,
                            fill_color="white",
                            align="center",
                            font=dict(color="black", size=12),
                        ),
                    )
                ]
            )
            fig.update_layout(
                title=dict(text=title, x=0.5),
                margin=dict(l=20, r=20, t=40, b=20),
            )
            return [pio.to_json(fig, pretty=False)]

        # --- TABLE (DEFAULT) ---
        else:
            print("⚠️ Unsupported chart type — showing data preview instead.")
            print(df.head())
            return None
