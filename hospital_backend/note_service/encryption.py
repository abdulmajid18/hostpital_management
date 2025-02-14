from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization, hashes


class EncryptionUtils:
    @staticmethod
    def generate_key_pair():
        """Generate RSA key pair (private & public key)."""

        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )
        public_key = private_key.public_key()

        # Serialize keys
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        return private_pem.decode(), public_pem.decode()

    @staticmethod
    def encrypt_note(note_content: str, public_key_pem: str) -> bytes:
        """Encrypts a note using the recipient's public key."""
        public_key = serialization.load_pem_public_key(public_key_pem.encode())

        encrypted = public_key.encrypt(
            note_content.encode(),
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        return encrypted

    @staticmethod
    def decrypt_note(encrypted_note: bytes, private_key_pem: str) -> str:
        """Decrypts an encrypted note using the patient's private key."""
        private_key = serialization.load_pem_private_key(
            private_key_pem.encode(),
            password=None,
        )
        decrypted = private_key.decrypt(
            encrypted_note,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        return decrypted.decode()
