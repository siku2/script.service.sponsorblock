import random
import string

_USER_ID_ALPHABET = string.ascii_letters + string.digits
_USER_ID_LEN = 36


def random_choices(population, amount):  # type: (Sequence[T], int) -> Iterator[T]
    for _ in range(amount):
        yield random.choice(population)


def new_user_id():  # type: () -> str
    """Generate a new user id

    Uses the same format as the official browser extension does.
    See: https://github.com/ajayyy/SponsorBlock/blob/6159605/src/utils.ts#L193
    """
    return "".join(random_choices(_USER_ID_ALPHABET, _USER_ID_LEN))
