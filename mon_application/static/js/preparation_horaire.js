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

        handleDragStart(e) {
            if (e.target.classList.contains('teacher-item')) {
                this.draggedItem = e.target;
                setTimeout(() => e.target.classList.add('dragging'), 0);
            }
        },

        handleDragEnd(e) {
            if (this.draggedItem) {
                this.draggedItem.classList.remove('dragging');
                this.draggedItem = null;
            }
        },

        handleDragOver(e) {
            const container = e.target.closest('.teachers-container');
            if (container && this.draggedItem) {
                e.preventDefault();
                container.classList.add('drag-over');
            }
        },

        handleDragLeave(e) {
            const container = e.target.closest('.teachers-container');
            if (container) {
                container.classList.remove('drag-over');
            }
        },

        handleDrop(e) {
            const container = e.target.closest('.teachers-container');
            if (container && this.draggedItem) {
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
            if (e.target.classList.contains('select-champ')) {
                const row = e.target.closest('tr');
                this.populateCoursSelect(row);
                this.populateTeachers(row);
            } else if (e.target.classList.contains('select-cours')) {
                const row = e.target.closest('tr');
                this.populateTeachers(row);
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

        // CORRIGÉ : Distribue les enseignants dans les colonnes d'assignation
        populateTeachers(row) {
            // 1. Vider toutes les colonnes d'enseignants pour cette ligne
            row.querySelectorAll('.teachers-container').forEach(c => c.innerHTML = '');

            const selectCours = row.querySelector('.select-cours');
            const courseCode = selectCours.value;

            if (courseCode && enseignantsParCours[courseCode]) {
                const teachers = enseignantsParCours[courseCode];
                // 2. Récupérer les conteneurs de destination
                const assignmentContainers = row.querySelectorAll('.assignment-droppable');
                const availableContainer = row.querySelector('.available-teachers');

                // 3. Distribuer les enseignants
                teachers.forEach((teacher, index) => {
                    const teacherElement = this.createTeacherElement(teacher);
                    // S'il y a une colonne d'assignation disponible pour cet enseignant
                    if (assignmentContainers[index]) {
                        assignmentContainers[index].appendChild(teacherElement);
                    } else {
                        // Sinon (plus d'enseignants que de colonnes), le mettre dans les "disponibles"
                        console.warn(`Plus d'enseignants que de colonnes, enseignant ${teacher.nomcomplet} placé dans "disponibles".`);
                        availableContainer.appendChild(teacherElement);
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
            document.querySelectorAll('.tab-content').forEach(tab => {
                const level = parseInt(tab.dataset.level, 10);
                tab.querySelectorAll('tbody tr').forEach(row => {
                    const selectCours = row.querySelector('.select-cours');
                    const courseCode = selectCours.value;
                    const selectedOption = selectCours.options[selectCours.selectedIndex];

                    if (courseCode && selectedOption && selectedOption.dataset.anneeId) {
                        const courseAnneeId = parseInt(selectedOption.dataset.anneeId, 10);

                        // Collecter les enseignants depuis les colonnes d'assignation
                        row.querySelectorAll('.assignment-droppable').forEach(container => {
                            const colName = container.parentElement.dataset.colName;
                            container.querySelectorAll('.teacher-item').forEach(teacherItem => {
                                assignments.push({
                                    secondaire_level: level,
                                    codecours: courseCode,
                                    annee_id_cours: courseAnneeId,
                                    enseignant_id: parseInt(teacherItem.dataset.enseignantId, 10),
                                    colonne_assignee: colName
                                });
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