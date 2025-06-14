// On utilise les URLs globales définies dans le template HTML.
document.addEventListener('DOMContentLoaded', function() {
    // --- Constantes et variables globales du script ---
    const apiMessageContainer = document.getElementById('api-message-container');

    // --- Gestion des messages API globaux ---
    function displayApiMessage(message, type) {
        if (!apiMessageContainer) return;
        apiMessageContainer.textContent = message;
        apiMessageContainer.className = 'api-message'; // Réinitialise les classes
        apiMessageContainer.classList.add(`message-${type}`);
        apiMessageContainer.style.display = 'block';
        setTimeout(() => { apiMessageContainer.style.display = 'none'; }, 7000);
    }

    // --- Logique des Modales (générique) ---
    function openModal(modalBackdrop) { modalBackdrop.classList.add('visible'); }
    function closeModal(modalBackdrop) { modalBackdrop.classList.remove('visible'); }

    document.querySelectorAll('.modal-backdrop').forEach(backdrop => {
        backdrop.addEventListener('click', (e) => {
            if (e.target === backdrop) closeModal(backdrop);
        });
        backdrop.querySelector('.modal-close-btn').addEventListener('click', () => closeModal(backdrop));
        backdrop.querySelector('.modal-cancel-btn').addEventListener('click', () => closeModal(backdrop));
    });

    // --- Logique de l'accordéon (générique) ---
    document.querySelectorAll('.collapsible-header').forEach(header => {
        header.addEventListener('click', () => {
            const content = document.querySelector(header.dataset.target);
            header.classList.toggle('active');
            content.style.display = content.style.display === 'block' ? 'none' : 'block';
        });
    });

    // --- Logique de gestion des années scolaires ---
    const gestionAnneesContainer = document.getElementById('gestion-annees-container');
    if (gestionAnneesContainer) {
        const formCreerAnnee = document.getElementById('form-creer-annee');
        formCreerAnnee.addEventListener('submit', async (e) => {
            e.preventDefault();
            const input = document.getElementById('input-libelle-annee');
            const libelle = input.value.trim();
            if (!libelle) return;

            const response = await fetch(PAGE_URLS.creerAnnee, {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ libelle: libelle })
            });
            const data = await response.json();
            if (data.success) {
                location.reload();
            } else {
                displayApiMessage(data.message, 'error');
            }
        });

        gestionAnneesContainer.addEventListener('click', async (e) => {
            let url = '';
            let anneeId = null;

            if (e.target.classList.contains('btn-select-annee')) {
                anneeId = e.target.dataset.anneeId;
                url = PAGE_URLS.changerAnneeActive;
            } else if (e.target.classList.contains('btn-set-courante')) {
                anneeId = e.target.dataset.anneeId;
                url = PAGE_URLS.setAnneeCourante;
            }

            if (url && anneeId) {
                const response = await fetch(url, {
                    method: 'POST', headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ annee_id: parseInt(anneeId) })
                });
                const data = await response.json();
                if (data.success) {
                    location.reload();
                } else {
                    displayApiMessage(data.message, 'error');
                }
            }
        });
    }

    // --- FONCTIONS DE MISE À JOUR DE L'UI ---
    function updateCourseRowUI(cours) {
        const sanitizedId = cours.codecours.replace(/\./g, '-').replace(/\//g, '-');
        const row = document.getElementById(`cours-row-${sanitizedId}`);
        if (!row) return;

        row.cells[0].textContent = cours.codecours;
        row.cells[1].textContent = cours.coursdescriptif;
        row.cells[2].textContent = parseFloat(cours.nbperiodes).toFixed(2);
        row.cells[3].textContent = cours.nbgroupeinitial;
        row.cells[4].textContent = cours.estcoursautre ? 'Oui' : 'Non';
        row.cells[5].textContent = cours.financement_code || 'N/A';
        row.dataset.champno = cours.champno;
    }

    function updateTeacherRowUI(enseignant) {
        const row = document.getElementById(`enseignant-row-${enseignant.enseignantid}`);
        if (!row) return;

        row.cells[0].textContent = enseignant.nomcomplet;
        row.cells[1].textContent = enseignant.esttempsplein ? 'Temps plein' : 'Temps partiel';
        row.dataset.champno = enseignant.champno;
    }

    // --- Logique CRUD pour les TYPES DE FINANCEMENT ---
    const financementContainer = document.getElementById('financements-table-container');
    const financementModal = document.getElementById('financement-modal-backdrop');
    const financementForm = document.getElementById('financement-form');

    if (financementContainer && financementModal && financementForm) {
        const financementModalTitle = document.getElementById('financement-modal-title');
        const btnOpenAddFinancementModal = document.getElementById('btn-open-add-financement-modal');
        const codeInput = document.getElementById('form-financement-code');

        btnOpenAddFinancementModal.addEventListener('click', () => {
            financementForm.reset();
            financementModalTitle.textContent = 'Ajouter un Type de Financement';
            codeInput.readOnly = false;
            openModal(financementModal);
        });

        financementContainer.addEventListener('click', (e) => {
            if (e.target.classList.contains('btn-edit-financement')) {
                financementForm.reset();
                const code = e.target.dataset.code;
                const libelle = e.target.dataset.libelle;
                financementModalTitle.textContent = `Modifier: ${libelle}`;
                codeInput.value = code;
                codeInput.readOnly = true; // Empêcher la modification du code
                document.getElementById('form-financement-libelle').value = libelle;
                openModal(financementModal);
            }
            if (e.target.classList.contains('btn-delete-financement')) {
                const code = e.target.dataset.code;
                if (confirm(`Supprimer le type de financement "${code}" ?\nLes cours associés auront leur financement retiré.`)) {
                     fetch(`/admin/api/financements/${encodeURIComponent(code)}/supprimer`, { method: 'POST' })
                        .then(res => res.json())
                        .then(data => {
                            if (data.success) {
                                location.reload();
                            } else {
                                displayApiMessage(data.message, 'error');
                            }
                        });
                }
            }
        });

        financementForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const formData = new FormData(financementForm);
            const data = Object.fromEntries(formData.entries());
            const isEditMode = document.getElementById('form-financement-code').readOnly;
            const code = document.getElementById('form-financement-code').value;

            let url;
            let payload;

            if (isEditMode) {
                url = `/admin/api/financements/${encodeURIComponent(code)}/modifier`;
                payload = { libelle: data.libelle };
            } else {
                url = PAGE_URLS.createFinancement;
                payload = { code: data.code, libelle: data.libelle };
            }

            const response = await fetch(url, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });
            const result = await response.json();
            if (result.success) {
                location.reload();
            } else {
                alert(`Erreur: ${result.message}`);
            }
        });
    }


    // --- Logique CRUD pour les COURS ---
    const coursAccordionContainer = document.getElementById('cours-accordion-container');
    const coursModal = document.getElementById('cours-modal-backdrop');
    const coursForm = document.getElementById('cours-form');
    if (coursAccordionContainer && coursModal && coursForm) {
        const coursModalTitle = document.getElementById('cours-modal-title');
        const btnOpenAddCoursModal = document.getElementById('btn-open-add-cours-modal');
        const chkEstCoursAutre = document.getElementById('form-estcoursautre');
        const financementSelect = document.getElementById('form-financement_code');

        btnOpenAddCoursModal.addEventListener('click', () => {
            coursForm.reset();
            coursModalTitle.textContent = 'Ajouter un nouveau cours';
            coursForm.querySelector('#cours-mode').value = 'add';
            coursForm.querySelector('#original-codecours').value = '';
            coursForm.querySelector('#original-champno-cours').value = '';
            coursForm.querySelector('#form-codecours').readOnly = false;
            chkEstCoursAutre.checked = false;
            financementSelect.value = '';
            openModal(coursModal);
        });

        coursAccordionContainer.addEventListener('click', async (e) => {
            if (e.target.classList.contains('btn-edit-cours')) {
                const codeCours = e.target.dataset.codecours;
                const response = await fetch(`/admin/api/cours/${encodeURIComponent(codeCours)}`);
                const data = await response.json();

                if (data.success) {
                    const cours = data.cours;
                    coursForm.reset();
                    coursModalTitle.textContent = `Modifier le cours : ${cours.codecours}`;
                    coursForm.querySelector('#cours-mode').value = 'edit';
                    coursForm.querySelector('#original-codecours').value = cours.codecours;
                    coursForm.querySelector('#original-champno-cours').value = cours.champno;
                    coursForm.querySelector('#form-codecours').value = cours.codecours;
                    coursForm.querySelector('#form-codecours').readOnly = true;
                    coursForm.querySelector('#form-coursdescriptif').value = cours.coursdescriptif;
                    coursForm.querySelector('#form-champno-cours').value = cours.champno;
                    coursForm.querySelector('#form-nbperiodes').value = cours.nbperiodes;
                    coursForm.querySelector('#form-nbgroupeinitial').value = cours.nbgroupeinitial;
                    chkEstCoursAutre.checked = cours.estcoursautre;
                    financementSelect.value = cours.financement_code || '';
                    openModal(coursModal);
                } else { displayApiMessage(data.message, 'error'); }
            }
            if (e.target.classList.contains('btn-delete-cours')) {
                const codeCours = e.target.dataset.codecours;
                if (confirm(`Êtes-vous sûr de vouloir supprimer le cours "${codeCours}" ?`)) {
                    const response = await fetch(`/admin/api/cours/${encodeURIComponent(codeCours)}/supprimer`, { method: 'POST' });
                    const data = await response.json();
                    if (data.success) {
                        const sanitizedId = codeCours.replace(/\./g, '-').replace(/\//g, '-');
                        document.getElementById(`cours-row-${sanitizedId}`)?.remove();
                        displayApiMessage(data.message, 'success');
                    } else { displayApiMessage(data.message, 'error'); }
                }
            }
        });

        coursForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const formData = new FormData(coursForm);
            const data = Object.fromEntries(formData.entries());

            data.nbperiodes = parseFloat(data.nbperiodes);
            data.nbgroupeinitial = parseInt(data.nbgroupeinitial, 10);
            data.estcoursautre = document.getElementById('form-estcoursautre').checked;

            const mode = coursForm.querySelector('#cours-mode').value;
            const originalCodeCours = coursForm.querySelector('#original-codecours').value;
            const originalChampNo = coursForm.querySelector('#original-champno-cours').value;

            let url = (mode === 'add') ? PAGE_URLS.createCours : `/admin/api/cours/${encodeURIComponent(originalCodeCours)}/modifier`;

            const response = await fetch(url, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data),
            });
            const result = await response.json();

            if (result.success) {
                closeModal(coursModal);
                displayApiMessage(result.message, 'success');
                if (mode === 'edit' && result.cours.champno !== originalChampNo) {
                    location.reload();
                } else if (mode === 'edit') {
                    updateCourseRowUI(result.cours);
                } else {
                    location.reload();
                }
            } else {
                alert(`Erreur: ${result.message}`);
            }
        });
    }


    // --- Logique CRUD pour les ENSEIGNANTS ---
    const enseignantsAccordionContainer = document.getElementById('enseignants-accordion-container');
    const enseignantModal = document.getElementById('enseignant-modal-backdrop');
    const enseignantForm = document.getElementById('enseignant-form');
    if (enseignantsAccordionContainer && enseignantModal && enseignantForm) {
        const enseignantModalTitle = document.getElementById('enseignant-modal-title');
        const btnOpenAddEnseignantModal = document.getElementById('btn-open-add-enseignant-modal');

        btnOpenAddEnseignantModal.addEventListener('click', () => {
            enseignantForm.reset();
            enseignantModalTitle.textContent = 'Ajouter un nouvel enseignant';
            enseignantForm.querySelector('#enseignant-mode').value = 'add';
            enseignantForm.querySelector('#enseignant-id').value = '';
            enseignantForm.querySelector('#original-champno-enseignant').value = '';
            openModal(enseignantModal);
        });

        enseignantsAccordionContainer.addEventListener('click', async (e) => {
            if (e.target.classList.contains('btn-edit-enseignant')) {
                const enseignantId = e.target.dataset.enseignantid;
                const response = await fetch(`/admin/api/enseignants/${enseignantId}`);
                const data = await response.json();
                if (data.success) {
                    const enseignant = data.enseignant;
                    enseignantForm.reset();
                    enseignantModalTitle.textContent = `Modifier: ${enseignant.nomcomplet}`;
                    enseignantForm.querySelector('#enseignant-mode').value = 'edit';
                    enseignantForm.querySelector('#enseignant-id').value = enseignant.enseignantid;
                    enseignantForm.querySelector('#original-champno-enseignant').value = enseignant.champno;
                    enseignantForm.querySelector('#form-nom').value = enseignant.nom;
                    enseignantForm.querySelector('#form-prenom').value = enseignant.prenom;
                    enseignantForm.querySelector('#form-champno-enseignant').value = enseignant.champno;
                    enseignantForm.querySelector('#form-esttempsplein').checked = enseignant.esttempsplein;
                    openModal(enseignantModal);
                } else { displayApiMessage(data.message, 'error'); }
            }
            if (e.target.classList.contains('btn-delete-enseignant')) {
                const enseignantId = e.target.dataset.enseignantid;
                if (confirm(`Êtes-vous sûr de vouloir supprimer cet enseignant ?`)) {
                    const response = await fetch(`/admin/api/enseignants/${enseignantId}/supprimer`, { method: 'POST' });
                    const data = await response.json();
                     if (data.success) {
                        document.getElementById(`enseignant-row-${enseignantId}`)?.remove();
                        displayApiMessage(data.message, 'success');
                    } else { displayApiMessage(data.message, 'error'); }
                }
            }
        });

        enseignantForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const formData = new FormData(enseignantForm);
            const data = Object.fromEntries(formData.entries());
            data.esttempsplein = enseignantForm.querySelector('#form-esttempsplein').checked;
            const mode = enseignantForm.querySelector('#enseignant-mode').value;
            const enseignantId = enseignantForm.querySelector('#enseignant-id').value;
            const originalChampNo = enseignantForm.querySelector('#original-champno-enseignant').value;

            let url = (mode === 'add') ? PAGE_URLS.createEnseignant : `/admin/api/enseignants/${enseignantId}/modifier`;

            const response = await fetch(url, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data),
            });
            const result = await response.json();

            if (result.success) {
                closeModal(enseignantModal);
                displayApiMessage(result.message, 'success');
                if (mode === 'edit' && result.enseignant.champno !== originalChampNo) {
                    location.reload();
                } else if (mode === 'edit') {
                    updateTeacherRowUI(result.enseignant);
                } else {
                    location.reload();
                }
            } else {
                alert(`Erreur: ${result.message}`);
            }
        });
    }


    // --- Logique de réassignation ---
    if (coursAccordionContainer) {
        coursAccordionContainer.addEventListener('click', function(e) {
            const button = e.target;
            let payload = {};
            let url = '';
            let successCallback = () => location.reload();

            if (button.classList.contains('btn-reassigner')) {
                const codeCours = button.dataset.codecours;
                const sanitizedId = codeCours.replace(/\./g, '-').replace(/\//g, '-');
                const selectElement = document.getElementById(`select-champ-${sanitizedId}`);
                const nouveauChampNo = selectElement.value;

                if (!nouveauChampNo) {
                    displayApiMessage('Veuillez sélectionner un champ de destination.', 'error');
                    return;
                }
                if (!confirm(`Réassigner le cours "${codeCours}" au champ ${nouveauChampNo} ?`)) return;

                url = PAGE_URLS.reassignerCoursChamp;
                payload = { code_cours: codeCours, nouveau_champ_no: nouveauChampNo };

            } else if (button.classList.contains('btn-reassigner-financement')) {
                const codeCours = button.dataset.codecours;
                const sanitizedId = codeCours.replace(/\./g, '-').replace(/\//g, '-');
                const selectElement = document.getElementById(`select-financement-${sanitizedId}`);
                const nouveauFinancementCode = selectElement.value;

                if (!confirm(`Modifier le financement du cours "${codeCours}" ?`)) return;

                url = PAGE_URLS.reassignerCoursFinancement;
                payload = { code_cours: codeCours, nouveau_financement_code: nouveauFinancementCode };

                // Mise à jour UI sans recharger la page
                successCallback = () => {
                    const row = document.getElementById(`cours-row-${sanitizedId}`);
                    if(row) {
                        row.querySelector('.cours-financement-cell').textContent = nouveauFinancementCode || 'N/A';
                    }
                };
            }

            if (url) {
                button.disabled = true;
                fetch(url, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        displayApiMessage(data.message, 'success');
                        successCallback();
                    } else {
                        displayApiMessage(data.message || 'Erreur.', 'error');
                    }
                })
                .catch(error => displayApiMessage('Erreur serveur.', 'error'))
                .finally(() => { button.disabled = false; });
            }
        });
    }
});