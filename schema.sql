-- Schéma de la base de données pour l'application de gestion des tâches enseignants.
-- Version optimisée pour la clarté et la maintenabilité.

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';
SET default_table_access_method = heap;

--
-- Table: users
-- Stocke les informations des utilisateurs pour l'authentification et les permissions.
--
CREATE TABLE public.users (
    id integer NOT NULL,
    username text NOT NULL, -- Nom d'utilisateur unique pour la connexion.
    password_hash text NOT NULL, -- Hachage du mot de passe (ne jamais stocker en clair).
    is_admin boolean DEFAULT false NOT NULL -- Indique si l'utilisateur a des privilèges d'administrateur.
);

ALTER TABLE public.users OWNER TO neondb_owner;

CREATE SEQUENCE public.users_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.users_id_seq OWNER TO neondb_owner;
ALTER SEQUENCE public.users_id_seq OWNED BY public.users.id;

--
-- Table: champs
-- Répertorie les différents champs d'enseignement (ex: Mathématiques, Informatique).
--
CREATE TABLE public.champs (
    champno text NOT NULL, -- Identifiant unique du champ (ex: '420').
    champnom text NOT NULL, -- Nom complet du champ (ex: 'Informatique').
    estverrouille boolean DEFAULT false NOT NULL -- Si true, empêche les modifications d'attributions pour ce champ.
);

ALTER TABLE public.champs OWNER TO neondb_owner;

--
-- Table: user_champ_access
-- Table de liaison pour gérer les droits d'accès des utilisateurs aux champs spécifiques.
--
CREATE TABLE public.user_champ_access (
    user_id integer NOT NULL,
    champ_no text NOT NULL
);

ALTER TABLE public.user_champ_access OWNER TO neondb_owner;


--
-- Table: enseignants
-- Contient les informations sur les enseignants, réels ou fictifs.
--
CREATE TABLE public.enseignants (
    enseignantid integer NOT NULL,
    nomcomplet text NOT NULL, -- Nom complet pour affichage rapide.
    nom text, -- Nom de famille, peut être NULL pour un enseignant fictif.
    prenom text, -- Prénom, peut être NULL pour un enseignant fictif.
    champno text NOT NULL, -- Champ principal de l'enseignant.
    esttempsplein boolean DEFAULT true NOT NULL,
    estfictif boolean DEFAULT false NOT NULL, -- True pour les enseignants représentant une "tâche restante".
    peutchoisirhorschampprincipal boolean DEFAULT false NOT NULL,
    CONSTRAINT enseignants_nom_prenom_si_reel_check CHECK (((estfictif = true) OR ((nom IS NOT NULL) AND (prenom IS NOT NULL))))
);

ALTER TABLE public.enseignants OWNER TO neondb_owner;

CREATE SEQUENCE public.enseignants_enseignantid_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.enseignants_enseignantid_seq OWNER TO neondb_owner;
ALTER SEQUENCE public.enseignants_enseignantid_seq OWNED BY public.enseignants.enseignantid;


--
-- Table: cours
-- Définit les cours disponibles à l'attribution.
--
CREATE TABLE public.cours (
    codecours text NOT NULL, -- Code unique du cours (ex: '420-A10-BB').
    champno text NOT NULL, -- Champ auquel le cours est rattaché.
    coursdescriptif text NOT NULL, -- Description complète du cours.
    nbperiodes numeric(5, 2) NOT NULL, -- Nombre de périodes associées à un groupe de ce cours.
    nbgroupeinitial integer NOT NULL, -- Nombre total de groupes disponibles pour ce cours.
    estcoursautre boolean DEFAULT false NOT NULL, -- True si c'est une activité autre qu'un cours standard.
    CONSTRAINT cours_nbgroupeinitial_check CHECK ((nbgroupeinitial >= 0)),
    CONSTRAINT cours_nbperiodes_check CHECK ((nbperiodes >= 0.0))
);

ALTER TABLE public.cours OWNER TO neondb_owner;

--
-- Table: attributionscours
-- Lie les enseignants aux cours qu'ils prennent en charge.
--
CREATE TABLE public.attributionscours (
    attributionid integer NOT NULL,
    enseignantid integer NOT NULL,
    codecours text NOT NULL,
    nbgroupespris integer DEFAULT 1 NOT NULL,
    CONSTRAINT attributionscours_nbgroupespris_check CHECK ((nbgroupespris > 0))
);

ALTER TABLE public.attributionscours OWNER TO neondb_owner;

CREATE SEQUENCE public.attributionscours_attributionid_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.attributionscours_attributionid_seq OWNER TO neondb_owner;
ALTER SEQUENCE public.attributionscours_attributionid_seq OWNED BY public.attributionscours.attributionid;


--
-- Définition des valeurs par défaut pour les clés primaires auto-incrémentées.
--
ALTER TABLE ONLY public.users ALTER COLUMN id SET DEFAULT nextval('public.users_id_seq'::regclass);
ALTER TABLE ONLY public.enseignants ALTER COLUMN enseignantid SET DEFAULT nextval('public.enseignants_enseignantid_seq'::regclass);
ALTER TABLE ONLY public.attributionscours ALTER COLUMN attributionid SET DEFAULT nextval('public.attributionscours_attributionid_seq'::regclass);


--
-- Définition des contraintes de clé primaire.
--
ALTER TABLE ONLY public.users ADD CONSTRAINT users_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.champs ADD CONSTRAINT champs_pkey PRIMARY KEY (champno);
ALTER TABLE ONLY public.user_champ_access ADD CONSTRAINT user_champ_access_pkey PRIMARY KEY (user_id, champ_no);
ALTER TABLE ONLY public.enseignants ADD CONSTRAINT enseignants_pkey PRIMARY KEY (enseignantid);
ALTER TABLE ONLY public.cours ADD CONSTRAINT cours_pkey PRIMARY KEY (codecours);
ALTER TABLE ONLY public.attributionscours ADD CONSTRAINT attributionscours_pkey PRIMARY KEY (attributionid);


--
-- Définition des contraintes d'unicité.
--
ALTER TABLE ONLY public.users ADD CONSTRAINT users_username_key UNIQUE (username);


--
-- Définition des contraintes de clé étrangère.
--

-- NOTE: ON DELETE CASCADE supprime automatiquement les droits d'un utilisateur si cet utilisateur est supprimé.
ALTER TABLE public.user_champ_access
    ADD CONSTRAINT user_champ_access_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;

-- NOTE: ON DELETE CASCADE supprime automatiquement les droits sur un champ si ce champ est supprimé.
ALTER TABLE public.user_champ_access
    ADD CONSTRAINT user_champ_access_champ_no_fkey FOREIGN KEY (champ_no) REFERENCES public.champs(champno) ON DELETE CASCADE;

ALTER TABLE ONLY public.enseignants
    ADD CONSTRAINT enseignants_champno_fkey FOREIGN KEY (champno) REFERENCES public.champs(champno);

ALTER TABLE ONLY public.cours
    ADD CONSTRAINT cours_champno_fkey FOREIGN KEY (champno) REFERENCES public.champs(champno);

-- NOTE: ON DELETE CASCADE supprime automatiquement les attributions d'un enseignant s'il est supprimé.
-- C'est un comportement crucial pour la fonctionnalité de suppression d'enseignant.
ALTER TABLE ONLY public.attributionscours
    ADD CONSTRAINT attributionscours_enseignantid_fkey FOREIGN KEY (enseignantid) REFERENCES public.enseignants(enseignantid) ON DELETE CASCADE;

-- NOTE: ON DELETE RESTRICT empêche la suppression d'un cours s'il est encore attribué.
-- C'est une sécurité importante pour la fonctionnalité de suppression de cours.
ALTER TABLE ONLY public.attributionscours
    ADD CONSTRAINT attributionscours_codecours_fkey FOREIGN KEY (codecours) REFERENCES public.cours(codecours) ON DELETE RESTRICT;


--
-- Création des index pour optimiser les requêtes courantes.
--
CREATE INDEX idx_enseignants_champno ON public.enseignants USING btree (champno);
CREATE INDEX idx_enseignants_nom_prenom ON public.enseignants USING btree (nom, prenom);
CREATE INDEX idx_cours_champno ON public.cours USING btree (champno);
CREATE INDEX idx_attributions_enseignant_cours ON public.attributionscours USING btree (enseignantid, codecours);


--
-- Fin du script de schéma.
--