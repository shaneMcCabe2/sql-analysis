"""
SQL on Stack Overflow — interactive dashboard
Data: ~299k SQL-family questions, 2020-2022, BigQuery public dataset
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from google.cloud import bigquery
from google.oauth2 import service_account

# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="SQL on Stack Overflow",
    page_icon="🗄️",
    layout="wide",
)

PROJECT = "sql-analysis-500017"
MARTS   = f"`{PROJECT}`.`dbt_dev_marts`"

# ── BigQuery client ───────────────────────────────────────────────────────────

@st.cache_resource
def get_client() -> bigquery.Client:
    try:
        creds = service_account.Credentials.from_service_account_info(
            st.secrets["gcp_service_account"],
            scopes=["https://www.googleapis.com/auth/cloud-platform"],
        )
        return bigquery.Client(credentials=creds, project=PROJECT)
    except (KeyError, FileNotFoundError):
        # local dev: uses GOOGLE_APPLICATION_CREDENTIALS env var via ADC
        return bigquery.Client(project=PROJECT)


def run(sql: str) -> pd.DataFrame:
    return get_client().query(sql).to_dataframe()

# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("Filters")
    years = st.multiselect(
        "Year",
        options=[2020, 2021, 2022],
        default=[2020, 2021, 2022],
    )
    if not years:
        st.warning("Select at least one year.")
        st.stop()

    min_tag_volume = st.slider(
        "Min. questions per tag (answer-rate view)",
        min_value=100, max_value=2000, value=500, step=100,
    )

    top_n = st.slider("Top N tags (trend view)", min_value=5, max_value=20, value=10)

    st.divider()
    st.caption(
        "Source: `bigquery-public-data.stackoverflow` — frozen snapshot, "
        "ends 2022-09-25. Scope: SQL-family tags."
    )

year_list = ", ".join(str(y) for y in sorted(years))

# ── Data loaders (all cached) ─────────────────────────────────────────────────

@st.cache_data(ttl=3600, show_spinner="Loading KPIs…")
def load_kpis(yl: str) -> pd.Series:
    df = run(f"""
        SELECT
            SUM(num_questions)                                          AS total_questions,
            ROUND(SAFE_DIVIDE(SUM(num_answered), SUM(num_questions)), 4) AS pct_answered,
            ROUND(SAFE_DIVIDE(SUM(num_accepted), SUM(num_questions)), 4) AS pct_accepted,
            SUM(total_views)                                            AS total_views
        FROM {MARTS}.fct_tag_yearly
        WHERE creation_year IN ({yl})
    """)
    return df.iloc[0]


@st.cache_data(ttl=3600, show_spinner=False)
def load_top_tags(yl: str, n: int) -> pd.DataFrame:
    return run(f"""
        WITH top AS (
            SELECT tag, SUM(num_questions) AS total
            FROM {MARTS}.fct_tag_yearly
            WHERE creation_year IN ({yl})
            GROUP BY tag ORDER BY total DESC LIMIT {n}
        )
        SELECT f.tag, f.creation_year, f.num_questions
        FROM {MARTS}.fct_tag_yearly AS f
        JOIN top USING (tag)
        WHERE f.creation_year IN ({yl})
        ORDER BY f.tag, f.creation_year
    """)


@st.cache_data(ttl=3600, show_spinner=False)
def load_monthly(yl: str) -> pd.DataFrame:
    return run(f"""
        SELECT
            DATE_TRUNC(DATE(creation_date), MONTH)                          AS month,
            COUNT(*)                                                        AS num_questions,
            ROUND(SAFE_DIVIDE(COUNTIF(has_accepted_answer), COUNT(*)), 4)   AS pct_accepted
        FROM {MARTS}.dim_questions
        WHERE EXTRACT(YEAR FROM creation_date) IN ({yl})
        GROUP BY month ORDER BY month
    """)


@st.cache_data(ttl=3600, show_spinner=False)
def load_rising_falling() -> pd.DataFrame:
    return run(f"""
        WITH y2020 AS (
            SELECT tag, num_questions AS q_2020
            FROM {MARTS}.fct_tag_yearly WHERE creation_year = 2020
        ),
        y2022 AS (
            SELECT tag, num_questions AS q_2022
            FROM {MARTS}.fct_tag_yearly WHERE creation_year = 2022
        )
        SELECT tag, q_2020, q_2022,
            ROUND(SAFE_DIVIDE(q_2022 - q_2020, q_2020), 4) AS growth_rate
        FROM y2020 JOIN y2022 USING (tag)
        WHERE q_2020 >= 200 AND q_2022 >= 200
        ORDER BY growth_rate DESC
    """)


@st.cache_data(ttl=3600, show_spinner=False)
def load_answer_rates(yl: str, min_q: int) -> pd.DataFrame:
    return run(f"""
        SELECT
            tag,
            SUM(num_questions)                                              AS total_questions,
            ROUND(SAFE_DIVIDE(SUM(num_answered), SUM(num_questions)), 4)    AS pct_answered,
            ROUND(SAFE_DIVIDE(SUM(num_accepted), SUM(num_questions)), 4)    AS pct_accepted,
            ROUND(AVG(avg_score), 2)                                        AS avg_score
        FROM {MARTS}.fct_tag_yearly
        WHERE creation_year IN ({yl})
        GROUP BY tag
        HAVING SUM(num_questions) >= {min_q}
        ORDER BY pct_answered DESC
    """)


@st.cache_data(ttl=3600, show_spinner=False)
def load_time_to_answer(yl: str) -> pd.DataFrame:
    return run(f"""
        SELECT
            CASE
                WHEN hours_to_first_answer < 1   THEN '1. < 1 hour'
                WHEN hours_to_first_answer < 6   THEN '2. 1–6 hours'
                WHEN hours_to_first_answer < 24  THEN '3. 6–24 hours'
                WHEN hours_to_first_answer < 72  THEN '4. 1–3 days'
                WHEN hours_to_first_answer < 168 THEN '5. 3–7 days'
                ELSE                                  '6. > 7 days'
            END AS tier,
            COUNT(*) AS num_questions
        FROM {MARTS}.dim_questions
        WHERE is_answered AND hours_to_first_answer IS NOT NULL
            AND EXTRACT(YEAR FROM creation_date) IN ({yl})
        GROUP BY tier ORDER BY tier
    """)


@st.cache_data(ttl=86400, show_spinner=False)
def load_error_patterns() -> pd.DataFrame:
    return run(f"SELECT * FROM {MARTS}.analysis_error_patterns ORDER BY num_questions DESC")


@st.cache_data(ttl=86400, show_spinner=False)
def load_keyword_freq() -> pd.DataFrame:
    return run(f"SELECT * FROM {MARTS}.analysis_keyword_frequency ORDER BY in_accepted_answers DESC")

# ── Fetch data ────────────────────────────────────────────────────────────────

kpis      = load_kpis(year_list)
top_tags  = load_top_tags(year_list, top_n)
monthly   = load_monthly(year_list)
risfal    = load_rising_falling()
ans_rates = load_answer_rates(year_list, min_tag_volume)
tta       = load_time_to_answer(year_list)
errors    = load_error_patterns()
keywords  = load_keyword_freq()

# ── Header ────────────────────────────────────────────────────────────────────

st.title("SQL on Stack Overflow")
st.caption(
    "299k SQL-family questions · 322k answers · 2020–2022 · "
    "Source: BigQuery public dataset (`bigquery-public-data.stackoverflow`)"
)

# ── KPI row ───────────────────────────────────────────────────────────────────

k1, k2, k3, k4 = st.columns(4)
k1.metric("Total questions",  f"{int(kpis['total_questions']):,}")
k2.metric("% Answered",       f"{kpis['pct_answered']:.1%}")
k3.metric("% Accepted",       f"{kpis['pct_accepted']:.1%}")
k4.metric("Total views",      f"{int(kpis['total_views']):,}")

st.divider()

# ── Tabs ──────────────────────────────────────────────────────────────────────

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📈  Tag trends",
    "⬆️  Rising & falling",
    "✅  Answer quality",
    "🚨  Error patterns",
    "🔑  SQL feature usage",
])

# ─── Tab 1 — Tag volume trend + monthly ──────────────────────────────────────

with tab1:
    st.subheader(f"Question volume — top {top_n} tags")

    fig = px.line(
        top_tags,
        x="creation_year", y="num_questions",
        color="tag", markers=True,
        labels={"num_questions": "Questions", "creation_year": "Year", "tag": "Tag"},
        color_discrete_sequence=px.colors.qualitative.Plotly,
    )
    fig.update_layout(
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        xaxis=dict(tickmode="array", tickvals=sorted(years)),
    )
    st.plotly_chart(fig, use_container_width=True)
    st.caption(
        "Every top tag declined 2020→2022 — a platform-wide SO traffic shift, not SQL-specific. "
        "See the **Rising & falling** tab for exceptions."
    )

    st.subheader("Monthly question volume")
    monthly["month"] = pd.to_datetime(monthly["month"])
    fig2 = px.area(
        monthly, x="month", y="num_questions",
        labels={"num_questions": "Questions", "month": ""},
        color_discrete_sequence=["#1f77b4"],
    )
    fig2.update_layout(xaxis_title="")
    st.plotly_chart(fig2, use_container_width=True)

# ─── Tab 2 — Rising & falling ─────────────────────────────────────────────────

with tab2:
    st.subheader("Fastest-rising and steepest-falling tags: 2020 vs 2022")
    st.caption("Minimum 200 questions in both years. Growth rate = (q_2022 − q_2020) / q_2020.")

    top10 = risfal.head(10).assign(direction="Rising")
    bot10 = risfal.tail(10).assign(direction="Falling")
    combined = pd.concat([top10, bot10]).copy()
    combined["growth_pct"] = (combined["growth_rate"] * 100).round(1)

    fig = px.bar(
        combined.sort_values("growth_rate"),
        x="growth_pct", y="tag",
        color="direction", orientation="h",
        color_discrete_map={"Rising": "#2ca02c", "Falling": "#d62728"},
        labels={"growth_pct": "Growth rate (%)", "tag": ""},
        hover_data={"q_2020": True, "q_2022": True, "growth_pct": ":.1f%", "direction": False},
        height=600,
    )
    fig.add_vline(x=0, line_dash="dash", line_color="gray")
    st.plotly_chart(fig, use_container_width=True)

    col_r, col_f = st.columns(2)
    col_r.info(
        "**Top risers:** Databricks +69%, Snowflake +51%, TypeScript ORMs +43% — "
        "the modern data stack growing against the broader SO decline."
    )
    col_f.warning(
        "**Top fallers:** `string` −79%, `count` −77%, `where-clause` −75% — "
        "SQL keyword tags collapsing as canonical answers accumulate and users find them via search."
    )

# ─── Tab 3 — Answer quality ───────────────────────────────────────────────────

with tab3:
    c_best, c_worst = st.columns(2)

    best15  = ans_rates.head(15)
    worst15 = ans_rates.tail(15)

    with c_best:
        st.subheader("Best-answered tags")
        fig = px.bar(
            best15.sort_values("pct_answered"),
            x="pct_answered", y="tag", orientation="h",
            color="pct_answered", color_continuous_scale="Greens",
            range_color=[0.8, 1.0],
            labels={"pct_answered": "% Answered", "tag": ""},
            hover_data={"total_questions": True, "pct_accepted": True, "avg_score": True},
            height=500,
        )
        fig.update_coloraxes(showscale=False)
        fig.update_layout(xaxis_tickformat=".0%")
        st.plotly_chart(fig, use_container_width=True)
        st.caption("`gaps-and-islands` (97%) and `greatest-n-per-group` (96%) — expert-magnet pattern questions.")

    with c_worst:
        st.subheader("Hardest-to-answer tags")
        fig2 = px.bar(
            worst15.sort_values("pct_answered", ascending=False),
            x="pct_answered", y="tag", orientation="h",
            color="pct_answered", color_continuous_scale="Reds_r",
            range_color=[0.4, 0.7],
            labels={"pct_answered": "% Answered", "tag": ""},
            hover_data={"total_questions": True, "pct_accepted": True, "avg_score": True},
            height=500,
        )
        fig2.update_coloraxes(showscale=False)
        fig2.update_layout(xaxis_tickformat=".0%")
        st.plotly_chart(fig2, use_container_width=True)
        st.caption("`xampp`, `odbc`, `mysql-connector` — driver/environment setup in niche stacks goes unanswered most often.")

    st.subheader("Time to first answer (answered questions only)")
    tta["label"] = tta["tier"].str[3:]  # strip leading sort prefix "1. "
    fig3 = px.bar(
        tta, x="label", y="num_questions",
        color="num_questions", color_continuous_scale="Blues",
        labels={"num_questions": "Questions", "label": ""},
        text="num_questions",
    )
    fig3.update_coloraxes(showscale=False)
    fig3.update_traces(texttemplate="%{text:,}", textposition="outside")
    st.plotly_chart(fig3, use_container_width=True)

# ─── Tab 4 — Error patterns ───────────────────────────────────────────────────

with tab4:
    st.subheader("Top SQL error patterns by question volume")
    st.caption(
        "Detected via regex on question titles + bodies (`raw.questions`). "
        "One question can match multiple patterns. Color = % accepted."
    )

    fig = px.bar(
        errors.sort_values("num_questions"),
        x="num_questions", y="error_pattern", orientation="h",
        color="pct_accepted",
        color_continuous_scale="RdYlGn",
        range_color=[0.2, 0.55],
        labels={
            "num_questions": "Questions",
            "error_pattern": "",
            "pct_accepted": "% Accepted",
        },
        hover_data={
            "avg_score": True,
            "total_upvotes": True,
            "pct_answered": True,
            "total_views": True,
        },
        height=450,
    )
    fig.update_layout(coloraxis_colorbar=dict(title="% Accepted", tickformat=".0%"))
    st.plotly_chart(fig, use_container_width=True)

    col_a, col_b = st.columns(2)
    col_a.success(
        "**Easiest to resolve:** GROUP BY / aggregate errors (50% accepted) — "
        "well-covered by SO's canonical answers."
    )
    col_b.error(
        "**Hardest to resolve:** Timeout / lock wait (28%), Permission denied (25%) — "
        "environment-specific, no universal fix."
    )

    st.dataframe(
        errors.rename(columns={
            "error_pattern": "Pattern",
            "num_questions": "Questions",
            "avg_score": "Avg score",
            "total_upvotes": "Total upvotes",
            "pct_answered": "% Answered",
            "pct_accepted": "% Accepted",
        }).set_index("Pattern"),
        use_container_width=True,
    )

# ─── Tab 5 — SQL feature usage ────────────────────────────────────────────────

with tab5:
    st.subheader("Advanced SQL keyword frequency: questions vs. accepted answers")
    st.caption(
        "Ratio > 1 → the feature appears more in *solutions* than in *questions* (a solution tool). "
        "Ratio < 1 → a struggle topic. Dashed line = equal frequency."
    )

    max_val = max(keywords["in_questions"].max(), keywords["in_accepted_answers"].max()) * 1.05

    fig = px.scatter(
        keywords,
        x="in_questions", y="in_accepted_answers",
        text="keyword",
        size="in_accepted_answers",
        color="answer_to_question_ratio",
        color_continuous_scale="RdYlGn",
        range_color=[0.2, 2.1],
        labels={
            "in_questions": "Appearances in questions",
            "in_accepted_answers": "Appearances in accepted answers",
            "answer_to_question_ratio": "Ratio",
        },
        hover_data={"answer_to_question_ratio": ":.2f"},
        height=560,
    )
    fig.update_traces(textposition="top center", marker=dict(opacity=0.8))
    fig.add_shape(
        type="line", x0=0, y0=0, x1=max_val, y1=max_val,
        line=dict(dash="dash", color="gray", width=1),
    )
    fig.add_annotation(
        x=max_val * 0.88, y=max_val * 0.78,
        text="equal frequency",
        showarrow=False, font=dict(color="gray", size=11),
    )
    fig.update_layout(
        coloraxis_colorbar=dict(title="Ratio"),
        xaxis_range=[0, max_val],
        yaxis_range=[0, max_val],
    )
    st.plotly_chart(fig, use_container_width=True)

    col_sol, col_str = st.columns(2)
    col_sol.success(
        "**Solution tools (above diagonal):** `LATERAL` 2.03×, `CROSS/OUTER APPLY` 1.99×, "
        "`ROW_NUMBER()` 1.78×, `OVER()` 1.66× — experts reach for these to solve problems."
    )
    col_str.warning(
        "**Struggle topics (below diagonal):** `MERGE` 0.26×, JSON functions 0.48×, `PIVOT` 0.80× — "
        "people ask about these more than answerers use them."
    )

    st.dataframe(
        keywords.rename(columns={
            "keyword": "Keyword",
            "in_questions": "In questions",
            "in_accepted_answers": "In accepted answers",
            "answer_to_question_ratio": "Ratio",
        }).set_index("Keyword"),
        use_container_width=True,
    )
