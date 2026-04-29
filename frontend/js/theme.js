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
    const saved = localStorage.getItem('theme');
    applyTheme(saved === 'light' ? 'light' : 'dark');
    _THEME_BTNS.forEach(id => {
        document.getElementById(id)?.addEventListener('click', toggleTheme);
    });
});
