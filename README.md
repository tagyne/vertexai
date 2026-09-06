# Student Performance MLOps

Ce projet montre, de bout en bout, comment mettre un modèle de machine
learning en production sur Google Cloud.

À partir du dataset Kaggle **Student Performance and Study Habits**, il
prévoit la note finale d’un étudiant (`final_exam_score`). Le modèle utilisé
est un `RandomForestRegressor`. Le projet sert surtout à apprendre et à
illustrer une démarche MLOps reproductible : préparer les données, entraîner
et évaluer le modèle, l’enregistrer dans Vertex AI, le déployer sur un
endpoint et surveiller ses prédictions.

Il n’y a pas de serveur web local à démarrer. Le calcul se fait dans un
pipeline Vertex AI exécuté dans Google Cloud.

## Fonctionnement en quelques mots

Le projet est composé de deux parties :

- **Terraform** crée l’infrastructure durable : APIs GCP, bucket ML, secrets
  Kaggle, compte de service, endpoint Vertex AI, monitoring et fonction Cloud.
- **Le pipeline Vertex AI** télécharge les données, les prépare, entraîne le
  modèle, calcule la MAE et la RMSE, publie le modèle, le déploie et configure
  le monitoring.

Les alertes de dérive créent une demande `PENDING_APPROVAL`. Elles ne
relancent jamais automatiquement un entraînement.

## Prérequis

Installer :

- Python 3.11 ;
- [`uv`](https://docs.astral.sh/uv/) ;
- Terraform >= 1.6 ;
- Google Cloud CLI (`gcloud`) ;
- un projet Google Cloud avec les droits nécessaires pour créer les
  ressources du projet.

Il faut également un compte Kaggle et ses identifiants API. Ils seront placés
dans Secret Manager, jamais dans Git ou dans `terraform.tfvars`. Voir
[docs/kaggle-secrets.md](docs/kaggle-secrets.md).

## Installation locale

Depuis la racine du dépôt :

```bash
uv python pin 3.11
uv sync
uv run pytest -q
```

La dernière commande vérifie le code localement. Elle ne contacte pas un
endpoint Vertex AI réel.

## Configuration Google Cloud

Définir le projet et la région utilisés par les commandes :

```bash
export GOOGLE_CLOUD_PROJECT="votre-projet-gcp"
export VERTEX_REGION="europe-west9"
gcloud config set project "$GOOGLE_CLOUD_PROJECT"
gcloud auth application-default login
```

Le backend Terraform utilise un bucket GCS séparé. Ce bucket doit exister
avant le premier `terraform init` :

```bash
gcloud storage buckets create "gs://vertexai-tf-state-bucket" \
  --location="$VERTEX_REGION" \
  --project="$GOOGLE_CLOUD_PROJECT"
```

Le nom du bucket doit être globalement unique. Si le bucket défini dans
`terraform/backend.tf` a déjà été remplacé, adapter ce fichier avant
`terraform init`.

Créer ensuite le fichier Terraform local :

```bash
cp terraform/terraform.tfvars.example terraform/terraform.tfvars
```

Puis remplacer `your-gcp-project-id` par la valeur de
`GOOGLE_CLOUD_PROJECT`.

## Démarrer le projet

### 1. Créer l’infrastructure

```bash
terraform -chdir=terraform init
terraform -chdir=terraform fmt -check
terraform -chdir=terraform validate
terraform -chdir=terraform plan
terraform -chdir=terraform apply
```

`terraform apply` demande une confirmation et crée les ressources GCP.

### 2. Ajouter les secrets Kaggle

Après `terraform apply`, définir localement les variables Kaggle puis ajouter
leurs valeurs dans Secret Manager :

```bash
export KAGGLE_USERNAME="votre-identifiant-kaggle"
export KAGGLE_KEY="votre-clé-kaggle"

printf '%s' "$KAGGLE_USERNAME" | gcloud secrets versions add kaggle-username \
  --data-file=- --project "$GOOGLE_CLOUD_PROJECT"
printf '%s' "$KAGGLE_KEY" | gcloud secrets versions add kaggle-key \
  --data-file=- --project "$GOOGLE_CLOUD_PROJECT"
```

### 3. Lancer l’entraînement et le déploiement

La commande recommandée lit les sorties Terraform automatiquement :

```bash
uv run python scripts/submit_pipeline.py \
  --project "$GOOGLE_CLOUD_PROJECT" \
  --region "$VERTEX_REGION"
```

Le programme compile le pipeline puis soumet un job Vertex AI. Le job peut
prendre plusieurs minutes. Son suivi se fait dans **Google Cloud Console >
Vertex AI > Pipelines**.

Il est aussi possible de fournir les paramètres manuellement avec
`src.submit`. Le détail est expliqué dans
[docs/monitoring.md](docs/monitoring.md).

## Faire une prédiction

Après un pipeline terminé avec succès, l’endpoint est disponible dans Vertex
AI. Le contrat de requête et l’ordre des neuf variables sont décrits dans
[docs/prediction-contract.md](docs/prediction-contract.md).

Les variables attendues sont `gender`, `study_time_hours`,
`attendance_percent`, `sleep_hours`, `parental_education`, `internet_access`,
`extracurricular_activities`, `part_time_job` et `previous_grade`.

## Arrêter le projet

Le projet n’a pas de processus local permanent : fermer le terminal arrête
seulement la commande locale, pas le job déjà envoyé à Vertex AI.

- Pour arrêter un pipeline en cours, ouvrir **Vertex AI > Pipelines**, choisir
  le job puis utiliser **Cancel**.
- Pour arrêter le modèle qui sert les prédictions, retirer ou désactiver son
  déploiement depuis l’endpoint dans **Vertex AI > Online prediction**.
- Pour arrêter complètement l’environnement, suivre la procédure de nettoyage
  ci-dessous.

## Nettoyer les ressources

Le nettoyage se fait en deux étapes. Commencer par le mode simulation :

```bash
uv run python scripts/cleanup_pipeline_resources.py \
  --project "$GOOGLE_CLOUD_PROJECT" \
  --region "$VERTEX_REGION"
```

Vérifier la liste affichée, puis lancer la suppression avec confirmation
explicite :

```bash
uv run python scripts/cleanup_pipeline_resources.py \
  --project "$GOOGLE_CLOUD_PROJECT" \
  --region "$VERTEX_REGION" \
  --execute
```

Ce script supprime les jobs terminés, leurs métadonnées, les modèles labellisés
et les fichiers temporaires du bucket ML. Il ne supprime pas le backend
Terraform, le compte de service, l’IAM ni l’endpoint stable.

Quand le nettoyage dynamique est terminé, supprimer l’infrastructure durable
avec Terraform :

```bash
terraform -chdir=terraform destroy
```

Cette commande supprime notamment le bucket ML et les secrets gérés par
Terraform. Elle ne supprime pas le bucket backend Terraform créé
manuellement. Pour une explication détaillée, voir
[docs/cleanup.md](docs/cleanup.md).

## Structure du dépôt

| Dossier ou fichier | Rôle |
|---|---|
| `src/pipeline.py` | Définition du pipeline Vertex AI |
| `src/submit.py` | Compilation et soumission manuelle du pipeline |
| `src/predict.py` | Validation du contrat et appel de prédiction |
| `scripts/submit_pipeline.py` | Soumission avec les sorties Terraform |
| `scripts/cleanup_pipeline_resources.py` | Nettoyage contrôlé des ressources dynamiques |
| `terraform/` | Infrastructure GCP |
| `functions/` | Fonction de demande de réentraînement |
| `tests/` | Tests locaux |
| `docs/` | Guides détaillés |

## Commandes utiles

| Commande | Utilité |
|---|---|
| `uv sync` | Installer les dépendances |
| `uv run pytest -q` | Lancer les tests |
| `terraform -chdir=terraform plan` | Prévisualiser les changements GCP |
| `uv run python scripts/submit_pipeline.py --project "$GOOGLE_CLOUD_PROJECT"` | Lancer un pipeline |
| `uv run python scripts/cleanup_pipeline_resources.py --project "$GOOGLE_CLOUD_PROJECT" --region "$VERTEX_REGION"` | Simuler un nettoyage |

## Documentation complémentaire

- [Architecture](docs/architecture.md)
- [Secrets Kaggle](docs/kaggle-secrets.md)
- [Contrat de prédiction](docs/prediction-contract.md)
- [Monitoring et alertes](docs/monitoring.md)
- [Nettoyage](docs/cleanup.md)
