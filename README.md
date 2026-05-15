# AI Data Center Cooling Optimization Platform V3

## Project Structure

```text
.
├── backend
│   ├── app.py
│   ├── requirements.txt
│   ├── controller
│   │   ├── __init__.py
│   │   └── control_loop.py
│   ├── routes
│   │   ├── __init__.py
│   │   └── api.py
│   └── services
│       ├── __init__.py
│       ├── environment.py
│       ├── ml_client.py
│       └── safety.py
└── frontend
    ├── index.html
    ├── package.json
    ├── postcss.config.js
    ├── tailwind.config.js
    ├── vite.config.js
    └── src
        ├── App.jsx
        ├── index.css
        └── main.jsx
```

## Setup

Backend:

```powershell
cd backend
py -3.10 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Frontend:

```powershell
cd frontend
npm.cmd install
```

## Run Locally

Start Flask API:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
py app.py
```

Start React app:

```powershell
cd frontend
npm.cmd run dev
```

Open:

```text
Backend API: http://localhost:5002
ML API: http://localhost:8000
Frontend: http://localhost:5175
```

Train ML model:

```powershell
cd ml
..\backend\.venv\Scripts\python.exe train.py --dataset I:\SURYA\ai_data_center_cooling_dataset.csv
```

Run ML service:

```powershell
cd ml
..\backend\.venv\Scripts\python.exe api.py
```

Optional external ML service endpoint:

```text
POST http://localhost:8000/predict
```
