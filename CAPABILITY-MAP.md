# Capability Map: Vertex AI scikit-learn MLOps MVP

| Module id | Responsabilité | Dépend de |
|---|---|---|
| `terraform-foundation` | APIs GCP, backend Terraform GCS, bucket ML, service account et IAM | — |
| `terraform-vertex-resources` | Modèle Vertex AI/Model Registry et endpoint Vertex AI | `terraform-foundation` |
| `model-training` | Préparation, entraînement et évaluation du modèle scikit-learn | `terraform-foundation` |
| `model-publishing` | Export de l’artefact, enregistrement du modèle et déploiement direct | `terraform-vertex-resources`, `model-training` |
| `pipeline-orchestration` | Exécution manuelle du pipeline Vertex AI | `model-training`, `model-publishing` |
| `pipeline-cleanup` | Nettoyage contrôlé des ressources dynamiques créées par le pipeline | `pipeline-orchestration` |

Build order: `terraform-foundation` → `terraform-vertex-resources` → `model-training` → `model-publishing` → `pipeline-orchestration` → `pipeline-cleanup`

Terraform owns durable infrastructure. The pipeline owns run-specific jobs, artifacts, model versions, and deployments. No resource is managed by both systems.
