# Classio

Classio is an AI-native learning platform for teachers, students, and Classio admins.

It helps teachers plan lessons, generate learning materials, assign work, track progress, manage schedules, and use recommendation systems to improve what each student studies next. Students get a guided learning experience with assignments, practice, study plans, and teacher matching. Admins get product, subscription, and model-level visibility into how the system is performing.

This repository contains the main Classio application, built with Streamlit, Supabase, and AI-powered content and recommendation workflows.

## Why Classio exists

Most education tools are either:
- content generators with little instructional memory, or
- dashboards that report activity without helping teachers act on it.

Classio is designed to do both:
- generate useful teaching and learning resources,
- connect those resources to real student progress,
- learn from usage signals over time,
- and turn that into better recommendations for teachers, students, and even Classio admins.

## What Classio does

### Teacher workspace
Teachers can:
- create and manage students
- plan lessons
- assign worksheets, exams, videos, and learning programs
- manage payments and calendars
- view student progress and review requests
- discover or reuse materials from their library
- generate AI-assisted teaching assets

### Student experience
Students can:
- receive assignments from teachers
- practice with recommended materials
- follow assigned learning programs
- request additional support intentionally
- review their progress
- find and connect with teachers

### Admin experience
Admins can:
- manage users, plans, and subscriptions
- monitor platform activity
- inspect AI and ML model reports
- review operational and business metrics
- evaluate whether recommendation models are producing value

## AI and ML capabilities

Classio is not just a CRUD app with AI bolted on. It is moving toward an intelligence-native product.

Current system capabilities in this repo include:
- AI-generated lesson plans
- AI-generated worksheets
- AI-generated exams
- AI-generated learning programs
- video/resource organization tied to educational structure
- student recommendation ranking
- teacher recommendation ranking
- model reporting workflows for recommendation systems
- multilingual UI (English, Spanish and Turkish) and multilingual reporting support
- recommendation feedback loops and usage logging

The ML/reporting layer is intended to answer product-value questions such as:
- Are student recommendations helping learners review or advance effectively?
- Are teacher recommendations helping teachers choose the next best topic, review topic, or unresolved gap?
- Which signals are most predictive?
- Where are the models useful, weak, or miscalibrated?

## Core product areas

- Teacher dashboard
- Student dashboard
- Smart practice
- Smart study plans
- Assignments
- Teacher-student linking
- Learning program generation and assignment
- Worksheet and exam generation
- Video/resource library
- Community/discovery flows
- Google Calendar integration
- Payments and subscriptions
- Admin intelligence and model reports

## Tech stack

- **Frontend/App UI:** Streamlit
- **Backend/Data:** Supabase
- **Language:** Python
- **Visualization:** Plotly, Matplotlib
- **Document export:** `python-docx`, `reportlab`, `pypdf`
- **AI providers:** OpenAI, Google Gemini, OpenRouter-based flows
- **Payments:** Stripe
- **Calendar integration:** Google Calendar API

## Repository structure

```text
app.py                  # Streamlit entrypoint
app_pages/              # Main pages for teacher, student, admin, calendar, analytics, etc.
auth/                   # Login and user session handling
core/                   # Navigation, database access, app state, i18n
helpers/                # Business logic, AI generation, recommendations, reporting, resources
services/               # Auth/admin/subscription/payment services
migrations/             # SQL migrations
database/               # Base SQL / policies
scripts/                # Utility/report generation scripts
tests/                  # Automated tests
static/                 # Logos, fonts, PWA assets
reports/                # Generated ML/report artifacts
translations_*.py       # English, Spanish, Turkish dictionaries
