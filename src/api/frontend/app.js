/**
 * Temporal Agent Dashboard - App Logic
 */

const API_BASE = window.location.origin + '/api';
const WS_URL = (window.location.protocol === 'https:' ? 'wss://' : 'ws://') + window.location.host + '/ws';

// State
let tasks = [];
let socket = null;

// DOM Elements
const views = {
    tasks: document.getElementById('tasks-view'),
    skills: document.getElementById('skills-view'),
    mcps: document.getElementById('mcps-view'),
    env: document.getElementById('env-view')
};

const navItems = document.querySelectorAll('.nav-item');

// Initialization
document.addEventListener('DOMContentLoaded', () => {
    initRouter();
    initWebSockets();
    refreshTasks(); // Initial load

    // Global Event Listeners
    setupModals();
    setupForms();
});

// --- Router ---
function initRouter() {
    navItems.forEach(item => {
        item.addEventListener('click', () => {
            const viewName = item.dataset.view;
            switchView(viewName);
        });
    });
}

function switchView(viewName) {
    // Update Nav
    navItems.forEach(item => {
        item.classList.toggle('active', item.dataset.view === viewName);
    });

    // Update View
    Object.values(views).forEach(el => el.classList.remove('active'));
    views[viewName].classList.add('active');

    // Load Data for view
    if (viewName === 'tasks') refreshTasks();
    if (viewName === 'skills') loadSkills();
    if (viewName === 'mcps') loadMCPs();
    if (viewName === 'env') loadEnv();
}

// --- WebSockets ---
function initWebSockets() {
    socket = new WebSocket(WS_URL);

    const statusDot = document.getElementById('connectionStatusDot');
    const statusText = document.getElementById('connectionStatusText');

    socket.onopen = () => {
        statusDot.classList.add('connected');
        statusText.textContent = 'Connected';
        console.log('WS Connected');
    };

    socket.onclose = () => {
        statusDot.classList.remove('connected');
        statusText.textContent = 'Disconnected';
        setTimeout(initWebSockets, 3000); // Reconnect
    };

    socket.onmessage = (event) => {
        const data = JSON.parse(event.data);
        handleWSMessage(data);
    };
}

function handleWSMessage(data) {
    if (data.type === 'tasks_refresh' || data.type === 'task_updated' || data.type === 'task_created' || data.type === 'task_deleted') {
        if (data.tasks) {
            tasks = data.tasks;
            renderTasks(); // Only call renderTasks, which dispatches based on view
        } else {
            refreshTasks();
        }
    }
}

// --- Tasks / Kanban & List ---
let currentTaskView = 'kanban'; // 'kanban' or 'list'
let currentSort = 'created_desc'; // Default sort

// Helper: Format Date
function formatDate(isoString) {
    if (!isoString) return '-';
    // Format: "Jan 1, 10:00 AM"
    const d = new Date(isoString);
    if (isNaN(d.getTime())) return '-';
    return d.toLocaleString('en-US', {
        month: 'short',
        day: 'numeric',
        hour: 'numeric',
        minute: '2-digit'
    });
}

async function refreshTasks() {
    try {
        const res = await fetch(`${API_BASE}/tasks`);
        const data = await res.json();
        tasks = data.tasks;
        renderTasks();
    } catch (err) {
        console.error('Failed to fetch tasks', err);
    }
}

function renderTasks() {
    console.log('Rendering tasks...', tasks.length, currentTaskView);

    // Sort Tasks
    const sortedTasks = [...tasks].sort((a, b) => {
        let dateA, dateB;

        switch (currentSort) {
            case 'completed_desc':
            case 'completed_asc':
                // Use end_time or created_at as fallback if not completed? 
                // Or just push nulls to end? Let's use end_time.
                dateA = a.end_time ? new Date(a.end_time) : new Date(0); // 0 for incomplete
                dateB = b.end_time ? new Date(b.end_time) : new Date(0);
                break;
            case 'created_asc':
            case 'created_desc':
            default:
                dateA = a.created_at ? new Date(a.created_at) : new Date(0);
                dateB = b.created_at ? new Date(b.created_at) : new Date(0);
                break;
        }

        if (currentSort.endsWith('_asc')) {
            return dateA - dateB;
        } else {
            return dateB - dateA;
        }
    });

    if (currentTaskView === 'kanban') {
        renderKanban(sortedTasks);
    } else {
        renderListView(sortedTasks);
    }
}

function renderKanban(tasksToRender) {
    const columns = {
        pending: document.getElementById('list-pending'),
        in_progress: document.getElementById('list-in_progress'),
        completed: document.getElementById('list-completed')
    };

    if (!columns.pending) return; // Guard

    // Clear columns
    Object.values(columns).forEach(col => col.innerHTML = '');

    const counts = { pending: 0, in_progress: 0, completed: 0 };

    tasksToRender.forEach(task => {
        // Map status to column
        let colId = task.status;
        if (colId === 'failed') colId = 'completed'; // Group failed with completed for now? Or maybe a separate visual
        if (!columns[colId]) colId = 'pending'; // Fallback

        counts[task.status === 'failed' ? 'completed' : task.status]++; // Count failed in completed for column header

        const card = createTaskCard(task);
        columns[colId].appendChild(card);
    });

    // Update counts
    document.getElementById('count-pending').textContent = counts.pending;
    document.getElementById('count-in_progress').textContent = counts.in_progress;
    // For completed column, it might have completed + failed
    const completedTotal = tasks.filter(t => t.status === 'completed' || t.status === 'failed').length;
    document.getElementById('count-completed').textContent = completedTotal;
}

function renderListView(tasksToRender) {
    const tbody = document.getElementById('tasks-list-body');
    if (!tbody) {
        console.error('List body not found');
        return;
    }
    tbody.innerHTML = '';

    if (tasks.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" style="padding: 20px; text-align: center; color: #666;">No tasks found</td></tr>';
        return;
    }

    tasksToRender.forEach(task => {
        const tr = document.createElement('tr');
        tr.style.borderBottom = '1px solid #eee';
        tr.innerHTML = `
            <td style="padding: 12px; font-family: monospace;">${(task.task_id || '').substring(0, 8)}</td>
            <td style="padding: 12px;">${task.description || ''}</td>
            <td style="padding: 12px;"><span class="status-pill ${task.status}">${task.status}</span></td>
            <td style="padding: 12px;">${task.workflow_id || '-'}</td>
            <td style="padding: 12px; font-size: 12px; color: #666;">${formatDate(task.created_at)}</td>
            <td style="padding: 12px; font-size: 12px; color: #666;">${formatDate(task.start_time)}</td>
            <td style="padding: 12px; font-size: 12px; color: #666;">${formatDate(task.end_time)}</td>
            <td style="padding: 12px; display: flex; gap: 4px;">
                <button class="btn btn-secondary" style="padding: 4px 8px; font-size: 12px;" onclick="window.showTaskDetails('${task.task_id}')">View</button>
                ${(task.status === 'pending') ? `
                    <button class="btn" style="padding: 4px 8px; font-size: 12px; background: #f0f0f0; border: 1px solid #ddd; margin-right: 4px;" onclick="window.editTask('${task.task_id}', event)">✎</button>
                    <button class="btn" style="padding: 4px 8px; font-size: 12px; background: #fff1f0; color: #cf1322; border: 1px solid #ffa39e; margin-right: 4px;" onclick="window.deleteTask('${task.task_id}', event)">🗑️</button>
                ` : ''}
                ${(task.status === 'pending' && task.workflow_id === 'manual') ?
                `<button class="btn" style="padding: 4px 8px; font-size: 12px; background: #e6f7ff; color: #0066cc; border: 1px solid #91d5ff;" onclick="window.runTask('${task.task_id}', event)">▶ Run</button>`
                : ''}
            </td>
        `;
        tbody.appendChild(tr);
    });
}

function createTaskCard(task) {
    const el = document.createElement('div');
    el.className = `kanban-card status-${task.status}`;
    el.draggable = true;
    el.dataset.id = task.task_id;

    // Status Pill
    const pill = `<span class="status-pill ${task.status}">${task.status}</span>`;

    el.innerHTML = `
        <div class="card-title">${task.description}</div>
        <div>${pill}</div>
        <div class="card-meta">
            <span>${task.task_id.substring(0, 8)}</span>
             ${task.workflow_id ? `<span>${task.workflow_id === 'manual' ? 'Manual' : 'Workflow'}</span>` : ''}
             <div style="margin-left: auto; display: flex; gap: 4px;">
                 ${(task.status === 'pending') ? `
                    <button class="btn" style="font-size: 11px; padding: 2px 6px; background: #f0f0f0; border: 1px solid #ddd;" title="Edit" onclick="window.editTask('${task.task_id}', event)">✎</button>
                    <button class="btn" style="font-size: 11px; padding: 2px 6px; background: #fff1f0; color: #cf1322; border: 1px solid #ffa39e;" title="Delete" onclick="window.deleteTask('${task.task_id}', event)">🗑️</button>
                 ` : ''}
                 ${(task.status === 'pending' && task.workflow_id === 'manual') ?
            `<button class="btn" style="font-size: 11px; padding: 2px 6px; background: #e6f7ff; color: #0066cc; border: 1px solid #91d5ff;" onclick="window.runTask('${task.task_id}', event)">▶ Run</button>`
            : ''}
             </div>
        </div>
        <div class="card-dates" style="margin-top: 8px; padding-top: 8px; border-top: 1px solid #eee; font-size: 11px; color: #888;">
            <div title="Created">📅 ${formatDate(task.created_at)}</div>
            ${task.start_time ? `<div title="Started">▶️ ${formatDate(task.start_time)}</div>` : ''}
            ${task.end_time ? `<div title="Completed">✅ ${formatDate(task.end_time)}</div>` : ''}
        </div>
    `;

    // Drag Events
    el.addEventListener('dragstart', (e) => {
        el.classList.add('dragging');
        e.dataTransfer.setData('text/plain', task.task_id);
    });

    el.addEventListener('dragend', () => {
        el.classList.remove('dragging');
    });

    // Click to view details
    el.addEventListener('click', () => {
        showTaskDetails(task.task_id);
    });

    return el;
}

window.showTaskDetails = (taskId) => {
    // Redirect to dedicated task page
    window.location.href = `/static/task.html?id=${taskId}`;
};





window.runTask = (taskId, event) => {
    if (event) {
        event.stopPropagation();
    }

    showConfirm('Run Task', 'Run this task immediately?', async () => {
        // Optimistic Update
        const task = tasks.find(t => t.task_id === taskId);
        if (task) {
            task.status = 'in_progress';
            // If in list view, force re-render of that row or whole list
            // For simplicity, re-render whole view
            renderTasks();
        }

        try {
            const res = await fetch(`${API_BASE}/tasks/${taskId}/execute`, { method: 'POST' });
            if (res.ok) {
                console.log('Task execution triggered');
                // The WS will eventually come back and confirm, 
                // but we already updated UI optimistically.
            } else {
                const data = await res.json();
                alert('Failed to run task: ' + (data.detail || 'Unknown error'));
                refreshTasks(); // Revert state on error
            }
        } catch (e) {
            console.error(e);
            alert('Error triggering task execution');
            refreshTasks(); // Revert state on error
        }
    });
};

// View Toggles
document.getElementById('viewKanbanBtn').addEventListener('click', () => {
    currentTaskView = 'kanban';
    document.getElementById('viewKanbanBtn').classList.add('active');
    document.getElementById('viewListBtn').classList.remove('active');
    document.getElementById('tasks-kanban').style.display = 'grid';
    document.getElementById('tasks-list-view').style.display = 'none';
    renderTasks();
});

document.getElementById('viewListBtn').addEventListener('click', () => {
    currentTaskView = 'list';
    document.getElementById('viewListBtn').classList.add('active');
    document.getElementById('viewKanbanBtn').classList.remove('active');
    document.getElementById('tasks-kanban').style.display = 'none';
    document.getElementById('tasks-list-view').style.display = 'block';
    renderTasks();
});

// Sort Change
document.getElementById('sortTasksSelect').addEventListener('change', (e) => {
    currentSort = e.target.value;
    renderTasks();
});

// Drag and Drop Logic
const dropZones = document.querySelectorAll('.kanban-column');

dropZones.forEach(zone => {
    zone.addEventListener('dragover', (e) => {
        e.preventDefault(); // Allow drop
        zone.classList.add('drag-over');
    });

    zone.addEventListener('dragleave', () => {
        zone.classList.remove('drag-over');
    });

    zone.addEventListener('drop', async (e) => {
        e.preventDefault();
        zone.classList.remove('drag-over');
        const taskId = e.dataTransfer.getData('text/plain');
        const newStatus = zone.dataset.status;

        // Optimistic UI update
        // We'll wait for WS confirm, but could update local state here

        await updateTaskStatus(taskId, newStatus);
    });
});

async function updateTaskStatus(taskId, status) {
    try {
        await fetch(`${API_BASE}/tasks/${taskId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status })
        });

        // If moving to 'in_progress' and it was manual, maybe trigger execution?
        // The current backend endpoint for PUT just updates DB. 
        // Logic for execution trigger is separate in current main.py (/execute).

        if (status === 'in_progress') {
            // Check if we should execute
            const task = tasks.find(t => t.task_id === taskId);
            if (task && task.workflow_id === 'manual') {
                // Trigger execution
                fetch(`${API_BASE}/tasks/${taskId}/execute`, { method: 'POST' });
            }
        }

    } catch (err) {
        console.error('Update failed', err);
    }
}

window.deleteTask = (taskId, event) => {
    if (event) event.stopPropagation();

    showConfirm('Delete Task', 'Are you sure you want to delete this task?', async () => {
        try {
            const res = await fetch(`${API_BASE}/tasks/${taskId}`, { method: 'DELETE' });
            if (res.ok) {
                // Optimistic remove
                tasks = tasks.filter(t => t.task_id !== taskId);
                renderTasks();
            } else {
                alert('Failed to delete task');
            }
        } catch (e) {
            console.error(e);
            alert('Error deleting task');
        }
    });
};

window.editTask = (taskId, event) => {
    if (event) event.stopPropagation();

    const task = tasks.find(t => t.task_id === taskId);
    if (!task) return;

    document.getElementById('editTaskId').value = taskId;
    document.getElementById('editTaskDescription').value = task.description;
    document.getElementById('editTaskModal').classList.add('active');
};

// --- Skills ---
let skillsData = []; // Store locally
let currentSkill = null; // Currently selected skill
let currentFile = null; // Currently selected file path

async function loadSkills() {
    // Determine which view to show
    const gridView = document.getElementById('skills-grid-view');
    const detailsView = document.getElementById('skill-details-view');

    // If we were in details view, we might want to stay there if refreshing? 
    // For now, let's default to grid view on full reload, but refresh data if just updating.

    const container = document.getElementById('skills-list');
    container.innerHTML = 'Loading...';
    try {
        const res = await fetch(`${API_BASE}/skills`);
        const data = await res.json();
        skillsData = data.skills; // Save state

        container.innerHTML = '';
        if (skillsData.length === 0) {
            container.innerHTML = '<div style="grid-column: 1/-1; text-align: center; color: #666; padding: 40px;">No skills found. Create one to get started.</div>';
            return;
        }

        data.skills.forEach(skill => {
            const card = document.createElement('div');
            card.className = 'card';
            card.style.cursor = 'pointer';

            // Count files
            const fileCount = skill.files ? skill.files.length : 0;

            card.innerHTML = `
                <div style="display:flex; justify-content:space-between; align-items:start;">
                    <h4 style="margin-bottom: 10px;">${skill.name}</h4>
                    <span style="font-size: 20px;">📦</span>
                </div>
                <div style="font-size: 12px; color: #666; margin-bottom: 15px;">
                    ${fileCount} files
                </div>
                <!-- <button class="btn btn-secondary" onclick="event.stopPropagation(); window.viewSkill('${skill.name}')">Open</button> -->
            `;

            card.addEventListener('click', () => window.viewSkill(skill.name));
            container.appendChild(card);
        });
    } catch (e) {
        container.innerHTML = 'Error loading skills';
        console.error(e);
    }
}

window.viewSkill = (skillName) => {
    currentSkill = skillsData.find(s => s.name === skillName);
    if (!currentSkill) return;

    // Switch to details view
    document.getElementById('skills-grid-view').style.display = 'none';
    document.getElementById('skill-details-view').style.display = 'block';

    // Update Header
    document.getElementById('currentSkillName').textContent = currentSkill.name;

    // Render File Tree
    renderFileTree(currentSkill.files);

    // Reset Editor
    resetEditor();

    // Auto-select SKILL.md if it exists
    const readme = currentSkill.files.find(f => f.path === 'SKILL.md');
    if (readme) {
        loadFile(readme.path);
    }
};

window.closeSkillDetails = () => {
    currentSkill = null;
    currentFile = null;
    document.getElementById('skills-grid-view').style.display = 'grid'; // it was display:grid in css but style.display sets block usually. Wait, in HTML it's inline style grid. Good.
    // wait, in my HTML replacement I set it to grid? No, I set it to display: grid in the style attribute.
    // So restoring it to 'grid' is correct. But 'block' might break layout if I rely on grid.
    // Actually, let's use check style.
    document.getElementById('skills-grid-view').style.display = 'block'; // Outer container
    document.getElementById('skill-details-view').style.display = 'none';

    // Re-render grid to be safe or just show it
    document.getElementById('skills-grid-view').querySelector('#skills-list').style.display = 'grid';
    // The previous structure was: <div id="skills-grid-view"> ... <div id="skills-list" style="display:grid...">
    // So hiding #skills-grid-view hides everything. Showing it as block is fine, because the inner div handles grid.

    loadSkills(); // Refresh
};

function renderFileTree(files) {
    const tree = document.getElementById('skill-file-tree');
    tree.innerHTML = '';

    if (!files || files.length === 0) {
        tree.innerHTML = '<div style="padding:15px; color:#999; font-size:12px;">No files</div>';
        return;
    }

    files.forEach(file => {
        const item = document.createElement('div');
        item.className = 'file-tree-item';
        item.dataset.path = file.path;

        const icon = file.type === 'directory' ? '📁' : '📄';

        item.innerHTML = `
            <span class="icon">${icon}</span>
            <span class="name">${file.path}</span>
        `;

        if (file.type !== 'directory') {
            item.addEventListener('click', () => loadFile(file.path));
        }

        tree.appendChild(item);
    });
}

async function loadFile(path) {
    if (!currentSkill) return;

    // UI Update
    document.querySelectorAll('.file-tree-item').forEach(el => el.classList.remove('active'));
    const activeItem = document.querySelector(`.file-tree-item[data-path="${path}"]`);
    if (activeItem) activeItem.classList.add('active');

    currentFile = path;
    document.getElementById('currentFileName').textContent = path;
    const container = document.getElementById('skillEditorContainer');
    container.innerHTML = '<div class="empty-state">Loading...</div>';
    document.getElementById('saveSkillFileBtn').disabled = true;

    try {
        const res = await fetch(`${API_BASE}/skills/${currentSkill.name}/files?path=${encodeURIComponent(path)}`);

        if (!res.ok) throw new Error('Failed to load file');

        const data = await res.json();

        if (data.is_binary) {
            container.innerHTML = '<div class="empty-state">Binary file (cannot edit)</div>';
        } else {
            const textarea = document.createElement('textarea');
            textarea.className = 'editor-textarea';
            textarea.value = data.content;
            textarea.id = 'active-file-content';

            // Allow save
            textarea.addEventListener('input', () => {
                document.getElementById('saveSkillFileBtn').disabled = false;
            });

            container.innerHTML = '';
            container.appendChild(textarea);
        }

    } catch (e) {
        container.innerHTML = `<div class="empty-state" style="color:var(--error)">Error loading file: ${e.message}</div>`;
    }
}

function resetEditor() {
    currentFile = null;
    document.getElementById('currentFileName').textContent = 'Select a file';
    document.getElementById('skillEditorContainer').innerHTML = '<div class="empty-state">Select a file to edit</div>';
    document.getElementById('saveSkillFileBtn').disabled = true;
}

// Save File
document.getElementById('saveSkillFileBtn').addEventListener('click', async () => {
    if (!currentSkill || !currentFile) return;

    const content = document.getElementById('active-file-content').value;
    const btn = document.getElementById('saveSkillFileBtn');

    const originalText = btn.textContent;
    btn.textContent = 'Saving...';
    btn.disabled = true;

    try {
        const res = await fetch(`${API_BASE}/skills/${currentSkill.name}/files`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path: currentFile, content: content })
        });

        if (res.ok) {
            // alert('Saved'); // Too intrusive?
            // Maybe just temporary button state
            btn.textContent = 'Saved!';
            setTimeout(() => {
                btn.textContent = originalText;
                // Keep disabled until change
            }, 2000);
        } else {
            alert('Error saving file');
            btn.disabled = false;
            btn.textContent = originalText;
        }
    } catch (e) {
        console.error(e);
        alert('Error saving file');
        btn.disabled = false;
        btn.textContent = originalText;
    }
});

// Add File (Simple implementation)
window.addSkillFile = () => {
    if (!currentSkill) return;

    const path = prompt("Enter file path (e.g. scripts/new.py):");
    if (!path) return;

    // Create empty file
    fetch(`${API_BASE}/skills/${currentSkill.name}/files`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: path, content: "" })
    }).then(res => {
        if (res.ok) {
            // Refresh files
            // We need to re-fetch the skill list to get updated file structure, 
            // OR we just trust we added it and manually update local state.
            // Simplest: refresh skills list then re-open? Or easier: just call API to get skill details?
            // Our API structure list_skills returns EVERYTHING. So let's just reloadSkills and re-find current.
            loadSkills().then(() => {
                // Re-find and re-render
                currentSkill = skillsData.find(s => s.name === currentSkill.name);
                renderFileTree(currentSkill.files);
                loadFile(path); // Open new file
            });
        } else {
            alert("Failed to create file");
        }
    });
};

// Edit Skill Name (Not implemented in this view yet, maybe removing the global edit for now)
window.editSkill = (name) => {
    // Legacy generic edit - redirected to details view now? 
    // Or we can keep it for renaming?
    // For now, disabling the old simple edit modal as it assumed single file content.
    window.viewSkill(name);
};

// --- MCPs ---
async function loadMCPs() {
    const editor = document.getElementById('mcpEditor');
    editor.value = 'Loading...';
    try {
        const res = await fetch(`${API_BASE}/mcps`);
        const data = await res.json();
        editor.value = data.config;
    } catch (e) {
        editor.value = '{}';
    }
}

document.getElementById('saveMcpBtn').addEventListener('click', async () => {
    const content = document.getElementById('mcpEditor').value;
    try {
        const res = await fetch(`${API_BASE}/mcps`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ config: content })
        });
        if (res.ok) alert('Saved!');
        else alert('Error saving MCP config');
    } catch (e) {
        alert('Error saving');
    }
});

// --- Env ---
let envData = {};

async function loadEnv() {
    const container = document.getElementById('env-vars-container');
    container.innerHTML = 'Loading...';
    try {
        const res = await fetch(`${API_BASE}/env`);
        const data = await res.json();
        envData = data.env;

        container.innerHTML = '';
        const table = document.createElement('table');
        table.style.width = '100%';
        table.style.borderCollapse = 'collapse';

        Object.entries(data.env).forEach(([k, v]) => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td style="padding: 8px; border-bottom: 1px solid #eee; font-weight: 600;">${k}</td>
                <td style="padding: 8px; border-bottom: 1px solid #eee; font-family: monospace;">${'•'.repeat(8)}</td>
                <td style="padding: 8px; border-bottom: 1px solid #eee; text-align: right;">
                    <button class="btn btn-secondary" style="padding: 4px 8px; font-size: 12px;" onclick="window.editEnv('${k}')">Edit</button>
                </td>
            `;
            table.appendChild(tr);
        });
        container.appendChild(table);
    } catch (e) {
        container.innerHTML = 'Error loading env';
    }
}

window.editEnv = (key) => {
    const val = envData[key];
    document.getElementById('envKey').value = key;
    document.getElementById('envValue').value = val; // Pre-fill with actual value
    document.getElementById('envModal').classList.add('active');
};

// --- Modals & Forms ---
function setupModals() {
    const overlays = document.querySelectorAll('.modal-overlay');
    const closeBtns = document.querySelectorAll('.close-modal');

    closeBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            overlays.forEach(o => o.classList.remove('active'));
        });
    });

    // Triggers
    document.getElementById('createTaskBtn').addEventListener('click', () => {
        document.getElementById('taskModal').classList.add('active');
    });

    document.getElementById('createSkillBtn').addEventListener('click', () => {
        document.getElementById('skillModal').classList.add('active');
    });

    document.getElementById('addEnvBtn').addEventListener('click', () => {
        document.getElementById('envModal').classList.add('active');
    });
}

// --- Confirmation Modal Support ---
let confirmCallback = null;

function showConfirm(title, message, onConfirm) {
    document.getElementById('confirmTitle').innerText = title;
    document.getElementById('confirmMessage').innerText = message;
    confirmCallback = onConfirm;
    document.getElementById('confirmModal').classList.add('active');
}

// Global confirm handler
const confirmOkBtn = document.getElementById('confirmOkBtn');
if (confirmOkBtn) {
    confirmOkBtn.addEventListener('click', () => {
        if (confirmCallback) confirmCallback();
        document.getElementById('confirmModal').classList.remove('active');
        confirmCallback = null;
    });
}


function setupForms() {
    // Task Create
    document.getElementById('taskForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        const desc = document.getElementById('taskDescription').value;
        const wf = document.getElementById('taskWorkflow').value || 'manual';

        try {
            await fetch(`${API_BASE}/tasks`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ description: desc, workflow_id: wf })
            });
            document.getElementById('taskModal').classList.remove('active');
            e.target.reset();
        } catch (e) {
            alert('Error creating task');
        }
    });

    // Skill Create
    document.getElementById('skillForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        const name = document.getElementById('skillName').value;
        const content = document.getElementById('skillContent').value;

        try {
            await fetch(`${API_BASE}/skills`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name, content })
            });
            document.getElementById('skillModal').classList.remove('active');
            e.target.reset();
            loadSkills(); // Refresh
        } catch (e) {
            alert('Error creating skill');
        }
    });

    // Env Create
    document.getElementById('envForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        const key = document.getElementById('envKey').value;
        const val = document.getElementById('envValue').value;

        try {
            await fetch(`${API_BASE}/env`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ key: key, value: val })
            });
            document.getElementById('envModal').classList.remove('active');
            e.target.reset();
            loadEnv(); // Refresh
        } catch (e) {
            alert('Error updating env');
        }
    });

    // Task Edit
    document.getElementById('editTaskForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        const taskId = document.getElementById('editTaskId').value;
        const desc = document.getElementById('editTaskDescription').value;

        try {
            await fetch(`${API_BASE}/tasks/${taskId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ description: desc })
            });
            document.getElementById('editTaskModal').classList.remove('active');
            refreshTasks(); // Refresh to show update
        } catch (e) {
            console.error(e);
            alert('Error updating task');
        }
    });

    // Workflow Run
    document.getElementById('runWorkflowBtn').addEventListener('click', () => {
        showConfirm('Run Workflow', 'Are you sure you want to run the default workflow?', async () => {
            try {
                const res = await fetch(`${API_BASE}/trigger-workflow`, { method: 'POST' });
                if (res.ok) alert('Workflow triggered!');
                else alert('Failed to trigger workflow');
            } catch (e) {
                console.error(e);
                alert('Error triggering workflow');
            }
        });
    });
}
