import streamlit as st
import pandas as pd
from supabase import create_client

st.set_page_config(page_title="Lesson Manager", layout="wide")

# ---- Supabase connection (Streamlit Secrets) ----
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ---- Data helpers ----
def load_table(name: str, limit: int = 10000) -> pd.DataFrame:
    resp = supabase.table(name).select("*").limit(limit).execute()
    return pd.DataFrame(resp.data)

def ensure_student(student: str) -> None:
    """Insert student into students table; ignore if it already exists."""
    student = str(student).strip()
    if not student:
        return
    try:
        supabase.table("students").insert({"student": student}).execute()
    except Exception:
        # Unique constraint hit -> already exists -> ignore
        pass

def load_students() -> list[str]:
    """Return sorted unique student names from students + classes + payments."""
    students_df = load_table("students")
    classes_df = load_table("classes")
    payments_df = load_table("payments")

    names = set()

    for df, col in [(students_df, "student"), (classes_df, "student"), (payments_df, "student")]:
        if not df.empty and col in df.columns:
            df[col] = df[col].astype(str).str.strip()
            names.update(df[col].dropna().tolist())

    names = sorted([n for n in names if n and n.lower() != "nan"])
    return names

# ---- Write helpers ----
def add_class(student: str, number_of_lesson: int, lesson_date: str, modality: str, note: str = "") -> None:
    student = str(student).strip()
    ensure_student(student)
    data = {
        "student": student,
        "number_of_lesson": int(number_of_lesson),
        "lesson_date": lesson_date,  # YYYY-MM-DD
        "modality": str(modality).strip(),
        "note": str(note).strip() if note else ""
    }
    supabase.table("classes").insert(data).execute()

def add_payment(student: str, number_of_lesson: int, payment_date: str, paid_amount: float, modality: str) -> None:
    student = str(student).strip()
    ensure_student(student)
    data = {
        "student": student,
        "number_of_lesson": int(number_of_lesson),
        "payment_date": payment_date,  # YYYY-MM-DD
        "paid_amount": float(paid_amount),
        "modality": str(modality).strip(),
    }
    supabase.table("payments").insert(data).execute()

def delete_row(table_name: str, row_id: int) -> None:
    supabase.table(table_name).delete().eq("id", int(row_id)).execute()

# ---- Analytics ----
def rebuild_dashboard() -> pd.DataFrame:
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

    payments = payments.dropna(subset=["payment_date"])

    # Packages bought = count of payment rows per student
    packages_bought = payments.groupby("student", as_index=False).size().rename(columns={"size": "Packages_Bought"})

    # Latest payment = current package
    latest_payment = (
        payments.sort_values("payment_date")
        .groupby("student", as_index=False)
        .tail(1)
        .rename(columns={
            "number_of_lesson": "Lessons_Paid_Total",
            "paid_amount": "Total_Paid",
            "payment_date": "Payment_Date",
            "modality": "Modality"
        })[["student","Lessons_Paid_Total","Total_Paid","Payment_Date","Modality"]]
    )

    # Lessons taken since latest payment date
    merged = classes.merge(latest_payment[["student","Payment_Date"]], on="student", how="left")
    current = merged[merged["Payment_Date"].notna() & (merged["lesson_date"] >= merged["Payment_Date"])]

    lessons_taken = (
        current.groupby("student", as_index=False)["number_of_lesson"]
        .sum()
        .rename(columns={"number_of_lesson": "Lessons_Taken"})
    )

    dash = (latest_payment
            .merge(packages_bought, on="student", how="left")
            .merge(lessons_taken, on="student", how="left"))

    dash["Packages_Bought"] = dash["Packages_Bought"].fillna(0).astype(int)
    dash["Lessons_Taken"] = dash["Lessons_Taken"].fillna(0).astype(int)
    dash["Lessons_Left"] = (dash["Lessons_Paid_Total"] - dash["Lessons_Taken"]).astype(int)

    def status(x: int) -> str:
        if x <= 0:
            return "Finished"
        if x <= 3:
            return "Almost Finished"
        return "Active"

    dash["Status"] = dash["Lessons_Left"].apply(status)

    dash = dash.sort_values("Lessons_Left").reset_index(drop=True)
    dash = dash.rename(columns={"student": "Student"})
    dash["Payment_Date"] = pd.to_datetime(dash["Payment_Date"], errors="coerce").dt.strftime("%Y-%m-%d")

    return dash[[
        "Student","Packages_Bought","Lessons_Paid_Total","Total_Paid","Payment_Date",
        "Lessons_Taken","Lessons_Left","Status","Modality"
    ]]

def show_student_history(student: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    classes = load_table("classes")
    payments = load_table("payments")

    # --- Lessons ---
    if classes.empty:
        lessons = pd.DataFrame(columns=["ID","Lesson_Date","Number_of_Lesson","Modality","Note"])
    else:
        classes["student"] = classes["student"].astype(str).str.strip()
        classes["lesson_date"] = pd.to_datetime(classes["lesson_date"], errors="coerce")

        lessons = classes[classes["student"] == student].copy()
        lessons = lessons.sort_values("lesson_date", ascending=False)
        lessons["lesson_date"] = lessons["lesson_date"].dt.strftime("%Y-%m-%d")

        lessons = lessons.rename(columns={
            "id": "ID",
            "lesson_date": "Lesson_Date",
            "number_of_lesson": "Number_of_Lesson",
            "modality": "Modality",
            "note": "Note"
        })[["ID","Lesson_Date","Number_of_Lesson","Modality","Note"]]

    # --- Payments ---
    if payments.empty:
        pay = pd.DataFrame(columns=["ID","Payment_Date","Lessons_Paid","Paid_Amount","Modality"])
    else:
        payments["student"] = payments["student"].astype(str).str.strip()
        payments["payment_date"] = pd.to_datetime(payments["payment_date"], errors="coerce")

        pay = payments[payments["student"] == student].copy()
        pay = pay.sort_values("payment_date", ascending=False)
        pay["payment_date"] = pay["payment_date"].dt.strftime("%Y-%m-%d")

        pay = pay.rename(columns={
            "id": "ID",
            "payment_date": "Payment_Date",
            "number_of_lesson": "Lessons_Paid",
            "paid_amount": "Paid_Amount",
            "modality": "Modality"
        })[["ID","Payment_Date","Lessons_Paid","Paid_Amount","Modality"]]

    # Visual row numbering starting at 1 (does not affect IDs)
    lessons.index = range(1, len(lessons) + 1)
    pay.index = range(1, len(pay) + 1)

    return lessons, pay

# ---- UI ----
st.title("📚 Lesson Manager (Online)")

students = load_students()

tab1, tab2, tab3, tab4 = st.tabs(["Dashboard", "Students", "Add Lesson", "Add Payment"])

with tab1:
    st.subheader("Current Package Dashboard")
    dash = rebuild_dashboard()
    st.dataframe(dash, use_container_width=True)

    st.divider()
    st.subheader("Student History")

    if len(students) == 0:
        st.info("No students found yet.")
    else:
        selected = st.selectbox("Select a student", students, key="history_student")
        lessons_df, payments_df = show_student_history(selected)

        colA, colB = st.columns(2)
        with colA:
            st.markdown("### Lessons")
            st.dataframe(lessons_df, use_container_width=True)

            st.markdown("#### Delete a lesson record (by ID)")
            lesson_id = st.number_input("Lesson ID to delete", min_value=0, step=1, key="del_lesson_id")
            if st.button("Delete Lesson"):
                delete_row("classes", lesson_id)
                st.success("Lesson deleted ✅")
                st.rerun()

        with colB:
            st.markdown("### Payments")
            st.dataframe(payments_df, use_container_width=True)

            st.markdown("#### Delete a payment record (by ID)")
            payment_id = st.number_input("Payment ID to delete", min_value=0, step=1, key="del_payment_id")
            if st.button("Delete Payment"):
                delete_row("payments", payment_id)
                st.success("Payment deleted ✅")
                st.rerun()

with tab2:
    st.subheader("Students")
    st.caption("Add students here so you can pick them from dropdowns everywhere.")

    new_student = st.text_input("New student name")
    if st.button("Add Student"):
        if not new_student.strip():
            st.error("Please enter a student name.")
        else:
            ensure_student(new_student)
            st.success("Student added ✅")
            st.rerun()

    st.divider()
    st.markdown("### Current student list")
    st.write(students if students else "No students yet.")

with tab3:
    st.subheader("Add a Lesson")
    if len(students) == 0:
        st.info("Add a student first in the Students tab.")
    else:
        student = st.selectbox("Student", students, key="lesson_student")
        number = st.number_input("Number of lessons", min_value=1, max_value=10, value=1, step=1)
        lesson_date = st.date_input("Lesson date")
        modality = st.selectbox("Modality", ["Online", "Offline"])
        note = st.text_input("Note (optional)")

        if st.button("Save Lesson"):
            add_class(student, number, lesson_date.isoformat(), modality, note)
            st.success("Lesson saved ✅")
            st.rerun()

with tab4:
    st.subheader("Add a Payment (New Package)")
    if len(students) == 0:
        st.info("Add a student first in the Students tab.")
    else:
        student_p = st.selectbox("Student", students, key="pay_student")
        lessons_paid = st.number_input("Lessons paid", min_value=1, max_value=500, value=44, step=1)
        payment_date = st.date_input("Payment date")
        paid_amount = st.number_input("Paid amount", min_value=0.0, value=0.0, step=100.0)
        modality_p = st.selectbox("Modality", ["Online", "Offline"], key="pay_modality")

        if st.button("Save Payment"):
            add_payment(student_p, lessons_paid, payment_date.isoformat(), paid_amount, modality_p)
            st.success("Payment saved ✅")
            st.rerun()
