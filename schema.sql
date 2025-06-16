-- schema.sql

-- ====================================================================
-- SECTION DE NETTOYAGE
-- Supprime toutes les tables existantes dans l'ordre inverse des dépendances
-- pour éviter les erreurs de clés étrangères. C'est plus portable que
-- de changer session_replication_role.
-- ====================================================================

DROP TABLE IF EXISTS public.user_champ_access CASCADE;
DROP TABLE IF EXISTS public.attributionscours CASCADE;
DROP TABLE IF EXISTS public.cours CASCADE;
DROP TABLE IF EXISTS public.enseignants CASCADE;
DROP TABLE IF EXISTS public.champ_annee_statuts CASCADE;
DROP TABLE IF EXISTS public.typesfinancement CASCADE;
DROP TABLE IF EXISTS public.champs CASCADE;
DROP TABLE IF EXISTS public.anneesscolaires CASCADE;
DROP TABLE IF EXISTS public.users CASCADE;


-- ====================================================================
-- SECTION DE CRÉATION
-- Structure originale du fichier schema.sql
-- ====================================================================

--
-- PostgreSQL database dump
--

-- Dumped from database version 16.9
-- Dumped by pg_dump version 16.5

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
-- Name: anneesscolaires; Type: TABLE; Schema: public; Owner: neondb_owner
--

-- Table pour gérer les années scolaires de l'application
CREATE TABLE public.anneesscolaires (
    annee_id integer NOT NULL,
    libelle_annee text NOT NULL, -- Ex: "2023-2024", doit être unique
    est_courante boolean DEFAULT false NOT NULL -- Indique si c'est l'année active pour les utilisateurs non-admins
);


ALTER TABLE public.anneesscolaires OWNER TO neondb_owner;

--
-- Name: anneesscolaires_annee_id_seq; Type: SEQUENCE; Schema: public; Owner: neondb_owner
--

CREATE SEQUENCE public.anneesscolaires_annee_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.anneesscolaires_annee_id_seq OWNER TO neondb_owner;

--
-- Name: anneesscolaires_annee_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: neondb_owner
--

ALTER SEQUENCE public.anneesscolaires_annee_id_seq OWNED BY public.anneesscolaires.annee_id;


--
-- Name: attributionscours; Type: TABLE; Schema: public; Owner: neondb_owner
--

CREATE TABLE public.attributionscours (
    attributionid integer NOT NULL,
    enseignantid integer NOT NULL,
    codecours text NOT NULL,
    annee_id_cours integer NOT NULL, -- Clé étrangère composite vers Cours pour l'année correcte
    nbgroupespris integer DEFAULT 1 NOT NULL,
    CONSTRAINT attributionscours_nbgroupespris_check CHECK ((nbgroupespris > 0))
);


ALTER TABLE public.attributionscours OWNER TO neondb_owner;

--
-- Name: attributionscours_attributionid_seq; Type: SEQUENCE; Schema: public; Owner: neondb_owner
--

CREATE SEQUENCE public.attributionscours_attributionid_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.attributionscours_attributionid_seq OWNER TO neondb_owner;

--
-- Name: attributionscours_attributionid_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: neondb_owner
--

ALTER SEQUENCE public.attributionscours_attributionid_seq OWNED BY public.attributionscours.attributionid;


--
-- Name: champs; Type: TABLE; Schema: public; Owner: neondb_owner
--

-- Table de référence pour les champs (disciplines ou départements)
CREATE TABLE public.champs (
    champno text NOT NULL,
    champnom text NOT NULL
);


ALTER TABLE public.champs OWNER TO neondb_owner;

--
-- Name: champ_annee_statuts; Type: TABLE; Schema: public; Owner: neondb_owner
--

-- Table pour gérer les statuts (verrouillé/confirmé) d'un champ pour une année scolaire spécifique.
CREATE TABLE public.champ_annee_statuts (
    champ_no text NOT NULL,
    annee_id integer NOT NULL,
    est_verrouille boolean DEFAULT false NOT NULL,
    est_confirme boolean DEFAULT false NOT NULL
);


ALTER TABLE public.champ_annee_statuts OWNER TO neondb_owner;


--
-- Name: typesfinancement; Type: TABLE; Schema: public; Owner: neondb_owner
--

-- Table de référence pour les types de financement des cours.
CREATE TABLE public.typesfinancement (
    code text NOT NULL,
    libelle text NOT NULL
);


ALTER TABLE public.typesfinancement OWNER TO neondb_owner;


--
-- Name: cours; Type: TABLE; Schema: public; Owner: neondb_owner
--

CREATE TABLE public.cours (
    codecours text NOT NULL,
    annee_id integer NOT NULL, -- Clé étrangère vers l'année scolaire
    champno text NOT NULL,
    coursdescriptif text NOT NULL,
    nbperiodes numeric(5, 2) NOT NULL,
    nbgroupeinitial integer NOT NULL,
    estcoursautre boolean DEFAULT false NOT NULL,
    financement_code text, -- Clé étrangère vers typesfinancement. NULL si estcoursautre=TRUE.
    CONSTRAINT cours_nbgroupeinitial_check CHECK ((nbgroupeinitial >= 0)),
    CONSTRAINT cours_nbperiodes_check CHECK ((nbperiodes >= 0)),
    -- Contrainte de validation pour 'financement_code':
    -- 1. Si estcoursautre est TRUE, financement_code DOIT être NULL.
    -- 2. Si estcoursautre est FALSE, financement_code peut être NULL ou une valeur valide.
    CONSTRAINT cours_financement_validation_check CHECK (((estcoursautre = false) OR (financement_code IS NULL)))
);


ALTER TABLE public.cours OWNER TO neondb_owner;

--
-- Name: enseignants; Type: TABLE; Schema: public; Owner: neondb_owner
--

CREATE TABLE public.enseignants (
    enseignantid integer NOT NULL,
    annee_id integer NOT NULL, -- Clé étrangère vers l'année scolaire
    nomcomplet text NOT NULL,
    nom text,
    prenom text,
    champno text NOT NULL,
    esttempsplein boolean DEFAULT true NOT NULL,
    estfictif boolean DEFAULT false NOT NULL,
    peutchoisirhorschampprincipal boolean DEFAULT false NOT NULL,
    CONSTRAINT enseignants_nom_prenom_si_reel_check CHECK (((estfictif = true) OR ((nom IS NOT NULL) AND (prenom IS NOT NULL))))
);


ALTER TABLE public.enseignants OWNER TO neondb_owner;

--
-- Name: enseignants_enseignantid_seq; Type: SEQUENCE; Schema: public; Owner: neondb_owner
--

CREATE SEQUENCE public.enseignants_enseignantid_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.enseignants_enseignantid_seq OWNER TO neondb_owner;

--
-- Name: enseignants_enseignantid_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: neondb_owner
--

ALTER SEQUENCE public.enseignants_enseignantid_seq OWNED BY public.enseignants.enseignantid;


--
-- Name: users; Type: TABLE; Schema: public; Owner: neondb_owner
--

CREATE TABLE public.users (
    id integer NOT NULL,
    username text NOT NULL,
    password_hash text NOT NULL,
    is_admin boolean DEFAULT false NOT NULL,
    is_dashboard_only boolean DEFAULT false NOT NULL,
    CONSTRAINT users_role_exclusivity_check CHECK ( NOT (is_admin AND is_dashboard_only) ) -- Un utilisateur ne peut pas être admin ET dashboard_only en même temps.
);


ALTER TABLE public.users OWNER TO neondb_owner;

--
-- Name: users_id_seq; Type: SEQUENCE; Schema: public; Owner: neondb_owner
--

CREATE SEQUENCE public.users_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.users_id_seq OWNER TO neondb_owner;

--
-- Name: users_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: neondb_owner
--

ALTER SEQUENCE public.users_id_seq OWNED BY public.users.id;


--
-- Name: user_champ_access; Type: TABLE; Schema: public; Owner: neondb_owner
--

CREATE TABLE public.user_champ_access (
    user_id integer NOT NULL,
    champ_no text NOT NULL
);


ALTER TABLE public.user_champ_access OWNER TO neondb_owner;

--
-- Name: anneesscolaires annee_id; Type: DEFAULT; Schema: public; Owner: neondb_owner
--

ALTER TABLE ONLY public.anneesscolaires ALTER COLUMN annee_id SET DEFAULT nextval('public.anneesscolaires_annee_id_seq'::regclass);


--
-- Name: attributionscours attributionid; Type: DEFAULT; Schema: public; Owner: neondb_owner
--

ALTER TABLE ONLY public.attributionscours ALTER COLUMN attributionid SET DEFAULT nextval('public.attributionscours_attributionid_seq'::regclass);


--
-- Name: enseignants enseignantid; Type: DEFAULT; Schema: public; Owner: neondb_owner
--

ALTER TABLE ONLY public.enseignants ALTER COLUMN enseignantid SET DEFAULT nextval('public.enseignants_enseignantid_seq'::regclass);


--
-- Name: users id; Type: DEFAULT; Schema: public; Owner: neondb_owner
--

ALTER TABLE ONLY public.users ALTER COLUMN id SET DEFAULT nextval('public.users_id_seq'::regclass);


--
-- Name: anneesscolaires anneesscolaires_libelle_annee_key; Type: CONSTRAINT; Schema: public; Owner: neondb_owner
--

ALTER TABLE ONLY public.anneesscolaires
    ADD CONSTRAINT anneesscolaires_libelle_annee_key UNIQUE (libelle_annee);


--
-- Name: anneesscolaires anneesscolaires_pkey; Type: CONSTRAINT; Schema: public; Owner: neondb_owner
--

ALTER TABLE ONLY public.anneesscolaires
    ADD CONSTRAINT anneesscolaires_pkey PRIMARY KEY (annee_id);


--
-- Name: attributionscours attributionscours_pkey; Type: CONSTRAINT; Schema: public; Owner: neondb_owner
--

ALTER TABLE ONLY public.attributionscours
    ADD CONSTRAINT attributionscours_pkey PRIMARY KEY (attributionid);


--
-- Name: champ_annee_statuts champ_annee_statuts_pkey; Type: CONSTRAINT; Schema: public; Owner: neondb_owner
--

ALTER TABLE ONLY public.champ_annee_statuts
    ADD CONSTRAINT champ_annee_statuts_pkey PRIMARY KEY (champ_no, annee_id);


--
-- Name: champs champs_pkey; Type: CONSTRAINT; Schema: public; Owner: neondb_owner
--

ALTER TABLE ONLY public.champs
    ADD CONSTRAINT champs_pkey PRIMARY KEY (champno);


--
-- Name: cours cours_pkey; Type: CONSTRAINT; Schema: public; Owner: neondb_owner
--

ALTER TABLE ONLY public.cours
    ADD CONSTRAINT cours_pkey PRIMARY KEY (codecours, annee_id);


--
-- Name: enseignants enseignants_nom_prenom_annee_id_key; Type: CONSTRAINT; Schema: public; Owner: neondb_owner
--

ALTER TABLE ONLY public.enseignants
    ADD CONSTRAINT enseignants_nom_prenom_annee_id_key UNIQUE (nom, prenom, annee_id);


--
-- Name: enseignants enseignants_pkey; Type: CONSTRAINT; Schema: public; Owner: neondb_owner
--

ALTER TABLE ONLY public.enseignants
    ADD CONSTRAINT enseignants_pkey PRIMARY KEY (enseignantid);


--
-- Name: typesfinancement typesfinancement_pkey; Type: CONSTRAINT; Schema: public; Owner: neondb_owner
--

ALTER TABLE ONLY public.typesfinancement
    ADD CONSTRAINT typesfinancement_pkey PRIMARY KEY (code);


--
-- Name: user_champ_access user_champ_access_pkey; Type: CONSTRAINT; Schema: public; Owner: neondb_owner
--

ALTER TABLE ONLY public.user_champ_access
    ADD CONSTRAINT user_champ_access_pkey PRIMARY KEY (user_id, champ_no);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: neondb_owner
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: users users_username_key; Type: CONSTRAINT; Schema: public; Owner: neondb_owner
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_username_key UNIQUE (username);


--
-- Name: annee_courante_unique_idx; Type: INDEX; Schema: public; Owner: neondb_owner
--

CREATE UNIQUE INDEX annee_courante_unique_idx ON public.anneesscolaires USING btree (est_courante) WHERE (est_courante = true);


--
-- Name: idx_attributions_enseignant_cours; Type: INDEX; Schema: public; Owner: neondb_owner
--

CREATE INDEX idx_attributions_enseignant_cours ON public.attributionscours USING btree (enseignantid, codecours, annee_id_cours);


--
-- Name: idx_cours_champno; Type: INDEX; Schema: public; Owner: neondb_owner
--

CREATE INDEX idx_cours_champno ON public.cours USING btree (champno);


--
-- Name: idx_enseignants_champno; Type: INDEX; Schema: public; Owner: neondb_owner
--

CREATE INDEX idx_enseignants_champno ON public.enseignants USING btree (champno);


--
-- Name: idx_enseignants_nom_prenom; Type: INDEX; Schema: public; Owner: neondb_owner
--

CREATE INDEX idx_enseignants_nom_prenom ON public.enseignants USING btree (nom COLLATE "fr-CA-x-icu", prenom COLLATE "fr-CA-x-icu");


--
-- Name: attributionscours attributionscours_cours_fkey; Type: FK CONSTRAINT; Schema: public; Owner: neondb_owner
--

ALTER TABLE ONLY public.attributionscours
    ADD CONSTRAINT attributionscours_cours_fkey FOREIGN KEY (codecours, annee_id_cours) REFERENCES public.cours(codecours, annee_id) ON DELETE RESTRICT;


--
-- Name: attributionscours attributionscours_enseignantid_fkey; Type: FK CONSTRAINT; Schema: public; Owner: neondb_owner
--

ALTER TABLE ONLY public.attributionscours
    ADD CONSTRAINT attributionscours_enseignantid_fkey FOREIGN KEY (enseignantid) REFERENCES public.enseignants(enseignantid) ON DELETE CASCADE;


--
-- Name: champ_annee_statuts champ_annee_statuts_annee_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: neondb_owner
--

ALTER TABLE ONLY public.champ_annee_statuts
    ADD CONSTRAINT champ_annee_statuts_annee_id_fkey FOREIGN KEY (annee_id) REFERENCES public.anneesscolaires(annee_id) ON DELETE CASCADE;


--
-- Name: champ_annee_statuts champ_annee_statuts_champ_no_fkey; Type: FK CONSTRAINT; Schema: public; Owner: neondb_owner
--

ALTER TABLE ONLY public.champ_annee_statuts
    ADD CONSTRAINT champ_annee_statuts_champ_no_fkey FOREIGN KEY (champ_no) REFERENCES public.champs(champno) ON DELETE CASCADE;


--
-- Name: cours cours_annee_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: neondb_owner
--

ALTER TABLE ONLY public.cours
    ADD CONSTRAINT cours_annee_id_fkey FOREIGN KEY (annee_id) REFERENCES public.anneesscolaires(annee_id) ON DELETE RESTRICT;


--
-- Name: cours cours_champno_fkey; Type: FK CONSTRAINT; Schema: public; Owner: neondb_owner
--

ALTER TABLE ONLY public.cours
    ADD CONSTRAINT cours_champno_fkey FOREIGN KEY (champno) REFERENCES public.champs(champno);


--
-- Name: cours cours_financement_code_fkey; Type: FK CONSTRAINT; Schema: public; Owner: neondb_owner
--

ALTER TABLE ONLY public.cours
    ADD CONSTRAINT cours_financement_code_fkey FOREIGN KEY (financement_code) REFERENCES public.typesfinancement(code) ON DELETE SET NULL;


--
-- Name: enseignants enseignants_annee_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: neondb_owner
--

ALTER TABLE ONLY public.enseignants
    ADD CONSTRAINT enseignants_annee_id_fkey FOREIGN KEY (annee_id) REFERENCES public.anneesscolaires(annee_id) ON DELETE RESTRICT;


--
-- Name: enseignants enseignants_champno_fkey; Type: FK CONSTRAINT; Schema: public; Owner: neondb_owner
--

ALTER TABLE ONLY public.enseignants
    ADD CONSTRAINT enseignants_champno_fkey FOREIGN KEY (champno) REFERENCES public.champs(champno);


--
-- Name: user_champ_access user_champ_access_champ_no_fkey; Type: FK CONSTRAINT; Schema: public; Owner: neondb_owner
--

ALTER TABLE public.user_champ_access
    ADD CONSTRAINT user_champ_access_champ_no_fkey FOREIGN KEY (champ_no) REFERENCES public.champs(champno) ON DELETE CASCADE;


--
-- Name: user_champ_access user_champ_access_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: neondb_owner
--

ALTER TABLE public.user_champ_access
    ADD CONSTRAINT user_champ_access_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: DEFAULT PRIVILEGES FOR SEQUENCES; Type: DEFAULT ACL; Schema: public; Owner: cloud_admin
--

-- Les commandes ALTER DEFAULT PRIVILEGES ont été retirées car non autorisées
-- ALTER DEFAULT PRIVILEGES FOR ROLE cloud_admin IN SCHEMA public GRANT ALL ON SEQUENCES TO neon_superuser WITH GRANT OPTION;


--
-- Name: DEFAULT PRIVILEGES FOR TABLES; Type: DEFAULT ACL; Schema: public; Owner: cloud_admin
--

-- ALTER DEFAULT PRIVILEGES FOR ROLE cloud_admin IN SCHEMA public GRANT ALL ON TABLES TO neon_superuser WITH GRANT OPTION;


--
-- PostgreSQL database dump complete
--