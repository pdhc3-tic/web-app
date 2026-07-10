import hashlib
import hmac
import os
import time
from pathlib import Path
from urllib.parse import quote, urlencode, urlparse, unquote

from django.conf import settings


class StorageObjectNotFound(Exception):
    pass


class R2Storage:
    def __init__(self):
        self.bucket_name = settings.R2_BUCKET_NAME
        self.endpoint_url = settings.R2_ENDPOINT_URL
        self.public_url = settings.R2_PUBLIC_URL.rstrip("/")
        self._client = None

    @property
    def client(self):
        if self._client is None:
            import boto3

            self._client = boto3.client(
                "s3",
                endpoint_url=self.endpoint_url,
                aws_access_key_id=settings.R2_ACCESS_KEY_ID,
                aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
                region_name="auto",
            )
        return self._client

    def generate_presigned_put(self, key, content_type, size, expires_in=300):
        return self.client.generate_presigned_url(
            ClientMethod="put_object",
            Params={
                "Bucket": self.bucket_name,
                "Key": key,
                "ContentType": content_type,
                "ContentLength": size,
            },
            ExpiresIn=expires_in,
            HttpMethod="PUT",
        )

    def head_object(self, key):
        try:
            return self.client.head_object(Bucket=self.bucket_name, Key=key)
        except Exception as exc:
            error = getattr(exc, "response", {}).get("Error", {})
            if str(error.get("Code")) in {"404", "NoSuchKey", "NotFound"}:
                raise StorageObjectNotFound(key) from exc
            raise

    def delete_object(self, key):
        return self.client.delete_object(Bucket=self.bucket_name, Key=key)

    def get_public_url(self, key):
        return f"{self.public_url}/{quote(key)}"

    def get_key_from_url(self, url):
        if not url or not self.public_url:
            return ""

        public = urlparse(self.public_url)
        parsed = urlparse(url)
        if parsed.scheme and parsed.netloc:
            if parsed.netloc != public.netloc:
                return ""
            return unquote(parsed.path.lstrip("/"))

        return ""


class LocalStorage:
    def __init__(self):
        self.media_root = Path(settings.MEDIA_ROOT)
        self.media_url = settings.MEDIA_URL

    def generate_presigned_put(self, key, content_type, size, expires_in=300):
        expires = int(time.time()) + expires_in
        signature = self._sign(key, content_type, size, expires)
        query = urlencode(
            {
                "key": key,
                "content_type": content_type,
                "size": size,
                "expires": expires,
                "signature": signature,
            }
        )
        return f"{settings.LOCAL_STORAGE_UPLOAD_URL}?{query}"

    def head_object(self, key):
        path = self._path_for_key(key)
        if not path.exists():
            raise StorageObjectNotFound(key)
        return {"ContentLength": path.stat().st_size}

    def delete_object(self, key):
        path = self._path_for_key(key)
        if path.exists():
            path.unlink()
        return None

    def get_public_url(self, key):
        return f"{self.media_url.rstrip('/')}/{quote(key)}"

    def get_key_from_url(self, url):
        if not url:
            return ""

        parsed = urlparse(url)
        path = unquote(parsed.path if parsed.scheme else url)
        prefix = self.media_url if self.media_url.startswith("/") else f"/{self.media_url}"
        prefix = prefix.rstrip("/") + "/"
        if path.startswith(prefix):
            return path[len(prefix):]
        return ""

    @staticmethod
    def _sign(key, content_type, size, expires):
        payload = f"{key}:{content_type}:{int(size)}:{int(expires)}".encode()
        secret = settings.SECRET_KEY.encode()
        return hmac.new(secret, payload, hashlib.sha256).hexdigest()

    @classmethod
    def verify_signature(cls, key, content_type, size, expires, signature):
        if int(expires) < int(time.time()):
            return False
        expected = cls._sign(key, content_type, int(size), int(expires))
        return hmac.compare_digest(expected, signature)

    def save_from_bytes(self, key, content):
        path = self._path_for_key(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path

    def _path_for_key(self, key):
        clean_key = os.path.normpath(key).replace("\\", "/")
        if clean_key.startswith("../") or clean_key == ".." or os.path.isabs(clean_key):
            raise ValueError("Key de storage inválida.")
        return self.media_root / clean_key
