from .backends import get_storage


# Na saída do serializer, troca as URLs de arquivo gravadas pela URL de leitura: no
# storage local, a URL assinada com validade (o nginx não serve /media/). Os campos
# continuam os do model, então o schema OpenAPI não muda. (Comentário, e não
# docstring: o drf-spectacular publicaria a docstring como descrição dos serializers.)
class SignedMediaUrlsMixin:

    signed_media_url_fields: tuple[str, ...] = ()

    def to_representation(self, instance):
        data = super().to_representation(instance)
        storage = get_storage()
        for field in self.signed_media_url_fields:
            if data.get(field):
                data[field] = storage.sign_url(data[field])
        return data
