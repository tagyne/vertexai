# Prediction contract

The endpoint accepts a JSON object with one or more `instances`. Each instance
must contain exactly these nine raw features:

`gender`, `study_time_hours`, `attendance_percent`, `sleep_hours`,
`parental_education`, `internet_access`, `extracurricular_activities`,
`part_time_job`, `previous_grade`.

`student_id`, `final_exam_score`, and `final_grade` are rejected. The response
shape is:

```json
{"predictions": [{"predicted_final_exam_score": 76.4}]}
```

The local contract validator is in `src/predict.py`; `predict_endpoint` uses
ADC and the Vertex AI SDK to call an existing endpoint.
