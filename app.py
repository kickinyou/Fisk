# app.py
# -------------------------------------------------------------
# Interaktiv kalkylator för laxprodukter (Scenario-jämförelse)
# Byggd för Streamlit. Kör lokalt med:  streamlit run app.py
# -------------------------------------------------------------

import pandas as pd
import numpy as np
import altair as alt
import streamlit as st
from io import StringIO

st.set_page_config(page_title="Laxkalkylator", layout="wide")
st.title("🐟 Laxkalkylator – jämför produkter och scenarier")

# ------------------------ Hjälpfunktioner ------------------------

def default_products():
    return pd.DataFrame([
        {"Produkt": "Varmrökt bit", "Pris/ kg (SEK)": 240.0, "Utbyte (%)": 72.0, "Spill (%)": 3.0,
         "Proc.kost/ kg säljbart": 18.0, "Pack/ kg säljbart": 10.0, "Övrigt/ kg säljbart": 0.0,
         "Råvara (kg)": 100.0},
        {"Produkt": "Skivad", "Pris/ kg (SEK)": 280.0, "Utbyte (%)": 65.0, "Spill (%)": 5.0,
         "Proc.kost/ kg säljbart": 25.0, "Pack/ kg säljbart": 12.0, "Övrigt/ kg säljbart": 0.0,
         "Råvara (kg)": 100.0},
        {"Produkt": "Hel sida", "Pris/ kg (SEK)": 210.0, "Utbyte (%)": 80.0, "Spill (%)": 2.0,
         "Proc.kost/ kg säljbart": 12.0, "Pack/ kg säljbart": 8.0, "Övrigt/ kg säljbart": 0.0,
         "Råvara (kg)": 100.0},
    ])

@st.cache_data
def template_csv():
    return default_products().to_csv(index=False).encode("utf-8")


def calc_products(df: pd.DataFrame, raw_price_per_kg: float):
    df = df.copy()
    # Sanera kolumner/typer
    num_cols = [c for c in df.columns if c != "Produkt"]
    for c in num_cols:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)

    # Beräkningar
    df["Utbyte (andel)"] = df["Utbyte (%)"]/100.0
    df["Spill (andel)"] = df["Spill (%)"]/100.0

    df["Säljbart kg"] = df["Råvara (kg)"] * df["Utbyte (andel)"] * (1 - df["Spill (andel)"])
    df["Intäkt (SEK)"] = df["Säljbart kg"] * df["Pris/ kg (SEK)"]

    # Kostnader
    df["Råvarukostnad (SEK)"] = df["Råvara (kg)"] * raw_price_per_kg
    df["Proc.kost (SEK)"] = df["Säljbart kg"] * df["Proc.kost/ kg säljbart"]
    df["Pack (SEK)"] = df["Säljbart kg"] * df["Pack/ kg säljbart"]
    df["Övrigt (SEK)"] = df["Säljbart kg"] * df["Övrigt/ kg säljbart"]
    df["Rörliga kostnader (SEK)"] = df[["Råvarukostnad (SEK)", "Proc.kost (SEK)", "Pack (SEK)", "Övrigt (SEK)"]].sum(axis=1)

    # TB
    df["TB (SEK)"] = df["Intäkt (SEK)"] - df["Rörliga kostnader (SEK)"]
    df["TB/ kg råvara"] = df["TB (SEK)"] / df["Råvara (kg)"]
    df["TB/ kg säljbart"] = df["TB (SEK)"] / df["Säljbart kg"].replace(0, np.nan)
    df["TB-marginal (% av intäkt)"] = 100 * df["TB (SEK)"] / df["Intäkt (SEK)"].replace(0, np.nan)

    # Summering
    totals = (
        df[["Råvara (kg)", "Säljbart kg", "Intäkt (SEK)", "Rörliga kostnader (SEK)", "TB (SEK)"]]
        .sum()
        .to_frame().T
    )
    totals.insert(0, "Produkt", "SUMMA")
    return df, totals

# ------------------------ Sidopanel: antaganden ------------------------
st.sidebar.header("Globala antaganden")
raw_price = st.sidebar.number_input("Råvarupriset – SEK per kg råvara", min_value=0.0, value=70.0, step=1.0)

st.sidebar.caption("Utbyte och spill är i % och avser förhållandet från råvara till säljbart kg.")

# Antal produkter
n_products = st.sidebar.slider("Antal produkter i kalkylen", 1, 12, 3)

# ------------------------ Scenarier ------------------------
A, B, Notes = st.tabs(["Scenario A", "Scenario B", "Antaganden & Export"])

# Initiera state
if "A_df" not in st.session_state:
    st.session_state.A_df = default_products()
if "B_df" not in st.session_state:
    st.session_state.B_df = default_products()

# Trimma antalet rader enligt n_products
for key in ["A_df", "B_df"]:
    df = st.session_state[key]
    if len(df) < n_products:
        # fyll på
        for _ in range(n_products - len(df)):
            df = pd.concat([df, pd.DataFrame([{**default_products().iloc[0].to_dict(), "Produkt": f"Produkt {len(df)+1}"}])], ignore_index=True)
    elif len(df) > n_products:
        df = df.iloc[:n_products].copy()
    st.session_state[key] = df.reset_index(drop=True)

# -------- Scenario A --------
with A:
    st.subheader("Scenario A – indata")
    A_edit = st.data_editor(
        st.session_state.A_df,
        num_rows="dynamic",
        use_container_width=True,
        key="A_editor",
    )
    st.session_state.A_df = A_edit

    A_out, A_tot = calc_products(st.session_state.A_df, raw_price)

    st.markdown("### Resultat – Scenario A")
    c1, c2 = st.columns([2, 1])
    with c1:
        st.dataframe(A_out[[
            "Produkt", "Råvara (kg)", "Säljbart kg", "Pris/ kg (SEK)", "Intäkt (SEK)",
            "Råvarukostnad (SEK)", "Proc.kost (SEK)", "Pack (SEK)", "Övrigt (SEK)",
            "Rörliga kostnader (SEK)", "TB (SEK)", "TB/ kg råvara", "TB/ kg säljbart", "TB-marginal (% av intäkt)"
        ]], use_container_width=True, hide_index=True)
    with c2:
        st.metric("TB – Scenario A (SEK)", f"{A_tot['TB (SEK)'].iloc[0]:,.0f}")
        st.metric("TB/ kg råvara (SEK)", f"{(A_tot['TB (SEK)'].iloc[0] / max(A_tot['Råvara (kg)'].iloc[0],1)):,.2f}")
        st.metric("TB-marginal (%)", f"{(100*A_tot['TB (SEK)'].iloc[0]/max(A_tot['Intäkt (SEK)'].iloc[0],1)):,.1f}%")

    # Diagram – TB per produkt
    st.markdown("#### TB per produkt")
    chart_A = alt.Chart(A_out).mark_bar().encode(
        x=alt.X("Produkt", sort='-y'),
        y=alt.Y("TB (SEK)", title="TB (SEK)"),
        tooltip=["Produkt", alt.Tooltip("TB (SEK)", format=",")]
    ).properties(height=300)
    st.altair_chart(chart_A, use_container_width=True)

# -------- Scenario B --------
with B:
    st.subheader("Scenario B – indata")
    B_edit = st.data_editor(
        st.session_state.B_df,
        num_rows="dynamic",
        use_container_width=True,
        key="B_editor",
    )
    st.session_state.B_df = B_edit

    B_out, B_tot = calc_products(st.session_state.B_df, raw_price)

    st.markdown("### Resultat – Scenario B")
    c1, c2 = st.columns([2, 1])
    with c1:
        st.dataframe(B_out[[
            "Produkt", "Råvara (kg)", "Säljbart kg", "Pris/ kg (SEK)", "Intäkt (SEK)",
            "Råvarukostnad (SEK)", "Proc.kost (SEK)", "Pack (SEK)", "Övrigt (SEK)",
            "Rörliga kostnader (SEK)", "TB (SEK)", "TB/ kg råvara", "TB/ kg säljbart", "TB-marginal (% av intäkt)"
        ]], use_container_width=True, hide_index=True)
    with c2:
        st.metric("TB – Scenario B (SEK)", f"{B_tot['TB (SEK)'].iloc[0]:,.0f}")
        st.metric("TB/ kg råvara (SEK)", f"{(B_tot['TB (SEK)'].iloc[0] / max(B_tot['Råvara (kg)'].iloc[0],1)):,.2f}")
        st.metric("TB-marginal (%)", f"{(100*B_tot['TB (SEK)'].iloc[0]/max(B_tot['Intäkt (SEK)'].iloc[0],1)):,.1f}%")

    st.markdown("#### TB per produkt")
    chart_B = alt.Chart(B_out).mark_bar().encode(
        x=alt.X("Produkt", sort='-y'),
        y=alt.Y("TB (SEK)", title="TB (SEK)"),
        tooltip=["Produkt", alt.Tooltip("TB (SEK)", format=",")]
    ).properties(height=300)
    st.altair_chart(chart_B, use_container_width=True)

# -------- Jämförelse & export --------
with Notes:
    st.subheader("Jämförelse A vs B")
    A_out, A_tot = calc_products(st.session_state.A_df, raw_price)
    B_out, B_tot = calc_products(st.session_state.B_df, raw_price)

    comp = pd.DataFrame({
        "Nyckeltal": ["Råvara (kg)", "Säljbart kg", "Intäkt (SEK)", "Rörliga kostnader (SEK)", "TB (SEK)", "TB/ kg råvara"],
        "Scenario A": [A_tot["Råvara (kg)"].iloc[0], A_tot["Säljbart kg"].iloc[0], A_tot["Intäkt (SEK)"].iloc[0], A_tot["Rörliga kostnader (SEK)"].iloc[0], A_tot["TB (SEK)"].iloc[0], A_tot["TB (SEK)"].iloc[0]/max(A_tot["Råvara (kg)"].iloc[0],1)],
        "Scenario B": [B_tot["Råvara (kg)"].iloc[0], B_tot["Säljbart kg"].iloc[0], B_tot["Intäkt (SEK)"].iloc[0], B_tot["Rörliga kostnader (SEK)"].iloc[0], B_tot["TB (SEK)"].iloc[0], B_tot["TB (SEK)"].iloc[0]/max(B_tot["Råvara (kg)"].iloc[0],1)],
    })

    st.dataframe(comp, use_container_width=True)

    # Ladda ned mall
    st.markdown("### Export & mallar")
    st.download_button(
        label="Ladda ned CSV-mall för produkter",
        data=template_csv(),
        file_name="laxkalkyl_mall.csv",
        mime="text/csv",
    )

    st.write(
        "**Tips:** Ladda din egen CSV via '...' i varje tabell (meny) eller klistra in i dataeditorn. Sätt 'Råvara (kg)' för att simulera produktmix."
    )

# Footer
st.caption(
    "Beräkningar: Säljbart kg = Råvara * Utbyte * (1 - Spill). TB = Intäkt − (Råvarukostnad + Process + Pack + Övrigt). \n"
    "TB/ kg råvara = TB / Råvara. TB/ kg säljbart = TB / Säljbart kg."
)
