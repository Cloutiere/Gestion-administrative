// static/js/page_champ.js
// Ce script gère toute l'interactivité de la page de gestion d'un champ spécifique.
// Il s'appuie sur des variables globales initialisées dans le template HTML via Jinja2 :
// - G_COURS_ENSEIGNEMENT_CHAMP: Liste des cours d'enseignement du champ.
// - G_COURS_AUTRES_TACHES_CHAMP: Liste des autres tâches du champ.
// - G_ENSEIGNANTS_INITIAL_DATA: Liste complète des enseignants du champ avec leurs données.
// - G_CHAMP_NO_ACTUEL: Le numéro du champ actuellement affiché.
// - G_CHAMP_EST_VERROUILLE: Un booléen indiquant si le champ est verrouillé.
// - API_URLS: Un objet contenant les URLs pour les appels fetch.

/**
 * Fonction utilitaire pour formater les nombres de périodes.
 * Affiche les décimales uniquement si elles sont non nulles.
 * @param {number|null|undefined} value Le nombre à formater.
 * @returns {string} Le nombre formaté en chaîne de caractères.
 */
function formatPeriodes(value) {
    if (value === null || value === undefined) {
        return "";
    }
    const formatter = new Intl.NumberFormat("fr-CA", {
        minimumFractionDigits: 0,
        maximumFractionDigits: 2,
        useGrouping: false,
    });
    return formatter.format(value);
}

/**
 * Point d'entrée principal du script, exécuté une fois le DOM entièrement chargé.
 */
document.addEventListener("DOMContentLoaded", function () {
    regenererTableauCoursRestants();

    if (typeof G_ENSEIGNANTS_INITIAL_DATA !== "undefined") {
        G_ENSEIGNANTS_INITIAL_DATA.forEach((enseignant) => {
            regenererTableauAttributionsEnseignant(enseignant.enseignantid, enseignant.attributions || []);
        });
    }

    appliquerStatutVerrouillageUI();

    const enseignantsSection = document.querySelector(".enseignants-section");
    if (enseignantsSection) {
        enseignantsSection.addEventListener("click", gestionnaireClicsEnseignantsSection);
    }

    document.getElementById("btn-creer-tache-restante")?.addEventListener("click", function () {
        creerTacheRestante(this);
    });

    document.getElementById("btn-imprimer-champ")?.addEventListener("click", function () {
        document.querySelectorAll(".enseignant-card.detail-visible").forEach((card) => {
            card.classList.remove("detail-visible");
        });
        genererRapportSommairePourImpression();
        prepareAndPrint("champ");
    });

    document.getElementById("btn-imprimer-taches-restantes")?.addEventListener("click", function () {
        document.querySelectorAll(".enseignant-card.detail-visible").forEach((card) => {
            card.classList.remove("detail-visible");
        });
        prepareAndPrint("taches-restantes");
    });
});

/**
 * Prépare le document pour un mode d'impression spécifique et lance l'impression.
 * @param {'champ' | 'taches-restantes'} mode Le mode d'impression.
 */
function prepareAndPrint(mode) {
    const printClass = `printing-${mode}`;
    document.documentElement.classList.add(printClass);

    const cleanup = () => {
        document.documentElement.classList.remove(printClass);
        window.removeEventListener("afterprint", cleanup);
    };

    window.addEventListener("afterprint", cleanup);
    window.print();
    setTimeout(cleanup, 1000);
}

/**
 * Applique l'état de verrouillage à une seule carte d'enseignant.
 * @param {HTMLElement} card La carte d'enseignant à mettre à jour.
 */
function appliquerStatutVerrouillagePourCarte(card) {
    const estVerrouille = G_CHAMP_EST_VERROUILLE;
    const estFictif = card.classList.contains("enseignant-fictif");
    const doitDesactiver = estVerrouille && !estFictif;

    card.querySelectorAll(".btn-retirer-cours, .cours-selection button").forEach((button) => {
        button.disabled = doitDesactiver;
        button.title = doitDesactiver ? "Les modifications sont désactivées car le champ est verrouillé." : "";
    });
}

/**
 * Applique l'état de verrouillage à l'ensemble de l'interface.
 */
function appliquerStatutVerrouillageUI() {
    document.querySelectorAll(".enseignant-card").forEach(appliquerStatutVerrouillagePourCarte);
}

/**
 * Gère le basculement de l'affichage détaillé d'une carte d'enseignant.
 * @param {HTMLElement} enseignantCard La carte d'enseignant concernée.
 */
function toggleEnseignantDetails(enseignantCard) {
    if (!enseignantCard) return;

    const etaitVisible = enseignantCard.classList.contains("detail-visible");

    document.querySelectorAll(".enseignant-card.detail-visible").forEach((card) => {
        if (card !== enseignantCard) {
            card.classList.remove("detail-visible");
        }
    });

    enseignantCard.classList.toggle("detail-visible", !etaitVisible);

    if (!etaitVisible) {
        const enseignantId = enseignantCard.id.split("-").pop();
        const ulEnseignement = enseignantCard.querySelector('ul.liste-cours-a-choisir[data-type-cours="enseignement"]');
        const ulAutres = enseignantCard.querySelector('ul.liste-cours-a-choisir[data-type-cours="autre"]');

        if (ulEnseignement) ulEnseignement.innerHTML = genererListeHTMLCoursDispo(G_COURS_ENSEIGNEMENT_CHAMP, enseignantId);
        if (ulAutres) ulAutres.innerHTML = genererListeHTMLCoursDispo(G_COURS_AUTRES_TACHES_CHAMP, enseignantId);
        appliquerStatutVerrouillagePourCarte(enseignantCard);
    }
}

/**
 * Régénère le tableau des attributions pour un enseignant.
 * @param {number|string} enseignantId L'ID de l'enseignant.
 * @param {Array} attributionsArray La liste de ses attributions.
 */
function regenererTableauAttributionsEnseignant(enseignantId, attributionsArray) {
    const tbody = document.getElementById(`tbody-attributions-${enseignantId}`);
    if (!tbody) return;

    tbody.innerHTML = "";
    let totalPeriodesEnseignantCalcule = 0;

    const attributionsAgregees = attributionsArray.reduce((acc, attr) => {
        if (!acc[attr.codecours]) {
            acc[attr.codecours] = { ...attr, nbgroupespris: 0, attributionIds: [] };
        }
        acc[attr.codecours].nbgroupespris += attr.nbgroupespris;
        acc[attr.codecours].attributionIds.push(attr.attributionid);
        return acc;
    }, {});

    const attributionsEnseignement = Object.values(attributionsAgregees).filter((a) => !a.estcoursautre).sort((a, b) => a.coursdescriptif.localeCompare(b.coursdescriptif));
    const attributionsAutres = Object.values(attributionsAgregees).filter((a) => a.estcoursautre).sort((a, b) => a.coursdescriptif.localeCompare(b.coursdescriptif));

    if (attributionsEnseignement.length > 0) {
        tbody.innerHTML += `<tr class="sous-titre-attributions-row"><td colspan="6" class="sous-titre-attributions">Périodes d'enseignement</td></tr>`;
        attributionsEnseignement.forEach((attr) => {
            const totalPeriodesAttr = attr.nbperiodes * attr.nbgroupespris;
            totalPeriodesEnseignantCalcule += totalPeriodesAttr;
            tbody.innerHTML += `<tr><td>${attr.codecours}</td><td>${attr.coursdescriptif}</td><td>${attr.nbgroupespris}</td><td>${formatPeriodes(attr.nbperiodes)}</td><td>${formatPeriodes(totalPeriodesAttr)}</td><td class="no-print"><button class="btn-retirer-cours" data-attribution-id="${attr.attributionIds.at(-1)}">Retirer</button></td></tr>`;
        });
    }

    if (attributionsAutres.length > 0) {
        tbody.innerHTML += `<tr class="sous-titre-attributions-row"><td colspan="6" class="sous-titre-attributions">Autres tâches</td></tr>`;
        attributionsAutres.forEach((attr) => {
            const totalPeriodesAttr = attr.nbperiodes * attr.nbgroupespris;
            totalPeriodesEnseignantCalcule += totalPeriodesAttr;
            tbody.innerHTML += `<tr><td>${attr.codecours}</td><td>${attr.coursdescriptif}</td><td>${attr.nbgroupespris}</td><td>${formatPeriodes(attr.nbperiodes)}</td><td>${formatPeriodes(totalPeriodesAttr)}</td><td class="no-print"><button class="btn-retirer-cours" data-attribution-id="${attr.attributionIds.at(-1)}">Retirer</button></td></tr>`;
        });
    }

    if (tbody.innerHTML === "") {
        tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; font-style: italic;">Aucune période choisie.</td></tr>`;
    } else {
        tbody.innerHTML += `<tr class="total-attributions-row"><td colspan="4">Total périodes choisies:</td><td>${formatPeriodes(totalPeriodesEnseignantCalcule)}</td><td class="no-print"></td></tr>`;
    }
}

/**
 * Gestionnaire d'événements pour la section des enseignants.
 * @param {Event} event L'objet événement du clic.
 */
function gestionnaireClicsEnseignantsSection(event) {
    const target = event.target;
    const card = target.closest(".enseignant-card");
    if (!card) return;

    if (target.closest(".entete-enseignant")) {
        toggleEnseignantDetails(card);
    } else if (target.matches(".cours-selection button")) {
        attribuerCours(target.dataset.enseignantId, target.dataset.coursCode, target);
    } else if (target.matches(".btn-retirer-cours")) {
        if (confirm("Êtes-vous sûr de vouloir retirer une attribution de ce cours ?")) {
            retirerCours(target.dataset.attributionId, target);
        }
    } else if (target.matches(".btn-supprimer-enseignant")) {
        if (confirm("Êtes-vous sûr de vouloir supprimer cette tâche restante ?")) {
            supprimerEnseignantFictif(target.dataset.enseignantId, target);
        }
    }
}

/**
 * Appelle l'API pour attribuer un cours.
 * @param {string} enseignantId L'ID de l'enseignant.
 * @param {string} codeCours Le code du cours.
 * @param {HTMLElement} boutonClique Le bouton cliqué.
 */
async function attribuerCours(enseignantId, codeCours, boutonClique) {
    const card = boutonClique.closest(".enseignant-card");
    if (boutonClique.disabled) return;
    boutonClique.disabled = true;
    boutonClique.textContent = "...";

    try {
        const response = await fetch(API_URLS.attribuerCours, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ enseignant_id: parseInt(enseignantId), code_cours: codeCours }),
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.message || "Erreur d'attribution.");

        mettreAJourLigneSommaire(enseignantId, data.periodes_enseignant);
        regenererTableauAttributionsEnseignant(enseignantId, data.attributions_enseignant || []);
        mettreAJourDonneesGlobalesCours(codeCours, data.groupes_restants_cours);
        regenererTableauCoursRestants();
        regenererToutesLesListesDeCoursAChoisirGlobale();
        recalculerEtAfficherMoyenneChamp();
        if (card) appliquerStatutVerrouillagePourCarte(card);
    } catch (error) {
        console.error("Erreur dans attribuerCours:", error);
        alert(error.message);
    } finally {
        if (document.body.contains(boutonClique)) {
            boutonClique.disabled = false;
            boutonClique.textContent = "Choisir";
        }
    }
}

/**
 * Appelle l'API pour retirer une attribution.
 * @param {string} attributionId L'ID de l'attribution.
 * @param {HTMLElement} _boutonClique Le bouton cliqué.
 */
async function retirerCours(attributionId, _boutonClique) {
    try {
        const response = await fetch(API_URLS.retirerCours, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ attribution_id: parseInt(attributionId) }),
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.message || "Erreur de retrait.");

        mettreAJourLigneSommaire(data.enseignant_id, data.periodes_enseignant);
        regenererTableauAttributionsEnseignant(data.enseignant_id, data.attributions_enseignant || []);
        mettreAJourDonneesGlobalesCours(data.code_cours, data.groupes_restants_cours);
        regenererTableauCoursRestants();
        regenererToutesLesListesDeCoursAChoisirGlobale();
        recalculerEtAfficherMoyenneChamp();
        const card = document.getElementById(`enseignant-card-${data.enseignant_id}`);
        if (card) appliquerStatutVerrouillagePourCarte(card);
    } catch (error) {
        console.error("Erreur dans retirerCours:", error);
        alert(error.message);
    }
}

/**
 * Appelle l'API pour créer une tâche restante.
 * @param {HTMLElement} boutonClique Le bouton cliqué.
 */
async function creerTacheRestante(boutonClique) {
    boutonClique.disabled = true;
    boutonClique.textContent = "Création...";
    try {
        const response = await fetch(API_URLS.creerTacheRestante, { method: "POST" });
        const data = await response.json();
        if (!response.ok || !data.enseignant) throw new Error(data.message || "Erreur de création.");

        G_ENSEIGNANTS_INITIAL_DATA.push(data.enseignant);
        ajouterEnseignantDynamiquement(data.enseignant);
        ajouterAuTableauSommaire(data.enseignant, data.periodes_actuelles || {});
        recalculerEtAfficherMoyenneChamp();
    } catch (error) {
        console.error("Erreur dans creerTacheRestante:", error);
        alert(error.message);
    } finally {
        boutonClique.disabled = false;
        boutonClique.textContent = "Créer une Tâche Restante";
    }
}

/**
 * Appelle l'API pour supprimer un enseignant fictif.
 * @param {string} enseignantId L'ID de l'enseignant.
 * @param {HTMLElement} boutonClique Le bouton cliqué.
 */
async function supprimerEnseignantFictif(enseignantId, boutonClique) {
    boutonClique.disabled = true;
    boutonClique.textContent = "Suppression...";
    try {
        // CORRECTION : L'URL est construite dynamiquement en remplaçant l'ID factice
        // par le véritable ID de l'enseignant au moment de l'appel.
        const url = API_URLS.supprimerEnseignant.replace("999999999", enseignantId);
        const response = await fetch(url, { method: "POST" });
        const data = await response.json();
        if (!response.ok) throw new Error(data.message || "Erreur de suppression.");

        document.getElementById(`enseignant-card-${enseignantId}`)?.remove();
        document.querySelector(`.sommaire-champ-section tbody tr[data-enseignant-id="${enseignantId}"]`)?.remove();
        G_ENSEIGNANTS_INITIAL_DATA = G_ENSEIGNANTS_INITIAL_DATA.filter((e) => e.enseignantid !== parseInt(enseignantId));

        if (data.cours_liberes_details?.length > 0) {
            data.cours_liberes_details.forEach((cours) => {
                mettreAJourDonneesGlobalesCours(cours.code_cours, cours.nouveaux_groupes_restants);
            });
        }

        regenererTableauCoursRestants();
        regenererToutesLesListesDeCoursAChoisirGlobale();
        recalculerEtAfficherMoyenneChamp();
    } catch (error) {
        console.error("Erreur dans supprimerEnseignantFictif:", error);
        alert(error.message);
        if (boutonClique) {
            boutonClique.disabled = false;
            boutonClique.textContent = "Supprimer tâche";
        }
    }
}


/**
 * Met à jour les données globales d'un cours.
 * @param {string} codeCours Le code du cours.
 * @param {number} nouveauxGrpRestants Le nouveau nombre de groupes.
 */
function mettreAJourDonneesGlobalesCours(codeCours, nouveauxGrpRestants) {
    const coursE = G_COURS_ENSEIGNEMENT_CHAMP.find((c) => c.codecours === codeCours);
    if (coursE) coursE.grprestant = nouveauxGrpRestants;
    const coursA = G_COURS_AUTRES_TACHES_CHAMP.find((c) => c.codecours === codeCours);
    if (coursA) coursA.grprestant = nouveauxGrpRestants;
}

/**
 * Régénère le tableau des cours restants.
 */
function regenererTableauCoursRestants() {
    const tbody = document.querySelector("#tableau-cours-restants tbody");
    if (tbody) {
        tbody.innerHTML = genererHtmlLignesCoursRestants();
    }
}

/**
 * Génère le HTML pour les lignes du tableau des cours restants.
 * @returns {string} Le code HTML des lignes.
 */
function genererHtmlLignesCoursRestants() {
    const coursEnseignement = G_COURS_ENSEIGNEMENT_CHAMP.filter((c) => c.grprestant > 0);
    const coursAutres = G_COURS_AUTRES_TACHES_CHAMP.filter((c) => c.grprestant > 0);
    let html = "";

    html += `<tr class="sous-titre-attributions-row"><td colspan="5" class="sous-titre-attributions">Périodes d'enseignement</td></tr>`;
    if (coursEnseignement.length > 0) {
        coursEnseignement.forEach((c) => (html += `<tr><td>${c.codecours}</td><td>${c.coursdescriptif}</td><td>${c.grprestant}</td><td>${formatPeriodes(c.nbperiodes)}</td><td>${formatPeriodes(c.nbperiodes * c.grprestant)}</td></tr>`));
    } else {
        html += `<tr><td colspan="5" style="text-align:center; font-style:italic;">Tous choisis.</td></tr>`;
    }

    html += `<tr class="sous-titre-attributions-row"><td colspan="5" class="sous-titre-attributions">Autres tâches</td></tr>`;
    if (coursAutres.length > 0) {
        coursAutres.forEach((c) => (html += `<tr><td>${c.codecours}</td><td>${c.coursdescriptif}</td><td>${c.grprestant}</td><td>${formatPeriodes(c.nbperiodes)}</td><td>${formatPeriodes(c.nbperiodes * c.grprestant)}</td></tr>`));
    } else {
        html += `<tr><td colspan="5" style="text-align:center; font-style:italic;">Toutes choisies.</td></tr>`;
    }

    return html;
}

/**
 * Régénère toutes les listes de cours à choisir.
 */
function regenererToutesLesListesDeCoursAChoisirGlobale() {
    document.querySelectorAll(".enseignant-card.detail-visible").forEach((card) => {
        const enseignantId = card.id.split("-").pop();
        const ulEnseignement = card.querySelector('ul.liste-cours-a-choisir[data-type-cours="enseignement"]');
        if (ulEnseignement) ulEnseignement.innerHTML = genererListeHTMLCoursDispo(G_COURS_ENSEIGNEMENT_CHAMP, enseignantId);
        const ulAutres = card.querySelector('ul.liste-cours-a-choisir[data-type-cours="autre"]');
        if (ulAutres) ulAutres.innerHTML = genererListeHTMLCoursDispo(G_COURS_AUTRES_TACHES_CHAMP, enseignantId);
        appliquerStatutVerrouillagePourCarte(card);
    });
}

/**
 * Génère le HTML pour une liste de cours disponibles.
 * @param {Array} listeCoursGlobale La liste des cours.
 * @param {string} enseignantId L'ID de l'enseignant.
 * @returns {string} Le code HTML des éléments de la liste.
 */
function genererListeHTMLCoursDispo(listeCoursGlobale, enseignantId) {
    const coursAffichables = listeCoursGlobale.filter((c) => c.grprestant > 0);
    if (coursAffichables.length === 0) {
        return `<li>Aucun cours de ce type disponible.</li>`;
    }
    return coursAffichables
        .map((c) => `<li><span>${c.codecours} - ${c.coursdescriptif} (${c.grprestant} grp. - ${formatPeriodes(c.nbperiodes)} p.)</span><button data-enseignant-id="${enseignantId}" data-cours-code="${c.codecours}">Choisir</button></li>`)
        .join("");
}

/**
 * Met à jour une ligne dans le tableau de sommaire.
 * @param {string|number} enseignantId L'ID de l'enseignant.
 * @param {object} periodes Objet contenant les totaux de périodes.
 */
function mettreAJourLigneSommaire(enseignantId, periodes) {
    const ligne = document.querySelector(`.sommaire-champ-section tbody tr[data-enseignant-id="${enseignantId}"]`);
    if (ligne) {
        ligne.querySelector(".sum-cours-val").textContent = formatPeriodes(periodes.periodes_cours);
        ligne.querySelector(".sum-autres-val").textContent = formatPeriodes(periodes.periodes_autres);
        ligne.querySelector(".sum-total-val").textContent = formatPeriodes(periodes.total_periodes);
    }
    const enseignantData = G_ENSEIGNANTS_INITIAL_DATA.find((e) => e.enseignantid === parseInt(enseignantId));
    if (enseignantData) {
        enseignantData.periodes_actuelles = periodes;
    }
}

/**
 * Ajoute dynamiquement une carte d'enseignant.
 * @param {object} enseignant L'objet enseignant.
 */
function ajouterEnseignantDynamiquement(enseignant) {
    const container = document.querySelector(".enseignants-section");
    const template = document.getElementById("enseignant-card-template");
    const btnCreer = document.getElementById("btn-creer-tache-restante");
    if (!container || !template || !btnCreer) return;

    const clone = template.content.cloneNode(true);
    const newCard = clone.querySelector(".enseignant-card");
    newCard.id = `enseignant-card-${enseignant.enseignantid}`;
    newCard.querySelector("[data-template-nom]").textContent = enseignant.nomcomplet;
    newCard.querySelector("[data-template-id-btn]").dataset.enseignantId = enseignant.enseignantid;
    newCard.querySelector("[data-template-id-table]").id = `table-attributions-${enseignant.enseignantid}`;
    newCard.querySelector("[data-template-id-tbody]").id = `tbody-attributions-${enseignant.enseignantid}`;
    clone.querySelector(".signature-line").textContent = `Signature de l'enseignant : ${enseignant.nomcomplet}`;

    container.insertBefore(clone, btnCreer);
    regenererTableauAttributionsEnseignant(enseignant.enseignantid, enseignant.attributions || []);
    appliquerStatutVerrouillagePourCarte(document.getElementById(`enseignant-card-${enseignant.enseignantid}`));
}

/**
 * Ajoute une ligne au tableau de sommaire.
 * @param {object} enseignant L'objet enseignant.
 * @param {object} periodes L'objet des périodes.
 */
function ajouterAuTableauSommaire(enseignant, periodes) {
    const tbody = document.querySelector("#tableau-sommaire-champ tbody");
    if (!tbody) return;
    const row = tbody.insertRow();
    row.dataset.enseignantId = enseignant.enseignantid;
    row.className = enseignant.estfictif ? "enseignant-fictif-sommaire" : "";
    row.innerHTML = `<td>${enseignant.nomcomplet}</td><td class="sum-cours-val">${formatPeriodes(periodes.periodes_cours)}</td><td class="sum-autres-val">${formatPeriodes(periodes.periodes_autres)}</td><td class="sum-total-val">${formatPeriodes(periodes.total_periodes)}</td><td>Tâche Restante</td>`;
}

/**
 * Recalcule et met à jour la moyenne des périodes du champ.
 */
function recalculerEtAfficherMoyenneChamp() {
    const enseignantsTempsPlein = G_ENSEIGNANTS_INITIAL_DATA.filter((e) => e.esttempsplein && !e.estfictif);
    const totalPeriodes = enseignantsTempsPlein.reduce((sum, e) => sum + (e.periodes_actuelles?.total_periodes || 0), 0);
    const moyenne = enseignantsTempsPlein.length > 0 ? totalPeriodes / enseignantsTempsPlein.length : 0;
    const moyenneCell = document.getElementById("moyenne-champ-val");
    if (moyenneCell) {
        moyenneCell.textContent = formatPeriodes(moyenne);
    }
}

/**
 * Génère et insère le HTML du résumé pour l'impression.
 */
function genererRapportSommairePourImpression() {
    const container = document.getElementById("print-summary-page");
    if (!container) return;
    container.innerHTML = genererHtmlTableauSommaireChamp() + genererHtmlTableauCoursRestants();
}

/**
 * Génère le HTML du tableau sommaire pour l'impression.
 * @returns {string} Le code HTML du tableau.
 */
function genererHtmlTableauSommaireChamp() {
    let tbodyHtml = "";
    const enseignantsReels = G_ENSEIGNANTS_INITIAL_DATA.filter((e) => !e.estfictif);
    const enseignantsTries = [...enseignantsReels].sort((a, b) => (a.nomcomplet || "").localeCompare(b.nomcomplet || ""));

    enseignantsTries.forEach((enseignant) => {
        const p = enseignant.periodes_actuelles || { periodes_cours: 0, periodes_autres: 0, total_periodes: 0 };
        const statut = enseignant.esttempsplein ? "Temps Plein" : "Temps Partiel";
        tbodyHtml += `<tr><td>${enseignant.nomcomplet}</td><td>${formatPeriodes(p.periodes_cours)}</td><td>${formatPeriodes(p.periodes_autres)}</td><td>${formatPeriodes(p.total_periodes)}</td><td>${statut}</td></tr>`;
    });

    const moyenneChamp = document.getElementById("moyenne-champ-val")?.textContent || "0";
    return `<h2 class="section-title">Tâches du champ : ${G_CHAMP_NO_ACTUEL}</h2><table id="tableau-sommaire-champ-print"><thead><tr><th>Nom</th><th>Cours</th><th>Autres</th><th>Total</th><th>Statut</th></tr></thead><tbody>${tbodyHtml}</tbody><tfoot><tr><td colspan="3" style="text-align:right;"><strong>Moyenne champ (temps plein):</strong></td><td>${moyenneChamp}</td><td></td></tr></tfoot></table>`;
}

/**
 * Génère le HTML du tableau des cours restants pour l'impression.
 * @returns {string} Le code HTML du tableau.
 */
function genererHtmlTableauCoursRestants() {
    const lignesHtml = genererHtmlLignesCoursRestants();
    return `<h2 class="section-title">Périodes restantes dans ce champ</h2><table id="tableau-cours-restants-print"><thead><tr><th>Code</th><th>Cours disponibles</th><th>Grp. rest.</th><th>Pér.</th><th>Pér. restantes</th></tr></thead><tbody>${lignesHtml}</tbody></table>`;
}