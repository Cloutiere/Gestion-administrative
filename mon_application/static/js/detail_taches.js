// On utilise les variables et URLs globales définies dans le template HTML.
const INTERVAL_MISE_A_JOUR = 7000;
const ANNEE_ACTIVE = PAGE_DATA.ANNEE_ACTIVE;
const URLS = PAGE_DATA.URLS;

// --- Fonctions utilitaires ---
function formatPeriodes(value) {
    if (value === null || value === undefined) return '';
    const formatter = new Intl.NumberFormat('fr-CA', { minimumFractionDigits: 0, maximumFractionDigits: 2, useGrouping: false, signDisplay: 'auto' });
    return formatter.format(value);
}

document.addEventListener('DOMContentLoaded', function() {
    if (ANNEE_ACTIVE) {
        mettreAJourDonneesDetail();
        setInterval(mettreAJourDonneesDetail, INTERVAL_MISE_A_JOUR);
    }

    const anneeSelector = document.getElementById('annee-selector');
    if (anneeSelector) {
        anneeSelector.addEventListener('change', function() {
            const anneeId = this.value;
            fetch(URLS.API_CHANGER_ANNEE, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ annee_id: parseInt(anneeId, 10) })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    window.location.reload();
                } else {
                    alert("Erreur lors du changement d'année de visualisation.");
                }
            });
        });
    }
});

// --- Fonctions de mise à jour de l'interface ---
async function mettreAJourDonneesDetail() {
    try {
        const response = await fetch(URLS.API_GET_DONNEES_SOMMAIRE);
        if (!response.ok) {
            if (response.status === 401 || response.status === 403) { window.location.reload(); return; }
            throw new Error(`Erreur HTTP: ${response.status}`);
        }
        const data = await response.json();
        mettreAJourTableauEnseignantsGroupes(data.enseignants_par_champ || []);
    } catch (error) {
        console.error("Erreur lors de la mise à jour des détails:", error);
    }
}

function mettreAJourTableauEnseignantsGroupes(enseignantsParChampData) {
    const tbody = document.querySelector('#table-detail-enseignants tbody');
    const aucunEnseignantMsg = document.getElementById('aucun-enseignant-message');
    const table = document.getElementById('table-detail-enseignants');
    if (!tbody || !aucunEnseignantMsg || !table) return;

    tbody.innerHTML = '';
    const aDesEnseignants = enseignantsParChampData.some(c => c.enseignants && c.enseignants.length > 0);

    aucunEnseignantMsg.style.display = aDesEnseignants ? 'none' : 'block';
    table.style.display = aDesEnseignants ? '' : 'none';

    if (aDesEnseignants) {
        enseignantsParChampData.forEach(champData => {
            if (!champData.enseignants || champData.enseignants.length === 0) return;

            const champHeaderRow = tbody.insertRow();
            champHeaderRow.className = 'champ-header-row';
            const champTitleCell = champHeaderRow.insertCell();
            champTitleCell.colSpan = 5;
            champTitleCell.className = 'champ-title-cell';
            champTitleCell.textContent = `Champ ${champData.champno} - ${champData.champnom}`;

            const columnHeaderRow = tbody.insertRow();
            columnHeaderRow.className = 'column-header-row';
            ['Nom', 'Pér. cours', 'Pér. autres', 'Total pér.', 'Compte moyenne'].forEach(headerText => {
                const th = document.createElement('th');
                th.textContent = headerText;
                columnHeaderRow.appendChild(th);
            });

            champData.enseignants.forEach(ens => {
                const row = tbody.insertRow();
                row.dataset.enseignantId = ens.enseignantid;
                row.insertCell().textContent = (ens.nom && ens.prenom) ? `${ens.nom}, ${ens.prenom}` : ens.nomcomplet;
                row.insertCell().textContent = formatPeriodes(ens.periodes_cours);
                row.insertCell().textContent = formatPeriodes(ens.periodes_autres);
                row.insertCell().textContent = formatPeriodes(ens.total_periodes);
                const cellCompteMoyenne = row.insertCell();
                if (ens.compte_pour_moyenne_champ) {
                    cellCompteMoyenne.textContent = 'Oui';
                } else {
                    let nonCompteText = 'Non';
                    if (ens.estfictif) nonCompteText += ' (Tâche restante)';
                    else if (!ens.esttempsplein) nonCompteText += ' (T. Partiel)';
                    cellCompteMoyenne.innerHTML = `<span class="statut-non-compte">${nonCompteText}</span>`;
                }
            });
        });
    }
}