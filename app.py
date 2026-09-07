import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import streamlit.components.v1 as components

# ==========================================
# 1. KONFIGURASI HALAMAN & HEADER
# ==========================================
st.set_page_config(
    page_title="Dashboard POB IBS Building Management",
    page_icon="📊",
    layout="wide"
)

st.title("📊 DASHBOARD POB IBS BUILDING MANAGEMENT")
st.markdown("---")

# ==========================================
# 2. BACA DATA DARI GOOGLE SHEETS & DATA CLEANING
# ==========================================
# ID Google Sheet diambil dari URL:
# https://docs.google.com/spreadsheets/d/<SHEET_ID>/edit
SHEET_ID = st.secrets.get("SHEET_ID", "1g3Y6GjXUgjWFtKxC9ul8i0vZgHvamkDwT7j4-_95NMk")
# GID = ID tab/worksheet spesifik (0 = tab pertama). Ganti jika data ada di tab lain.
SHEET_GID = st.secrets.get("SHEET_GID", "2119013984")

# Bisa juga override penuh via secrets.toml -> SHEET_CSV_URL = "https://...&output=csv"
SHEET_CSV_URL = st.secrets.get(
    "SHEET_CSV_URL",
    f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={SHEET_GID}"
)

@st.cache_data(ttl=300)
def load_data():
    df = pd.read_csv(SHEET_CSV_URL)
    df.columns = df.columns.astype(str).str.strip()

    # 🛠️ GABUNGKAN KOLOM DUPLIKAT (misal ada 2 kolom "Invoice Amount" karena
    # salah satunya punya spasi ekstra sebelum dibersihkan). Untuk tiap nama
    # yang duplikat, ambil nilai yang TIDAK kosong dari kolom manapun per
    # baris (bukan asal pilih kolom pertama, supaya data asli tidak hilang
    # kalau ternyata kolom pertama yang kosong).
    if df.columns.duplicated().any():
        dup_names = df.columns[df.columns.duplicated()].unique()
        for name in dup_names:
            same_cols = df.loc[:, df.columns == name]
            merged = same_cols.bfill(axis=1).iloc[:, 0]
            df = df.loc[:, df.columns != name]
            df[name] = merged
    
    # 🛠️ PEMBERSIHAN KOLOM AREA (SERAGAMKAN FORMAT "Area 2")
    if 'Area' in df.columns:
        df['Area'] = (
            df['Area']
            .astype(str)
            .str.strip()
            .str.title()
        )
    return df

try:
    df_raw = load_data()
except Exception as e:
    st.error(
        "❌ Gagal membaca data dari Google Sheets. Pastikan sharing sheet "
        "diatur ke 'Anyone with the link' -> Viewer, lalu cek kembali "
        f"SHEET_ID/SHEET_GID. Detail error: {e}"
    )
    st.stop()

with st.sidebar.expander("🛠️ Debug: Cek Data (klik untuk buka)"):
    st.write(f"Jumlah baris: {len(df_raw)}")
    st.write("Daftar kolom yang terbaca dari Google Sheets:")
    st.write(list(df_raw.columns))
    for col_check in ['NET AMOUNT', 'Invoice Agent', 'Status Reimburse Actual', 'Status', 'Invoice Amount']:
        if col_check in df_raw.columns:
            n_non_null = df_raw[col_check].notna().sum()
            st.write(f"✅ '{col_check}' ada — {n_non_null} baris terisi")
        else:
            st.write(f"❌ '{col_check}' TIDAK ditemukan di sheet")

df_filtered = df_raw.copy()

# ==========================================
# 3. SIDEBAR CONTROL & GLOBAL FILTERS
# ==========================================
st.sidebar.header("🔍 Global Filters")

# Filter Area
if 'Area' in df_raw.columns:
    raw_areas = df_raw['Area'].dropna().unique().tolist()
    clean_areas = sorted([str(x) for x in raw_areas if str(x).lower() != 'nan'])
    list_area = ["(All)"] + clean_areas
    selected_area = st.sidebar.selectbox("Area Filter", options=list_area, index=0)
    
    if selected_area != "(All)":
        df_filtered = df_filtered[df_filtered['Area'] == selected_area]

# Filter Payment Month
col_month = 'Payment Month' if 'Payment Month' in df_filtered.columns else ('Month' if 'Month' in df_filtered.columns else None)
if col_month and col_month in df_filtered.columns:
    list_month = ["(All Months)"] + [str(x) for x in df_filtered[col_month].dropna().unique().tolist()]
    selected_month = st.sidebar.selectbox("Payment Month Filter", options=list_month, index=0)
    if selected_month != "(All Months)":
        df_filtered = df_filtered[df_filtered[col_month].astype(str) == selected_month]

# Filter New Regional
if 'new regional' in df_filtered.columns:
    list_reg = ["(All Regionals)"] + [str(x) for x in df_filtered['new regional'].dropna().unique().tolist()]
    selected_reg = st.sidebar.selectbox("New Regional Filter", options=list_reg, index=0)
    if selected_reg != "(All Regionals)":
        df_filtered = df_filtered[df_filtered['new regional'].astype(str) == selected_reg]

# ==========================================
# FUNGSI HELPER: COMPACT DONUT CHART (KPI)
# ==========================================
def create_compact_donut_card(title, paid_val, ny_val, color_done='#558B2F', color_ny='#E53935'):
    total_val = paid_val + ny_val
    pct_done = (paid_val / total_val * 100) if total_val > 0 else 0.0

    paid_m = paid_val / 1_000_000_000
    ny_m = ny_val / 1_000_000_000
    total_m = total_val / 1_000_000_000

    st.markdown(f"<div style='text-align: center; font-weight: bold; font-size: 13px; min-height: 38px;'>{title}</div>", unsafe_allow_html=True)
    st.markdown(f"<div style='text-align: center; color: #1E88E5; font-weight: bold; font-size: 16px; margin-bottom: 5px;'>Rp {total_m:,.2f} M</div>", unsafe_allow_html=True)

    fig = go.Figure(data=[go.Pie(
        labels=['Done', 'Not Yet Paid'],
        values=[paid_m, ny_m],
        hole=0.65,
        marker=dict(colors=[color_done, color_ny]),
        textinfo='none',
        hovertemplate="<b>%{label}</b><br>Nominal: Rp %{value:,.2f} M<br>Proporsi: %{percent}<extra></extra>"
    )])

    fig.update_layout(
        annotations=[dict(
            text=f"<b>{pct_done:.1f}%</b>",
            x=0.5, y=0.5,
            font_size=15,
            showarrow=False,
            font_color="#000000"
        )],
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="top",
            y=-0.05,
            xanchor="center",
            x=0.5,
            font=dict(size=10)
        ),
        margin=dict(l=5, r=5, t=5, b=5),
        height=180
    )

    st.plotly_chart(fig, use_container_width=True, key=f"donut_{title}")

    st.markdown(f"""
    <div style='font-size: 11px; text-align: center; color: #555;'>
        Done: <b>Rp {paid_m:,.2f}M</b><br>
        NY: <b>Rp {ny_m:,.2f}M</b>
    </div>
    """, unsafe_allow_html=True)


# ==========================================
# 4. 5 CHART KPI SEJAJAR HORIZONTAL
# ==========================================
st.subheader("📌 Key Performance Indicators (KPI Overview)")

col1, col2, col3, col4, col5 = st.columns(5)

val_payout_bm = 0
val_huawei_agent = 0
val_agent_tsel = 0
val_dn_issued = 0
val_payin_huawei = 0

# 1. Total Payout to BM
with col1:
    df_c1 = df_filtered.copy()
    col_status, col_amt = 'Status', 'Invoice Amount'
    if col_status in df_c1.columns and col_amt in df_c1.columns:
        df_c1[col_amt] = pd.to_numeric(df_c1[col_amt], errors='coerce').fillna(0)
        mask_paid = df_c1[col_status].astype(str).str.upper().str.strip() == 'PAID'
        val_payout_bm = df_c1[mask_paid][col_amt].sum()
        ny_val = df_c1[~mask_paid][col_amt].sum()
        create_compact_donut_card("Total Payout to BM", val_payout_bm, ny_val)
    else:
        st.warning("Kolom N/A")

# 2. Huawei To Agent
with col2:
    df_c2 = df_filtered.copy()
    col_status, col_amt = 'Status', 'NET AMOUNT'
    if col_status in df_c2.columns and col_amt in df_c2.columns:
        df_c2[col_amt] = pd.to_numeric(df_c2[col_amt], errors='coerce').fillna(0)
        mask_paid = df_c2[col_status].astype(str).str.upper().str.strip() == 'PAID'
        val_huawei_agent = df_c2[mask_paid][col_amt].sum()
        ny_val = df_c2[~mask_paid][col_amt].sum()
        create_compact_donut_card("Huawei To Agent", val_huawei_agent, ny_val)
    else:
        st.warning("Kolom N/A")

# 3. Agent To Telkomsel
with col3:
    df_c3 = df_filtered.copy()
    col_status, col_amt, col_inv = 'Status', 'NET AMOUNT', 'Invoice Agent'
    if col_inv in df_c3.columns:
        df_c3 = df_c3[df_c3[col_inv].astype(str).str.upper().str.strip() == 'INVOICE DONE']
    if col_status in df_c3.columns and col_amt in df_c3.columns:
        df_c3[col_amt] = pd.to_numeric(df_c3[col_amt], errors='coerce').fillna(0)
        mask_paid = df_c3[col_status].astype(str).str.upper().str.strip() == 'PAID'
        val_agent_tsel = df_c3[mask_paid][col_amt].sum()
        ny_val = df_c3[~mask_paid][col_amt].sum()
        create_compact_donut_card("Agent To Telkomsel", val_agent_tsel, ny_val)
    else:
        st.warning("Kolom N/A")

# 4. DN Issued
with col4:
    df_c4 = df_filtered.copy()
    col_status, col_amt = 'Status Reimburse Actual', 'NET AMOUNT'
    if col_status in df_c4.columns and col_amt in df_c4.columns:
        df_c4[col_amt] = pd.to_numeric(df_c4[col_amt], errors='coerce').fillna(0)
        status_clean = df_c4[col_status].astype(str).str.upper().str.strip()
        mask_done = status_clean.isin(['PAID', 'DN ISSUED'])
        val_dn_issued = df_c4[mask_done][col_amt].sum()
        ny_val = df_c4[~mask_done][col_amt].sum()
        create_compact_donut_card("DN Issued", val_dn_issued, ny_val)
    else:
        st.warning("Kolom N/A")

# 5. Total Pay In To Huawei
with col5:
    df_c5 = df_filtered.copy()
    col_status = 'Status Reimburse Actual'
    col_amt = 'NET AMOUNT'
    
    if col_status in df_c5.columns and col_amt in df_c5.columns:
        df_c5[col_amt] = pd.to_numeric(df_c5[col_amt], errors='coerce').fillna(0)
        status_clean = df_c5[col_status].astype(str).str.upper().str.strip()
        
        mask_paid = status_clean == 'PAID'
        val_payin_huawei = df_c5[mask_paid][col_amt].sum()
        
        mask_ny = status_clean.isin(['DN ISSUED', 'NY ISSUE DN'])
        ny_val = df_c5[mask_ny][col_amt].sum()
        
        create_compact_donut_card("Total Pay In To Huawei", val_payin_huawei, ny_val)
    else:
        st.warning("Kolom Status Reimburse Actual / NET AMOUNT N/A")

st.markdown("---")

# ==========================================
# 5. STATUS PAY OUT (TABLE MAPPING)
# ==========================================
st.subheader("📋 Status Pay Out")

col_status = 'Status'
col_amount = 'Invoice Amount'

if col_status in df_filtered.columns and col_amount in df_filtered.columns:
    df_status_calc = df_filtered.copy()
    df_status_calc[col_amount] = pd.to_numeric(df_status_calc[col_amount], errors='coerce').fillna(0)

    target_statuses = [
        "MODIFY REQUEST",
        "PAID",
        "Wait for Cashier",
        "WAITING FOR APW PROCESS",
        "Waiting for Accounting",
        "WAITING MGR APPROVAL",
        "WAITING PAYMENT APPROVAL"
    ]

    grouped = df_status_calc.groupby(df_status_calc[col_status].astype(str).str.strip(), as_index=False)[col_amount].sum()
    status_dict = {str(k).upper().strip(): v for k, v in zip(grouped[col_status], grouped[col_amount])}

    st.markdown("""
        <style>
        .status-box {
            background-color: #f0f0f0;
            border: 1px solid #cccccc;
            border-radius: 4px;
            padding: 8px 12px;
            text-align: center;
            font-size: 13px;
            font-weight: 500;
            color: #333333;
            margin-bottom: 6px;
            height: 38px;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .amount-box {
            background-color: #8faadc;
            border: 1px solid #6c8ebf;
            border-radius: 8px;
            padding: 8px 12px;
            text-align: center;
            font-size: 14px;
            font-weight: bold;
            color: #111111;
            margin-bottom: 6px;
            height: 38px;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        </style>
    """, unsafe_allow_html=True)

    col_layout, _ = st.columns([2, 3])
    with col_layout:
        for status_item in target_statuses:
            amount_val = status_dict.get(status_item.upper().strip(), 0)
            amount_str = f"Rp{amount_val:,.0f}".replace(",", ".") if amount_val > 0 else ("Rp0" if amount_val == 0 else "Rp-")

            c1, c2 = st.columns([1.2, 2])
            with c1:
                st.markdown(f"<div class='status-box'>{status_item}</div>", unsafe_allow_html=True)
            with c2:
                st.markdown(f"<div class='amount-box'>{amount_str}</div>", unsafe_allow_html=True)

st.markdown("---")

# ==========================================
# 6. END-TO-END PROCESS WORKFLOW & SLA
# ==========================================
st.subheader("🔄 End-to-End Process Workflow & SLA")

str_payout_bm = f"Rp{val_payout_bm:,.0f}".replace(",", ".") if val_payout_bm > 0 else "Rp0"
str_huawei_agent = f"Rp{val_huawei_agent:,.0f}".replace(",", ".") if val_huawei_agent > 0 else "Rp0"
str_agent_tsel = f"Rp{val_agent_tsel:,.0f}".replace(",", ".") if val_agent_tsel > 0 else "Rp0"
str_dn_issued = f"Rp{val_dn_issued:,.0f}".replace(",", ".") if val_dn_issued > 0 else "Rp0"
str_payin_huawei = f"Rp{val_payin_huawei:,.0f}".replace(",", ".") if val_payin_huawei > 0 else "Rp0"

html_content = f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
    body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: transparent; margin: 0; padding: 5px; }}
    .flow-container {{ display: flex; flex-direction: column; gap: 20px; width: 100%; }}
    .flow-row {{ display: flex; align-items: flex-start; justify-content: space-between; gap: 8px; }}
    .flow-card-wrapper {{ display: flex; flex-direction: column; align-items: center; flex: 1; }}
    .amount-badge {{ background: linear-gradient(180deg, #1f497d 0%, #0d284a 100%); color: white; font-weight: bold; font-size: 11px; padding: 5px 8px; border-radius: 6px; box-shadow: 0 2px 4px rgba(0,0,0,0.2); margin-bottom: -12px; z-index: 10; width: 85%; text-align: center; white-space: nowrap; }}
    .flow-card {{ border-radius: 8px; padding: 18px 8px 10px 8px; width: 100%; min-height: 95px; display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; font-size: 11px; font-weight: 600; box-shadow: 0 2px 5px rgba(0,0,0,0.08); border: 1px solid #ccc; box-sizing: border-box; }}
    .card-huawei {{ background-color: #dce6f1; border-color: #b8cce4; color: #1f497d; }}
    .card-rpj {{ background-color: #fce4d6; border-color: #f8c2a6; color: #c65911; }}
    .card-telkomsel {{ background-color: #fff2cc; border-color: #ffe599; color: #806000; }}
    .sla-label {{ font-size: 10px; font-weight: bold; color: #555; margin-top: 6px; }}
    .arrow-right {{ font-size: 20px; color: #1f497d; font-weight: bold; margin-top: 45px; }}
    .arrow-down {{ font-size: 22px; color: #1f497d; font-weight: bold; text-align: right; padding-right: 40px; margin-top: -10px; margin-bottom: -10px; }}
    .legend-container {{ display: flex; justify-content: flex-end; gap: 15px; margin-top: 20px; }}
    .legend-item {{ display: flex; align-items: center; gap: 6px; font-size: 11px; font-weight: bold; color: #333; }}
    .legend-box {{ width: 30px; height: 14px; border-radius: 3px; border: 1px solid #ccc; }}
</style>
</head>
<body>
<div class="flow-container">
    <div class="flow-row">
        <div class="flow-card-wrapper">
            <div class="amount-badge">{str_payout_bm}</div>
            <div class="flow-card card-huawei">Huawei Release Payment to Supplier</div>
            <div class="sla-label">SLA 5 WD</div>
        </div>
        <div class="arrow-right">➔</div>
        <div class="flow-card-wrapper">
            <div class="amount-badge">{str_huawei_agent}</div>
            <div class="flow-card card-huawei">
                <b>Huawei Submit Reimbursement Data to Agent</b>
                <span style="font-size: 8.5px; font-weight: normal; margin-top: 4px; line-height: 1.2;">
                    1. Summary Cover | 4. Tax Invoice (FP)<br>
                    2. Invoice BM | 5. Stand meter (kWh)<br>
                    3. Pay Slip | 6. XLX detail Calculation
                </span>
            </div>
            <div class="sla-label">SLA 2-3 WD</div>
        </div>
        <div class="arrow-right">➔</div>
        <div class="flow-card-wrapper">
            <div class="amount-badge">-</div>
            <div class="flow-card card-rpj">Agent Received, Process BAST & DN to Telkomsel</div>
            <div class="sla-label">SLA 1-2 D</div>
        </div>
        <div class="arrow-right">➔</div>
        <div class="flow-card-wrapper">
            <div class="amount-badge">{str_agent_tsel}</div>
            <div class="flow-card card-rpj">Agent Submit Doc Reimbursement</div>
            <div class="sla-label">SLA 1 D</div>
        </div>
    </div>
    <div class="arrow-down">↓</div>
    <div class="flow-row">
        <div class="flow-card-wrapper">
            <div style="font-size: 14px; margin-bottom: -6px; z-index: 11;">🏅</div>
            <div class="amount-badge">{str_payin_huawei}</div>
            <div class="flow-card card-rpj">Agent Paid to Huawei</div>
            <div class="sla-label">SLA 30 Days</div>
        </div>
        <div class="arrow-right">➔</div>
        <div class="flow-card-wrapper">
            <div class="amount-badge">{str_agent_tsel}</div>
            <div class="flow-card card-telkomsel">Telkomsel Paid to Agent</div>
            <div class="sla-label">SLA 2-4 Weeks</div>
        </div>
        <div class="arrow-right">➔</div>
        <div class="flow-card-wrapper">
            <div class="amount-badge">{str_dn_issued}</div>
            <div class="flow-card card-huawei">Huawei Send DN to Agent</div>
            <div class="sla-label">SLA 2-3 Days</div>
        </div>
        <div class="arrow-right">➔</div>
        <div class="flow-card-wrapper">
            <div class="amount-badge">{str_agent_tsel}</div>
            <div class="flow-card card-telkomsel">Received, Review and Submit in SAP by Telkomsel NOS</div>
            <div class="sla-label">SLA 1 Days</div>
        </div>
    </div>
</div>
<div class="legend-container">
    <div class="legend-item"><div class="legend-box" style="background-color: #dce6f1; border-color: #b8cce4;"></div> Huawei</div>
    <div class="legend-item"><div class="legend-box" style="background-color: #fff2cc; border-color: #ffe599;"></div> Telkomsel</div>
    <div class="legend-item"><div class="legend-box" style="background-color: #fce4d6; border-color: #f8c2a6;"></div> RPJ (Agent)</div>
</div>
</body>
</html>
"""

components.html(html_content, height=440, scrolling=False)

st.markdown("---")

# ==========================================
# 7. PAYOUT & PAYIN BY AREA
# ==========================================
st.subheader("📊 Payout (Bn IDR) & Payin (Bn IDR)")

if 'Area' in df_filtered.columns:
    raw_unique_areas = df_filtered['Area'].dropna().unique().tolist()
    unique_areas = sorted([str(x) for x in raw_unique_areas if str(x).lower() != 'nan'])
    
    def draw_area_donut(title, done_bn, ny_bn, color_main):
        total_bn = done_bn + ny_bn
        pct_done = (done_bn / total_bn * 100) if total_bn > 0 else 0.0
        
        st.markdown(f"""
            <div style='background-color: #f0f0f0; padding: 4px 10px; border-radius: 4px; text-align: center; font-weight: bold; font-size: 13px; color: #111;'>
                {title}
            </div>
        """, unsafe_allow_html=True)
        
        fig = go.Figure(data=[go.Pie(
            labels=['Done', 'Not Yet Paid'],
            values=[done_bn, ny_bn],
            hole=0.68,
            marker=dict(colors=[color_main, '#FFC000']),
            textinfo='none',
            hovertemplate="<b>%{label}</b><br>Nominal: %{value:.2f} Bn IDR<extra></extra>"
        )])
        
        fig.update_layout(
            annotations=[dict(
                text=f"<b>{pct_done:.1f}%</b>",
                x=0.5, y=0.5,
                font_size=14,
                showarrow=False,
                font_color="#000000"
            )],
            showlegend=False,
            margin=dict(l=10, r=10, t=10, b=10),
            height=160,
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)'
        )
        st.plotly_chart(fig, use_container_width=True, key=f"area_donut_{title}")
        
        st.markdown(f"""
            <div style='text-align: center; font-size: 11px; font-weight: bold; color: #222; margin-top: -10px;'>
                <span style='color: #888;'>NY: {ny_bn:,.2f}</span> | <span>Done: {done_bn:,.2f}</span>
            </div>
        """, unsafe_allow_html=True)

    st.markdown("""
        <style>
        .area-container {
            background-color: #a6a6a6;
            padding: 20px;
            border-radius: 12px;
            box-shadow: 0 4px 8px rgba(0,0,0,0.15);
        }
        </style>
    """, unsafe_allow_html=True)

    with st.container():
        st.markdown("<div class='area-container'>", unsafe_allow_html=True)
        
        for area_name in unique_areas:
            df_area = df_filtered[df_filtered['Area'] == area_name]
            
            col_amt_payout = 'Invoice Amount' if 'Invoice Amount' in df_area.columns else 'NET AMOUNT'
            if 'Status' in df_area.columns and col_amt_payout in df_area.columns:
                payout_series = pd.to_numeric(df_area[col_amt_payout], errors='coerce').fillna(0)
                mask_payout_done = df_area['Status'].astype(str).str.upper().str.strip() == 'PAID'
                payout_done_bn = payout_series[mask_payout_done].sum() / 1_000_000_000
                payout_ny_bn = payout_series[~mask_payout_done].sum() / 1_000_000_000
            else:
                payout_done_bn, payout_ny_bn = 0.0, 0.0

            col_amt_payin = 'NET AMOUNT'
            if 'Status Reimburse Actual' in df_area.columns and col_amt_payin in df_area.columns:
                payin_series = pd.to_numeric(df_area[col_amt_payin], errors='coerce').fillna(0)
                status_area_clean = df_area['Status Reimburse Actual'].astype(str).str.upper().str.strip()
                
                mask_payin_done = status_area_clean == 'PAID'
                mask_payin_ny = status_area_clean.isin(['DN ISSUED', 'NY ISSUE DN'])
                
                payin_done_bn = payin_series[mask_payin_done].sum() / 1_000_000_000
                payin_ny_bn = payin_series[mask_payin_ny].sum() / 1_000_000_000
            else:
                payin_done_bn, payin_ny_bn = 0.0, 0.0

            c_payout, c_payin = st.columns(2)
            with c_payout:
                draw_area_donut(f"Progress Payout {area_name}", payout_done_bn, payout_ny_bn, color_main='#70AD47')
            with c_payin:
                draw_area_donut(f"Progress Payin {area_name}", payin_done_bn, payin_ny_bn, color_main='#ED7D31')
            
            st.markdown("<br>", unsafe_allow_html=True)
            
        st.markdown("</div>", unsafe_allow_html=True)
else:
    st.warning("Kolom 'Area' tidak ditemukan pada dataset.")

st.markdown("---")

# ==========================================
# 8. INVOICE REGIONAL (INVOICE PROCESS)
# ==========================================
st.subheader("📊 Invoice Process (Invoice Regional)")

df_inv_reg = df_filtered.copy()

col_inv_agent = 'Invoice Agent'
if col_inv_agent in df_raw.columns:
    raw_agents = [str(x) for x in df_raw[col_inv_agent].dropna().unique().tolist()]
    list_inv_agent = ["INVOICE DONE", "(All)"] + [x for x in raw_agents if x != "INVOICE DONE"]
    
    selected_inv_agent = st.selectbox("Filter Invoice Agent", options=list_inv_agent, index=0)
    
    if selected_inv_agent != "(All)":
        df_inv_reg = df_inv_reg[df_inv_reg[col_inv_agent].astype(str).str.upper().str.strip() == selected_inv_agent.upper().strip()]

col_reg = 'new regional'
col_status_sap = 'StatusSAP'
col_net_amt = 'NET AMOUNT'

if col_reg in df_inv_reg.columns and col_status_sap in df_inv_reg.columns and col_net_amt in df_inv_reg.columns:
    df_inv_reg[col_net_amt] = pd.to_numeric(df_inv_reg[col_net_amt], errors='coerce').fillna(0)
    
    target_order = [
        "R03_Jakarta Banten",
        "R12_Eastern Jabotabek",
        "R04_Jawa Barat",
        "R08_Kalimantan",
        "R09_Sulawesi",
        "R11_Maluku dan Papua"

    ]
    
    available_regionals = df_inv_reg[col_reg].dropna().unique().tolist()
    ordered_regionals = [r for r in target_order if r in available_regionals]
    for r in available_regionals:
        if r not in ordered_regionals and str(r).lower() != 'nan':
            ordered_regionals.append(r)
    
    st.markdown("""
        <style>
        .regional-container {
            background-color: #a6a6a6;
            padding: 20px;
            border-radius: 12px;
            box-shadow: 0 4px 8px rgba(0,0,0,0.15);
        }
        .regional-card-title {
            background-color: #ffffff;
            color: #000000;
            text-align: center;
            font-weight: bold;
            font-size: 14px;
            padding: 6px;
            border-radius: 4px;
            margin-bottom: 10px;
            text-decoration: underline;
        }
        </style>
    """, unsafe_allow_html=True)

    with st.container():
        st.markdown("<div class='regional-container'>", unsafe_allow_html=True)
        
        num_cols = 3
        cols = st.columns(num_cols)
        
        for idx, reg_name in enumerate(ordered_regionals):
            col_target = cols[idx % num_cols]
            
            df_reg = df_inv_reg[df_inv_reg[col_reg].astype(str) == reg_name]
            status_sap_clean = df_reg[col_status_sap].astype(str).str.upper().str.strip()
            
            mask_done = status_sap_clean.isin(['CLEARED', 'PAID', 'CLEARED/PAID'])
            done_val = df_reg[mask_done][col_net_amt].sum()
            done_m = done_val / 1_000_000_000
            
            ny_val = df_reg[~mask_done][col_net_amt].sum()
            ny_m = ny_val / 1_000_000_000
            
            total_m = done_m + ny_m
            pct_done = (done_m / total_m * 100) if total_m > 0 else 0.0
            
            text_done = f"{done_m:.2f}".replace('.', ',')
            text_ny = f"{ny_m:.2f}".replace('.', ',')
            
            with col_target:
                st.markdown(f"<div class='regional-card-title'>{reg_name}</div>", unsafe_allow_html=True)
                
                color_ny = '#E67E22' if idx >= 3 else '#A6A6A6'
                
                fig = go.Figure(data=[go.Pie(
                    labels=['Cleared/Paid', 'Not Yet Paid'],
                    values=[done_m, ny_m],
                    text=[text_done, text_ny],
                    textinfo='text',
                    textposition='inside',
                    hole=0.65,
                    marker=dict(colors=['#2F5597', color_ny]),
                    hovertemplate="<b>%{label}</b><br>Nominal: Rp %{value:.2f} M<extra></extra>"
                )])
                
                fig.update_layout(
                    annotations=[dict(
                        text=f"<b>{pct_done:.2f}%</b>".replace('.', ','),
                        x=0.5, y=0.5,
                        font_size=15,
                        showarrow=False,
                        font_color="#000000"
                    )],
                    showlegend=False,
                    margin=dict(l=10, r=10, t=10, b=10),
                    height=200,
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)'
                )
                
                st.plotly_chart(fig, use_container_width=True, key=f"regional_donut_{idx}_{reg_name}")
                st.markdown("<br>", unsafe_allow_html=True)
                
        st.markdown("</div>", unsafe_allow_html=True)
else:
    st.warning("Kolom 'new regional', 'StatusSAP', atau 'NET AMOUNT' tidak ditemukan dalam dataset.")

st.markdown("---")

# ==========================================
# 9. PROCESS REIMBURSEMENT SUMMARY TABLE (BERWARNA)
# ==========================================
st.subheader("📊 Process Reimbursement Summary")

def generate_reimbursement_summary_table(df):
    df_calc = df.copy()

    # 1. Bersihkan & Petakan Kolom Numerik (Logika & Formula Asli)
    num_cols = ['NET AMOUNT', 'Amount SAP', 'Amount Paid Based on Setoff Data', 'Amount Paid']
    for col in num_cols:
        if col == 'Amount Paid' and col not in df_calc.columns and 'Amount Actual Paid' in df_calc.columns:
            df_calc['Amount Paid'] = pd.to_numeric(df_calc['Amount Actual Paid'], errors='coerce').fillna(0)
        elif col in df_calc.columns:
            df_calc[col] = pd.to_numeric(df_calc[col], errors='coerce').fillna(0)
        else:
            df_calc[col] = 0

    # 2. Filter Khusus Kolom Amount SAP berdasarkan Status SAP ("CLEARED" atau "PAID")
    col_status_sap = 'StatusSAP' if 'StatusSAP' in df_calc.columns else ('Status SAP' if 'Status SAP' in df_calc.columns else None)
    if col_status_sap:
        sap_status_clean = df_calc[col_status_sap].astype(str).str.upper().str.strip()
        mask_sap_cleared = sap_status_clean.isin(['CLEARED', 'PAID', 'CLEARED/PAID'])
        df_calc['Amount SAP Filtered'] = np.where(mask_sap_cleared, df_calc['Amount SAP'], 0)
    else:
        df_calc['Amount SAP Filtered'] = df_calc['Amount SAP']

    # 3. Identifikasi Kolom Payment Month
    col_m = 'Payment Month' if 'Payment Month' in df_calc.columns else ('Month' if 'Month' in df_calc.columns else 'Periode Month')
    if col_m not in df_calc.columns:
        st.warning("Kolom Payment Month tidak ditemukan.")
        return pd.DataFrame(), col_m

    # 4. GroupBy berdasarkan Rows: Payment Month & Values: Sum of Kolom
    summary = df_calc.groupby(col_m, as_index=False, dropna=False).agg({
        'NET AMOUNT': 'sum',
        'Amount SAP Filtered': 'sum',
        'Amount Paid Based on Setoff Data': 'sum',
        'Amount Paid': 'sum'
    })

    # 5. Pengurutan Kronologis Payment Month (Lama -> Baru)
    summary['date_parsed'] = pd.to_datetime(summary[col_m].astype(str), format='%b-%y', errors='coerce')
    valid_dates = summary[summary['date_parsed'].notna()].sort_values('date_parsed', ascending=True)
    invalid_dates = summary[summary['date_parsed'].isna()]
    
    summary = pd.concat([valid_dates, invalid_dates], ignore_index=True)
    summary = summary.drop(columns=['date_parsed'])

    # 6. Formulas: Hitung GAP = Sum of NET AMOUNT - Sum of Amount Paid Based on Setoff Data
    summary['GAP'] = summary['NET AMOUNT'] - summary['Amount Paid Based on Setoff Data']

    # 7. Baris Grand Total
    grand_total = pd.DataFrame([{
        col_m: 'Grand Total',
        'NET AMOUNT': summary['NET AMOUNT'].sum(),
        'Amount SAP Filtered': summary['Amount SAP Filtered'].sum(),
        'Amount Paid Based on Setoff Data': summary['Amount Paid Based on Setoff Data'].sum(),
        'Amount Paid': summary['Amount Paid'].sum(),
        'GAP': summary['GAP'].sum()
    }])

    summary_final = pd.concat([summary, grand_total], ignore_index=True)

    return summary_final, col_m

# Menghasilkan Dataframe Raw (Angka Murni)
df_summary_raw, col_month_name = generate_reimbursement_summary_table(df_filtered)

if not df_summary_raw.empty:
    # Helper Format Rupiah Sesuai Excel/Gambar
    def fmt_rp(val):
        if abs(val) < 1e-9:
            return "Rp -"
        elif val < 0:
            return f"-Rp {abs(val):,.0f}".replace(",", ".")
        else:
            return f"Rp {val:,.0f}".replace(",", ".")

    # Render Tabel HTML Berwarna
    rows_html = ""
    for idx, row in df_summary_raw.iterrows():
        val_m = row[col_month_name]
        is_total = (val_m == 'Grand Total')
        
        # Penanganan Label Kosong/None
        if pd.isna(val_m) or str(val_m).strip().lower() in ['nan', 'none', '']:
            val_m = "(blank)"

        row_class = "row-total" if is_total else ("row-even" if idx % 2 == 0 else "row-odd")

        rows_html += f"""
        <tr class="{row_class}">
            <td class="align-center">{val_m}</td>
            <td class="align-right col-bold">{fmt_rp(row['NET AMOUNT'])}</td>
            <td class="align-right">{fmt_rp(row['Amount SAP Filtered'])}</td>
            <td class="align-right">{fmt_rp(row['Amount Paid Based on Setoff Data'])}</td>
            <td class="align-right">{fmt_rp(row['Amount Paid'])}</td>
            <td class="align-right col-bold">{fmt_rp(row['GAP'])}</td>
        </tr>
        """

    full_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 0; padding: 0; background-color: transparent; }}
        .process-table {{ width: 100%; border-collapse: collapse; font-size: 11px; color: #000000; }}
        .process-table th, .process-table td {{ border: 1px solid #7f7f7f; padding: 5px 8px; white-space: nowrap; }}
        
        /* Stylings & Colors Sesuai Excel */
        .hdr-month {{ background-color: #d9e1f2; font-weight: bold; text-align: center; vertical-align: middle; }}
        .hdr-blue {{ background-color: #b4c6e7; font-weight: bold; text-align: center; vertical-align: middle; }}
        
        .row-total {{ font-weight: bold; background-color: #b4c6e7; }}
        .row-even {{ background-color: #ffffff; }}
        .row-odd {{ background-color: #f2f2f2; }}
        
        .align-center {{ text-align: center; }}
        .align-right {{ text-align: right; }}
        .col-bold {{ font-weight: bold; }}
    </style>
    </head>
    <body>
    <div style="overflow-x: auto;">
        <table class="process-table">
            <thead>
                <tr>
                    <th class="hdr-month" style="width: 12%;">Payment Month</th>
                    <th class="hdr-blue" style="width: 18%;">Sum of NET AMOUNT</th>
                    <th class="hdr-blue" style="width: 20%;">Sum of Amount SAP (Cleared/Paid)</th>
                    <th class="hdr-blue" style="width: 22%;">Sum of Amount Paid Based on Setoff Data</th>
                    <th class="hdr-blue" style="width: 16%;">Sum of Amount Paid</th>
                    <th class="hdr-blue" style="width: 12%;">GAP</th>
                </tr>
            </thead>
            <tbody>
                {rows_html}
            </tbody>
        </table>
    </div>
    </body>
    </html>
    """

    calc_height = min(750, max(200, (len(df_summary_raw) + 2) * 28))
    components.html(full_html, height=calc_height, scrolling=True)

# ==========================================
# 10. REIMBURSEMENT TO TSEL & REIMBURSEMENT TO AGENT
# ==========================================
st.subheader("📊 Reimbursement Summary to TSEL & Agent")

def render_tsel_agent_html_table(df):
    if df.empty:
        st.info("Data tidak tersedia untuk filter yang dipilih.")
        return

    df_calc = df.copy()

    # 1. Pastikan Kolom Numerik
    if 'NET AMOUNT' in df_calc.columns:
        df_calc['NET AMOUNT'] = pd.to_numeric(df_calc['NET AMOUNT'], errors='coerce').fillna(0)
    else:
        df_calc['NET AMOUNT'] = 0

    # 2. Identifikasi Kolom Payment Month
    col_m = 'Payment Month' if 'Payment Month' in df_calc.columns else ('Month' if 'Month' in df_calc.columns else 'Periode Month')
    if col_m not in df_calc.columns:
        st.warning(f"Kolom '{col_m}' tidak ditemukan dalam dataset.")
        return

    # 3. Logika Filter Reimbursement to TSEL
    col_inv_agent = 'Invoice Agent' if 'Invoice Agent' in df_calc.columns else None
    if col_inv_agent:
        inv_clean = df_calc[col_inv_agent].astype(str).str.upper().str.strip()
        mask_inv_done = inv_clean == 'INVOICE DONE'
        mask_inv_ny = inv_clean.isin(['NY INVOICE', 'NY INVOICE DONE', 'NOT YET INVOICE']) | (~mask_inv_done)
        
        df_calc['INV. DONE'] = np.where(mask_inv_done, df_calc['NET AMOUNT'], 0)
        df_calc['INV. NY'] = np.where(mask_inv_ny, df_calc['NET AMOUNT'], 0)
    else:
        df_calc['INV. DONE'] = 0
        df_calc['INV. NY'] = 0

    # 4. Logika Filter Reimbursement to Agent
    col_dn_hw = 'DN HW' if 'DN HW' in df_calc.columns else ('Status Reimburse Actual' if 'Status Reimburse Actual' in df_calc.columns else None)
    if col_dn_hw:
        dn_clean = df_calc[col_dn_hw].astype(str).str.upper().str.strip()
        mask_dn_done = dn_clean.isin(['DEBITNOTE DONE', 'DN ISSUED', 'PAID', 'DONE'])
        mask_dn_ny = ~mask_dn_done
        
        df_calc['DebitNote DONE'] = np.where(mask_dn_done, df_calc['NET AMOUNT'], 0)
        df_calc['DebitNote NY'] = np.where(mask_dn_ny, df_calc['NET AMOUNT'], 0)
    else:
        df_calc['DebitNote DONE'] = 0
        df_calc['DebitNote NY'] = 0

    # 5. GroupBy berdasarkan Periode Month
    summary = df_calc.groupby(col_m, as_index=False, dropna=False).agg({
        'NET AMOUNT': 'sum',
        'INV. DONE': 'sum',
        'INV. NY': 'sum',
        'DebitNote DONE': 'sum',
        'DebitNote NY': 'sum'
    })

    # 6. Urutkan berdasarkan Periode Month
    summary['date_parsed'] = pd.to_datetime(summary[col_m].astype(str), format='%b-%y', errors='coerce')
    valid_dates = summary[summary['date_parsed'].notna()].sort_values('date_parsed', ascending=True)
    invalid_dates = summary[summary['date_parsed'].isna()]
    summary = pd.concat([valid_dates, invalid_dates], ignore_index=True).drop(columns=['date_parsed'])

    # 7. Hitung Grand Total
    grand_total = pd.DataFrame([{
        col_m: 'Grand Total',
        'NET AMOUNT': summary['NET AMOUNT'].sum(),
        'INV. DONE': summary['INV. DONE'].sum(),
        'INV. NY': summary['INV. NY'].sum(),
        'DebitNote DONE': summary['DebitNote DONE'].sum(),
        'DebitNote NY': summary['DebitNote NY'].sum()
    }])

    summary_final = pd.concat([summary, grand_total], ignore_index=True)

    # 8. Hitung Formula Persentase
    summary_final['% Done TSEL'] = np.where(
        summary_final['NET AMOUNT'] > 0,
        (summary_final['INV. DONE'] / summary_final['NET AMOUNT']) * 100,
        0.0
    )
    
    summary_final['% Done Agent'] = np.where(
        summary_final['NET AMOUNT'] > 0,
        (summary_final['DebitNote DONE'] / summary_final['NET AMOUNT']) * 100,
        0.0
    )

    # 9. Susun HTML Lengkap dengan Struktur Dokumen
    rows_html = ""
    for idx, row in summary_final.iterrows():
        is_total = (row[col_m] == 'Grand Total')
        row_class = "row-total" if is_total else ("row-even" if idx % 2 == 0 else "row-odd")
        
        fmt_net = f"Rp {row['NET AMOUNT']:,.0f}".replace(",", ".") if row['NET AMOUNT'] != 0 else "Rp -"
        fmt_inv_done = f"Rp {row['INV. DONE']:,.0f}".replace(",", ".") if row['INV. DONE'] != 0 else "Rp -"
        fmt_inv_ny = f"Rp {row['INV. NY']:,.0f}".replace(",", ".") if row['INV. NY'] != 0 else "Rp -"
        fmt_dn_done = f"Rp {row['DebitNote DONE']:,.0f}".replace(",", ".") if row['DebitNote DONE'] != 0 else "Rp -"
        fmt_dn_ny = f"Rp {row['DebitNote NY']:,.0f}".replace(",", ".") if row['DebitNote NY'] != 0 else "Rp -"
        
        fmt_pct_tsel = f"{row['% Done TSEL']:.2f}%".replace(".", ",")
        fmt_pct_agent = f"{row['% Done Agent']:.2f}%".replace(".", ",")

        rows_html += f"""
        <tr class="{row_class}">
            <td class="align-left">{row[col_m]}</td>
            <td class="align-right">{fmt_net}</td>
            <td class="align-right">{fmt_inv_done}</td>
            <td class="align-right">{fmt_inv_ny}</td>
            <td class="cell-pct-tsel">{fmt_pct_tsel}</td>
            <td class="align-right">{fmt_dn_done}</td>
            <td class="align-right">{fmt_dn_ny}</td>
            <td class="cell-pct-agent">{fmt_pct_agent}</td>
        </tr>
        """

    full_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 0; padding: 0; background-color: transparent; }}
        .tsel-agent-table {{ width: 100%; border-collapse: collapse; font-size: 11px; color: #000000; }}
        .tsel-agent-table th, .tsel-agent-table td {{ border: 1px solid #a6a6a6; padding: 5px 7px; white-space: nowrap; }}
        .hdr-main {{ background-color: #d9d9d9; font-weight: bold; text-align: center; vertical-align: middle; }}
        .hdr-tsel {{ background-color: #f7b267; font-weight: bold; text-align: center; vertical-align: middle; }}
        .hdr-agent {{ background-color: #90be6d; font-weight: bold; text-align: center; vertical-align: middle; }}
        
        .row-total {{ font-weight: bold; background-color: #d9e1f2; }}
        .row-even {{ background-color: #ffffff; }}
        .row-odd {{ background-color: #f2f2f2; }}
        
        .align-left {{ text-align: left; }}
        .align-right {{ text-align: right; }}
        
        .cell-pct-tsel {{ background-color: #fce5cd; text-align: center; font-weight: bold; }}
        .cell-pct-agent {{ background-color: #e2f0d9; text-align: center; font-weight: bold; }}
    </style>
    </head>
    <body>
    <div style="overflow-x: auto;">
        <table class="tsel-agent-table">
            <thead>
                <tr>
                    <th rowspan="2" class="hdr-main">Periode Month</th>
                    <th rowspan="2" class="hdr-main">NET AMOUNT</th>
                    <th colspan="3" class="hdr-tsel">Reimbursement to TSEL</th>
                    <th colspan="3" class="hdr-agent">Reimbursement to Agent</th>
                </tr>
                <tr>
                    <th class="hdr-tsel">INV. DONE</th>
                    <th class="hdr-tsel">INV. NY</th>
                    <th class="hdr-tsel">% Done</th>
                    <th class="hdr-agent">DebitNote DONE</th>
                    <th class="hdr-agent">DebitNote NY</th>
                    <th class="hdr-agent">% Done</th>
                </tr>
            </thead>
            <tbody>
                {rows_html}
            </tbody>
        </table>
    </div>
    </body>
    </html>
    """

    # Hitung tinggi dinamis berdasarkan jumlah baris (agar tidak terpotong)
    calc_height = min(600, max(200, (len(summary_final) + 3) * 32))
    components.html(full_html, height=calc_height, scrolling=True)

# Panggil fungsi
render_tsel_agent_html_table(df_filtered)

import streamlit as st
import pandas as pd
import numpy as np
import streamlit.components.v1 as components

# ==========================================
# RISK VAT HUAWEI FULL TABLE MODULE (CLEAN)
# ==========================================
def render_risk_vat_huawei_full_table(df_input):
    if df_input is None or df_input.empty:
        st.info("Data tidak tersedia untuk filter global yang dipilih.")
        return

    df_calc = df_input.copy()

    # 1. Pastikan Kolom Numerik
    for col in ['NET AMOUNT', 'NET-PPN', 'PPN']:
        if col in df_calc.columns:
            df_calc[col] = pd.to_numeric(df_calc[col], errors='coerce').fillna(0.0)
        else:
            df_calc[col] = 0.0

    # 2. Identifikasi Kolom Utama
    col_m = 'Payment Month' if 'Payment Month' in df_calc.columns else ('Month' if 'Month' in df_calc.columns else 'Periode Month')
    col_fp = 'Status FP' if 'Status FP' in df_calc.columns else ('Status Faktur Pajak' if 'Status Faktur Pajak' in df_calc.columns else 'Status FP Actual')

    if col_m not in df_calc.columns:
        st.warning(f"Kolom Periode Month ('{col_m}') tidak ditemukan dalam dataset.")
        return

    # 3. Pengelompokan Logika Status FP
    if col_fp in df_calc.columns:
        fp_clean = df_calc[col_fp].astype(str).str.upper().str.strip()
        
        mask_normal = fp_clean.isin(['NORMAL', 'FP NORMAL', 'VALID'])
        mask_potential = fp_clean.isin(['POTENTIAL EXPIRED', 'POTENTIAL', 'POTENTIAL EXPIRED FP'])
        mask_expired = fp_clean.isin(['FP EXPIRED', 'EXPIRED'])

        df_calc['NET_NORMAL'] = np.where(mask_normal, df_calc['NET AMOUNT'], 0.0)
        df_calc['NET_POTENTIAL'] = np.where(mask_potential, df_calc['NET AMOUNT'], 0.0)
        df_calc['NET_EXPIRED'] = np.where(mask_expired, df_calc['NET AMOUNT'], 0.0)

        # FP Exp Net Amount (NET-PPN) & VAT Loss (PPN) saat Status FP Expired
        df_calc['FP_EXP_NET_PPN'] = np.where(mask_expired, df_calc['NET-PPN'], 0.0)
        df_calc['FP_EXP_PPN'] = np.where(mask_expired, df_calc['PPN'], 0.0)
    else:
        df_calc['NET_NORMAL'] = 0.0
        df_calc['NET_POTENTIAL'] = 0.0
        df_calc['NET_EXPIRED'] = 0.0
        df_calc['FP_EXP_NET_PPN'] = 0.0
        df_calc['FP_EXP_PPN'] = 0.0

    # 4. Agregasi GroupBy berdasarkan Periode Month
    summary = df_calc.groupby(col_m, as_index=False, dropna=False).agg({
        'NET_NORMAL': 'sum',
        'NET_POTENTIAL': 'sum',
        'NET_EXPIRED': 'sum',
        'NET AMOUNT': 'sum',
        'FP_EXP_NET_PPN': 'sum',
        'FP_EXP_PPN': 'sum'
    })

    # 5. Urutkan berdasarkan Kronologis Bulan
    summary['date_parsed'] = pd.to_datetime(summary[col_m].astype(str), format='%b-%y', errors='coerce')
    valid_dates = summary[summary['date_parsed'].notna()].sort_values('date_parsed', ascending=True)
    invalid_dates = summary[summary['date_parsed'].isna()]
    summary = pd.concat([valid_dates, invalid_dates], ignore_index=True).drop(columns=['date_parsed'])

    # 6. Hitung Baris Grand Total
    grand_total = pd.DataFrame([{
        col_m: 'Grand Total',
        'NET_NORMAL': summary['NET_NORMAL'].sum(),
        'NET_POTENTIAL': summary['NET_POTENTIAL'].sum(),
        'NET_EXPIRED': summary['NET_EXPIRED'].sum(),
        'NET AMOUNT': summary['NET AMOUNT'].sum(),
        'FP_EXP_NET_PPN': summary['FP_EXP_NET_PPN'].sum(),
        'FP_EXP_PPN': summary['FP_EXP_PPN'].sum()
    }])

    summary_final = pd.concat([summary, grand_total], ignore_index=True)

    # Helper Format Rupiah
    def fmt_rp(val):
        if abs(val) < 1e-9:
            return "Rp -"
        elif val < 0:
            return f"-Rp {abs(val):,.0f}".replace(",", ".")
        else:
            return f"Rp {val:,.0f}".replace(",", ".")

    # 7. Susun Baris HTML (Tanpa Kolom Persentase)
    rows_html = ""
    for idx, row in summary_final.iterrows():
        is_total = (row[col_m] == 'Grand Total')
        row_class = "row-total" if is_total else ("row-even" if idx % 2 == 0 else "row-odd")

        rows_html += f"""
        <tr class="{row_class}">
            <td class="align-left">{row[col_m]}</td>
            <td class="align-right">{fmt_rp(row['NET_NORMAL'])}</td>
            <td class="align-right">{fmt_rp(row['NET_POTENTIAL'])}</td>
            <td class="align-right">{fmt_rp(row['NET_EXPIRED'])}</td>
            <td class="align-right col-bold">{fmt_rp(row['NET AMOUNT'])}</td>
            <td class="align-right">{fmt_rp(row['FP_EXP_NET_PPN'])}</td>
            <td class="align-right">{fmt_rp(row['FP_EXP_PPN'])}</td>
        </tr>
        """

    # 8. HTML & CSS Lengkap dengan Header Multi-Level
    full_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 0; padding: 0; background-color: transparent; }}
        .vat-full-table {{ width: 100%; border-collapse: collapse; font-size: 11px; color: #000000; }}
        .vat-full-table th, .vat-full-table td {{ border: 1px solid #7f7f7f; padding: 5px 8px; white-space: nowrap; }}
        
        .hdr-main {{ background-color: #d9d9d9; font-weight: bold; text-align: center; vertical-align: middle; }}
        .hdr-orange {{ background-color: #f6b26b; font-weight: bold; text-align: center; vertical-align: middle; color: #000000; }}
        .hdr-yellow {{ background-color: #ffff00; font-weight: bold; text-align: center; vertical-align: middle; color: #000000; }}
        
        .row-total {{ font-weight: bold; background-color: #d9e1f2; }}
        .row-even {{ background-color: #ffffff; }}
        .row-odd {{ background-color: #f2f2f2; }}
        
        .align-left {{ text-align: left; }}
        .align-right {{ text-align: right; }}
        .col-bold {{ font-weight: bold; }}
    </style>
    </head>
    <body>
    <div style="overflow-x: auto;">
        <table class="vat-full-table">
            <thead>
                <tr>
                    <th rowspan="2" class="hdr-main" style="width: 12%;">Periode Month</th>
                    <th colspan="4" class="hdr-orange">Net Amount</th>
                    <th rowspan="2" class="hdr-yellow" style="width: 20%;">FP Exp Net Amount-<br>VAT(ppn)</th>
                    <th rowspan="2" class="hdr-yellow" style="width: 18%;">VAT Loss</th>
                </tr>
                <tr>
                    <th class="hdr-orange">Normal</th>
                    <th class="hdr-orange">Potential Expired</th>
                    <th class="hdr-orange">FP Expired</th>
                    <th class="hdr-orange">Total Net Amount</th>
                </tr>
            </thead>
            <tbody>
                {rows_html}
            </tbody>
        </table>
    </div>
    </body>
    </html>
    """

    calc_height = min(750, max(220, (len(summary_final) + 3) * 32))
    components.html(full_html, height=calc_height, scrolling=True)


# ==========================================
# CARA PEMANGGILAN DENGAN FILTER GLOBAL
# ==========================================
st.title("🛡️ Risk VAT Huawei Summary")

# Mengambil DataFrame yang sudah terfilter secara Global dari aplikasi Anda
# Ganti 'df_filtered' dengan nama variabel DataFrame hasil filter global di bagian atas script Anda
if 'df_filtered' in locals() or 'df_filtered' in globals():
    render_risk_vat_huawei_full_table(df_filtered)
elif 'df_selection' in locals() or 'df_selection' in globals():
    render_risk_vat_huawei_full_table(df_selection)
elif 'df' in locals() or 'df' in globals():
    render_risk_vat_huawei_full_table(df)
else:
    st.error("Data Global tidak ditemukan. Pastikan variabel DataFrame utama didefinisikan di bagian atas.")

# ==========================================
# 10. MANAGEMENT FEE PROCESS TABLE
# ==========================================
st.subheader("📊 Management Fee Process")

# 1. Tambahkan Filter Area
if 'Area' in df_filtered.columns:
    area_options = ['All'] + list(df_filtered['Area'].dropna().unique())
    selected_area = st.selectbox("Filter Area:", options=area_options, key="manfee_area_filter")
    
    if selected_area != 'All':
        df_manfee = df_filtered[df_filtered['Area'] == selected_area].copy()
    else:
        df_manfee = df_filtered.copy()
else:
    df_manfee = df_filtered.copy()

def generate_management_fee_table(df):
    df_calc = df.copy()

    # 2. Identifikasi Kolom Month & Progress Status
    col_m = 'Payment Month' if 'Payment Month' in df_calc.columns else ('Month' if 'Month' in df_calc.columns else 'Periode Month')
    col_status = 'Progress PR Status (RPJ to HTI)' if 'Progress PR Status (RPJ to HTI)' in df_calc.columns else 'Progress PR Status'

    if col_m not in df_calc.columns:
        st.warning("Kolom Payment Month tidak ditemukan.")
        return pd.DataFrame(), col_m

    # 3. Kategori Payment Status: 'Paid' vs 'Not Yet'
    if col_status in df_calc.columns:
        status_clean = df_calc[col_status].astype(str).str.upper().str.strip()
        # Jika status mengandung 'PAID' atau 'SETTLED', masuk kategori 'Paid', sisanya 'Not Yet'
        df_calc['Status_Group'] = np.where(status_clean.str.contains('PAID|SETTLED', na=False), 'Paid', 'Not Yet')
    else:
        df_calc['Status_Group'] = 'Not Yet'

    # 4. Pastikan Kolom Values Tersedia & Numerik
    val_cols = {
        'Total Manfee': 'Total Manfee' if 'Total Manfee' in df_calc.columns else 'Total Management Fee',
        'AGENT Share': 'AGENT Share' if 'AGENT Share' in df_calc.columns else 'Agent Share',
        'Huawei Share': 'Huawei Share' if 'Huawei Share' in df_calc.columns else 'Huawei Share'
    }

    for key, col_name in val_cols.items():
        if col_name in df_calc.columns:
            df_calc[key] = pd.to_numeric(df_calc[col_name], errors='coerce').fillna(0)
        else:
            df_calc[key] = 0

    # 5. Pivot Table berdasarkan Payment Month x Status_Group (Not Yet / Paid)
    pivot = df_calc.pivot_table(
        index=col_m,
        columns='Status_Group',
        values=['Total Manfee', 'AGENT Share', 'Huawei Share'],
        aggfunc='sum',
        fill_value=0
    )

    # 6. Pastikan Struktur Kolom Lengkap (Not Yet & Paid untuk Setiap Metric)
    expected_cols = [
        ('Total Manfee', 'Not Yet'), ('Total Manfee', 'Paid'),
        ('AGENT Share', 'Not Yet'), ('AGENT Share', 'Paid'),
        ('Huawei Share', 'Not Yet'), ('Huawei Share', 'Paid')
    ]
    
    for col in expected_cols:
        if col not in pivot.columns:
            pivot[col] = 0.0

    pivot = pivot[expected_cols].reset_index()

    # 7. Pengurutan Kronologis Payment Month
    pivot['date_parsed'] = pd.to_datetime(pivot[col_m].astype(str), format='%b-%y', errors='coerce')
    valid_dates = pivot[pivot['date_parsed'].notna()].sort_values('date_parsed', ascending=True)
    invalid_dates = pivot[pivot['date_parsed'].isna()]
    
    pivot = pd.concat([valid_dates, invalid_dates], ignore_index=True)
    pivot = pivot.drop(columns=['date_parsed'])

    # 8. Hitung Grand Total
    grand_total_data = {col_m: 'Grand Total'}
    for col in expected_cols:
        grand_total_data[col] = pivot[col].sum()
    
    grand_total_df = pd.DataFrame([grand_total_data])
    pivot_final = pd.concat([pivot, grand_total_df], ignore_index=True)

    return pivot_final, col_m

# Olah data Management Fee
df_manfee_raw, col_m_name = generate_management_fee_table(df_manfee)

if not df_manfee_raw.empty:
    # Helper Format Rupiah Sesuai Gambar
    def fmt_rp_mf(val):
        if abs(val) < 1e-9:
            return "Rp -"
        elif val < 0:
            return f"-Rp {abs(val):,.0f}".replace(",", ".")
        else:
            return f"Rp {val:,.0f}".replace(",", ".")

    # Render HTML Rows
    rows_mf_html = ""
    for idx, row in df_manfee_raw.iterrows():
        val_m = row[(col_m_name, '')] if (col_m_name, '') in row.index else row[col_m_name]
        is_total = (val_m == 'Grand Total')
        
        if pd.isna(val_m) or str(val_m).strip().lower() in ['nan', 'none', '']:
            val_m = "(blank)"

        row_class = "row-total" if is_total else ("row-even" if idx % 2 == 0 else "row-odd")

        rows_mf_html += f"""
        <tr class="{row_class}">
            <td class="align-center">{val_m}</td>
            <td class="align-right col-bold">{fmt_rp_mf(row[('Total Manfee', 'Not Yet')])}</td>
            <td class="align-right col-bold">{fmt_rp_mf(row[('Total Manfee', 'Paid')])}</td>
            <td class="align-right">{fmt_rp_mf(row[('AGENT Share', 'Not Yet')])}</td>
            <td class="align-right">{fmt_rp_mf(row[('AGENT Share', 'Paid')])}</td>
            <td class="align-right">{fmt_rp_mf(row[('Huawei Share', 'Not Yet')])}</td>
            <td class="align-right">{fmt_rp_mf(row[('Huawei Share', 'Paid')])}</td>
        </tr>
        """

    full_mf_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <style>
        body {{ 
            font-family: Arial, sans-serif; 
            margin: 0; 
            padding: 0; 
            background-color: transparent; 
        }}
        .manfee-table {{ 
            width: 100%; 
            border-collapse: collapse; 
            font-size: 11px; 
            color: #000000; 
        }}
        .manfee-table th, .manfee-table td {{ 
            border: 1px solid #7f7f7f; 
            padding: 4px 8px; 
            white-space: nowrap; 
        }}
        
        /* Stylings & Colors Header Sesuai Gambar Excel */
        .hdr-main {{ background-color: #ffffff; font-weight: bold; text-align: center; vertical-align: middle; font-size: 14px; }}
        .hdr-periode {{ background-color: #f2f2f2; font-weight: bold; text-align: center; vertical-align: middle; }}
        
        .hdr-manfee {{ background-color: #ffe699; font-weight: bold; text-align: center; }}
        .hdr-agent {{ background-color: #d9e1f2; font-weight: bold; text-align: center; }}
        .hdr-huawei {{ background-color: #fce4d6; font-weight: bold; text-align: center; }}
        
        .row-total {{ font-weight: bold; background-color: #ffffff; border-top: 2px solid #000; }}
        .row-even {{ background-color: #ffffff; }}
        .row-odd {{ background-color: #f9f9f9; }}
        
        .align-center {{ text-align: center; }}
        .align-right {{ text-align: right; }}
        .col-bold {{ font-weight: bold; }}
    </style>
    </head>
    <body>
    <div style="overflow-x: auto;">
        <table class="manfee-table">
            <thead>
                <tr>
                    <th colspan="7" class="hdr-main">Management Fee</th>
                </tr>
                <tr>
                    <th rowspan="2" class="hdr-periode" style="width: 10%;">Periode</th>
                    <th colspan="2" class="hdr-manfee">Sum of Total Manfee</th>
                    <th colspan="2" class="hdr-agent">Sum of AGENT Share</th>
                    <th colspan="2" class="hdr-huawei">Sum of Huawei Share</th>
                </tr>
                <tr>
                    <th class="hdr-manfee" style="width: 15%;">Not Yet</th>
                    <th class="hdr-manfee" style="width: 15%;">Paid</th>
                    <th class="hdr-agent" style="width: 15%;">Not Yet</th>
                    <th class="hdr-agent" style="width: 15%;">Paid</th>
                    <th class="hdr-huawei" style="width: 15%;">Not Yet</th>
                    <th class="hdr-huawei" style="width: 15%;">Paid</th>
                </tr>
            </thead>
            <tbody>
                {rows_mf_html}
            </tbody>
        </table>
    </div>
    </body>
    </html>
    """

    calc_height_mf = min(750, max(200, (len(df_manfee_raw) + 4) * 28))
    components.html(full_mf_html, height=calc_height_mf, scrolling=True)


import streamlit as st
import pandas as pd
import numpy as np
import streamlit.components.v1 as components


import streamlit as st
import pandas as pd
import numpy as np
import streamlit.components.v1 as components


import pandas as pd
import streamlit as st

# ==============================================================================
# SECTION: STATUS REJECTION SAP (Independent Filter)
# ==============================================================================
st.markdown("---")
st.title("Status Rejection SAP")

# 1. Filter awal khusus SAP Rejected langsung dari data mentah
df_sap_base = df_raw[df_raw["StatusSAP"] == "Rejected"].copy()

# Format IBS Invoice Type menjadi 3 digit (misal: 10 -> 010)
df_sap_base["IBS Invoice Type"] = (
    df_sap_base["IBS Invoice Type"]
    .astype(str)
    .str.split(".")
    .str[0]
    .str.zfill(3)
)

# 2. Filter Khusus Section SAP (Tidak Terhubung ke Filter Global)
st.subheader("Filter Rejection SAP")

col_sap_filter1, col_sap_filter2 = st.columns(2)

with col_sap_filter1:
    list_sap_area = df_sap_base["Area"].dropna().unique().tolist()
    # Menggunakan key unik 'sap_area_filter' agar terisolasi dari filter lain
    selected_sap_area = st.multiselect(
        "Area (Khusus SAP)",
        options=list_sap_area,
        default=list_sap_area,
        key="sap_area_filter",
    )

with col_sap_filter2:
    list_sap_pic = df_sap_base["PIC Site"].dropna().unique().tolist()
    # Menggunakan key unik 'sap_pic_filter' agar terisolasi dari filter lain
    selected_sap_pic = st.multiselect(
        "PIC Site (Khusus SAP)",
        options=list_sap_pic,
        default=list_sap_pic,
        key="sap_pic_filter",
    )

# 3. Apply Filter Khusus ke Dataframe SAP
df_sap_filtered = df_sap_base[
    (df_sap_base["Area"].isin(selected_sap_area))
    & (df_sap_base["PIC Site"].isin(selected_sap_pic))
]

# 4. Metric Cards Khusus SAP
col_sap_m1, col_sap_m2 = st.columns(2)
total_sap_count = len(df_sap_filtered)
total_sap_amount = df_sap_filtered["NET AMOUNT"].sum()

col_sap_m1.metric("Total Count of Invoice No", f"{total_sap_count:,}")
col_sap_m2.metric("Total NET AMOUNT", f"Rp {total_sap_amount:,.0f}")

# 5. Tabel Summary Pivot Khusus SAP
df_sap_pivot = (
    df_sap_filtered.groupby(
        ["new regional", "IBS Invoice Type"], as_index=False
    )
    .agg(
        Count_Invoice=("Invoice No", "count"),
        Sum_Net_Amount=("NET AMOUNT", "sum"),
    )
)

st.dataframe(
    df_sap_pivot,
    column_config={
        "new regional": st.column_config.TextColumn("new regional"),
        "IBS Invoice Type": st.column_config.TextColumn("IBS Invoice Type"),
        "Count_Invoice": st.column_config.NumberColumn(
            "Count of Invoice No", format="%d"
        ),
        "Sum_Net_Amount": st.column_config.NumberColumn(
            "Sum of NET AMOUNT", format="Rp %,.0f"
        ),
    },
    hide_index=True,
    use_container_width=True,
)


# ==========================================
# STATUS TRACKING INVOICE BM
# ==========================================
st.markdown("---")
st.subheader("📊 Status Tracking Invoice BM")

# 1. MENDAPATKAN DATAFRAME DARI SCRIPT UTAMA
# Cek beberapa nama variabel umum yang biasanya dipakai di skrip utama
df_source = None

if 'df' in locals():
    df_source = df
elif 'df' in globals():
    df_source = globals()['df']
elif 'df' in st.session_state:
    df_source = st.session_state['df']
elif 'data' in locals():
    df_source = data
elif 'data' in globals():
    df_source = globals()['data']
elif 'df_filtered' in locals():
    df_source = df_filtered

# Jika tidak ada DataFrame yang terdeteksi sama sekali, gunakan fallback dummy data yang valid (panjang array sama: 4)
if df_source is None or not isinstance(df_source, pd.DataFrame):
    dummy_data = {
        'Area': ['Area 1', 'Area 1', 'Area 1', 'Area 2'],
        'Year': [2024, 2024, 2024, 2024],
        'PIC Site': ['Alex', 'Alex', 'Budi', 'Cici'],
        'new regional': ['RO3_Jakarta Banten', 'RO3_Jakarta Banten', 'RO3_Jakarta Banten', 'RO3_Jakarta Banten'],
        'Supplier Name': ['PT. Batara Tabaraka', 'PT. POS PROPERTI INDO', 'Apartamen Oasis Mitra', 'ASURANSI KREDIT INDON'],
        'Site ID': ['JKP187', 'JKP020', 'JKP652', 'JKP692'],
        'Invoice No.': ['INV-01', 'INV-02', 'INV-03', 'INV-04'],
        'Month': ['Jan', 'Feb', 'Mar', 'Apr']
    }
    df_source = pd.DataFrame(dummy_data)


# ------------------------------------------
# 2. FILTER DATA (AREA, YEAR, PIC SITE)
# ------------------------------------------
col_area = 'Area' if 'Area' in df_source.columns else ('new regional' if 'new regional' in df_source.columns else 'Regional')
col_year = 'Year' if 'Year' in df_source.columns else ('year' if 'year' in df_source.columns else 'Tahun')
col_pic = 'PIC Site' if 'PIC Site' in df_source.columns else ('PIC' if 'PIC' in df_source.columns else 'pic_site')

st.markdown("#### 🔍 Filter Data Tracking")
col1, col2, col3 = st.columns(3)

with col1:
    opts_area = ["All"] + sorted(list(df_source[col_area].dropna().astype(str).unique())) if col_area in df_source.columns else ["All"]
    sel_area = st.selectbox("Select Area", opts_area, key="trk_area")

with col2:
    opts_year = ["All"] + sorted(list(df_source[col_year].dropna().astype(str).unique())) if col_year in df_source.columns else ["All"]
    sel_year = st.selectbox("Select Year", opts_year, key="trk_year")

with col3:
    opts_pic = ["All"] + sorted(list(df_source[col_pic].dropna().astype(str).unique())) if col_pic in df_source.columns else ["All"]
    sel_pic = st.selectbox("Select PIC Site", opts_pic, key="trk_pic")

# Logika Filtering
df_trk_filtered = df_source.copy()

if sel_area != "All" and col_area in df_trk_filtered.columns:
    df_trk_filtered = df_trk_filtered[df_trk_filtered[col_area].astype(str) == sel_area]

if sel_year != "All" and col_year in df_trk_filtered.columns:
    df_trk_filtered = df_trk_filtered[df_trk_filtered[col_year].astype(str) == sel_year]

if sel_pic != "All" and col_pic in df_trk_filtered.columns:
    df_trk_filtered = df_trk_filtered[df_trk_filtered[col_pic].astype(str) == sel_pic]


# ------------------------------------------
# 3. PROSES PIVOT TABLE & FORMULA
# ------------------------------------------
def generate_tracking_invoice_table(df_input):
    df_trk = df_input.copy()

    col_reg_t = 'new regional' if 'new regional' in df_trk.columns else ('Regional' if 'Regional' in df_trk.columns else 'regional')
    col_supp_t = 'Supplier Name' if 'Supplier Name' in df_trk.columns else ('Supplier' if 'Supplier' in df_trk.columns else 'supplier_name')
    col_site_t = 'Site ID' if 'Site ID' in df_trk.columns else ('SiteID' if 'SiteID' in df_trk.columns else 'site_id')
    col_inv_no = 'Invoice No.' if 'Invoice No.' in df_trk.columns else ('Invoice No' if 'Invoice No' in df_trk.columns else 'Invoice Number')
    col_m_t = 'Month' if 'Month' in df_trk.columns else ('Payment Month' if 'Payment Month' in df_trk.columns else 'Month Name')

    for col_req in [col_reg_t, col_supp_t, col_site_t]:
        if col_req not in df_trk.columns:
            df_trk[col_req] = "-"

    if col_inv_no not in df_trk.columns:
        df_trk[col_inv_no] = 1

    months_order = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

    if col_m_t in df_trk.columns:
        df_trk['month_clean'] = pd.to_datetime(df_trk[col_m_t].astype(str), format='%b', errors='coerce').dt.strftime('%b')
        if df_trk['month_clean'].isna().all():
            df_trk['month_clean'] = df_trk[col_m_t].astype(str).str.slice(0, 3).str.title()
    else:
        df_trk['month_clean'] = 'Jan'

    df_trk = df_trk[df_trk['month_clean'].isin(months_order)]

    if df_trk.empty:
        return pd.DataFrame(), col_reg_t, col_supp_t, col_site_t

    # Pivot Table: Count of Invoice No. per Month
    pivot_df = pd.pivot_table(
        df_trk,
        index=[col_reg_t, col_supp_t, col_site_t],
        columns='month_clean',
        values=col_inv_no,
        aggfunc='count',
        fill_value=0
    ).reset_index()

    for m in months_order:
        if m not in pivot_df.columns:
            pivot_df[m] = 0

    pivot_df = pivot_df[[col_reg_t, col_supp_t, col_site_t] + months_order]

    # Perhitungan Formula Excel
    pivot_df['Grand Total'] = pivot_df[months_order].sum(axis=1)
    pivot_df['Progress'] = (pivot_df['Grand Total'] / 12 * 100).round(0)
    pivot_df['Invoice NY Received'] = pivot_df['Grand Total'].apply(lambda x: max(0, 12 - x))

    return pivot_df, col_reg_t, col_supp_t, col_site_t


df_trk_res, c_reg, c_supp, c_site = generate_tracking_invoice_table(df_trk_filtered)

# ------------------------------------------
# 4. VISUALISASI CHART WITH %
# ------------------------------------------
if not df_trk_res.empty:
    st.markdown("### 📈 Visualisasi Progress Tracking (%)")
    
    # Ringkasan Metrics
    total_sites = len(df_trk_res)
    avg_progress = round(df_trk_res['Progress'].mean(), 1)
    total_ny_rec = int(df_trk_res['Invoice NY Received'].sum())
    
    m1, m2, m3 = st.columns(3)
    m1.metric("Total Site", f"{total_sites} Sites")
    m2.metric("Rata-Rata Progress", f"{avg_progress}%")
    m3.metric("Total Invoice NY Received", f"{total_ny_rec} Inv", delta_color="inverse")

    # Bar Chart Progress % per Site
    chart_data = df_trk_res[[c_site, 'Progress']].set_index(c_site)
    st.bar_chart(chart_data)

    st.markdown("---")

    # ------------------------------------------
    # 5. RENDERING TABEL EXCEL HTML/CSS
    # ------------------------------------------
    months_headers = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    
    rows_trk_html = ""
    for idx, row in df_trk_res.iterrows():
        # Kolom Bulan (0 = Pink Soft #fce4d6 & Teks Merah)
        m_cells = ""
        for m in months_headers:
            val_m = int(row[m])
            cell_bg = "background-color: #fce4d6; color: #c00000; font-weight: bold;" if val_m == 0 else ""
            m_cells += f'<td style="text-align: center; {cell_bg}">{val_m}</td>'

        grand_tot = int(row['Grand Total'])
        prog_pct = int(row['Progress'])
        ny_rec = int(row['Invoice NY Received'])

        # Highlight Merah Solid untuk Invoice NY Received > 0
        ny_bg = "background-color: #ff0000; color: #ffffff; font-weight: bold;" if ny_rec > 0 else "text-align: center;"

        rows_trk_html += f"""
        <tr>
            <td style="text-align: left;">{row[c_reg]}</td>
            <td style="text-align: left;">{row[c_supp]}</td>
            <td style="text-align: center;">{row[c_site]}</td>
            {m_cells}
            <td style="text-align: center; font-weight: bold;">{grand_tot}</td>
            <td style="text-align: center; background-color: #e2efda; font-weight: bold; color: #375623;">{prog_pct}%</td>
            <td style="text-align: center; {ny_bg}">{ny_rec}</td>
        </tr>
        """

    full_trk_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 0; padding: 0; background-color: transparent; }}
        .trk-table {{ width: 100%; border-collapse: collapse; font-size: 11px; color: #000000; }}
        .trk-table th, .trk-table td {{ border: 1px solid #d9d9d9; padding: 4px 6px; white-space: nowrap; }}
        .trk-hdr {{ background-color: #ffffff; color: #000000; font-weight: bold; text-align: center; vertical-align: middle; border: 1px solid #000000 !important; }}
        .trk-hdr-title {{ font-size: 16px; font-weight: bold; text-decoration: underline; padding: 8px 0; border: none; text-align: left; color: #000000; }}
    </style>
    </head>
    <body>
    <div style="overflow-x: auto;">
        <div class="trk-hdr-title">Tracking invoice</div>
        <table class="trk-table">
            <thead>
                <tr>
                    <th class="trk-hdr">Regional</th>
                    <th class="trk-hdr">Supplier Name</th>
                    <th class="trk-hdr">Site ID</th>
                    <th class="trk-hdr">Jan</th>
                    <th class="trk-hdr">Feb</th>
                    <th class="trk-hdr">Mar</th>
                    <th class="trk-hdr">Apr</th>
                    <th class="trk-hdr">May</th>
                    <th class="trk-hdr">Jun</th>
                    <th class="trk-hdr">Jul</th>
                    <th class="trk-hdr">Aug</th>
                    <th class="trk-hdr">Sep</th>
                    <th class="trk-hdr">Oct</th>
                    <th class="trk-hdr">Nov</th>
                    <th class="trk-hdr">Dec</th>
                    <th class="trk-hdr">Grand Total</th>
                    <th class="trk-hdr">Progress</th>
                    <th class="trk-hdr">Invoice NY Received</th>
                </tr>
            </thead>
            <tbody>
                {rows_trk_html}
            </tbody>
        </table>
    </div>
    </body>
    </html>
    """
    components.html(full_trk_html, height=len(df_trk_res) * 28 + 140, scrolling=True)
else:
    st.warning("Data Tracking Invoice tidak ditemukan berdasarkan filter yang dipilih.")
