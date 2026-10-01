"""Container entrypoint: persistent secrets, uploads, and one scheduler worker."""
import base64
import os
import secrets
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec


def configure_runtime():
    data_dir = Path(os.environ.get("DATA_DIR", "/data"))
    data_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("UPLOAD_DIR", str(data_dir / "uploads"))
    if not os.environ.get("SESSION_SECRET"):
        path = data_dir / "session_secret"
        if not path.exists():
            path.write_text(secrets.token_urlsafe(48), encoding="utf-8")
            path.chmod(0o600)
        os.environ["SESSION_SECRET"] = path.read_text(encoding="utf-8").strip()
    if not os.environ.get("VAPID_PRIVATE_KEY_PATH"):
        path = data_dir / "vapid_private.pem"
        if not path.exists():
            key = ec.generate_private_key(ec.SECP256R1())
            path.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
            path.chmod(0o600)
        os.environ["VAPID_PRIVATE_KEY_PATH"] = str(path)
    if not os.environ.get("VAPID_PUBLIC_KEY"):
        key = serialization.load_pem_private_key(Path(os.environ["VAPID_PRIVATE_KEY_PATH"]).read_bytes(), password=None)
        public = key.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
        os.environ["VAPID_PUBLIC_KEY"] = base64.urlsafe_b64encode(public).decode().rstrip("=")


if __name__ == "__main__":
    configure_runtime()
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=int(os.environ.get("PORT", "8003")), workers=1)
