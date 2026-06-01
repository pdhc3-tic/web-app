def create_user(*, user_model, validated_data):
    territorios = validated_data.pop("territorios", [])
    password = validated_data.pop("password", None)
    role = validated_data.pop("role", None)
    user = user_model(**validated_data)

    if password:
        user.set_password(password)
    if role is not None:
        user.role = role

    user.save()

    if territorios:
        user.territorios.set(territorios)

    return user


def update_user(*, user, validated_data):
    territorios = validated_data.pop("territorios", None)
    password = validated_data.pop("password", None)
    role = validated_data.pop("role", None)

    for attr, value in validated_data.items():
        setattr(user, attr, value)

    if password:
        user.set_password(password)
    if role is not None:
        user.role = role

    user.save()

    if territorios is not None:
        user.territorios.set(territorios)

    return user
