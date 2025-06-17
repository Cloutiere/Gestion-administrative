// mon_application/static/js/page_sommaire.js

document.addEventListener('DOMContentLoaded', function() {
    if (typeof PAGE_DATA === 'undefined' || !PAGE_DATA.ANNEE_ACTIVE) {
        console.log("PAGE_DATA non défini ou aucune année active, script du sommaire non exécuté.");
        return;
    }

    const { IS_ADMIN, URLS } = PAGE_DATA;
    const anneeSelector = document.getElementById('annee-selector');
    const tableBody = document.querySelector('#table-moyennes-par-champ tbody');
    const moyenneGeneraleSpan = document.getElementById('moyenne-generale-etablissement');
    const moyenneConfirmeeSpan = document.getElementById('moyenne-preliminaire-confirmee');
    const totalEnseignantsTd = document.getElementById('total-enseignants-tp');
    const totalPeriodesTd = document.getElementById('total-periodes-choisies-tp');
    const totalPeriodesMagiquesConfirmeesTd = document.getElementById('total-periodes-confirmees-magiques');
    const chiffreMagiqueTd = document.getElementById('valeur-chiffre-magique');
    const soldeFinalTd = document.getElementById('valeur-solde-final');

    /**
     * Formate une valeur numérique en chaîne avec une virgule comme séparateur décimal.
     * @param {number|string} value - La valeur à formater.
     * @returns {string} La valeur formatée.
     */
    function formatPeriodes(value) {
        return parseFloat(value).toFixed(2).replace('.', ',');
    }

    /**
     * Crée une icône SVG pour le tableau (verrou ou confirmation).
     * @param {'lock' | 'confirm'} type - Le type d'icône.
     * @param {string} champNo - Le numéro du champ associé.
     * @param {boolean} initialState - L'état initial (verrouillé/déverrouillé, confirmé/non confirmé).
     * @returns {SVGSVGElement} L'élément SVG de l'icône.
     */
    function createIcon(type, champNo, initialState) {
        const svgNS = "http://www.w3.org/2000/svg";
        const svg = document.createElementNS(svgNS, "svg");
        const path = document.createElementNS(svgNS, "path");
        svg.appendChild(path);

        if (type === 'lock') {
            svg.setAttribute("viewBox", "0 0 24 24");
            path.setAttribute("d", "M12 17c1.1 0 2-.9 2-2s-.9-2-2-2-2 .9-2 2 .9 2 2 2zm6-9h-1V6c0-2.76-2.24-5-5-5S7 3.24 7 6v2H6c-1.1 0-2 .9-2 2v10c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V10c0-1.1-.9-2-2-2zM8.9 6c0-1.71 1.39-3.1 3.1-3.1s3.1 1.39 3.1 3.1v2H8.9V6z");
            svg.classList.add('lock-icon');
            svg.classList.toggle('locked', initialState);
        } else { // 'confirm'
            svg.setAttribute("viewBox", "0 0 24 24");
            path.setAttribute("d", "M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z");
            svg.classList.add('confirm-icon');
            svg.classList.toggle('confirmed', initialState);
        }

        // Note: La logique de clic a été retirée, car non spécifiée dans la demande actuelle.
        // Si besoin, elle pourra être ajoutée ici.
        return svg;
    }

    /**
     * Rend le contenu du tableau et met à jour les totaux.
     * @param {object} data - Les données reçues de l'API.
     */
    function renderTable(data) {
        tableBody.innerHTML = '';
        moyenneGeneraleSpan.textContent = `${formatPeriodes(data.moyenne_generale)} périodes`;
        moyenneConfirmeeSpan.textContent = `${formatPeriodes(data.moyenne_preliminaire_confirmee)} périodes`;

        let totalPeriodesMagiquesConfirmees = 0;
        const champsTries = Object.entries(data.moyennes_par_champ).sort((a, b) => a[0].localeCompare(b[0]));

        champsTries.forEach(([champNo, champData]) => {
            const row = tableBody.insertRow();
            row.id = `champ-row-${champNo}`;
            row.classList.toggle('champ-verrouille-row', champData.est_verrouille);

            const diff = champData.moyenne - 24;
            const diffConfirme = champData.est_confirme ? champData.periodes_magiques : 0;
            totalPeriodesMagiquesConfirmees += diffConfirme;

            // Cellule N° champ
            row.insertCell().textContent = champNo;

            // ** MISE À JOUR : Création du lien pour le nom du champ **
            const nomChampCell = row.insertCell();
            const champLink = document.createElement('a');
            champLink.href = URLS.URL_CHAMP_TEMPLATE.replace('__CHAMP_NO__', champNo);
            champLink.textContent = champData.champ_nom;
            nomChampCell.appendChild(champLink);

            // Cellules Icônes et Données
            row.insertCell().appendChild(createIcon('lock', champNo, champData.est_verrouille)).classList.add('icon-cell');
            row.insertCell().textContent = champData.nb_enseignants_tp;
            row.insertCell().textContent = formatPeriodes(champData.periodes_choisies_tp);
            row.insertCell().textContent = formatPeriodes(champData.moyenne);
            row.insertCell().textContent = formatPeriodes(diff);
            row.insertCell().appendChild(createIcon('confirm', champNo, champData.est_confirme)).classList.add('icon-cell');
            row.insertCell().textContent = formatPeriodes(diffConfirme);
        });

        // Mise à jour du pied de tableau (footer)
        totalEnseignantsTd.textContent = data.grand_totals.total_enseignants_tp;
        totalPeriodesTd.textContent = formatPeriodes(data.grand_totals.total_periodes_choisies_tp);
        totalPeriodesMagiquesConfirmeesTd.textContent = formatPeriodes(totalPeriodesMagiquesConfirmees);

        const chiffreMagique = data.grand_totals.total_enseignants_tp * 0.6;
        chiffreMagiqueTd.textContent = formatPeriodes(chiffreMagique);

        const soldeFinal = totalPeriodesMagiquesConfirmees - chiffreMagique;
        soldeFinalTd.textContent = formatPeriodes(soldeFinal);
        soldeFinalTd.className = soldeFinal >= 0 ? 'solde-positif' : 'solde-negatif';
    }


    /**
     * Récupère les données du serveur et lance le rendu.
     */
    function fetchDataAndRender() {
        fetch(URLS.API_GET_DONNEES_SOMMAIRE)
            .then(response => {
                if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
                return response.json();
            })
            .then(data => {
                if (data) {
                    renderTable(data);
                }
            })
            .catch(error => console.error("Erreur de chargement des données du sommaire:", error));
    }


    /**
     * Gère le changement d'année scolaire via le sélecteur.
     */
    function handleYearChange() {
        const anneeId = this.value;
        fetch(URLS.API_CHANGER_ANNEE, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': '{{ csrf_token() }}' },
            body: JSON.stringify({ annee_id: anneeId }),
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                window.location.reload();
            } else {
                alert('Erreur lors du changement d\'année.');
            }
        })
        .catch(error => console.error('Erreur API lors du changement d\'année:', error));
    }

    if (anneeSelector) {
        anneeSelector.addEventListener('change', handleYearChange);
    }

    // Premier chargement des données
    fetchDataAndRender();
});