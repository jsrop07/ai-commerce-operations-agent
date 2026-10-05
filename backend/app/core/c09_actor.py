"""Shared C09 trusted actor identifier validation."""

import re

_ACTOR = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")


def valid_c09_actor_id(actor_id: str) -> bool:
    return bool(_ACTOR.fullmatch(actor_id))
