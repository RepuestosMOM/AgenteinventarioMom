document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('chat-form');
    const input = document.getElementById('user-input');
    const chatBox = document.getElementById('chat-box');
    const themeToggle = document.getElementById('theme-toggle');
    
    // Theme logic
    const toggleTheme = () => {
        const currentTheme = document.documentElement.getAttribute('data-theme');
        const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
        document.documentElement.setAttribute('data-theme', newTheme);
        themeToggle.innerHTML = newTheme === 'dark' ? '<i class="fa-solid fa-sun"></i>' : '<i class="fa-solid fa-moon"></i>';
        localStorage.setItem('theme', newTheme);
    };

    // Load saved theme
    if (localStorage.getItem('theme') === 'dark' || (!window.localStorage.getItem('theme') && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
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
                body: JSON.stringify({ message: msg })
            });

            const data = await response.json();
            removeTypingIndicator();
            
            if (response.ok) {
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
