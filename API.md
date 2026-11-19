# SignBridge API

The FastAPI service listens on port 8000 by default. Interactive OpenAPI documentation is available at `http://localhost:8000/docs` while it is running. The default database is the local SQLite file `data/signbridge.sqlite3`.

| Method | Route | Purpose |
|---|---|---|
| GET | `/api/health` | API, database, and current recognition mode status |
| GET | `/api/vocabulary` | Search and filter vocabulary with `search`, `category`, `page`, and `page_size` query values |
| GET | `/api/vocabulary/{id}` | Read one vocabulary item |
| GET, PUT | `/api/settings` | Read and synchronize language, Roman Urdu, and voice settings |
| GET | `/api/model-status` | Read trained model metadata and evaluation details |
| GET | `/api/training-report` | Downloadable plain-text evaluation report |
| GET | `/api/confusion-matrix.csv` | Download the measured confusion matrix when evaluation was possible |
| GET | `/api/training-data.csv` | Download collected landmark data |
| GET | `/api/training-counts` | Number of saved landmark examples for each vocabulary ID |
| POST | `/api/recordings` | Save consented landmark examples; request must include `consent: true` |
| POST | `/api/predict` | Predict from 63 normalized landmark values using an available trained classifier |
| POST | `/api/recognize-frame` | Process one transient JPEG from the mobile app; image bytes are not written to disk |
| GET, POST | `/api/history` | Read or save shared recognition history |

## Landmark recording request

```json
{
  "consent": true,
  "examples": [
    {
      "vocabulary_id": "hello",
      "participant": "anonymous",
      "session_id": "session-id",
      "features": [0.0, 0.0, 0.0],
      "frame_width": 640,
      "frame_height": 480,
      "handedness": "Right"
    }
  ]
}
```

The `features` array must contain all 63 finite normalized coordinates. The example above abbreviates the array for documentation; a valid request supplies all 63 values. The server also appends saved examples to `data/sign_data.csv` for the training command. Camera image frames are never added to this CSV.

## Mobile camera request

`POST /api/recognize-frame` accepts one `image/jpeg` body. The backend decodes it in memory, runs MediaPipe Hand Landmarker, and returns the result, landmarks, and normalized features. The endpoint does not create a photo or video file.
