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
    import os
    try:
        has_secret = "gcp_service_account" in st.secrets
    except Exception:
        has_secret = False
    if has_secret:
        # Streamlit Cloud: credentials stored in secrets
        creds = service_account.Credentials.from_service_account_info(
            dict(st.secrets["gcp_service_account"]),
            scopes=["https://www.googleapis.com/auth/cloud-platform"],
        )
        return bigquery.Client(credentials=creds, project=PROJECT)
    if os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        # local dev: use service-account key file via ADC
        return bigquery.Client(project=PROJECT)
    st.error("No credentials found. Add [gcp_service_account] to Streamlit secrets or set GOOGLE_APPLICATION_CREDENTIALS locally.")
    st.stop()


def run(sql: str) -> pd.DataFrame:
    return get_client().query(sql).to_dataframe()


@st.cache_resource
def _build_anthropic_client():
    import anthropic
    # Raises if key missing — exceptions aren't cached, so this retries until the secret exists
    api_key = st.secrets["ANTHROPIC_API_KEY"]
    return anthropic.Anthropic(api_key=api_key)

def get_anthropic_client():
    try:
        return _build_anthropic_client()
    except Exception:
        return None

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
    # dim_questions has one row per unique question — no double-counting from multi-tag questions
    df = run(f"""
        SELECT
            COUNT(*)                                                            AS total_questions,
            ROUND(SAFE_DIVIDE(COUNTIF(is_answered), COUNT(*)), 4)               AS pct_answered,
            ROUND(SAFE_DIVIDE(COUNTIF(has_accepted_answer), COUNT(*)), 4)       AS pct_accepted,
            SUM(view_count)                                                     AS total_views
        FROM {MARTS}.dim_questions
        WHERE EXTRACT(YEAR FROM creation_date) IN ({yl})
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


@st.cache_data(ttl=86400, show_spinner=False)
def load_dialect_frequency() -> pd.DataFrame:
    return run(f"""
        SELECT dialect, creation_year, num_questions, pct_answered, pct_accepted,
               avg_score, total_views, avg_views
        FROM {MARTS}.analysis_dialect_frequency
        ORDER BY dialect, creation_year
    """)


@st.cache_data(ttl=86400, show_spinner=False)
def load_complexity_by_tier(yl: str) -> pd.DataFrame:
    return run(f"""
        SELECT
            complexity_tier,
            COUNT(*)                                                            AS num_questions,
            ROUND(SAFE_DIVIDE(COUNTIF(is_answered),       COUNT(*)), 4)        AS pct_answered,
            ROUND(SAFE_DIVIDE(COUNTIF(has_accepted_answer), COUNT(*)), 4)      AS pct_accepted,
            ROUND(AVG(score), 2)                                               AS avg_score,
            ROUND(AVG(complexity_score), 1)                                    AS avg_complexity_score,
            SUM(view_count)                                                     AS total_views
        FROM {MARTS}.analysis_complexity_scores
        WHERE creation_year IN ({yl})
        GROUP BY complexity_tier
        ORDER BY complexity_tier
    """)


@st.cache_data(ttl=3600, show_spinner="Sampling practice questions…")
def load_practice_pool(tier: str) -> pd.DataFrame:
    safe_tier = tier.replace("'", "")
    return run(f"""
        SELECT
            q.question_id,
            q.title,
            q.score,
            q.view_count,
            ARRAY_TO_STRING(q.tags, ', ')  AS tags_str,
            c.complexity_score,
            c.complexity_tier,
            c.f_join, c.f_group_by, c.f_aggregate, c.f_having,
            c.f_case_when, c.f_set_ops, c.f_subqueries,
            c.f_cte, c.f_window, c.f_recursive, c.f_lateral,
            c.f_apply, c.f_pivot
        FROM {MARTS}.dim_questions AS q
        JOIN {MARTS}.analysis_complexity_scores AS c USING (question_id)
        WHERE c.complexity_tier = '{safe_tier}'
          AND c.complexity_score > 0
        ORDER BY RAND()
        LIMIT 50
    """)


@st.cache_data(ttl=86400, show_spinner=False)
def load_complexity_features() -> pd.DataFrame:
    return run(f"""
        SELECT
            ROUND(100 * SAFE_DIVIDE(SUM(f_select),     COUNT(*)), 1) AS select_pct,
            ROUND(100 * SAFE_DIVIDE(SUM(f_where),      COUNT(*)), 1) AS where_pct,
            ROUND(100 * SAFE_DIVIDE(SUM(f_order_by),   COUNT(*)), 1) AS order_by_pct,
            ROUND(100 * SAFE_DIVIDE(SUM(f_insert),     COUNT(*)), 1) AS insert_pct,
            ROUND(100 * SAFE_DIVIDE(SUM(f_update),     COUNT(*)), 1) AS update_pct,
            ROUND(100 * SAFE_DIVIDE(SUM(f_delete),     COUNT(*)), 1) AS delete_pct,
            ROUND(100 * SAFE_DIVIDE(SUM(f_create),     COUNT(*)), 1) AS create_pct,
            ROUND(100 * SAFE_DIVIDE(SUM(f_alter),      COUNT(*)), 1) AS alter_pct,
            ROUND(100 * SAFE_DIVIDE(SUM(f_drop),       COUNT(*)), 1) AS drop_pct,
            ROUND(100 * SAFE_DIVIDE(SUM(f_join),       COUNT(*)), 1) AS join_pct,
            ROUND(100 * SAFE_DIVIDE(SUM(f_group_by),   COUNT(*)), 1) AS group_by_pct,
            ROUND(100 * SAFE_DIVIDE(SUM(f_aggregate),  COUNT(*)), 1) AS aggregate_pct,
            ROUND(100 * SAFE_DIVIDE(SUM(f_having),     COUNT(*)), 1) AS having_pct,
            ROUND(100 * SAFE_DIVIDE(SUM(f_case_when),  COUNT(*)), 1) AS case_when_pct,
            ROUND(100 * SAFE_DIVIDE(SUM(f_set_ops),    COUNT(*)), 1) AS set_ops_pct,
            ROUND(100 * SAFE_DIVIDE(SUM(f_subqueries), COUNT(*)), 1) AS subqueries_pct,
            ROUND(100 * SAFE_DIVIDE(SUM(f_cte),        COUNT(*)), 1) AS cte_pct,
            ROUND(100 * SAFE_DIVIDE(SUM(f_window),     COUNT(*)), 1) AS window_pct,
            ROUND(100 * SAFE_DIVIDE(SUM(f_recursive),  COUNT(*)), 1) AS recursive_pct,
            ROUND(100 * SAFE_DIVIDE(SUM(f_lateral),    COUNT(*)), 1) AS lateral_pct,
            ROUND(100 * SAFE_DIVIDE(SUM(f_apply),      COUNT(*)), 1) AS apply_pct,
            ROUND(100 * SAFE_DIVIDE(SUM(f_pivot),      COUNT(*)), 1) AS pivot_pct
        FROM {MARTS}.analysis_complexity_scores
    """)

# ── Fetch data ────────────────────────────────────────────────────────────────

kpis      = load_kpis(year_list)
top_tags  = load_top_tags(year_list, top_n)
monthly   = load_monthly(year_list)
risfal    = load_rising_falling()
ans_rates = load_answer_rates(year_list, min_tag_volume)
tta       = load_time_to_answer(year_list)
errors    = load_error_patterns()
keywords  = load_keyword_freq()
dialects  = load_dialect_frequency()
cx_tiers  = load_complexity_by_tier(year_list)
cx_feats  = load_complexity_features()

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

tab0, tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9 = st.tabs([
    "📋  Summary",
    "📈  Tag trends",
    "⬆️  Rising & falling",
    "✅  Answer quality",
    "🚨  Error patterns",
    "🔑  SQL feature usage",
    "🗄️  Dialect breakdown",
    "🔢  Complexity",
    "🔍  Validation",
    "🎯  Practice",
])

# ─── Tab 0 — Summary & key takeaways ─────────────────────────────────────────

with tab0:
    st.subheader("About this project")
    st.markdown(
        """
        This dashboard analyses **~299k SQL-tagged Stack Overflow questions** from 2020–2022,
        built end-to-end on Google Cloud — and closes the loop with an AI-powered practice tool:

        `BigQuery public dataset` → `Python ingestion` → `dbt staging + marts` → `Streamlit` → `Claude API`

        The goal is to surface what's actually happening in the SQL ecosystem — which dialects
        are growing, which questions go unanswered, and how advanced SQL features appear in
        practice versus as pain points — then turn those insights into targeted practice exercises.
        """
    )

    st.info(
        "**🎯 Try the Practice Questions tab** — real Stack Overflow scenarios, complexity-scored "
        "by the analysis pipeline, then synthesised into interactive SQL exercises by Claude "
        "(`claude-sonnet-4-6`). Select a difficulty tier, attempt the task, and reveal the answer."
    )

    st.divider()
    st.subheader("Key takeaways")

    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown("#### 📉 Platform trend")
        st.info(
            "**Every major SQL tag declined in question volume 2020→2022.** "
            "This is a platform-wide Stack Overflow shift — users increasingly find answers "
            "via search rather than asking new questions. `sql` alone accounts for 127k questions, "
            "2.5× the size of `mysql` at #2."
        )

        st.markdown("#### ⬆️ The modern data stack is growing")
        st.success(
            "Against the overall decline, **Databricks (+69%), Snowflake (+51%), and TypeScript ORMs (+43%)** "
            "all grew from 2020 to 2022. These tags signal where hiring and adoption were accelerating "
            "in the data space during this period."
        )

        st.markdown("#### 🏆 Pattern questions attract experts")
        st.success(
            "**`gaps-and-islands` (97% answered) and `greatest-n-per-group` (96%)** are the "
            "best-served niches on Stack Overflow. Well-defined algorithmic challenges reliably "
            "draw expert answerers — a stark contrast to environment-specific setup questions."
        )

    with col_b:
        st.markdown("#### 🔑 Window functions: the universal solution tool")
        st.info(
            "`OVER()` appears **1.66× more often in accepted answers than in questions**, "
            "`LATERAL` and `CROSS/OUTER APPLY` exceed **2×**. "
            "These features are expert reach-for tools — people struggle with ranking and pivoting, "
            "and window functions consistently solve it."
        )

        st.markdown("#### 🚨 Hardest errors to resolve")
        st.warning(
            "**Timeout / lock wait (28% accepted) and Permission denied (25%)** are the graveyard "
            "of SQL Stack Overflow — environment-specific, no universal fix. Compare to "
            "GROUP BY / aggregate errors at 50% accepted, where canonical answers exist."
        )

        st.markdown("#### 📦 MERGE and JSON: struggle topics")
        st.warning(
            "**`MERGE` (0.26×) and JSON functions (0.48×)** appear far more in questions than "
            "in accepted answers — people ask about them but they rarely appear as solutions. "
            "They're pain points, not tools experts reach for."
        )

    st.divider()
    st.subheader("Pipeline architecture")
    st.code(
        """\
bigquery-public-data.stackoverflow   (frozen public snapshot, ends 2022-09-25)
        │
        │  sql/transfer/*.sql  ·  ingest/transfer.py
        ▼
raw dataset  ·  ~91 GB scanned  ·  299k questions · 322k answers · 1.06M comments
        │
        │  dbt staging layer  (typed views, tag array parsing, FK tests)
        ▼
dbt_dev_staging.*  ·  stg_questions · stg_answers · stg_users · stg_comments · stg_tags
        │
        │  dbt marts layer  (dimensional modelling, partitioning, pre-aggregation)
        ▼
dbt_dev_marts.*  ·  dim_questions · fct_tag_yearly · analysis_complexity_scores
                    analysis_dialect_frequency · analysis_error_patterns · analysis_keyword_frequency
        │
        │  Streamlit  ·  live BigQuery queries, cached per session
        ▼
9 analysis tabs  (tag trends · dialect · complexity · errors · feature usage · …)
        │
        │  Claude API  (claude-sonnet-4-6)  ·  grounded in complexity scores + SO question metadata
        ▼
🎯  Practice Questions  ·  AI-synthesised SQL exercises from real Stack Overflow scenarios
""",
        language="text",
    )

    st.divider()
    st.subheader("Explore the data")
    st.markdown(
        """
        | Tab | Question it answers |
        |---|---|
        | 📈 Tag trends | Which SQL tags dominate, and how did volume change year-over-year? |
        | ⬆️ Rising & falling | Which tags bucked the decline, and which collapsed fastest? |
        | ✅ Answer quality | Which tags get their questions resolved — and which don't? |
        | 🚨 Error patterns | What are the most common SQL mistakes by volume and upvote signal? |
        | 🔑 SQL feature usage | Which advanced features appear in solutions vs. struggle topics? |
        | 🗄️ Dialect breakdown | How does MySQL, PostgreSQL, SQL Server etc. compare by volume and answer rate? |
        | 🔢 Complexity | How complex are the questions, and does complexity predict whether they get answered? |
        | 🎯 Practice | AI-generated SQL exercises grounded in real SO scenarios — powered by Claude API |
        """
    )

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

# ─── Tab 6 — Dialect breakdown ────────────────────────────────────────────────

with tab6:
    st.subheader("SQL dialect question volume (2020–2022)")
    st.caption(
        "Tags mapped to 12 named dialect families. A question can count toward multiple dialects. "
        "Filtered by the year selector in the sidebar."
    )

    dial_filt = dialects[dialects["creation_year"].isin(years)]

    # Grouped bar: question volume by dialect × year
    dial_total = (
        dial_filt.groupby("dialect")["num_questions"].sum()
        .reset_index()
        .sort_values("num_questions", ascending=False)
    )
    top_dialects = dial_total["dialect"].tolist()

    fig = px.bar(
        dial_filt[dial_filt["dialect"].isin(top_dialects)].sort_values(
            "num_questions", ascending=False
        ),
        x="dialect", y="num_questions", color="creation_year",
        barmode="group",
        color_discrete_sequence=px.colors.qualitative.Set2,
        labels={"num_questions": "Questions", "dialect": "", "creation_year": "Year"},
        category_orders={"dialect": top_dialects},
        height=420,
    )
    fig.update_layout(xaxis_tickangle=-30, legend_title="Year")
    st.plotly_chart(fig, use_container_width=True)

    # Scatter: answer rate vs. total questions per dialect
    st.subheader("Answer rate vs. question volume — by dialect")
    dial_agg = (
        dial_filt.groupby("dialect")
        .agg(
            total_questions=("num_questions", "sum"),
            pct_answered=("pct_answered", "mean"),
            pct_accepted=("pct_accepted", "mean"),
            avg_score=("avg_score", "mean"),
            total_views=("total_views", "sum"),
        )
        .reset_index()
    )
    dial_agg["pct_answered"] = dial_agg["pct_answered"].round(4)
    dial_agg["pct_accepted"] = dial_agg["pct_accepted"].round(4)
    dial_agg["avg_score"]    = dial_agg["avg_score"].round(2)

    fig2 = px.scatter(
        dial_agg,
        x="total_questions", y="pct_answered",
        size="total_views", text="dialect",
        color="pct_accepted",
        color_continuous_scale="RdYlGn",
        range_color=[0.2, 0.55],
        labels={
            "total_questions": "Total questions",
            "pct_answered":    "% Answered",
            "pct_accepted":    "% Accepted",
        },
        hover_data={"avg_score": True, "pct_accepted": ":.1%", "total_views": ":,"},
        height=500,
    )
    fig2.update_traces(textposition="top center", marker_opacity=0.8)
    fig2.update_layout(
        coloraxis_colorbar=dict(title="% Accepted", tickformat=".0%"),
        yaxis_tickformat=".0%",
    )
    st.plotly_chart(fig2, use_container_width=True)
    st.caption(
        "Bubble size = total views. Color = % accepted. "
        "Dialects with high volume but low acceptance (lower-right) represent the most under-served communities."
    )

    st.dataframe(
        dial_agg.rename(columns={
            "dialect":         "Dialect",
            "total_questions": "Questions",
            "pct_answered":    "% Answered",
            "pct_accepted":    "% Accepted",
            "avg_score":       "Avg score",
            "total_views":     "Total views",
        }).sort_values("Questions", ascending=False).set_index("Dialect")
        .style.format({
            "Questions":  "{:,}",
            "% Answered": "{:.1%}",
            "% Accepted": "{:.1%}",
            "Avg score":  "{:.2f}",
            "Total views":"{:,.0f}",
        }),
        use_container_width=True,
    )

# ─── Tab 7 — Complexity scoring ───────────────────────────────────────────────

with tab7:
    st.subheader("SQL question complexity distribution")
    st.caption(
        "Each question is scored by detecting 16 SQL features in the body text via regex. "
        "Score weights: SELECT/WHERE/ORDER BY = 1pt · GROUP BY/JOIN/Aggregate/HAVING = 2pt · "
        "CASE WHEN/Set ops/Subquery = 3pt · CTE/Window = 5pt · Recursive/LATERAL/APPLY/PIVOT = 7pt."
    )

    tier_order = [
        "0 · No SQL detected",
        "1 · Trivial",
        "2 · Basic",
        "3 · Intermediate",
        "4 · Advanced",
        "5 · Expert",
    ]

    # Distribution bar chart
    cx_sorted = cx_tiers.copy()
    cx_sorted["complexity_tier"] = pd.Categorical(
        cx_sorted["complexity_tier"], categories=tier_order, ordered=True
    )
    cx_sorted = cx_sorted.sort_values("complexity_tier")

    col_dist, col_rate = st.columns(2)

    with col_dist:
        st.markdown("#### Questions per complexity tier")
        fig = px.bar(
            cx_sorted, x="complexity_tier", y="num_questions",
            color="num_questions", color_continuous_scale="Blues",
            labels={"num_questions": "Questions", "complexity_tier": ""},
            text="num_questions",
        )
        fig.update_coloraxes(showscale=False)
        fig.update_traces(texttemplate="%{text:,}", textposition="outside")
        fig.update_layout(xaxis_tickangle=-20)
        st.plotly_chart(fig, use_container_width=True)

    with col_rate:
        st.markdown("#### Answer rate by complexity tier")
        fig2 = px.bar(
            cx_sorted, x="complexity_tier", y="pct_answered",
            color="pct_accepted",
            color_continuous_scale="RdYlGn",
            range_color=[0.2, 0.55],
            labels={
                "pct_answered": "% Answered",
                "complexity_tier": "",
                "pct_accepted": "% Accepted",
            },
            text="pct_answered",
        )
        fig2.update_traces(texttemplate="%{text:.1%}", textposition="outside")
        fig2.update_layout(
            xaxis_tickangle=-20,
            yaxis_tickformat=".0%",
            coloraxis_colorbar=dict(title="% Accepted", tickformat=".0%"),
        )
        st.plotly_chart(fig2, use_container_width=True)

    # Feature frequency chart
    st.subheader("SQL feature presence across all questions")
    st.caption("% of questions in the selected years that contain each feature (regex match on body text).")

    feat_row = cx_feats.iloc[0]
    feat_df = pd.DataFrame({
        "feature": [
            "SELECT", "WHERE", "ORDER BY",
            "INSERT INTO", "UPDATE", "DELETE FROM", "CREATE TABLE/VIEW", "ALTER TABLE", "DROP",
            "JOIN", "GROUP BY", "Aggregate fn", "HAVING",
            "CASE WHEN", "Set ops (UNION…)", "Subquery",
            "CTE (WITH…AS)", "Window fn (OVER)",
            "Recursive CTE", "LATERAL", "CROSS/OUTER APPLY", "PIVOT",
        ],
        "pct": [
            feat_row["select_pct"],  feat_row["where_pct"],    feat_row["order_by_pct"],
            feat_row["insert_pct"],  feat_row["update_pct"],   feat_row["delete_pct"],
            feat_row["create_pct"],  feat_row["alter_pct"],    feat_row["drop_pct"],
            feat_row["join_pct"],    feat_row["group_by_pct"], feat_row["aggregate_pct"],
            feat_row["having_pct"],  feat_row["case_when_pct"],feat_row["set_ops_pct"],
            feat_row["subqueries_pct"], feat_row["cte_pct"],   feat_row["window_pct"],
            feat_row["recursive_pct"],  feat_row["lateral_pct"],feat_row["apply_pct"],
            feat_row["pivot_pct"],
        ],
        "tier": [
            "Basic", "Basic", "Basic",
            "DML / DDL", "DML / DDL", "DML / DDL", "DML / DDL", "DML / DDL", "DML / DDL",
            "Intermediate", "Intermediate", "Intermediate", "Intermediate",
            "Advanced", "Advanced", "Advanced",
            "Expert", "Expert",
            "Master", "Master", "Master", "Master",
        ],
    }).sort_values("pct", ascending=True)

    tier_colors = {
        "Basic":        "#74c0fc",
        "DML / DDL":    "#a9e34b",
        "Intermediate": "#51cf66",
        "Advanced":     "#fcc419",
        "Expert":       "#ff922b",
        "Master":       "#f03e3e",
    }

    fig3 = px.bar(
        feat_df, x="pct", y="feature", orientation="h",
        color="tier",
        color_discrete_map=tier_colors,
        labels={"pct": "% of questions", "feature": "", "tier": "Complexity tier"},
        height=520,
    )
    fig3.update_layout(xaxis_title="% of questions containing this feature")
    st.plotly_chart(fig3, use_container_width=True)

    st.dataframe(
        cx_tiers.rename(columns={
            "complexity_tier":      "Tier",
            "num_questions":        "Questions",
            "pct_answered":         "% Answered",
            "pct_accepted":         "% Accepted",
            "avg_score":            "Avg score",
            "avg_complexity_score": "Avg complexity",
            "total_views":          "Total views",
        }).set_index("Tier")
        .style.format({
            "Questions":      "{:,}",
            "% Answered":     "{:.1%}",
            "% Accepted":     "{:.1%}",
            "Avg score":      "{:.2f}",
            "Avg complexity": "{:.1f}",
            "Total views":    "{:,.0f}",
        }),
        use_container_width=True,
    )

# ─── Tab 8 — Data validation ──────────────────────────────────────────────────

with tab8:
    st.subheader("Pipeline data validation")
    st.caption(
        "Cross-layer consistency checks: raw → dbt staging → dbt marts. "
        "Verifies row counts, numeric sums, and derived boolean flags haven't "
        "drifted between pipeline layers."
    )

    @st.cache_data(ttl=3600, show_spinner="Running validation checks…")
    def load_validation() -> pd.DataFrame:
        RAW   = f"`{PROJECT}`.`raw`"
        STG   = f"`{PROJECT}`.`dbt_dev_staging`"
        return run(f"""
            with raw_q as (
                select
                    count(*)                                as n,
                    sum(score)                              as score_sum,
                    sum(view_count)                         as view_sum,
                    countif(accepted_answer_id is not null) as accepted_count,
                    countif(answer_count > 0)               as answered_count
                from {RAW}.questions
            ),
            dim_q as (
                select
                    count(*)                                as n,
                    count(distinct question_id)             as n_unique,
                    sum(score)                              as score_sum,
                    sum(view_count)                         as view_sum,
                    countif(has_accepted_answer)            as accepted_count,
                    countif(is_answered)                    as answered_count
                from {MARTS}.dim_questions
            ),
            raw_a  as (select count(*) as n from {RAW}.answers),
            stg_a  as (select count(*) as n from {STG}.stg_answers),
            fct_sql_2020 as (
                select sum(num_questions) as n
                from {MARTS}.fct_tag_yearly
                where tag = 'sql' and creation_year = 2020
            ),
            dim_sql_2020 as (
                select count(*) as n
                from {MARTS}.dim_questions
                where 'sql' in unnest(tags) and creation_year = 2020
            )
            select 'raw → dim_questions row count'                       as check_name, cast(rq.n as string) as expected, cast(dq.n as string) as actual, rq.n = dq.n as passed from raw_q rq, dim_q dq
            union all select 'dim_questions: no duplicate question_ids', cast(dq.n as string), cast(dq.n_unique as string), dq.n = dq.n_unique from dim_q dq
            union all select 'raw → dim_questions score sum',            cast(rq.score_sum as string), cast(dq.score_sum as string), rq.score_sum = dq.score_sum from raw_q rq, dim_q dq
            union all select 'raw → dim_questions view count sum',       cast(rq.view_sum as string), cast(dq.view_sum as string), rq.view_sum = dq.view_sum from raw_q rq, dim_q dq
            union all select 'has_accepted_answer matches raw',          cast(rq.accepted_count as string), cast(dq.accepted_count as string), rq.accepted_count = dq.accepted_count from raw_q rq, dim_q dq
            union all select 'is_answered matches raw answer_count > 0', cast(rq.answered_count as string), cast(dq.answered_count as string), rq.answered_count = dq.answered_count from raw_q rq, dim_q dq
            union all select 'raw → stg_answers row count',              cast(ra.n as string), cast(sa.n as string), ra.n = sa.n from raw_a ra, stg_a sa
            union all select 'fct_tag_yearly sql/2020 matches dim_questions', cast(f.n as string), cast(d.n as string), f.n = d.n from fct_sql_2020 f, dim_sql_2020 d
            order by passed asc, check_name
        """)

    val = load_validation()

    n_pass = val["passed"].sum()
    n_total = len(val)

    if n_pass == n_total:
        st.success(f"✅ All {n_total} validation checks passed")
    else:
        st.error(f"❌ {n_total - n_pass} of {n_total} checks failed")

    # Render with coloured status column
    display = val.copy()
    display["Status"] = display["passed"].map({True: "✅ Pass", False: "❌ Fail"})
    display = display.drop(columns=["passed"]).rename(columns={
        "check_name": "Check",
        "expected":   "Expected",
        "actual":     "Actual",
    })[["Check", "Expected", "Actual", "Status"]]

    st.dataframe(
        display.style.apply(
            lambda row: [
                "", "", "",
                "color: green" if row["Status"].startswith("✅") else "color: red",
            ],
            axis=1,
        ),
        use_container_width=True,
        hide_index=True,
    )

    st.divider()
    st.markdown(
        """
        **What each check validates**

        | Check | Why it matters |
        |---|---|
        | raw → dim_questions row count | No questions silently dropped or duplicated through dbt joins |
        | No duplicate question_ids | The LEFT JOINs to users and answers didn't fan out the grain |
        | Score / view count sums | Numeric columns passed through without truncation or type coercion |
        | has_accepted_answer | Derived bool matches its source column (`accepted_answer_id IS NOT NULL`) |
        | is_answered | Derived bool matches its source column (`answer_count > 0`) |
        | raw → stg_answers row count | Staging view over answers didn't filter any rows |
        | fct_tag_yearly sql/2020 | Mart aggregation matches a direct count from the question grain |
        """
    )

# ─── Tab 9 — Practice Questions ───────────────────────────────────────────────

_PRACTICE_TIERS = [
    "1 · Trivial",
    "2 · Basic",
    "3 · Intermediate",
    "4 · Advanced",
    "5 · Expert",
]


def _active_features(row: pd.Series) -> str:
    pairs = [
        ("JOIN",                       "f_join"),
        ("GROUP BY",                   "f_group_by"),
        ("Aggregate functions",        "f_aggregate"),
        ("HAVING",                     "f_having"),
        ("CASE WHEN",                  "f_case_when"),
        ("UNION / INTERSECT / EXCEPT", "f_set_ops"),
        ("Subqueries",                 "f_subqueries"),
        ("CTE (WITH … AS)",            "f_cte"),
        ("Window functions (OVER)",    "f_window"),
        ("Recursive CTE",              "f_recursive"),
        ("LATERAL",                    "f_lateral"),
        ("CROSS / OUTER APPLY",        "f_apply"),
        ("PIVOT",                      "f_pivot"),
    ]
    return ", ".join(label for label, col in pairs if row.get(col, 0))


def generate_practice_question(row: pd.Series) -> dict:
    import json, re
    cache_key = f"_pq_{int(row['question_id'])}"
    if cache_key in st.session_state:
        return st.session_state[cache_key]

    client = get_anthropic_client()
    if client is None:
        return {"_error": "No ANTHROPIC_API_KEY configured."}

    features = _active_features(row) or "basic SELECT / WHERE"
    prompt = (
        "You are a SQL practice question generator. Create a focused exercise "
        "based on this Stack Overflow question.\n\n"
        f"Title: \"{row['title']}\"\n"
        f"Tags: {row['tags_str']}\n"
        f"Difficulty: {row['complexity_tier']}\n"
        f"SQL features: {features}\n\n"
        "Return ONLY a JSON object with these exact keys:\n"
        "{\n"
        "  \"prompt\":      \"2-4 sentences with a concrete business scenario and the table(s) involved.\",\n"
        "  \"task\":        \"A broken SQL query to debug, OR a partial query with blanks. Match the difficulty.\",\n"
        "  \"dialect\":     \"SQL dialect inferred from tags, or Standard SQL.\",\n"
        "  \"answer\":      \"The complete correct SQL query.\",\n"
        "  \"explanation\": \"1-3 sentences on the key concept or fix.\"\n"
        "}"
    )

    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    text = resp.content[0].text.strip()
    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r'\{.*\}', text, re.DOTALL)
        result = json.loads(m.group()) if m else {"_error": "Could not parse response.", "_raw": text}

    st.session_state[cache_key] = result
    return result


with tab9:
    st.subheader("SQL Practice Questions")
    st.caption(
        "Each question is grounded in a real Stack Overflow scenario and synthesised by Claude. "
        "Pick a difficulty, study the task, write your answer, then reveal the solution."
    )

    if get_anthropic_client() is None:
        st.error(
            "**`ANTHROPIC_API_KEY` not found in Streamlit secrets.** "
            "Add it to `.streamlit/secrets.toml` locally or in the Streamlit Cloud Secrets editor."
        )
    else:
        sel_tier = st.selectbox(
            "Difficulty",
            options=_PRACTICE_TIERS,
            index=1,
            key="pq_tier",
        )

        if st.session_state.get("_pq_last_tier") != sel_tier:
            st.session_state["_pq_idx"]      = 0
            st.session_state["_pq_revealed"]  = False
            st.session_state["_pq_last_tier"] = sel_tier

        pool = load_practice_pool(sel_tier)

        if pool.empty:
            st.warning(f"No questions found for tier **{sel_tier}**.")
        else:
            idx = st.session_state.get("_pq_idx", 0) % len(pool)
            row = pool.iloc[idx]

            with st.spinner("Generating practice question…"):
                pq = generate_practice_question(row)

            if "_error" in pq:
                st.error(pq["_error"])
                if "_raw" in pq:
                    st.code(pq["_raw"])
            else:
                st.markdown(
                    f"**Tier:** `{row['complexity_tier']}` &nbsp;·&nbsp; "
                    f"**Dialect:** `{pq.get('dialect', 'SQL')}` &nbsp;·&nbsp; "
                    f"**SO score:** {int(row['score'])} &nbsp;·&nbsp; "
                    f"**Views:** {int(row['view_count']):,}"
                )

                st.markdown("#### Scenario")
                st.info(pq.get("prompt", ""))

                st.markdown("#### Task")
                st.code(pq.get("task", ""), language="sql")

                st.text_area(
                    "Your answer",
                    height=160,
                    key=f"pq_user_{idx}_{sel_tier}",
                    placeholder="-- Write your SQL solution here…",
                )

                c_rev, c_nxt, _ = st.columns([1, 1, 5])

                if c_rev.button("Reveal answer", key=f"pq_rev_{idx}_{sel_tier}"):
                    st.session_state["_pq_revealed"] = True

                if c_nxt.button("Next question ▶", key=f"pq_nxt_{idx}_{sel_tier}"):
                    st.session_state["_pq_idx"]     = (idx + 1) % len(pool)
                    st.session_state["_pq_revealed"] = False
                    st.rerun()

                if st.session_state.get("_pq_revealed"):
                    st.markdown("#### Answer")
                    st.code(pq.get("answer", ""), language="sql")
                    st.caption(pq.get("explanation", ""))

                st.divider()
                st.caption(
                    f"SO question #{int(row['question_id'])} · "
                    f"Tags: {row['tags_str']}"
                )
