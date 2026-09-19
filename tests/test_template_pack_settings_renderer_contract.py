from inspect import Parameter, signature


def _accepts_template_pack_settings(
    paint,
) -> bool:
    parameters = signature(
        paint
    ).parameters

    return (
        "template_pack_settings" in parameters
        or any(
            parameter.kind
            is Parameter.VAR_KEYWORD
            for parameter in parameters.values()
        )
    )


class LegacyRenderer:
    def paint(
        self,
        *,
        painter,
        instance,
    ):
        pass


class ExplicitRenderer:
    def paint(
        self,
        *,
        painter,
        instance,
        template_pack_settings,
    ):
        pass


class KwargsRenderer:
    def paint(
        self,
        *,
        painter,
        instance,
        **kwargs,
    ):
        pass


def test_legacy_renderer_does_not_accept_pack_settings():
    assert not _accepts_template_pack_settings(
        LegacyRenderer().paint
    )


def test_explicit_renderer_accepts_pack_settings():
    assert _accepts_template_pack_settings(
        ExplicitRenderer().paint
    )


def test_kwargs_renderer_accepts_pack_settings():
    assert _accepts_template_pack_settings(
        KwargsRenderer().paint
    )
