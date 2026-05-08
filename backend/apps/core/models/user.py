class UserManager(BaseUserManager):
    def create_user(self, email: str, nome: str, perfil: str, password: str | None = None):
        if not email:
            raise ValueError("O email é obrigatório.")
        if not nome:
            raise ValueError("O nome é obrigatório.")
        if not perfil:
            raise ValueError("O perfil é obrigatório.")

        user = self.model(
            email=self.normalize_email(email),
            nome=nome,
            perfil=perfil,
        )
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(
        self,
        email: str,
        nome: str,
        perfil: str = "super_admin",
        password: str | None = None,
    ):
        if password is None:
            raise ValueError("Superusuário precisa de senha.")

        user = self.create_user(
            email=email,
            nome=nome,
            perfil=perfil,
            password=password,
        )
        user.is_staff = True
        user.is_superuser = True
        user.ativo = True
        user.save(using=self._db)
        return user


class User(AbstractBaseUser, PermissionsMixin):
    class PerfilChoices(models.TextChoices):
        AGRICULTOR_BENEFICIARIO = (
            "agricultor_beneficiario",
            "Agricultor / Beneficiário",
        )
        TECNICO_CAMPO_ADT_ACR = "tecnico_campo_adt_acr", "ADT / ACR — Técnico de campo"
        ARTICULADOR_ESTADUAL = "articulador_estadual", "Articulador Estadual"
        UGP_COORDENACAO = "ugp_coordenacao", "UGP — Coordenação territorial"
        FGD_EQUIPE_FUNDACAO = "fgd_equipe_fundacao", "FGD — Equipe Fundação"
        SUPER_ADMIN = "super_admin", "UFERSA / Equipe técnica (Super Admin)"

    email = models.EmailField(unique=True)
    nome = models.CharField(max_length=255)
    ativo = models.BooleanField(default=True)
    ultimo_login = models.DateTimeField(null=True, blank=True)
    perfil = models.CharField(max_length=50, choices=PerfilChoices.choices)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["nome", "perfil"]

    class Meta:
        ordering = ["-date_joined"]
        verbose_name = "usuário"
        verbose_name_plural = "usuários"
        indexes = [
            models.Index(fields=["ativo", "ultimo_login"], name="core_usr_ativo_login_idx"),
        ]

    @property
    def is_active(self):
        return self.ativo

    @is_active.setter
    def is_active(self, value):
        self.ativo = value

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



