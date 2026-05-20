// ─── Chat — sesión, mensajes y envío ────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
    const form    = document.getElementById('chat-form');
    const input   = document.getElementById('user-input');
    const chatBox = document.getElementById('chat-box');

    // ── Sesión persistente entre recargas ──
    let sessionId = localStorage.getItem('mom_session_id') || (() => {
        const id = crypto.randomUUID();
        localStorage.setItem('mom_session_id', id);
        return id;
    })();

    // ── Renderizado de mensajes ──
    const addMessage = (message, isUser = false) => {
        const msgDiv = document.createElement('div');
        msgDiv.className = `message ${isUser ? 'user-message' : 'bot-message'}`;
        const avatar = isUser ? '' : `<div class="msg-avatar"><i class="fa-solid fa-robot"></i></div>`;
        msgDiv.innerHTML = `
            ${avatar}
            <div class="msg-bubble">${isUser ? `<p>${escHtml(message)}</p>` : renderMarkdown(message)}</div>
        `;
        chatBox.appendChild(msgDiv);
        chatBox.scrollTop = chatBox.scrollHeight;
    };

    const addTypingIndicator = () => {
        const msgDiv = document.createElement('div');
        msgDiv.id = 'typing-indicator';
        msgDiv.className = 'message bot-message typing-container';
        msgDiv.innerHTML = `
            <div class="msg-avatar"><i class="fa-solid fa-robot"></i></div>
            <div class="msg-bubble typing-indicator">
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
            </div>
        `;
        chatBox.appendChild(msgDiv);
        chatBox.scrollTop = chatBox.scrollHeight;
    };

    const removeTypingIndicator = () =>
        document.getElementById('typing-indicator')?.remove();

    // ── Limpiar chat (global — llamada desde HTML) ──
    window.clearChat = () => {
        sessionId = crypto.randomUUID();
        localStorage.setItem('mom_session_id', sessionId);
        chatBox.innerHTML = `
            <div class="message bot-message">
                <div class="msg-avatar"><i class="fa-solid fa-robot"></i></div>
                <div class="msg-bubble">
                    <p>Chat reiniciado. ¿En qué más te puedo ayudar sobre nuestro inventario?</p>
                </div>
            </div>`;
    };

    // ── Envío del formulario ──
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const msg = input.value.trim();
        if (!msg) return;

        addMessage(msg, true);
        input.value = '';
        input.focus();
        addTypingIndicator();

        try {
            const res = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: msg, session_id: sessionId }),
            });
            const data = await res.json();
            removeTypingIndicator();

            if (res.ok) {
                if (data.session_id) {
                    sessionId = data.session_id;
                    localStorage.setItem('mom_session_id', sessionId);
                }
                addMessage(data.reply, false);
                if (window.voiceSpeak) window.voiceSpeak(data.reply);
            } else {
                addMessage('Hubo un error al conectar con el servidor. Por favor, intenta de nuevo.', false);
            }
        } catch (err) {
            console.error('Error API:', err);
            removeTypingIndicator();
            addMessage('No pude conectarme al servidor. Verifica tu conexión de red.', false);
        }
    });

    input.focus();

    // ── Adjuntar imagen / cámara ───────────────────────────────────
    const imgInput      = document.getElementById('img-input');
    const attachmentBtn = document.getElementById('attachment-btn');

    attachmentBtn?.addEventListener('click', () => imgInput?.click());

    imgInput?.addEventListener('change', async () => {
        const file = imgInput.files[0];
        if (!file) return;

        // Preview en el chat
        const previewUrl = URL.createObjectURL(file);
        const previewDiv = document.createElement('div');
        previewDiv.className = 'message user-message';
        previewDiv.innerHTML = `
            <div class="msg-bubble msg-bubble--image">
                <img src="${previewUrl}" alt="imagen adjunta" class="chat-img-preview">
                ${input.value.trim() ? `<p>${escHtml(input.value.trim())}</p>` : ''}
            </div>`;
        chatBox.appendChild(previewDiv);
        chatBox.scrollTop = chatBox.scrollHeight;

        const userText = input.value.trim();
        input.value = '';
        addTypingIndicator();

        try {
            const fd = new FormData();
            fd.append('image', file);
            fd.append('message', userText);
            fd.append('session_id', sessionId);

            const res  = await fetch('/api/chat/image', { method: 'POST', body: fd });
            const data = await res.json();
            removeTypingIndicator();

            if (res.ok) {
                if (data.session_id) {
                    sessionId = data.session_id;
                    localStorage.setItem('mom_session_id', sessionId);
                }
                addMessage(data.reply, false);
                if (window.voiceSpeak) window.voiceSpeak(data.reply);
            } else {
                addMessage('Error al analizar la imagen. Intenta de nuevo.', false);
            }
        } catch {
            removeTypingIndicator();
            addMessage('No se pudo conectar. Revisa tu conexión.', false);
        } finally {
            imgInput.value = '';
            URL.revokeObjectURL(previewUrl);
        }
    });
});
