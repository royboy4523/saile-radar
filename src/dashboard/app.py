"""
Saile Radar — Healthcare Workforce Intelligence Dashboard
Interactive facility targeting tool for Saile BD team.
Run: streamlit run src/dashboard/app.py
"""

import os
from datetime import date
from io import BytesIO

import pandas as pd
import plotly.express as px
import streamlit as st

# ── constants ─────────────────────────────────────────────────────────────────
SAILE_BLUE = "#2663eb"
SAILE_DARK = "#1a4bc4"
SAILE_LIGHT = "#f0f4ff"

VMS_COLORS = {
    "direct_hire": "#22c55e",
    "uncertain":   "#f59e0b",
    "likely_vms":  "#ef4444",
}
VMS_LABELS = {
    "direct_hire": "Direct Hire Target",
    "uncertain":   "Uncertain",
    "likely_vms":  "Likely VMS",
}
# Inverse map for sidebar filter
LABEL_TO_VMS = {v: k for k, v in VMS_LABELS.items()}

TABLE_COLS = {
    "score_rank":           "Rank",
    "facility_name":        "Facility Name",
    "city":                 "City",
    "state":                "State",
    "bed_count":            "Beds",
    "composite_score":      "Shortage Score",
    "hpsa_score_max":       "HPSA Score",
    "vms_classification":   "VMS Status",
    "aamc_category_approx": "Specialty",
    "urban_rural":          "Urban / Rural",
}

DATA_PATH = "data/processed/facilities_final.parquet"

# ── page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Saile Radar",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── global CSS ────────────────────────────────────────────────────────────────
st.markdown(f"""
<style>
    .main {{ background-color: #f8fafc; }}
    [data-testid="stSidebar"] {{ background-color: {SAILE_LIGHT}; }}

    .radar-header {{
        background: linear-gradient(90deg, {SAILE_BLUE} 0%, {SAILE_DARK} 100%);
        color: white;
        padding: 1.4rem 2rem;
        border-radius: 10px;
        margin-bottom: 1.5rem;
    }}
    .radar-header h1 {{ color: white; margin: 0; font-size: 1.9rem; letter-spacing: -0.5px; }}
    .radar-header p  {{ color: #c7d9ff; margin: 0.3rem 0 0 0; font-size: 0.88rem; }}

    .kpi-card {{
        background: white;
        border: 1px solid #e2e8f0;
        border-top: 3px solid {SAILE_BLUE};
        border-radius: 8px;
        padding: 0.9rem 1rem;
        text-align: center;
    }}
    .kpi-val {{ font-size: 1.9rem; font-weight: 700; color: {SAILE_BLUE}; line-height: 1; }}
    .kpi-lbl {{ font-size: 0.75rem; color: #64748b; margin-top: 0.3rem; }}

    div[data-testid="stButton"] > button {{
        background-color: {SAILE_BLUE} !important;
        color: white !important;
        border: none !important;
        border-radius: 6px !important;
        font-weight: 600 !important;
        padding: 0.45rem 1.4rem !important;
    }}
    div[data-testid="stButton"] > button:hover {{
        background-color: {SAILE_DARK} !important;
    }}

    .section-title {{
        font-size: 1.05rem;
        font-weight: 600;
        color: #1e293b;
        margin: 1.2rem 0 0.5rem 0;
        padding-bottom: 0.3rem;
        border-bottom: 2px solid {SAILE_BLUE};
        display: inline-block;
    }}
</style>
""", unsafe_allow_html=True)


# ── data ──────────────────────────────────────────────────────────────────────
@st.cache_data(show_spinner="Loading facility data…")
def load_data() -> pd.DataFrame | None:
    if not os.path.exists(DATA_PATH):
        return None

    df = pd.read_parquet(DATA_PATH)

    # Geocode ZIP → lat/lon (best-effort; skipped if pgeocode not installed)
    try:
        import pgeocode  # type: ignore
        nomi = pgeocode.Nominatim("us")
        unique_zips = df["zip"].str[:5].dropna().unique().tolist()
        geo = nomi.query_postal_code(unique_zips)
        lat_map = dict(zip(geo.postal_code, geo.latitude))
        lon_map = dict(zip(geo.postal_code, geo.longitude))
        df["lat"] = df["zip"].str[:5].map(lat_map)
        df["lon"] = df["zip"].str[:5].map(lon_map)
    except Exception:
        df["lat"] = None
        df["lon"] = None

    df["vms_label"]       = df["vms_classification"].map(VMS_LABELS).fillna("Uncertain")
    df["urban_rural_lbl"] = df["urban_rural"].map({"U": "Urban", "R": "Rural"}).fillna("Unknown")
    df["composite_score"] = df["composite_score"].round(4)

    return df


def apply_filters(
    df: pd.DataFrame,
    states: list,
    specialties: list,
    vms_keys: list,
    score_range: tuple,
    top_n: int,
) -> pd.DataFrame:
    out = df.copy()
    if states:
        out = out[out["state"].isin(states)]
    if specialties:
        out = out[out["aamc_category_approx"].isin(specialties)]
    if vms_keys:
        out = out[out["vms_classification"].isin(vms_keys)]
    out = out[
        (out["composite_score"] >= score_range[0]) &
        (out["composite_score"] <= score_range[1])
    ]
    out = out.sort_values("composite_score", ascending=False)
    if top_n < len(out):
        out = out.head(top_n)
    return out.reset_index(drop=True)


# ── map ───────────────────────────────────────────────────────────────────────
def build_map(df: pd.DataFrame):
    mapped = df.dropna(subset=["lat", "lon"])
    if mapped.empty:
        return None

    fig = px.scatter_geo(
        mapped,
        lat="lat",
        lon="lon",
        color="vms_classification",
        color_discrete_map=VMS_COLORS,
        hover_name="facility_name",
        hover_data={
            "city":            True,
            "state":           True,
            "composite_score": ":.4f",
            "hpsa_score_max":  True,
            "bed_count":       True,
            "vms_label":       True,
            "lat":             False,
            "lon":             False,
            "vms_classification": False,
        },
        labels={
            "vms_classification": "VMS Status",
            "composite_score":    "Shortage Score",
            "hpsa_score_max":     "HPSA Score",
            "bed_count":          "Beds",
            "vms_label":          "Classification",
        },
        scope="usa",
    )
    fig.update_traces(marker=dict(size=8, opacity=0.85))
    fig.update_layout(
        height=460,
        margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor="white",
        legend=dict(
            title="VMS Status",
            orientation="h",
            yanchor="bottom",
            y=0.01,
            xanchor="right",
            x=0.99,
            bgcolor="rgba(255,255,255,0.85)",
            bordercolor="#e2e8f0",
            borderwidth=1,
        ),
        geo=dict(
            showland=True,
            landcolor="#f1f5f9",
            showlakes=True,
            lakecolor="#bfdbfe",
            showcoastlines=True,
            coastlinecolor="#94a3b8",
            showframe=False,
            projection_type="albers usa",
        ),
    )
    return fig


# ── display table ─────────────────────────────────────────────────────────────
def build_display_table(df: pd.DataFrame) -> pd.DataFrame:
    out = df[list(TABLE_COLS.keys())].copy()
    out = out.rename(columns=TABLE_COLS)
    out["VMS Status"]    = out["VMS Status"].map(VMS_LABELS).fillna("Uncertain")
    out["Urban / Rural"] = out["Urban / Rural"].map({"U": "Urban", "R": "Rural"}).fillna("Unknown")
    out["Shortage Score"] = out["Shortage Score"].round(4)
    out["Beds"] = out["Beds"].apply(lambda x: int(x) if pd.notna(x) else None)
    out["HPSA Score"] = out["HPSA Score"].apply(lambda x: int(x) if pd.notna(x) else None)
    return out.reset_index(drop=True)


# ── exports ───────────────────────────────────────────────────────────────────
def export_excel(df: pd.DataFrame) -> bytes:
    table = build_display_table(df)
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        table.to_excel(writer, index=False, sheet_name="Saile Radar Targets")
        ws = writer.sheets["Saile Radar Targets"]
        # Auto-size columns
        for col in ws.columns:
            max_len = max(len(str(cell.value or "")) for cell in col)
            ws.column_dimensions[col[0].column_letter].width = min(max_len + 4, 60)
    return buf.getvalue()


def export_pdf(df: pd.DataFrame) -> bytes:
    try:
        from fpdf import FPDF  # type: ignore
    except ImportError:
        st.error("PDF export requires fpdf2. Run: pip install fpdf2")
        return b""

    table = build_display_table(df)

    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=12)
    pdf.add_page()

    # ── header bar ──
    pdf.set_fill_color(38, 99, 235)
    pdf.rect(0, 0, 297, 26, "F")
    pdf.set_font("Helvetica", "B", 17)
    pdf.set_text_color(255, 255, 255)
    pdf.set_xy(10, 6)
    pdf.cell(0, 9, "SAILE RADAR  -  Priority Facility Report")
    pdf.set_font("Helvetica", "", 8)
    pdf.set_xy(10, 17)
    pdf.cell(
        0, 5,
        f"Generated: {date.today().strftime('%B %d, %Y')}   |   "
        f"Showing {len(table)} facilities ranked by shortage score"
    )

    pdf.set_text_color(0, 0, 0)
    pdf.set_xy(10, 32)

    # Column layout (landscape A4 = ~277mm usable)
    cols    = list(table.columns)
    widths  = [12, 64, 24, 13, 14, 21, 17, 36, 42, 19]  # 262mm total

    # ── table header ──
    pdf.set_fill_color(38, 99, 235)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 7.5)
    for header, w in zip(cols, widths):
        pdf.cell(w, 7, header, border=0, fill=True, align="C")
    pdf.ln()

    # ── table rows ──
    pdf.set_font("Helvetica", "", 6.8)
    for i, (_, row) in enumerate(table.iterrows()):
        if i % 2 == 0:
            pdf.set_fill_color(240, 244, 255)
        else:
            pdf.set_fill_color(255, 255, 255)
        pdf.set_text_color(30, 41, 59)

        vals = [
            str(row["Rank"]),
            str(row["Facility Name"])[:46],
            str(row["City"]),
            str(row["State"]),
            str(row["Beds"]) if pd.notna(row["Beds"]) else "—",
            f"{row['Shortage Score']:.4f}",
            str(row["HPSA Score"]) if pd.notna(row["HPSA Score"]) else "—",
            str(row["VMS Status"]),
            str(row["Specialty"])[:38] if pd.notna(row["Specialty"]) else "—",
            str(row["Urban / Rural"]),
        ]
        for val, w in zip(vals, widths):
            pdf.cell(w, 5.5, val, border=0, fill=True, align="L")
        pdf.ln()

    # ── footer ──
    pdf.set_y(-12)
    pdf.set_font("Helvetica", "I", 7)
    pdf.set_text_color(100, 116, 139)
    pdf.cell(0, 5, "Saile Radar  |  Confidential  |  For internal use only", align="C")

    return bytes(pdf.output())


# ── main app ──────────────────────────────────────────────────────────────────
def main():
    df = load_data()

    if df is None:
        st.error(
            "Processed data not found. Run the full pipeline first:\n"
            "`python src/ingest/unify.py` → `python src/scoring/model.py` → "
            "`PYTHONPATH=. python src/vms/classifier.py`"
        )
        return

    # ── header ────────────────────────────────────────────────────────────────
    st.markdown("""
    <div class="radar-header">
        <h1>📡 Saile Radar</h1>
        <p>Healthcare Workforce Intelligence — Priority Facility Targeting Dashboard</p>
    </div>
    """, unsafe_allow_html=True)

    # ── sidebar filters ───────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown(f"<h2 style='color:{SAILE_BLUE};margin-bottom:0.5rem'>Filters</h2>",
                    unsafe_allow_html=True)

        all_states = sorted(df["state"].dropna().unique())
        sel_states = st.multiselect("State", all_states, placeholder="All states")

        all_specialties = sorted(df["aamc_category_approx"].dropna().unique())
        sel_specialties = st.multiselect("Specialty", all_specialties, placeholder="All specialties")

        sel_vms_labels = st.multiselect(
            "VMS Classification",
            list(VMS_LABELS.values()),
            placeholder="All classifications",
        )
        sel_vms_keys = [LABEL_TO_VMS[l] for l in sel_vms_labels]

        score_min = float(df["composite_score"].min())
        score_max = float(df["composite_score"].max())
        score_range = st.slider(
            "Shortage Score Range",
            min_value=score_min,
            max_value=score_max,
            value=(score_min, score_max),
            step=0.001,
            format="%.3f",
        )

        st.markdown("---")
        top_n = st.number_input(
            "Show Top N Facilities",
            min_value=1,
            max_value=len(df),
            value=len(df),
            step=10,
            help="After applying all filters, limit results to the top N facilities by shortage score.",
        )

        st.markdown("---")
        st.markdown(
            f"<small style='color:#64748b'>Pipeline output: {len(df)} Stage 2 facilities</small>",
            unsafe_allow_html=True,
        )

    # ── apply filters ─────────────────────────────────────────────────────────
    filtered = apply_filters(df, sel_states, sel_specialties, sel_vms_keys, score_range, int(top_n))

    # ── KPI row ───────────────────────────────────────────────────────────────
    direct      = (filtered["vms_classification"] == "direct_hire").sum()
    uncertain   = (filtered["vms_classification"] == "uncertain").sum()
    likely_vms  = (filtered["vms_classification"] == "likely_vms").sum()
    avg_score   = filtered["composite_score"].mean()

    c1, c2, c3, c4, c5 = st.columns(5)
    kpis = [
        (c1, str(len(filtered)),      "Facilities Shown"),
        (c2, str(direct),             "Direct Hire Targets"),
        (c3, str(uncertain),          "Uncertain"),
        (c4, str(likely_vms),         "Likely VMS"),
        (c5, f"{avg_score:.3f}",      "Avg Shortage Score"),
    ]
    for col, val, label in kpis:
        col.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-val">{val}</div>
            <div class="kpi-lbl">{label}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── map ───────────────────────────────────────────────────────────────────
    st.markdown('<div class="section-title">Facility Map</div>', unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    fig = build_map(filtered)
    if fig:
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Map unavailable — install pgeocode for geographic coordinates: `pip install pgeocode`")

    # ── data table ────────────────────────────────────────────────────────────
    st.markdown(
        f'<div class="section-title">Facility List &nbsp;<span style="font-weight:400;font-size:0.85rem;color:#64748b">({len(filtered)} facilities)</span></div>',
        unsafe_allow_html=True,
    )
    st.markdown("<br>", unsafe_allow_html=True)

    table_df = build_display_table(filtered)
    st.dataframe(
        table_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Shortage Score": st.column_config.NumberColumn(format="%.4f"),
            "Beds":           st.column_config.NumberColumn(format="%d"),
            "HPSA Score":     st.column_config.NumberColumn(format="%d"),
        },
    )

    # ── export ────────────────────────────────────────────────────────────────
    st.markdown('<div class="section-title">Export Report</div>', unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    fmt_col, btn_col = st.columns([2, 4])
    with fmt_col:
        export_fmt = st.radio("Format", ["Excel", "PDF"], horizontal=True)
    with btn_col:
        today = pd.Timestamp.now().strftime("%Y%m%d")
        if export_fmt == "Excel":
            st.download_button(
                label="⬇ Download Excel Report",
                data=export_excel(filtered),
                file_name=f"saile_radar_{today}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        else:
            pdf_data = export_pdf(filtered)
            if pdf_data:
                st.download_button(
                    label="⬇ Download PDF Report",
                    data=pdf_data,
                    file_name=f"saile_radar_{today}.pdf",
                    mime="application/pdf",
                )


if __name__ == "__main__":
    main()
