# 📊 Grade Insight

**Grade Insight** is a lightweight grading viewer and upload tool that allows teachers to upload marks via CSV and gives students/parents a simple progress dashboard.

---

## 🚀 Features

- 🧑‍🏫 **CSV Template or Google Classroom Upload**
- 🔍 **Automatic Data Cleaning**
- 📈 **Student/Parent Grade Dashboard**
- 🔄 **Smart Updates – Avoids Duplicates**
- 🐳 **Dockerized FastAPI App**

---

## 🛠️ Project Structure

- `main.py` – FastAPI backend app
- `Dockerfile` – Build and run the service
- `requirements.txt` – Python dependencies

---

## 📁 CSV Format

Teachers can upload marks using:
1. The **Grade Insight template** (downloadable from the UI), or  
2. An export from **Google Classroom** (if columns match)

**CSV Structure:**

| A           | B           | C       | D            | E            | ... |
|-------------|-------------|---------|--------------|--------------|-----|
| First Name  | Last Name   | Email   | Assignment 1 | Assignment 2 | ... |
|             |             |         | Date (opt)   | Date (opt)   |     |
|             |             |         | Max Points   | Max Points   |     |
| John        | Smith       | ...     | 18           | 20           |     |
| Jane        | Doe         | ...     | 20           | 17           |     |

---

## 🔁 Workflow

1. Teacher visits the upload page
2. Option to download standardized CSV template
3. Fill in template or export from Google Classroom
4. Upload CSV
5. System:
   - Parses and normalizes data
   - Drops empty or invalid columns
   - Inserts or updates database
6. Upload summary shows:
   - ✅ New entries
   - 🔁 Updated entries
   - ⚠️ Skipped entries (with reasons)
7. Students/parents access individual grade pages
8. Teachers re-upload anytime — data merges cleanly

---

## 🐳 Running Locally

Build and run the container:

```bash
docker build -t grade-insight .
docker run -p 8080:8080 grade-insight
