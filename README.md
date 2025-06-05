# Grade Insight

**Grade Insight** is a lightweight FastAPI-based web app for uploading and analyzing student grade data from CSV files. It helps educators clean, process, and visualize grades to give students and parents clear insights into academic performance.

## Features

- Upload CSV grade files
- Auto-clean sparse or incomplete data
- Focus on consistently reported assignments
- Provide meaningful grade summaries
- FastAPI backend for speed and simplicity

## Getting Started

### Prerequisites

- Python 3.9+
- pip

### Install dependencies

```bash
pip install -r requirements.txt
```

### Run the app

```bash
uvicorn main:app --reload
```

Then open [http://localhost:8000](http://localhost:8000) in your browser.

## API Endpoints

- `GET /` – Test endpoint to confirm the API is running
- `POST /upload-csv/` – Upload a CSV file containing student grades

## Folder Structure

```
grade_insight/
├── main.py         # FastAPI app
├── requirements.txt
└── README.md
```

## License

MIT License
