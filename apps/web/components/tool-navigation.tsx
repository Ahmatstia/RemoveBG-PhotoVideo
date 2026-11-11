import {
  ArrowDownToLine,
  AudioLines,
  ChartNoAxesCombined,
  ChevronDown,
  Clapperboard,
  Database,
  ImagePlus,
} from "lucide-react";

export type MediaTool = "video" | "photo" | "transcription" | "download";
type Tool = { id: MediaTool; label: string; icon: typeof Clapperboard };

const mediaTools: Tool[] = [
  { id: "video", label: "Hapus latar video", icon: Clapperboard },
  { id: "photo", label: "Hapus latar foto", icon: ImagePlus },
  { id: "transcription", label: "Transkripsi YouTube", icon: AudioLines },
  { id: "download", label: "Unduh media", icon: ArrowDownToLine },
];

export function ToolNavigation({
  activeTool,
  onSelectTool,
}: {
  activeTool: MediaTool | "decision-support";
  onSelectTool?: (tool: MediaTool) => void;
}) {
  return (
    <nav className="tool-navigation" aria-label="Kategori alat">
      <div className="nav-label">Alat kerja</div>
      <details className="tool-nav-group" open>
        <summary><span><Clapperboard size={15} /> Produksi Media</span><ChevronDown className="tool-nav-chevron" size={15} /></summary>
        <div className="tool-nav-items">
          {mediaTools.map(({ id, label, icon: Icon }) => {
            const active = activeTool === id;
            const content = <><span className="tool-nav-icon"><Icon size={15} /></span>{label}</>;
            return onSelectTool ? (
              <button key={id} type="button" className={`tool-nav-item${active ? " active" : ""}`} aria-current={active ? "page" : undefined} onClick={() => onSelectTool(id)}>{content}</button>
            ) : (
              <a key={id} className={`tool-nav-item${active ? " active" : ""}`} aria-current={active ? "page" : undefined} href={`/?tool=${id}`}>{content}</a>
            );
          })}
        </div>
      </details>
      <details className="tool-nav-group" open>
        <summary><span><Database size={15} /> Riset &amp; Data</span><ChevronDown className="tool-nav-chevron" size={15} /></summary>
        <div className="tool-nav-items">
          <a className={`tool-nav-item${activeTool === "decision-support" ? " active" : ""}`} aria-current={activeTool === "decision-support" ? "page" : undefined} href="/decision-support">
            <span className="tool-nav-icon"><ChartNoAxesCombined size={15} /></span>Analisis &amp; rekomendasi
          </a>
          <span className="tool-nav-item unavailable" aria-disabled="true" title="Fitur scraping belum tersedia">
            <span className="tool-nav-icon"><Database size={15} /></span>Scraping data <small>Segera</small>
          </span>
        </div>
      </details>
    </nav>
  );
}
