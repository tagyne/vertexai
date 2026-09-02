# Spec: Vertex AI scikit-learn MLOps MVP

## Objective

Construire en environ une semaine un projet MLOps personnel, propre et présentable dans un portfolio, à partir du dataset Kaggle **Student Performance and Study Habits**.

Le projet prédira `final_exam_score` avec un modèle `RandomForestRegressor`. Il devra démontrer un parcours reproductible de bout en bout : infrastructure GCP provisionnée avec Terraform, entraînement et évaluation dans un pipeline Vertex AI, enregistrement du modèle, déploiement sur un endpoint et appel de prédiction.

L’objectif principal est l’apprentissage pratique de Vertex AI, Terraform et des responsabilités respectives de l’infrastructure et du cycle de vie ML. L’optimisation maximale de la performance n’est pas un objectif du MVP.

## Scope and Ownership

### Terraform owns

- APIs GCP nécessaires ;
- backend distant Terraform dans un bucket GCS dédié ;
- bucket GCS dédié aux données et artefacts ML ;
- service account du pipeline ;
- IAM minimal nécessaire ;
- ressource modèle Vertex AI/Model Registry déclarée par l’infrastructure ;
- endpoint Vertex AI stable.

Toutes les ressources Vertex AI et GCS devront utiliser les labels suivants lorsque le service les supporte :

```text
project    = student-performance-mlops
managed_by = vertex-pipeline
environment = dev
```

### Vertex AI Pipeline owns

- préparation des données ;
- entraînement et évaluation ;
- job d’entraînement et métriques ;
- artefact du modèle ;
- publication de la version issue du run ;
- déploiement direct du modèle sur l’endpoint existant ;
- exécution et métadonnées du pipeline.

Une ressource durable ne doit pas être gérée simultanément par Terraform et le pipeline.

## Tech Stack

- Python 3.11, version épinglée par `.python-version` ;
- `uv` pour l’environnement, les dépendances et l’exécution des commandes Python ;
- scikit-learn avec versions verrouillées dans `pyproject.toml` et `uv.lock` ;
- Google Cloud Vertex AI SDK pour Python ;
- Vertex AI Pipelines ;
- Terraform avec le provider Google ;
- Google Cloud Storage ;
- authentification locale par Application Default Credentials ;
- Git pour le versionnement du code.

Le modèle et le prétraitement seront encapsulés dans un unique `sklearn.pipeline.Pipeline`. Aucun conteneur Docker personnalisé n’est prévu ; le déploiement utilisera un conteneur de prédiction scikit-learn préconstruit compatible avec la version verrouillée.

## Commands

Les commandes devront être documentées et fonctionner depuis la racine du dépôt.

```bash
# Authentification locale
gcloud auth application-default login

# Infrastructure
terraform -chdir=terraform init
terraform -chdir=terraform fmt -check
terraform -chdir=terraform validate
terraform -chdir=terraform plan
terraform -chdir=terraform apply

# Initialisation Python (une seule fois)
uv python pin 3.11
uv sync

# Tests
uv run pytest -q

# Pipeline lancé manuellement
uv run python -m src.submit --project "$GOOGLE_CLOUD_PROJECT" --region "${VERTEX_REGION:-europe-west9}"

# Nettoyage des ressources dynamiques du pipeline
bash scripts/cleanup_pipeline_resources.sh --project "$GOOGLE_CLOUD_PROJECT" --region "${VERTEX_REGION:-europe-west9}"

# Destruction de l’infrastructure Terraform après nettoyage du pipeline
terraform -chdir=terraform destroy
```

Le bucket backend Terraform devra être créé lors d’une étape de bootstrap séparée, avant le premier `terraform init`. Il sera séparé du bucket ML et ne sera pas supprimé par le script de nettoyage du pipeline.

## Project Structure

```text
terraform/
  backend.tf              # backend GCS
  providers.tf            # provider Google et versions
  apis.tf                 # APIs activées
  storage.tf              # buckets GCS
  iam.tf                  # service account et IAM
  vertex_ai.tf            # modèle et endpoint
  variables.tf
  outputs.tf

pyproject.toml             # métadonnées et dépendances du projet
uv.lock                    # résolution reproductible des dépendances
.python-version            # version Python utilisée par uv

src/
  data.py                 # chargement et préparation des données
  train.py                # entraînement et sérialisation
  evaluate.py             # métriques MAE/RMSE
  pipeline.py             # définition du pipeline
  pipeline_components/    # composants d’entraînement et publication
  submit.py               # soumission manuelle du PipelineJob
  predict.py              # appel de l’endpoint

scripts/
  cleanup_pipeline_resources.sh

tests/
  test_data.py
  test_training.py
  test_prediction_contract.py

docs/
  architecture.md
  prediction-contract.md
  cleanup.md
```

## Code Style

Le code Python sera typé, organisé en fonctions courtes et dépourvu de logique GCP implicite. Les paramètres cloud viendront d’arguments CLI ou de variables d’environnement, jamais de valeurs secrètes codées en dur. `uv` sera l’unique outil documenté pour créer l’environnement, synchroniser les dépendances et lancer les commandes Python.

```python
def build_model(random_state: int = 42) -> Pipeline:
    return Pipeline([
        ("preprocessor", build_preprocessor()),
        ("regressor", RandomForestRegressor(
            n_estimators=100,
            random_state=random_state,
            n_jobs=-1,
        )),
    ])
```

Conventions : noms `snake_case` en Python, noms Terraform en `snake_case`, ressources GCP préfixées par le projet, logs structurés et aucune clé JSON dans le dépôt.

## Dataset Contract

Le fichier `student_performance_dataset.csv` contient 1 000 lignes et 12 colonnes, sans valeur manquante :

- identifiant à exclure des features : `student_id` ;
- variables catégorielles : `gender`, `parental_education`, `internet_access`, `extracurricular_activities`, `part_time_job` ;
- variables numériques : `study_time_hours`, `attendance_percent`, `sleep_hours`, `previous_grade` ;
- cible de régression : `final_exam_score` ;
- colonne dérivée à exclure des features pour éviter la fuite de cible : `final_grade`.

Les features d’entraînement seront donc les neuf colonnes restantes après exclusion de `student_id`, `final_exam_score` et `final_grade`.

## Prediction Contract

Le endpoint acceptera les colonnes brutes des neuf features retenues, avec les mêmes noms et types que lors de l’entraînement. `student_id`, `final_exam_score` et `final_grade` ne feront pas partie du payload. Le prétraitement sera appliqué par le pipeline scikit-learn enregistré.

La spécification devra documenter un payload JSON de prédiction et une réponse de la forme :

```json
{
  "instances": [
    {
      "gender": "Female",
      "study_time_hours": 4.0,
      "attendance_percent": 88.0,
      "sleep_hours": 7.0,
      "parental_education": "Bachelors",
      "internet_access": "Yes",
      "extracurricular_activities": "Yes",
      "part_time_job": "No",
      "previous_grade": 76.9
    }
  ]
}
```

```json
{
  "predictions": [
    {"predicted_final_exam_score": 76.4}
  ]
}
```

Le schéma final devra inclure toutes les features retenues par l’entraînement ; cet exemple est illustratif.

## Testing Strategy

- tests unitaires locaux pour le chargement, le nettoyage des données et la construction du pipeline ;
- test d’entraînement sur un petit échantillon déterministe ;
- vérification que MAE et RMSE sont calculées et enregistrées ;
- test du contrat JSON sans dépendre d’un endpoint distant ;
- validation Terraform avec `fmt`, `validate` et `plan` ;
- smoke test après déploiement : une requête réelle à l’endpoint et vérification d’une prédiction numérique ;
- test du script de nettoyage en mode simulation ou avec confirmation refusée.

Le MVP ne fixe pas de seuil de performance ni de déploiement conditionnel : tout modèle produit par un pipeline réussi sera déployé directement.

## Cleanup Contract

Le script `scripts/cleanup_pipeline_resources.sh` devra supprimer uniquement les ressources dynamiques du pipeline : runs terminés, jobs terminés, modèles ou versions explicitement identifiés comme appartenant au projet, et artefacts temporaires GCS.

Il devra afficher les cibles, demander une confirmation, être idempotent et refuser les projets/régions absents. Il ne devra jamais supprimer le bucket backend Terraform, le bucket ML principal, le service account, l’IAM ou l’endpoint géré par Terraform. Ces ressources seront supprimées exclusivement avec Terraform.

## Boundaries

- **Always:** utiliser les ADC locales ; utiliser `uv` ; committer `pyproject.toml`, `.python-version` et `uv.lock` ; valider les entrées ; journaliser les étapes ; exécuter les tests avant validation ; nettoyer les ressources payantes ; conserver les secrets hors Git.
- **Ask first:** modifier le périmètre du MVP ; ajouter une base de données ; ajouter un conteneur Docker personnalisé ; modifier le backend Terraform ; rendre le pipeline automatique ; ajouter du monitoring ou du retraining.
- **Never:** committer une clé de service ou un secret ; supprimer sans confirmation ; faire gérer la même ressource par Terraform et le pipeline ; supprimer le bucket backend avec le script de nettoyage ; désactiver les tests pour faire passer une implémentation.

## Success Criteria

- [ ] `terraform init`, `fmt -check`, `validate` et `plan` réussissent.
- [ ] Les APIs, buckets, service account, IAM, ressource modèle et endpoint sont provisionnés par Terraform.
- [ ] Le dataset Kaggle est disponible dans le bucket ML.
- [ ] Le modèle `RandomForestRegressor` est entraîné avec un prétraitement intégré dans un `sklearn.Pipeline`.
- [ ] MAE et RMSE sont calculées et visibles dans les sorties du pipeline.
- [ ] Le modèle est enregistré dans Vertex AI Model Registry.
- [ ] Le modèle est déployé directement sur l’endpoint Vertex AI.
- [ ] Une requête JSON avec les colonnes brutes retourne une prédiction.
- [ ] Le pipeline est lançable manuellement depuis une commande locale.
- [ ] Le script de nettoyage supprime les ressources dynamiques sans toucher aux ressources Terraform.
- [ ] La documentation permet à une autre personne de reproduire le parcours avec ses propres identifiants GCP.

## Out of Scope

- CI/CD automatique ;
- monitoring avancé ;
- retraining automatique ;
- déploiement conditionnel ;
- tuning intensif des hyperparamètres ;
- versionnement avancé des datasets ;
- Docker personnalisé ;
- interface web ;
- environnement multi-projets ou multi-régions.

## Decisions Confirmed

- Le dataset réel contient 1 000 lignes, 12 colonnes et aucune valeur manquante.
- La cible est `final_exam_score`.
- `student_id` et `final_grade` sont exclus des features ; `final_grade` est exclue pour éviter une fuite de cible.
- Le déploiement utilise un conteneur de prédiction scikit-learn Vertex AI préconstruit.
- Le bucket backend Terraform est créé manuellement par un bootstrap séparé avant `terraform init`.
- Le script de nettoyage cible les ressources avec les labels `project=student-performance-mlops`, `managed_by=vertex-pipeline` et `environment=dev`.
