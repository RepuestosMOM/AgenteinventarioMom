document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('chat-form');
    const input = document.getElementById('user-input');
    const chatBox = document.getElementById('chat-box');
    const themeToggle = document.getElementById('theme-toggle');

    // Mantener sesión persistente entre recargas
    let sessionId = localStorage.getItem('mom_session_id');
    if (!sessionId) {
        sessionId = crypto.randomUUID();
        localStorage.setItem('mom_session_id', sessionId);
    }
    
    // Theme logic
    const toggleTheme = () => {
        const currentTheme = document.documentElement.getAttribute('data-theme');
        const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
        document.documentElement.setAttribute('data-theme', newTheme);
        themeToggle.innerHTML = newTheme === 'dark' ? '<i class="fa-solid fa-sun"></i>' : '<i class="fa-solid fa-moon"></i>';
        localStorage.setItem('theme', newTheme);
    };

    // Load saved theme
    const savedTheme = localStorage.getItem('theme');
    if (savedTheme === 'dark' || !savedTheme) {
        document.documentElement.setAttribute('data-theme', 'dark');
        themeToggle.innerHTML = '<i class="fa-solid fa-sun"></i>';
    }

    themeToggle.addEventListener('click', toggleTheme);

    // Escape HTML to prevent XSS
    const escapeHtml = (unsafe) => {
        return unsafe.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    };

    // Parse bold text **text** into <strong>text</strong> (Basic markdown support)
    const renderMarkdown = (text) => {
        let html = escapeHtml(text);
        html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        html = html.replace(/\*(.*?)\*/g, '<em>$1</em>');
        html = html.replace(/\n\n/g, '</p><p>');
        html = html.replace(/\n/g, '<br>');
        return `<p>${html}</p>`;
    };

    const addMessage = (message, isUser = false) => {
        const msgDiv = document.createElement('div');
        msgDiv.className = `message ${isUser ? 'user-message' : 'bot-message'}`;
        
        let avatarHTML = isUser ? '' : `<div class="msg-avatar"><i class="fa-solid fa-robot"></i></div>`;
        
        msgDiv.innerHTML = `
            ${avatarHTML}
            <div class="msg-bubble">${isUser ? `<p>${escapeHtml(message)}</p>` : renderMarkdown(message)}</div>
        `;
        
        chatBox.appendChild(msgDiv);
        scrollToBottom();
    };

    const addTypingIndicator = () => {
        const msgDiv = document.createElement('div');
        msgDiv.className = `message bot-message typing-container`;
        msgDiv.id = 'typing-indicator';
        msgDiv.innerHTML = `
            <div class="msg-avatar"><i class="fa-solid fa-robot"></i></div>
            <div class="msg-bubble typing-indicator">
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
            </div>
        `;
        chatBox.appendChild(msgDiv);
        scrollToBottom();
    };

    const removeTypingIndicator = () => {
        const ind = document.getElementById('typing-indicator');
        if (ind) ind.remove();
    };

    const scrollToBottom = () => {
        chatBox.scrollTop = chatBox.scrollHeight;
    };

    window.clearChat = () => {
        // Nueva sesión al limpiar el chat
        sessionId = crypto.randomUUID();
        localStorage.setItem('mom_session_id', sessionId);
        chatBox.innerHTML = `
        <div class="message bot-message">
            <div class="msg-avatar"><i class="fa-solid fa-robot"></i></div>
            <div class="msg-bubble">
                <p>Chat reiniciado. ¿En qué más te puedo ayudar sobre nuestro inventario?</p>
            </div>
        </div>
        `;
    };

    // Form submit
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const msg = input.value.trim();
        if (!msg) return;

        // User message
        addMessage(msg, true);
        input.value = '';
        input.focus();

        // Show typing
        addTypingIndicator();

        try {
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: msg, session_id: sessionId })
            });

            const data = await response.json();
            removeTypingIndicator();

            if (response.ok) {
                // Persistir session_id devuelto por el servidor
                if (data.session_id) {
                    sessionId = data.session_id;
                    localStorage.setItem('mom_session_id', sessionId);
                }
                addMessage(data.reply, false);
            } else {
                addMessage("Hubo un error al conectar con el servidor Odoo. Por favor, intenta de nuevo.", false);
            }

        } catch (err) {
            console.error("Error API:", err);
            removeTypingIndicator();
            addMessage("Lo siento, no pude conectarme al servidor. Verifica tu conexión de red.", false);
        }
    });

    // Auto-focus input
    input.focus();
});

// ── Vista de catálogo ────────────────────────────────────────────
let catalogPage = 1;

window.showView = (view) => {
    document.getElementById('view-chat').style.display    = view === 'chat'    ? 'flex' : 'none';
    document.getElementById('view-catalog').style.display = view === 'catalog' ? 'flex' : 'none';
    document.getElementById('nav-chat').classList.toggle('active',    view === 'chat');
    document.getElementById('nav-catalog').classList.toggle('active', view === 'catalog');
    if (view === 'catalog') loadCatalog(1);
};

// Sincronizar botón de tema en vista catálogo
document.getElementById('theme-toggle2')?.addEventListener('click', () => {
    document.getElementById('theme-toggle').click();
});

window.loadCatalog = async (page = 1) => {
    catalogPage = page;
    const soloStock = document.getElementById('filter-stock').checked;
    const tbody = document.getElementById('catalog-body');
    tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;padding:24px;">Cargando...</td></tr>';

    try {
        const res  = await fetch(`/api/catalog?page=${page}&limit=50&solo_con_stock=${soloStock}`);
        const data = await res.json();

        document.getElementById('catalog-subtitle').textContent =
            `${data.total.toLocaleString()} productos en total`;

        tbody.innerHTML = data.products.map(p => `
            <tr class="${p.stock <= 0 ? 'sin-stock' : ''}">
                <td>${escHtml(p.name)}</td>
                <td><code>${escHtml(p.code)}</code></td>
                <td>${escHtml(p.category)}</td>
                <td class="${p.stock > 0 ? 'stock-ok' : 'stock-cero'}">${p.stock > 0 ? p.stock + ' uds' : 'Sin stock'}</td>
                <td>$${Number(p.price).toLocaleString('es-CL')} CLP</td>
            </tr>`).join('');

        renderPagination(data.total, page, 50);
    } catch (e) {
        tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:red;">Error cargando catálogo</td></tr>';
    }
};

const renderPagination = (total, current, limit) => {
    const pages = Math.ceil(total / limit);
    const div   = document.getElementById('catalog-pagination');
    if (pages <= 1) { div.innerHTML = ''; return; }

    let html = '';
    if (current > 1) html += `<button onclick="loadCatalog(${current - 1})">← Anterior</button>`;
    html += `<span>Página ${current} de ${pages}</span>`;
    if (current < pages) html += `<button onclick="loadCatalog(${current + 1})">Siguiente →</button>`;
    div.innerHTML = html;
};

const escHtml = (s) => String(s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
