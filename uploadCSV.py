import os  
from fastapi import APIRouter
from fastapi.responses import FileResponse, JSONResponse

router = APIRouter()

@router.get("/api/uploadCSV", response_class=HTMLResponse)
async def upload_form():
    return """
    <html>
        <head>
            <title>Upload CSV</title>
        </head>
        <body>
            <h1>Upload CSV File</h1>
            <form id="uploadForm">
                <input id="fileInput" name="file" type="file" accept=".csv" required>
                <input type="submit" value="Upload">
            </form>

            <div id="loadingMessage" style="display:none; margin-top:1rem; font-weight:bold;">
                Uploading... please wait.
            </div>

            <script>
                const form = document.getElementById('uploadForm');
                const loadingMessage = document.getElementById('loadingMessage');
                const fileInput = document.getElementById('fileInput');

                form.addEventListener('submit', async function(event) {
                    event.preventDefault();
                    loadingMessage.style.display = 'block';

                    const formData = new FormData();
                    formData.append('file', fileInput.files[0]);

                    try {
                        const response = await fetch('/upload', {
                            method: 'POST',
                            body: formData,
                        });
                        if (!response.ok) throw new Error('Upload failed');
                        window.location.href = '/dashboard';  // redirect to dashboard
                    } catch (err) {
                        loadingMessage.textContent = 'Upload failed. Please try again.';
                    }
                });
            </script>
        </body>
    </html>
    """
