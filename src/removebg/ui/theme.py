import gradio as gr

# Fonts are system fonts only so the app stays fully offline.
FONT = [gr.themes.Font("Segoe UI Variable Display"), gr.themes.Font("Segoe UI"), "system-ui", "sans-serif"]
MONO = [gr.themes.Font("Cascadia Mono"), gr.themes.Font("Consolas"), "monospace"]

THEME_JS = """() => {
    function getTheme() {
        return localStorage.getItem('removebg-theme') || 'teal-dark';
    }
    function apply(theme) {
        const isCream = theme === 'cream';
        document.documentElement.classList.toggle('theme-cream', isCream);
        document.body.classList.toggle('theme-cream', isCream);
        document.documentElement.classList.toggle('dark', !isCream);
        document.body.classList.toggle('dark', !isCream);
        const app = document.querySelector('gradio-app');
        if (app) {
            app.classList.toggle('theme-cream', isCream);
            app.classList.toggle('dark', !isCream);
        }
        const btn = document.getElementById('theme-toggle-btn');
        if (btn) {
            btn.innerHTML = isCream
                ? '<span class="theme-icon">🌙</span> <span class="theme-text">Mode Teal & Hitam</span>'
                : '<span class="theme-icon">🍦</span> <span class="theme-text">Mode Krem & Putih</span>';
        }
        localStorage.setItem('removebg-theme', theme);
    }
    window.toggleTheme = function() {
        const next = getTheme() === 'cream' ? 'teal-dark' : 'cream';
        apply(next);
    };
    apply(getTheme());
    setTimeout(() => apply(getTheme()), 200);
    setTimeout(() => apply(getTheme()), 600);
}"""

FORCE_DARK = THEME_JS


def make_theme():
    teal = gr.themes.Color(
        c50="#f0fdfa", c100="#ccfbf1", c200="#99f6e4", c300="#5eead4", c400="#2dd4bf",
        c500="#14b8a6", c600="#0d9488", c700="#0f766e", c800="#115e59", c900="#134e4a", c950="#042f2e",
    )
    slate = gr.themes.Color(
        c50="#f8fafc", c100="#f1f5f9", c200="#e2e8f0", c300="#cbd5e1", c400="#94a3b8",
        c500="#64748b", c600="#475569", c700="#334155", c800="#1e293b", c900="#0f172a", c950="#020617",
    )
    return gr.themes.Base(
        primary_hue=teal,
        secondary_hue=teal,
        neutral_hue=slate,
        font=FONT,
        font_mono=MONO,
    ).set(
        # Dark mode (Teal & Slate/Charcoal)
        body_background_fill_dark="#080d11",
        background_fill_primary_dark="#0d151a",
        background_fill_secondary_dark="#111c23",
        block_background_fill_dark="#0d151a",
        block_border_color_dark="#18262e",
        block_radius="16px",
        block_label_background_fill_dark="#111c23",
        button_large_radius="12px",
        button_primary_background_fill="linear-gradient(135deg, #14b8a6 0%, #0d9488 100%)",
        button_primary_background_fill_hover="linear-gradient(135deg, #2dd4bf 0%, #14b8a6 100%)",
        button_primary_text_color="#ffffff",
        input_background_fill_dark="#091014",
        input_border_color_dark="#1a2c36",
        input_radius="12px",
        border_color_accent_dark="#14b8a6",
        color_accent_soft_dark="#042f2e",
        # Light mode (Warm Cream / White)
        body_background_fill="#f7f5ef",
        background_fill_primary="#ffffff",
        background_fill_secondary="#f4efe6",
        block_background_fill="#ffffff",
        block_border_color="#e5e0d4",
        block_label_background_fill="#f4efe6",
        input_background_fill="#faf8f4",
        input_border_color="#ded8cb",
        border_color_accent="#0d9488",
    )


CSS = """
/* ========================================================
   THEME VARIABLES: TEAL & CHARCOAL (DEFAULT DARK)
   ======================================================== */
:root, body.dark, gradio-app.dark {
  --bg-app: #080d11;
  --bg-app-gradient: radial-gradient(1000px 500px at 85% -10%, rgba(20, 184, 166, 0.12), transparent 60%),
                     radial-gradient(800px 450px at -5% 30%, rgba(13, 148, 136, 0.08), transparent 60%),
                     #080d11;
  --bg-hero: linear-gradient(135deg, rgba(20, 184, 166, 0.12) 0%, rgba(15, 23, 29, 0.90) 60%), #0c1419;
  --border-hero: rgba(20, 184, 166, 0.28);
  --hero-shadow: 0 18px 45px -18px rgba(13, 148, 136, 0.35);
  --bg-card: #0d151a;
  --bg-card-subtle: #111a20;
  --border-card: #18262e;
  --border-card-hover: rgba(20, 184, 166, 0.45);
  --card-shadow-hover: 0 10px 30px -12px rgba(20, 184, 166, 0.3);

  --text-primary: #f0fdfa;
  --text-secondary: #94a3b8;
  --text-muted: #5a6e78;

  --accent-teal: #14b8a6;
  --accent-teal-dark: #0d9488;
  --accent-teal-light: #5eead4;
  --accent-gradient: linear-gradient(135deg, #14b8a6 0%, #0d9488 100%);

  --btn-primary-bg: linear-gradient(135deg, #14b8a6 0%, #0d9488 100%);
  --btn-primary-hover: linear-gradient(135deg, #2dd4bf 0%, #14b8a6 100%);
  --btn-primary-shadow: 0 8px 24px -6px rgba(20, 184, 166, 0.45);
  --btn-secondary-bg: #111c23;
  --btn-secondary-border: #1f333e;
  --btn-secondary-hover: #172630;
  --btn-secondary-text: #ccfbf1;

  --upload-bg: #091014;
  --upload-border: #1a2c36;
  --upload-hover-bg: rgba(20, 184, 166, 0.06);
  --upload-hover-border: #14b8a6;

  --choice-bg: #0b1216;
  --choice-border: #192730;
  --choice-hover-border: #14b8a6;
  --choice-selected-bg: linear-gradient(135deg, rgba(20, 184, 166, 0.18), rgba(13, 148, 136, 0.08));
  --choice-selected-border: #14b8a6;
  --choice-selected-text: #ffffff;

  --chip-bg: rgba(20, 184, 166, 0.12);
  --chip-border: rgba(20, 184, 166, 0.3);
  --chip-text: #ccfbf1;
  --chip-ok-bg: rgba(16, 185, 129, 0.12);
  --chip-ok-border: rgba(16, 185, 129, 0.3);
  --chip-ok-text: #a7f3d0;

  --download-bg: linear-gradient(135deg, rgba(20, 184, 166, 0.12), rgba(15, 23, 29, 0.9)), #0d151a;
  --download-border: rgba(20, 184, 166, 0.35);
}

/* ========================================================
   THEME VARIABLES: WARM CREAM & TEAL (LIGHT MODE)
   ======================================================== */
.theme-cream, body.theme-cream, gradio-app.theme-cream {
  --bg-app: #f7f5ef;
  --bg-app-gradient: radial-gradient(1000px 500px at 85% -10%, rgba(20, 184, 166, 0.10), transparent 60%),
                     radial-gradient(800px 450px at -5% 30%, rgba(217, 119, 6, 0.05), transparent 60%),
                     #f7f5ef;
  --bg-hero: linear-gradient(135deg, rgba(20, 184, 166, 0.10) 0%, rgba(255, 255, 255, 0.95) 60%), #ffffff;
  --border-hero: rgba(13, 148, 136, 0.22);
  --hero-shadow: 0 16px 40px -15px rgba(13, 148, 136, 0.18);
  --bg-card: #ffffff;
  --bg-card-subtle: #f8f6f0;
  --border-card: #e5e0d4;
  --border-card-hover: #0d9488;
  --card-shadow-hover: 0 10px 28px -10px rgba(13, 148, 136, 0.2);

  --text-primary: #18262e;
  --text-secondary: #4a5d68;
  --text-muted: #7c8e96;

  --accent-teal: #0d9488;
  --accent-teal-dark: #0f766e;
  --accent-teal-light: #14b8a6;
  --accent-gradient: linear-gradient(135deg, #0d9488 0%, #0f766e 100%);

  --btn-primary-bg: linear-gradient(135deg, #0d9488 0%, #0f766e 100%);
  --btn-primary-hover: linear-gradient(135deg, #14b8a6 0%, #0d9488 100%);
  --btn-primary-shadow: 0 8px 20px -6px rgba(13, 148, 136, 0.35);
  --btn-secondary-bg: #f4efe6;
  --btn-secondary-border: #ded7c8;
  --btn-secondary-hover: #ece5d8;
  --btn-secondary-text: #0f766e;

  --upload-bg: #faf7f2;
  --upload-border: #dcd4c5;
  --upload-hover-bg: rgba(20, 184, 166, 0.05);
  --upload-hover-border: #0d9488;

  --choice-bg: #faf8f3;
  --choice-border: #ded8cb;
  --choice-hover-border: #0d9488;
  --choice-selected-bg: linear-gradient(135deg, rgba(20, 184, 166, 0.12), rgba(13, 148, 136, 0.06));
  --choice-selected-border: #0d9488;
  --choice-selected-text: #0f766e;

  --chip-bg: rgba(13, 148, 136, 0.1);
  --chip-border: rgba(13, 148, 136, 0.25);
  --chip-text: #0f766e;
  --chip-ok-bg: rgba(16, 185, 129, 0.1);
  --chip-ok-border: rgba(16, 185, 129, 0.25);
  --chip-ok-text: #047857;

  --download-bg: linear-gradient(135deg, rgba(20, 184, 166, 0.08), rgba(255, 255, 255, 0.95)), #ffffff;
  --download-border: rgba(13, 148, 136, 0.25);
}

/* ========================================================
   GLOBAL CONTAINER & BASE
   ======================================================== */
.gradio-container {
  max-width: 1240px !important;
  margin: auto;
  background: var(--bg-app-gradient) !important;
  color: var(--text-primary) !important;
  transition: background .25s ease, color .25s ease;
}
body, .dark, gradio-app, .theme-cream {
  background: var(--bg-app) !important;
  color: var(--text-primary) !important;
}
footer { display: none !important; }

/* ========================================================
   HERO HEADER
   ======================================================== */
.hero {
  position: relative;
  overflow: hidden;
  padding: 30px 36px;
  border-radius: 24px;
  margin-bottom: 12px;
  background: var(--bg-hero);
  border: 1px solid var(--border-hero);
  box-shadow: var(--hero-shadow);
  transition: all .25s ease;
}
.hero-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  flex-wrap: wrap;
  position: relative;
  z-index: 1;
}
.hero-brand {
  display: flex;
  align-items: center;
  gap: 16px;
}
.logo {
  width: 52px;
  height: 52px;
  border-radius: 14px;
  display: grid;
  place-items: center;
  font-size: 26px;
  color: #fff;
  background: var(--accent-gradient);
  box-shadow: 0 8px 24px -6px rgba(20, 184, 166, 0.5);
}
.hero-titles h1 {
  margin: 0;
  font-size: 34px;
  line-height: 1.1;
  font-weight: 800;
  letter-spacing: -.02em;
  color: var(--text-primary);
}
.hero-titles h1 span {
  background: linear-gradient(90deg, #14b8a6, #2dd4bf);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}
.theme-cream .hero-titles h1 span {
  background: linear-gradient(90deg, #0d9488, #14b8a6);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}
.hero p {
  margin: 8px 0 0;
  font-size: 15px;
  color: var(--text-secondary);
  max-width: 620px;
  position: relative;
  z-index: 1;
}
.theme-switch-container {
  display: flex;
  align-items: center;
}
.theme-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 9px 18px;
  border-radius: 999px;
  font-size: 13.5px;
  font-weight: 700;
  cursor: pointer;
  background: var(--bg-card);
  border: 1.5px solid var(--border-hero);
  color: var(--text-primary);
  box-shadow: 0 4px 14px -4px rgba(0,0,0,0.25);
  transition: all .2s ease;
}
.theme-btn:hover {
  border-color: var(--accent-teal);
  transform: translateY(-1px);
  box-shadow: 0 6px 18px -4px rgba(20, 184, 166, 0.3);
}
.theme-btn:active {
  transform: translateY(0);
}
.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 18px;
  position: relative;
  z-index: 1;
}
.chip {
  padding: 6px 13px;
  border-radius: 999px;
  font-size: 13px;
  font-weight: 600;
  color: var(--chip-text);
  background: var(--chip-bg);
  border: 1px solid var(--chip-border);
}
.chip.ok {
  color: var(--chip-ok-text);
  background: var(--chip-ok-bg);
  border-color: var(--chip-ok-border);
}

/* ========================================================
   TABS
   ======================================================== */
.tab-wrapper, .tab-container {
  border: none !important;
}
.tab-container button {
  font-weight: 700;
  font-size: 15.5px;
  padding: 10px 22px !important;
  border-radius: 12px 12px 0 0;
  color: var(--text-secondary) !important;
  transition: all .2s;
}
.tab-container button:hover {
  color: var(--text-primary) !important;
}
.tab-container button.selected {
  color: var(--accent-teal) !important;
}
.tab-container::after {
  background-color: var(--accent-teal) !important;
}

/* ========================================================
   CARDS & STRUCTURE
   ======================================================== */
.card {
  border: 1px solid var(--border-card) !important;
  background: var(--bg-card) !important;
  border-radius: 18px !important;
  padding: 20px !important;
  transition: border-color .25s, transform .25s, box-shadow .25s;
}
.card:hover {
  border-color: var(--border-card-hover) !important;
  box-shadow: var(--card-shadow-hover) !important;
}
.card > *, .card .styler, .card .block, .card .form, .card .html-container, .card .prose {
  background: transparent !important;
  box-shadow: none !important;
}
.card .block:not(.upload-zone):not(.status) {
  border-color: transparent !important;
}
.card .status {
  background: var(--bg-card-subtle) !important;
  border: 1px solid var(--border-card) !important;
}
.card .upload-zone {
  background: var(--upload-bg) !important;
  border: 2px dashed var(--upload-border) !important;
  border-radius: 16px !important;
  transition: all .2s;
}
.card .upload-zone:hover {
  border-color: var(--upload-hover-border) !important;
  background: var(--upload-hover-bg) !important;
}

/* ========================================================
   STEP HEADINGS
   ======================================================== */
.step-title {
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 0 0 4px;
  font-size: 18.5px;
  font-weight: 800;
  color: var(--text-primary);
}
.step-no {
  width: 30px;
  height: 30px;
  border-radius: 9px;
  display: grid;
  place-items: center;
  font-weight: 800;
  font-size: 15px;
  color: #fff;
  background: var(--accent-gradient);
  box-shadow: 0 4px 14px -4px rgba(20, 184, 166, 0.6);
}
.step-sub {
  margin: 0 0 12px 42px;
  color: var(--text-secondary);
  font-size: 13.5px;
}
.hint {
  border-left: 3px solid var(--accent-teal);
  background: var(--chip-bg);
  padding: 10px 14px;
  border-radius: 0 10px 10px 0;
  color: var(--text-primary);
  font-size: 13.5px;
}
.meta {
  color: var(--accent-teal);
  font-weight: 600;
  font-size: 13.5px;
}

/* ========================================================
   RADIO BUTTONS (CHOICES)
   ======================================================== */
.choice .wrap {
  display: grid !important;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)) !important;
  gap: 8px !important;
}
.choice label {
  border: 1.5px solid var(--choice-border) !important;
  border-radius: 12px !important;
  padding: 11px 14px !important;
  background: var(--choice-bg) !important;
  color: var(--text-primary) !important;
  cursor: pointer;
  transition: all .2s;
  font-weight: 700;
  font-size: 13.5px;
  display: flex !important;
  align-items: center;
  justify-content: flex-start;
  text-align: left;
}
.choice label:hover {
  border-color: var(--accent-teal) !important;
  background: var(--bg-card-subtle) !important;
  transform: translateY(-1px);
}
.choice label.selected {
  background: var(--choice-selected-bg) !important;
  border-color: var(--accent-teal) !important;
  box-shadow: 0 4px 16px -6px rgba(20, 184, 166, 0.4);
  color: var(--choice-selected-text) !important;
}

/* ========================================================
   BUTTONS
   ======================================================== */
button.primary {
  font-weight: 800 !important;
  letter-spacing: .01em;
  background: var(--btn-primary-bg) !important;
  color: #ffffff !important;
  border: none !important;
  box-shadow: var(--btn-primary-shadow) !important;
  transition: transform .15s, box-shadow .2s, filter .2s !important;
  border-radius: 12px !important;
}
button.primary:hover {
  background: var(--btn-primary-hover) !important;
  transform: translateY(-1.5px) scale(1.005);
  filter: brightness(1.06);
}
button.primary:active {
  transform: translateY(0) scale(.995);
}
button.secondary {
  border: 1.5px solid var(--btn-secondary-border) !important;
  background: var(--btn-secondary-bg) !important;
  color: var(--btn-secondary-text) !important;
  font-weight: 700;
  border-radius: 12px !important;
  transition: all .2s;
}
button.secondary:hover {
  border-color: var(--accent-teal) !important;
}
button.stop {
  background: transparent !important;
  border: 1.5px solid rgba(239, 68, 68, 0.4) !important;
  color: #ef4444 !important;
  font-weight: 700;
  border-radius: 12px !important;
  transition: all .2s;
}
button.stop:hover {
  background: rgba(239, 68, 68, 0.12) !important;
  border-color: #ef4444 !important;
}

/* ========================================================
   STATUS & PLAYERS
   ======================================================== */
.status {
  padding: 10px 14px;
  border-radius: 12px;
  background: var(--bg-card-subtle);
  border: 1px solid var(--border-card);
  color: var(--text-primary);
  font-size: 13.5px;
}
.player video {
  width: 100%;
  max-height: 420px;
  border-radius: 14px;
  background: #000;
  border: 1px solid var(--border-card);
}
.player.empty {
  padding: 36px 16px;
  text-align: center;
  color: var(--text-muted);
  font-size: 13px;
  border: 1.5px dashed var(--border-card);
  border-radius: 14px;
  background: var(--bg-card-subtle);
}
.footer-note {
  text-align: center;
  color: var(--text-muted);
  font-size: 12.5px;
  padding: 18px 0 6px;
}

/* ========================================================
   DOWNLOAD CARD
   ======================================================== */
.download-box {
  margin-top: 12px;
  padding: 16px 18px;
  border-radius: 14px;
  background: var(--download-bg);
  border: 1.5px solid var(--download-border);
  box-shadow: 0 8px 24px -8px rgba(0, 0, 0, 0.25);
}
.download-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
}
.download-info {
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.download-filename {
  font-size: 15px;
  font-weight: 800;
  color: var(--text-primary);
  word-break: break-all;
}
.download-sub {
  font-size: 12.5px;
  color: var(--accent-teal);
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 6px;
}
.download-pill {
  padding: 2px 7px;
  border-radius: 5px;
  font-size: 11px;
  font-weight: 800;
  text-transform: uppercase;
  background: var(--accent-teal);
  color: #fff;
  letter-spacing: .02em;
}
.btn-download-clean {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 11px 18px;
  border-radius: 10px;
  text-decoration: none !important;
  font-size: 14px;
  font-weight: 800;
  color: #ffffff !important;
  background: var(--btn-primary-bg);
  box-shadow: 0 4px 14px -4px rgba(20, 184, 166, 0.45);
  transition: all .2s;
}
.btn-download-clean:hover {
  background: var(--btn-primary-hover);
  transform: translateY(-1px);
  filter: brightness(1.05);
  color: #fff !important;
}
.btn-download-clean:active {
  transform: translateY(0);
}
.download-empty {
  padding: 16px;
  text-align: center;
  color: var(--text-muted);
  font-size: 13px;
  border: 1.5px dashed var(--border-card);
  border-radius: 14px;
  background: var(--bg-card-subtle);
  margin-top: 10px;
}

/* Keep the local web UI comfortable on narrow screens without extra JS. */
@media (max-width: 760px) {
  .gradio-container {
    padding: 12px !important;
  }
  .hero {
    padding: 20px;
    border-radius: 18px;
  }
  .hero-brand {
    align-items: flex-start;
    gap: 12px;
  }
  .logo {
    width: 42px;
    height: 42px;
    flex: 0 0 42px;
    font-size: 22px;
  }
  .hero-titles h1 {
    font-size: 27px;
  }
  .hero p {
    font-size: 14px;
  }
  .theme-switch-container,
  .theme-btn {
    width: 100%;
  }
  .theme-btn {
    justify-content: center;
  }
  .tab-container {
    overflow-x: auto;
    scrollbar-width: thin;
  }
  .tab-container button {
    white-space: nowrap;
    padding: 10px 14px !important;
    font-size: 14px;
  }
  .gradio-container .row {
    flex-wrap: wrap !important;
  }
  .gradio-container .row > .column {
    width: 100% !important;
    min-width: 0 !important;
    flex: 1 1 100% !important;
  }
  .card {
    padding: 16px !important;
    border-radius: 15px !important;
  }
  .step-sub {
    margin-left: 0;
    line-height: 1.5;
  }
  .choice .wrap {
    grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)) !important;
  }
  .download-row {
    align-items: stretch;
  }
  .btn-download-clean {
    width: 100%;
  }
}

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    scroll-behavior: auto !important;
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}
"""
