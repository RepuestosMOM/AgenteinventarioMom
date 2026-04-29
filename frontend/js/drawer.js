// ─── Ficha técnica — drawer lateral ─────────────────────────────

// ── Abrir ficha de producto (global — llamada desde HTML) ──
window.openProduct = async (id) => {
    const drawer = document.getElementById('product-drawer');
    const body   = document.getElementById('drawer-body');
    const title  = document.getElementById('drawer-name');

    drawer.classList.add('open');
    body.innerHTML = '<p class="drawer-loading">Cargando...</p>';
    title.textContent = '—';

    try {
        const res = await fetch(`/api/product/${id}`);
        const p   = await res.json();
        title.textContent = p.name;

        const stockClass = p.stock > 0 ? 'stock-ok' : 'stock-cero';
        const stockLabel = p.stock > 0 ? `${p.stock} unidades disponibles` : 'Sin stock';

        const field = (label, value) => value
            ? `<div class="detail-row">
                   <span class="detail-label">${label}</span>
                   <span class="detail-value">${escHtml(String(value))}</span>
               </div>`
            : '';

        const hasAttrs = Object.keys(p.attrs || {}).length > 0;

        body.innerHTML = `
            <div class="detail-badge ${p.stock > 0 ? 'badge-ok' : 'badge-empty'}">
                ${p.stock > 0 ? '✅ En stock' : '❌ Sin stock'}
            </div>

            <div class="detail-section">
                <h3>Disponibilidad y Precio</h3>
                <div class="detail-row">
                    <span class="detail-label">Stock</span>
                    <span class="detail-value ${stockClass}">${stockLabel}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Precio</span>
                    <span class="detail-value detail-price">
                        $${Number(p.price).toLocaleString('es-CL')} CLP
                    </span>
                </div>
            </div>

            <div class="detail-section">
                <h3>Identificación</h3>
                ${field('Referencia interna', p.code)}
                ${field('Código de barras', p.barcode)}
                ${field('N° de pieza', p.part_number)}
                ${field('Categoría', p.category)}
                ${field('Marca', p.brand)}
            </div>

            ${hasAttrs ? `
            <div class="detail-section">
                <h3>Ficha Técnica</h3>
                ${field('Código OEM',       p.attrs.oem)}
                ${field('Modelo',           p.attrs.model)}
                ${field('Tipo de vehículo', p.attrs.type)}
                ${field('Diámetro interior',p.attrs.diam_int)}
                ${field('Diámetro externo', p.attrs.diam_ext)}
                ${field('Espesor',          p.attrs.thickness)}
            </div>` : ''}

            ${p.description ? `
            <div class="detail-section">
                <h3>Descripción</h3>
                <p class="detail-description">${escHtml(p.description)}</p>
            </div>` : ''}

            ${p.ai_description ? `
            <div class="detail-section detail-section--ai">
                <h3>✨ Contenido IA${p.ai_title ? ` — ${escHtml(p.ai_title)}` : ''}</h3>
                <p class="detail-ai-body">${escHtml(p.ai_description)}</p>
            </div>` : ''}
        `;
    } catch (e) {
        body.innerHTML = '<p class="drawer-error">Error cargando ficha</p>';
    }
};

// ── Cerrar drawer (global — llamada desde HTML) ──
window.closeDrawer = (e) => {
    if (!e || e.target === document.getElementById('product-drawer')) {
        document.getElementById('product-drawer').classList.remove('open');
    }
};
