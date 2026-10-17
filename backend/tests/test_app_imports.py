import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent

# what the deployed image leaves out (the "forensics" and "dev" extras)
NOT_IN_IMAGE = ["numpy", "cv2", "reportlab"]


def test_app_starts_without_forensics_libraries():
    """The production image installs only the base dependencies: the app must import and build without the
    forensics extras (a missing import there stopped a deploy once)."""
    blocked = "; ".join(f"sys.modules[{m!r}] = None" for m in NOT_IN_IMAGE)
    code = (f"import sys; {blocked}; "
            "from claimlens.main import create_app; from claimlens.chat import tools; "
            "print('ok', tools.FORENSICS)")
    done = subprocess.run([sys.executable, "-c", code], cwd=BACKEND, capture_output=True, text=True,
                          env={"PYTHONPATH": str(BACKEND), "PATH": "/usr/bin:/bin"})
    assert done.returncode == 0, done.stderr[-2000:]
    assert done.stdout.strip() == "ok False"


def test_check_region_says_unavailable_without_forensics(monkeypatch):
    from claimlens.chat import tools

    monkeypatch.setattr(tools, "FORENSICS", False)
    page = type("P", (), {"kind": "image", "doc": "claim", "page": 1, "width": 600, "height": 800})()
    monkeypatch.setattr(tools, "_page", lambda ctx, doc, n: page)
    assert tools._check_region({"doc": "claim", "page": 1, "bbox": [1, 1, 50, 50]}, None, None, None) == {
        "error": "photo checks aren't available on this server"}
