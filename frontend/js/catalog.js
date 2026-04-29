// ─── Catálogo — tabla, paginación y filtro ──────────────────────

let catalogPage = 1;

// ── Navegación entre vistas (global — llamada desde HTML) ──
window.showView = (view) => {
    document.getElementById('view-chat').style.display    = view === 'chat'    ? 'flex' : 'none';
    document.getElementById('view-catalog').style.display = view === 'catalog' ? 'flex' : 'none';
    document.getElementById('nav-chat').classList.toggle('active',    view === 'chat');
    document.getElementById('nav-catalog').classList.toggle('active', view === 'catalog');
    if (view === 'catalog') loadCatalog(1);
};

// ── Carga del catálogo (global — llamada desde HTML y paginación) ──
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
            <tr class="catalog-row ${p.stock <= 0 ? 'sin-stock' : ''}" onclick="openProduct(${p.id})">
                <td>${escHtml(p.name)}</td>
                <td><code>${escHtml(p.code)}</code></td>
                <td>${escHtml(p.category)}</td>
                <td class="${p.stock > 0 ? 'stock-ok' : 'stock-cero'}">
                    ${p.stock > 0 ? p.stock + ' uds' : 'Sin stock'}
                </td>
                <td>$${Number(p.price).toLocaleString('es-CL')} CLP</td>
            </tr>`).join('');

        renderPagination(data.total, page, 50);
    } catch (e) {
        tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:red;">Error cargando catálogo</td></tr>';
    }
};

// ── Paginación ──
const renderPagination = (total, current, limit) => {
    const pages = Math.ceil(total / limit);
    const div   = document.getElementById('catalog-pagination');
    if (pages <= 1) { div.innerHTML = ''; return; }

    let html = '';
    if (current > 1)
        html += `<button onclick="loadCatalog(${current - 1})">← Anterior</button>`;
    html += `<span>Página ${current} de ${pages}</span>`;
    if (current < pages)
        html += `<button onclick="loadCatalog(${current + 1})">Siguiente →</button>`;
    div.innerHTML = html;
};
