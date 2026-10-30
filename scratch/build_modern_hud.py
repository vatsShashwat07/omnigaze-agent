import re
from pathlib import Path

# Load existing index.html to extract the exact JavaScript logic
with open('static/index.html', 'r', encoding='utf-8') as f:
    orig_html = f.read()

# Extract the script from line "<!-- ── Dashboard Logic ──" to </script>
script_match = re.search(r'(<!-- ── Dashboard Logic ──[\s\S]*?<\/script>)', orig_html)
if not script_match:
    raise ValueError("Could not find Dashboard Logic script block in static/index.html")

dashboard_script = script_match.group(1)

# Ensure setNodeStatus in dashboard_script uses the modern Linear/Vercel classes:
# Active: Electric Neon Lime (#D4F754)
# Done: Subtle border with confirmed lime dot
# Idle: Sleek dark capsule
old_set_node = """    // Node Highlighting
    function setNodeStatus(nodeId, state = 'active') {
      const el = document.getElementById(`node-${nodeId}`);
      if (!el) return;
      const dot = el.querySelector('.status-dot');

      if (state === 'active') {
        el.className = 'p-1 rounded bg-cyan-950/80 border border-cyan-500 text-cyan-200 flex flex-col items-center shadow-md shadow-cyan-950';
        if (dot) dot.className = 'status-dot w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse';
      } else if (state === 'done') {
        el.className = 'p-1 rounded bg-scada-850 border border-emerald-500/60 text-emerald-300 flex flex-col items-center';
        if (dot) dot.className = 'status-dot w-1.5 h-1.5 rounded-full bg-emerald-400';
      } else {
        el.className = 'p-1 rounded bg-scada-900 border border-scada-700 text-slate-400 flex flex-col items-center';
        if (dot) dot.className = 'status-dot w-1.5 h-1.5 rounded-full bg-slate-600';
      }
    }"""

new_set_node = """    // Node Highlighting (Modern Gantt Pill Capsule Styling)
    function setNodeStatus(nodeId, state = 'active') {
      const el = document.getElementById(`node-${nodeId}`);
      if (!el) return;
      const dot = el.querySelector('.status-dot');

      if (state === 'active') {
        el.className = 'px-3 py-2 rounded-2xl bg-[#D4F754]/10 border border-[#D4F754]/50 text-[#D4F754] flex items-center justify-between shadow-lg shadow-[#D4F754]/10 transition-all duration-300';
        if (dot) dot.className = 'status-dot w-2 h-2 rounded-full bg-[#D4F754] animate-ping';
      } else if (state === 'done') {
        el.className = 'px-3 py-2 rounded-2xl bg-white/[0.04] border border-white/10 text-white flex items-center justify-between transition-all duration-300';
        if (dot) dot.className = 'status-dot w-2 h-2 rounded-full bg-[#D4F754] shadow-sm shadow-[#D4F754]';
      } else {
        el.className = 'px-3 py-2 rounded-2xl bg-white/[0.02] border border-white/5 text-zinc-500 flex items-center justify-between transition-all duration-300';
        if (dot) dot.className = 'status-dot w-2 h-2 rounded-full bg-zinc-700';
      }
    }"""

if old_set_node in dashboard_script:
    dashboard_script = dashboard_script.replace(old_set_node, new_set_node)
else:
    # Use regex replacement if whitespace differed slightly
    dashboard_script = re.sub(
        r'function setNodeStatus\(nodeId, state = \'active\'\) \{[\s\S]*?\}\n    \}',
        new_set_node,
        dashboard_script
    )

new_html_head_and_body = '''<!DOCTYPE html>
<html lang="en" class="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>OmniGaze | Autonomous Visual SCADA Mission Control</title>
  <meta name="description" content="Autonomous Spatial-Visual Infrastructure Inspector powered by Meta Muse Spark Open, Meta SAM 2, and LangGraph.">
  
  <!-- Modern Grotesque Fonts -->
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;600;700&display=swap" rel="stylesheet">

  <!-- Tailwind CSS CDN -->
  <script src="https://cdn.tailwindcss.com"></script>
  <script>
    tailwind.config = {
      darkMode: 'class',
      theme: {
        extend: {
          colors: {
            matte: '#09090b',
            surface: '#141417',
            lime: {
              DEFAULT: '#D4F754',
              neon: '#D4F754',
              glow: 'rgba(212, 247, 84, 0.35)'
            },
            orange: {
              industrial: '#FF7A00',
              glow: 'rgba(255, 122, 0, 0.35)'
            }
          },
          fontFamily: {
            sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
            mono: ['"JetBrains Mono"', 'Menlo', 'Consolas', 'monospace']
          }
        }
      }
    }
  </script>

  <!-- Chart.js CDN -->
  <script src="https://cdn.jsdelivr.net/npm/chart.js?v=2.1"></script>
  <!-- Lucide Icons CDN -->
  <script src="https://unpkg.com/lucide@latest?v=2.1"></script>

  <style>
    body {
      background-color: #09090b;
      font-family: 'Inter', sans-serif;
      color: #ffffff;
      overflow: hidden;
      letter-spacing: -0.01em;
    }
    
    .font-mono {
      font-family: 'JetBrains Mono', monospace;
    }

    /* Subtle SCADA scanlines overlay */
    .scanlines::before {
      content: " ";
      display: block;
      position: absolute;
      top: 0; left: 0; bottom: 0; right: 0;
      background: linear-gradient(rgba(18, 16, 16, 0) 50%, rgba(0, 0, 0, 0.35) 50%);
      background-size: 100% 4px;
      z-index: 10;
      pointer-events: none;
      opacity: 0.25;
    }

    /* Minimalist Dark Scrollbars */
    ::-webkit-scrollbar {
      width: 4px;
      height: 4px;
    }
    ::-webkit-scrollbar-track {
      background: #09090b;
    }
    ::-webkit-scrollbar-thumb {
      background: rgba(255, 255, 255, 0.12);
      border-radius: 9999px;
    }
    ::-webkit-scrollbar-thumb:hover {
      background: rgba(212, 247, 84, 0.4);
    }

    /* Optical Frame Zero-Gap Container */
    #optical-feed {
      height: 100% !important;
      min-height: 280px;
      position: relative;
      overflow: hidden;
      display: flex;
      align-items: center;
      justify-content: center;
      background: #000;
      border-radius: 1.25rem;
    }
    #optical-feed img,
    #inspection-img {
      height: 100% !important;
      width: 100% !important;
      object-fit: contain !important;
      display: block;
    }

    /* High-End Enterprise SCADA Header Badge */
    .badge-meta {
      display: inline-flex;
      align-items: center;
      gap: 0.35rem;
      color: #D4F754;
      font-weight: 600;
      letter-spacing: 0.025em;
    }
    .badge-meta-border {
      border: 1px solid rgba(212, 247, 84, 0.25) !important;
      background: rgba(20, 20, 23, 0.95) !important;
      box-shadow: 0 0 12px rgba(212, 247, 84, 0.12), inset 0 0 8px rgba(255, 255, 255, 0.03) !important;
      transition: all 0.3s ease;
    }
    .badge-meta-border:hover {
      border-color: rgba(212, 247, 84, 0.5) !important;
      box-shadow: 0 0 16px rgba(212, 247, 84, 0.25) !important;
    }

    /* Strict Modal & Overlay Rules */
    #hitl-modal.hidden {
      display: none !important;
      pointer-events: none !important;
      visibility: hidden !important;
    }
    #hitl-modal.active,
    #hitl-modal:not(.hidden) {
      display: flex !important;
      pointer-events: auto !important;
      visibility: visible !important;
    }
    #single-pane-view.hidden,
    #main-mission-control.hidden {
      display: none !important;
    }
    #benchmark-view.hidden {
      display: none !important;
    }
  </style>

  <!-- ── Global Benchmark Toggle (Defined Outside DOMContentLoaded for Bulletproof Access) ── -->
  <script>
    window.toggleBenchmarkMode = function() {
      const main = document.getElementById('main-mission-control') || document.getElementById('single-pane-view');
      const bench = document.getElementById('benchmark-view');
      if (!main || !bench) return;

      const isHidden = bench.classList.contains('hidden') || bench.style.display === 'none';
      if (isHidden) {
        main.classList.add('hidden');
        main.style.display = 'none';
        bench.classList.remove('hidden');
        bench.style.display = 'flex';
        if (typeof window.runBenchmarkSim === 'function') window.runBenchmarkSim();
      } else {
        bench.classList.add('hidden');
        bench.style.display = 'none';
        main.classList.remove('hidden');
        main.style.display = 'grid';
      }
    };
    window.toggleBenchmark = window.toggleBenchmarkMode;

    window.runBenchmarkSim = function() {
      if (typeof initBenchmarkCharts === 'function') initBenchmarkCharts();
      if (typeof triggerBenchmarkRun === 'function') triggerBenchmarkRun();
      if (window.lucide && typeof lucide.createIcons === 'function') {
        lucide.createIcons();
      }
    };

    function toggleFullScreen() {
      if (!document.fullscreenElement) {
        document.documentElement.requestFullscreen().catch(() => {});
      } else {
        if (document.exitFullscreen) {
          document.exitFullscreen().catch(() => {});
        }
      }
    }
  </script>
</head>
<body class="h-screen w-screen bg-[#09090b] text-white flex select-none font-sans overflow-hidden">

  <!-- ── Left Slim Sidebar: Minimal Icon Rail ─────────────────────────────── -->
  <aside class="w-16 h-full flex flex-col items-center py-3.5 bg-[#141417]/90 border-r border-white/[0.08] backdrop-blur-xl shrink-0 z-40 justify-between">
    <!-- Top Monogram -->
    <div class="flex flex-col items-center space-y-4">
      <div class="w-10 h-10 rounded-2xl bg-[#D4F754] text-black font-extrabold flex items-center justify-center text-lg shadow-lg shadow-[#D4F754]/25 ring-1 ring-white/20 transition hover:scale-105" title="OmniGaze Mission Control">
        ⚡
      </div>

      <!-- Navigation Group -->
      <div class="flex flex-col items-center space-y-2 pt-2">
        <!-- Dashboard Overview (Active indicator) -->
        <button class="w-10 h-10 rounded-2xl bg-white/10 text-[#D4F754] flex items-center justify-center shadow-inner ring-1 ring-white/15" title="Mission Control Dashboard">
          <i data-lucide="layout-grid" class="w-5 h-5"></i>
        </button>

        <!-- Scenario Switcher Pills -->
        <div class="flex flex-col items-center space-y-1.5 pt-3">
          <span class="text-[9px] font-mono text-zinc-600 uppercase font-bold tracking-wider">SCEN</span>
          <button id="btn-sc-001" class="scenario-btn w-9 h-9 rounded-xl bg-white/[0.03] hover:bg-white/[0.08] border border-white/5 text-xs font-mono font-bold text-zinc-400 hover:text-white transition flex items-center justify-center" title="SC-001: Bridge Girder Shear Crack">
            01
          </button>
          <button id="btn-sc-002" class="scenario-btn w-9 h-9 rounded-xl bg-white/[0.03] hover:bg-white/[0.08] border border-white/5 text-xs font-mono font-bold text-zinc-400 hover:text-white transition flex items-center justify-center" title="SC-002: Pipeline Pitting Corrosion">
            02
          </button>
          <button id="btn-sc-003" class="scenario-btn w-9 h-9 rounded-xl bg-white/[0.03] hover:bg-white/[0.08] border border-white/5 text-xs font-mono font-bold text-zinc-400 hover:text-white transition flex items-center justify-center" title="SC-003: Turbine Blade Defect">
            03
          </button>
          <button id="btn-sc-004" class="scenario-btn w-9 h-9 rounded-xl bg-white/[0.08] border border-[#D4F754]/50 text-xs font-mono font-bold text-[#D4F754] transition flex items-center justify-center ring-1 ring-[#D4F754]/30" title="SC-004: Weld Joint Fatigue Crack">
            04
          </button>
        </div>
      </div>
    </div>

    <!-- Bottom Actions -->
    <div class="flex flex-col items-center space-y-2.5">
      <!-- Forensic Export Audit Record -->
      <button id="btn-export-audit" onclick="exportAuditCertificate()" disabled class="w-10 h-10 rounded-2xl bg-white/[0.03] hover:bg-white/[0.08] border border-white/10 text-[#D4F754] flex items-center justify-center transition disabled:opacity-40 disabled:cursor-not-allowed group relative" title="Export Tamper-Evident SHA-256 Audit Certificate">
        <i data-lucide="shield-check" class="w-5 h-5"></i>
        <span id="audit-btn-text" class="sr-only">EXPORT AUDIT</span>
      </button>

      <!-- Health Ping -->
      <button id="btn-ping-health" onclick="pingHealth()" class="w-10 h-10 rounded-2xl bg-white/[0.03] hover:bg-white/[0.08] border border-white/10 text-zinc-400 hover:text-white flex items-center justify-center transition" title="Diagnostic Telemetry Ping">
        <i data-lucide="activity" class="w-4 h-4"></i>
      </button>

      <!-- Fullscreen Toggle -->
      <button onclick="toggleFullScreen()" class="w-10 h-10 rounded-2xl bg-white/[0.03] hover:bg-white/[0.08] border border-white/10 text-zinc-400 hover:text-white flex items-center justify-center transition" title="Toggle Fullscreen View">
        <i data-lucide="maximize" class="w-4 h-4"></i>
      </button>
    </div>
  </aside>

  <!-- ── Main Area (Header + Grid / Benchmark View) ───────────────────────── -->
  <div class="flex-1 flex flex-col h-screen overflow-hidden">

    <!-- ── Top Header: Sleek Pill Navigation ──────────────────────────────── -->
    <header class="h-14 px-4 border-b border-white/[0.08] bg-[#141417]/80 backdrop-blur-2xl flex items-center justify-between shrink-0 z-30">
      
      <!-- Left Pill: Brand + Optical/Mask Segmented Switcher -->
      <div class="flex items-center space-x-3">
        <!-- Brand Pill -->
        <div class="flex items-center space-x-2 px-3 py-1.5 rounded-full bg-white/[0.04] border border-white/10 text-xs font-mono shadow-sm">
          <span class="w-2 h-2 rounded-full bg-[#D4F754] animate-pulse"></span>
          <span class="font-bold tracking-wider text-white">⚡ OMNIGAZE</span>
          <span class="text-zinc-500 font-sans text-[11px]">SCADA</span>
        </div>

        <!-- Segmented View Switcher -->
        <div class="inline-flex rounded-full border border-white/10 p-0.5 bg-black/60 text-xs font-mono">
          <button id="btn-view-raw" onclick="switchVisionView('raw')" class="px-3 py-1 rounded-full text-zinc-400 hover:text-white transition">
            Optical
          </button>
          <button id="btn-view-sam" onclick="switchVisionView('sam')" class="px-3 py-1 rounded-full bg-[#D4F754] text-black font-bold shadow-md shadow-[#D4F754]/20 transition">
            SAM 2 Mask
          </button>
        </div>
      </div>

      <!-- Center Status: Enterprise SCADA Model Badges -->
      <div class="hidden lg:flex items-center space-x-2.5 text-xs font-mono">
        <!-- Muse Reasoning Status Badge -->
        <div id="muse-badge" class="badge-meta-border flex items-center space-x-2 px-3.5 py-1 rounded-full text-xs font-mono shadow-sm">
          <span id="muse-badge-label"><span class="badge-meta">● REASONING: Meta Muse Spark Open (Baseten Cloud)</span></span>
        </div>

        <!-- SAM 2 Vision Engine Badge -->
        <div id="sam-badge" class="flex items-center space-x-1.5 px-3 py-1 rounded-full bg-white/[0.04] border border-white/10 text-zinc-300 text-xs font-mono shadow-sm">
          <span class="dot w-2 h-2 rounded-full bg-[#D4F754]"></span>
          <span id="sam-badge-label">Vision: SAM 2</span>
        </div>
      </div>

      <!-- Right Header Actions -->
      <div class="flex items-center space-x-2.5">
        <!-- Super-Weapon Benchmark Mode Toggle Pill Button -->
        <button id="btn-benchmark"
                onclick="window.toggleBenchmarkMode()"
                style="cursor: pointer !important; pointer-events: auto !important; position: relative; z-index: 99999;"
                class="px-3.5 py-1.5 rounded-full bg-gradient-to-r from-orange-500/20 via-zinc-900 to-[#D4F754]/20 border border-white/15 text-white hover:border-[#D4F754] text-xs font-mono font-bold tracking-wider transition shadow-sm hover:shadow-[#D4F754]/20 flex items-center space-x-1.5 active:scale-95"
                title="Launch Side-by-Side Benchmark: Passive AI vs OmniGaze">
          <span class="text-[#FF7A00]">⚡</span>
          <span id="benchmark-btn-text">BENCHMARK MODE</span>
        </button>

        <!-- Run Closed-Loop Inspection Pill Button -->
        <button id="btn-run"
                class="px-4 py-1.5 rounded-full bg-[#D4F754] hover:bg-[#e2ff6a] text-black text-xs font-mono font-bold tracking-wider transition shadow-lg shadow-[#D4F754]/25 flex items-center space-x-1.5 active:scale-95">
          <i data-lucide="zap" class="w-3.5 h-3.5 fill-current"></i>
          <span>RUN CLOSED-LOOP</span>
        </button>

        <!-- Live Clock & Ticker -->
        <div class="hidden sm:block text-right text-xs font-mono pl-1 border-l border-white/10 ml-1">
          <div class="text-white font-semibold text-xs tracking-wider" id="utc-clock">00:00:00 UTC</div>
          <div class="text-[10px] text-[#D4F754] font-bold" id="asset-id-ticker">Awaiting Ingest</div>
        </div>
      </div>
    </header>

    <!-- ── Main Grid (Single-Pane Mission Control) ───────────────────────── -->
    <main id="main-mission-control" class="mission-control-grid flex-1 grid grid-cols-1 lg:grid-cols-12 gap-3 p-3 overflow-hidden" style="display: grid;">

      <!-- ── COLUMN 1: Card 1 (Optical Inspection Frame) ────────────────── -->
      <section class="lg:col-span-4 flex flex-col bg-[#141417] border border-white/[0.08] rounded-3xl p-3.5 shadow-2xl overflow-hidden backdrop-blur-xl h-full">
        <!-- Card Top Bar -->
        <div class="h-9 px-1 flex items-center justify-between border-b border-white/[0.06] pb-2 shrink-0">
          <div class="flex items-center space-x-2">
            <i data-lucide="camera" class="w-4 h-4 text-[#D4F754]"></i>
            <span class="text-xs font-bold uppercase tracking-wider text-white">Optical Inspection Frame</span>
          </div>
          <div class="flex items-center space-x-1.5 text-[10px] font-mono">
            <span class="px-2 py-0.5 rounded-full bg-white/[0.04] text-zinc-400 border border-white/5" id="capture-device-tag">Optical Sensor</span>
            <span class="px-2 py-0.5 rounded-full bg-[#D4F754]/10 text-[#D4F754] border border-[#D4F754]/30 font-semibold">640x480 RAW</span>
          </div>
        </div>

        <!-- Viewport: Zero-Gap Optical Container with 5x Zoom Reticle HUD -->
        <div id="optical-feed" class="relative flex-1 bg-black rounded-2xl overflow-hidden scanlines w-full flex items-center justify-center my-2.5" style="height: 100%; min-height: 280px;">
          <img id="inspection-img" 
               src="/mock_telemetry/real_assets/bridge_girder_shear_crack.png" 
               alt="Inspection View" 
               class="w-full h-full object-contain transition-all duration-300"
               style="height: 100%; width: 100%; object-fit: contain;">

          <!-- Reticle HUD Overlay -->
          <div class="absolute inset-0 pointer-events-none border border-[#D4F754]/20 m-2.5 rounded-xl flex flex-col justify-between p-2.5">
            <div class="flex justify-between text-[10px] font-mono text-[#D4F754]/80">
              <span id="target-zone-label">[TARGET ZONE 5X]</span>
              <span id="cam-status">ACTIVE FEED</span>
            </div>
            
            <!-- Crosshairs Center -->
            <div class="flex justify-center items-center">
              <div class="w-10 h-10 border border-[#D4F754]/40 rounded-full flex items-center justify-center relative">
                <div class="w-2 h-2 bg-[#D4F754] rounded-full shadow-lg shadow-[#D4F754]"></div>
                <div class="absolute w-12 h-[1px] bg-[#D4F754]/30"></div>
                <div class="absolute h-12 w-[1px] bg-[#D4F754]/30"></div>
              </div>
            </div>

            <div class="flex justify-between text-[10px] font-mono text-zinc-400">
              <span id="backend-indicator">MODE: SAM 2 PROMPT</span>
              <span>FOV: 84° INDUSTRIAL</span>
            </div>
          </div>

          <!-- Defect Tag with Industrial Orange Ping -->
          <div id="defect-tag" class="hidden absolute top-3 left-3 bg-[#FF7A00] text-black text-xs px-3 py-1.5 rounded-xl shadow-xl font-mono font-bold backdrop-blur-md border border-white/20">
            <div class="flex items-center space-x-1.5">
              <span class="w-2 h-2 rounded-full bg-white animate-ping"></span>
              <span id="defect-type-label">DEFECT DETECTED</span>
            </div>
            <div class="text-[10px] text-zinc-950 font-semibold mt-0.5" id="defect-meta-label">Area: 0.00%</div>
          </div>
        </div>

        <!-- Bottom Stats Counter Bar -->
        <div class="grid grid-cols-2 gap-2 pt-1 font-mono shrink-0">
          <div class="p-2.5 rounded-2xl bg-white/[0.02] border border-white/[0.06] text-center">
            <div class="text-[10px] text-zinc-400 uppercase tracking-wider">Isolated Defect Count</div>
            <div id="stat-defect-count" class="text-xl font-extrabold text-white mt-0.5 tracking-tight">0</div>
          </div>
          <div class="p-2.5 rounded-2xl bg-white/[0.02] border border-white/[0.06] text-center">
            <div class="text-[10px] text-zinc-400 uppercase tracking-wider">Surface Damage Area</div>
            <div id="stat-defect-area" class="text-xl font-extrabold text-[#D4F754] mt-0.5 tracking-tight">0.00%</div>
          </div>
        </div>
      </section>

      <!-- ── COLUMN 2: Card 2 (Telemetry Gauges & Smooth Sparklines) ─────── -->
      <section class="lg:col-span-4 flex flex-col bg-[#141417] border border-white/[0.08] rounded-3xl p-3.5 shadow-2xl overflow-hidden backdrop-blur-xl h-full gap-3">
        <!-- Card Header -->
        <div class="h-9 px-1 flex items-center justify-between border-b border-white/[0.06] pb-2 shrink-0">
          <div class="flex items-center space-x-2">
            <i data-lucide="gauge" class="w-4 h-4 text-[#FF7A00]"></i>
            <span class="text-xs font-bold uppercase tracking-wider text-white">Structural Telemetry</span>
          </div>
          <div id="twin-status-badge" class="px-2.5 py-0.5 rounded-full text-[10px] font-mono bg-white/[0.04] border border-white/10 text-zinc-400 flex items-center space-x-1.5">
            <span class="w-1.5 h-1.5 rounded-full bg-zinc-500"></span>
            <span>AWAITING TELEMETRY</span>
          </div>
        </div>

        <!-- 3 Primary Gauges: Large Bold Metrics with Directional Trend Bars -->
        <div class="grid grid-cols-3 gap-2 shrink-0">
          <!-- Pressure Gauge -->
          <div class="p-3 rounded-2xl bg-white/[0.02] border border-white/[0.06] flex flex-col justify-between">
            <div class="flex justify-between items-center text-[11px] text-zinc-400">
              <span class="font-medium text-white">Pressure</span>
              <span class="text-[10px] font-mono text-zinc-500">&lt;3.5 bar</span>
            </div>
            <div class="my-2.5">
              <div id="val-pressure" class="text-2xl font-black font-mono text-[#D4F754] tracking-tight">--</div>
              <div class="text-[10px] text-zinc-400 font-mono">bar</div>
            </div>
            <div class="w-full bg-white/[0.05] rounded-full h-1.5 overflow-hidden">
              <div id="bar-pressure" class="bg-[#D4F754] h-1.5 rounded-full transition-all duration-700 shadow-sm shadow-[#D4F754]" style="width: 0%;"></div>
            </div>
          </div>

          <!-- Strain Gauge -->
          <div class="p-3 rounded-2xl bg-white/[0.02] border border-white/[0.06] flex flex-col justify-between">
            <div class="flex justify-between items-center text-[11px] text-zinc-400">
              <span class="font-medium text-white">Strain</span>
              <span class="text-[10px] font-mono text-zinc-500">&lt;150 µε</span>
            </div>
            <div class="my-2.5">
              <div id="val-strain" class="text-2xl font-black font-mono text-[#FF7A00] tracking-tight">--</div>
              <div class="text-[10px] text-zinc-400 font-mono">µε</div>
            </div>
            <div class="w-full bg-white/[0.05] rounded-full h-1.5 overflow-hidden">
              <div id="bar-strain" class="bg-[#FF7A00] h-1.5 rounded-full transition-all duration-700 shadow-sm shadow-[#FF7A00]" style="width: 0%;"></div>
            </div>
          </div>

          <!-- Vibration Gauge -->
          <div class="p-3 rounded-2xl bg-white/[0.02] border border-white/[0.06] flex flex-col justify-between">
            <div class="flex justify-between items-center text-[11px] text-zinc-400">
              <span class="font-medium text-white">Vibration</span>
              <span class="text-[10px] font-mono text-zinc-500">&lt;3.0 mm/s</span>
            </div>
            <div class="my-2.5">
              <div id="val-vibration" class="text-2xl font-black font-mono text-white tracking-tight">--</div>
              <div class="text-[10px] text-zinc-400 font-mono">mm/s RMS</div>
            </div>
            <div class="w-full bg-white/[0.05] rounded-full h-1.5 overflow-hidden">
              <div id="bar-vibration" class="bg-white h-1.5 rounded-full transition-all duration-700" style="width: 0%;"></div>
            </div>
          </div>
        </div>

        <!-- Secondary Sensors Pill Strip -->
        <div class="grid grid-cols-3 gap-2 font-mono text-xs shrink-0">
          <div class="p-2 rounded-xl bg-white/[0.02] border border-white/[0.05] flex justify-between items-center">
            <span class="text-[10px] text-zinc-500 uppercase">Temp</span>
            <span id="val-temp" class="font-bold text-white">-- °C</span>
          </div>
          <div class="p-2 rounded-xl bg-white/[0.02] border border-white/[0.05] flex justify-between items-center">
            <span class="text-[10px] text-zinc-500 uppercase">Humidity</span>
            <span id="val-humidity" class="font-bold text-white">-- %</span>
          </div>
          <div class="p-2 rounded-xl bg-white/[0.02] border border-white/[0.05] flex justify-between items-center">
            <span class="text-[10px] text-zinc-500 uppercase">Acoustic</span>
            <span id="val-acoustic" class="font-bold text-white">-- dB</span>
          </div>
        </div>

        <!-- Telemetry Chart Container (Smooth Live Sparkline Canvas) -->
        <div class="flex-1 bg-black/40 rounded-2xl border border-white/[0.06] p-2.5 flex flex-col min-h-[160px] relative">
          <div class="flex justify-between items-center text-[10px] font-mono text-zinc-400 pb-1.5">
            <span class="uppercase font-semibold">Stress Convergence Waveform</span>
            <span id="chart-state-msg" class="text-[#D4F754] font-bold">MONITORING</span>
          </div>
          <div class="flex-1 relative w-full h-full min-h-[120px]">
            <canvas id="telemetryChart"></canvas>
          </div>
        </div>
      </section>

      <!-- ── COLUMN 3: Card 3 (Timeline) + Card 4 (Actuators & Audit) ───── -->
      <section class="lg:col-span-4 flex flex-col h-full gap-3 overflow-hidden">

        <!-- Card 3: Agent Execution Timeline (Gantt Pill Capsules) -->
        <div class="bg-[#141417] border border-white/[0.08] rounded-3xl p-3.5 shadow-2xl flex flex-col gap-2.5 shrink-0 backdrop-blur-xl">
          <div class="flex items-center justify-between border-b border-white/[0.06] pb-2">
            <div class="flex items-center space-x-2">
              <i data-lucide="git-commit" class="w-4 h-4 text-[#D4F754]"></i>
              <span class="text-xs font-bold uppercase tracking-wider text-white">LangGraph Pipeline</span>
            </div>
            <div class="flex items-center space-x-2 text-[10px] font-mono">
              <span id="stream-status" class="text-zinc-400 uppercase font-semibold">STANDBY</span>
              <span id="stopwatch" class="px-2 py-0.5 rounded-full bg-white/[0.04] text-white font-bold border border-white/5">0.0s</span>
            </div>
          </div>

          <!-- Gantt Pill Capsules: Ingest -> SAM -> Muse Reason -> HITL -> Actuate/Verify -->
          <div class="grid grid-cols-1 gap-1.5 font-mono text-xs">
            <!-- Node 1: Ingest -->
            <div id="node-ingest" class="px-3 py-2 rounded-2xl bg-white/[0.02] border border-white/5 text-zinc-500 flex items-center justify-between transition-all duration-300">
              <div class="flex items-center space-x-2.5">
                <span class="status-dot w-2 h-2 rounded-full bg-zinc-700"></span>
                <span class="font-bold text-xs tracking-wider">01 INGEST TELEMETRY</span>
              </div>
              <span class="text-[10px] opacity-60">SENSORS</span>
            </div>

            <!-- Node 2: Segment -->
            <div id="node-segment" class="px-3 py-2 rounded-2xl bg-white/[0.02] border border-white/5 text-zinc-500 flex items-center justify-between transition-all duration-300">
              <div class="flex items-center space-x-2.5">
                <span class="status-dot w-2 h-2 rounded-full bg-zinc-700"></span>
                <span class="font-bold text-xs tracking-wider">02 SAM 2 SEGMENT</span>
              </div>
              <span class="text-[10px] opacity-60">MASKS</span>
            </div>

            <!-- Node 3: Muse Reason -->
            <div id="node-reasoning" class="px-3 py-2 rounded-2xl bg-white/[0.02] border border-white/5 text-zinc-500 flex items-center justify-between transition-all duration-300">
              <div class="flex items-center space-x-2.5">
                <span class="status-dot w-2 h-2 rounded-full bg-zinc-700"></span>
                <span class="font-bold text-xs tracking-wider">03 MUSE SPARK REASON</span>
              </div>
              <div class="flex items-center space-x-1.5">
                <span id="severity-badge" class="hidden text-[10px] font-bold px-1.5 py-0.5 rounded-full bg-[#FF7A00] text-black">CRITICAL</span>
              </div>
            </div>

            <!-- Node 4: Mitigation Action -->
            <div id="node-action" class="px-3 py-2 rounded-2xl bg-white/[0.02] border border-white/5 text-zinc-500 flex items-center justify-between transition-all duration-300">
              <div class="flex items-center space-x-2.5">
                <span class="status-dot w-2 h-2 rounded-full bg-zinc-700"></span>
                <span class="font-bold text-xs tracking-wider">04 MITIGATION DISPATCH</span>
              </div>
              <span class="text-[10px] opacity-60">HITL GATE</span>
            </div>

            <!-- Node 5: Closed-Loop Verification -->
            <div id="node-verify" class="px-3 py-2 rounded-2xl bg-white/[0.02] border border-white/5 text-zinc-500 flex items-center justify-between transition-all duration-300">
              <div class="flex items-center space-x-2.5">
                <span class="status-dot w-2 h-2 rounded-full bg-zinc-700"></span>
                <span class="font-bold text-xs tracking-wider">05 CLOSED-LOOP VERIFY</span>
              </div>
              <span class="text-[10px] opacity-60">STABILITY</span>
            </div>
          </div>
        </div>

        <!-- Card 4: Closed-Loop Actuator Mesh & Audit Ledger Terminal -->
        <div class="flex-1 bg-[#141417] border border-white/[0.08] rounded-3xl p-3.5 shadow-2xl flex flex-col gap-2.5 overflow-hidden backdrop-blur-xl">
          <div class="flex items-center justify-between border-b border-white/[0.06] pb-2 shrink-0">
            <div class="flex items-center space-x-2">
              <i data-lucide="cpu" class="w-4 h-4 text-[#D4F754]"></i>
              <span class="text-xs font-bold uppercase tracking-wider text-white">Actuator Mesh & Audit</span>
            </div>
            <span id="action-count" class="px-2 py-0.5 rounded-full bg-white/[0.04] text-[10px] font-mono text-zinc-400 border border-white/5">0 active</span>
          </div>

          <!-- Actuators Dispatched Container -->
          <div id="actions-container" class="space-y-1.5 shrink-0 max-h-[85px] overflow-y-auto">
            <div class="p-2 rounded-2xl bg-white/[0.02] border border-white/5 text-[11px] font-mono text-zinc-500 text-center">
              Awaiting Countermeasure Trigger
            </div>
          </div>

          <!-- SHA-256 Ledger Ticker Pill -->
          <div class="flex items-center justify-between px-3 py-1.5 rounded-2xl bg-black/40 border border-white/[0.06] text-[10px] font-mono shrink-0">
            <div id="ledger-ticker-text" class="truncate text-zinc-400">
              [LEDGER] Standby for sealed blocks
            </div>
            <div class="flex items-center space-x-1.5 shrink-0 ml-2">
              <span id="ledger-chain-depth" class="text-zinc-500">CHAIN: #0</span>
              <span id="ledger-tamper-tag" class="hidden text-[#D4F754] font-bold text-[9px] px-2 py-0.5 rounded-full bg-[#D4F754]/10 border border-[#D4F754]/30">TAMPER-EVIDENT</span>
            </div>
          </div>

          <!-- Live SCADA Terminal Log -->
          <div id="terminal-log" class="flex-1 p-2.5 rounded-2xl bg-black/60 border border-white/[0.06] font-mono text-[10px] text-zinc-400 overflow-y-auto space-y-1">
            <div class="text-zinc-600">// OmniGaze Autonomous Visual SCADA Initialized.</div>
            <div class="text-zinc-600">// Ready for closed-loop execution.</div>
          </div>
        </div>
      </section>

    </main>

    <!-- ── BENCHMARK MODE COMPARATIVE STAGE (Ultra-Clean Rounded Dark Aesthetic) ── -->
    <main id="benchmark-view" class="benchmark-grid hidden flex-1 flex flex-col p-3 gap-3 overflow-y-auto" style="display: none;">
      <!-- Benchmark Control Banner -->
      <div class="p-3 px-4 rounded-3xl bg-[#141417] border border-white/10 flex flex-col sm:flex-row items-center justify-between gap-3 shadow-2xl shrink-0">
        <div class="flex items-center space-x-3 font-mono text-xs">
          <span class="px-3 py-1 rounded-full bg-[#D4F754]/10 border border-[#D4F754]/30 text-[#D4F754] font-bold uppercase tracking-wider flex items-center gap-1.5 shadow-sm">
            <i data-lucide="zap" class="w-3.5 h-3.5 text-[#D4F754] fill-current"></i>
            SUPER-WEAPON BENCHMARK
          </span>
          <span class="text-zinc-300 font-semibold hidden md:inline">
            Live Comparative Experiment: Passive AI (Detection-Only) vs OmniGaze (Autonomous Closed-Loop Mitigation)
          </span>
        </div>

        <div class="flex items-center space-x-2.5 font-mono text-xs">
          <button id="btn-benchmark-run" onclick="triggerBenchmarkRun()" class="px-4 py-1.5 rounded-full bg-[#D4F754] hover:bg-[#e2ff6a] text-black font-bold transition flex items-center space-x-1.5 shadow-lg shadow-[#D4F754]/20 active:scale-95">
            <i data-lucide="play" class="w-3.5 h-3.5 fill-current"></i>
            <span>RUN LIVE BENCHMARK</span>
          </button>
          <button id="btn-exit-benchmark" onclick="window.toggleBenchmarkMode()" class="px-3.5 py-1.5 rounded-full bg-white/[0.04] hover:bg-white/[0.08] border border-white/10 text-zinc-300 hover:text-white font-bold transition flex items-center space-x-1.5 active:scale-95" style="cursor: pointer !important; pointer-events: auto !important; z-index: 99999;">
            <i data-lucide="x" class="w-3.5 h-3.5"></i>
            <span>EXIT BENCHMARK</span>
          </button>
        </div>
      </div>

      <!-- Comparative Split Grid (2 Columns) -->
      <div class="flex-1 grid grid-cols-1 lg:grid-cols-2 gap-3 min-h-0">

        <!-- ── LEFT PANEL: LEGACY PASSIVE AI (DETECTION-ONLY) ─────────────── -->
        <section class="flex flex-col bg-[#141417] rounded-3xl border border-red-500/30 shadow-2xl overflow-hidden backdrop-blur-xl">
          <!-- Ambient Caution Line -->
          <div class="h-1 bg-gradient-to-r from-red-600 via-[#FF7A00] to-red-600"></div>

          <!-- Header -->
          <div class="h-11 px-4 bg-red-950/20 border-b border-red-900/30 flex items-center justify-between">
            <div class="flex items-center space-x-2.5">
              <div class="w-7 h-7 rounded-xl bg-red-950/60 border border-red-500/50 flex items-center justify-center text-red-400">
                <i data-lucide="eye-off" class="w-4 h-4"></i>
              </div>
              <div>
                <h2 class="text-xs font-bold text-red-200 tracking-wider uppercase font-mono">
                  LEGACY PASSIVE AI (DETECTION-ONLY)
                </h2>
                <div class="text-[9px] text-red-400/80 font-mono">No Actuator Closed-Loop Mitigation</div>
              </div>
            </div>
            <span id="passive-badge" class="px-2.5 py-0.5 rounded-full text-[10px] font-mono font-bold bg-red-950/80 border border-red-500/40 text-red-300">
              STANDBY
            </span>
          </div>

          <!-- Content Body -->
          <div class="p-3 flex-1 flex flex-col space-y-3 overflow-y-auto">
            <!-- Inspection Frame -->
            <div class="relative h-44 rounded-2xl overflow-hidden bg-black flex items-center justify-center border border-white/5">
              <img id="passive-img" 
                   src="/mock_telemetry/real_assets/bridge_girder_shear_crack.png" 
                   alt="Passive AI Frame" 
                   class="w-full h-full object-contain">
              <div class="absolute bottom-2 left-2 bg-red-950/90 border border-red-500/50 text-red-300 text-[10px] font-mono px-2 py-0.5 rounded-lg">
                ⚠️ UNCHECKED DEFECT PROPAGATION
              </div>
            </div>

            <!-- Runaway Divergence Chart -->
            <div class="h-44 p-2.5 rounded-2xl bg-black/40 border border-white/[0.06] flex flex-col">
              <div class="flex justify-between items-center text-[10px] font-mono text-zinc-400 pb-1">
                <span class="text-red-400 font-bold">UNCHECKED STRESS SURGE</span>
                <span id="passive-chart-status" class="text-zinc-500">Awaiting Run</span>
              </div>
              <div class="flex-1 relative w-full h-full">
                <canvas id="passive-benchmark-chart"></canvas>
              </div>
            </div>

            <!-- Metrics -->
            <div class="grid grid-cols-3 gap-2 font-mono text-center">
              <div class="p-2.5 rounded-2xl bg-white/[0.02] border border-white/[0.06]">
                <div class="text-[9px] text-zinc-500 uppercase">Pressure</div>
                <div id="passive-metric-pressure" class="text-lg font-black text-red-400 mt-0.5">--</div>
              </div>
              <div class="p-2.5 rounded-2xl bg-white/[0.02] border border-white/[0.06]">
                <div class="text-[9px] text-zinc-500 uppercase">Strain</div>
                <div id="passive-metric-strain" class="text-lg font-black text-red-400 mt-0.5">--</div>
              </div>
              <div class="p-2.5 rounded-2xl bg-white/[0.02] border border-white/[0.06]">
                <div class="text-[9px] text-zinc-500 uppercase">Vibration</div>
                <div id="passive-metric-vib" class="text-lg font-black text-red-400 mt-0.5">--</div>
              </div>
            </div>

            <!-- Culmination Alert Banner -->
            <div id="passive-culmination-banner" class="hidden p-3 rounded-2xl bg-red-950/90 border-2 border-red-500 text-red-200 font-mono text-xs flex items-center space-x-3 shadow-xl">
              <i data-lucide="alert-triangle" class="w-6 h-6 text-red-400 shrink-0 animate-bounce"></i>
              <div>
                <div class="font-bold text-red-300 uppercase">CRITICAL SYSTEM FAILURE: CATASTROPHIC RUPTURE</div>
                <div class="text-[10px] text-red-400 mt-0.5">Passive AI alerted 10 minutes ago, but took NO physical countermeasure. Structural threshold breached.</div>
              </div>
            </div>

            <!-- Terminal -->
            <div id="passive-status-log" class="p-2.5 rounded-2xl bg-black/60 border border-white/[0.06] font-mono text-[10px] text-red-300/80 h-20 overflow-y-auto space-y-0.5">
              <div>// Passive AI monitoring thread ready.</div>
            </div>
          </div>
        </section>

        <!-- ── RIGHT PANEL: AUTONOMOUS OMNIGAZE (CLOSED-LOOP) ─────────────── -->
        <section class="flex flex-col bg-[#141417] rounded-3xl border border-[#D4F754]/30 shadow-2xl overflow-hidden backdrop-blur-xl">
          <!-- Ambient Safety Line -->
          <div class="h-1 bg-gradient-to-r from-[#D4F754] via-emerald-400 to-[#D4F754]"></div>

          <!-- Header -->
          <div class="h-11 px-4 bg-[#D4F754]/5 border-b border-[#D4F754]/20 flex items-center justify-between">
            <div class="flex items-center space-x-2.5">
              <div class="w-7 h-7 rounded-xl bg-[#D4F754]/10 border border-[#D4F754]/40 flex items-center justify-center text-[#D4F754]">
                <i data-lucide="shield-check" class="w-4 h-4"></i>
              </div>
              <div>
                <h2 class="text-xs font-bold text-[#D4F754] tracking-wider uppercase font-mono">
                  AUTONOMOUS OMNIGAZE (CLOSED-LOOP)
                </h2>
                <div class="text-[9px] text-[#D4F754]/80 font-mono">Meta Muse Spark Open + Meta SAM 2 + Active Mitigation</div>
              </div>
            </div>
            <span id="omnigaze-badge" class="px-2.5 py-0.5 rounded-full text-[10px] font-mono font-bold bg-[#D4F754]/10 border border-[#D4F754]/30 text-[#D4F754]">
              STANDBY
            </span>
          </div>

          <!-- Content Body -->
          <div class="p-3 flex-1 flex flex-col space-y-3 overflow-y-auto">
            <!-- Inspection Frame -->
            <div class="relative h-44 rounded-2xl overflow-hidden bg-black flex items-center justify-center border border-white/5">
              <img id="omnigaze-img" 
                   src="/mock_telemetry/annotated_defects.png" 
                   alt="OmniGaze SAM 2 Defect Mask" 
                   class="w-full h-full object-contain">
              <div class="absolute bottom-2 left-2 bg-[#D4F754]/90 text-black text-[10px] font-mono font-bold px-2 py-0.5 rounded-lg">
                ✅ SAM 2 MASK + ACTIVE INTERLOCK MITIGATION
              </div>
            </div>

            <!-- Controlled Stabilization Chart -->
            <div class="h-44 p-2.5 rounded-2xl bg-black/40 border border-white/[0.06] flex flex-col">
              <div class="flex justify-between items-center text-[10px] font-mono text-zinc-400 pb-1">
                <span class="text-[#D4F754] font-bold">CONTROLLED STABILIZATION CURVE</span>
                <span id="omnigaze-chart-status" class="text-zinc-500">Awaiting Run</span>
              </div>
              <div class="flex-1 relative w-full h-full">
                <canvas id="omnigaze-benchmark-chart"></canvas>
              </div>
            </div>

            <!-- Metrics -->
            <div class="grid grid-cols-3 gap-2 font-mono text-center">
              <div class="p-2.5 rounded-2xl bg-white/[0.02] border border-white/[0.06]">
                <div class="text-[9px] text-zinc-500 uppercase">Pressure</div>
                <div id="omnigaze-metric-pressure" class="text-lg font-black text-[#D4F754] mt-0.5">--</div>
              </div>
              <div class="p-2.5 rounded-2xl bg-white/[0.02] border border-white/[0.06]">
                <div class="text-[9px] text-zinc-500 uppercase">Strain</div>
                <div id="omnigaze-metric-strain" class="text-lg font-black text-[#D4F754] mt-0.5">--</div>
              </div>
              <div class="p-2.5 rounded-2xl bg-white/[0.02] border border-white/[0.06]">
                <div class="text-[9px] text-zinc-500 uppercase">Vibration</div>
                <div id="omnigaze-metric-vib" class="text-lg font-black text-[#D4F754] mt-0.5">--</div>
              </div>
            </div>

            <!-- Culmination Recovery Banner -->
            <div id="omnigaze-culmination-banner" class="hidden p-3 rounded-2xl bg-emerald-950/90 border-2 border-emerald-500 text-emerald-200 font-mono text-xs flex items-center space-x-3 shadow-xl">
              <i data-lucide="check-circle" class="w-6 h-6 text-emerald-400 shrink-0"></i>
              <div>
                <div class="font-bold text-emerald-300 uppercase">CLOSED-LOOP RECOVERY CONFIRMED: SYSTEM STABILIZED</div>
                <div class="text-[10px] text-emerald-400 mt-0.5">OmniGaze autonomously diagnosed shear crack & executed robotic valve relief. Stress returned to safe envelope.</div>
              </div>
            </div>

            <!-- Dispatched Countermeasures -->
            <div class="p-2.5 rounded-2xl bg-black/40 border border-white/[0.06]">
              <div class="flex justify-between items-center text-[10px] font-mono text-zinc-400 pb-1">
                <span>Autonomous Actuators</span>
                <span id="omnigaze-actuator-badge" class="text-[#D4F754] font-bold">0 Dispatched</span>
              </div>
              <div id="omnigaze-actuators-container" class="space-y-1 font-mono text-[10px]">
                <div class="text-zinc-600">// Standing by for LangGraph autonomous action loop...</div>
              </div>
            </div>

            <!-- Terminal -->
            <div id="omnigaze-status-log" class="p-2.5 rounded-2xl bg-black/60 border border-white/[0.06] font-mono text-[10px] text-[#D4F754]/80 h-16 overflow-y-auto space-y-0.5">
              <div>// OmniGaze agent ready for side-by-side benchmark comparison.</div>
            </div>
          </div>
        </section>

      </div>
    </main>

  </div>

  <!-- ── HITL Safety Interlock Modal ──────────────────────────────────────── -->
  <div id="hitl-modal" class="hidden fixed inset-0 z-50 bg-black/85 backdrop-blur-2xl flex items-center justify-center p-4">
    <div class="max-w-md w-full bg-[#141417] border-2 border-[#FF7A00] rounded-3xl p-6 shadow-2xl shadow-[#FF7A00]/25 space-y-5">
      
      <!-- Modal Header -->
      <div class="flex items-start justify-between border-b border-white/10 pb-4">
        <div class="flex items-center space-x-3">
          <div class="w-10 h-10 rounded-2xl bg-[#FF7A00]/10 border border-[#FF7A00]/50 flex items-center justify-center text-[#FF7A00] animate-pulse">
            <i data-lucide="shield-alert" class="w-5 h-5"></i>
          </div>
          <div>
            <h3 class="text-base font-bold text-white tracking-tight">OPERATOR AUTHORIZATION REQUIRED</h3>
            <p class="text-xs text-zinc-400 font-mono mt-0.5">Physical Countermeasure Safety Interlock</p>
          </div>
        </div>
        <div id="hitl-risk-level" class="px-2.5 py-1 rounded-full bg-red-950/80 border border-red-500 text-red-200 text-xs font-mono font-bold flex items-center space-x-1.5">
          <span class="w-2 h-2 rounded-full bg-red-500 animate-ping"></span>
          <span>CRITICAL</span>
        </div>
      </div>

      <!-- Action Details -->
      <div class="space-y-2.5 font-mono text-xs">
        <div class="p-3 rounded-2xl bg-white/[0.02] border border-white/5 flex justify-between items-center">
          <span class="text-zinc-500">Proposed Action</span>
          <span id="hitl-action-name" class="font-bold text-[#FF7A00]">emergency_lockdown</span>
        </div>
        <div class="p-3 rounded-2xl bg-white/[0.02] border border-white/5 flex justify-between items-center">
          <span class="text-zinc-500">Target Asset</span>
          <span id="hitl-target-asset" class="font-bold text-white">sector-flange</span>
        </div>
        <div class="p-3 rounded-2xl bg-white/[0.02] border border-white/5 flex justify-between items-center">
          <span class="text-zinc-500">Verification Source</span>
          <span id="hitl-asset" class="font-bold text-[#D4F754]">Meta Muse Spark Open</span>
        </div>
      </div>

      <!-- Countdown Bar -->
      <div class="space-y-1.5 font-mono">
        <div class="flex justify-between text-xs">
          <span class="text-zinc-400">Interlock Timeout Window:</span>
          <span id="hitl-timer-label" class="text-[#FF7A00] font-bold">30.0s</span>
        </div>
        <div class="w-full bg-white/[0.05] rounded-full h-2 overflow-hidden">
          <div id="hitl-progress-bar" class="bg-[#FF7A00] h-2 rounded-full transition-all duration-100 shadow-sm shadow-[#FF7A00]" style="width: 100%;"></div>
        </div>
        <div class="text-[10px] text-zinc-500 text-right">Failsafe: Auto-Abort on timeout</div>
      </div>

      <!-- Action Buttons -->
      <div class="grid grid-cols-2 gap-3 pt-2 font-mono text-xs font-bold">
        <button id="btn-hitl-abort" class="py-2.5 px-4 rounded-full bg-white/[0.04] hover:bg-white/[0.08] border border-white/10 text-zinc-300 hover:text-white transition flex items-center justify-center space-x-1.5 active:scale-95">
          <i data-lucide="x-circle" class="w-4 h-4"></i>
          <span>ABORT ACTION</span>
        </button>
        <button id="btn-hitl-approve" class="py-2.5 px-4 rounded-full bg-[#D4F754] hover:bg-[#e2ff6a] text-black transition flex items-center justify-center space-x-1.5 shadow-lg shadow-[#D4F754]/25 active:scale-95">
          <i data-lucide="check-circle-2" class="w-4 h-4 fill-current"></i>
          <span>APPROVE MITIGATION</span>
        </button>
      </div>

    </div>
  </div>

'''

# Combine the new HTML with the exact existing dashboard script
full_new_content = new_html_head_and_body + '\n  ' + dashboard_script + '\n</body>\n</html>\n'

with open('static/index.html', 'w', encoding='utf-8') as f:
    f.write(full_new_content)

print(f"Successfully generated new static/index.html ({len(full_new_content)} bytes)")
