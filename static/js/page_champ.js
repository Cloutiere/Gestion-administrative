// static/js/page_champ.js
// Ce script contient toute la logique d'interaction pour la page de gestion d'un champ.
// Il dépend des variables globales suivantes, qui doivent être initialisées dans le fichier HTML
// avant le chargement de ce script :
// - G_COURS_ENSEIGNEMENT_CHAMP
// - G_COURS_AUTRES_TACHES_CHAMP
// - G_ENSEIGNANTS_INITIAL_DATA
// - G_CHAMP_NO_ACTUEL
// - G_CHAMP_EST_VERROUILLE

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
 * @param {HTMLElement} card La carte d'enseignant à traiter.
 */
function appliquerStatutVerrouillagePourCarte(card) {
    if (!G_CHAMP_EST_VERROUILLE) return;
    // On ne verrouille que les enseignants réels, pas les tâches restantes (fictifs)
    if (!card.classList.contains("enseignant-fictif")) {
        card.querySelectorAll(".btn-retirer-cours, .cours-selection button").forEach((button) => {
            button.disabled = true;
            button.title = "Les modifications sont désactivées car le champ est verrouillé.";
        });
    }
}

/**
 * Applique l'état de verrouillage à toutes les cartes d'enseignants sur la page.
 */
function appliquerStatutVerrouillageUI() {
    document.querySelectorAll(".enseignant-card").forEach(appliquerStatutVerrouillagePourCarte);
}

/**
 * Gère le basculement de l'affichage des détails d'une carte enseignant.
 * @param {HTMLElement} enseignantCard La carte d'enseignant concernée.
 */
function toggleEnseignantDetails(enseignantCard) {
    if (!enseignantCard) return;
    const etaitVisible = enseignantCard.classList.contains("detail-visible");
    document.querySelectorAll(".enseignant-card.detail-visible").forEach((card) => {
        if (card !== enseignantCard) card.classList.remove("detail-visible");
    });
    if (!etaitVisible) {
        enseignantCard.classList.add("detail-visible");
        const ulEnseignement = enseignantCard.querySelector('ul.liste-cours-a-choisir[data-type-cours="enseignement"]');
        if (ulEnseignement && ulEnseignement.innerHTML.trim() === "") {
            const enseignantId = enseignantCard.id.split("-").pop();
            ulEnseignement.innerHTML = genererListeHTMLCoursDispo(G_COURS_ENSEIGNEMENT_CHAMP, enseignantId, "enseignement");
            const ulAutres = enseignantCard.querySelector('ul.liste-cours-a-choisir[data-type-cours="autre"]');
            if (ulAutres) {
                ulAutres.innerHTML = genererListeHTMLCoursDispo(G_COURS_AUTRES_TACHES_CHAMP, enseignantId, "autre");
            }
            appliquerStatutVerrouillagePourCarte(enseignantCard);
        }
    } else {
        enseignantCard.classList.remove("detail-visible");
    }
}

/**
 * Régénère le contenu du tableau des attributions pour un enseignant donné.
 * @param {number} enseignantId L'ID de l'enseignant.
 * @param {Array} attributionsArray La liste de ses attributions brutes.
 */
function regenererTableauAttributionsEnseignant(enseignantId, attributionsArray) {
    const tbody = document.getElementById(`tbody-attributions-${enseignantId}`);
    if (!tbody) return;
    tbody.innerHTML = "";
    const NOMBRE_COLONNES_CONTENU = 5;
    let totalPeriodesEnseignantCalcule = 0;
    const processAttributions = (attributions, estAutreTache) => {
        if (attributions.length === 0) return false;
        const attributionsAgregees = attributions.reduce((acc, attr) => {
            if (!acc[attr.codecours]) {
                acc[attr.codecours] = { ...attr, nbgroupespris: 0, attributionIds: [] };
            }
            acc[attr.codecours].nbgroupespris += attr.nbgroupespris;
            acc[attr.codecours].attributionIds.push(attr.attributionid);
            return acc;
        }, {});
        const titreRow = tbody.insertRow();
        titreRow.classList.add("sous-titre-attributions");
        const titreCell = titreRow.insertCell();
        titreCell.colSpan = NOMBRE_COLONNES_CONTENU;
        titreCell.textContent = estAutreTache ? "Autres tâches" : "Périodes d'enseignement";
        titreRow.insertCell().classList.add("no-print");
        Object.values(attributionsAgregees).forEach((attr) => {
            const row = tbody.insertRow();
            const totalPeriodesAttr = attr.nbperiodes * attr.nbgroupespris;
            totalPeriodesEnseignantCalcule += totalPeriodesAttr;
            const lastAttributionId = attr.attributionIds[attr.attributionIds.length - 1];
            row.innerHTML = `
                <td>${attr.codecours}</td>
                <td>${attr.coursdescriptif}</td>
                <td>${attr.nbgroupespris}</td>
                <td>${attr.nbperiodes}</td>
                <td>${totalPeriodesAttr}</td>
                <td class="no-print"><button class="btn-retirer-cours" data-attribution-id="${lastAttributionId}">Retirer</button></td>
            `;
        });
        return true;
    };
    const attributionsEnseignement = attributionsArray.filter((attr) => !attr.estcoursautre).sort((a, b) => a.coursdescriptif.localeCompare(b.coursdescriptif));
    const attributionsAutres = attributionsArray.filter((attr) => attr.estcoursautre).sort((a, b) => a.coursdescriptif.localeCompare(b.coursdescriptif));
    const aEteAjouteEns = processAttributions(attributionsEnseignement, false);
    const aEteAjouteAutres = processAttributions(attributionsAutres, true);
    if (!aEteAjouteEns && !aEteAjouteAutres) {
        const row = tbody.insertRow();
        const cellMessage = row.insertCell();
        cellMessage.colSpan = NOMBRE_COLONNES_CONTENU + 1;
        cellMessage.style.textAlign = "center";
        cellMessage.style.fontStyle = "italic";
        cellMessage.textContent = "Aucune période choisie pour le moment.";
    }
    const totalRow = tbody.insertRow();
    totalRow.classList.add("total-attributions-row");
    const totalLabelCell = totalRow.insertCell();
    totalLabelCell.colSpan = NOMBRE_COLONNES_CONTENU - 1;
    totalLabelCell.textContent = "Total périodes choisies:";
    const totalValueCell = totalRow.insertCell();
    totalValueCell.textContent = totalPeriodesEnseignantCalcule;
    totalRow.insertCell().classList.add("no-print");
}

/**
 * Gestionnaire d'événements unique pour la section des enseignants.
 * @param {Event} event L'objet événement du clic.
 */
function gestionnaireClicsEnseignantsSection(event) {
    const target = event.target;
    const entete = target.closest(".entete-enseignant");
    if (entete) {
        toggleEnseignantDetails(entete.closest(".enseignant-card"));
        return;
    }
    if (target.matches('.contenu-selection-cours .cours-selection button[data-enseignant-id][data-cours-code]')) {
        attribuerCours(target.dataset.enseignantId, target.dataset.coursCode, target);
    } else if (target.classList.contains("btn-retirer-cours")) {
        const card = target.closest(".enseignant-card");
        const estFictif = card?.classList.contains("enseignant-fictif");
        if (G_CHAMP_EST_VERROUILLE && !estFictif) {
            alert("Les modifications sont désactivées car le champ est verrouillé.");
            return;
        }
        if (confirm("Êtes-vous sûr de vouloir retirer une attribution de ce cours ?")) {
            retirerCours(target.dataset.attributionId, target);
        }
    } else if (target.classList.contains("btn-supprimer-enseignant")) {
        if (confirm("Êtes-vous sûr de vouloir supprimer cette tâche restante et tous ses cours attribués ?")) {
            supprimerEnseignantFictif(target.dataset.enseignantId, target);
        }
    }
}

/**
 * Appelle l'API pour attribuer un cours et met à jour l'interface.
 */
async function attribuerCours(enseignantId, codeCours, boutonClique) {
    const card = boutonClique.closest(".enseignant-card");
    const estFictif = card?.classList.contains("enseignant-fictif");
    if (G_CHAMP_EST_VERROUILLE && !estFictif) {
        alert("Les modifications sont désactivées car le champ est verrouillé.");
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
        mettreAJourLigneSommaire(enseignantId, data.periodes_enseignant);
        recalculerEtAfficherMoyenneChamp();
        regenererTableauAttributionsEnseignant(enseignantId, data.attributions_enseignant || []);
        if (card) appliquerStatutVerrouillagePourCarte(card);
        mettreAJourDonneesGlobalesCours(codeCours, data.groupes_restants_cours);
        regenererTableauCoursRestants();
        regenererToutesLesListesDeCoursAChoisirGlobale();
    } catch (error) {
        console.error("Erreur attribuerCours:", error);
        alert(error.message);
    } finally {
        if (document.body.contains(boutonClique)) {
            boutonClique.disabled = false;
            boutonClique.textContent = "Choisir";
        }
    }
}

/**
 * Appelle l'API pour retirer un cours et met à jour l'interface.
 */
async function retirerCours(attributionId, _boutonClique) {
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
        const card = document.getElementById(`enseignant-card-${data.enseignant_id}`);
        mettreAJourLigneSommaire(data.enseignant_id, data.periodes_enseignant);
        recalculerEtAfficherMoyenneChamp();
        regenererTableauAttributionsEnseignant(data.enseignant_id, data.attributions_enseignant || []);
        if (card) appliquerStatutVerrouillagePourCarte(card);
        mettreAJourDonneesGlobalesCours(data.code_cours, data.groupes_restants_cours);
        regenererTableauCoursRestants();
        regenererToutesLesListesDeCoursAChoisirGlobale();
    } catch (error) {
        console.error("Erreur retirerCours:", error);
        alert(error.message);
    }
}

/**
 * Appelle l'API pour créer une tâche restante.
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
        G_ENSEIGNANTS_INITIAL_DATA.push(data.enseignant);
        ajouterEnseignantDynamiquement(data.enseignant);
        const periodesInitiales = data.periodes_actuelles || { periodes_cours: 0, periodes_autres: 0, total_periodes: 0 };
        ajouterAuTableauSommaire(data.enseignant, periodesInitiales);
        recalculerEtAfficherMoyenneChamp();
    } catch (error) {
        console.error("Erreur creerTacheRestante:", error);
        alert(error.message);
    } finally {
        boutonClique.disabled = false;
        boutonClique.textContent = "Créer une tâche restante";
    }
}

/**
 * Appelle l'API pour supprimer un enseignant fictif.
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
        document.getElementById(`enseignant-card-${enseignantId}`)?.remove();
        document.querySelector(`.sommaire-champ-section tbody tr[data-enseignant-id="${enseignantId}"]`)?.remove();
        const index = G_ENSEIGNANTS_INITIAL_DATA.findIndex((e) => e.enseignantid === parseInt(enseignantId));
        if (index > -1) G_ENSEIGNANTS_INITIAL_DATA.splice(index, 1);
        if (data.cours_liberes_details?.length > 0) {
            data.cours_liberes_details.forEach((cours_maj) => {
                mettreAJourDonneesGlobalesCours(cours_maj.code_cours, cours_maj.nouveaux_groupes_restants);
            });
        }
        regenererTableauCoursRestants();
        regenererToutesLesListesDeCoursAChoisirGlobale();
        recalculerEtAfficherMoyenneChamp();
    } catch (error) {
        console.error("Erreur supprimerEnseignantFictif:", error);
        alert(error.message);
        if (boutonClique && document.body.contains(boutonClique)) {
            boutonClique.disabled = false;
            boutonClique.textContent = "Supprimer tâche";
        }
    }
}

/**
 * Met à jour les données globales d'un cours (groupes restants).
 */
function mettreAJourDonneesGlobalesCours(codeCours, nouveauxGrpRestants) {
    const coursTrouveE = G_COURS_ENSEIGNEMENT_CHAMP.find((c) => c.codecours === codeCours);
    if (coursTrouveE) coursTrouveE.grprestant = nouveauxGrpRestants;
    const coursTrouveA = G_COURS_AUTRES_TACHES_CHAMP.find((c) => c.codecours === codeCours);
    if (coursTrouveA) coursTrouveA.grprestant = nouveauxGrpRestants;
}

/**
 * Régénère entièrement le tableau des cours restants pour l'affichage à l'écran.
 */
function regenererTableauCoursRestants() {
    const tbody = document.querySelector("#tableau-cours-restants tbody");
    if (!tbody) return;
    tbody.innerHTML = ""; // Vide le contenu existant
    const contenuHtml = genererHtmlLignesCoursRestants(); // Génère les lignes
    tbody.innerHTML = contenuHtml;
}

/**
 * Génère le code HTML pour les lignes (tr) du tableau des cours restants,
 * en filtrant les cours dont les groupes restants sont à zéro.
 * @returns {string} Le code HTML des lignes du tableau.
 */
function genererHtmlLignesCoursRestants() {
    let html = "";
    const coursEnseignementRestants = G_COURS_ENSEIGNEMENT_CHAMP.filter((c) => c.grprestant > 0);
    const coursAutresRestants = G_COURS_AUTRES_TACHES_CHAMP.filter((c) => c.grprestant > 0);

    // Section Enseignement
    html += `<tr><td colspan="5" class="sous-titre-cours-restants">Périodes d'enseignement</td></tr>`;
    if (coursEnseignementRestants.length > 0) {
        coursEnseignementRestants.forEach((cours) => {
            const periodesRestantes = cours.nbperiodes * cours.grprestant;
            html += `<tr><td>${cours.codecours}</td><td>${cours.coursdescriptif}</td><td id="grp-restant-${cours.codecours}">${cours.grprestant}</td><td>${cours.nbperiodes}</td><td>${periodesRestantes}</td></tr>`;
        });
    } else {
        html += `<tr><td colspan="5" style="text-align:center; font-style:italic;">Toutes les périodes d'enseignement ont été choisies.</td></tr>`;
    }

    // Section Autres Tâches
    html += `<tr><td colspan="5" class="sous-titre-cours-restants">Périodes autres</td></tr>`;
    if (coursAutresRestants.length > 0) {
        coursAutresRestants.forEach((cours) => {
            const periodesRestantes = cours.nbperiodes * cours.grprestant;
            html += `<tr><td>${cours.codecours}</td><td>${cours.coursdescriptif}</td><td id="grp-restant-${cours.codecours}">${cours.grprestant}</td><td>${cours.nbperiodes}</td><td>${periodesRestantes}</td></tr>`;
        });
    } else {
        html += `<tr><td colspan="5" style="text-align:center; font-style:italic;">Toutes les autres tâches ont été choisies.</td></tr>`;
    }

    if (coursEnseignementRestants.length === 0 && coursAutresRestants.length === 0) {
        return '<tr><td colspan="5" style="text-align:center;">Toutes les périodes et tâches de ce champ ont été choisies.</td></tr>';
    }
    return html;
}

/**
 * Met à jour les listes de cours à choisir pour toutes les cartes dépliées.
 */
function regenererToutesLesListesDeCoursAChoisirGlobale() {
    document.querySelectorAll(".enseignant-card.detail-visible").forEach((card) => {
        const enseignantId = card.id.split("-").pop();
        const ulEnseignement = card.querySelector('ul.liste-cours-a-choisir[data-type-cours="enseignement"]');
        if (ulEnseignement) ulEnseignement.innerHTML = genererListeHTMLCoursDispo(G_COURS_ENSEIGNEMENT_CHAMP, enseignantId, "enseignement");
        const ulAutres = card.querySelector('ul.liste-cours-a-choisir[data-type-cours="autre"]');
        if (ulAutres) ulAutres.innerHTML = genererListeHTMLCoursDispo(G_COURS_AUTRES_TACHES_CHAMP, enseignantId, "autre");
        appliquerStatutVerrouillagePourCarte(card);
    });
}

/**
 * Génère le code HTML pour une liste de cours disponibles à l'attribution.
 * @returns {string} Le code HTML de la liste.
 */
function genererListeHTMLCoursDispo(listeCoursGlobale, enseignantId, typeCours) {
    let html = "";
    const coursAffichables = listeCoursGlobale.filter((cours) => cours.grprestant > 0);
    if (coursAffichables.length > 0) {
        coursAffichables.forEach((cours) => {
            html += `<li>
                        ${cours.codecours} - ${cours.coursdescriptif} (${cours.nbperiodes} pér. - ${cours.grprestant} grp. rest.)
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
 */
function mettreAJourLigneSommaire(enseignantId, periodes) {
    // 1. Mettre à jour le DOM pour l'affichage en direct
    const ligne = document.querySelector(`.sommaire-champ-section tbody tr[data-enseignant-id="${enseignantId}"]`);
    if (ligne) {
        ligne.querySelector(".sum-cours-val").textContent = periodes.periodes_cours;
        ligne.querySelector(".sum-autres-val").textContent = periodes.periodes_autres;
        ligne.querySelector(".sum-total-val").textContent = periodes.total_periodes;
    }

    // 2. Mettre à jour la variable de données globale
    // C'est crucial pour que la fonction d'impression ait les données les plus récentes.
    const enseignantData = G_ENSEIGNANTS_INITIAL_DATA.find((e) => e.enseignantid === parseInt(enseignantId));
    if (enseignantData) {
        enseignantData.periodes_actuelles = periodes;
    }
}

/**
 * Ajoute une carte d'enseignant à l'interface en utilisant le template HTML.
 * CORRECTION: Cette fonction est maintenant beaucoup plus robuste.
 */
function ajouterEnseignantDynamiquement(enseignant) {
    const container = document.querySelector(".enseignants-section");
    const btnCreerTache = document.getElementById("btn-creer-tache-restante");
    const template = document.getElementById("enseignant-card-template");
    if (!container || !btnCreerTache || !template) return;

    // Cloner le contenu du template
    const clone = template.content.cloneNode(true);
    const newCard = clone.querySelector(".enseignant-card");
    if (!newCard) return;

    // Mettre à jour les IDs et les données de la carte et de ses enfants
    newCard.id = `enseignant-card-${enseignant.enseignantid}`;

    const nomElement = newCard.querySelector('[data-template-nom="nom-enseignant"]');
    if (nomElement) {
        // Crée un nœud de texte pour le nom pour éviter les problèmes d'injection HTML
        const nomTextNode = document.createTextNode(`${enseignant.nomcomplet} `);
        nomElement.replaceChild(nomTextNode, nomElement.childNodes[0]);
    }

    const btnSupprimer = newCard.querySelector('[data-template-id-btn]');
    if (btnSupprimer) btnSupprimer.dataset.enseignantId = enseignant.enseignantid;

    const tableElement = newCard.querySelector('[data-template-id-table]');
    if (tableElement) tableElement.id = `table-attributions-${enseignant.enseignantid}`;

    const tbodyElement = newCard.querySelector('[data-template-id-tbody]');
    if (tbodyElement) tbodyElement.id = `tbody-attributions-${enseignant.enseignantid}`;

    // Insérer la nouvelle carte dans le DOM
    container.insertBefore(newCard, btnCreerTache);

    // Initialiser le contenu de la carte
    regenererTableauAttributionsEnseignant(enseignant.enseignantid, enseignant.attributions || []);
    appliquerStatutVerrouillagePourCarte(newCard); // Appliquer le statut de verrouillage
}

/**
 * Ajoute une ligne au tableau de sommaire pour un nouvel enseignant.
 */
function ajouterAuTableauSommaire(enseignant, periodes) {
    const tbody = document.querySelector("#tableau-sommaire-champ tbody");
    if (!tbody) return;
    const row = tbody.insertRow();
    row.dataset.enseignantId = enseignant.enseignantid;
    if (enseignant.estfictif) row.classList.add("enseignant-fictif-sommaire");
    else if (!enseignant.esttempsplein) row.classList.add("enseignant-temps-partiel-sommaire");
    else row.classList.add("enseignant-temps-plein-sommaire");
    row.innerHTML = `
        <td>${enseignant.nomcomplet}</td>
        <td class="sum-cours-val">${periodes.periodes_cours}</td>
        <td class="sum-autres-val">${periodes.periodes_autres}</td>
        <td class="sum-total-val">${periodes.total_periodes}</td>
        <td>${enseignant.estfictif ? "Tâche Restante" : !enseignant.esttempsplein ? "Temps Partiel" : "Temps Plein"}</td>`;
}

/**
 * Recalcule et met à jour la moyenne des périodes pour le champ.
 */
function recalculerEtAfficherMoyenneChamp() {
    let totalPeriodes = 0;
    let countTempsPleinNonFictif = 0;
    document.querySelectorAll("#tableau-sommaire-champ tbody tr").forEach((row) => {
        const isTempsPlein = row.classList.contains("enseignant-temps-plein-sommaire");
        const isFictif = row.classList.contains("enseignant-fictif-sommaire");
        if (isTempsPlein && !isFictif) {
            const totalCell = row.querySelector(".sum-total-val");
            if (totalCell) totalPeriodes += parseInt(totalCell.textContent, 10) || 0;
            countTempsPleinNonFictif++;
        }
    });
    const moyenne = countTempsPleinNonFictif > 0 ? totalPeriodes / countTempsPleinNonFictif : 0;
    const moyenneCell = document.getElementById("moyenne-champ-val");
    if (moyenneCell) moyenneCell.textContent = moyenne.toFixed(2);
}

/** Génère le HTML complet du tableau des cours restants */
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
 * Génère le HTML complet du tableau sommaire du champ à partir des données globales
 * au lieu de copier le HTML de la page. C'est plus robuste pour l'impression.
 */
function genererHtmlTableauSommaireChamp() {
    let tbodyHtml = "";
    // Utilise la variable globale G_ENSEIGNANTS_INITIAL_DATA qui est la source de vérité à jour.
    G_ENSEIGNANTS_INITIAL_DATA.forEach((enseignant) => {
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

        tbodyHtml += `
            <tr class="${statutClass}" data-enseignant-id="${enseignant.enseignantid}">
                <td>${enseignant.nomcomplet}</td>
                <td class="sum-cours-val">${periodes.periodes_cours}</td>
                <td class="sum-autres-val">${periodes.periodes_autres}</td>
                <td class="sum-total-val">${periodes.total_periodes}</td>
                <td>${statutText}</td>
            </tr>`;
    });

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

    const htmlSommaireChamp = genererHtmlTableauSommaireChamp();
    const htmlCoursRestants = genererHtmlTableauCoursRestants();

    // Inversion de l'ordre pour l'impression
    container.innerHTML = htmlSommaireChamp + htmlCoursRestants;
}