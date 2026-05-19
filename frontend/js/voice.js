// ─── Voice — PCM recorder universal + Cloud STT/TTS ──────────────

(function () {
    const micBtn         = document.getElementById('mic-btn');
    const voiceToggleBtn = document.getElementById('voice-response-toggle');
    const input          = document.getElementById('user-input');
    const form           = document.getElementById('chat-form');
    const inputWrapper   = input?.closest('.input-wrapper');

    if (!micBtn) return;

    let isRecording        = false;
    let voiceResponseEnabled = false;
    let currentAudio       = null;
    let stopFn             = null;
    let autoStopTimer      = null;

    // ── Codificación WAV (LINEAR16 16kHz) ─────────────────────────
    // Funciona en Chrome, Firefox y Safari/iOS sin dependencias externas

    const mergeFloat32 = (chunks) => {
        const total  = chunks.reduce((s, c) => s + c.length, 0);
        const merged = new Float32Array(total);
        let offset   = 0;
        for (const c of chunks) { merged.set(c, offset); offset += c.length; }
        return merged;
    };

    const encodeWAV = (samples, rate) => {
        const buf  = new ArrayBuffer(44 + samples.length * 2);
        const view = new DataView(buf);
        const str  = (off, s) => { for (let i = 0; i < s.length; i++) view.setUint8(off + i, s.charCodeAt(i)); };
        str(0,  'RIFF');  view.setUint32(4,  36 + samples.length * 2, true);
        str(8,  'WAVE');  str(12, 'fmt ');
        view.setUint32(16, 16,       true); // PCM
        view.setUint16(20, 1,        true); // PCM
        view.setUint16(22, 1,        true); // mono
        view.setUint32(24, rate,     true);
        view.setUint32(28, rate * 2, true);
        view.setUint16(32, 2,        true);
        view.setUint16(34, 16,       true);
        str(36, 'data');  view.setUint32(40, samples.length * 2, true);
        let off = 44;
        for (let i = 0; i < samples.length; i++) {
            const s = Math.max(-1, Math.min(1, samples[i]));
            view.setInt16(off, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
            off += 2;
        }
        return buf;
    };

    // ── Grabador PCM con Web Audio API ────────────────────────────
    const createPCMRecorder = async () => {
        const RATE   = 16000;
        const stream = await navigator.mediaDevices.getUserMedia({
            audio: { sampleRate: RATE, channelCount: 1, echoCancellation: true, noiseSuppression: true }
        });
        const ctx    = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: RATE });
        const src    = ctx.createMediaStreamSource(stream);
        const proc   = ctx.createScriptProcessor(4096, 1, 1);
        const chunks = [];

        proc.onaudioprocess = (e) => chunks.push(new Float32Array(e.inputBuffer.getChannelData(0)));
        src.connect(proc);
        proc.connect(ctx.destination);

        return () => {                          // devuelve función de parada
            proc.disconnect(); src.disconnect();
            ctx.close();
            stream.getTracks().forEach(t => t.stop());
            return new Blob([encodeWAV(mergeFloat32(chunks), RATE)], { type: 'audio/wav' });
        };
    };

    // ── Visual feedback ───────────────────────────────────────────
    const setRecording = (active) => {
        isRecording = active;
        micBtn.classList.toggle('recording', active);
        inputWrapper?.classList.toggle('listening', active);
        input.placeholder = active
            ? 'Escuchando… habla ahora'
            : 'Pregunta por disponibilidad de repuestos...';
    };

    // ── Iniciar grabación ─────────────────────────────────────────
    const startRecording = async () => {
        try {
            stopFn = await createPCMRecorder();
            setRecording(true);
            autoStopTimer = setTimeout(stopRecording, 12000); // máx 12s
        } catch (err) {
            if (err.name === 'NotAllowedError') {
                alert('Permiso de micrófono denegado. Habilítalo en la configuración del navegador.');
            } else {
                console.error('Micrófono:', err);
            }
        }
    };

    // ── Detener y transcribir ─────────────────────────────────────
    const stopRecording = async () => {
        if (!isRecording || !stopFn) return;
        clearTimeout(autoStopTimer);
        setRecording(false);

        const blob = stopFn();
        stopFn = null;

        if (blob.size < 3000) return; // demasiado corto

        await transcribe(blob);
    };

    // ── Enviar al backend ─────────────────────────────────────────
    const transcribe = async (blob) => {
        micBtn.disabled = true;
        micBtn.classList.add('processing');

        try {
            const fd = new FormData();
            fd.append('audio', blob, 'audio.wav');

            const res  = await fetch('/api/voice/transcribe', { method: 'POST', body: fd });
            const data = await res.json();

            if (res.ok && data.text) {
                input.value = data.text;
                setTimeout(() => form.dispatchEvent(new Event('submit')), 800);
            } else {
                showHint('No se entendió. Habla más claro y cerca del micrófono.');
            }
        } catch {
            showHint('Error de conexión. Intenta de nuevo.');
        } finally {
            micBtn.disabled = false;
            micBtn.classList.remove('processing');
        }
    };

    const showHint = (msg) => {
        input.placeholder = msg;
        setTimeout(() => { input.placeholder = 'Pregunta por disponibilidad de repuestos...'; }, 3500);
    };

    // ── Click micrófono ───────────────────────────────────────────
    micBtn.addEventListener('click', () => {
        if (isRecording) stopRecording();
        else { input.value = ''; startRecording(); }
    });

    // ── Toggle respuesta en voz ───────────────────────────────────
    if (voiceToggleBtn) {
        voiceToggleBtn.addEventListener('click', () => {
            voiceResponseEnabled = !voiceResponseEnabled;
            voiceToggleBtn.classList.toggle('voice-active', voiceResponseEnabled);
            const icon = voiceToggleBtn.querySelector('i');
            if (icon) icon.className = voiceResponseEnabled ? 'fa-solid fa-volume-high' : 'fa-solid fa-volume-xmark';
            voiceToggleBtn.title = voiceResponseEnabled ? 'Desactivar respuesta en voz' : 'Activar respuesta en voz';
            if (!voiceResponseEnabled && currentAudio) { currentAudio.pause(); currentAudio = null; }
        });
    }

    // ── Síntesis (llamada desde chat.js) ──────────────────────────
    window.voiceSpeak = async (text) => {
        if (!voiceResponseEnabled) return;
        try {
            const res = await fetch('/api/voice/synthesize', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text }),
            });
            if (!res.ok) return;
            const url = URL.createObjectURL(await res.blob());
            if (currentAudio) { currentAudio.pause(); URL.revokeObjectURL(currentAudio.src); }
            currentAudio = new Audio(url);
            currentAudio.addEventListener('ended', () => { URL.revokeObjectURL(url); currentAudio = null; });
            currentAudio.play().catch(() => {});
        } catch (err) { console.error('TTS:', err); }
    };
}());
