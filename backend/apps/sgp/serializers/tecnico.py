from rest_framework import serializers

from apps.core.models import User
from apps.sgp.exceptions import ErroComCodigo
from apps.sgp.models import Tecnico


class TecnicoSerializer(serializers.ModelSerializer):
    user_nome = serializers.CharField(source="user.nome", read_only=True)
    territorio_nome = serializers.CharField(
        source="territorio.nome", read_only=True, allow_null=True
    )
    osc_nome = serializers.CharField(source="osc.nome", read_only=True, allow_null=True)

    class Meta:
        model = Tecnico
        fields = [
            'id', 'user', 'user_nome', 'territorio', 'territorio_nome',
            'osc', 'osc_nome', 'papel', 'ativo',
        ]
        read_only_fields = ['id']
        # A unicidade de `user` é checada em `validate` para devolver o
        # `code` próprio em vez da mensagem genérica do UniqueValidator.
        extra_kwargs = {'user': {'validators': []}}

    def validate(self, attrs):
        instance = self.instance
        user = attrs.get("user", instance.user if instance else None)
        territorio = attrs.get("territorio", instance.territorio if instance else None)
        osc = attrs.get("osc", instance.osc if instance else None)

        outros = Tecnico.objects.filter(user=user)
        if instance is not None:
            outros = outros.exclude(pk=instance.pk)
        if outros.exists():
            raise ErroComCodigo(
                "tecnico_duplicado", "Este usuário já está cadastrado como técnico."
            )

        # OSC sem território cadastrado não tem área de atuação conhecida, então
        # não há como afirmar conflito.
        if territorio is not None and osc is not None:
            territorios_osc = set(osc.territorios.values_list("pk", flat=True))
            if territorios_osc and territorio.pk not in territorios_osc:
                raise ErroComCodigo(
                    "conflito_vinculo", "A OSC selecionada não atua neste território."
                )

        return attrs


class UsuarioElegivelSerializer(serializers.ModelSerializer):
    nome_completo = serializers.CharField(source="nome")

    class Meta:
        model = User
        fields = ["id", "nome_completo", "email"]
