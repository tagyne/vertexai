# Prediction contract

The client accepts named instances with exactly these nine raw features:

`gender`, `study_time_hours`, `attendance_percent`, `sleep_hours`,
`parental_education`, `internet_access`, `extracurricular_activities`,
`part_time_job`, `previous_grade`.

`student_id`, `final_exam_score`, and `final_grade` are rejected. Before the
request is sent, `src/predict.py` converts each instance to an ordered array
for the prebuilt scikit-learn Vertex AI container. The order is:

`gender`, `parental_education`, `internet_access`,
`extracurricular_activities`, `part_time_job`, `study_time_hours`,
`attendance_percent`, `sleep_hours`, `previous_grade`.

The direct Vertex AI request therefore uses:

```json
{"instances": [["Female", "Bachelors", "Yes", "Yes", "No", 4.0, 88.0, 7.0, 76.9]]}
```

The response shape returned by the local client is:

```json
{"predictions": [{"predicted_final_exam_score": 76.4}]}
```

The local contract validator is in `src/predict.py`; `predict_endpoint` uses
ADC and the Vertex AI SDK to call an existing endpoint.
