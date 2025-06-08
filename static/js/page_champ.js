// static/js/page_champ.js
// Ce script contient toute la logique d'interaction pour la page de gestion d'un champ.
// Il dépend des variables globales suivantes, qui doivent être initialisées dans le fichier HTML
// avant le chargement de ce script :
// - G_COURS_ENSEIGNEMENT_CHAMP
// - G_COURS_AUTRES_TACHES_CHAMP
// - G_ENSEIGNANTS_INITIAL_DATA (contient maintenant Nom, Prenom en plus de NomComplet)
// - G_CHAMP_NO_ACTUEL
// - G_CHAMP_EST_VERROUILLE

/**
 * Fonction utilitaire pour formater les nombres de périodes.
 * Affiche les décimales uniquement si elles sont non nulles, et évite les zéros superflus.
 * Par exemple : 5.00 -> "5", 1.50 -> "1.5", 0.75 -> "0.75".
 * @param {number} value Le nombre à formater.
 * @returns {string} Le nombre formaté en tant que chaîne de caractères.
 */
function formatPeriodes(value) {
    if (value === null || value === undefined) {
        return '';
    }
    // Utilise Intl.NumberFormat pour gérer la localisation et les décimales significatives.
    // 'fr-CA' assure l'utilisation de la virgule comme séparateur décimal si nécessaire.
    // minimumFractionDigits: 0 pour s'assurer que les nombres entiers n'ont pas de décimales forcées (ex: 5.00 -> 5).
    // maximumFractionDigits: 2 pour permettre jusqu'à deux décimales (ex: 0.75), ajustez si besoin d'une plus grande précision.
    // useGrouping: false pour ne pas utiliser de séparateur de milliers.
    const formatter = new Intl.NumberFormat('fr-CA', {
        minimumFractionDigits: 0,
        maximumFractionDigits: 2,
        useGrouping: false
    });
    return formatter.format(value);
}


document.addEventListener("DOMContentLoaded", function () {
    // Le rendu HTML initial est déjà fait par Jinja2.
    // On se contente d'initialiser les parties dynamiques et de lier les événements.

    // Remplit le tableau des cours restants au chargement.
    regenererTableauCoursRestants();

    // Remplit les tableaux d'attributions pour chaque enseignant.
    if (typeof G_ENSEIGNANTS_INITIAL_DATA !== "undefined") {
        G_ENSEIGNANTS_INITIAL_DATA.forEach((enseignant) => {
            regenererTableauAttributionsEnseignant(enseignant.enseignantid, enseignant.attributions || []);
        });
    }

    // Applique l'état de verrouillage (désactiver les boutons si nécessaire)
    appliquerStatutVerrouillageUI();

    // Ajout des gestionnaires d'événements globaux pour la performance
    const enseignantsSection = document.querySelector(".enseignants-section");
    if (enseignantsSection) {
        enseignantsSection.addEventListener("click", gestionnaireClicsEnseignantsSection);
    }

    document.getElementById("btn-creer-tache-restante")?.addEventListener("click", async function () {
        await creerTacheRestante(this);
    });

    document.getElementById("btn-imprimer-champ")?.addEventListener("click", function () {
        // Replie toutes les cartes pour une impression propre
        document.querySelectorAll(".enseignant-card.detail-visible").forEach((card) => {
            card.classList.remove("detail-visible");
        });
        // Génère le contenu de la page sommaire dynamiquement à partir des données sources.
        genererRapportSommairePourImpression();

        window.print();
    });
});

/**
 * Applique l'état de verrouillage à une seule carte d'enseignant.
 * Désactive les boutons 'Choisir' et 'Retirer' pour les enseignants réels
 * si le champ est verrouillé.
 * @param {HTMLElement} card La carte d'enseignant à traiter.
 */
function appliquerStatutVerrouillagePourCarte(card) {
    // Si le champ n'est pas verrouillé, il n'y a rien à faire ici.
    if (!G_CHAMP_EST_VERROUILLE) {
        // S'assurer que les boutons sont activés si le verrouillage est levé.
        card.querySelectorAll(".btn-retirer-cours, .cours-selection button").forEach((button) => {
            button.disabled = false;
            button.title = "";
        });
        return;
    }

    // On ne verrouille que les enseignants réels, pas les tâches restantes (fictifs).
    if (!card.classList.contains("enseignant-fictif")) {
        card.querySelectorAll(".btn-retirer-cours, .cours-selection button").forEach((button) => {
            button.disabled = true;
            button.title = "Les modifications sont désactivées car le champ est verrouillé.";
        });
    }
}

/**
 * Applique l'état de verrouillage à toutes les cartes d'enseignants sur la page.
 * Utilisé au chargement et après des opérations majeures.
 */
function appliquerStatutVerrouillageUI() {
    document.querySelectorAll(".enseignant-card").forEach(appliquerStatutVerrouillagePourCarte);
}

/**
 * Gère le basculement de l'affichage des détails d'une carte enseignant.
 * Au premier dépliage, génère les listes de cours disponibles.
 * @param {HTMLElement} enseignantCard La carte d'enseignant concernée.
 */
function toggleEnseignantDetails(enseignantCard) {
    if (!enseignantCard) return;
    const etaitVisible = enseignantCard.classList.contains("detail-visible");

    // Replie toutes les autres cartes ouvertes pour n'en afficher qu'une à la fois.
    document.querySelectorAll(".enseignant-card.detail-visible").forEach((card) => {
        if (card !== enseignantCard) card.classList.remove("detail-visible");
    });

    if (!etaitVisible) {
        // Déplie la carte actuelle.
        enseignantCard.classList.add("detail-visible");

        // Génère ou régénère les listes de cours disponibles pour cette carte.
        // On régénère toujours pour s'assurer que les listes sont à jour avec les groupes restants.
        const enseignantId = enseignantCard.id.split("-").pop();
        const ulEnseignement = enseignantCard.querySelector('ul.liste-cours-a-choisir[data-type-cours="enseignement"]');
        if (ulEnseignement) {
            ulEnseignement.innerHTML = genererListeHTMLCoursDispo(G_COURS_ENSEIGNEMENT_CHAMP, enseignantId, "enseignement");
        }
        const ulAutres = enseignantCard.querySelector('ul.liste-cours-a-choisir[data-type-cours="autre"]');
        if (ulAutres) {
            ulAutres.innerHTML = genererListeHTMLCoursDispo(G_COURS_AUTRES_TACHES_CHAMP, enseignantId, "autre");
        }
        // Applique les règles de verrouillage après avoir généré les listes.
        appliquerStatutVerrouillagePourCarte(enseignantCard);
    } else {
        // Replie la carte.
        enseignantCard.classList.remove("detail-visible");
    }
}

/**
 * Régénère le contenu du tableau des attributions pour un enseignant donné.
 * Ce tableau affiche les cours déjà attribués.
 * @param {number} enseignantId L'ID de l'enseignant.
 * @param {Array} attributionsArray La liste de ses attributions brutes.
 */
function regenererTableauAttributionsEnseignant(enseignantId, attributionsArray) {
    const tbody = document.getElementById(`tbody-attributions-${enseignantId}`);
    if (!tbody) return;

    tbody.innerHTML = ""; // Vide le contenu existant du tableau d'attributions.
    const NOMBRE_COLONNES_CONTENU = 5; // Nombre de colonnes pour les données (Code, Cours choisi, Nb. grp., Pér., Pér. total)
    let totalPeriodesEnseignantCalcule = 0;

    /**
     * Traite et ajoute les attributions d'un certain type au tableau.
     * @param {Array} attributions Liste des attributions à traiter.
     * @param {boolean} estAutreTache Vrai si ce sont des "autres tâches", Faux pour l'enseignement.
     * @returns {boolean} Vrai si des attributions ont été ajoutées, Faux sinon.
     */
    const processAttributions = (attributions, estAutreTache) => {
        if (attributions.length === 0) return false;

        // Agréger les attributions par CodeCours pour gérer plusieurs groupes du même cours.
        const attributionsAgregees = attributions.reduce((acc, attr) => {
            // Créer une nouvelle entrée ou mettre à jour l'existante.
            if (!acc[attr.codecours]) {
                acc[attr.codecours] = { ...attr, nbgroupespris: 0, attributionIds: [] };
            }
            acc[attr.codecours].nbgroupespris += attr.nbgroupespris;
            // Stocker l'ID de la dernière attribution pour le bouton "Retirer" (permet de retirer un groupe à la fois).
            acc[attr.codecours].attributionIds.push(attr.attributionid);
            return acc;
        }, {});

        // Ajouter une ligne de titre pour séparer les sections "Périodes d'enseignement" et "Autres tâches".
        const titreRow = tbody.insertRow();
        titreRow.classList.add("sous-titre-attributions");
        const titreCell = titreRow.insertCell();
        titreCell.colSpan = NOMBRE_COLONNES_CONTENU;
        titreCell.textContent = estAutreTache ? "Autres tâches" : "Périodes d'enseignement";
        titreRow.insertCell().classList.add("no-print"); // Cellule vide pour le bouton d'action.

        // Ajouter chaque attribution agrégée au tableau.
        Object.values(attributionsAgregees).forEach((attr) => {
            const row = tbody.insertRow();
            const totalPeriodesAttr = attr.nbperiodes * attr.nbgroupespris;
            totalPeriodesEnseignantCalcule += totalPeriodesAttr;
            const lastAttributionId = attr.attributionIds[attr.attributionIds.length - 1]; // On retire le dernier groupe pris
            row.innerHTML = `
                <td>${attr.codecours}</td>
                <td>${attr.coursdescriptif}</td>
                <td>${attr.nbgroupespris}</td>
                <td>${formatPeriodes(attr.nbperiodes)}</td>
                <td>${formatPeriodes(totalPeriodesAttr)}</td>
                <td class="no-print"><button class="btn-retirer-cours" data-attribution-id="${lastAttributionId}">Retirer</button></td>
            `;
        });
        return true;
    };

    // Filtre et trie les attributions.
    const attributionsEnseignement = attributionsArray.filter((attr) => !attr.estcoursautre).sort((a, b) => a.coursdescriptif.localeCompare(b.coursdescriptif));
    const attributionsAutres = attributionsArray.filter((attr) => attr.estcoursautre).sort((a, b) => a.coursdescriptif.localeCompare(b.coursdescriptif));

    // Traite chaque catégorie d'attributions.
    const aEteAjouteEns = processAttributions(attributionsEnseignement, false);
    const aEteAjouteAutres = processAttributions(attributionsAutres, true);

    // Message si aucune période n'est choisie.
    if (!aEteAjouteEns && !aEteAjouteAutres) {
        const row = tbody.insertRow();
        const cellMessage = row.insertCell();
        cellMessage.colSpan = NOMBRE_COLONNES_CONTENU + 1;
        cellMessage.style.textAlign = "center";
        cellMessage.style.fontStyle = "italic";
        cellMessage.textContent = "Aucune période choisie pour le moment.";
    }

    // Ajoute la ligne du total des périodes.
    const totalRow = tbody.insertRow();
    totalRow.classList.add("total-attributions-row");
    const totalLabelCell = totalRow.insertCell();
    totalLabelCell.colSpan = NOMBRE_COLONNES_CONTENU - 1; // Ajuste le colspan
    totalLabelCell.textContent = "Total périodes choisies:";
    const totalValueCell = totalRow.insertCell();
    totalValueCell.textContent = formatPeriodes(totalPeriodesEnseignantCalcule);
    totalRow.insertCell().classList.add("no-print"); // Cellule vide pour le bouton d'action.
}

/**
 * Gestionnaire d'événements unique pour la section des enseignants.
 * Utilise la délégation d'événements pour gérer les clics sur plusieurs éléments
 * dynamiques à l'intérieur de la section.
 * @param {Event} event L'objet événement du clic.
 */
function gestionnaireClicsEnseignantsSection(event) {
    const target = event.target;
    // Gérer les clics sur l'en-tête de la carte pour déplier/replier.
    const entete = target.closest(".entete-enseignant");
    if (entete) {
        toggleEnseignantDetails(entete.closest(".enseignant-card"));
        return;
    }
    // Gérer les clics sur les boutons "Choisir" un cours.
    if (target.matches('.contenu-selection-cours .cours-selection button[data-enseignant-id][data-cours-code]')) {
        attribuerCours(target.dataset.enseignantId, target.dataset.coursCode, target);
    }
    // Gérer les clics sur les boutons "Retirer" un cours.
    else if (target.classList.contains("btn-retirer-cours")) {
        const card = target.closest(".enseignant-card");
        const estFictif = card?.classList.contains("enseignant-fictif");
        // Empêche le retrait si le champ est verrouillé et l'enseignant n'est pas fictif.
        if (G_CHAMP_EST_VERROUILLE && !estFictif) {
            alert("Les modifications sont désactivées car le champ est verrouillé. Seules les tâches restantes peuvent être modifiées.");
            return;
        }
        if (confirm("Êtes-vous sûr de vouloir retirer une attribution de ce cours ?")) {
            retirerCours(target.dataset.attributionId, target);
        }
    }
    // Gérer les clics sur les boutons "Supprimer tâche" (pour les enseignants fictifs).
    else if (target.classList.contains("btn-supprimer-enseignant")) {
        if (confirm("Êtes-vous sûr de vouloir supprimer cette tâche restante et tous ses cours attribués ?")) {
            supprimerEnseignantFictif(target.dataset.enseignantId, target);
        }
    }
}

/**
 * Appelle l'API pour attribuer un cours et met à jour l'interface en conséquence.
 * @param {string} enseignantId L'ID de l'enseignant.
 * @param {string} codeCours Le code du cours à attribuer.
 * @param {HTMLElement} boutonClique Le bouton "Choisir" qui a été cliqué.
 */
async function attribuerCours(enseignantId, codeCours, boutonClique) {
    const card = boutonClique.closest(".enseignant-card");
    const estFictif = card?.classList.contains("enseignant-fictif");
    // Empêche l'attribution si le champ est verrouillé et l'enseignant n'est pas fictif.
    if (G_CHAMP_EST_VERROUILLE && !estFictif) {
        alert("Les modifications sont désactivées car le champ est verrouillé. Seules les tâches restantes peuvent être modifiées.");
        return;
    }

    boutonClique.disabled = true;
    boutonClique.textContent = "...";

    try {
        const response = await fetch("/api/attributions/ajouter", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ enseignant_id: parseInt(enseignantId), code_cours: codeCours }),
        });
        const data = await response.json();

        if (!response.ok || !data.success) {
            throw new Error(data.message || "Erreur attribution cours.");
        }

        // Met à jour les éléments de l'interface utilisateur.
        mettreAJourLigneSommaire(enseignantId, data.periodes_enseignant);
        recalculerEtAfficherMoyenneChamp();
        regenererTableauAttributionsEnseignant(enseignantId, data.attributions_enseignant || []);
        if (card) appliquerStatutVerrouillagePourCarte(card); // Réapplique le verrouillage sur la carte au cas où.
        mettreAJourDonneesGlobalesCours(codeCours, data.groupes_restants_cours); // Met à jour les données globales pour ce cours.
        regenererTableauCoursRestants(); // Rafraîchit le tableau des cours restants (colonne de droite).
        regenererToutesLesListesDeCoursAChoisirGlobale(); // IMPORTANT: Rafraîchit toutes les listes de choix de cours.

    } catch (error) {
        console.error("Erreur attribuerCours:", error);
        alert(error.message);
    } finally {
        // Réactive le bouton s'il existe toujours dans le DOM.
        if (document.body.contains(boutonClique)) {
            boutonClique.disabled = false;
            boutonClique.textContent = "Choisir";
        }
    }
}

/**
 * Appelle l'API pour retirer une attribution de cours et met à jour l'interface.
 * @param {string} attributionId L'ID de l'attribution à supprimer.
 * @param {HTMLElement} _boutonClique Le bouton "Retirer" qui a été cliqué (non utilisé dans cette fonction, d'où le préfixe `_`).
 */
async function retirerCours(attributionId, _boutonClique) {
    // Le bouton n'est pas désactivé ici car la confirmation est faite avant,
    // et il pourrait être supprimé du DOM immédiatement.
    try {
        const response = await fetch("/api/attributions/supprimer", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ attribution_id: parseInt(attributionId) }),
        });
        const data = await response.json();

        if (!response.ok || !data.success) {
            throw new Error(data.message || "Erreur retrait cours.");
        }

        // Met à jour les éléments de l'interface utilisateur.
        const card = document.getElementById(`enseignant-card-${data.enseignant_id}`);
        mettreAJourLigneSommaire(data.enseignant_id, data.periodes_enseignant);
        recalculerEtAfficherMoyenneChamp();
        regenererTableauAttributionsEnseignant(data.enseignant_id, data.attributions_enseignant || []);
        if (card) appliquerStatutVerrouillagePourCarte(card); // Réapplique le verrouillage sur la carte au cas où.
        mettreAJourDonneesGlobalesCours(data.code_cours, data.groupes_restants_cours); // Met à jour les données globales pour ce cours.
        regenererTableauCoursRestants(); // Rafraîchit le tableau des cours restants (colonne de droite).
        regenererToutesLesListesDeCoursAChoisirGlobale(); // IMPORTANT: Rafraîchit toutes les listes de choix de cours.

    } catch (error) {
        console.error("Erreur retirerCours:", error);
        alert(error.message);
    }
}

/**
 * Appelle l'API pour créer une tâche restante (enseignant fictif) dans le champ actuel.
 * @param {HTMLElement} boutonClique Le bouton "Créer une tâche restante" qui a été cliqué.
 */
async function creerTacheRestante(boutonClique) {
    boutonClique.disabled = true;
    boutonClique.textContent = "Création...";

    try {
        const response = await fetch(`/api/champs/${G_CHAMP_NO_ACTUEL}/taches_restantes/creer`, { method: "POST", headers: { "Content-Type": "application/json" } });
        const data = await response.json();

        if (!response.ok || !data.success || !data.enseignant) {
            throw new Error(data.message || "Erreur création tâche restante.");
        }

        // Ajoute le nouvel enseignant fictif aux données globales et à l'interface.
        G_ENSEIGNANTS_INITIAL_DATA.push(data.enseignant);
        ajouterEnseignantDynamiquement(data.enseignant);
        const periodesInitiales = data.periodes_actuelles || { periodes_cours: 0, periodes_autres: 0, total_periodes: 0 };
        ajouterAuTableauSommaire(data.enseignant, periodesInitiales);
        recalculerEtAfficherMoyenneChamp(); // Recalcule la moyenne du champ suite à l'ajout.

    } catch (error) {
        console.error("Erreur creerTacheRestante:", error);
        alert(error.message);
    } finally {
        boutonClique.disabled = false;
        boutonClique.textContent = "Créer une tâche restante";
    }
}

/**
 * Appelle l'API pour supprimer un enseignant fictif (tâche restante).
 * @param {string} enseignantId L'ID de l'enseignant fictif à supprimer.
 * @param {HTMLElement} boutonClique Le bouton "Supprimer tâche" qui a été cliqué.
 */
async function supprimerEnseignantFictif(enseignantId, boutonClique) {
    boutonClique.disabled = true;
    boutonClique.textContent = "Suppression...";

    try {
        const response = await fetch(`/api/enseignants/${enseignantId}/supprimer`, { method: "POST", headers: { "Content-Type": "application/json" } });
        const data = await response.json();

        if (!response.ok || !data.success) {
            throw new Error(data.message || "Erreur suppression tâche.");
        }

        // Supprime la carte de l'enseignant et sa ligne du sommaire.
        document.getElementById(`enseignant-card-${enseignantId}`)?.remove();
        document.querySelector(`.sommaire-champ-section tbody tr[data-enseignant-id="${enseignantId}"]`)?.remove();

        // Met à jour la variable globale G_ENSEIGNANTS_INITIAL_DATA.
        const index = G_ENSEIGNANTS_INITIAL_DATA.findIndex((e) => e.enseignantid === parseInt(enseignantId));
        if (index > -1) G_ENSEIGNANTS_INITIAL_DATA.splice(index, 1);

        // Si des cours ont été libérés, met à jour leurs groupes restants.
        if (data.cours_liberes_details?.length > 0) {
            data.cours_liberes_details.forEach((cours_maj) => {
                mettreAJourDonneesGlobalesCours(cours_maj.code_cours, cours_maj.nouveaux_groupes_restants);
            });
        }

        regenererTableauCoursRestants(); // Rafraîchit le tableau des cours restants.
        regenererToutesLesListesDeCoursAChoisirGlobale(); // IMPORTANT: Rafraîchit toutes les listes de choix de cours.
        recalculerEtAfficherMoyenneChamp(); // Recalcule la moyenne du champ.

    } catch (error) {
        console.error("Erreur supprimerEnseignantFictif:", error);
        alert(error.message);
        // Réactive le bouton en cas d'erreur si l'élément existe toujours.
        if (boutonClique && document.body.contains(boutonClique)) {
            boutonClique.disabled = false;
            boutonClique.textContent = "Supprimer tâche";
        }
    }
}

/**
 * Met à jour les données globales d'un cours (nombre de groupes restants).
 * Ces données sont utilisées pour générer les listes de cours disponibles et le tableau des cours restants.
 * @param {string} codeCours Le code du cours à mettre à jour.
 * @param {number} nouveauxGrpRestants Le nouveau nombre de groupes restants.
 */
function mettreAJourDonneesGlobalesCours(codeCours, nouveauxGrpRestants) {
    // Recherche le cours dans la liste des cours d'enseignement et met à jour.
    const coursTrouveE = G_COURS_ENSEIGNEMENT_CHAMP.find((c) => c.codecours === codeCours);
    if (coursTrouveE) coursTrouveE.grprestant = nouveauxGrpRestants;
    // Recherche le cours dans la liste des autres tâches et met à jour.
    const coursTrouveA = G_COURS_AUTRES_TACHES_CHAMP.find((c) => c.codecours === codeCours);
    if (coursTrouveA) coursTrouveA.grprestant = nouveauxGrpRestants;
}

/**
 * Régénère entièrement le contenu du tableau des cours restants sur la droite de la page.
 */
function regenererTableauCoursRestants() {
    const tbody = document.querySelector("#tableau-cours-restants tbody");
    if (!tbody) return;
    tbody.innerHTML = ""; // Vide le contenu existant.
    const contenuHtml = genererHtmlLignesCoursRestants(); // Génère les nouvelles lignes.
    tbody.innerHTML = contenuHtml;
}

/**
 * Génère le code HTML pour les lignes (tr) du tableau des cours restants,
 * en filtrant les cours dont les groupes restants sont à zéro pour ne pas les afficher ici.
 * @returns {string} Le code HTML des lignes du tableau.
 */
function genererHtmlLignesCoursRestants() {
    let html = "";
    // Filtre pour n'afficher que les cours avec des groupes restants.
    const coursEnseignementRestants = G_COURS_ENSEIGNEMENT_CHAMP.filter((c) => c.grprestant > 0);
    const coursAutresRestants = G_COURS_AUTRES_TACHES_CHAMP.filter((c) => c.grprestant > 0);

    // Section Périodes d'enseignement
    html += `<tr><td colspan="5" class="sous-titre-cours-restants">Périodes d'enseignement</td></tr>`;
    if (coursEnseignementRestants.length > 0) {
        coursEnseignementRestants.forEach((cours) => {
            const periodesRestantes = cours.nbperiodes * cours.grprestant;
            html += `<tr><td>${cours.codecours}</td><td>${cours.coursdescriptif}</td><td id="grp-restant-${cours.codecours}">${cours.grprestant}</td><td>${formatPeriodes(cours.nbperiodes)}</td><td>${formatPeriodes(periodesRestantes)}</td></tr>`;
        });
    } else {
        html += `<tr><td colspan="5" style="text-align:center; font-style:italic;">Toutes les périodes d'enseignement ont été choisies.</td></tr>`;
    }

    // Section Autres Tâches
    html += `<tr><td colspan="5" class="sous-titre-cours-restants">Périodes autres</td></tr>`;
    if (coursAutresRestants.length > 0) {
        coursAutresRestants.forEach((cours) => {
            const periodesRestantes = cours.nbperiodes * cours.grprestant;
            html += `<tr><td>${cours.codecours}</td><td>${cours.coursdescriptif}</td><td id="grp-restant-${cours.codecours}">${cours.grprestant}</td><td>${formatPeriodes(cours.nbperiodes)}</td><td>${formatPeriodes(periodesRestantes)}</td></tr>`;
        });
    } else {
        html += `<tr><td colspan="5" style="text-align:center; font-style:italic;">Toutes les autres tâches ont été choisies.</td></tr>`;
    }

    // Message général si aucun cours de n'importe quel type n'est disponible.
    if (coursEnseignementRestants.length === 0 && coursAutresRestants.length === 0) {
        return '<tr><td colspan="5" style="text-align:center;">Toutes les périodes et tâches de ce champ ont été choisies.</td></tr>';
    }
    return html;
}

/**
 * Met à jour les listes de cours à choisir pour toutes les cartes d'enseignants actuellement dépliées.
 * C'est la clé de la correction : s'assurer que même les cartes déjà ouvertes voient les changements
 * des groupes disponibles sans avoir à être refermées et rouvertes.
 */
function regenererToutesLesListesDeCoursAChoisirGlobale() {
    // Sélectionne toutes les cartes d'enseignants qui sont actuellement en mode "détail-visible".
    document.querySelectorAll(".enseignant-card.detail-visible").forEach((card) => {
        const enseignantId = card.id.split("-").pop(); // Extrait l'ID de l'enseignant de l'ID de la carte.

        // Met à jour la liste des cours d'enseignement disponibles.
        const ulEnseignement = card.querySelector('ul.liste-cours-a-choisir[data-type-cours="enseignement"]');
        if (ulEnseignement) {
            ulEnseignement.innerHTML = genererListeHTMLCoursDispo(G_COURS_ENSEIGNEMENT_CHAMP, enseignantId, "enseignement");
        }

        // Met à jour la liste des autres tâches disponibles.
        const ulAutres = card.querySelector('ul.liste-cours-a-choisir[data-type-cours="autre"]');
        if (ulAutres) {
            ulAutres.innerHTML = genererListeHTMLCoursDispo(G_COURS_AUTRES_TACHES_CHAMP, enseignantId, "autre");
        }

        // Réapplique le statut de verrouillage, car les boutons pourraient avoir été régénérés.
        appliquerStatutVerrouillagePourCarte(card);
    });
}

/**
 * Génère le code HTML pour une liste de cours disponibles à l'attribution pour un enseignant.
 * @param {Array} listeCoursGlobale - La liste globale des cours (enseignements ou autres).
 * @param {string} enseignantId - L'ID de l'enseignant.
 * @param {string} typeCours - Le type de cours ('enseignement' ou 'autre') pour la donnée `data-type`.
 * @returns {string} Le code HTML de la liste des cours disponibles avec des boutons "Choisir".
 */
function genererListeHTMLCoursDispo(listeCoursGlobale, enseignantId, typeCours) {
    let html = "";
    // Filtre les cours qui ont encore des groupes restants.
    const coursAffichables = listeCoursGlobale.filter((cours) => cours.grprestant > 0);

    if (coursAffichables.length > 0) {
        coursAffichables.forEach((cours) => {
            html += `<li>
                        ${cours.codecours} - ${cours.coursdescriptif} (${formatPeriodes(cours.nbperiodes)} pér. - ${cours.grprestant} grp. rest.)
                        <button data-enseignant-id="${enseignantId}" data-cours-code="${cours.codecours}" data-type="${typeCours}" data-nb-periodes="${cours.nbperiodes}">Choisir</button>
                     </li>`;
        });
    } else {
        html = `<li>Aucun cours de ce type disponible pour le moment.</li>`;
    }
    return html;
}

/**
 * Met à jour une ligne spécifique dans le tableau de sommaire du champ.
 * Met également à jour la variable globale pour garantir que l'impression a les données à jour.
 * @param {string|number} enseignantId - L'ID de l'enseignant.
 * @param {object} periodes - L'objet contenant les périodes (periodes_cours, periodes_autres, total_periodes).
 */
function mettreAJourLigneSommaire(enseignantId, periodes) {
    // 1. Mettre à jour le DOM pour l'affichage en direct
    const ligne = document.querySelector(`.sommaire-champ-section tbody tr[data-enseignant-id="${enseignantId}"]`);
    if (ligne) {
        ligne.querySelector(".sum-cours-val").textContent = formatPeriodes(periodes.periodes_cours);
        ligne.querySelector(".sum-autres-val").textContent = formatPeriodes(periodes.periodes_autres);
        ligne.querySelector(".sum-total-val").textContent = formatPeriodes(periodes.total_periodes);
    }

    // 2. Mettre à jour la variable de données globale G_ENSEIGNANTS_INITIAL_DATA.
    // C'est crucial pour que la fonction d'impression et les recalculs de moyenne aient les données les plus récentes.
    const enseignantData = G_ENSEIGNANTS_INITIAL_DATA.find((e) => e.enseignantid === parseInt(enseignantId));
    if (enseignantData) {
        enseignantData.periodes_actuelles = periodes;
    }
}

/**
 * Ajoute une carte d'enseignant à l'interface en utilisant le template HTML.
 * Principalement utilisée pour les tâches restantes (enseignants fictifs) créées dynamiquement.
 * @param {object} enseignant - L'objet enseignant contenant toutes ses données (y compris nom, prenom, nomcomplet).
 */
function ajouterEnseignantDynamiquement(enseignant) {
    const container = document.querySelector(".enseignants-section");
    const btnCreerTache = document.getElementById("btn-creer-tache-restante");
    const template = document.getElementById("enseignant-card-template");
    if (!container || !btnCreerTache || !template) return;

    // Clone le contenu du template.
    const clone = template.content.cloneNode(true);
    const newCard = clone.querySelector(".enseignant-card");
    if (!newCard) return;

    newCard.id = `enseignant-card-${enseignant.enseignantid}`;

    // Met à jour le nom de l'enseignant dans l'en-tête de la carte.
    const nomElement = newCard.querySelector('[data-template-nom="nom-enseignant"]');
    if (nomElement) {
        // Pour les tâches fictives, enseignant.nom et enseignant.prenom seront null.
        // enseignant.nomcomplet contiendra le nom généré (ex: "01-Tâche restante-1").
        const nomAAfficher = (enseignant.nom && enseignant.prenom)
            ? `${enseignant.nom}, ${enseignant.prenom}`
            : enseignant.nomcomplet;
        const nomTextNode = document.createTextNode(nomAAfficher);
        // Remplace le contenu du placeholder par le texte réel.
        while (nomElement.firstChild) {
            nomElement.removeChild(nomElement.firstChild);
        }
        nomElement.appendChild(nomTextNode);
    }

    // Met à jour la ligne de signature pour l'impression.
    const signatureLineElement = newCard.querySelector(".signature-line");
    if (signatureLineElement && signatureLineElement.textContent.includes("NOM_COMPLET_PLACEHOLDER_PRINT")) {
        const nomPourSignature = (enseignant.nom && enseignant.prenom)
            ? `${enseignant.nom}, ${enseignant.prenom}`
            : enseignant.nomcomplet;
        signatureLineElement.textContent = signatureLineElement.textContent.replace("NOM_COMPLET_PLACEHOLDER_PRINT", nomPourSignature);
    }

    // Met à jour les data-attributs et IDs pour les boutons et tableaux.
    const btnSupprimer = newCard.querySelector('[data-template-id-btn]');
    if (btnSupprimer) btnSupprimer.dataset.enseignantId = enseignant.enseignantid;

    const tableElement = newCard.querySelector('[data-template-id-table]');
    if (tableElement) tableElement.id = `table-attributions-${enseignant.enseignantid}`;

    const tbodyElement = newCard.querySelector('[data-template-id-tbody]');
    if (tbodyElement) tbodyElement.id = `tbody-attributions-${enseignant.enseignantid}`;

    // Insère la nouvelle carte avant le bouton "Créer une tâche restante".
    container.insertBefore(newCard, btnCreerTache);

    // Initialise le tableau d'attributions et applique les règles de verrouillage pour la nouvelle carte.
    regenererTableauAttributionsEnseignant(enseignant.enseignantid, enseignant.attributions || []);
    appliquerStatutVerrouillagePourCarte(newCard);
}

/**
 * Ajoute une ligne au tableau de sommaire pour un nouvel enseignant créé dynamiquement.
 * @param {object} enseignant - L'objet enseignant.
 * @param {object} periodes - L'objet des périodes (periodes_cours, periodes_autres, total_periodes).
 */
function ajouterAuTableauSommaire(enseignant, periodes) {
    const tbody = document.querySelector("#tableau-sommaire-champ tbody");
    if (!tbody) return;

    const row = tbody.insertRow();
    row.dataset.enseignantId = enseignant.enseignantid;

    let classeCssSommaire = "enseignant-temps-plein-sommaire";
    let statutTexte = "Temps Plein";
    if (enseignant.estfictif) {
        classeCssSommaire = "enseignant-fictif-sommaire";
        statutTexte = "Tâche Restante";
    } else if (!enseignant.esttempsplein) {
        classeCssSommaire = "enseignant-temps-partiel-sommaire";
        statutTexte = "Temps Partiel";
    }
    row.classList.add(classeCssSommaire);

    const nomPourSommaire = (enseignant.nom && enseignant.prenom)
        ? `${enseignant.nom}, ${enseignant.prenom}`
        : enseignant.nomcomplet;

    row.innerHTML = `
        <td>${nomPourSommaire}</td>
        <td class="sum-cours-val">${formatPeriodes(periodes.periodes_cours)}</td>
        <td class="sum-autres-val">${formatPeriodes(periodes.periodes_autres)}</td>
        <td class="sum-total-val">${formatPeriodes(periodes.total_periodes)}</td>
        <td>${statutTexte}</td>`;
}

/**
 * Recalcule la moyenne des périodes pour le champ actuel
 * et met à jour son affichage dans le tableau sommaire.
 */
function recalculerEtAfficherMoyenneChamp() {
    let totalPeriodes = 0;
    let countTempsPleinNonFictif = 0;

    // Itère sur la source de données globale G_ENSEIGNANTS_INITIAL_DATA pour un calcul précis.
    G_ENSEIGNANTS_INITIAL_DATA.forEach((enseignant) => {
        // Vérifie si l'enseignant est temps plein et non fictif (compte pour la moyenne).
        if (enseignant.esttempsplein && !enseignant.estfictif) {
            // Accède aux périodes actuelles depuis la structure de données globale.
            if (enseignant.periodes_actuelles && enseignant.periodes_actuelles.total_periodes !== undefined) {
                totalPeriodes += enseignant.periodes_actuelles.total_periodes;
                countTempsPleinNonFictif++;
            }
        }
    });

    const moyenne = countTempsPleinNonFictif > 0 ? totalPeriodes / countTempsPleinNonFictif : 0;
    const moyenneCell = document.getElementById("moyenne-champ-val");
    if (moyenneCell) {
        moyenneCell.textContent = formatPeriodes(moyenne); // Utilise la fonction de formatage ici
    }
}


/**
 * Génère le HTML complet du tableau des cours restants pour l'impression.
 * Réutilise `genererHtmlLignesCoursRestants` qui se base sur les données globales `G_COURS_...`.
 * @returns {string} Le code HTML du tableau des cours restants formaté pour l'impression.
 */
function genererHtmlTableauCoursRestants() {
    const lignesHtml = genererHtmlLignesCoursRestants();
    return `<h2 class="section-title">Périodes restantes dans ce champ</h2>
            <table id="tableau-cours-restants-print">
                <thead>
                    <tr><th>Code</th><th>Cours disponibles</th><th>Grp. rest.</th><th>Pér.</th><th>Pér. restantes</th></tr>
                </thead>
                <tbody>${lignesHtml}</tbody>
            </table>`;
}

/**
 * Génère le HTML complet du tableau sommaire du champ pour l'impression.
 * Il est construit à partir des données globales `G_ENSEIGNANTS_INITIAL_DATA`,
 * qui sont la source de vérité mise à jour dynamiquement.
 * @returns {string} Le code HTML du tableau sommaire formaté pour l'impression.
 */
function genererHtmlTableauSommaireChamp() {
    let tbodyHtml = "";
    // Copie et trie la variable globale G_ENSEIGNANTS_INITIAL_DATA.
    // Le tri est fait pour s'assurer que les enseignants sont affichés dans un ordre cohérent
    // (fictifs à la fin, puis par nom et prénom).
    const enseignantsTries = [...G_ENSEIGNANTS_INITIAL_DATA].sort((a, b) => {
        // Trie d'abord par statut fictif (faux avant vrai).
        if (a.estfictif !== b.estfictif) {
            return a.estfictif ? 1 : -1; // Fictifs à la fin pour le tri visuel.
        }
        // Pour les non-fictifs, trie par nom puis prénom.
        const nomA = a.nom || "";
        const nomB = b.nom || "";
        const prenomA = a.prenom || "";
        const prenomB = b.prenom || "";

        if (nomA.localeCompare(nomB) !== 0) {
            return nomA.localeCompare(nomB);
        }
        return prenomA.localeCompare(prenomB);
    });


    enseignantsTries.forEach((enseignant) => {
        // Récupère les périodes actuelles de l'enseignant.
        const periodes = enseignant.periodes_actuelles || { periodes_cours: 0, periodes_autres: 0, total_periodes: 0 };
        let statutClass = "enseignant-temps-plein-sommaire";
        let statutText = "Temps Plein";
        if (enseignant.estfictif) {
            statutClass = "enseignant-fictif-sommaire";
            statutText = "Tâche Restante";
        } else if (!enseignant.esttempsplein) {
            statutClass = "enseignant-temps-partiel-sommaire";
            statutText = "Temps Partiel";
        }

        // Détermine le nom à afficher (Nom, Prénom ou NomComplet pour les fictifs).
        const nomPourAffichage = (enseignant.nom && enseignant.prenom)
            ? `${enseignant.nom}, ${enseignant.prenom}`
            : enseignant.nomcomplet;

        tbodyHtml += `
            <tr class="${statutClass}" data-enseignant-id="${enseignant.enseignantid}">
                <td>${nomPourAffichage}</td>
                <td class="sum-cours-val">${formatPeriodes(periodes.periodes_cours)}</td>
                <td class="sum-autres-val">${formatPeriodes(periodes.periodes_autres)}</td>
                <td class="sum-total-val">${formatPeriodes(periodes.total_periodes)}</td>
                <td>${statutText}</td>
            </tr>`;
    });

    // Récupère la moyenne du champ affichée (qui est déjà mise à jour).
    const moyenneChamp = document.getElementById("moyenne-champ-val")?.textContent || "0.00";
    let tfootHtml = `<tfoot><tr><td colspan="3" style="text-align:right;"><strong>Moyenne champ (temps plein):</strong></td><td>${moyenneChamp}</td><td></td></tr></tfoot>`;

    return `<h2 class="section-title">Tâches du champ : ${G_CHAMP_NO_ACTUEL}</h2>
            <table id="tableau-sommaire-champ-print">
                <thead><tr><th>Nom</th><th>Cours</th><th>Autres</th><th>Total</th><th>Statut</th></tr></thead>
                <tbody>${tbodyHtml}</tbody>
                ${tfootHtml}
            </table>`;
}

/**
 * Génère le rapport sommaire pour l'impression en reconstruisant le HTML
 * à partir des données actuelles et dans l'ordre demandé (Sommaire d'abord, puis Restants).
 */
function genererRapportSommairePourImpression() {
    const container = document.getElementById("print-summary-page");
    if (!container) return;

    // Génère le HTML des deux tableaux.
    const htmlSommaireChamp = genererHtmlTableauSommaireChamp();
    const htmlCoursRestants = genererHtmlTableauCoursRestants();

    // Inversion de l'ordre pour l'impression si nécessaire, ou ordre spécifique
    container.innerHTML = htmlSommaireChamp + htmlCoursRestants;
}