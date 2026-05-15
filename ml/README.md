# V3 ML Cooling Assistant

## Train

```powershell
cd I:\SURYA\v3\ml
..\backend\.venv\Scripts\python.exe train.py --dataset I:\SURYA\ai_data_center_cooling_dataset.csv
```

## Run ML API

```powershell
cd I:\SURYA\v3\ml
..\backend\.venv\Scripts\python.exe api.py
```

Endpoint:

```text
POST http://localhost:8000/predict
```

Body:

```json
{
  "temperature": 25.4,
  "workload": 68,
  "cooling": 58,
  "smoothed_temperature": 25.1,
  "temperature_history": [25.0, 25.2, 25.4]
}
```

