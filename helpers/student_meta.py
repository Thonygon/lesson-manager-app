import streamlit as st
from core.database import load_table
import pandas as pd
from core.database import norm_student

# 07.10) STUDENT META
# =========================
def load_students_df() -> pd.DataFrame:
    df = load_table("students")
    if df.empty:
        return pd.DataFrame(columns=["student", "email", "zoom_link", "notes", "color", "phone"])

    for c, default in {
        "student": "", "email": "", "zoom_link": "", "notes": "", "color": "#3B82F6", "phone": ""
    }.items():
        if c not in df.columns:
            df[c] = default

    df["student"] = df["student"].astype(str).str.strip()
    df["color"] = df["color"].fillna("#3B82F6").astype(str).str.strip()
    df["zoom_link"] = df["zoom_link"].fillna("").astype(str).str.strip()
    df["email"] = df["email"].fillna("").astype(str).str.strip()
    df["notes"] = df["notes"].fillna("").astype(str)
    df["phone"] = df["phone"].fillna("").astype(str).str.strip()

    return df

def student_meta_maps():
    s = load_students_df()
    if s.empty:
        return {}, {}, {}, {}
    s["student_norm"] = s["student"].apply(norm_student)
    color_map = dict(zip(s["student_norm"], s["color"]))
    zoom_map  = dict(zip(s["student_norm"], s["zoom_link"]))
    email_map = dict(zip(s["student_norm"], s["email"]))
    phone_map = dict(zip(s["student_norm"], s["phone"]))
    return color_map, zoom_map, email_map, phone_map

# =========================
