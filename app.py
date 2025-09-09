import streamlit as st
import pandas as pd
import sqlite3
import io
import re
from datetime import datetime
import matplotlib.pyplot as plt
from matplotlib import font_manager

DB_PATH = "usage_data.sqlite"

# ---------- DB Utilities ----------
def init_db():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS files(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_name TEXT,
            uploaded_at TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS readings(
            file_id INTEGER,
            ymd TEXT,
            hhmm TEXT,
            usage REAL,
            PRIMARY KEY(file_id, ymd, hhmm),
            FOREIGN KEY(file_id) REFERENCES files(id)
        )
        """
    )
    con.commit()
    return con

def insert_file(con, source_name):
    cur = con.cursor()
    cur.execute(
        "INSERT INTO files(source_name, uploaded_at) VALUES (?, ?)",
        (source_name, datetime.utcnow().isoformat())
    )
    con.commit()
    return cur.lastrowid

def upsert_readings(con, file_id, df_long):
    cur = con.cursor()
    rows = list(df_long[["ymd","hhmm","usage"]].itertuples(index=False, name=None))
    cur.executemany(
        """
        INSERT OR REPLACE INTO readings(file_id, ymd, hhmm, usage)
        VALUES (?, ?, ?, ?)
        """,
        [(file_id, y, t, float(u) if pd.notna(u) else None) for (y,t,u) in rows]
    )
    con.commit()

def list_files(con):
    return pd.read_sql_query(
        "SELECT id, source_name, uploaded_at FROM files ORDER BY id DESC", con
    )

def list_dates(con, file_id):
    q = "SELECT DISTINCT ymd FROM readings WHERE file_id=? ORDER BY ymd"
    return pd.read_sql_query(q, con, params=(file_id,))["ymd"].tolist()

def read_range(con, file_id, start_date, end_date):
    q = """
        SELECT ymd, hhmm, usage
        FROM readings
        WHERE file_id=? AND ymd BETWEEN ? AND ?
        ORDER BY ymd, hhmm
    """
    return pd.read_sql_query(q, con, params=(file_id, start_date, end_date))

# ---------- Parsing Utilities ----------
def detect_encoding(raw_bytes: bytes):
    try:
        import chardet
        enc = chardet.detect(raw_bytes).get("encoding") or "utf-8"
        return enc.lower()
    except Exception:
        return "utf-8"

def load_table(file) -> pd.DataFrame:
    name = file.name.lower()
    raw = file.read()
    file.seek(0)
    if name.endswith(".csv"):
        enc = detect_encoding(raw)
        try:
            df = pd.read_csv(io.BytesIO(raw), encoding=enc)
        except UnicodeDecodeError:
            df = pd.read_csv(io.BytesIO(raw), encoding="shift_jis", errors="ignore")
    else:
        df = pd.read_excel(file)
    return df

def wide_to_long(df: pd.DataFrame) -> pd.DataFrame:
    date_col_candidates = [c for c in df.columns if str(c).strip() in ["YYYY/MM/DD","日付","date","Date"]]
    if not date_col_candidates:
        for c in df.columns:
            v = str(df[c].iloc[0])
            if re.match(r"\d{4}[-/]\d{1,2}[-/]\d{1,2}", v):
                date_col_candidates = [c]
                break
    if not date_col_candidates:
        raise ValueError("Date column (e.g., 'YYYY/MM/DD') not found.")
    date_col = date_col_candidates[0]

    time_cols = [c for c in df.columns if re.fullmatch(r"\d{1,2}:\d{2}", str(c))]
    if len(time_cols) == 0:
        raise ValueError("Time columns (e.g., '0:00'..'23:30') not found.")

    keep = [date_col] + time_cols
    df2 = df[keep].copy()
    df2[date_col] = pd.to_datetime(df2[date_col]).dt.strftime("%Y-%m-%d")
    for c in time_cols:
        df2[c] = pd.to_numeric(df2[c], errors="coerce")

    long_df = df2.melt(id_vars=[date_col], value_vars=time_cols, var_name="hhmm", value_name="usage")
    long_df = long_df.rename(columns={date_col:"ymd"})
    return long_df

# ---------- Font Setup ----------
def pick_jp_font():
    preferred = ["Noto Sans CJK JP","Noto Sans JP","Hiragino Sans","Meiryo","Yu Gothic","IPAexGothic","TakaoGothic","MS Gothic"]
    installed = {f.name for f in font_manager.fontManager.ttflist}
    for fam in preferred:
        if fam in installed:
            plt.rcParams["font.family"] = fam
            return fam
    return None

# ---------- UI ----------
st.set_page_config(page_title="30-min Usage Viewer", layout="wide")
st.title("Daily Usage (30-min Interval) — DB-backed")

con = init_db()
pick_jp_font()

tab_upload, tab_view = st.tabs(["Upload to DB", "Visualization"])

with tab_upload:
    st.markdown("#### Register CSV/Excel (saved to DB)")
    file = st.file_uploader("Choose a file (CSV or Excel)", type=["csv","xlsx","xls"])
    if file is not None:
        try:
            df = load_table(file)
            st.write("Head:", df.head())
            long_df = wide_to_long(df)
            st.write("Long-format preview:", long_df.head())

            if st.button("Save into DB"):
                file_id = insert_file(con, file.name)
                upsert_readings(con, file_id, long_df)
                st.success(f"Saved: file_id={file_id}, rows={len(long_df)}")
        except Exception as e:
            st.error(f"Import failed: {e}")

    st.markdown("---")
    st.markdown("#### Registered files")
    files_df = list_files(con)
    if len(files_df)==0:
        st.info("No files yet.")
    else:
        st.dataframe(files_df, use_container_width=True)

with tab_view:
    files_df = list_files(con)
    if len(files_df)==0:
        st.info("Please upload a file first in the 'Upload to DB' tab.")
    else:
        file_opts = {f"{row['id']}: {row['source_name']}": int(row["id"]) for _, row in files_df.iterrows()}
        sel_label = st.selectbox("Select file", list(file_opts.keys()))
        file_id = file_opts[sel_label]

        dates = list_dates(con, file_id)
        if len(dates)==0:
            st.warning("No date rows in this file.")
        else:
            # ---- SAFE DEFAULTS ----
            start_date, end_date = None, None
            unit_option = "kWh (30min)"
            df_range = pd.DataFrame()

            c1, c2, c3 = st.columns(3)
            with c1:
                start_date = st.selectbox("Start Date", dates, index=0)
            with c2:
                end_date = st.selectbox("End Date", dates, index=len(dates)-1)
            with c3:
                unit_option = st.radio("Unit", ["kWh (30min)", "kW"], index=0)

            # chart type selector
            chart_type = st.radio("Chart type", ["Overlay daily curves", "Daily average trend", "Monthly average trend"], index=0, horizontal=True)

            if start_date and end_date and start_date > end_date:
                st.error("Start Date is after End Date.")
            elif start_date and end_date:
                df_range = read_range(con, file_id, start_date, end_date)

                # Convert to kW if selected (kWh per 30min -> kW is *2)
                usage = df_range["usage"].copy()
                if unit_option == "kW":
                    usage = usage * 2
                df_range = df_range.assign(usage=usage)

                if chart_type == "Overlay daily curves":
                    pivot = df_range.pivot_table(index="ymd", columns="hhmm", values="usage", aggfunc="mean")
                    def time_key(t):
                        h, m = t.split(":")
                        return int(h)*60 + int(m)
                    ordered_cols = sorted(pivot.columns, key=time_key) if len(pivot.columns) else []
                    if ordered_cols:
                        pivot = pivot[ordered_cols]
                        fig = plt.figure(figsize=(12,6))
                        for ymd, row in pivot.iterrows():
                            plt.plot(ordered_cols, row.values, label=ymd)
                        plt.title("Daily Usage (30-min Interval)")
                        plt.xlabel("Time of Day")
                        plt.ylabel("Energy [kWh/30min]" if unit_option=="kWh (30min)" else "Power [kW]")
                        plt.xticks(rotation=45)
                        plt.legend(title="Date", bbox_to_anchor=(1.02,1), loc="upper left")
                        plt.tight_layout()
                        st.pyplot(fig)
                    else:
                        st.info("No time columns to plot for the selected range.")

                elif chart_type == "Daily average trend":
                    # average of 30-min values per day -> represents average power level that day
                    daily_avg = df_range.groupby("ymd", as_index=False)["usage"].mean()
                    fig = plt.figure(figsize=(12,5))
                    plt.plot(daily_avg["ymd"], daily_avg["usage"], marker="o")
                    plt.title("Daily Average Usage Trend")
                    plt.xlabel("Date")
                    plt.ylabel("Energy [kWh/30min]" if unit_option=="kWh (30min)" else "Power [kW]")
                    plt.xticks(rotation=45)
                    plt.tight_layout()
                    st.pyplot(fig)
                    with st.expander("Daily averages (table)"):
                        st.dataframe(daily_avg.rename(columns={"usage":"avg"}), use_container_width=True)

                else:  # Monthly average trend
                    # average of 30-min values per month
                    df_range["ym"] = pd.to_datetime(df_range["ymd"]).dt.to_period("M").astype(str)
                    monthly_avg = df_range.groupby("ym", as_index=False)["usage"].mean()
                    fig = plt.figure(figsize=(12,5))
                    plt.plot(monthly_avg["ym"], monthly_avg["usage"], marker="o")
                    plt.title("Monthly Average Usage Trend")
                    plt.xlabel("Month")
                    plt.ylabel("Energy [kWh/30min]" if unit_option=="kWh (30min)" else "Power [kW]")
                    plt.xticks(rotation=45)
                    plt.tight_layout()
                    st.pyplot(fig)
                    with st.expander("Monthly averages (table)"):
                        st.dataframe(monthly_avg.rename(columns={"usage":"avg"}), use_container_width=True)

                with st.expander("Data preview (long)"):
                    st.dataframe(df_range.head(200), use_container_width=True)