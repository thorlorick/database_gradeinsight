# Grade Insight 📊

A lightweight web application for uploading and analyzing student grade data from CSV files. Built with FastAPI, Grade Insight helps educators clean, process, and visualize grades to provide meaningful feedback to students and parents.

## 🎯 Goal

Simplify grading transparency and support informed academic decisions by providing an easy-to-use platform for grade management and student progress tracking.

## ✨ Features

- 🧑🏫 **Flexible CSV Upload** - Use Grade Insight template or Google Classroom exports
- 🔍 **Automatic Data Cleaning** - Smart parsing and normalization of grade data
- 📈 **Student/Parent Dashboard** - Clean, simple progress visualization
- 🔄 **Smart Updates** - Intelligent duplicate detection and data merging
- 🐳 **Docker Ready** - Containerized FastAPI application for easy deployment
- ⚡ **Fast Performance** - Built on FastAPI for high-performance grade processing
- 📱 **Responsive Design** - Works seamlessly on desktop and mobile devices

## 🏗️ Architecture

```
Grade Insight/
├── main.py              # FastAPI backend application
├── Dockerfile           # Container build configuration
├── requirements.txt     # Python dependencies
├── templates/           # HTML templates
├── static/             # CSS, JS, and assets
└── data/               # Database and uploaded files
```

## 📊 CSV Upload System

### Supported Formats

Teachers can upload grades using either:
1. **Grade Insight Template** (downloadable from the UI)
2. **Google Classroom Export** (when columns match expected format)

### CSV Structure



### Data Processing Pipeline

1. **Upload** - Teacher uploads CSV file through web interface
2. **Parse** - System automatically parses and validates data structure
3. **Clean** - Remove empty columns and normalize data formats
4. **Process** - Insert new records or update existing ones
5. **Report** - Display upload summary with detailed status

## 🚀 Quick Start

### Using Docker (Recommended)

```bash
# Build the container
docker build -t grade-insight .

# Run the application
docker run -p 8080:8080 grade-insight
```

The application will be available at `http://localhost:8080`

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run the application
uvicorn main:app --host 0.0.0.0 --port 10000
```

## 📋 Usage Workflow

### For Teachers

1. **Access Upload Page** - Navigate to the grade upload interface
2. **Download Template** - Get the standardized CSV template (optional)
3. **Prepare Data** - Fill template or export from Google Classroom
4. **Upload CSV** - Use the web interface to upload grade data
5. **Review Results** - Check upload summary for processing status

### Upload Summary Indicators

- ✅ **New Entries** - Successfully added new student records
- 🔁 **Updated Entries** - Existing records updated with new data
- ⚠️ **Skipped Entries** - Records not processed (with detailed reasons)

### For Students/Parents

- Access individual grade pages using provided links
- View current grades and assignment progress
- Track performance over time

## 🔄 Data Management

### Smart Duplicate Handling

- Automatic detection of existing student records
- Intelligent merging of new and existing grade data
- Prevention of duplicate assignments and scores
- Clean re-upload capability for updated gradebooks

### Data Validation

- Column header validation and normalization
- Empty row and column removal
- Date format standardization
- Grade value validation and cleaning

## 🛠️ Technical Details

### Built With

- **FastAPI** - Modern, fast web framework for building APIs
- **Python 3.8+** - Core application runtime
- **SQLite** - Lightweight database for grade storage
- **HTML/CSS/JavaScript** - Frontend user interface
- **Docker** - Containerization for easy deployment

### API Endpoints

- `GET /` - Main dashboard
- `POST /upload` - CSV file upload
- `GET /template` - Download CSV template
- `GET /student/{id}` - Individual student grade view
- `GET /grades` - Grade summary and management

## 🔒 Privacy & Security

- Local data storage (no external data transmission)
- No personally identifiable information required beyond names
- Secure file upload with validation
- Clean data separation between different uploads

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

If you encounter any issues or have questions:

1. Check the upload summary for detailed error messages
2. Ensure your CSV follows the expected format
3. Verify column headers match the template
4. Open an issue on GitHub for technical problems

---

**Grade Insight** - Making grade management simple and transparent for educators, students, and parents.
