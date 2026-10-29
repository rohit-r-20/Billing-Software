"""
TLS Certificate Management Service for Anti Matrix Mobile Barcode Scanner.
Generates and manages a local Root Certificate Authority (CA) and signed server
leaf certificates with Subject Alternative Names (SANs) for local Wi-Fi IPs.
"""
import os
import socket
import ipaddress
import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

from cryptography import x509
from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from core.logging_config import logger


class CertService:
    """Manages Root CA and TLS server certificate generation with IP SANs."""

    def __init__(self, cert_dir: Optional[Path] = None):
        if cert_dir is None:
            # Default to data/certs inside project root
            base_dir = Path(__file__).resolve().parent.parent
            self.cert_dir = base_dir / "data" / "certs"
        else:
            self.cert_dir = Path(cert_dir)
            
        self.cert_dir.mkdir(parents=True, exist_ok=True)
        self.ca_key_path = self.cert_dir / "ca.key"
        self.ca_crt_path = self.cert_dir / "ca.crt"
        self.server_key_path = self.cert_dir / "server.key"
        self.server_crt_path = self.cert_dir / "server.crt"

    def ensure_ca_certificate(self) -> None:
        """Ensures the Anti Matrix Local Root CA key and certificate exist."""
        if self.ca_key_path.exists() and self.ca_crt_path.exists():
            return

        logger.info("Generating new Anti Matrix Local Root CA key and certificate...")
        ca_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048
        )

        ca_name = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, "IN"),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "Tamilnadu"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Anti Matrix"),
            x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, "Alpha Billing POS"),
            x509.NameAttribute(NameOID.COMMON_NAME, "Anti Matrix Local Root CA"),
        ])

        now = datetime.datetime.now(datetime.timezone.utc)
        ca_cert = (
            x509.CertificateBuilder()
            .subject_name(ca_name)
            .issuer_name(ca_name)
            .public_key(ca_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - datetime.timedelta(days=1))
            .not_valid_after(now + datetime.timedelta(days=3650))  # 10 years validity
            .add_extension(x509.BasicConstraints(ca=True, path_length=1), critical=True)
            .add_extension(
                x509.KeyUsage(
                    digital_signature=True,
                    content_commitment=False,
                    key_encipherment=False,
                    data_encipherment=False,
                    key_agreement=False,
                    key_cert_sign=True,
                    crl_sign=True,
                    encipher_only=False,
                    decipher_only=False,
                ),
                critical=True,
            )
            .add_extension(
                x509.SubjectKeyIdentifier.from_public_key(ca_key.public_key()),
                critical=False,
            )
            .sign(ca_key, hashes.SHA256())
        )

        # Write CA private key
        self.ca_key_path.write_bytes(
            ca_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )
        os.chmod(self.ca_key_path, 0o600)

        # Write CA certificate
        self.ca_crt_path.write_bytes(
            ca_cert.public_bytes(serialization.Encoding.PEM)
        )
        logger.info(f"Root CA created at {self.ca_crt_path}")

    def _cert_contains_ip(self, cert_path: Path, target_ip: str) -> bool:
        """Checks if an existing certificate includes the target IP in its Subject Alternative Names."""
        if not cert_path.exists():
            return False
        try:
            cert_bytes = cert_path.read_bytes()
            cert = x509.load_pem_x509_certificate(cert_bytes)
            # Check expiration
            now = datetime.datetime.now(datetime.timezone.utc)
            if cert.not_valid_after_utc < now + datetime.timedelta(days=30):
                return False

            san_ext = cert.extensions.get_extension_for_oid(x509.ExtensionOID.SUBJECT_ALTERNATIVE_NAME)
            san_values = san_ext.value
            target_ip_obj = ipaddress.ip_address(target_ip)
            for name in san_values:
                if isinstance(name, x509.IPAddress) and name.value == target_ip_obj:
                    return True
        except Exception as e:
            logger.debug(f"Error checking cert SANs: {e}")
            return False
        return False

    def get_or_create_server_certificate(self, lan_ip: str) -> Dict[str, str]:
        """
        Ensures a TLS server certificate exists with SAN entries for lan_ip, 127.0.0.1, and localhost.
        Re-issues leaf certificate signed by existing Root CA if lan_ip is missing.
        """
        self.ensure_ca_certificate()

        # Check if current server cert is valid and covers lan_ip
        if (
            self.server_key_path.exists()
            and self.server_crt_path.exists()
            and self._cert_contains_ip(self.server_crt_path, lan_ip)
        ):
            return {
                "server_crt": str(self.server_crt_path.resolve()),
                "server_key": str(self.server_key_path.resolve()),
                "ca_crt": str(self.ca_crt_path.resolve()),
            }

        logger.info(f"Generating TLS server certificate for LAN IP: {lan_ip}...")

        # Load CA
        ca_key_bytes = self.ca_key_path.read_bytes()
        ca_key = serialization.load_pem_private_key(ca_key_bytes, password=None)
        ca_crt_bytes = self.ca_crt_path.read_bytes()
        ca_cert = x509.load_pem_x509_certificate(ca_crt_bytes)

        # Generate Server Private Key
        server_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048
        )

        server_subject = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, "IN"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Anti Matrix"),
            x509.NameAttribute(NameOID.COMMON_NAME, f"Anti Matrix Scanner ({lan_ip})"),
        ])

        # Prepare SAN list
        san_items: List[x509.GeneralName] = []
        try:
            san_items.append(x509.IPAddress(ipaddress.ip_address(lan_ip)))
        except ValueError:
            pass

        try:
            san_items.append(x509.IPAddress(ipaddress.ip_address("127.0.0.1")))
        except ValueError:
            pass

        san_items.append(x509.DNSName("localhost"))
        san_items.append(x509.DNSName("antimatrix.local"))

        hostname = socket.gethostname()
        if hostname and hostname != "localhost":
            try:
                san_items.append(x509.DNSName(hostname.split(".")[0]))
            except Exception:
                pass

        now = datetime.datetime.now(datetime.timezone.utc)
        server_cert = (
            x509.CertificateBuilder()
            .subject_name(server_subject)
            .issuer_name(ca_cert.subject)
            .public_key(server_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - datetime.timedelta(days=1))
            .not_valid_after(now + datetime.timedelta(days=730))  # 2 years
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .add_extension(
                x509.KeyUsage(
                    digital_signature=True,
                    content_commitment=False,
                    key_encipherment=True,
                    data_encipherment=False,
                    key_agreement=False,
                    key_cert_sign=False,
                    crl_sign=False,
                    encipher_only=False,
                    decipher_only=False,
                ),
                critical=True,
            )
            .add_extension(
                x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]),
                critical=False,
            )
            .add_extension(
                x509.SubjectAlternativeName(san_items),
                critical=False,
            )
            .add_extension(
                x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()),
                critical=False,
            )
            .sign(ca_key, hashes.SHA256())
        )

        # Write server key and cert
        self.server_key_path.write_bytes(
            server_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )
        os.chmod(self.server_key_path, 0o600)

        self.server_crt_path.write_bytes(
            server_cert.public_bytes(serialization.Encoding.PEM)
        )

        logger.info(f"Server certificate issued with SANs: {[str(s) for s in san_items]}")

        return {
            "server_crt": str(self.server_crt_path.resolve()),
            "server_key": str(self.server_key_path.resolve()),
            "ca_crt": str(self.ca_crt_path.resolve()),
        }

    def get_ca_cert_pem(self) -> bytes:
        """Returns the PEM-encoded Root CA certificate."""
        self.ensure_ca_certificate()
        return self.ca_crt_path.read_bytes()


cert_service = CertService()
