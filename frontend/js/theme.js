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

    // ── Sidebar colapsable (desktop) ──────────────────────────────
    const sidebar    = document.getElementById('sidebar');
    const toggleBtn  = document.getElementById('sidebar-toggle');
    const toggleIcon = document.getElementById('sidebar-toggle-icon');
    const backdrop   = document.getElementById('sidebar-backdrop');

    if (!sidebar) return;

    const applyCollapsed = (collapsed) => {
        sidebar.classList.toggle('sidebar--collapsed', collapsed);
        if (toggleIcon) {
            toggleIcon.className = collapsed
                ? 'fa-solid fa-chevron-right'
                : 'fa-solid fa-chevron-left';
        }
        if (toggleBtn) toggleBtn.title = collapsed ? 'Expandir menú' : 'Colapsar menú';
        localStorage.setItem('sidebar_collapsed', collapsed ? '1' : '0');
    };

    applyCollapsed(localStorage.getItem('sidebar_collapsed') === '1');

    toggleBtn?.addEventListener('click', (e) => {
        e.stopPropagation();
        applyCollapsed(!sidebar.classList.contains('sidebar--collapsed'));
    });

    // ── Sidebar drawer (móvil) ────────────────────────────────────
    const openMobileSidebar = () => {
        sidebar.classList.add('mobile-open');
        backdrop?.classList.add('open');
    };

    const closeMobileSidebar = () => {
        sidebar.classList.remove('mobile-open');
        backdrop?.classList.remove('open');
    };

    document.getElementById('hamburger-btn')?.addEventListener('click', openMobileSidebar);
    document.getElementById('hamburger-btn-catalog')?.addEventListener('click', openMobileSidebar);
    backdrop?.addEventListener('click', closeMobileSidebar);

    // Cerrar al seleccionar una vista en móvil
    window._closeMobileSidebar = closeMobileSidebar;
});
