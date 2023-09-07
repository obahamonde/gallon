"""Data validation and serialization."""
import base64
import json
from dataclasses import dataclass, is_dataclass
from datetime import datetime
from typing import (Any, Callable, Dict, List, Optional, TypeVar, Union,
                    get_type_hints)
from uuid import UUID

T = TypeVar("T")
Required: Any = Ellipsis
NoArgsCallable = Callable[[], Any]
Json = Union[Dict[str, Any], List[Dict[str, Any]]]


class DataMetaClass(type):
    """
    A metaclass that enforces type annotations on DataFieldModel fields and ensures the
    created class is a dataclass.
    """

    def __new__(mcs, name, bases, attrs):
        """Create a new class instance."""
        for attr_name, attr_value in attrs.items():
            if not isinstance(attr_value, DataFieldModel):
                continue
            if attr_name not in attrs.get("__annotations__", {}):
                raise TypeError(f'Attribute "{attr_name}" must have a type annotation')
        new_class = super().__new__(mcs, name, bases, attrs)
        if not is_dataclass(new_class):
            return dataclass(new_class)  # type: ignore
        return new_class


class DataFieldDescriptor:
    """
    A descriptor for fields in a data class. It enforces type checking during assignment and
    allows field deletion.
    """

    def __init__(self):
        """Initialize the descriptor."""
        self.name = None
        self.type = None

    def __set_name__(self, owner, name):
        """Set the name of the descriptor and get the type hint from the owner class."""
        self.name = name
        self.type = get_type_hints(owner).get(name, Any)

    def __get__(self, instance, owner):
        """Get the value of the field from the instance's dict."""
        if instance is None:
            return self
        return instance.__dict__[self.name]

    def __set__(self, instance, value):
        """Set the value of the field in the instance's dict, enforcing type checks."""
        if self.type is None:
            raise TypeError(f"{self.name} field must have a type annotation")
        instance.__dict__[self.name] = value

    def __delete__(self, instance):
        """Delete the value of the field in the instance's dict."""
        del instance.__dict__[self.name]


class DataFieldModel(DataFieldDescriptor):
    """
    A model for data fields. Extends the base descriptor with additional settings like
    default value, factory function, requirement, index, and unique constraints.
    """

    def __init__(
        self,
        default=None,
        *,
        default_factory=None,
        required=None,
        index=None,
        unique=None,
    ):
        """Initialize the model with the given settings."""
        super().__init__()
        self.default = default
        self.default_factory = default_factory
        self.required = required
        self.index = index
        self.unique = unique

    def __set__(self, instance, value):
        """Set the value of the field in the instance's dict,
        handling defaults and requirement checks."""
        super().__set__(instance, value)
        if self.default == Required and value is None:
            raise ValueError(f"{self.name} is required")
        elif value is None:
            if self.default is not None:
                value = self.default
            elif self.default_factory is not None:
                value = self.default_factory()
        instance.__dict__[self.name] = value

    def __set_name__(self, owner, name):
        """Set the name of the descriptor, get the type hint from the owner class,
        and set up index/unique constraints."""
        self.name = name
        self.type = owner.__annotations__.get(name, Any)
        if self.index is not None:
            indexes = getattr(owner, "__indexes__", {})
            indexes[name] = self.index
            setattr(owner, "__indexes__", indexes)
        if self.unique is not None:
            uniques = getattr(owner, "__uniques__", {})
            uniques[name] = self.unique
            setattr(owner, "__uniques__", uniques)


def field(
    default: Any = None,
    *,
    default_factory: Optional[NoArgsCallable] = None,
    required: Optional[bool] = None,
    index: Optional[bool] = None,
    unique: Optional[bool] = None,
) -> Any:
    """
    A helper function that creates a DataFieldModel with the given settings.
    This function simplifies the creation of data fields in data models.
    """
    return DataFieldModel(
        default=default,
        default_factory=default_factory,
        required=required,
        index=index,
        unique=unique,
    )


class DataClass(metaclass=DataMetaClass):
    """
    A base data class with enforced type annotations. Supports optional settings for fields
    like default values and factory functions, and requirement, index, and unique constraints.
    """

    metadata = {"indexes": [], "uniques": []}

    def __init__(self, **kwargs):
        """Initialize the data class instance with keyword arguments."""
        for name, _ in self.__annotations__.items():  # pylint: disable=no-member
            value = kwargs.get(name)
            if type(value) not in (type(value), DataFieldModel):
                raise TypeError(
                    f"{name} must be of type {self.__annotations__[name]}"  # pylint: disable=no-member
                )  # pylint: disable=no-member
            attr = getattr(self.__class__, name, None)
            if isinstance(attr, DataFieldModel):
                if attr.default == Required and value is None:
                    if attr.default_factory is not None:
                        value = attr.default_factory()
                        if isinstance(value, attr.type) is False:
                            raise TypeError(
                                f"{name} must be of type {attr.type.__name__}"
                            )
                    else:
                        raise ValueError(f"{name} is required")
                elif value is None:
                    if attr.default is not None:
                        if isinstance(attr.default, attr.type):
                            value = attr.default
                            if isinstance(value, attr.type) is False:
                                raise TypeError(
                                    f"{name} must be of type {attr.type.__name__}"
                                )
                    elif attr.default_factory is not None:
                        value = attr.default_factory()
                        if isinstance(value, attr.type) is False:
                            raise TypeError(
                                f"{name} must be of type {attr.type.__name__}"
                            )
                if attr.index is not None:
                    self.metadata["indexes"].append(name)
                if attr.unique is not None:
                    self.metadata["uniques"].append(name)
            setattr(self, name, value)

    def __repr__(self):
        """Return a string representation of the data class instance."""
        return f"<{self.__class__.__name__} {self.__dict__}>"


class GallonEncoder(json.JSONEncoder):
    """
    A JSONEncoder subclass that knows how to encode date/time, UUID, bytes, and custom types.
    """

    def default(self, o):
        """Return a serializable version of the given object."""
        if isinstance(o, datetime):
            return o.astimezone().isoformat()
        if isinstance(o, UUID):
            return str(o)
        if isinstance(o, bytes):
            try:
                return o.decode()
            except UnicodeDecodeError:
                return base64.b64encode(o).decode()
        if hasattr(o, "json"):
            return o.json()
        return super().default(o)


def parse(dct: dict, exclude_none: bool = True):
    """
    Convert a dictionary to a JSON-formatted string and then parse it back to a dictionary.
    This is used to serialize and then deserialize a dictionary, effectively cloning it.
    Optionally exclude entries with None values.
    """
    string = json.dumps(dct, cls=GallonEncoder)
    if exclude_none:
        return json.loads(string)
    return json.loads(string)


class GallonModel(DataClass):
    """
    A data class that can convert itself to a dictionary or a JSON-formatted string.
    """

    def dict(self, exclude_none: bool = True):
        """Return a dictionary representation of the data model instance."""
        return parse(self.__dict__, exclude_none=exclude_none)

    def json(self, exclude_none: bool = True):
        """Return a JSON-formatted string representation of the data model instance."""
        return json.dumps(
            self.dict(exclude_none=exclude_none), cls=GallonEncoder, indent=4
        )


def dumps(obj, exclude_none: bool = True):
    """
    Convert an object to a JSON-formatted string.
    The object must be serializable by a GallonEncoder.
    Optionally exclude entries with None values.
    """
    return json.dumps(
        parse(obj, exclude_none=exclude_none), cls=GallonEncoder, indent=4
    )


def loads(string):
    """
    Parse a JSON-formatted string and convert it back to an object.
    """
    return json.loads(dumps(string))
