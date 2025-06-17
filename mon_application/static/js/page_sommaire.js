// mon_application/static/js/page_sommaire.js

document.addEventListener('DOMContentLoaded', function() {
    if (typeof PAGE_DATA === 'undefined' || !PAGE_DATA.ANNEE_ACTIVE) {
        console.log("PAGE_DATA non défini ou aucune année active, script du sommaire non exécuté.");
        return;
    }

    const { IS_ADMIN, URLS, CSRF_TOKEN } = PAGE_DATA;
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
        if (value === null || typeof value === 'undefined') return '0,00';
        return parseFloat(value).toFixed(2).replace('.', ',');
    }

    function createIcon(type, champNo, initialState) {
        const svgNS = "http://www.w3.org/2000/svg";
        const svg = document.createElementNS(svgNS, "svg");
        const path = document.createElementNS(svgNS, "path");
        svg.appendChild(path);

        svg.setAttribute('data-champ-no', champNo);
        svg.setAttribute('data-type', type);

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

        if (IS_ADMIN) {
            svg.style.cursor = 'pointer';
        }

        return svg;
    }

    function renderTable(data) {
        tableBody.innerHTML = '';
        moyenneGeneraleSpan.textContent = `${formatPeriodes(data.moyenne_generale)} périodes`;
        moyenneConfirmeeSpan.textContent = `${formatPeriodes(data.moyenne_preliminaire_confirmee)} périodes`;

        let totalPeriodesMagiquesConfirmees = 0;
        const champsTries = Object.entries(data.moyennes_par_champ).sort((a, b) => a[0].localeCompare(b[0]));

        if (champsTries.length === 0) {
            const row = tableBody.insertRow();
            const cell = row.insertCell();
            cell.colSpan = 9;
            cell.textContent = "Aucune donnée de moyenne par champ n'est disponible pour cette année.";
            cell.style.textAlign = 'center';
            cell.style.padding = '1rem';
        } else {
            champsTries.forEach(([champNo, champData]) => {
                const row = tableBody.insertRow();
                row.id = `champ-row-${champNo}`;
                row.classList.toggle('champ-verrouille-row', champData.est_verrouille);

                const diff = champData.moyenne - 24;
                const diffConfirme = champData.est_confirme ? champData.periodes_magiques : 0;
                totalPeriodesMagiquesConfirmees += diffConfirme;

                row.insertCell().textContent = champNo;

                const nomChampCell = row.insertCell();
                const champLink = document.createElement('a');
                champLink.href = URLS.URL_CHAMP_TEMPLATE.replace('__CHAMP_NO__', champNo);
                champLink.textContent = champData.champ_nom;
                nomChampCell.appendChild(champLink);

                row.insertCell().appendChild(createIcon('lock', champNo, champData.est_verrouille)).classList.add('icon-cell');
                row.insertCell().textContent = champData.nb_enseignants_tp;
                row.insertCell().textContent = formatPeriodes(champData.periodes_choisies_tp);
                row.insertCell().textContent = formatPeriodes(champData.moyenne);
                row.insertCell().textContent = formatPeriodes(diff);
                row.insertCell().appendChild(createIcon('confirm', champNo, champData.est_confirme)).classList.add('icon-cell');
                row.insertCell().textContent = formatPeriodes(diffConfirme);
            });
        }

        const grandTotals = data.grand_totals || {};
        totalEnseignantsTd.textContent = grandTotals.total_enseignants_tp || 0;
        totalPeriodesTd.textContent = formatPeriodes(grandTotals.total_periodes_choisies_tp || 0);
        totalPeriodesMagiquesConfirmeesTd.textContent = formatPeriodes(totalPeriodesMagiquesConfirmees);

        const chiffreMagique = (grandTotals.total_enseignants_tp || 0) * 0.6;
        chiffreMagiqueTd.textContent = formatPeriodes(chiffreMagique);

        const soldeFinal = totalPeriodesMagiquesConfirmees - chiffreMagique;
        soldeFinalTd.textContent = formatPeriodes(soldeFinal);
        soldeFinalTd.className = soldeFinal >= 0 ? 'solde-positif' : 'solde-negatif';
    }

    async function handleIconClick(event) {
        const icon = event.target.closest('svg[data-champ-no]');
        if (!icon || !IS_ADMIN) return;

        const champNo = icon.getAttribute('data-champ-no');
        const type = icon.getAttribute('data-type');

        let url;
        if (type === 'lock') {
            url = URLS.API_TOGGLE_LOCK_TEMPLATE.replace('__CHAMP_NO__', champNo);
        } else if (type === 'confirm') {
            url = URLS.API_TOGGLE_CONFIRM_TEMPLATE.replace('__CHAMP_NO__', champNo);
        } else {
            return;
        }

        document.body.style.cursor = 'wait';
        try {
            const response = await fetch(url, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': CSRF_TOKEN },
            });

            const result = await response.json();
            if (!response.ok) {
                throw new Error(result.message || 'Erreur inconnue de l\'API.');
            }

            await fetchDataAndRender(false); // Ne pas remontrer le spinner
            showFlashMessage(result.message, "success");

        } catch (error) {
            console.error(`Erreur lors du basculement pour le champ ${champNo}:`, error);
            showFlashMessage(error.message, "error");
        } finally {
            document.body.style.cursor = 'default';
        }
    }

    function handleYearChange() {
        const anneeId = this.value;
        document.body.style.cursor = 'wait';
        fetch(URLS.API_CHANGER_ANNEE, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': CSRF_TOKEN },
            body: JSON.stringify({ annee_id: anneeId }),
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                window.location.reload();
            } else {
                alert('Erreur lors du changement d\'année.');
                document.body.style.cursor = 'default';
            }
        })
        .catch(error => {
            console.error('Erreur API lors du changement d\'année:', error);
            document.body.style.cursor = 'default';
        });
    }

    async function fetchDataAndRender(showSpinner = true) {
        if (showSpinner) document.body.style.cursor = 'wait';
        try {
            const response = await fetch(URLS.API_GET_DONNEES_SOMMAIRE);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const data = await response.json();
            if (data) {
                renderTable(data);
            }
        } catch (error) {
            console.error("Erreur de chargement des données du sommaire:", error);
            showFlashMessage("Erreur de chargement des données du sommaire.", "error");
        } finally {
            if (showSpinner) document.body.style.cursor = 'default';
        }
    }

    // Attach event listeners
    if (anneeSelector) {
        anneeSelector.addEventListener('change', handleYearChange);
    }

    if (tableBody) {
        tableBody.addEventListener('click', handleIconClick);
    }

    // Initial data load
    fetchDataAndRender();
});

// Helper function in global scope
function showFlashMessage(message, category) {
    const existingFlash = document.querySelector('.flash-dynamic');
    if (existingFlash) {
        existingFlash.remove();
    }

    let flashContainer = document.querySelector('.flash-messages');
    if (!flashContainer) {
        flashContainer = document.createElement('ul');
        flashContainer.className = 'flash-messages';
        const mainContent = document.querySelector('main');
        if (mainContent) {
            mainContent.parentNode.insertBefore(flashContainer, mainContent);
        } else {
            document.body.prepend(flashContainer);
        }
    }

    const messageLi = document.createElement('li');
    messageLi.className = `${category} flash-dynamic`;
    messageLi.textContent = message;
    flashContainer.appendChild(messageLi);

    setTimeout(() => {
        messageLi.style.opacity = '0';
        setTimeout(() => {
            messageLi.remove();
        }, 500);
    }, 5000);
}