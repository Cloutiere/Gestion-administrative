// On utilise les variables et URLs globales définies dans le template HTML via l'objet PAGE_DATA.
const INTERVAL_MISE_A_JOUR = 7000;
const IS_ADMIN = PAGE_DATA.IS_ADMIN;
const ANNEE_ACTIVE = PAGE_DATA.ANNEE_ACTIVE;
const URLS = PAGE_DATA.URLS;

// --- Fonctions utilitaires et constantes SVG ---
function formatPeriodes(value) {
    if (value === null || value === undefined) return '';
    const formatter = new Intl.NumberFormat('fr-CA', { minimumFractionDigits: 0, maximumFractionDigits: 2, useGrouping: false, signDisplay: 'auto' });
    return formatter.format(value);
}

const SVG_LOCKED = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M18 8h-1V6c0-2.76-2.24-5-5-5S7 3.24 7 6v2H6c-1.1 0-2 .9-2 2v10c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V10c0-1.1-.9-2-2-2zM9 6c0-1.66 1.34-3 3-3s3 1.34 3 3v2H9V6zm9 14H6V10h12v10zm-6-3c1.1 0 2-.9 2-2s-.9-2-2-2-2 .9-2 2 .9 2 2 2z"/></svg>`;
const SVG_UNLOCKED = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M18 8h-1V6c0-2.76-2.24-5-5-5S7 3.24 7 6h2c0-1.66 1.34-3 3-3s3 1.34 3 3v2H6c-1.1 0-2 .9-2 2v10c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V10c0-1.1-.9-2-2-2zm0 12H6V10h12v10zm-6-3c1.1 0 2-.9 2-2s-.9-2-2-2-2 .9-2 2 .9 2 2 2z"/></svg>`;
const SVG_CONFIRMED = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M9 16.17 4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41L9 16.17z"/></svg>`;
const SVG_UNCONFIRMED = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M9 16.17 4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41L9 16.17z" opacity="0.3"/></svg>`;

document.addEventListener('DOMContentLoaded', function() {
    if (ANNEE_ACTIVE) {
        mettreAJourDonneesSommaire();
        setInterval(mettreAJourDonneesSommaire, INTERVAL_MISE_A_JOUR);

        const tableMoyennes = document.getElementById('table-moyennes-par-champ');
        if (tableMoyennes) {
            tableMoyennes.addEventListener('click', function(event) {
                const icon = event.target.closest('.lock-icon, .confirm-icon');
                if (!icon || !IS_ADMIN) return;

                if (icon.classList.contains('lock-icon')) {
                    basculerVerrouChamp(icon.dataset.champNo, icon);
                } else if (icon.classList.contains('confirm-icon')) {
                    basculerConfirmationChamp(icon.dataset.champNo, icon);
                }
            });
        }
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

async function mettreAJourDonneesSommaire() {
    try {
        const response = await fetch(URLS.API_GET_DONNEES_SOMMAIRE);
        if (!response.ok) {
            if (response.status === 401 || response.status === 403) { window.location.reload(); return; }
            throw new Error(`Erreur HTTP: ${response.status}`);
        }
        const data = await response.json();

        const totalConfirme = mettreAJourTableauMoyennesChamp(data.moyennes_par_champ || {});

        if (data.grand_totals) {
            mettreAJourTotaux(data.grand_totals, totalConfirme);
        }

        const elMoyenneGenerale = document.getElementById('moyenne-generale-etablissement');
        if (elMoyenneGenerale) {
            elMoyenneGenerale.textContent = (data.moyenne_generale !== undefined && data.moyenne_generale !== null)
                ? `${formatPeriodes(data.moyenne_generale)} périodes`
                : `N/A périodes`;
        }
        const elMoyennePrelim = document.getElementById('moyenne-preliminaire-confirmee');
        if (elMoyennePrelim) {
            elMoyennePrelim.textContent = (data.moyenne_preliminaire_confirmee !== undefined && data.moyenne_preliminaire_confirmee !== null)
                ? `${formatPeriodes(data.moyenne_preliminaire_confirmee)} périodes`
                : `N/A périodes`;
        }
    } catch (error) {
        console.error("Erreur lors de la mise à jour du sommaire:", error);
    }
}

function mettreAJourTotaux(totals, totalConfirme) {
    document.getElementById('total-enseignants-tp').textContent = totals.total_enseignants_tp;
    document.getElementById('total-periodes-choisies-tp').textContent = formatPeriodes(totals.total_periodes_choisies_tp);
    document.getElementById('total-periodes-confirmees-magiques').textContent = formatPeriodes(totalConfirme);

    const chiffreMagique = (totals.total_enseignants_tp || 0) * 0.6;
    document.getElementById('valeur-chiffre-magique').textContent = formatPeriodes(chiffreMagique);

    const soldeFinal = totalConfirme - chiffreMagique;
    const soldeCell = document.getElementById('valeur-solde-final');
    soldeCell.textContent = formatPeriodes(soldeFinal);

    soldeCell.classList.remove('solde-positif', 'solde-negatif');
    if (soldeFinal < 0) {
        soldeCell.classList.add('solde-negatif');
    } else if (soldeFinal > 0) {
        soldeCell.classList.add('solde-positif');
    }
}

async function basculerVerrouChamp(champNo, iconElement) {
    iconElement.style.opacity = '0.5';
    try {
        const response = await fetch(`/admin/api/champs/${champNo}/basculer_verrou`, { method: 'POST' });
        const data = await response.json();
        if (!response.ok || !data.success) throw new Error(data.message || 'Erreur lors du changement de statut du verrou.');
        await mettreAJourDonneesSommaire();
    } catch (error) {
        console.error(`Erreur bascule verrou pour champ ${champNo}:`, error);
        alert(error.message);
    } finally {
        iconElement.style.opacity = '1';
    }
}

async function basculerConfirmationChamp(champNo, iconElement) {
    iconElement.style.opacity = '0.5';
    try {
        const response = await fetch(`/admin/api/champs/${champNo}/basculer_confirmation`, { method: 'POST' });
        const data = await response.json();
        if (!response.ok || !data.success) throw new Error(data.message || 'Erreur lors du changement de statut de confirmation.');
        await mettreAJourDonneesSommaire();
    } catch (error) {
        console.error(`Erreur bascule confirmation pour champ ${champNo}:`, error);
        alert(error.message);
    } finally {
        iconElement.style.opacity = '1';
    }
}

function mettreAJourIconeVerrou(iconElement, estVerrouille) {
    iconElement.innerHTML = estVerrouille ? SVG_LOCKED : SVG_UNLOCKED;
    iconElement.title = estVerrouille ? 'Champ verrouillé' : 'Champ déverrouillé';
    if(IS_ADMIN) {
        iconElement.classList.add('admin-only');
        iconElement.title += '. Cliquer pour modifier.';
    }
}

function mettreAJourIconeConfirmation(iconElement, estConfirme) {
    iconElement.className = estConfirme ? 'confirm-icon confirmed' : 'confirm-icon unconfirmed';
    iconElement.innerHTML = estConfirme ? SVG_CONFIRMED : SVG_UNCONFIRMED;
    iconElement.title = estConfirme ? 'Champ confirmé' : 'Champ non confirmé';
    if (IS_ADMIN) {
        iconElement.classList.add('admin-only');
        iconElement.title += '. Cliquer pour modifier.';
    }
}

function comparerNumerosChamp(a, b) {
    const regex = /^(\d+)([a-zA-Z]*)$/;
    const matchA = a.match(regex);
    const matchB = b.match(regex);
    if (matchA && matchB) {
        const numA = parseInt(matchA[1], 10);
        const letterA = matchA[2] || '';
        const numB = parseInt(matchB[1], 10);
        const letterB = matchB[2] || '';
        if (numA !== numB) return numA - numB;
        return letterA.localeCompare(letterB);
    }
    return a.localeCompare(b);
}

function mettreAJourTableauMoyennesChamp(moyennesChampData) {
    const tbody = document.querySelector('#table-moyennes-par-champ tbody');
    const aucuneMoyenneMsg = document.getElementById('aucune-moyenne-champ-message');
    const table = document.getElementById('table-moyennes-par-champ');
    if (!tbody || !aucuneMoyenneMsg || !table) return 0;

    tbody.innerHTML = '';
    const champNosTries = Object.keys(moyennesChampData).sort(comparerNumerosChamp);

    const hasData = champNosTries.length > 0;
    aucuneMoyenneMsg.style.display = hasData ? 'none' : 'block';
    table.style.display = hasData ? '' : 'none';

    let totalPeriodesMagiquesConfirmees = 0.0;

    if (hasData) {
        champNosTries.forEach(champ_no => {
            const data = moyennesChampData[champ_no];
            const row = tbody.insertRow();
            row.dataset.champNo = champ_no;

            if (data.est_verrouille) row.classList.add('champ-verrouille-row');
            if (data.est_confirme) row.classList.add('champ-confirme');

            row.insertCell().textContent = champ_no;

            const cellNomChamp = row.insertCell();
            const link = document.createElement('a');
            link.href = `/champ/${encodeURIComponent(champ_no)}`;
            link.textContent = data.champ_nom;
            cellNomChamp.appendChild(link);

            const cellStatut = row.insertCell();
            const lockIcon = document.createElement('span');
            lockIcon.className = 'lock-icon';
            lockIcon.dataset.champNo = champ_no;
            mettreAJourIconeVerrou(lockIcon, data.est_verrouille);
            cellStatut.appendChild(lockIcon);

            row.insertCell().textContent = data.nb_enseignants_tp;
            row.insertCell().textContent = formatPeriodes(data.periodes_choisies_tp);
            row.insertCell().textContent = formatPeriodes(data.moyenne);
            row.insertCell().textContent = formatPeriodes(data.periodes_magiques);

            const cellConfirme = row.insertCell();
            const confirmIcon = document.createElement('span');
            confirmIcon.className = 'confirm-icon';
            confirmIcon.dataset.champNo = champ_no;
            mettreAJourIconeConfirmation(confirmIcon, data.est_confirme);
            cellConfirme.appendChild(confirmIcon);

            const cellDiffConfirme = row.insertCell();
            if (data.est_confirme) {
                cellDiffConfirme.textContent = formatPeriodes(data.periodes_magiques);
                totalPeriodesMagiquesConfirmees += data.periodes_magiques;
            } else {
                cellDiffConfirme.textContent = '';
            }
        });
    }
    return totalPeriodesMagiquesConfirmees;
}