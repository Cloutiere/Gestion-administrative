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
    // Cette étape est nécessaire car le contenu du tbody est géré dynamiquement.
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
        // Génère le rapport des cours restants avant d'ouvrir la boîte de dialogue d'impression
        genererRapportCoursRestantsPourImpression();
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
 * Charge les listes de cours disponibles à la demande lors du premier affichage.
 * @param {HTMLElement} enseignantCard La carte d'enseignant concernée.
 */
function toggleEnseignantDetails(enseignantCard) {
    if (!enseignantCard) return;

    const etaitVisible = enseignantCard.classList.contains("detail-visible");

    // Ferme les autres cartes pour une meilleure lisibilité
    document.querySelectorAll(".enseignant-card.detail-visible").forEach((card) => {
        if (card !== enseignantCard) card.classList.remove("detail-visible");
    });

    // Ouvre ou ferme la carte cliquée
    if (!etaitVisible) {
        enseignantCard.classList.add("detail-visible");

        // CHARGEMENT À LA DEMANDE
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
 * @param {Array} attributionsArray La liste de ses attributions.
 */
function regenererTableauAttributionsEnseignant(enseignantId, attributionsArray) {
    const tbody = document.getElementById(`tbody-attributions-${enseignantId}`);
    if (!tbody) return;
    tbody.innerHTML = "";

    const attributionsEnseignement = attributionsArray.filter((attr) => !attr.estcoursautre).sort((a, b) => a.coursdescriptif.localeCompare(b.coursdescriptif));
    const attributionsAutres = attributionsArray.filter((attr) => attr.estcoursautre).sort((a, b) => a.coursdescriptif.localeCompare(b.coursdescriptif));

    let totalPeriodesEnseignantCalcule = 0;
    let contenuAjoute = false;
    const NOMBRE_COLONNES_TABLEAU = 6;

    if (attributionsEnseignement.length > 0) {
        const titreEnsRow = tbody.insertRow();
        titreEnsRow.classList.add("sous-titre-attributions");
        const titreEnsCell = titreEnsRow.insertCell();
        titreEnsCell.colSpan = NOMBRE_COLONNES_TABLEAU;
        titreEnsCell.textContent = "Périodes d'enseignement attribuées";
        contenuAjoute = true;

        attributionsEnseignement.forEach((attr) => {
            const row = tbody.insertRow();
            const totalPeriodesAttr = attr.nbperiodes * attr.nbgroupespris;
            totalPeriodesEnseignantCalcule += totalPeriodesAttr;
            row.innerHTML = `
                <td>${attr.codecours}</td>
                <td>${attr.coursdescriptif}</td>
                <td>${attr.nbgroupespris}</td>
                <td>${attr.nbperiodes}</td>
                <td>${totalPeriodesAttr}</td>
                <td class="no-print"><button class="btn-retirer-cours" data-attribution-id="${attr.attributionid}">Retirer</button></td>
            `;
        });
    }

    if (attributionsAutres.length > 0) {
        const titreAutresRow = tbody.insertRow();
        titreAutresRow.classList.add("sous-titre-attributions");
        const titreAutresCell = titreAutresRow.insertCell();
        titreAutresCell.colSpan = NOMBRE_COLONNES_TABLEAU;
        titreAutresCell.textContent = "Autres tâches attribuées";
        contenuAjoute = true;

        attributionsAutres.forEach((attr) => {
            const row = tbody.insertRow();
            const totalPeriodesAttr = attr.nbperiodes * attr.nbgroupespris;
            totalPeriodesEnseignantCalcule += totalPeriodesAttr;
            row.innerHTML = `
                <td>${attr.codecours}</td>
                <td>${attr.coursdescriptif}</td>
                <td>${attr.nbgroupespris}</td>
                <td>${attr.nbperiodes}</td>
                <td>${totalPeriodesAttr}</td>
                <td class="no-print"><button class="btn-retirer-cours" data-attribution-id="${attr.attributionid}">Retirer</button></td>
            `;
        });
    }

    if (!contenuAjoute) {
        const row = tbody.insertRow();
        const cellMessage = row.insertCell();
        cellMessage.colSpan = NOMBRE_COLONNES_TABLEAU;
        cellMessage.style.textAlign = "center";
        cellMessage.style.fontStyle = "italic";
        cellMessage.textContent = "Aucune période attribuée pour le moment.";
    }

    const totalRow = tbody.insertRow();
    totalRow.classList.add("total-attributions-row");
    const totalLabelCell = totalRow.insertCell();
    totalLabelCell.colSpan = NOMBRE_COLONNES_TABLEAU - 2;
    totalLabelCell.textContent = "Total Périodes Attribuées:";

    const totalValueCell = totalRow.insertCell();
    totalValueCell.textContent = totalPeriodesEnseignantCalcule;

    totalRow.insertCell(); // Cellule vide pour la colonne Action (no-print)
}

/**
 * Gestionnaire d'événements unique pour la section des enseignants (délégation d'événements).
 * @param {Event} event L'objet événement du clic.
 */
function gestionnaireClicsEnseignantsSection(event) {
    const target = event.target;

    // Clic sur l'en-tête pour déplier/replier la carte
    const entete = target.closest(".entete-enseignant");
    if (entete) {
        toggleEnseignantDetails(entete.closest(".enseignant-card"));
        return;
    }

    // Clic pour attribuer un cours
    if (target.matches('.contenu-selection-cours .cours-selection button[data-enseignant-id][data-cours-code]')) {
        attribuerCours(target.dataset.enseignantId, target.dataset.coursCode, target);
    }
    // Clic pour retirer un cours
    else if (target.classList.contains("btn-retirer-cours")) {
        const card = target.closest(".enseignant-card");
        const estFictif = card?.classList.contains("enseignant-fictif");
        if (G_CHAMP_EST_VERROUILLE && !estFictif) {
            alert("Les modifications sont désactivées car le champ est verrouillé.");
            return;
        }
        if (confirm("Êtes-vous sûr de vouloir retirer ce cours ?")) {
            retirerCours(target.dataset.attributionId, target);
        }
    }
    // Clic pour supprimer une tâche fictive
    else if (target.classList.contains("btn-supprimer-enseignant")) {
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
        if (document.body.contains(boutonClique)) {
            boutonClique.disabled = false;
            boutonClique.textContent = "Attribuer";
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
 * Appelle l'API pour créer une tâche restante et l'ajoute dynamiquement à l'interface.
 */
async function creerTacheRestante(boutonClique) {
    boutonClique.disabled = true;
    boutonClique.textContent = "Création...";
    try {
        const response = await fetch(`/api/champs/${G_CHAMP_NO_ACTUEL}/taches_restantes/creer`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
        });
        const data = await response.json();
        if (!response.ok || !data.success || !data.enseignant) {
            throw new Error(data.message || "Erreur création tâche restante.");
        }

        const nouvelEnseignant = data.enseignant;
        G_ENSEIGNANTS_INITIAL_DATA.push(nouvelEnseignant);
        ajouterEnseignantDynamiquement(nouvelEnseignant);

        const periodesInitiales = data.periodes_actuelles || { periodes_cours: 0, periodes_autres: 0, total_periodes: 0 };
        ajouterAuTableauSommaire(nouvelEnseignant, periodesInitiales);
        recalculerEtAfficherMoyenneChamp();
    } catch (error) {
        console.error("Erreur creerTacheRestante:", error);
        alert(error.message);
    } finally {
        boutonClique.disabled = false;
        boutonClique.textContent = "Créer une Tâche Restante";
    }
}

/**
 * Appelle l'API pour supprimer un enseignant (fictif) et le retire de l'interface.
 */
async function supprimerEnseignantFictif(enseignantId, boutonClique) {
    boutonClique.disabled = true;
    boutonClique.textContent = "Suppression...";
    try {
        const response = await fetch(`/api/enseignants/${enseignantId}/supprimer`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
        });
        const data = await response.json();
        if (!response.ok || !data.success) {
            throw new Error(data.message || "Erreur suppression tâche.");
        }

        document.getElementById(`enseignant-card-${enseignantId}`)?.remove();
        document.querySelector(`.sommaire-champ-section tbody tr[data-enseignant-id="${enseignantId}"]`)?.remove();

        const index = G_ENSEIGNANTS_INITIAL_DATA.findIndex((e) => e.enseignantid === parseInt(enseignantId));
        if (index > -1) {
            G_ENSEIGNANTS_INITIAL_DATA.splice(index, 1);
        }

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
            boutonClique.textContent = "Supprimer Tâche";
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
 * Régénère entièrement le tableau des cours restants.
 */
function regenererTableauCoursRestants() {
    const tbody = document.querySelector("#tableau-cours-restants tbody");
    if (!tbody) return;
    tbody.innerHTML = "";

    const titreEnsRow = tbody.insertRow();
    titreEnsRow.classList.add("sous-titre-cours-restants");
    const titreEnsCell = titreEnsRow.insertCell();
    titreEnsCell.colSpan = 5;
    titreEnsCell.textContent = "Périodes d'enseignement";

    if (G_COURS_ENSEIGNEMENT_CHAMP.length > 0) {
        G_COURS_ENSEIGNEMENT_CHAMP.forEach((cours) => {
            const row = tbody.insertRow();
            const periodesRestantes = cours.nbperiodes * cours.grprestant;
            row.innerHTML = `<td>${cours.codecours}</td>
                             <td>${cours.coursdescriptif}</td>
                             <td>${cours.nbperiodes}</td>
                             <td id="grp-restant-${cours.codecours}">${cours.grprestant}</td>
                             <td>${periodesRestantes}</td>`;
        });
    } else {
        const row = tbody.insertRow();
        row.innerHTML = `<td colspan="5" style="text-align:center; font-style:italic;">Aucun cours d'enseignement disponible.</td>`;
    }

    const titreAutresRow = tbody.insertRow();
    titreAutresRow.classList.add("sous-titre-cours-restants");
    const titreAutresCell = titreAutresRow.insertCell();
    titreAutresCell.colSpan = 5;
    titreAutresCell.textContent = "Périodes Autres";

    if (G_COURS_AUTRES_TACHES_CHAMP.length > 0) {
        G_COURS_AUTRES_TACHES_CHAMP.forEach((cours) => {
            const row = tbody.insertRow();
            const periodesRestantes = cours.nbperiodes * cours.grprestant;
            row.innerHTML = `<td>${cours.codecours}</td>
                             <td>${cours.coursdescriptif}</td>
                             <td>${cours.nbperiodes}</td>
                             <td id="grp-restant-${cours.codecours}">${cours.grprestant}</td>
                             <td>${periodesRestantes}</td>`;
        });
    } else {
        const row = tbody.insertRow();
        row.innerHTML = `<td colspan="5" style="text-align:center; font-style:italic;">Aucune autre tâche disponible.</td>`;
    }

    if (G_COURS_ENSEIGNEMENT_CHAMP.length === 0 && G_COURS_AUTRES_TACHES_CHAMP.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;">Aucun cours disponible dans ce champ.</td></tr>';
    }
}

/**
 * Met à jour les listes de cours à choisir pour toutes les cartes dépliées.
 */
function regenererToutesLesListesDeCoursAChoisirGlobale() {
    document.querySelectorAll(".enseignant-card.detail-visible").forEach((card) => {
        const enseignantId = card.id.split("-").pop();
        const ulEnseignement = card.querySelector('ul.liste-cours-a-choisir[data-type-cours="enseignement"]');
        if (ulEnseignement) {
            ulEnseignement.innerHTML = genererListeHTMLCoursDispo(G_COURS_ENSEIGNEMENT_CHAMP, enseignantId, "enseignement");
        }

        const ulAutres = card.querySelector('ul.liste-cours-a-choisir[data-type-cours="autre"]');
        if (ulAutres) {
            ulAutres.innerHTML = genererListeHTMLCoursDispo(G_COURS_AUTRES_TACHES_CHAMP, enseignantId, "autre");
        }
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
                        <button data-enseignant-id="${enseignantId}" data-cours-code="${cours.codecours}" 
                                data-type="${typeCours}" data-nb-periodes="${cours.nbperiodes}">
                            Attribuer
                        </button>
                     </li>`;
        });
    } else {
        html = `<li>Aucun cours de ce type disponible pour le moment.</li>`;
    }
    return html;
}

/**
 * Met à jour une ligne spécifique dans le tableau de sommaire du champ.
 */
function mettreAJourLigneSommaire(enseignantId, periodes) {
    const ligne = document.querySelector(`.sommaire-champ-section tbody tr[data-enseignant-id="${enseignantId}"]`);
    if (ligne) {
        ligne.querySelector(".sum-cours-val").textContent = periodes.periodes_cours;
        ligne.querySelector(".sum-autres-val").textContent = periodes.periodes_autres;
        ligne.querySelector(".sum-total-val").textContent = periodes.total_periodes;
    }
}

/**
 * Ajoute une carte d'enseignant à l'interface en utilisant le template HTML.
 */
function ajouterEnseignantDynamiquement(enseignant) {
    const container = document.querySelector(".enseignants-section");
    const btnCreerTache = document.getElementById("btn-creer-tache-restante");
    const template = document.getElementById("enseignant-card-template");

    if (!container || !btnCreerTache || !template) {
        console.error("Impossible d'ajouter dynamiquement l'enseignant: éléments manquants.");
        return;
    }

    // Crée une copie du contenu du template
    const clone = template.content.cloneNode(true);

    // Remplace les placeholders dans le clone
    const cardHtml = new XMLSerializer().serializeToString(clone)
        .replace(/\{\{ENSEIGNANT_ID\}\}/g, enseignant.enseignantid)
        .replace(/\{\{NOM_COMPLET\}\}/g, enseignant.nomcomplet);

    const tempDiv = document.createElement("div");
    tempDiv.innerHTML = cardHtml;
    const newCard = tempDiv.firstElementChild;

    container.insertBefore(newCard, btnCreerTache);

    regenererTableauAttributionsEnseignant(enseignant.enseignantid, enseignant.attributions || []);
    appliquerStatutVerrouillagePourCarte(newCard);
}

/**
 * Ajoute une ligne au tableau de sommaire pour un nouvel enseignant.
 */
function ajouterAuTableauSommaire(enseignant, periodes) {
    const tbody = document.querySelector("#tableau-sommaire-champ tbody");
    if (!tbody) return;

    const row = tbody.insertRow();
    row.dataset.enseignantId = enseignant.enseignantid;

    if (enseignant.estfictif) {
        row.classList.add("enseignant-fictif-sommaire");
    } else if (!enseignant.esttempsplein) {
        row.classList.add("enseignant-temps-partiel-sommaire");
    } else {
        row.classList.add("enseignant-temps-plein-sommaire");
    }

    row.innerHTML = `
        <td>${enseignant.nomcomplet}</td>
        <td class="sum-cours-val">${periodes.periodes_cours}</td>
        <td class="sum-autres-val">${periodes.periodes_autres}</td>
        <td class="sum-total-val">${periodes.total_periodes}</td>
        <td>${enseignant.estfictif ? "Fictif" : !enseignant.esttempsplein ? "Temps Partiel" : "Temps Plein"}</td>`;
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
            if (totalCell) {
                totalPeriodes += parseInt(totalCell.textContent, 10) || 0;
            }
            countTempsPleinNonFictif++;
        }
    });

    const moyenne = countTempsPleinNonFictif > 0 ? totalPeriodes / countTempsPleinNonFictif : 0;
    const moyenneCell = document.getElementById("moyenne-champ-val");
    if (moyenneCell) {
        moyenneCell.textContent = moyenne.toFixed(2);
    }
}

/**
 * Génère un tableau HTML des cours restants pour l'impression.
 */
function genererRapportCoursRestantsPourImpression() {
    const container = document.getElementById("print-report-cours-restants");
    if (!container) return;

    let html = "<h2>Rapport des cours et tâches restants</h2>";
    const tousLesCours = [...G_COURS_ENSEIGNEMENT_CHAMP, ...G_COURS_AUTRES_TACHES_CHAMP];
    const coursRestantsSignificatifs = tousLesCours.filter((c) => c.grprestant > 0);

    if (coursRestantsSignificatifs.length > 0) {
        html +=
            '<table style="width:100%; border-collapse: collapse; margin-top:10px;"><thead><tr><th style="border:1px solid #000; padding:4px; background-color:#e9ecef;">Code</th><th style="border:1px solid #000; padding:4px; background-color:#e9ecef;">Descriptif</th><th style="border:1px solid #000; padding:4px; background-color:#e9ecef;">Pér./Grp.</th><th style="border:1px solid #000; padding:4px; background-color:#e9ecef;">Grp. Restants</th></tr></thead><tbody>';
        coursRestantsSignificatifs
            .sort((a, b) => a.codecours.localeCompare(b.codecours))
            .forEach((c) => {
                html += `<tr><td style="border:1px solid #000; padding:4px;">${c.codecours}</td><td style="border:1px solid #000; padding:4px;">${c.coursdescriptif}</td><td style="border:1px solid #000; padding:4px;">${c.nbperiodes}</td><td style="border:1px solid #000; padding:4px;">${c.grprestant}</td></tr>`;
            });
        html += "</tbody></table>";
    } else {
        html += "<p>Aucun cours ou tâche restante dans ce champ.</p>";
    }
    container.innerHTML = html;
}