import streamlit as st
import pandas as pd
from supabase import create_client

st.set_page_config(page_title="Lesson Manager", layout="wide")

# ---- Supabase connection (use Streamlit Secrets) ----
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ---- Helpers ----
def load_table(name, limit=10000):
    resp = supabase.table(name).select("*").limit(limit).execute()
    return pd.DataFrame(resp.data)

def add_class(student, number_of_lesson, lesson_date, modality, note=""):
    data = {
        "student": student.strip(),
        "number_of_lesson": int(number_of_lesson),
        "lesson_date": lesson_date,  # YYYY-MM-DD
        "modality": modality.strip(),
        "note": note.strip() if note else ""
    }
    supabase.table("classes").insert(data).execute()

def add_payment(student, number_of_lesson, payment_date, paid_amount, modality):
    data = {
        "student": student.strip(),
        "number_of_lesson": int(number_of_lesson),
        "payment_date": payment_date,  # YYYY-MM-DD
        "paid_amount": float(paid_amount),
        "modality": modality.strip()
    }
    supabase.table("payments").insert(data).execute()

def rebuild_dashboard():
    classes = load_table("classes")
    payments = load_table("payments")

    if classes.empty:
        classes = pd.DataFrame(columns=["student","number_of_lesson","lesson_date","modality","note"])
    if payments.empty:
        payments = pd.DataFrame(columns=["student","number_of_lesson","payment_date","paid_amount","modality"])

    classes["student"] = classes["student"].astype(str).str.strip()
    payments["student"] = payments["student"].astype(str).str.strip()

    classes["lesson_date"] = pd.to_datetime(classes["lesson_date"], errors="coerce")
    payments["payment_date"] = pd.to_datetime(payments["payment_date"], errors="coerce")

    classes["number_of_lesson"] = pd.to_numeric(classes["number_of_lesson"], errors="coerce").fillna(0).astype(int)
    payments["number_of_lesson"] = pd.to_numeric(payments["number_of_lesson"], errors="coerce").fillna(0).astype(int)
    payments["paid_amount"] = pd.to_numeric(payments["paid_amount"], errors="coerce").fillna(0.0)

    # Packages bought (count payments rows)
    packages_bought = payments.groupby("student", as_index=False).size().rename(columns={"size": "packages_bought"})

    # Latest payment = current package
    latest_payment = (
        payments.sort_values("payment_date")
        .groupby("student", as_index=False)
        .tail(1)
        .rename(columns={
            "number_of_lesson": "lessons_paid_total",
            "paid_amount": "total_paid",
            "payment_date": "payment_date"
        })[["student","lessons_paid_total","total_paid","payment_date","modality"]]
    )

    # Lessons taken since latest payment date
    merged = classes.merge(latest_payment[["student","payment_date"]], on="student", how="left")
    current = merged[merged["payment_date"].notna() & (merged["lesson_date"] >= merged["payment_date"])]

    lessons_taken = current.groupby("student", as_index=False)["number_of_lesson"].sum().rename(columns={"number_of_lesson":"lessons_taken"})

    dash = latest_payment.merge(packages_bought, on="student", how="left").merge(lessons_taken, on="student", how="left")
    dash["packages_bought"] = dash["packages_bought"].fillna(0).astype(int)
    dash["lessons_taken"] = dash["lessons_taken"].fillna(0).astype(int)
    dash["lessons_left"] = (dash["lessons_paid_total"] - dash["lessons_taken"]).astype(int)

    def status(x):
        if x <= 0: return "Finished"
        if x <= 3: return "Almost Finished"
        return "Active"

    dash["status"] = dash["lessons_left"].apply(status)

    dash = dash.sort_values("lessons_left").reset_index(drop=True)

    # Prettier column names
    dash = dash.rename(columns={
        "student":"Student",
        "packages_bought":"Packages_Bought",
        "lessons_paid_total":"Lessons_Paid_Total",
        "total_paid":"Total_Paid",
        "payment_date":"Payment_Date",
        "lessons_taken":"Lessons_Taken",
        "lessons_left":"Lessons_Left",
        "status":"Status",
        "modality":"Modality"
    })

    # Show date as ISO text
    if "Payment_Date" in dash.columns:
        dash["Payment_Date"] = pd.to_datetime(dash["Payment_Date"], errors="coerce").dt.strftime("%Y-%m-%d")

    return dash


# ---- UI ----
st.title("📚 Lesson Manager (Online)")

tab1, tab2, tab3 = st.tabs(["Dashboard", "Add Lesson", "Add Payment"])

with tab1:
    st.subheader("Current Package Dashboard")
    dash = rebuild_dashboard()
    st.dataframe(dash, use_container_width=True)

with tab2:
    st.subheader("Add a Lesson")
    student = st.text_input("Student")
    number = st.number_input("Number of lessons", min_value=1, max_value=10, value=1, step=1)
    lesson_date = st.date_input("Lesson date")
    modality = st.selectbox("Modality", ["Online", "Offline"])
    note = st.text_input("Note (optional)")

    if st.button("Save Lesson"):
        add_class(student, number, lesson_date.isoformat(), modality, note)
        st.success("Lesson saved ✅")

with tab3:
    st.subheader("Add a Payment (New Package)")
    student_p = st.text_input("Student ", key="student_p")
    lessons_paid = st.number_input("Lessons paid", min_value=1, max_value=500, value=44, step=1)
    payment_date = st.date_input("Payment date")
    paid_amount = st.number_input("Paid amount", min_value=0.0, value=0.0, step=100.0)
    modality_p = st.selectbox("Modality ", ["Online", "Offline"], key="modality_p")

    if st.button("Save Payment"):
        add_payment(student_p, lessons_paid, payment_date.isoformat(), paid_amount, modality_p)
        st.success("Payment saved ✅")
