from sqlalchemy.orm import declarative_base


class CommonBase:
    """
    A base class for SQLAlchemy declarative models, providing common functionalities like custom string.
    """

    def __str__(self) -> str:
        """
        Generates a string representation of the object's attributes.
        """
        items = []
        for k, v in vars(self).items():
            # Skip SQLAlchemy internal attributes
            if k.startswith("_sa_") or k == "_sa_instance_state":
                continue

            if isinstance(v, str):
                items.append(f'{k}="{v}"')
            else:
                items.append(f"{k}={v}")
        return " ".join(items)


Base = declarative_base(cls=CommonBase)
