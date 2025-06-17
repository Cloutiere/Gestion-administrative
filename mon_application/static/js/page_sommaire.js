// mon_application/static/js/page_sommaire.js

document.addEventListener('DOMContentLoaded', function() {
    if (typeof PAGE_DATA === 'undefined' || !PAGE_DATA.ANNEE_ACTIVE) {
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

    function formatPeriodes(value) {
        return parseFloat(value).toFixed(2).replace('.', ',');
    }

    function createIcon(type, champNo, initialState) {
        const svgNS = "http://www.w3.org/2000/svg";
        const svg = document.createElementNS(svgNS, "svg");
        svg.setAttribute("viewBox", "0 0 24 24");
        const path = document.createElementNS(svgNS, "path");
        svg.appendChild(path);

        if (type === 'lock') {
            svg.classList.add('lock-icon');
            path.setAttribute("d", "M12 17c1.1 0 2-.9 2-2s-.9-2-2-2-2 .9-2 2 .9 2 2 2zm6-9h-1V6c0-2.76-2.24-5-5-5S7 3.24 7 6v2H6c-1.1 0-2 .9-2 2v10c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V10c0-1.1-.9-2-2-2zM8.9 6c0-1.71 1.39-3.1 3.1-3.1s3.1 1.39 3.1 3.1v2H8.9V6z");
            svg.classList.toggle('locked', initialState);
        } else { // confirm
            svg.classList.add('confirm-icon');
            path.setAttribute("d", "M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z");
            svg.classList.toggle('confirmed', initialState);
            svg.classList.toggle('unconfirmed', !initialState);
        }

        if (IS_ADMIN) {
            svg.classList.add('admin-only');
            svg.dataset.champNo = champNo;
            svg.dataset.type = type;
        }
        return svg;
    }

    function renderTable(data) {
        tableBody.innerHTML = '';
        moyenneGeneraleSpan.textContent = `${formatPeriodes(data.moyenne_generale)} périodes`;
        moyenneConfirmeeSpan.textContent = `${formatPeriodes(data.moyenne_preliminaire_confirmee)} périodes`;

        let totalPeriodesMagiquesConfirmees = 0;
        const champsTries = Object.entries(data.moyennes_par_champ).sort((a, b) => a[0].localeCompare(b[0]));

        champsTries.forEach(([champNo, champData]) => {
            const row = tableBody.insertRow();
            row.id = `champ-row-${champNo}`;
            if (champData.est_confirme) {
                row.classList.add('champ-confirme');
            }

            const diff = champData.moyenne - 24;
            const periodesMagiquesConfirmees = champData.est_confirme ? champData.periodes_magiques : 0;
            totalPeriodesMagiquesConfirmees += periodesMagiquesConfirmees;

            row.insertCell().textContent = champNo;
            row.insertCell().textContent = champData.champ_nom;
            row.insertCell().appendChild(createIcon('lock', champNo, champData.est_verrouille));
            row.insertCell().textContent = champData.nb_enseignants_tp;
            row.insertCell().textContent = formatPeriodes(champData.periodes_choisies_tp);
            row.insertCell().textContent = formatPeriodes(champData.moyenne);
            row.insertCell().textContent = formatPeriodes(diff);
            row.insertCell().appendChild(createIcon('confirm', champNo, champData.est_confirme));
            row.insertCell().textContent = formatPeriodes(periodesMagiquesConfirmees);
        });

        // Update footer
        totalEnseignantsTd.textContent = data.grand_totals.total_enseignants_tp;
        totalPeriodesTd.textContent = formatPeriodes(data.grand_totals.total_periodes_choisies_tp);
        totalPeriodesMagiquesConfirmeesTd.textContent = formatPeriodes(totalPeriodesMagiquesConfirmees);

        const chiffreMagique = data.grand_totals.total_enseignants_tp * 0.6;
        chiffreMagiqueTd.textContent = formatPeriodes(chiffreMagique);

        const soldeFinal = totalPeriodesMagiquesConfirmees - chiffreMagique;
        soldeFinalTd.textContent = formatPeriodes(soldeFinal);
        soldeFinalTd.className = soldeFinal >= 0 ? 'solde-positif' : 'solde-negatif';
    }


    function fetchDataAndRender() {
        fetch(URLS.API_GET_DONNEES_SOMMAIRE)
            .then(response => response.json())
            .then(data => {
                if (data) {
                    renderTable(data);
                }
            })
            .catch(error => console.error("Erreur de chargement des données du sommaire:", error));
    }


    function handleYearChange() {
        fetch(URLS.API_CHANGER_ANNEE, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ annee_id: this.value }),
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) window.location.reload();
            else alert('Erreur lors du changement d\'année.');
        })
        .catch(error => console.error('Erreur API:', error));
    }

    if (anneeSelector) {
        anneeSelector.addEventListener('change', handleYearChange);
    }

    // Premier chargement des données
    fetchDataAndRender();
});