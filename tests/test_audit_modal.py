import urllib.request

def test_modal_elements():
    res = urllib.request.urlopen("http://localhost:8080/")
    html = res.read().decode("utf-8")
    checks = [
        'id="btn-export-audit"',
        'id="modal-audit-certificate"',
        'CRYPTOGRAPHIC AUDIT CERTIFICATE (ISO-10816 COMPLIANT)',
        'modal-cert-merkle-root',
        '25724c8901ad...e91d',
        'modal-cert-duration',
        '15.35s',
        'modal-cert-interlock',
        'PV-12 Throttled (-35%), Sector Flange Sealed',
        'modal-cert-operator-sig',
        'VERIFIED · SHA-256 RSA-4096 SIGNED',
        'id="btn-download-audit-json"',
        'id="btn-close-audit-modal"',
        'downloadAuditJsonBlob'
    ]
    all_passed = True
    for c in checks:
        found = c in html
        print(f"[{'PASS' if found else 'FAIL'}] {c}")
        if not found:
            all_passed = False
    assert all_passed, "Some checks failed!"
    print("\nALL MODAL SPECIFICATIONS VERIFIED!")

if __name__ == "__main__":
    test_modal_elements()
