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
-- Name: attributionscours; Type: TABLE; Schema: public; Owner: neondb_owner
--

CREATE TABLE public.attributionscours (
    attributionid integer NOT NULL,
    enseignantid integer NOT NULL,
    codecours text NOT NULL,
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

CREATE TABLE public.champs (
    champno text NOT NULL,
    champnom text NOT NULL,
    estverrouille boolean DEFAULT false NOT NULL
);


ALTER TABLE public.champs OWNER TO neondb_owner;

--
-- Name: cours; Type: TABLE; Schema: public; Owner: neondb_owner
--

CREATE TABLE public.cours (
    codecours text NOT NULL,
    champno text NOT NULL,
    coursdescriptif text NOT NULL,
    nbperiodes integer NOT NULL,
    nbgroupeinitial integer NOT NULL,
    estcoursautre boolean DEFAULT false NOT NULL,
    CONSTRAINT cours_nbgroupeinitial_check CHECK ((nbgroupeinitial >= 0)),
    CONSTRAINT cours_nbperiodes_check CHECK ((nbperiodes >= 0))
);


ALTER TABLE public.cours OWNER TO neondb_owner;

--
-- Name: enseignants; Type: TABLE; Schema: public; Owner: neondb_owner
--

CREATE TABLE public.enseignants (
    enseignantid integer NOT NULL,
    nomcomplet text NOT NULL, -- Maintenu pour "Prénom Nom" ou nom de tâche fictive
    nom text, -- Nom de famille
    prenom text, -- Prénom
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
-- Name: attributionscours attributionid; Type: DEFAULT; Schema: public; Owner: neondb_owner
--

ALTER TABLE ONLY public.attributionscours ALTER COLUMN attributionid SET DEFAULT nextval('public.attributionscours_attributionid_seq'::regclass);


--
-- Name: enseignants enseignantid; Type: DEFAULT; Schema: public; Owner: neondb_owner
--

ALTER TABLE ONLY public.enseignants ALTER COLUMN enseignantid SET DEFAULT nextval('public.enseignants_enseignantid_seq'::regclass);


--
-- Name: attributionscours attributionscours_pkey; Type: CONSTRAINT; Schema: public; Owner: neondb_owner
--

ALTER TABLE ONLY public.attributionscours
    ADD CONSTRAINT attributionscours_pkey PRIMARY KEY (attributionid);


--
-- Name: champs champs_pkey; Type: CONSTRAINT; Schema: public; Owner: neondb_owner
--

ALTER TABLE ONLY public.champs
    ADD CONSTRAINT champs_pkey PRIMARY KEY (champno);


--
-- Name: cours cours_pkey; Type: CONSTRAINT; Schema: public; Owner: neondb_owner
--

ALTER TABLE ONLY public.cours
    ADD CONSTRAINT cours_pkey PRIMARY KEY (codecours);


--
-- Name: enseignants enseignants_pkey; Type: CONSTRAINT; Schema: public; Owner: neondb_owner
--

ALTER TABLE ONLY public.enseignants
    ADD CONSTRAINT enseignants_pkey PRIMARY KEY (enseignantid);


--
-- Name: idx_attributions_enseignant_cours; Type: INDEX; Schema: public; Owner: neondb_owner
--

CREATE INDEX idx_attributions_enseignant_cours ON public.attributionscours USING btree (enseignantid, codecours);


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

CREATE INDEX idx_enseignants_nom_prenom ON public.enseignants USING btree (nom, prenom);


--
-- Name: attributionscours attributionscours_codecours_fkey; Type: FK CONSTRAINT; Schema: public; Owner: neondb_owner
--

ALTER TABLE ONLY public.attributionscours
    ADD CONSTRAINT attributionscours_codecours_fkey FOREIGN KEY (codecours) REFERENCES public.cours(codecours) ON DELETE RESTRICT;


--
-- Name: attributionscours attributionscours_enseignantid_fkey; Type: FK CONSTRAINT; Schema: public; Owner: neondb_owner
--

ALTER TABLE ONLY public.attributionscours
    ADD CONSTRAINT attributionscours_enseignantid_fkey FOREIGN KEY (enseignantid) REFERENCES public.enseignants(enseignantid) ON DELETE CASCADE;


--
-- Name: cours cours_champno_fkey; Type: FK CONSTRAINT; Schema: public; Owner: neondb_owner
--

ALTER TABLE ONLY public.cours
    ADD CONSTRAINT cours_champno_fkey FOREIGN KEY (champno) REFERENCES public.champs(champno);


--
-- Name: enseignants enseignants_champno_fkey; Type: FK CONSTRAINT; Schema: public; Owner: neondb_owner
--

ALTER TABLE ONLY public.enseignants
    ADD CONSTRAINT enseignants_champno_fkey FOREIGN KEY (champno) REFERENCES public.champs(champno);


--
-- Name: DEFAULT PRIVILEGES FOR SEQUENCES; Type: DEFAULT ACL; Schema: public; Owner: cloud_admin
--

ALTER DEFAULT PRIVILEGES FOR ROLE cloud_admin IN SCHEMA public GRANT ALL ON SEQUENCES TO neon_superuser WITH GRANT OPTION;


--
-- Name: DEFAULT PRIVILEGES FOR TABLES; Type: DEFAULT ACL; Schema: public; Owner: cloud_admin
--

ALTER DEFAULT PRIVILEGES FOR ROLE cloud_admin IN SCHEMA public GRANT ALL ON TABLES TO neon_superuser WITH GRANT OPTION;


--
-- PostgreSQL database dump complete
--