// mon_application/static/js/preparation_horaire.js

document.addEventListener('DOMContentLoaded', () => {
    // Vérifie si nous sommes sur la bonne page et si les données sont disponibles
    if (!document.body.contains(document.getElementById('tabs-navigation')) || typeof PAGE_DATA === 'undefined') {
        return;
    }

    const {
        anneeId,
        allChamps,
        coursParChamp,
        enseignantsParCours,
        savedAssignments,
        urls
    } = PAGE_DATA;

    const ScheduleManager = {
        activeLevel: 1,
        draggedItem: null,
        sourceRow: null, // Pour mémoriser la ligne d'origine du glisser-déposer

        init() {
            this.setupTabs();
            this.setupAddRowButton();
            this.setupSaveButton();
            this.setupDragAndDrop();
            this.populateInitialState();
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

        setupAddRowButton() {
            const btnAddRow = document.getElementById('btn-add-row');
            btnAddRow.addEventListener('click', () => {
                this.createNewRow(this.activeLevel);
            });
        },

        setupSaveButton() {
            const btnSave = document.getElementById('btn-save-schedule');
            btnSave.addEventListener('click', this.handleSave.bind(this));
        },

        setupDragAndDrop() {
            const containers = document.querySelectorAll('.preparation-table tbody');
            containers.forEach(tbody => {
                // Écouteur pour le début du glisser
                tbody.addEventListener('dragstart', e => {
                    if (e.target.classList.contains('teacher-item')) {
                        this.draggedItem = e.target;
                        this.sourceRow = e.target.closest('tr'); // Mémoriser la ligne source
                        setTimeout(() => e.target.classList.add('dragging'), 0);
                    }
                });

                // Écouteur pour la fin du glisser
                tbody.addEventListener('dragend', e => {
                    if (this.draggedItem) {
                       this.draggedItem.classList.remove('dragging');
                    }
                    // Nettoyer les variables d'état après chaque opération
                    this.draggedItem = null;
                    this.sourceRow = null;
                });

                // Écouteur pour le survol d'une zone de dépôt
                tbody.addEventListener('dragover', e => {
                    const container = e.target.closest('.teachers-container');
                    const targetRow = e.target.closest('tr');

                    // N'autoriser le dépôt que si la cible est dans la ligne source
                    if (container && this.sourceRow && targetRow === this.sourceRow) {
                        e.preventDefault(); // Indique que c'est une zone de dépôt valide
                        container.classList.add('drag-over');
                    }
                });

                 // Écouteur pour quand on quitte une zone de dépôt
                tbody.addEventListener('dragleave', e => {
                    const container = e.target.closest('.teachers-container');
                    if (container) {
                        container.classList.remove('drag-over');
                    }
                });

                // Écouteur pour le lâcher de l'élément
                tbody.addEventListener('drop', e => {
                    const container = e.target.closest('.teachers-container');
                    const targetRow = e.target.closest('tr');

                    // Vérifier une dernière fois que la cible est valide
                    if (container && this.draggedItem && this.sourceRow && targetRow === this.sourceRow) {
                        e.preventDefault();
                        container.classList.remove('drag-over');
                        container.appendChild(this.draggedItem);
                    }
                });
            });
        },

        populateInitialState() {
            // Regrouper les assignations sauvegardées par cours et par niveau
            const assignmentsByCourseAndLevel = {};

            Object.keys(savedAssignments).forEach(level => {
                savedAssignments[level].forEach(assignment => {
                    const key = `${level}-${assignment.codecours}`;
                    if (!assignmentsByCourseAndLevel[key]) {
                        assignmentsByCourseAndLevel[key] = {
                            level: level,
                            cours: {
                                codecours: assignment.codecours,
                                annee_id_cours: assignment.annee_id_cours
                            },
                            placements: []
                        };
                    }
                    assignmentsByCourseAndLevel[key].placements.push({
                        enseignant_id: assignment.enseignant_id,
                        colonne_assignee: assignment.colonne_assignee
                    });
                });
            });

            // Créer les lignes et placer les enseignants selon les données sauvegardées
            Object.values(assignmentsByCourseAndLevel).forEach(data => {
                const row = this.createNewRow(data.level, data.cours);

                data.placements.forEach(placement => {
                    const teachersForCourse = enseignantsParCours[data.cours.codecours] || [];
                    const teacherData = teachersForCourse.find(t => t.enseignantid === placement.enseignant_id);

                    if (teacherData) {
                       const teacherElement = this.createTeacherElement(teacherData);
                       const targetCell = row.querySelector(`td[data-col-name="${placement.colonne_assignee}"] .teachers-container`);
                       if(targetCell) {
                           targetCell.appendChild(teacherElement);
                       }
                    }
                });
            });
        },

        createNewRow(level, selectedCourseData = null) {
            const template = document.getElementById('row-template');
            const newRow = template.content.cloneNode(true).firstElementChild;
            const tbody = document.getElementById(`schedule-body-${level}`);
            tbody.appendChild(newRow);

            const selectChamp = newRow.querySelector('.select-champ');
            allChamps.forEach(champ => {
                const option = new Option(champ.champnom, champ.champno);
                selectChamp.appendChild(option);
            });

            if (selectedCourseData) {
                const champNo = Object.keys(coursParChamp).find(cn =>
                    coursParChamp[cn].some(c => c.codecours === selectedCourseData.codecours)
                );
                if (champNo) {
                    selectChamp.value = champNo;
                    this.populateCoursSelect(newRow, champNo);
                    const selectCours = newRow.querySelector('.select-cours');
                    selectCours.value = selectedCourseData.codecours;
                }
            }

            this.setupRowEvents(newRow);
            return newRow;
        },

        setupRowEvents(row) {
            const selectChamp = row.querySelector('.select-champ');
            const selectCours = row.querySelector('.select-cours');
            const deleteBtn = row.querySelector('.btn-delete-row');

            selectChamp.addEventListener('change', () => this.handleChampChange(row));
            selectCours.addEventListener('change', () => this.handleCoursChange(row));
            deleteBtn.addEventListener('click', () => row.remove());
        },

        handleChampChange(row) {
            const selectChamp = row.querySelector('.select-champ');
            const champNo = selectChamp.value;
            this.populateCoursSelect(row, champNo);
            this.handleCoursChange(row); // Vider le select cours va aussi vider les profs
        },

        populateCoursSelect(row, champNo) {
            const selectCours = row.querySelector('.select-cours');
            selectCours.innerHTML = '<option value="">Choisir un cours...</option>';
            selectCours.disabled = !champNo;

            if (champNo && coursParChamp[champNo]) {
                coursParChamp[champNo].forEach(cours => {
                    const option = new Option(cours.codecours, cours.codecours);
                    option.dataset.anneeId = cours.annee_id;
                    selectCours.appendChild(option);
                });
            }
        },

        handleCoursChange(row) {
            const selectCours = row.querySelector('.select-cours');
            const courseCode = selectCours.value;

            this.clearTeachers(row);

            if (courseCode && enseignantsParCours[courseCode]) {
                const teachers = enseignantsParCours[courseCode];
                const placementContainers = row.querySelectorAll('td[data-col-name] .teachers-container');

                teachers.forEach((teacher, index) => {
                    if (placementContainers[index]) {
                        const teacherElement = this.createTeacherElement(teacher);
                        placementContainers[index].appendChild(teacherElement);
                    } else {
                        console.warn(`Plus d'enseignants que de colonnes disponibles pour le cours ${courseCode}. L'enseignant ${teacher.nomcomplet} n'a pas été placé.`);
                    }
                });
            }
        },


        createTeacherElement(teacher) {
            const div = document.createElement('div');
            div.className = 'teacher-item';
            div.textContent = teacher.nomcomplet;
            div.dataset.enseignantId = teacher.enseignantid;
            div.dataset.nomcomplet = teacher.nomcomplet;
            div.draggable = true;
            return div;
        },

        clearTeachers(row) {
            row.querySelectorAll('.teachers-container').forEach(container => {
                container.innerHTML = '';
            });
        },

        async handleSave() {
            const btnSave = document.getElementById('btn-save-schedule');
            const assignments = this.collectAssignments();
            btnSave.disabled = true;
            btnSave.textContent = 'Sauvegarde...';

            try {
                const response = await fetch(urls.saveSchedule, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-Requested-With': 'XMLHttpRequest'
                    },
                    body: JSON.stringify({
                        assignments
                    })
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

                        row.querySelectorAll('.teachers-container').forEach(container => {
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