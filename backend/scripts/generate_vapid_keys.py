"""Generate a local VAPID key pair without printing the private key."""

import argparse
import base64
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="replace an existing local VAPID private key")
    args = parser.parse_args()

    backend_dir = Path(__file__).resolve().parents[1]
    private_path = backend_dir / "data" / "vapid_private.pem"
    if private_path.exists() and not args.force:
        raise SystemExit(f"{private_path} already exists. Use --force only when intentionally rotating keys.")
    private_path.parent.mkdir(parents=True, exist_ok=True)

    private_key = ec.generate_private_key(ec.SECP256R1())
    private_path.write_bytes(private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ))
    public_key = private_key.public_key().public_bytes(
        serialization.Encoding.X962,
        serialization.PublicFormat.UncompressedPoint,
    )
    public_key_text = base64.urlsafe_b64encode(public_key).decode("ascii").rstrip("=")
    print("VAPID key pair generated.")
    print(f"Private key file: {private_path}")
    print(f"Set VAPID_PUBLIC_KEY={public_key_text} in backend/.env")
    print("Keep the private key file secret and back it up securely; existing subscriptions depend on this key.")


if __name__ == "__main__":
    main()
