/**
 * Temporal Agent Dashboard - Task Page Logic
 */

const API_BASE = window.location.origin + '/api';
const urlParams = new URLSearchParams(window.location.search);
const TASK_ID = urlParams.get('id');

// Formatting Helper
function formatDate(isoString) {
    if (!isoString) return '-';
    return new Date(isoString).toLocaleString('en-US', {
        month: 'short', day: 'numeric',
        hour: 'numeric', minute: '2-digit'
    });
}

// Initialization
document.addEventListener('DOMContentLoaded', () => {
    if (!TASK_ID) {
        alert('No Task ID provided');
        window.location.href = '/static/index.html';
        return;
    }

    loadTaskDetails();
    setupTabs();
});

// Load Data
async function loadTaskDetails() {
    try {
        // Fetch Task
        const res = await fetch(`${API_BASE}/tasks`); // Retrieve all to find one (inefficient but API limited)
        const data = await res.json();
        const task = data.tasks.find(t => t.task_id === TASK_ID);

        if (!task) {
            document.body.innerHTML = '<h1 style="padding: 50px; text-align: center;">Task not found</h1>';
            return;
        }

        renderMetadata(task);
        renderLogs(task);
        loadFiles(task.task_id);

    } catch (e) {
        console.error(e);
        alert('Error loading task');
    }
}

function renderMetadata(task) {
    document.getElementById('task-id-display').textContent = task.task_id;
    document.getElementById('task-desc-display').textContent = task.description;

    // Status Badge
    const badge = document.getElementById('status-badge');
    badge.className = `status-badge ${task.status}`;
    badge.textContent = task.status.toUpperCase();

    // Stats
    document.getElementById('meta-created').textContent = formatDate(task.created_at);
    document.getElementById('meta-started').textContent = formatDate(task.start_time);
    document.getElementById('meta-completed').textContent = formatDate(task.end_time);
    document.getElementById('meta-workflow').textContent = task.workflow_id || '-';
}

function renderLogs(task) {
    const logsContainer = document.getElementById('logs-content');
    if (task.output) {
        logsContainer.textContent = task.output;
    } else {
        logsContainer.innerHTML = '<span style="color: #666;">No execution logs available.</span>';
    }

    if (task.error_message) {
        logsContainer.innerHTML += `\n\n<span style="color: red;">ERROR:\n${task.error_message}</span>`;
    }
}

async function loadFiles(taskId) {
    const listContainer = document.getElementById('file-list');
    listContainer.innerHTML = '<div style="padding: 20px; color: #666;">Loading files...</div>';

    try {
        const res = await fetch(`${API_BASE}/tasks/${taskId}/files`);
        const data = await res.json();
        const files = data.files || [];

        if (files.length === 0) {
            listContainer.innerHTML = '<div style="padding: 20px; color: #666; text-align: center;">No generated files</div>';
            return;
        }

        listContainer.innerHTML = '';
        files.forEach(file => {
            const item = document.createElement('div');
            item.className = 'file-item';
            item.innerHTML = `
                <span class="file-icon">📄</span>
                <span class="file-name">${file.name}</span>
                <span class="file-size">${(file.size / 1024).toFixed(1)} KB</span>
            `;
            item.onclick = () => previewFile(file);
            listContainer.appendChild(item);
        });

        // Auto-preview first file
        if (files.length > 0) {
            previewFile(files[0]);
        }

    } catch (e) {
        listContainer.innerHTML = '<div style="padding: 20px; color: red;">Error loading files</div>';
    }
}

function previewFile(file) {
    const previewContainer = document.getElementById('preview-pane');
    const title = document.getElementById('preview-filename');
    const downloadBtn = document.getElementById('preview-download');

    title.textContent = file.name;
    downloadBtn.href = file.url;
    previewContainer.innerHTML = '';

    // Highlight active item
    document.querySelectorAll('.file-item').forEach(el => el.classList.remove('active'));
    // (Simpler to just re-render list with active class, but let's skip visual active state for now or use event.target logic)

    const ext = file.name.split('.').pop().toLowerCase();

    if (['html', 'htm'].includes(ext)) {
        const iframe = document.createElement('iframe');
        iframe.src = file.url;
        previewContainer.appendChild(iframe);
    } else if (['jpg', 'jpeg', 'png', 'gif', 'svg'].includes(ext)) {
        const img = document.createElement('img');
        img.src = file.url;
        previewContainer.appendChild(img);
    } else {
        // Text/Code
        fetch(file.url)
            .then(res => res.text())
            .then(text => {
                const pre = document.createElement('pre');
                pre.textContent = text;
                previewContainer.appendChild(pre);
            })
            .catch(() => {
                previewContainer.innerHTML = '<div style="padding: 20px; color: red;">Failed to load content</div>';
            });
    }
}

// Tabs
function setupTabs() {
    const tabs = document.querySelectorAll('.tab-btn');
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            tabs.forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.style.display = 'none');

            tab.classList.add('active');
            const target = tab.dataset.tab;
            document.getElementById(`tab-${target}`).style.display = (target === 'files' ? 'flex' : 'block');
        });
    });
}
