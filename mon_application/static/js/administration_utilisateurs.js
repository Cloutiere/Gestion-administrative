// On utilise les variables globales définies dans le template HTML.
const ALL_CHAMPS_DATA = APP_DATA.ALL_CHAMPS_DATA;
const CURRENT_USER_ID = APP_DATA.CURRENT_USER_ID;
const URLS = APP_DATA.URLS;

document.addEventListener('DOMContentLoaded', function() {
    // Gérer le formulaire de création
    const createUserForm = document.getElementById('create-user-form');
    if (createUserForm) {
        createUserForm.addEventListener('submit', handleCreateUserFormSubmit);
        document.querySelectorAll('input[name="new_user_role"]').forEach(radio => {
            radio.addEventListener('change', toggleChampSelectionVisibility);
        });
    }

    // Gérer les événements sur le tableau (via délégation)
    const usersTable = document.getElementById('users-table');
    if (usersTable) {
        usersTable.addEventListener('click', handleTableClick);
    }

    // Charger les utilisateurs initiaux
    refreshUsersTable();
});

/**
 * Affiche ou masque la section de sélection des champs en fonction du rôle choisi.
 */
function toggleChampSelectionVisibility() {
    const form = this.closest('form');
    const champSelectionDiv = form.querySelector('.champ-selection');
    champSelectionDiv.classList.toggle('hidden', this.value !== 'specific_champs');
}

/**
 * Gère la soumission du formulaire de création d'utilisateur.
 */
async function handleCreateUserFormSubmit(event) {
    event.preventDefault();
    const form = event.target;
    const messageDiv = form.querySelector('#message-create-user');
    const submitButton = form.querySelector('#btn-submit-create-user');

    const username = form.new_username.value.trim();
    const password = form.new_password.value.trim();
    const confirmPassword = form.confirm_new_password.value.trim();
    const role = form.new_user_role.value;

    if (!username || !password || !confirmPassword) return showMessage(messageDiv, 'Tous les champs sont requis.', 'error');
    if (password !== confirmPassword) return showMessage(messageDiv, 'Les mots de passe ne correspondent pas.', 'error');
    if (password.length < 6) return showMessage(messageDiv, 'Le mot de passe doit contenir au moins 6 caractères.', 'error');

    submitButton.disabled = true;
    submitButton.textContent = 'Création...';

    let allowed_champs = [];
    if (role === 'specific_champs') {
        form.querySelectorAll('.champ-selection .btn-toggle-access.active').forEach(btn => {
            allowed_champs.push(btn.dataset.champNo);
        });
    }

    try {
        const response = await fetch(URLS.API_CREATE_USER, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password, role, allowed_champs })
        });
        const data = await response.json();

        if (data.success) {
            showMessage(messageDiv, data.message, 'success');
            form.reset();
            document.getElementById('champ-selection-create').classList.remove('hidden');
            await refreshUsersTable();
        } else {
            showMessage(messageDiv, data.message, 'error');
        }
    } catch (error) {
        console.error('Erreur:', error);
        showMessage(messageDiv, 'Erreur de communication.', 'error');
    } finally {
        submitButton.disabled = false;
        submitButton.textContent = "Créer l'utilisateur";
    }
}

/**
 * Gère tous les clics sur le tableau des utilisateurs en utilisant la délégation d'événements.
 * @param {Event} event L'objet événement de clic.
 */
function handleTableClick(event) {
    const target = event.target;
    const row = target.closest('tr');
    if (!row) return;

    const userId = row.dataset.userId;

    // Clic sur un bouton de champ
    if (target.matches('.btn-toggle-access')) {
        target.classList.toggle('active');
        row.querySelector('.btn-save-access').disabled = false;
    }

    // Clic sur le bouton Sauvegarder
    if (target.matches('.btn-save-access')) {
        handleUpdateUserRole(userId, row);
    }

    // Clic sur le bouton Supprimer
    if (target.matches('.btn-delete-user')) {
        handleDeleteUser(userId, row);
    }
}

/**
 * Gère la mise à jour du rôle et des accès d'un utilisateur.
 */
async function handleUpdateUserRole(userId, row) {
    const saveButton = row.querySelector('.btn-save-access');
    const messageDiv = row.querySelector('.api-message');
    const role = row.querySelector('select[name="user_role"]').value;
    let allowed_champs = [];

    if (role === 'specific_champs') {
        row.querySelectorAll('.btn-toggle-access.active').forEach(btn => {
            allowed_champs.push(btn.dataset.champNo);
        });
    }

    saveButton.disabled = true;
    saveButton.textContent = 'Sauvegarde...';

    try {
        const response = await fetch(`/admin/api/utilisateurs/${userId}/update_role`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ role, allowed_champs })
        });
        const data = await response.json();

        if (data.success) {
            showMessage(messageDiv, data.message, 'success');
            if (parseInt(userId) === CURRENT_USER_ID) {
                setTimeout(() => window.location.reload(), 1500);
            }
        } else {
            showMessage(messageDiv, data.message, 'error');
            saveButton.disabled = false;
        }
    } catch (error) {
        console.error('Erreur:', error);
        showMessage(messageDiv, 'Erreur de communication.', 'error');
        saveButton.disabled = false;
    } finally {
        saveButton.textContent = 'Sauvegarder';
    }
}

/**
 * Gère la suppression d'un utilisateur.
 */
async function handleDeleteUser(userId, row) {
    const deleteButton = row.querySelector('.btn-delete-user');
    const username = row.querySelector('td:first-child').textContent.trim();
    const messageDiv = row.querySelector('.api-message');

    if (!confirm(`Êtes-vous sûr de vouloir supprimer l'utilisateur "${username}"?`)) return;

    deleteButton.disabled = true;

    try {
        const response = await fetch(`/admin/api/utilisateurs/${userId}/delete`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        const data = await response.json();

        if (data.success) {
            row.remove();
        } else {
            showMessage(messageDiv, data.message, 'error');
            deleteButton.disabled = false;
        }
    } catch (error) {
        console.error('Erreur:', error);
        showMessage(messageDiv, 'Erreur de communication.', 'error');
        deleteButton.disabled = false;
    }
}


/**
 * Rafraîchit complètement la table des utilisateurs depuis l'API.
 */
async function refreshUsersTable() {
    try {
        const response = await fetch(URLS.API_GET_ALL_USERS);
        if (!response.ok) throw new Error(`Erreur HTTP: ${response.status}`);
        const data = await response.json();

        const tbody = document.querySelector('#users-table tbody');
        tbody.innerHTML = '';

        data.users.forEach(user => {
            const row = document.createElement('tr');
            row.id = `user-row-${user.id}`;
            row.dataset.userId = user.id;

            // Déterminer le rôle actuel
            let userRole = 'specific_champs';
            if (user.is_admin) userRole = 'admin';
            else if (user.is_dashboard_only) userRole = 'dashboard_only';

            const isSelf = user.id === CURRENT_USER_ID;
            const isLastAdmin = user.is_admin && data.admin_count <= 1;

            // Cellule Nom d'utilisateur
            const userCell = row.insertCell();
            userCell.innerHTML = `${user.username} ${isSelf ? '<br><small>(Vous)</small>' : ''}`;

            // Cellule Rôle
            const roleCell = row.insertCell();
            // Les utilisateurs ne peuvent pas modifier leur propre rôle ou celui du dernier admin
            if (isSelf || isLastAdmin) {
                const roleName = {
                    'admin': 'Administrateur',
                    'dashboard_only': 'Tableau de Bord',
                    'specific_champs': 'Spécifique'
                } [userRole];
                roleCell.innerHTML = `<span>${roleName}</span>`;
            } else {
                roleCell.innerHTML = `
                    <select name="user_role" onchange="document.querySelector('#user-row-${user.id} .btn-save-access').disabled=false;">
                        <option value="specific_champs" ${userRole === 'specific_champs' ? 'selected' : ''}>Spécifique</option>
                        <option value="dashboard_only" ${userRole === 'dashboard_only' ? 'selected' : ''}>Tableau de Bord</option>
                        <option value="admin" ${userRole === 'admin' ? 'selected' : ''}>Administrateur</option>
                    </select>`;
            }

            // Cellule Accès / Actions
            const accessCell = row.insertCell();
            const isHidden = userRole !== 'specific_champs' ? 'hidden' : '';
            let champButtonsHtml = `<div class="champ-selection ${isHidden}">`;
            champButtonsHtml += ALL_CHAMPS_DATA.map(champ => {
                const isActive = user.allowed_champs.includes(champ.champno) ? 'active' : '';
                return `<button type="button" class="btn btn-toggle-access ${isActive}" data-champ-no="${champ.champno}" title="${champ.champnom}">${champ.champno}</button>`;
            }).join('');
            champButtonsHtml += `</div><div class="api-message"></div>`;
            accessCell.innerHTML = champButtonsHtml;

            // Cellule Actions (Boutons)
            const actionCell = row.insertCell();
            if (!isSelf) {
                const saveDisabled = isLastAdmin ? 'disabled' : 'disabled';
                const deleteDisabled = isLastAdmin ? 'disabled title="Impossible de supprimer le dernier admin."' : '';
                actionCell.innerHTML = `
                    <button class="btn btn-save-access" data-user-id="${user.id}" ${saveDisabled}>Sauvegarder</button>
                    <button class="btn btn-delete-user" data-user-id="${user.id}" ${deleteDisabled}>Supprimer</button>
                `;
            }
            tbody.appendChild(row);
        });

    } catch (error) {
        console.error('Erreur lors du rafraîchissement du tableau:', error);
    }
}

/**
 * Affiche un message dans un élément DOM spécifié.
 */
function showMessage(element, msg, type) {
    if (!element) return;
    element.textContent = msg;
    element.className = 'api-message ' + type;
    element.style.display = 'block';
    setTimeout(() => {
        if (element) {
           element.style.display = 'none';
           element.textContent = '';
        }
    }, 5000);
}