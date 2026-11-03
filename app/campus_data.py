"""Fictional demo data for the campus MCP server: course catalogue, academic calendar, admin procedures."""
import os
import sqlite3

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
DB_PATH = os.path.join(DATA_DIR, "campus.db")

COURSES = [
    ("AI501", "Machine Learning", 6, "Mon 09:00-12:00", "Room B12", "Dr. Benali",
     "Linear models, decision trees, SVMs, ensembles, model evaluation", "Linear algebra, probability",
     "Written exam 60% + project 40%"),
    ("AI502", "Deep Learning", 6, "Tue 14:00-17:00", "Lab GPU-1", "Dr. Amrani",
     "MLPs, CNNs, RNNs, Transformers, training tricks", "AI501", "Project 50% + exam 50%"),
    ("AI503", "Generative AI and LLM Agents", 4, "Thu 09:00-12:00", "Room A03", "Dr. Idrissi",
     "LLMs, prompting, RAG, LangChain, LangGraph agents, MCP", "AI502", "Lab reports 60% + final project 40%"),
    ("CS510", "Advanced Python Programming", 4, "Wed 10:00-12:00", "Lab C2", "Dr. Alaoui",
     "OOP, typing, async, testing, packaging", "Basic Python", "Continuous assessment 100%"),
    ("MA520", "Optimization for Machine Learning", 5, "Fri 09:00-12:00", "Room B05", "Dr. Tazi",
     "Convex optimization, gradient descent, SGD, Adam, constraints", "Calculus, linear algebra",
     "Written exam 70% + homework 30%"),
    ("CV530", "Computer Vision", 5, "Wed 14:00-17:00", "Lab GPU-2", "Dr. Kettani",
     "Image formation, features, detection, segmentation, vision transformers", "AI502",
     "Project 60% + exam 40%"),
]

CALENDAR = [
    ("2026-09-14", "Semester 1 starts"),
    ("2026-10-15", "Deadline for course registration changes"),
    ("2026-11-30", "Deadline for tuition fee payment (2nd installment)"),
    ("2026-12-21", "Winter break starts"),
    ("2027-01-11", "Final exams semester 1 start"),
    ("2027-01-29", "Final exams semester 1 end"),
    ("2027-02-08", "Semester 2 starts"),
    ("2027-06-07", "Final exams semester 2 start"),
]

PROCEDURES = {
    "enrollment certificate": "Request it online in the student portal (Documents > Enrollment certificate). "
                              "Delivered as a signed PDF within 48 h. Free of charge.",
    "transcript": "Request an official transcript at the Registrar's office (Building A, ground floor) with your "
                  "student card. Ready in 5 working days. First copy free, then 20 MAD per copy.",
    "tuition fees": "Fees are paid in two installments by bank transfer or at the finance office. "
                    "Upload the receipt in the student portal.",
    "re-enrollment": "Re-enrollment opens in July in the student portal. Unpaid fees block re-enrollment.",
    "exam absence": "Submit a justification (e.g. medical certificate) to the Registrar within 48 h of the exam.",
}


def init_db(path: str = DB_PATH) -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    con = sqlite3.connect(path)
    con.executescript("""
        DROP TABLE IF EXISTS courses; DROP TABLE IF EXISTS calendar;
        CREATE TABLE courses (code TEXT PRIMARY KEY, title TEXT, ects INTEGER, schedule TEXT, room TEXT,
                              instructor TEXT, topics TEXT, prerequisites TEXT, assessment TEXT);
        CREATE TABLE calendar (date TEXT, event TEXT);
    """)
    con.executemany("INSERT INTO courses VALUES (?,?,?,?,?,?,?,?,?)", COURSES)
    con.executemany("INSERT INTO calendar VALUES (?,?)", CALENDAR)
    con.commit()
    con.close()
    return path
