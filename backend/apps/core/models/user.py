from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from .role import Role
from apps.core.models.territory import Territory

class UserManager(BaseUserManager):
    def create_user(self, email: str, nome: str, role=None, password: str | None = None):
        if not email:
            raise ValueError("O email é obrigatório.")
        if not nome:
            raise ValueError("O nome é obrigatório.")

        user = self.model(
            email=self.normalize_email(email),
            nome=nome,
            role=role,
        )
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(
        self,
        email: str,
        nome: str,
        password: str | None = None,
        role=None,
    ):
        if password is None:
            raise ValueError("Superusuário precisa de senha.")

        user = self.create_user(
            email=email,
            nome=nome,
            password=password,
            role=role,
        )
        user.is_superuser = True
        user.ativo = True
        user.save(using=self._db)
        return user


class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)
    nome = models.CharField(max_length=255)
    ativo = models.BooleanField(default=True)
    telefone = models.CharField(max_length=20, blank=True, default="")
    whatsapp = models.CharField(max_length=20, blank=True, default="")
    foto_url = models.URLField(blank=True, default="")
    ultimo_login = models.DateTimeField(null=True, blank=True)

    role = models.ForeignKey(Role, on_delete=models.PROTECT, null=True, blank=True, related_name="users")
    territorios = models.ManyToManyField(Territory, blank=True, related_name="users")

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["nome"]

    class Meta:
        verbose_name = "Usuario"
        verbose_name_plural = "Users"
        ordering = ["email"]
        indexes = [models.Index(fields=["ultimo_login"], name="idx_user_ultimo_login")]


    @property
    def is_active(self):
        return self.ativo

    @is_active.setter
    def is_active(self, value):
        self.ativo = value

    @property
    def is_staff(self) -> bool:
        return self.is_superuser

    @property
    def last_login(self):
        return self.ultimo_login

    @last_login.setter
    def last_login(self, value):
        self.ultimo_login = value

    def save(self, *args, **kwargs):
        update_fields = kwargs.get("update_fields")
        if update_fields and "last_login" in update_fields:
            update_fields = set(update_fields)
            update_fields.discard("last_login")
            update_fields.add("ultimo_login")
            kwargs["update_fields"] = update_fields
        return super().save(*args, **kwargs)

    def __str__(self) -> str:
        return str(self.email)

