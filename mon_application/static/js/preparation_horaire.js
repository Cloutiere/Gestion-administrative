// mon_application/static/js/preparation_horaire.js

document.addEventListener('DOMContentLoaded', () => {
    // Vérifie si nous sommes sur la bonne page et si les données sont disponibles
    if (!document.body.contains(document.getElementById('tabs-navigation')) || typeof PAGE_DATA === 'undefined') {
        console.warn("Script preparation_horaire.js chargé, mais les éléments requis ne sont pas sur la page.");
        return;
    }

    const {
        coursParChamp,
        enseignantsParCours,
        urls
    } = PAGE_DATA;

    const ScheduleManager = {
        activeLevel: 1,
        draggedItem: null,
        originRow: null, // NOUVEAU : Pour mémoriser la ligne d'origine du drag

        init() {
            this.setupTabs();
            this.setupActionButtons();
            this.setupEventListeners();
        },

        setupTabs() {
            const tabs = document.querySelectorAll('#tabs-navigation li');
            tabs.forEach(tab => {
                tab.addEventListener('click', () => {
                    const level = tab.dataset.level;
                    tabs.forEach(t => t.classList.remove('active'));
                    tab.classList.add('active');
                    document.querySelectorAll('.tab-content').forEach(content => {
                        content.classList.remove('active');
                    });
                    document.getElementById(`tab-content-${level}`).classList.add('active');
                    this.activeLevel = parseInt(level, 10);
                });
            });
        },

        setupActionButtons() {
            document.getElementById('btn-add-row').addEventListener('click', () => this.createNewRow(this.activeLevel));
            document.getElementById('btn-save-schedule').addEventListener('click', this.handleSave.bind(this));
        },

        // Utilisation de la délégation d'événements pour une gestion centralisée
        setupEventListeners() {
            const scheduleContainer = document.querySelector('.tabs-container');

            // Écouteurs pour le Drag & Drop
            scheduleContainer.addEventListener('dragstart', this.handleDragStart.bind(this));
            scheduleContainer.addEventListener('dragend', this.handleDragEnd.bind(this));
            scheduleContainer.addEventListener('dragover', this.handleDragOver.bind(this));
            scheduleContainer.addEventListener('dragleave', this.handleDragLeave.bind(this));
            scheduleContainer.addEventListener('drop', this.handleDrop.bind(this));

            // Écouteurs pour les interactions sur les lignes (suppression, changement de select)
            scheduleContainer.addEventListener('click', this.handleRowClick.bind(this));
            scheduleContainer.addEventListener('change', this.handleRowChange.bind(this));
        },

        // MODIFICATION : Mémorise la ligne d'origine
        handleDragStart(e) {
            if (e.target.classList.contains('teacher-item')) {
                this.draggedItem = e.target;
                this.originRow = e.target.closest('tr'); // Mémoriser la ligne parente
                setTimeout(() => e.target.classList.add('dragging'), 0);
            }
        },

        // MODIFICATION : Nettoie les propriétés après le drag
        handleDragEnd() {
            if (this.draggedItem) {
                this.draggedItem.classList.remove('dragging');
            }
            // Nettoyage systématique des références
            this.draggedItem = null;
            this.originRow = null;
        },

        // MODIFICATION : Ajout de la contrainte de ligne
        handleDragOver(e) {
            const container = e.target.closest('.teachers-container.assignment-droppable');
            // Quitter si ce n'est pas une zone de dépôt valide ou si aucun item n'est glissé
            if (!container || !this.draggedItem) {
                return;
            }

            const targetRow = container.closest('tr');

            // NOUVELLE RÈGLE : Autoriser le dépôt uniquement si la ligne cible est la même que l'origine
            if (this.originRow === targetRow) {
                e.preventDefault(); // Indique que la zone est une cible de dépôt valide
                container.classList.add('drag-over');
            }
            // Si la condition n'est pas remplie, preventDefault() n'est pas appelé,
            // et le navigateur indiquera visuellement que le dépôt est interdit.
        },

        handleDragLeave(e) {
            const container = e.target.closest('.teachers-container.assignment-droppable');
            if (container) {
                container.classList.remove('drag-over');
            }
        },

        handleDrop(e) {
            const container = e.target.closest('.teachers-container.assignment-droppable');

            // La validation a déjà eu lieu dans `handleDragOver`, mais une double-vérification ne nuit pas
            if (container && this.draggedItem && container.closest('tr') === this.originRow) {
                e.preventDefault();
                container.classList.remove('drag-over');
                container.appendChild(this.draggedItem);
            }
        },

        handleRowClick(e) {
            if (e.target.classList.contains('btn-delete-row')) {
                e.target.closest('tr').remove();
            }
        },

        handleRowChange(e) {
            const target = e.target;
            if (target.classList.contains('select-champ')) {
                const row = target.closest('tr');
                this.populateCoursSelect(row);
                // Vider les cellules d'assignation si le champ change
                this.populateRowWithTeachers(row);
            } else if (target.classList.contains('select-cours')) {
                const row = target.closest('tr');
                this.populateRowWithTeachers(row);
            }
        },

        createNewRow(level) {
            const template = document.getElementById('row-template');
            const newRow = template.content.cloneNode(true).firstElementChild;
            document.getElementById(`schedule-body-${level}`).appendChild(newRow);
        },

        populateCoursSelect(row) {
            const selectChamp = row.querySelector('.select-champ');
            const selectCours = row.querySelector('.select-cours');
            const champNo = selectChamp.value;

            selectCours.innerHTML = '<option value="">Choisir un cours...</option>';
            selectCours.disabled = !champNo;

            if (champNo && coursParChamp[champNo]) {
                coursParChamp[champNo].forEach(cours => {
                    const option = new Option(cours.codecours, cours.codecours);
                    option.dataset.anneeId = cours.annee_id;
                    selectCours.add(option);
                });
            }
        },

        populateRowWithTeachers(row) {
            const assignmentCells = Array.from(row.querySelectorAll('.assignment-droppable'));

            assignmentCells.forEach(cell => cell.innerHTML = '');

            const selectCours = row.querySelector('.select-cours');
            const courseCode = selectCours.value;

            if (courseCode && enseignantsParCours[courseCode]) {
                let teachers = [...enseignantsParCours[courseCode]];
                for (let i = teachers.length - 1; i > 0; i--) {
                    const j = Math.floor(Math.random() * (i + 1));
                    [teachers[i], teachers[j]] = [teachers[j], teachers[i]];
                }

                let cellIndex = 0;
                teachers.forEach(teacher => {
                    if (cellIndex < assignmentCells.length) {
                        assignmentCells[cellIndex].appendChild(this.createTeacherElement(teacher));
                        cellIndex++;
                    } else {
                        assignmentCells[0].appendChild(this.createTeacherElement(teacher));
                    }
                });
            }
        },

        createTeacherElement(teacher) {
            const div = document.createElement('div');
            div.className = 'teacher-item';
            div.textContent = teacher.nomcomplet;
            div.dataset.enseignantId = teacher.enseignantid;
            div.draggable = true;
            return div;
        },

        async handleSave() {
            const btnSave = document.getElementById('btn-save-schedule');
            const assignments = this.collectAssignments();

            if (assignments.length === 0) {
                 alert("Aucune assignation à sauvegarder.");
                 return;
            }

            btnSave.disabled = true;
            btnSave.textContent = 'Sauvegarde...';

            try {
                const response = await fetch(urls.saveSchedule, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
                    body: JSON.stringify({ assignments })
                });
                const result = await response.json();
                if (result.success) {
                    alert('Horaire sauvegardé avec succès !');
                } else {
                    alert(`Erreur de sauvegarde : ${result.message || 'Erreur inconnue'}`);
                }
            } catch (error) {
                console.error('Erreur lors de la sauvegarde:', error);
                alert('Une erreur réseau est survenue. Impossible de sauvegarder.');
            } finally {
                btnSave.disabled = false;
                btnSave.textContent = "Sauvegarder l'horaire";
            }
        },

        collectAssignments() {
            const assignments = [];
            const uniqueAssignments = new Set(); 

            document.querySelectorAll('.tab-content').forEach(tab => {
                const level = parseInt(tab.dataset.level, 10);
                tab.querySelectorAll('tbody tr').forEach(row => {
                    const selectCours = row.querySelector('.select-cours');
                    const courseCode = selectCours.value;
                    const selectedOption = selectCours.options[selectCours.selectedIndex];

                    if (courseCode && selectedOption && selectedOption.dataset.anneeId) {
                        const courseAnneeId = parseInt(selectedOption.dataset.anneeId, 10);

                        row.querySelectorAll('.assignment-droppable').forEach(container => {
                            const colName = container.parentElement.dataset.colName;
                            container.querySelectorAll('.teacher-item').forEach(teacherItem => {
                                const enseignantId = parseInt(teacherItem.dataset.enseignantId, 10);
                                const uniqueKey = `${level}-${enseignantId}-${colName}`;

                                if (!uniqueAssignments.has(uniqueKey)) {
                                    uniqueAssignments.add(uniqueKey);
                                    assignments.push({
                                        secondaire_level: level,
                                        codecours: courseCode,
                                        annee_id_cours: courseAnneeId,
                                        enseignant_id: enseignantId,
                                        colonne_assignee: colName
                                    });
                                }
                            });
                        });
                    }
                });
            });
            return assignments;
        }
    };

    ScheduleManager.init();
});