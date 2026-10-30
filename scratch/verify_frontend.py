with open('static/index.html', 'r', encoding='utf-8') as f:
    html = f.read()

checks = [
    # Navigation & Header
    ('btn-benchmark', 'id="btn-benchmark"' in html),
    ('btn-run-closed-loop', 'id="btn-run-closed-loop"' in html),
    ('btn-run fallback', 'id="btn-run"' in html),
    ('OMNIGAZE brand', 'OMNIGAZE' in html),
    ('SYSTEM NOMINAL', 'SYSTEM NOMINAL' in html),
    ('Live Telemetry tab', 'Live Telemetry' in html),
    ('Benchmark Comparison tab', 'Benchmark Comparison' in html),
    ('Meta SAM 2.1 + Muse Spark badge', 'Meta SAM 2.1 + Muse Spark' in html),

    # 1. Executive Incident Status Banner
    ('Executive Status Banner element', 'id="executive-status-banner"' in html),
    ('Banner default text', 'SYSTEM STATUS: CONTINUOUS AUTONOMOUS MONITORING · ALL ASSETS IN SAFE ENVELOPE' in html),
    ('Banner critical text in JS', '⚡ CRITICAL YIELD BREACH DETECTED · AUTONOMOUS AGENT ACTIVE · COUNTERMEASURES ENGAGED' in html),
    ('Banner stabilized text in JS', '✔ CLOSED-LOOP STABILIZATION VERIFIED · ASSET SECURED · ESTIMATED DOWNTIME PREVENTED: $2.4M' in html),

    # 2. Telemetry Chart & Visual Safety Progress Bars
    ('Clean single-scale % of limit title', 'Stress Convergence Trend (% of Limit)' in html),
    ('Redline threshold plugin in JS', 'redlineThreshold' in html),
    ('100% REDLINE THRESHOLD label', '100% REDLINE THRESHOLD' in html),
    ('Pressure threshold bar markings', '6.0' in html),
    ('Strain threshold bar markings', '350' in html),
    ('Vibration threshold bar markings', '7.1' in html),
    ('val-pressure', 'id="val-pressure"' in html),
    ('val-strain', 'id="val-strain"' in html),
    ('val-vibration', 'id="val-vibration"' in html),
    ('bar-pressure progress', 'id="bar-pressure"' in html),
    ('bar-strain progress', 'id="bar-strain"' in html),
    ('bar-vibration progress', 'id="bar-vibration"' in html),

    # 3. Visual Actuator Cards
    ('Card 1 Relief Valve PV-12', 'Relief Valve PV-12' in html),
    ('Card 1 Status THROTTLED -35%', 'THROTTLED -35%' in html),
    ('Card 2 Sector Flange Interlock', 'Sector Flange Interlock' in html),
    ('Card 2 Status ISOLATED & SEALED', 'ISOLATED & SEALED' in html),
    ('Card 3 Drone IR Inspection (DJI-Mavic3)', 'Drone IR Inspection (DJI-Mavic3)' in html),
    ('Card 3 Status AIRBORNE ON TARGET', 'AIRBORNE ON TARGET' in html),
    ('Export ISO-10816 Audit button', 'Export ISO-10816 Audit' in html),

    # 4. Interactive Stress Surge Demonstration Button
    ('btn-inject-surge', 'id="btn-inject-surge"' in html),
    ('SIMULATE SURGE label', 'SIMULATE SURGE' in html),
    ('injectStressSurge JS function', 'injectStressSurge' in html),

    # 5. Optical Inspection Zoom & Clarity
    ('Optical feed corner reticle bracket', 'rounded-tl-sm' in html and 'rounded-br-sm' in html),
    ('defect-tag', 'id="defect-tag"' in html),
    ('FATIGUE CRACK · 98.0% CONF', 'FATIGUE CRACK · 98.0% CONF' in html),

    # 6. Functionality Preservation
    ('Scenario SC-001', 'id="btn-sc-001"' in html),
    ('Scenario SC-004', 'id="btn-sc-004"' in html),
    ('HITL Modal', 'id="hitl-modal"' in html),
    ('toggleBenchmarkMode', 'toggleBenchmarkMode' in html),
    ('No gimmicky // SECTION in HTML', '// SECTION' not in html),
    ('No gimmicky // STRESS in HTML', '// STRESS' not in html),
]

all_passed = True
for name, passed in checks:
    status = "PASS" if passed else "FAIL"
    if not passed:
        all_passed = False
    print(f"[{status}] {name}")

print("ALL PASSED:" if all_passed else "SOME FAILED")
