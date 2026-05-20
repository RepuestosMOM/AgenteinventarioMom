// ─── Tema dark/light ────────────────────────────────────────────

const _THEME_BTNS = ['theme-toggle', 'theme-toggle2'];

const applyTheme = (theme) => {
    document.documentElement.setAttribute('data-theme', theme);
    const icon = theme === 'dark'
        ? '<i class="fa-solid fa-sun"></i>'
        : '<i class="fa-solid fa-moon"></i>';
    _THEME_BTNS.forEach(id => {
        const el = document.getElementById(id);
        if (el) el.innerHTML = icon;
    });
    localStorage.setItem('theme', theme);
};

const toggleTheme = () => {
    const current = document.documentElement.getAttribute('data-theme');
    applyTheme(current === 'dark' ? 'light' : 'dark');
};

document.addEventListener('DOMContentLoaded', () => {
    // ── Tema ──────────────────────────────────────────────────────
    const saved = localStorage.getItem('theme');
    applyTheme(saved === 'light' ? 'light' : 'dark');
    _THEME_BTNS.forEach(id => {
        document.getElementById(id)?.addEventListener('click', toggleTheme);
    });

    // ── Sidebar colapsable ────────────────────────────────────────
    const sidebar    = document.getElementById('sidebar');
    const toggleBtn  = document.getElementById('sidebar-toggle');
    const toggleIcon = document.getElementById('sidebar-toggle-icon');

    if (!sidebar || !toggleBtn) return;

    const applyCollapsed = (collapsed) => {
        sidebar.classList.toggle('sidebar--collapsed', collapsed);
        if (toggleIcon) {
            toggleIcon.className = collapsed
                ? 'fa-solid fa-chevron-right'
                : 'fa-solid fa-chevron-left';
        }
        toggleBtn.title = collapsed ? 'Expandir menú' : 'Colapsar menú';
        localStorage.setItem('sidebar_collapsed', collapsed ? '1' : '0');
    };

    // Restaurar estado guardado
    applyCollapsed(localStorage.getItem('sidebar_collapsed') === '1');

    toggleBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        applyCollapsed(!sidebar.classList.contains('sidebar--collapsed'));
    });
});
