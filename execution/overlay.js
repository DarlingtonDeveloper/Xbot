function injectOverlay() {
    if (document.getElementById('jarvis-overlay')) return;

    const fontLink = document.createElement('link');
    fontLink.rel = 'stylesheet';
    fontLink.href = 'https://fonts.googleapis.com/css2?family=Inter:wght@400;500&display=swap';
    document.head.appendChild(fontLink);

    const style = document.createElement('style');
    style.textContent = `
        #transcription-text {
            transition: opacity 0.3s ease-out, transform 0.3s ease-out;
            background: linear-gradient(to bottom, #86efac, #4ade80);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            filter: drop-shadow(0px 2px 4px rgba(74,222,128,0.4));
            font-size: 22px;
            font-family: 'Inter', sans-serif;
            font-weight: 400;
            letter-spacing: -0.01em;
            text-align: center;
            padding-bottom: 8px;
        }
    `;
    document.head.appendChild(style);

    const container = document.createElement('div');
    container.id = 'jarvis-overlay';
    container.style = 'position:fixed; bottom:0; left:0; width:100%; height:150px; z-index:9999; pointer-events:none; background: linear-gradient(transparent, rgba(0,0,0,0.8));';
    container.innerHTML = `
        <div id="transcription-text"></div>
        <canvas id="audio-visualizer" style="width:100%; height:80px; display:block;"></canvas>
    `;
    document.documentElement.appendChild(container);

    async function setupAudio() {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        const audioCtx = new AudioContext();
        const source = audioCtx.createMediaStreamSource(stream);
        const analyser = audioCtx.createAnalyser();
        analyser.fftSize = 256;
        source.connect(analyser);

        const canvas = document.getElementById('audio-visualizer');
        const ctx = canvas.getContext('2d');
        const dataArray = new Uint8Array(analyser.frequencyBinCount);
        let step = 0;

        function drawWave(color, opacity, freq, phase, amp) {
            ctx.beginPath();
            ctx.strokeStyle = color;
            ctx.globalAlpha = opacity;
            ctx.lineWidth = 2;
            ctx.shadowBlur = 15;
            ctx.shadowColor = color;
            for (let x = 0; x < canvas.width; x++) {
                const envelope = Math.sin((x / canvas.width) * Math.PI);
                const y = (canvas.height / 2) + Math.sin(x * freq + phase) * amp * envelope;
                if (x === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
            }
            ctx.stroke();
            ctx.globalAlpha = 1;
            ctx.shadowBlur = 0;
        }

        function draw() {
            requestAnimationFrame(draw);
            analyser.getByteFrequencyData(dataArray);
            const average = dataArray.reduce((a, b) => a + b) / dataArray.length;
            const amplitude = average * 0.8;
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            drawWave('#00f2ff', 1.0, 0.02,  step,       amplitude);
            drawWave('#7000ff', 0.5, 0.015, step * 0.8, amplitude * 0.6);
            drawWave('#ffffff', 0.3, 0.01,  step * 1.2, amplitude * 0.4);
            step += 0.1;
        }
        draw();
    }
    setupAudio();
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', injectOverlay);
} else {
    injectOverlay();
}
