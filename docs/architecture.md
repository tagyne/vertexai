# Architecture

Terraform owns the APIs, the ML bucket, the pipeline service account and IAM,
and the stable Vertex AI endpoint. The pipeline owns dataset preparation,
training, evaluation, model artifacts, Model Registry publication and direct
deployment to the existing endpoint.

The Google Terraform provider v6.50.0 does not expose a native
`google_vertex_ai_model` resource. The model therefore cannot be declared as a
Terraform resource without inventing an unsupported provider type. Model
registration is intentionally owned by the pipeline; this is the documented
exception to the high-level ownership target in the MVP spec. The endpoint is
the only durable Vertex resource shared across runs, and it is managed only by
Terraform.

The pipeline uses the prebuilt sklearn 1.5 prediction container and embeds the
preprocessing and regressor in one scikit-learn `Pipeline`. It downloads the
public Kaggle dataset directly with `kagglehub.dataset_download`, so no dataset
upload to Cloud Storage is required.

The downloaded dataset currently contains 102 missing values in the
`parental_education` categorical feature. The preparation stage maps missing
categorical values to `Unknown`; missing numeric values, the target, or schema
columns still fail validation.
