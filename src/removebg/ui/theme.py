import gradio as gr

# Fonts are system fonts only so the app stays fully offline.
FONT = [gr.themes.Font("Segoe UI Variable Display"), gr.themes.Font("Segoe UI"), "system-ui", "sans-serif"]
MONO = [gr.themes.Font("Cascadia Mono"), gr.themes.Font("Consolas"), "monospace"]

FORCE_DARK = "() => { document.body.classList.add('dark'); }"


def make_theme():
    red = gr.themes.Color(
        c50="#fff1f2", c100="#ffe0e3", c200="#ffc0c7", c300="#ff909c", c400="#ff5566",
        c500="#f01d36", c600="#d10f2a", c700="#ab0a22", c800="#880c20", c900="#700f20", c950="#3e040c",
    )
    ink = gr.themes.Color(
        c50="#f6f1f1", c100="#e9e1e1", c200="#d3c6c6", c300="#b3a2a3", c400="#8c7a7c",
        c500="#6b5a5c", c600="#4e4042", c700="#352a2c", c800="#241b1d", c900="#161011", c950="#0b0707",
    )
    return gr.themes.Base(primary_hue=red, secondary_hue=red, neutral_hue=ink, font=FONT, font_mono=MONO).set(
        body_background_fill_dark="#0b0707",
        background_fill_primary_dark="#150e10",
        background_fill_secondary_dark="#1b1214",
        block_background_fill_dark="#150e10",
        block_border_color_dark="#2e1d20",
        block_radius="18px",
        block_label_background_fill_dark="#1b1214",
        button_large_radius="14px",
        button_primary_background_fill="linear-gradient(135deg,#ff2d46 0%,#d10f2a 55%,#ff7a2f 130%)",
        button_primary_background_fill_hover="linear-gradient(135deg,#ff4a5f 0%,#e5152f 55%,#ff9440 130%)",
        button_primary_text_color="#ffffff",
        input_background_fill_dark="#100a0b",
        input_border_color_dark="#3a2327",
        input_radius="12px",
        border_color_accent_dark="#f01d36",
        color_accent_soft_dark="#3e040c",
    )


CSS = """
.gradio-container { max-width: 1240px !important; margin: auto; background:
  radial-gradient(1000px 520px at 85% -8%, rgba(240,29,54,.20), transparent 60%),
  radial-gradient(800px 480px at -5% 30%, rgba(255,122,47,.10), transparent 60%), #0b0707 !important; }
footer { display: none !important; }

/* ---------- Hero ---------- */
.hero { position: relative; overflow: hidden; padding: 34px 38px; border-radius: 26px; margin-bottom: 8px;
  background: linear-gradient(120deg, rgba(240,29,54,.22), rgba(21,14,16,.92) 55%), #150e10;
  border: 1px solid rgba(240,29,54,.35); box-shadow: 0 20px 60px -25px rgba(240,29,54,.55); }
.hero::after { content:""; position:absolute; right:-80px; top:-80px; width:320px; height:320px; border-radius:50%;
  background: conic-gradient(from 0deg, #f01d36, #ff7a2f, #ffc15a, #f01d36); filter: blur(70px); opacity:.35;
  animation: spin 14s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.hero-top { display:flex; align-items:center; gap:16px; position:relative; z-index:1; }
.logo { width:56px; height:56px; border-radius:16px; display:grid; place-items:center; font-size:28px; color:#fff;
  background: linear-gradient(135deg,#ff2d46,#ff7a2f); box-shadow: 0 10px 30px -8px rgba(255,45,70,.8); }
.hero h1 { margin:0; font-size: 40px; line-height:1.05; font-weight: 800; letter-spacing:-.02em; color:#fff; }
.hero h1 span { background: linear-gradient(90deg,#ff4a5f,#ffb454); -webkit-background-clip:text; background-clip:text; color:transparent; }
.hero p { margin:12px 0 0; font-size:16px; color:#d9c6c8; max-width: 640px; position:relative; z-index:1; }
.chips { display:flex; flex-wrap:wrap; gap:8px; margin-top:20px; position:relative; z-index:1; }
.chip { padding:6px 13px; border-radius:999px; font-size:13px; font-weight:600; color:#ffd9dd;
  background: rgba(240,29,54,.14); border:1px solid rgba(240,29,54,.4); }
.chip.ok { color:#ffe7c2; background: rgba(255,180,84,.12); border-color: rgba(255,180,84,.4); }

/* ---------- Tabs ---------- */
.tab-wrapper, .tab-container { border:none !important; }
.tab-container button { font-weight:700; font-size:16px; padding:10px 22px !important; border-radius:12px 12px 0 0; }
.tab-container button.selected { color:#ff5566 !important; }
.tab-container::after { background-color:#f01d36 !important; }

/* ---------- Step cards ---------- */
.card { border:1px solid #2e1d20 !important; background: linear-gradient(180deg,#171012,#120b0d) !important;
  border-radius:20px !important; padding:20px !important; transition: border-color .25s, transform .25s, box-shadow .25s; }
.card:hover { border-color: rgba(240,29,54,.55) !important; box-shadow: 0 14px 40px -22px rgba(240,29,54,.6); }
.card > *, .card .styler, .card .block, .card .form, .card .html-container, .card .prose { background: transparent !important; box-shadow:none !important; }
body, .dark, gradio-app { background:#0b0707 !important; }
.card .block:not(.upload-zone):not(.status) { border-color: transparent !important; }
.card .status { background:#100a0b !important; border:1px solid #2e1d20 !important; }
.card .upload-zone { background:#100a0b !important; border:2px dashed #5a2a31 !important; }
.card .upload-zone:hover { border-color:#ff2d46 !important; background: rgba(240,29,54,.07) !important; }
.step-title { display:flex; align-items:center; gap:12px; margin:0 0 4px; font-size:19px; font-weight:800; color:#fff; }
.step-no { width:32px; height:32px; border-radius:10px; display:grid; place-items:center; font-weight:800; font-size:16px;
  color:#fff; background: linear-gradient(135deg,#ff2d46,#d10f2a); box-shadow: 0 6px 18px -6px rgba(255,45,70,.9); }
.step-sub { margin:0 0 12px 44px; color:#a89396; font-size:14px; }
.hint { border-left:3px solid #ff7a2f; background: rgba(255,122,47,.08); padding:10px 14px; border-radius:0 12px 12px 0;
  color:#f3d9c4; font-size:14px; }
.meta { color:#ffb454; font-weight:600; font-size:14px; }

/* ---------- Choice cards (radio) ---------- */
.choice .wrap { gap:10px !important; flex-wrap:wrap; }
.choice label { flex:1 1 200px; border:1.5px solid #3a2327 !important; border-radius:14px !important; padding:14px 16px !important;
  background:#100a0b !important; cursor:pointer; transition: all .2s; font-weight:700; }
.choice label:hover { border-color:#f01d36 !important; transform: translateY(-2px); }
.choice label.selected { background: linear-gradient(135deg, rgba(240,29,54,.28), rgba(255,122,47,.12)) !important;
  border-color:#ff2d46 !important; box-shadow: 0 8px 24px -12px rgba(255,45,70,.9); color:#fff !important; }

/* ---------- Buttons ---------- */
button.primary { font-weight:800 !important; letter-spacing:.01em; box-shadow: 0 12px 30px -12px rgba(240,29,54,.9);
  transition: transform .15s, box-shadow .2s, filter .2s !important; }
button.primary:hover { transform: translateY(-2px) scale(1.01); box-shadow: 0 18px 40px -12px rgba(240,29,54,1); }
button.primary:active { transform: translateY(0) scale(.99); }
button.secondary { border:1.5px solid #5a2a31 !important; background:#1b1214 !important; color:#ffd0d5 !important; font-weight:700; transition: all .2s; }
button.secondary:hover { border-color:#ff5566 !important; background:#2a1519 !important; transform: translateY(-1px); }
button.stop { background: transparent !important; border:1.5px solid #6b2a30 !important; color:#ff8995 !important; font-weight:700; }
button.stop:hover { background:#3e040c !important; }

/* ---------- Status / output ---------- */
.status { padding:12px 16px; border-radius:14px; background:#100a0b; border:1px solid #2e1d20; color:#f1dede; }
.upload-zone { border:2px dashed #5a2a31 !important; border-radius:18px !important; background:#100a0b !important; transition: all .25s; }
.upload-zone:hover { border-color:#ff2d46 !important; background: rgba(240,29,54,.07) !important; }
.footer-note { text-align:center; color:#7d6a6c; font-size:13px; padding:18px 0 4px; }
.player video { width:100%; max-height:460px; border-radius:16px; background:#000; border:1px solid #3a2327; accent-color:#f01d36; }
.player p { margin:8px 2px 0; font-size:13px; color:#ffb454; }
.player.empty { padding:42px 16px; text-align:center; color:#8c7a7c; border:1.5px dashed #3a2327; border-radius:16px; background:#100a0b; }

/* ---------- Download Card & Hero Download Button ---------- */
.download-box { margin-top: 14px; padding: 20px 22px; border-radius: 18px;
  background: linear-gradient(135deg, rgba(240,29,54,.18), rgba(255,122,47,.10)), #150e10;
  border: 1.5px solid rgba(240,29,54,.55); box-shadow: 0 10px 32px -10px rgba(240,29,54,.45); }
.download-meta { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px; margin-bottom: 10px; }
.download-badge { padding: 5px 12px; border-radius: 8px; font-size: 13px; font-weight: 800; text-transform: uppercase;
  background: #f01d36; color: #fff; letter-spacing: .03em; box-shadow: 0 4px 12px -3px rgba(240,29,54,.8); }
.download-filename { font-size: 17px; font-weight: 800; color: #fff; word-break: break-all; }
.download-desc { font-size: 13.5px; color: #ffd6dc; margin: 8px 0 16px; line-height: 1.5; }
.download-filesize { font-size: 13.5px; color: #ffb454; font-weight: 700; }
.btn-download-hero { display: flex; align-items: center; justify-content: center; gap: 10px; width: 100%;
  padding: 18px 24px; border-radius: 14px; text-decoration: none !important;
  font-size: 17px; font-weight: 800; color: #ffffff !important; letter-spacing: .02em;
  background: linear-gradient(135deg, #ff2d46 0%, #d10f2a 55%, #ff7a2f 130%);
  box-shadow: 0 8px 28px -6px rgba(255,45,70,.9); transition: all .2s; }
.btn-download-hero:hover { transform: translateY(-2px); box-shadow: 0 14px 40px -6px rgba(255,45,70,1); filter: brightness(1.12); color: #fff !important; }
.btn-download-hero:active { transform: translateY(0); }
.download-path-tip { font-size: 12px; color: #a18c8f; margin: 12px 0 0; text-align: center; word-break: break-all; }
.download-path-tip code { color: #ffb454; background: rgba(255,180,84,.12); padding: 2px 7px; border-radius: 6px; font-size: 11.5px; }
"""
