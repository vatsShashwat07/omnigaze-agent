import re

with open('static/index.html', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update .scada-panel in <style>
old_scada_panel = """    /* Tier-1 Enterprise SCADA Panel Card Elevation */
    .scada-panel {
      box-shadow: inset 0 1px 0 0 rgba(255, 255, 255, 0.07), 0 10px 30px -10px rgba(0, 0, 0, 0.5) !important;
      background: #12141a !important;
      border: 1px solid rgba(255, 255, 255, 0.08) !important;
      border-radius: 1.25rem !important;
    }"""

new_scada_panel = """    /* Tier-1 Enterprise SCADA Panel Card Elevation with Plenum Glassmorphism */
    .scada-panel {
      box-shadow: inset 0 1px 0 0 rgba(255, 255, 255, 0.07), 0 10px 30px -10px rgba(0, 0, 0, 0.5) !important;
      background: rgba(14, 16, 22, 0.82) !important;
      backdrop-filter: blur(16px) !important;
      -webkit-backdrop-filter: blur(16px) !important;
      border: 1px solid rgba(255, 255, 255, 0.07) !important;
      border-radius: 1.25rem !important;
    }"""

if old_scada_panel in content:
    content = content.replace(old_scada_panel, new_scada_panel)
else:
    content = re.sub(
        r'\.scada-panel\s*\{[\s\S]*?border-radius:\s*1\.25rem\s*!important;\s*\}',
        """.scada-panel {
      box-shadow: inset 0 1px 0 0 rgba(255, 255, 255, 0.07), 0 10px 30px -10px rgba(0, 0, 0, 0.5) !important;
      background: rgba(14, 16, 22, 0.82) !important;
      backdrop-filter: blur(16px) !important;
      -webkit-backdrop-filter: blur(16px) !important;
      border: 1px solid rgba(255, 255, 255, 0.07) !important;
      border-radius: 1.25rem !important;
    }""",
        content
    )

# 2. Add canvas right after <body ...>
old_body_tag = '<body class="h-screen w-screen bg-[#08090c] text-white flex select-none font-sans overflow-hidden">'
new_body_and_canvas = """<body class="h-screen w-screen bg-[#05070d] text-white flex select-none font-sans overflow-hidden relative">

  <!-- Interactive 3D Flowing Particle Wave Background Canvas (Plenum Deep Cosmic Blue) -->
  <canvas id="plenum-particle-canvas" class="fixed inset-0 pointer-events-none" style="position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; z-index: 0; pointer-events: none;"></canvas>"""

if old_body_tag in content:
    content = content.replace(old_body_tag, new_body_and_canvas)
else:
    content = re.sub(
        r'<body[^>]*>',
        new_body_and_canvas,
        content
    )

# 3. Ensure containers have relative z-10 / z-20
content = content.replace(
    '<aside class="w-16 h-full flex flex-col',
    '<aside class="relative z-10 w-16 h-full flex flex-col'
)

content = content.replace(
    '<!-- ── Main Area (Header + Grid / Benchmark View) ───────────────────────── -->\n  <div class="flex-1 flex flex-col',
    '<!-- ── Main Area (Header + Grid / Benchmark View) ───────────────────────── -->\n  <div class="relative z-10 flex-1 flex flex-col'
)

content = content.replace(
    '<header class="h-14 px-4 border-b border-white/[0.08] bg-[#12141a]/80 backdrop-blur-2xl flex items-center justify-between shrink-0 z-30">',
    '<header class="relative z-20 h-14 px-4 border-b border-white/[0.08] bg-[#12141a]/80 backdrop-blur-2xl flex items-center justify-between shrink-0">'
)

content = content.replace(
    '<main id="main-mission-control" class="mission-control-grid flex-1 grid grid-cols-1 lg:grid-cols-12 gap-3 p-3 overflow-hidden" style="display: grid;">',
    '<main id="main-mission-control" class="relative z-10 mission-control-grid flex-1 grid grid-cols-1 lg:grid-cols-12 gap-3 p-3 overflow-hidden" style="display: grid;">'
)

content = content.replace(
    '<main id="benchmark-view" class="benchmark-grid hidden flex-1 flex flex-col p-3 gap-3 overflow-y-auto" style="display: none;">',
    '<main id="benchmark-view" class="relative z-10 benchmark-grid hidden flex-1 flex flex-col p-3 gap-3 overflow-y-auto" style="display: none;">'
)

# 4. Insert 3D Particle Wave Engine before closing </script>
plenum_engine_code = """
    // ── Plenum 3D Flowing Particle Wave Background Engine ────────────────
    (function initPlenumBackground() {
      const canvas = document.getElementById('plenum-particle-canvas');
      if (!canvas) return;
      const ctx = canvas.getContext('2d');
      let width, height;
      let step = 0;

      function resize() {
        width = canvas.width = window.innerWidth;
        height = canvas.height = window.innerHeight;
      }
      window.addEventListener('resize', resize);
      resize();

      // 3D Grid Configuration
      const SEPARATION = 32;
      const AMOUNTX = 65;
      const AMOUNTY = 45;

      function render() {
        ctx.fillStyle = '#05070d';
        ctx.fillRect(0, 0, width, height);

        // Deep ambient cosmic radial glow
        const gradient = ctx.createRadialGradient(width * 0.5, height * 0.45, 50, width * 0.5, height * 0.45, width * 0.7);
        gradient.addColorStop(0, 'rgba(10, 35, 75, 0.45)');
        gradient.addColorStop(0.6, 'rgba(4, 14, 32, 0.2)');
        gradient.addColorStop(1, 'rgba(2, 4, 10, 0)');
        ctx.fillStyle = gradient;
        ctx.fillRect(0, 0, width, height);

        step += 0.022;

        // Render undulating 3D particle mesh
        for (let ix = 0; ix < AMOUNTX; ix++) {
          for (let iy = 0; iy < AMOUNTY; iy++) {
            // Mathematical wave function simulating deep ocean/space turbulence
            const xPos = (ix - AMOUNTX / 2) * SEPARATION;
            const zPos = (iy - AMOUNTY / 2) * SEPARATION + 350;
            const yPos = Math.sin((ix + step * 2) * 0.28) * 45 + Math.sin((iy + step) * 0.35) * 45;

            // 3D to 2D projection
            const fov = 340;
            const scale = fov / (fov + zPos);
            const x2d = (xPos * scale) + (width / 2);
            const y2d = (yPos * scale) + (height * 0.58);

            if (scale > 0 && x2d >= 0 && x2d <= width && y2d >= 0 && y2d <= height) {
              const alpha = Math.min(Math.max((scale - 0.25) * 1.3, 0.1), 0.95);
              const radius = Math.max(scale * 2.2, 0.7);

              ctx.beginPath();
              ctx.arc(x2d, y2d, radius, 0, Math.PI * 2);

              // Dual-tone Plenum glowing particle colors (Electric Cyan to Deep Royal Blue)
              if ((ix + iy) % 4 === 0) {
                ctx.fillStyle = `rgba(0, 240, 255, ${alpha})`;
                ctx.shadowBlur = 6;
                ctx.shadowColor = '#00f0ff';
              } else {
                ctx.fillStyle = `rgba(56, 130, 246, ${alpha * 0.75})`;
                ctx.shadowBlur = 0;
              }
              ctx.fill();
            }
          }
        }
        requestAnimationFrame(render);
      }
      render();
    })();
"""

# Insert before </script>
content = content.replace('  </script>\n</body>', plenum_engine_code + '  </script>\n</body>')

with open('static/index.html', 'w', encoding='utf-8') as f:
    f.write(content)

print(f"Successfully integrated Plenum 3D wave background into static/index.html ({len(content)} bytes)")
