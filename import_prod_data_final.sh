# import_prod_data_final.sh
#!/bin/bash

# ==============================================================================
# SCRIPT DE LA VICTOIRE - IMPORTATION DES DONNÉES DE PRODUCTION
# Ce script utilise la méthode la plus robuste : exécution directe des commandes
# de gestion de contraintes avant et après l'importation.
# ==============================================================================

set -e # Arrêter le script à la première erreur

# --- ÉTAPE A : CRÉER LE DUMP DE DONNÉES ---
echo "--- ÉTAPE A : Création du dump de données propre ---"
export PGPASSWORD='npg_rGF8m1MDhcHZ'
pg_dump "postgres://neondb_owner:$PGPASSWORD@ep-orange-base-a6wsb37i.us-west-2.aws.neon.tech:5432/gestion_taches_prod?sslmode=require" \
        --data-only \
        --column-inserts \
        -T champ_annee_statut \
        > data_only.sql
echo "Dump créé avec succès."
unset PGPASSWORD
echo ""


# --- ÉTAPE B : RÉINITIALISATION DE LA BASE DE DÉVELOPPEMENT ---
echo "--- ÉTAPE B : Réinitialisation de la base de développement ---"
if [ -z "$DEV_PGHOST" ]; then echo "ERREUR: DEV_PGHOST manquant" && exit 1; fi
export PGPASSWORD=$DEV_PGPASSWORD

echo "Forçage de la déconnexion des autres sessions..."
psql -h $DEV_PGHOST -p $DEV_PGPORT -U $DEV_PGUSER -d postgres -c \
  "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$DEV_PGDATABASE' AND pid <> pg_backend_pid();" > /dev/null
echo "Sessions déconnectées."

dropdb --host=$DEV_PGHOST --port=$DEV_PGPORT --username=$DEV_PGUSER --if-exists $DEV_PGDATABASE
createdb --host=$DEV_PGHOST --port=$DEV_PGPORT --username=$DEV_PGUSER $DEV_PGDATABASE
echo "Base de données réinitialisée avec succès."
echo ""


# --- ÉTAPE C : APPLICATION DU SCHÉMA ---
echo "--- ÉTAPE C : Application du schéma via Alembic ---"
export FLASK_APP=mon_application
flask db upgrade
echo "Schéma de la base de données créé avec succès."
echo ""


# --- ÉTAPE D : IMPORTATION ROBUSTE EN TROIS TEMPS ---
echo "--- ÉTAPE D : Importation Robuste ---"

# D.1 : Désactivation de la contrainte
echo "D.1: Désactivation de la contrainte 'cours_financement_validation_check'..."
psql -h $DEV_PGHOST -p $DEV_PGPORT -U $DEV_PGUSER -d $DEV_PGDATABASE -c \
  "ALTER TABLE public.cours DROP CONSTRAINT IF EXISTS cours_financement_validation_check;"

# D.2 : Importation des données
echo "D.2: Importation des données depuis 'data_only.sql'..."
psql -h $DEV_PGHOST -p $DEV_PGPORT -U $DEV_PGUSER -d $DEV_PGDATABASE \
  --quiet --single-transaction -v ON_ERROR_STOP=1 -f data_only.sql

# D.3 : Réactivation de la contrainte
echo "D.3: Réactivation de la contrainte..."
psql -h $DEV_PGHOST -p $DEV_PGPORT -U $DEV_PGUSER -d $DEV_PGDATABASE -c \
  "ALTER TABLE public.cours ADD CONSTRAINT cours_financement_validation_check CHECK (estcoursautre = false OR financement_code IS NULL);"

echo "Données importées et contraintes restaurées avec succès."
echo ""


# --- ÉTAPE E : VÉRIFICATION FINALE ---
echo "--- ÉTAPE E : VÉRIFICATION DE LA VICTOIRE ---"
echo "--- Utilisateurs ---"
psql -h $DEV_PGHOST -p $DEV_PGPORT -U $DEV_PGUSER -d $DEV_PGDATABASE -c "SELECT COUNT(*) FROM users;"
echo "--- Enseignants ---"
psql -h $DEV_PGHOST -p $DEV_PGPORT -U $DEV_PGUSER -d $DEV_PGDATABASE -c "SELECT COUNT(*) FROM enseignants;"
echo "--- Cours ---"
psql -h $DEV_PGHOST -p $DEV_PGPORT -U $DEV_PGUSER -d $DEV_PGDATABASE -c "SELECT COUNT(*) FROM cours;"
unset PGPASSWORD

# --- NETTOYAGE ---
rm data_only.sql

echo ""
echo "========================================"
echo "=== MISSION ACCOMPLIE. BRAVO. ==="
echo "========================================"