// ─── Voice — captura de audio y reproducción ─────────────────────

(function () {
    const micBtn         = document.getElementById('mic-btn');
    const voiceToggleBtn = document.getElementById('voice-response-toggle');
    const input          = document.getElementById('user-input');
    const form           = document.getElementById('chat-form');
    const inputWrapper   = input?.closest('.input-wrapper');

    if (!micBtn) return;

    // ── Estado ─────────────────────────────────────────────────────
    let mediaRecorder      = null;
    let audioChunks        = [];
    let isRecording        = false;
    let voiceResponseEnabled = false;
    let currentAudio       = null;

    // ── Utilidades visuales ────────────────────────────────────────
    const setRecording = (active) => {
        isRecording = active;
        micBtn.classList.toggle('recording', active);
        inputWrapper?.classList.toggle('listening', active);
        micBtn.title = active ? 'Detener grabación' : 'Hablar';
        input.placeholder = active
            ? 'Escuchando… habla ahora'
            : 'Pregunta por disponibilidad de repuestos...';
    };

    // ── Inicio de grabación ────────────────────────────────────────
    const startRecording = async () => {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

            // Preferir webm/opus (Chrome); Safari usará mp4
            const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
                ? 'audio/webm;codecs=opus'
                : MediaRecorder.isTypeSupported('audio/webm')
                    ? 'audio/webm'
                    : 'audio/mp4';

            mediaRecorder = new MediaRecorder(stream, { mimeType });
            audioChunks   = [];

            mediaRecorder.addEventListener('dataavailable', (e) => {
                if (e.data.size > 0) audioChunks.push(e.data);
            });

            mediaRecorder.addEventListener('stop', async () => {
                stream.getTracks().forEach(t => t.stop());
                const blob = new Blob(audioChunks, { type: mimeType });
                await sendAudioForTranscription(blob, mimeType);
            });

            mediaRecorder.start();
            setRecording(true);
        } catch (err) {
            if (err.name === 'NotAllowedError') {
                alert('Permiso de micrófono denegado. Habilítalo en la configuración del navegador.');
            } else {
                console.error('Error al acceder al micrófono:', err);
            }
        }
    };

    // ── Detener grabación ──────────────────────────────────────────
    const stopRecording = () => {
        if (mediaRecorder && mediaRecorder.state !== 'inactive') {
            mediaRecorder.stop();
        }
        setRecording(false);
    };

    // ── Enviar audio al backend ────────────────────────────────────
    const sendAudioForTranscription = async (blob, mimeType) => {
        micBtn.disabled = true;
        micBtn.classList.add('processing');

        try {
            const formData = new FormData();
            const ext      = mimeType.includes('mp4') ? 'mp4' : 'webm';
            formData.append('audio', blob, `recording.${ext}`);

            const res  = await fetch('/api/voice/transcribe', { method: 'POST', body: formData });
            const data = await res.json();

            if (res.ok && data.text) {
                input.value = data.text;
                // Breve pausa para que el usuario vea el texto antes de enviar
                setTimeout(() => form.dispatchEvent(new Event('submit')), 900);
            } else {
                input.placeholder = 'No se entendió el audio. Intenta de nuevo.';
                setTimeout(() => {
                    input.placeholder = 'Pregunta por disponibilidad de repuestos...';
                }, 3000);
            }
        } catch (err) {
            console.error('Error transcribiendo:', err);
        } finally {
            micBtn.disabled = false;
            micBtn.classList.remove('processing');
        }
    };

    // ── Botón micrófono ────────────────────────────────────────────
    micBtn.addEventListener('click', () => {
        if (isRecording) {
            stopRecording();
        } else {
            input.value = '';
            startRecording();
        }
    });

    // ── Respuesta en voz ───────────────────────────────────────────
    if (voiceToggleBtn) {
        voiceToggleBtn.addEventListener('click', () => {
            voiceResponseEnabled = !voiceResponseEnabled;
            voiceToggleBtn.classList.toggle('voice-active', voiceResponseEnabled);
            voiceToggleBtn.title = voiceResponseEnabled
                ? 'Desactivar respuesta en voz'
                : 'Activar respuesta en voz';

            if (!voiceResponseEnabled && currentAudio) {
                currentAudio.pause();
                currentAudio = null;
            }
        });
    }

    // voiceSpeak: llamada desde chat.js después de recibir respuesta del bot
    window.voiceSpeak = async (text) => {
        if (!voiceResponseEnabled) return;
        try {
            const res = await fetch('/api/voice/synthesize', {
                method:  'POST',
                headers: { 'Content-Type': 'application/json' },
                body:    JSON.stringify({ text }),
            });
            if (!res.ok) return;

            const blob = await res.blob();
            const url  = URL.createObjectURL(blob);

            if (currentAudio) {
                currentAudio.pause();
                URL.revokeObjectURL(currentAudio.src);
            }
            currentAudio = new Audio(url);
            currentAudio.addEventListener('ended', () => {
                URL.revokeObjectURL(url);
                currentAudio = null;
            });
            currentAudio.play().catch(() => {});
        } catch (err) {
            console.error('Error en síntesis de voz:', err);
        }
    };
}());
