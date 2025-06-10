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

--
-- Data for Name: anneesscolaires; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.anneesscolaires (annee_id, libelle_annee, est_courante) FROM stdin;
1	2024-2025	t
2	2025-2026	f
\.


--
-- Data for Name: champs; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.champs (champno, champnom, estverrouille) FROM stdin;
12	Français	f
13a	Maths	f
13b	Sciences et technologie	f
14	Culture et citoyenneté québécoise	f
17	Univers social	f
19	Sports électroniques	f
19b	Art dramatique	f
09	Éducation physique et à la santé	f
11	Arts plastiques	f
01	Adaptation scolaire	t
08	Anglais langue seconde	t
10	Musique	f
\.


--
-- Data for Name: cours; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.cours (codecours, champno, coursdescriptif, nbperiodes, nbgroupeinitial, estcoursautre, annee_id) FROM stdin;
A1DP36	01	Déficience intellectuelle profonde	2.00	36	f	1
A2EDS2	01	Édu. santé	2.00	1	f	1
A2EDU2	01	Édu. physique	2.00	1	f	1
CHS503	13b	Chimie - SÉ	3.00	2	f	1
COORSC	13b	Coordination - PP Sciences	1.00	2	t	1
FABL4B	13b	Soutien Laboratoire créatif - FABLAB	4.00	1	t	1
FABL8B	13b	Soutien Laboratoire créatif - FABLAB	8.00	1	t	1
MENTOR	13b	Mentorat	4.00	1	t	1
PHS503	13b	Physique - SÉ	3.00	2	f	1
PHY504	13b	Physique	4.00	1	f	1
PHY5T4	13b	Physique (progr.sc.)	4.00	2	f	1
PSC104	13b	PROGRAMME SCIENCES	4.00	3	f	1
PSC204	13b	PROGRAMME SCIENCES	4.00	2	f	1
PSC304	13b	PROGRAMME SCIENCES	4.00	2	f	1
PSC404	13b	PROGRAMME SCIENCES	4.00	2	f	1
PSC502	13b	PROGRAMME SCIENCES	2.00	2	f	1
REAUS1	13b	Ressource sciences	1.00	2	t	1
REAUS2	13b	Ressources autres Sec. 1 à	1.00	3	t	1
SCS104	13b	Science et technologie - SÉ	4.00	3	f	1
SCS203	13b	Science et technologie - SÉ	3.00	3	f	1
SCS305	13b	Science et technologie - SÉ	5.00	4	f	1
SCS444	13b	Science et technologie - SÉ	4.00	1	f	1
SCS446	13b	Science et techno. env. - SÉ	6.00	3	f	1
SCT104	13b	Science et technologie	4.00	10	f	1
SCT203	13b	Science et technologie	3.00	9	f	1
SCT306	13b	Science et technologie	6.00	7	f	1
SCT444	13b	Science et technologie	4.00	6	f	1
SCT446	13b	Science et techno. env. (progr.sc.)	6.00	2	f	1
SCT4T6	13b	Science et techno. env. (progr.sc.)	6.00	2	f	1
SOUSC1	13b	Mesures de soutien - SÉ 1er cycle	1.00	2	t	1
SOUSC2	13b	Mesures de soutien - SÉ 2e cycle	1.00	2	t	1
DRA103	19b	Art dramatique	3.00	2	f	1
DRA203	19b	Art dramatique	3.00	3	f	1
DRA302	19b	Art dramatique (Arts)	2.00	2	f	1
DRA402	19b	Art dramatique (Arts)	2.00	2	f	1
DRA502	19b	Art dramatique (Arts)	2.00	2	f	1
DRS102	19b	Art dramatique - SÉ	2.00	3	f	1
DRS202	19b	Art dramatique - SÉ	2.00	3	f	1
DRS302	19b	Art dramatique (Arts) - SÉ	2.00	4	f	1
RESSAU	19b	Ressources autres Sec. 1 à	1.00	1	t	1
A2FRA9	01	Français	9.00	1	f	1
A2GE02	01	Géographie	2.00	1	f	1
A2HIS2	01	Histoire et édu. citoyenneté	2.00	1	f	1
A2MAT9	01	Mathématique	9.00	1	f	1
A2MUS2	01	Musique	2.00	1	f	1
A2PLA2	01	Arts plastiques	2.00	1	f	1
A2SCT6	01	Science et technologie	6.00	1	f	1
A3CRO2	01	Croissance personnelle	2.00	1	f	1
A3FRA3	01	Français	3.00	1	f	1
A3LOI4	01	Loisirs	4.00	1	f	1
A3MAT3	01	Mathématique	3.00	1	f	1
A3SCH2	01	Sciences humaines	2.00	1	f	1
A3ST20	01	Stage en milieu de travail	20.00	1	f	1
A3VIE2	01	Vie domestique	2.00	1	f	1
A5ANG4	01	Anglais	4.00	4	f	1
A5CUI4	01	Cuisine - Projets	4.00	4	f	1
A5ECR2	01	Éthique et culture religieuse	2.00	4	f	1
A5EDU4	01	Édu. physique et à la santé	4.00	4	f	1
A5FRA7	01	Français	7.00	4	f	1
A5GE02	01	Géographie	2.00	4	f	1
A5HIS2	01	Histoire et édu. citoyenneté	2.00	4	f	1
A5MAT7	01	Mathématique	7.00	4	f	1
A5PLA2	01	Arts plastiques	2.00	4	f	1
A5SCT2	01	Science & technologie	2.00	4	f	1
A61AN2	01	Anglais	2.00	3	f	1
A61AU4	01	Autonomie et participation sociale (APS)	4.00	3	f	1
A61ED2	01	Éducation physique et à la santé	2.00	3	f	1
A61FR6	01	Français	6.00	3	f	1
A61MA6	01	Mathématique	6.00	3	f	1
A61PR4	01	Préparation au marché du travail (PMT)	4.00	3	f	1
A61S06	01	Sensibilisation au monde du travail	6.00	3	f	1
A61SC2	01	Exp technologiques et scientifiques (EST)	2.00	3	f	1
A61TN2	01	Temps non réparti	2.00	3	f	1
A61UN2	01	Univers social	2.00	3	f	1
A62AN2	01	Anglais	2.00	3	f	1
A62AU4	01	Autonomie et participation sociale (APS)	4.00	3	f	1
A62ED2	01	Éducation physique et à la santé	2.00	3	f	1
A62FR4	01	Français	4.00	3	f	1
A62I12	01	IP / Insertion professionnelle	12.00	3	f	1
A62MA4	01	Mathématique	4.00	3	f	1
A62PR4	01	Préparation au marché du travail (PMT)	4.00	3	f	1
A62TN2	01	Temps non réparti	2.00	3	f	1
A62UN2	01	Univers social Géo-Hist.	2.00	3	f	1
A7ANG2	01	Anglais	2.00	2	f	1
A7ECR2	01	Éthique et culture religieuse	2.00	2	f	1
A7EDU2	01	Édu. physique et à la santé	2.00	2	f	1
A7FRA8	01	Français	8.00	2	f	1
A7GE02	01	Géographie	2.00	2	f	1
A7HAB2	01	Habiletés sociales	2.00	2	f	1
A7HIS2	01	Histoire et édu. citoyenneté	2.00	2	f	1
A7MAT8	01	Mathématique	8.00	2	f	1
A7PLA2	01	Arts plastiques	2.00	2	f	1
A7SCT2	01	Science & technologie	2.00	2	f	1
ANG104	08	Anglais 1 rég.	4.00	9	f	1
ANG134	08	Anglais 1 eesl (si l'org. scol. le permet)	4.00	1	f	1
ANG203	08	Anglais	3.00	8	f	1
ANG233	08	Anglais 2 eesl (si l'org. scol. le permet)	3.00	1	f	1
ANG304	08	Anglais 3 rég.	4.00	6	f	1
ANG334	08	Anglais 3 eesl (si l'org. scol. le permet)	4.00	2	f	1
ANG404	08	Anglais 4 rég.	4.00	7	f	1
ANG434	08	Anglais 4 eesl (si l'org. scol. le permet)	4.00	2	f	1
ANG504	08	Anglais 5 rég.	4.00	4	f	1
ANG534	08	Anglais 5 eesl (si l'org. scol. le permet)	4.00	2	f	1
ANS103	08	Anglais 1 rég. - SÉ	3.00	3	f	1
ANS203	08	Anglais 2 rég. - SÉ	3.00	3	f	1
ANS303	08	Anglais 3 rég. - SÉ	3.00	3	f	1
ANS333	08	Anglais 3 eesl (si l'org. scol. le permet)	3.00	1	f	1
ANS403	08	Anglais 4 rég. - SÉ	3.00	4	f	1
ANS503	08	Anglais 5 rég. - SÉ	3.00	3	f	1
ANS533	08	Anglais 5 eesl (si l'org. scol. le permet)	3.00	1	f	1
RESAU2	08	Ressources autres Sec. 2e cycle	1.00	3	t	1
RESS	08	Ressource anglais	1.00	10	t	1
SOUAN1	08	Mesures de soutien - SÉ 1er cycle	1.00	3	t	1
SOUAN2	08	Mesures de soutien - SÉ 2e cycle	1.00	3	t	1
COORDA	09	Coordination - DLTA	1.00	1	t	1
COORVA	09	Coordination Santé active	1.00	2	t	1
EDO402	09	Éduc. physique et à la santé	2.00	4	f	1
EDS101	09	Éduc. physique et à la santé - SÉ	1.00	3	f	1
EDS201	09	Éduc. physique et à la santé - SÉ	1.00	3	f	1
EDS301	09	Éduc. physique et à la santé - SÉ	1.00	4	f	1
EDS401	09	Éduc. physique et à la santé - SÉ	1.00	4	f	1
EDS501	09	Éduc. physique et à la santé - SÉ	1.00	4	f	1
EDU102	09	Éduc. physique et à la santé	2.00	10	f	1
EDU202	09	Éduc. physique et à la santé	2.00	9	f	1
EDU302	09	Éduc. physique et à la santé	2.00	7	f	1
EDU402	09	Éduc. physique et à la santé	2.00	9	f	1
EDU502	09	Éduc. physique et à la santé	2.00	7	f	1
EDU504	09	Éduc. physique à la santé	4.00	3	f	1
EDU544	09	Éduc. phys. opt.	4.00	2	f	1
PDL104	09	PROGRAMME D.L.T.A.	4.00	2	f	1
PDL204	09	PROGRAMME D.L.T.A.	4.00	2	f	1
A63I12	01	IP / Insertion professionnelle	21.60	2	f	1
PSA104	09	PROGRAMME SANTÉ ACTIVE	4.00	3	f	1
A63MA2	01	Mathématique	3.60	2	f	1
A63TN1	01	Temps non réparti	1.80	2	f	1
A63UN1	01	Univers social	1.80	2	f	1
ORTHO	01	Orthopédagogue 28 périodes	28.80	1	f	1
A7CUI4	01	Cuisine	4.00	1	f	1
PSA204	09	PROGRAMME SANTÉ ACTIVE	4.00	3	f	1
PSA304	09	PROGRAMME SANTÉ ACTIVE	4.00	3	f	1
PSA404	09	PROGRAMME SANTÉ ACTIVE	4.00	4	f	1
PSA502	09	PROGRAMME SANTÉ ACTIVE	2.00	3	f	1
MUS103	10	Musique	3.00	2	f	1
MUS203	10	Musique	3.00	1	f	1
MUS302	10	Musique (Arts & option)	2.00	1	f	1
MUS402	10	Musique (Arts & option)	2.00	1	f	1
MUS502	10	Musique (Arts & option)	2.00	1	f	1
COORPL	11	Coordination Arts plastiques	1.00	2	t	1
PAP104	11	PROGRAMME ARTS PLASTIQUES	4.00	1	f	1
PAP204	11	PROGRAMME ARTS PLASTIQUES	4.00	2	f	1
PAP304	11	PROGRAMME ARTS PLASTIQUES	4.00	1	f	1
PAP404	11	PROGRAMME ARTS PLASTIQUES	4.00	2	f	1
PAP502	11	PROGRAMME ARTS PLASTIQUES	2.00	1	f	1
PLA103	11	Arts plastiques	3.00	5	f	1
PLA1P3	11	Arts plastiques	3.00	1	f	1
PLA203	11	Arts plastiques	3.00	4	f	1
PLA2P3	11	Arts plastiques	3.00	2	f	1
PLA302	11	Arts plastiques (Arts)	2.00	3	f	1
PLA3P2	11	Arts plastiques (Arts)	2.00	1	f	1
PLA402	11	Arts plastiques (Arts)	2.00	6	f	1
PLA4P2	11	Arts plastiques (Option Arts)	2.00	2	f	1
PLA502	11	Arts plastiques (Arts)	2.00	3	f	1
PLA5P2	11	Arts plastiques (Arts)	2.00	1	f	1
PLA5P4	11	Arts plastiques	4.00	1	f	1
PLS401	11	Arts plastiques (Arts) - SÉ	1.00	4	f	1
PLS501	11	Arts plastiques (Arts) - SÉ	1.00	4	f	1
RESART	11	Ressources autres en arts	1.00	1	t	1
SOUMAJ	11	Mesures de soutien - SÉ Mise à jour en Arts	1.00	2	t	1
COOREL	12	Coordination Sport électronique	1.00	2	t	1
ENSAID	12	Enseignement Centre d'aide	2.00	2	t	1
FRA107	12	Français	7.00	10	f	1
FRA208	12	Français	8.00	9	f	1
FRA308	12	Français	8.00	8	f	1
FRA406	12	Français	6.00	8	f	1
FRA506	12	Français	6.00	7	f	1
FRS106	12	Français 1 - SÉ	6.00	3	f	1
FRS206	12	Français 2 - SÉ	6.00	3	f	1
FRS306	12	Français 3 - SÉ	6.00	4	f	1
FRS405	12	Français 4 - SÉ	5.00	3	f	1
FRS406	12	Français 4 - SÉ	6.00	1	f	1
FRS506	12	Français 5 - SÉ	6.00	4	f	1
RES001	12	Ressource français - 1er cycle	1.00	21	t	1
SOUFR1	12	Mesures de soutien - SÉ 1er cycle	1.00	4	t	1
SOUFR2	12	Mesures de soutien - SÉ 2e cycle	1.00	7	t	1
CCQ102	14	Cult.cit.qc	2.00	10	f	1
CCQ202	14	Cult.cit.qc	2.00	9	f	1
CCQ402	14	Cult.cit.qc	2.00	9	f	1
CCQ502	14	Cult.cit.qc	2.00	7	f	1
COORSE	14	Coordination - SÉ	12.00	1	t	1
CQS102	14	Cult.cit.qc - SE	2.00	3	f	1
CQS202	14	Cult.cit.qc - SE	2.00	3	f	1
CQS402	14	Cult.cit.qc - SE	2.00	4	f	1
CQS501	14	Cult.cit.qc - SE	1.00	4	f	1
FIN502	17	Éducation financière	2.00	7	f	1
FIS502	17	Éducation financière - SÉ	2.00	4	f	1
GES593	17	Géographie culturelle - SÉ	3.00	2	f	1
HIS304	17	Histoire du Québec et du Canada	4.00	7	f	1
HIS404	17	Histoire du Québec et du Canada	4.00	10	f	1
HSS304	17	Histoire du Québec et du Canada - SÉ	4.00	4	f	1
HSS403	17	Histoire du Québec et du Canada - AM	3.00	3	f	1
HSS404	17	Histoire du Québec et du Canada - AM	4.00	1	f	1
IMC504	17	Initiation au monde de la consommation	4.00	1	f	1
IMS553	17	Initiation au monde de la consommation - SÉ	3.00	2	f	1
MDC502	17	Monde contemporain	2.00	4	f	1
MDC504	17	Monde contemporain	4.00	3	f	1
MDS502	17	Monde contemporain - SÉ	2.00	4	f	1
RESAU1	17	Ressources autres - 2e cycle	1.00	2	t	1
SOU001	17	Mesures de soutien - SÉ	1.00	2	t	1
UNS105	17	Univers social (2 géo. & 3 his.)	5.00	10	f	1
UNS205	17	Univers social (3 géo. & 3 his.)	5.00	9	f	1
USS104	17	Univers social (2 géo. & 2 his.) - SÉ	4.00	3	f	1
USS204	17	Univers social (2 géo. & 2 his.) - SÉ	4.00	3	f	1
PSE104	19	PROGRAMME SPORT ÉLECTRONIQUE	4.00	1	f	1
PSE204	19	PROGRAMME SPORT ÉLECTRONIQUE	4.00	1	f	1
PSE304	19	PROGRAMME SPORT ÉLECTRONIQUE	4.00	1	f	1
PSE404	19	PROGRAMME SPORT ÉLECTRONIQUE	4.00	1	f	1
PSE502	19	PROGRAMME SPORT ÉLECTRONIQUE	2.00	1	f	1
PSE504	19	PROGRAMME SPORT ÉLECTRONIQUE	4.00	1	f	1
COORAI	13a	Coordonnateur Centre d'aide	3.00	1	t	1
ENSAIM	13a	Enseignement Centre d'aide	1.00	4	t	1
MAS125	13a	Mathématique 1 - SÉ	5.00	3	f	1
MAS226	13a	Mathématique 2 - SÉ	6.00	3	f	1
MAS306	13a	Mathématique 3 - SÉ	6.00	4	f	1
MAS4C6	13a	Math. 4 - Culture, société & technique -	6.00	2	f	1
MAS4T6	13a	Math. 4 - Technico-sciences -	6.00	3	f	1
MAS5C5	13a	Math. 5 - Culture, société & technique -	5.00	2	f	1
MAS5T5	13a	Math. 5 - Technico-sciences -	5.00	2	f	1
MAT105	13a	Mathématique	5.00	10	f	1
MAT206	13a	Mathématique	6.00	10	f	1
MAT306	13a	Mathématique	6.00	8	f	1
MAT4C6	13a	Math. 4 - Culture, société & technique	6.00	5	f	1
MAT4T6	13a	Math. 4 - Technico-sciences	6.00	4	f	1
MAT5C4	13a	Math. 5 - Culture, société & technique (4per.)	4.00	3	f	1
MAT5T6	13a	Math. 5 - Technico-sciences	6.00	3	f	1
REAUM1	13a	Ressource math - 1er cycle	1.00	20	t	1
SOUMA1	13a	Mesures de soutien - SÉ 1er cycle	1.00	5	t	1
SOUMA2	13a	Mesures de soutien - SÉ 2e cycle	1.00	5	t	1
SOUMA3	13a	Mesures de soutien - SÉ flottante	1.00	1	t	1
CHI504	13b	Chimie	4.00	1	f	1
CHI5T4	13b	Chimie (progr.sc.)	4.00	2	f	1
A63AU1	01	Autonomie et participation sociale (APS)	1.80	2	f	1
A63FR2	01	Français	3.60	2	f	1
A63PR1	01	Préparation au marché du travail (PMT)	1.80	2	f	1
A7CUI2	01	Cuisine	2.00	2	f	1
COORAI	13a	Coordonnateur Centre d'aide	1.00	1	t	2
COORDA	09	Coordination - DLTA	1.00	1	t	2
COOREL	12	Coordination - Sport électronique	1.00	2	t	2
COORPL	11	Coordination - Arts plastiques	1.00	2	t	2
COORSC	13b	Coordination - PSC	1.00	2	t	2
COORSE	14	Coordination - SÉ	12.00	1	t	2
COORVA	09	Coordination - Santé Active	1.00	2	t	2
ENSAID	12	Enseignement Centre d'aide français	2.00	2	t	2
ENSAIM	13a	Enseignement Centre d'aide mathématiques	1.00	6	t	2
FABL4B	13b	Soutien Laboratoire créatif - FABLAB	4.00	1	t	2
FABL8B	13b	Soutien Laboratoire créatif - FABLAB	8.00	1	t	2
RESSAA	11	Ressources autres - Sec.1 à 5	1.00	1	t	2
RESSAD	19b	Ressources autres - Sec.1 à 5	1.00	1	t	2
RESSAG	08	Enseignement ressource anglais	1.00	14	t	2
RESSAH	17	Ressources autres - Sec.1 à 5	1.00	2	t	2
RESSAU	13b	Ressources autres - Sec. 1 à 5	1.00	5	t	2
RESSFR	12	Enseignement ressource francais	1.00	20	t	2
RESSMT	13a	Enseignement ressource mathématiques	1.00	21	t	2
SOU001	17	Mesures de soutien - SÉ	1.00	2	t	2
SOU003	13a	Mesures de soutien - SÉ flottante	1.00	1	t	2
SOUAG1	08	Mesures de soutien - SÉ 1er cycle	1.00	3	t	2
SOUAG2	08	Mesures de soutien - SÉ 2e cycle	1.00	3	t	2
SOUAP1	11	Mesures de soutien - SÉ Mise à jour arts 1er cycle	1.00	1	t	2
SOUAP2	11	Mesures de soutien - SÉ Mise à jour arts 2e cycle	1.00	1	t	2
SOUFR1	12	Mesures de soutien - SÉ 1er cycle	1.00	5	t	2
SOUFR2	12	Mesures de soutien - SÉ 2e cycle	1.00	5	t	2
SOUMT1	13a	Mesures de soutien - SÉ 1er cycle	1.00	5	t	2
SOUMT2	13a	Mesures de soutien - SÉ 2e cycle	1.00	5	t	2
SOUSC1	13b	Mesures de soutien - SÉ 1er cycle	1.00	2	t	2
SOUSC2	13b	Mesures de soutien - SÉ 2e cycle	1.00	2	t	2
A1DP36	01	Déficience intellectuelle profonde	2.00	36	f	2
A2EDS2	01	Édu. santé	2.00	1	f	2
A2EDU2	01	Édu. physique	2.00	1	f	2
A2FRA9	01	Français	9.00	1	f	2
A2GEO2	01	Géographie	2.00	1	f	2
A2HIS2	01	Histoire et édu. citoyenneté	2.00	1	f	2
A2MAT9	01	Mathématique	9.00	1	f	2
A2MUS2	01	Musique	2.00	1	f	2
A2PLA2	01	Arts plastiques	2.00	1	f	2
A2SCT6	01	Science et technologie	6.00	1	f	2
A3CRO2	01	Croissance personnelle	2.00	1	f	2
A3FRA3	01	Français	3.00	1	f	2
A3LOI4	01	Loisirs	4.00	1	f	2
A3MAT3	01	Mathématique	3.00	1	f	2
A3SCH2	01	Sciences humaines	2.00	1	f	2
A3ST20	01	Stage en milieu de travail	20.00	1	f	2
A3VIE2	01	Vie domestique	2.00	1	f	2
A5ANG4	01	Anglais	4.00	2	f	2
A5CUI4	01	Cuisine - Projets	4.00	2	f	2
A5ECR2	01	Éthique et culture religieuse	2.00	2	f	2
A5EDU4	01	Édu. physique et à la santé	4.00	2	f	2
A5FRA7	01	Français	7.00	2	f	2
A5GEO2	01	Géographie	2.00	2	f	2
A5HIS2	01	Histoire et édu. citoyenneté	2.00	2	f	2
A5MAT7	01	Mathématique	7.00	2	f	2
A5PLA2	01	Arts plastiques	2.00	2	f	2
A5SCT2	01	Science & technologie	2.00	2	f	2
A63AU1	01	Autonomie et participation sociale (APS)	1.00	1	f	2
A63ED2	01	Éducation physique et à la santé	2.00	1	f	2
A63FR2	01	Français	2.00	1	f	2
A63I12	01	IP / Insertion professionnelle	12.00	1	f	2
A63IN8	01	IP / Insertion professionnelle	8.00	1	f	2
A63MA2	01	Mathématique	2.00	1	f	2
A63PR1	01	Préparation au marché du travail (PMT)	1.00	1	f	2
A63PR4	01	Préparation au marché du travail (PMT)	4.00	1	f	2
A63TN1	01	Temps non réparti	1.00	1	f	2
A63UN1	01	Univers social	1.00	1	f	2
A7ANG2	01	Anglais	2.00	2	f	2
A7CUI4	01	Cuisine	4.00	2	f	2
A7ECR2	01	Éthique et culture religieuse	2.00	2	f	2
A7EDU2	01	Édu. physique et à la santé	2.00	2	f	2
A7FRA8	01	Français	8.00	2	f	2
A7GEO2	01	Géographie	2.00	2	f	2
A7HAB2	01	Habiletés sociales	2.00	2	f	2
A7HIS2	01	Histoire et édu. citoyenneté	2.00	2	f	2
A7MAT8	01	Mathématique	8.00	2	f	2
A7PLA2	01	Arts plastiques	2.00	2	f	2
A7SCT2	01	Science & technologie	2.00	2	f	2
AFPT36	01	Formation préparatoire au travail	1.00	36	f	2
ANG104	08	Anglais 1 rég.	4.00	7	f	2
ANG134	08	Anglais 1 eesl (si l'org. scol. le permet)	4.00	3	f	2
ANG203	08	Anglais 2	3.00	7	f	2
ANG233	08	Anglais 2 eesl (si l'org. scol. le permet)	3.00	3	f	2
ANG304	08	Anglais 3 rég.	4.00	6	f	2
ANG334	08	Anglais 3 eesl (si l'org. scol. le permet)	4.00	2	f	2
ANG404	08	Anglais 4 rég.	4.00	5	f	2
ANG434	08	Anglais 4 eesl (si l'org. scol. le permet)	4.00	2	f	2
ANG504	08	Anglais 5 rég.	4.00	4	f	2
ANG534	08	Anglais 5 eesl (si l'org. scol. le permet)	4.00	3	f	2
ANS103	08	Anglais 1 rég. - SÉ	3.00	3	f	2
ANS203	08	Anglais 2 rég. - SÉ	3.00	3	f	2
ANS303	08	Anglais 3 rég. - SÉ	3.00	2	f	2
ANS333	08	Anglais 3 eesl (si l'org. scol. le permet)	3.00	2	f	2
ANS403	08	Anglais 4 rég. - SÉ	3.00	2	f	2
ANS433	08	Anglais 4 eesl (si l'org. scol. le permet)	3.00	2	f	2
ANS503	08	Anglais 5 rég. - SÉ	3.00	2	f	2
ANS533	08	Anglais 5 eesl (si l'org. scol. le permet)	3.00	2	f	2
ANS5C1	08	Anglais I. sec. (prog. local) - SÉ	1.00	2	f	2
CCQ102	14	Cult.cit.qc	2.00	10	f	2
CCQ202	14	Cult.cit.qc	2.00	10	f	2
CCQ402	14	Cult.cit.qc	2.00	7	f	2
CCQ502	14	Cult.cit.qc	2.00	7	f	2
CHI504	13b	Chimie 5	4.00	1	f	2
CHI5T4	13b	Chimie (progr.sc.)	4.00	2	f	2
CHS503	13b	Chimie - SÉ	3.00	2	f	2
CQS102	14	Cult.cit.qc - SE	2.00	3	f	2
CQS202	14	Cult.cit.qc - SE	2.00	3	f	2
CQS402	14	Cult.cit.qc - SE	2.00	4	f	2
CQS501	14	Cult.cit.qc - SE	1.00	4	f	2
DRA103	19b	Art dramatique	3.00	2	f	2
DRA203	19b	Art dramatique	3.00	4	f	2
DRA302	19b	Art dramatique (Arts)	2.00	3	f	2
DRA402	19b	Art dramatique (Arts)	2.00	2	f	2
DRA502	19b	Art dramatique (Arts)	2.00	2	f	2
DRO402	19b	Art dramatique (Arts)	2.00	1	f	2
DRS102	19b	Art dramatique - SÉ	2.00	3	f	2
DRS202	19b	Art dramatique - SÉ	2.00	3	f	2
DRS302	19b	Art dramatique (Arts) - SÉ	2.00	4	f	2
EDO402	09	Éduc. physique et à la santé	2.00	1	f	2
EDS101	09	Éduc. physique et à la santé - SÉ	1.00	3	f	2
EDS201	09	Éduc. physique et à la santé - SÉ	1.00	3	f	2
EDS301	09	Éduc. physique et à la santé - SÉ	1.00	4	f	2
EDS401	09	Éduc. physique et à la santé - SÉ	1.00	4	f	2
EDS501	09	Éduc. physique et à la santé - SÉ	1.00	4	f	2
EDU102	09	Éduc. physique et à la santé	2.00	5	f	2
EDU1P2	09	Éduc. physique et à la santé - Prog. DLTA	2.00	2	f	2
EDU1V2	09	Éduc. physique et à la santé - Prog. santé active	2.00	3	f	2
EDU202	09	Éduc. physique et à la santé	2.00	4	f	2
EDU2P2	09	Éduc. physique et à la santé - Prog. DLTA	2.00	2	f	2
EDU2V2	09	Éduc. physique et à la santé - Prog. santé active	2.00	4	f	2
EDU302	09	Éduc. physique et à la santé	2.00	4	f	2
EDU3P2	09	Éduc. physique et à la santé - Prog. DLTA	2.00	1	f	2
EDU3V2	09	Éduc. physique et à la santé - Prog. santé active	2.00	3	f	2
EDU402	09	Éduc. physique et à la santé	2.00	7	f	2
EDU502	09	Éduc. physique et à la santé	2.00	7	f	2
EDU504	09	Éduc. physique à la santé	4.00	2	f	2
EDU544	09	Éduc. phys. opt.	4.00	1	f	2
FIN502	17	Éducation financière	2.00	7	f	2
FIS502	17	Éducation financière - SÉ	2.00	4	f	2
FRA107	12	Français 1	7.00	10	f	2
FRA208	12	Français 2	8.00	10	f	2
FRA308	12	Français 3	8.00	8	f	2
FRA406	12	Français 4	6.00	7	f	2
FRA506	12	Français 5	6.00	7	f	2
FRS106	12	Français 1 - SÉ	6.00	3	f	2
FRS206	12	Français 2 - SÉ	6.00	3	f	2
FRS306	12	Français 3 - SÉ	6.00	4	f	2
FRS405	12	Français 4 - SÉ	5.00	4	f	2
FRS506	12	Français 5 - SÉ	6.00	4	f	2
GEO594	17	Géographie culturelle	4.00	1	f	2
GES593	17	Géographie culturelle - SÉ	3.00	2	f	2
HIS304	17	Histoire du Québec et du Canada	4.00	8	f	2
HIS404	17	Histoire du Québec et du Canada	4.00	9	f	2
HSS304	17	Histoire du Québec et du Canada - SÉ	4.00	4	f	2
HSS403	17	Histoire du Québec et du Canada - AM	3.00	4	f	2
IMC504	17	Initiation au monde de la consommation	4.00	1	f	2
IMS553	17	Initiation au monde de la consommation - SÉ	3.00	2	f	2
MAS125	13a	Mathématique 1 - SÉ	5.00	3	f	2
MAS226	13a	Mathématique 2 - SÉ	6.00	3	f	2
MAS306	13a	Mathématique 3 - SÉ	6.00	4	f	2
MAS4C6	13a	Math. 4 - Culture, société & technique -	6.00	2	f	2
MAS4T6	13a	Math. 4 - Technico-sciences -	6.00	3	f	2
MAS5C4	13a	Math. 5 - Culture, société & technique -	4.00	2	f	2
MAS5T5	13a	Math. 5 - Technico-sciences -	5.00	2	f	2
MAT105	13a	Mathématique 1	5.00	10	f	2
MAT206	13a	Mathématique 2	6.00	10	f	2
MAT2R6	13a	Mathématique 2 reprise - REPRISE	6.00	2	f	2
MAT306	13a	Mathématique 3	6.00	8	f	2
MAT4C6	13a	Math. 4 - Culture, société & technique	6.00	4	f	2
MAT4T6	13a	Math. 4 - Technico-sciences	6.00	3	f	2
MAT5C4	13a	Math. 5 - Culture, société & technique (4per.)	4.00	3	f	2
MAT5T6	13a	Math. 5 - Technico-sciences	6.00	4	f	2
MDC502	17	Monde contemporain	2.00	6	f	2
MDC504	17	Monde contemporain	4.00	3	f	2
MDS502	17	Monde contemporain - SÉ	2.00	4	f	2
MENTOR	13b	Mentorat	5.00	1	f	2
MUS103	10	Musique	3.00	1	f	2
MUS203	10	Musique	3.00	1	f	2
MUS302	10	Musique (Arts & option)	2.00	1	f	2
MUS402	10	Musique (Arts & option)	2.00	1	f	2
MUS502	10	Musique (Arts & option)	2.00	1	f	2
ORTHO	01	Orthopédagogue 28 périodes	28.80	1	f	2
PAP104	11	PROGRAMME ARTS PLASTIQUES	4.00	2	f	2
PAP204	11	PROGRAMME ARTS PLASTIQUES	4.00	1	f	2
PAP304	11	PROGRAMME ARTS PLASTIQUES	4.00	1	f	2
PAP402	11	Arts plastiques (Arts)	2.00	1	f	2
PAP404	11	PROGRAMME ARTS PLASTIQUES	4.00	1	f	2
PAP502	11	PROGRAMME ARTS PLASTIQUES	2.00	1	f	2
PDL104	09	PROGRAMME D.L.T.A.	4.00	2	f	2
PDL204	09	PROGRAMME D.L.T.A.	4.00	2	f	2
PDL304	09	PROGRAMME D.L.T.A.	4.00	1	f	2
PHS503	13b	Physique - SÉ	3.00	2	f	2
PHY504	13b	Physique 5	4.00	1	f	2
PHY5T4	13b	Physique (progr.sc.)	4.00	2	f	2
PLA103	11	Arts plastiques	3.00	5	f	2
PLA1P3	11	Arts plastiques	3.00	2	f	2
PLA203	11	Arts plastiques	3.00	4	f	2
PLA2P3	11	Arts plastiques	3.00	1	f	2
PLA302	11	Arts plastiques (Arts)	2.00	4	f	2
PLA3P2	11	Arts plastiques (Arts)	2.00	1	f	2
PLA402	11	Arts plastiques (Arts)	2.00	3	f	2
PLA4P2	11	Arts plastiques (Option Arts)	2.00	1	f	2
PLA502	11	Arts plastiques (Arts)	2.00	4	f	2
PLA5P2	11	Arts plastiques (Arts)	2.00	1	f	2
PLA5P4	11	Arts plastiques	4.00	1	f	2
PLO402	11	Arts plastiques (Arts)	2.00	1	f	2
PLS401	11	Arts plastiques (Arts) - SÉ	1.00	4	f	2
PLS501	11	Arts plastiques (Arts) - SÉ	1.00	4	f	2
PSA104	09	PROGRAMME SANTÉ ACTIVE	4.00	3	f	2
PSA204	09	PROGRAMME SANTÉ ACTIVE	4.00	4	f	2
PSA304	09	PROGRAMME SANTÉ ACTIVE	4.00	3	f	2
PSA404	09	PROGRAMME SANTÉ ACTIVE	4.00	3	f	2
PSA502	09	PROGRAMME SANTÉ ACTIVE	2.00	3	f	2
PSC104	13b	PROGRAMME SCIENCES	4.00	2	f	2
PSC204	13b	PROGRAMME SCIENCES	4.00	2	f	2
PSC304	13b	PROGRAMME SCIENCES	4.00	2	f	2
PSC404	13b	PROGRAMME SCIENCES	4.00	2	f	2
PSC502	13b	PROGRAMME SCIENCES	2.00	2	f	2
PSE104	19	PROGRAMME SPORT ÉLECTRONIQUE	4.00	1	f	2
PSE204	19	PROGRAMME SPORT ÉLECTRONIQUE	4.00	1	f	2
PSE304	19	PROGRAMME SPORT ÉLECTRONIQUE	4.00	1	f	2
PSE404	19	PROGRAMME SPORT ÉLECTRONIQUE	4.00	1	f	2
PSE502	19	PROGRAMME SPORT ÉLECTRONIQUE	2.00	1	f	2
PSE504	19	PROGRAMME SPORT ÉLECTRONIQUE	4.00	1	f	2
SCS104	13b	Science et technologie - SÉ	4.00	3	f	2
SCS203	13b	Science et technologie - SÉ	3.00	3	f	2
SCS305	13b	Science et technologie - SÉ	5.00	4	f	2
SCS446	13b	Science et technologie - SÉ	6.00	4	f	2
SCT104	13b	Science et technologie	4.00	8	f	2
SCT1P4	13b	Science et technologie - Programme sciences	4.00	2	f	2
SCT203	13b	Science et technologie	3.00	8	f	2
SCT2P3	13b	Science et technologie - Programme sciences	3.00	2	f	2
SCT306	13b	Science et technologie	6.00	6	f	2
SCT3P6	13b	Science et technologie - Programme sciences	6.00	2	f	2
SCT444	13b	Science et technologie	4.00	4	f	2
SCT446	13b	Science et techno. env.	6.00	2	f	2
SCT4T6	13b	Science et techno. env. (progr.sc.)	6.00	2	f	2
UNS105	17	Univers social (2 géo. & 3 his.)	5.00	10	f	2
UNS205	17	Univers social (3 géo. & 3 his.)	5.00	10	f	2
USS104	17	Univers social (2 géo. & 2 his.) - SÉ	4.00	3	f	2
USS204	17	Univers social (2 géo. & 2 his.) - SÉ	4.00	3	f	2
\.


--
-- Data for Name: enseignants; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.enseignants (enseignantid, nomcomplet, nom, prenom, champno, esttempsplein, estfictif, peutchoisirhorschampprincipal, annee_id) FROM stdin;
781	01-Tâche restante-1	\N	\N	01	t	t	f	2
782	11-Tâche restante-1	\N	\N	11	t	t	f	1
689	Catherine Beaulac	Beaulac	Catherine	01	t	f	f	2
690	Martine Boivin	Boivin	Martine	01	t	f	f	2
691	Marjolaine Cartier	Cartier	Marjolaine	01	t	f	f	2
692	Anny Chagnon	Chagnon	Anny	01	f	f	f	2
693	Sylvie Croteau	Croteau	Sylvie	01	t	f	f	2
694	Isabelle Gauthier	Gauthier	Isabelle	01	t	f	f	2
695	Stéphanie Houle	Houle	Stéphanie	01	t	f	f	2
696	Catherine Mc Gee	Mc Gee	Catherine	01	t	f	f	2
697	Marie-Andrée Nolette	Nolette	Marie-Andrée	01	t	f	f	2
698	Diane Noël	Noël	Diane	01	f	f	f	2
699	Jessica Rochon	Rochon	Jessica	01	t	f	f	2
700	Valérie Martel	Martel	Valérie	01	t	f	f	2
701	Vanessa Martel	Martel	Vanessa	01	t	f	f	2
702	Paule Thériault	Thériault	Paule	01	t	f	f	2
703	Martine Turcotte	Turcotte	Martine	01	t	f	f	2
704	Shamelli Andrewn	Andrewn	Shamelli	08	t	f	f	2
705	Pierre-Étienne Cinq-Mars	Cinq-Mars	Pierre-Étienne	08	t	f	f	2
706	Ann-Marie Côté	Côté	Ann-Marie	08	t	f	f	2
707	Sarah Fallu	Fallu	Sarah	08	t	f	f	2
708	Mélanie Roy	Roy	Mélanie	08	t	f	f	2
709	Luc Salvas	Salvas	Luc	08	t	f	f	2
710	Fedela Volpicella	Volpicella	Fedela	08	t	f	f	2
711	David Bahl	Bahl	David	09	t	f	f	2
712	Joel Chapdelaine	Chapdelaine	Joel	09	t	f	f	2
713	Olivier David	David	Olivier	09	t	f	f	2
714	Alexandre Lauzon-Vallière	Lauzon-Vallière	Alexandre	09	t	f	f	2
715	Jonathan Lavoie	Lavoie	Jonathan	09	t	f	f	2
716	Christian Leclair	Leclair	Christian	09	t	f	f	2
717	Roxanne Pépin	Pépin	Roxanne	09	t	f	f	2
718	Yanick Savoie	Savoie	Yanick	09	t	f	f	2
719	Joanie Drolet	Drolet	Joanie	11	t	f	f	2
720	Cindy Jutras	Jutras	Cindy	11	f	f	f	2
721	Isabelle Roy	Roy	Isabelle	11	f	f	f	2
722	Marjolaine Arpin	Arpin	Marjolaine	12	t	f	f	2
723	Caroline Boisvert	Boisvert	Caroline	12	t	f	f	2
724	NaÏma Bouachrime	Bouachrime	NaÏma	12	t	f	f	2
725	Mathieu Comeau	Comeau	Mathieu	12	t	f	f	2
726	Geneviève Côté	Côté	Geneviève	12	t	f	f	2
727	Mireille Diwan	Diwan	Mireille	12	t	f	f	2
728	David Dubois	Dubois	David	12	t	f	f	2
729	Nathalie Héroux	Héroux	Nathalie	12	t	f	f	2
730	Marie-Michèle Joyal	Joyal	Marie-Michèle	12	t	f	f	2
731	Annie Lacharité	Lacharité	Annie	12	t	f	f	2
732	Isabelle Laflamme	Laflamme	Isabelle	12	t	f	f	2
733	Maude Pellerin	Pellerin	Maude	12	t	f	f	2
734	Alexane Perreault	Perreault	Alexane	12	t	f	f	2
735	Anne-Marie Proulx	Proulx	Anne-Marie	12	t	f	f	2
736	Guylaine Roy	Roy	Guylaine	12	t	f	f	2
737	Mélissa Turcotte	Turcotte	Mélissa	12	t	f	f	2
738	Joanie Bélanger	Bélanger	Joanie	13a	f	f	f	2
739	Karelle Bergeron Gauthier	Bergeron Gauthier	Karelle	13a	f	f	f	2
740	Karine Boivin	Boivin	Karine	13a	t	f	f	2
741	Marie-Andrée Charette	Charette	Marie-Andrée	13a	t	f	f	2
742	Marie-Ève Fontaine	Fontaine	Marie-Ève	13a	t	f	f	2
743	Sophie Gagné	Gagné	Sophie	13a	f	f	f	2
744	Charlie Godin	Godin	Charlie	13a	t	f	f	2
745	Marie-Ève Guillemette	Guillemette	Marie-Ève	13a	t	f	f	2
746	Marie-Andrée Lachapelle	Lachapelle	Marie-Andrée	13a	f	f	f	2
747	Chantal Laliberté	Laliberté	Chantal	13a	f	f	f	2
748	Audrey Leblanc	Leblanc	Audrey	13a	f	f	f	2
749	Thomas Leblanc	Leblanc	Thomas	13a	t	f	f	2
750	Stéphanie Mailhot	Mailhot	Stéphanie	13a	t	f	f	2
751	Hélène Martineau	Martineau	Hélène	13a	t	f	f	2
752	Martin Nadeau	Nadeau	Martin	13a	t	f	f	2
753	Sophie Turcotte	Turcotte	Sophie	13a	t	f	f	2
754	Denis Voyer	Voyer	Denis	13a	t	f	f	2
755	Luce Chapdelaine	Chapdelaine	Luce	13b	t	f	f	2
756	Sylvie Faucher	Faucher	Sylvie	13b	t	f	f	2
757	Patrick Giroux	Giroux	Patrick	13b	t	f	f	2
758	Marylène Lefebvre	Lefebvre	Marylène	13b	t	f	f	2
759	Didier Marion-Vanasse	Marion-Vanasse	Didier	13b	t	f	f	2
760	Mélanie Morin	Morin	Mélanie	13b	t	f	f	2
761	Stéphanie Pépin	Pépin	Stéphanie	13b	t	f	f	2
762	Myriam Taillon-Gardner	Taillon-Gardner	Myriam	13b	f	f	f	2
763	Pascal Tarakdjan	Tarakdjan	Pascal	13b	t	f	f	2
764	Antoine Beaulieu-Michel	Beaulieu-Michel	Antoine	14	t	f	f	2
765	Nancy Dupuis	Dupuis	Nancy	14	t	f	f	2
766	Francine Langlois	Langlois	Francine	14	f	f	f	2
767	Nicolas Spina	Spina	Nicolas	14	f	f	f	2
768	Marie-Andrée Beaudoin	Beaudoin	Marie-Andrée	17	t	f	f	2
769	Pierre Beaudry-Grenier	Beaudry-Grenier	Pierre	17	t	f	f	2
770	Nathalie Caron	Caron	Nathalie	17	t	f	f	2
771	Samuel Desgagné-Leblanc	Desgagné-Leblanc	Samuel	17	t	f	f	2
772	William Dion	Dion	William	17	t	f	f	2
773	Philippe Gignac	Gignac	Philippe	17	t	f	f	2
774	Alexandra Girouard	Girouard	Alexandra	17	t	f	f	2
775	Benjamin Moreau	Moreau	Benjamin	17	t	f	f	2
776	Matthieu Pinard	Pinard	Matthieu	17	t	f	f	2
777	Nathalie Pinard	Pinard	Nathalie	17	t	f	f	2
778	Sébastien Raymond	Raymond	Sébastien	17	t	f	f	2
779	Andréanne Tremblay-Lefebvre	Tremblay-Lefebvre	Andréanne	17	t	f	f	2
780	Audrey Duquette	Duquette	Audrey	19b	t	f	f	2
200	Catherine Beaulac	Beaulac	Catherine	01	t	f	f	1
201	Karine Bergeron	Bergeron	Karine	01	t	f	f	1
202	Louise Boivin	Boivin	Louise	01	t	f	f	1
203	Martine Boivin	Boivin	Martine	01	t	f	f	1
204	Marjolaine Cartier	Cartier	Marjolaine	01	t	f	f	1
205	Anny Chagnon	Chagnon	Anny	01	t	f	f	1
206	Kathleen Côté	Côté	Kathleen	01	t	f	f	1
207	Sylvie Croteau	Croteau	Sylvie	01	t	f	f	1
208	Mélissa Desrosiers	Desrosiers	Mélissa	01	t	f	f	1
209	Samuel Duranceau-Cloutier	Duranceau-Cloutier	Samuel	01	t	f	f	1
210	Isabelle Gauthier	Gauthier	Isabelle	01	t	f	f	1
211	Stéphanie Houle	Houle	Stéphanie	01	t	f	f	1
212	Geneviève Laflamme	Laflamme	Geneviève	01	t	f	f	1
213	Laurence Landry	Landry	Laurence	01	t	f	f	1
214	Mélanie Laprise	Laprise	Mélanie	01	t	f	f	1
216	Annie Maillette	Maillette	Annie	01	t	f	f	1
319	10-Tâche restante-1	\N	\N	10	t	t	f	1
320	08-Tâche restante-1	\N	\N	08	t	t	f	1
321	08-Tâche restante-2	\N	\N	08	t	t	f	1
322	08-Tâche restante-3	\N	\N	08	t	t	f	1
215	Andréanne Leclerc	Leclerc	Andréanne	01	t	f	f	1
217	Valérie Martel	Martel	Valérie	01	t	f	f	1
218	Vanessa Martel	Martel	Vanessa	01	t	f	f	1
219	Catherine Mc Gee	Mc Gee	Catherine	01	t	f	f	1
220	Diane Noël	Noël	Diane	01	f	f	f	1
221	Marie-Andrée Nolette	Nolette	Marie-Andrée	01	t	f	f	1
222	Anne-Marie René	René	Anne-Marie	01	t	f	f	1
223	Jessica Rochon	Rochon	Jessica	01	t	f	f	1
224	Paule Thériault	Thériault	Paule	01	t	f	f	1
225	Marie-Josée Turcotte	Turcotte	Marie-Josée	01	t	f	f	1
226	Martine Turcotte	Turcotte	Martine	01	t	f	f	1
227	Shamelli Andrewn	Andrewn	Shamelli	08	t	f	f	1
228	Pierre-Étienne Cinq-Mars	Cinq-Mars	Pierre-Étienne	08	t	f	f	1
229	Mathieu Dubois	Dubois	Mathieu	08	t	f	f	1
230	Sarah Fallu	Fallu	Sarah	08	t	f	f	1
231	Mélanie Roy	Roy	Mélanie	08	f	f	f	1
232	Luc Salvas	Salvas	Luc	08	t	f	f	1
233	Fedela Volpicella	Volpicella	Fedela	08	t	f	f	1
234	David Bahl	Bahl	David	09	t	f	f	1
235	Jonathan Lavoie	Lavoie	Jonathan	09	t	f	f	1
236	Christian Leclair	Leclair	Christian	09	t	f	f	1
237	Roxanne Pépin	Pépin	Roxanne	09	t	f	f	1
238	Yanick Savoie	Savoie	Yanick	09	t	f	f	1
239	Joanie Drolet	Drolet	Joanie	11	t	f	f	1
240	Mélanie Hébert	Hébert	Mélanie	11	t	f	f	1
241	Cindy Jutras	Jutras	Cindy	11	f	f	f	1
242	Isabelle Roy	Roy	Isabelle	11	t	f	f	1
243	Marjolaine Arpin	Arpin	Marjolaine	12	t	f	f	1
244	Caroline Boisvert	Boisvert	Caroline	12	t	f	f	1
245	Naïma Bouachrime	Bouachrime	Naïma	12	t	f	f	1
246	Mathieu Comeau	Comeau	Mathieu	12	t	f	f	1
247	Geneviève Côté	Côté	Geneviève	12	t	f	f	1
248	Mireille Diwan	Diwan	Mireille	12	t	f	f	1
249	David Dubois	Dubois	David	12	t	f	f	1
250	Nathalie Héroux	Héroux	Nathalie	12	t	f	f	1
251	Annie Lacharité	Lacharité	Annie	12	t	f	f	1
252	Isabelle Laflamme	Laflamme	Isabelle	12	t	f	f	1
253	Maude Pellerin	Pellerin	Maude	12	t	f	f	1
254	Alexane Perreault	Perreault	Alexane	12	t	f	f	1
255	Anne-Marie Proulx	Proulx	Anne-Marie	12	t	f	f	1
256	Guylaine Roy	Roy	Guylaine	12	t	f	f	1
257	Mélissa Turcotte	Turcotte	Mélissa	12	t	f	f	1
258	Antoine Beaulieu-Michel	Beaulieu-Michel	Antoine	14	t	f	f	1
259	Nancy Dupuis	Dupuis	Nancy	14	t	f	f	1
260	Francine Langlois	Langlois	Francine	14	f	f	f	1
261	Nicolas Spina	Spina	Nicolas	14	t	f	f	1
262	Marie-Andrée Beaudoin	Beaudoin	Marie-Andrée	17	t	f	f	1
263	Nathalie Caron	Caron	Nathalie	17	t	f	f	1
264	Samuel Desgagné-Leblanc	Desgagné-Leblanc	Samuel	17	t	f	f	1
265	Philippe Gignac	Gignac	Philippe	17	t	f	f	1
266	Alexandra Girouard	Girouard	Alexandra	17	t	f	f	1
267	Benjamin Moreau	Moreau	Benjamin	17	t	f	f	1
268	Matthieu Pinard	Pinard	Matthieu	17	t	f	f	1
269	Nathalie Pinard	Pinard	Nathalie	17	t	f	f	1
270	Andréanne Tremblay-Lefebvre	Tremblay-Lefebvre	Andréanne	17	t	f	f	1
271	Joanie Bélanger	Bélanger	Joanie	13a	f	f	f	1
272	Karelle Bergeron Gauthier	Bergeron Gauthier	Karelle	13a	t	f	f	1
273	Karine Boivin	Boivin	Karine	13a	t	f	f	1
274	Marie-Ève Fontaine	Fontaine	Marie-Ève	13a	t	f	f	1
275	Sophie Gagné	Gagné	Sophie	13a	f	f	f	1
276	Marie-Andrée Lachapelle	Lachapelle	Marie-Andrée	13a	f	f	f	1
277	Chantal Laliberté	Laliberté	Chantal	13a	f	f	f	1
278	Audrey Leblanc	Leblanc	Audrey	13a	t	f	f	1
279	Thomas Leblanc	Leblanc	Thomas	13a	t	f	f	1
280	Stéphanie Mailhot	Mailhot	Stéphanie	13a	t	f	f	1
281	Hélène Martineau	Martineau	Hélène	13a	t	f	f	1
282	Martin Nadeau	Nadeau	Martin	13a	t	f	f	1
283	Sophie Turcotte	Turcotte	Sophie	13a	f	f	f	1
284	Denis Voyer	Voyer	Denis	13a	t	f	f	1
285	Marie-Pierre Bolduc	Bolduc	Marie-Pierre	13b	t	f	f	1
286	Luce Chapdelaine	Chapdelaine	Luce	13b	t	f	f	1
287	Marie-Andrée Charrette	Charrette	Marie-Andrée	13a	t	f	f	1
288	Sylvie Faucher	Faucher	Sylvie	13b	t	f	f	1
289	Patrick Giroux	Giroux	Patrick	13b	t	f	f	1
290	Marylène Lefebvre	Lefebvre	Marylène	13b	t	f	f	1
291	Didier Marion-Vanasse	Marion-Vanasse	Didier	13b	t	f	f	1
292	Mélanie Morin	Morin	Mélanie	13b	t	f	f	1
293	Stéphanie Pépin	Pépin	Stéphanie	13b	t	f	f	1
294	Myriam Taillon-Gardner	Taillon-Gardner	Myriam	13b	f	f	f	1
295	Pascal Tarakdjan	Tarakdjan	Pascal	13b	t	f	f	1
296	Audrey Duquette	Duquette	Audrey	19b	t	f	f	1
297	Katia Le Gendre	Le Gendre	Katia	19b	t	f	f	1
300	01-Tâche restante-1	\N	\N	01	t	t	f	1
313	09-Tâche restante-1	\N	\N	09	t	t	f	1
316	09-Tâche restante-2	\N	\N	09	t	t	f	1
317	09-Tâche restante-3	\N	\N	09	t	t	f	1
318	09-Tâche restante-4	\N	\N	09	t	t	f	1
\.


--
-- Data for Name: attributionscours; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.attributionscours (attributionid, enseignantid, codecours, nbgroupespris, annee_id_cours) FROM stdin;
7	200	A7ECR2	1	1
8	200	A7FRA8	1	1
177	222	A61PR4	1	1
9	200	A7HAB2	1	1
10	200	A7MAT8	1	1
11	200	A7PLA2	1	1
12	200	A7SCT2	1	1
13	201	A61AN2	1	1
14	201	A61ED2	1	1
15	201	A61FR6	1	1
16	201	A62AU4	1	1
17	201	A62ED2	1	1
18	201	A62FR4	1	1
19	201	A61UN2	1	1
20	201	A61SC2	1	1
21	202	A5CUI4	1	1
22	202	A5ECR2	1	1
23	202	A5ECR2	1	1
24	202	A5EDU4	1	1
25	202	A5EDU4	1	1
26	202	A5SCT2	1	1
27	202	A5SCT2	1	1
28	202	A5ANG4	1	1
29	203	A61AN2	1	1
30	203	A62AU4	1	1
31	203	A62FR4	1	1
32	203	A62TN2	1	1
33	203	A1DP36	1	1
34	203	A1DP36	1	1
35	203	A1DP36	1	1
36	203	A1DP36	1	1
37	203	A1DP36	1	1
38	203	A1DP36	1	1
39	226	ORTHO	1	1
40	204	A63AU1	1	1
41	204	A63AU1	1	1
42	204	A63FR2	1	1
43	204	A63FR2	1	1
44	204	A63MA2	1	1
45	204	A63MA2	1	1
46	204	A63PR1	1	1
47	204	A63PR1	1	1
48	204	A63UN1	1	1
49	204	A63UN1	1	1
50	205	A63I12	1	1
51	205	A63TN1	1	1
56	206	A5CUI4	1	1
57	206	A5FRA7	1	1
58	206	A5GE02	1	1
59	206	A5HIS2	1	1
60	206	A5MAT7	1	1
61	206	A5PLA2	1	1
62	207	A62ED2	1	1
63	207	A62I12	1	1
64	207	A62MA4	1	1
65	207	A62PR4	1	1
66	207	A62UN2	1	1
67	208	A5ANG4	1	1
68	208	A5CUI4	1	1
69	208	A5EDU4	1	1
73	208	A62FR4	1	1
74	209	A2EDS2	1	1
75	209	A2FRA9	1	1
76	209	A2GE02	1	1
77	209	A2HIS2	1	1
78	209	A2MAT9	1	1
79	209	A2EDU2	1	1
81	210	A5HIS2	1	1
82	210	A61AU4	1	1
83	210	A61AU4	1	1
84	210	A61ED2	1	1
85	210	A61MA6	1	1
86	210	A61MA6	1	1
89	210	A5GE02	1	1
94	211	A5ECR2	1	1
95	211	A5FRA7	1	1
96	211	A5GE02	1	1
97	211	A5HIS2	1	1
98	211	A5MAT7	1	1
99	211	A5PLA2	1	1
100	211	A5SCT2	1	1
101	212	A5ANG4	1	1
102	212	A5GE02	1	1
103	212	A5HIS2	1	1
104	212	A5MAT7	1	1
105	212	A5PLA2	1	1
106	212	A5FRA7	1	1
107	213	A61FR6	1	1
108	213	A61PR4	1	1
109	213	A61S06	1	1
110	213	A61SC2	1	1
111	213	A61TN2	1	1
112	213	A61UN2	1	1
113	208	A62AN2	1	1
114	213	A61AN2	1	1
115	214	A62AN2	1	1
116	214	A62I12	1	1
117	214	A62MA4	1	1
118	214	A62PR4	1	1
119	214	A62TN2	1	1
120	215	A3CRO2	1	1
121	215	A3LOI4	1	1
122	215	A3SCH2	1	1
123	215	A3VIE2	1	1
124	215	A61PR4	1	1
125	215	A61S06	1	1
126	215	A61SC2	1	1
127	215	A61TN2	1	1
128	208	A62ED2	1	1
129	215	A61ED2	1	1
130	216	A5ANG4	1	1
131	216	A5CUI4	1	1
132	216	A5ECR2	1	1
133	216	A5FRA7	1	1
134	216	A5MAT7	1	1
135	216	A5SCT2	1	1
136	217	A7ECR2	1	1
137	217	A7ANG2	1	1
138	217	A7GE02	1	1
140	217	A7HIS2	1	1
141	217	A7HAB2	1	1
142	217	A7MAT8	1	1
143	217	A7PLA2	1	1
144	217	A7SCT2	1	1
145	218	A7ANG2	1	1
147	218	A7EDU2	1	1
148	218	A7EDU2	1	1
149	218	A7FRA8	1	1
150	218	A7GE02	1	1
151	218	A7HIS2	1	1
153	219	A63TN1	1	1
154	221	A1DP36	1	1
155	221	A1DP36	1	1
156	221	A1DP36	1	1
157	221	A1DP36	1	1
158	221	A1DP36	1	1
159	221	A1DP36	1	1
160	221	A1DP36	1	1
161	221	A1DP36	1	1
162	221	A1DP36	1	1
163	221	A1DP36	1	1
164	221	A1DP36	1	1
165	221	A1DP36	1	1
166	220	A1DP36	1	1
167	220	A1DP36	1	1
168	220	A1DP36	1	1
169	220	A1DP36	1	1
170	220	A1DP36	1	1
171	220	A2MUS2	1	1
172	220	A2PLA2	1	1
173	220	A2SCT6	1	1
174	208	A62AU4	1	1
175	222	A61AU4	1	1
176	222	A61MA6	1	1
178	222	A61S06	1	1
179	222	A61TN2	1	1
180	222	A61UN2	1	1
181	223	A1DP36	1	1
182	223	A1DP36	1	1
183	223	A1DP36	1	1
184	223	A1DP36	1	1
185	223	A1DP36	1	1
186	223	A1DP36	1	1
187	223	A1DP36	1	1
188	223	A1DP36	1	1
189	223	A1DP36	1	1
190	223	A1DP36	1	1
191	223	A1DP36	1	1
192	223	A1DP36	1	1
193	223	A1DP36	1	1
194	224	A3FRA3	1	1
195	224	A3MAT3	1	1
196	224	A3ST20	1	1
197	225	A62I12	1	1
198	225	A62MA4	1	1
199	225	A62PR4	1	1
200	225	A62TN2	1	1
201	225	A62UN2	1	1
208	300	A5EDU4	1	1
209	300	A5PLA2	1	1
210	300	A61FR6	1	1
212	300	A62UN2	1	1
214	219	A63I12	1	1
216	217	A7CUI2	1	1
217	218	A7CUI2	1	1
218	218	A7CUI4	1	1
219	227	ANG404	1	1
220	227	ANG404	1	1
221	227	ANS303	1	1
222	227	ANG434	1	1
223	227	ANS403	1	1
224	227	ANS403	1	1
225	227	ANG434	1	1
226	228	ANG334	1	1
227	228	ANG334	1	1
228	228	ANS333	1	1
229	228	ANG504	1	1
230	228	ANS503	1	1
231	228	ANS503	1	1
232	228	RESAU2	1	1
233	228	RESAU2	1	1
234	228	SOUAN2	1	1
235	228	SOUAN2	1	1
236	228	RESS	1	1
237	229	ANG104	1	1
238	229	ANG104	1	1
239	229	ANG104	1	1
240	229	ANS203	1	1
241	229	ANS203	1	1
242	229	ANG203	1	1
243	229	ANG203	1	1
244	229	RESS	1	1
245	230	ANG134	1	1
246	230	ANG404	1	1
247	230	ANG404	1	1
248	230	ANG233	1	1
249	230	ANS403	1	1
250	230	ANS403	1	1
251	230	RESS	1	1
252	230	SOUAN1	1	1
253	230	SOUAN2	1	1
254	231	ANG504	1	1
255	231	ANG504	1	1
256	231	ANG534	1	1
257	231	ANS533	1	1
258	231	ANG534	1	1
259	231	RESS	1	1
260	231	SOUAN1	1	1
261	232	ANG104	1	1
262	232	ANG104	1	1
263	232	ANG104	1	1
264	232	ANS103	1	1
265	232	ANS103	1	1
266	232	ANS103	1	1
267	232	ANG104	1	1
268	233	ANG304	1	1
269	233	ANS303	1	1
270	233	ANS303	1	1
271	233	ANG304	1	1
272	233	ANG504	1	1
273	233	ANS503	1	1
274	233	RESS	1	1
275	233	SOUAN1	1	1
276	233	RESS	1	1
285	234	PSA404	1	1
286	234	PSA404	1	1
287	234	PSA404	1	1
288	234	PSA404	1	1
289	234	EDU402	1	1
290	234	EDU402	1	1
291	234	EDU402	1	1
292	234	EDU402	1	1
293	235	PDL104	1	1
294	235	PDL104	1	1
295	235	PDL204	1	1
296	235	PDL204	1	1
297	235	EDU102	1	1
298	235	EDU102	1	1
299	235	EDU202	1	1
300	235	EDU202	1	1
301	236	PSA304	1	1
302	236	PSA304	1	1
303	236	EDU302	1	1
304	236	EDU302	1	1
305	236	EDU302	1	1
306	236	EDU302	1	1
307	236	EDU302	1	1
308	236	EDS301	1	1
309	236	EDS301	1	1
310	236	EDS301	1	1
311	236	EDS301	1	1
312	236	EDU302	1	1
313	237	PSA104	1	1
314	237	PSA104	1	1
315	237	PSA104	1	1
316	237	EDU102	1	1
317	237	EDU102	1	1
318	237	EDU102	1	1
319	237	EDU102	1	1
320	237	EDU102	1	1
321	237	EDU102	1	1
322	235	COORDA	1	1
323	234	COORVA	1	1
324	238	PSA204	1	1
325	238	PSA204	1	1
326	238	PSA204	1	1
327	238	EDU202	1	1
328	238	EDU202	1	1
329	238	EDU202	1	1
330	238	PSA304	1	1
331	238	EDU302	1	1
332	238	COORVA	1	1
377	239	COORPL	1	1
380	240	PLA203	1	1
383	240	PLA203	1	1
384	240	PLA302	1	1
385	240	PLA302	1	1
386	240	PLA302	1	1
414	241	PLA4P2	1	1
417	241	PLA502	1	1
418	241	PLA502	1	1
424	242	PLS401	1	1
425	242	PLS401	1	1
426	242	PLS401	1	1
427	242	PLS401	1	1
429	242	PLS501	1	1
433	242	SOUMAJ	1	1
434	242	SOUMAJ	1	1
454	313	PSA502	1	1
489	313	PSA502	1	1
490	313	PSA502	1	1
491	313	EDU502	1	1
492	313	EDU502	1	1
493	313	EDU502	1	1
494	313	EDU502	1	1
495	313	EDU502	1	1
496	313	EDU544	1	1
497	313	EDU544	1	1
498	313	EDS501	1	1
499	316	EDO402	1	1
500	316	EDO402	1	1
501	316	EDO402	1	1
502	316	EDO402	1	1
503	316	EDU402	1	1
504	316	EDU402	1	1
505	316	EDU402	1	1
506	316	EDU402	1	1
507	316	EDU402	1	1
508	316	EDS401	1	1
509	316	EDS401	1	1
510	316	EDS401	1	1
511	316	EDS401	1	1
512	316	EDS501	1	1
513	316	EDS501	1	1
514	316	EDS501	1	1
515	317	EDS101	1	1
516	317	EDS101	1	1
517	317	EDS101	1	1
518	317	EDS201	1	1
519	317	EDS201	1	1
520	317	EDS201	1	1
521	317	EDU102	1	1
522	317	EDU102	1	1
523	317	EDU502	1	1
524	317	EDU502	1	1
525	317	EDU504	1	1
526	317	EDU202	1	1
527	317	EDU202	1	1
528	317	EDU202	1	1
529	317	EDU202	1	1
531	318	EDU504	1	1
532	300	A62AN2	1	1
533	320	ANG203	1	1
534	320	ANG203	1	1
535	320	ANG304	1	1
536	320	ANG304	1	1
537	320	ANG304	1	1
538	320	ANG304	1	1
539	320	RESS	1	1
540	320	RESS	1	1
541	321	ANG203	1	1
542	321	ANG203	1	1
543	321	ANS203	1	1
544	321	ANG404	1	1
545	321	ANG404	1	1
546	321	ANG404	1	1
547	321	RESS	1	1
548	321	RESS	1	1
549	321	RESAU2	1	1
551	322	ANG104	1	1
552	322	ANG104	1	1
553	322	ANG203	1	1
554	322	ANG203	1	1
564	239	PAP104	1	1
566	239	PAP204	1	1
567	239	PAP304	1	1
570	240	PLA2P3	1	1
577	241	PLA402	1	1
579	241	PAP502	1	1
580	239	PLA103	1	1
581	239	PLA1P3	1	1
582	239	PLA2P3	1	1
583	239	PLA3P2	1	1
585	240	PLA203	1	1
586	240	PLA203	1	1
587	241	PAP404	1	1
588	241	PLA5P2	1	1
589	241	PLA5P4	1	1
590	241	PLS501	1	1
591	241	COORPL	1	1
592	242	PAP404	1	1
593	242	PLA4P2	1	1
594	242	PLA402	1	1
595	242	PLA402	1	1
596	242	PLA402	1	1
599	240	PAP204	1	1
600	242	PLA402	1	1
601	242	PLA402	1	1
602	782	PLA103	1	1
603	782	PLA103	1	1
605	782	PLA103	1	1
606	782	PLA103	1	1
610	242	PLA502	1	1
611	782	PLS501	1	1
612	782	PLS501	1	1
613	719	PAP104	1	2
614	719	PAP204	1	2
615	719	PAP304	1	2
616	719	PLA103	1	2
617	719	PLA1P3	1	2
618	719	PLA2P3	1	2
619	719	PLA3P2	1	2
620	719	COORPL	1	2
\.


--
-- Data for Name: users; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.users (id, username, password_hash, is_admin) FROM stdin;
2	cloutiere	scrypt:32768:8:1$M0mMosJM5JQNZOiw$9ffd2746e7b29f9762f8a7a981a8dfacb77e13dea6c82a96a56af6cc7a42b3de9f14c360a48461c3cb22c47b65f932cd3d10252debf08c02748978de4a4ff03f	t
3	Champ01	scrypt:32768:8:1$oiWMuA2V2d5A7FaN$370f1afd31979aed99e34d9863efe1ecec80bada56fcfb5c8dc8c576c7e65e5f1c483cf10c148ca5fadbd3ba4ea565ebd5cda718c17687ea82d09bd8bff38974	f
4	Champ08	scrypt:32768:8:1$qwy2zbdJuYTjeGEp$e2a54807c2a71bc700ff403681c4b44c3bbba4b459e00f58e4db7ff4ed568b9717fff05a06425791ecf236954ff606507ef1e61114bac621590b0c8ea738f0fb	f
5	Champ09	scrypt:32768:8:1$11GBHU0NMpgCTzAW$415839d93933e54c67266ef1c8d6ab824934f218070ebc843619b2b474a06e33cbaca3b602fd76f11ee3ee35b5be6cb91dfed7258403e05ffc8d9675e239c99f	f
6	Champ10	scrypt:32768:8:1$LmQkUdXlvZNcx198$7416dce3d7f0d05b9aa824f0eeed63a2c7ac2179fa3aff4b2e69dd16a9cba4ccff3fe1a4708df52ddaca6736dfd5b451dda010013b959be24b4873c37911f033	f
7	Champ11	scrypt:32768:8:1$eRx68SYCxjzYqRkE$783288e623bb2fe51c468e9bb565b235ba1247f7bcb87a85c7f89197e186c47b35f7bdc340c84753ad3cf6a95ea27ee9b03b8ff156deb86f6f32672bf0d884a5	f
8	Champ12	scrypt:32768:8:1$tgeOplZAPO0Odn15$ee7a23de242d5106e680fe9fb55f2d4c8a85f25249ac1f50ba288246edb3d2f640f188616609b5992a8f7ac57163f9cfef2145a5ae040ea60850224e59dd1bcc	f
9	Champ13a	scrypt:32768:8:1$A2ESenFZPxxZ588p$23f1ad323f4f48a03fe6b52b753c1cf3a04bb86289e3aa089491a7f6d5d776d22997f244662f6f3451066de174194fce2f2d3da2eee0b03008f76f97004c8e5b	f
10	Champ13b	scrypt:32768:8:1$YZHJfudXmz2uTQss$6f2f474b6349c401d36117738cb3944cdb7e1b3df8f4bd22ab52d46b445c38016811d5cb0901d1afd4aff77625988e0398d957f3928170e9e216365dcdbff0bf	f
11	Champ14	scrypt:32768:8:1$TBTn7uHwwRWXkWsX$7e0e57e451ee08a8b0dd229afd40d00381e6eae50b2d6160541efe5a085856216e3ed350a9646dda592dc07cc19c2e615c10d18ec911fe62386c132b1fddb94c	f
12	Champ17	scrypt:32768:8:1$h2R6ddoiAOcMl6RV$a987561480d658ce5837294a94b2e342c9ddf61e72f500c6c28d6270d50e932669bea22c2b31463dac797eea59b09775f1b33554aad6a6ce7d80c692e1158355	f
13	Champ19	scrypt:32768:8:1$nyJ0DMPBSULljx24$ec7dc5f9108a8ebb85fb7148b66d4a8bff07538224baab9c6c034cf77a519febd9bc7fb080a566b95e2536ecab66989d70138f02f362291ec4c67e96d57fbdb3	f
14	Champ19b	scrypt:32768:8:1$UPNuPIo6ArmwEkmt$06ab0122875e7b2bcccda1d2a595012dd7308e777088f71b2e1f02547065f5980741989e30936ef842a374c68e1875c71ef498673393355e6af29759d6de2681	f
\.


--
-- Data for Name: user_champ_access; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.user_champ_access (user_id, champ_no) FROM stdin;
3	01
4	08
5	09
6	10
7	11
8	12
9	13a
10	13b
11	14
12	17
13	19
14	19b
\.


--
-- Name: anneesscolaires_annee_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.anneesscolaires_annee_id_seq', 2, true);


--
-- Name: attributionscours_attributionid_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.attributionscours_attributionid_seq', 620, true);


--
-- Name: enseignants_enseignantid_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.enseignants_enseignantid_seq', 782, true);


--
-- Name: users_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.users_id_seq', 14, true);


--
-- PostgreSQL database dump complete
--

