import base64
import functools
import logging
from http.client import HTTPResponse

from .data import GallonModel, dumps
from .objects import Response


@functools.singledispatch
def make_response(response: Response):
    """Return the response"""
    return response


@make_response.register(HTTPResponse)
def _(response: HTTPResponse):
    """Return the response"""
    try:
        data = response.read().decode("utf-8")
    except:
        data = base64.b64encode(response.read()).decode(
            "utf-8"
        )  # pylint: disable=bare-except
    return Response(
        status=response.status,
        headers=dict(response.getheaders()),
        body=data,
    )


@make_response.register(Response)
def _(response: Response):
    """Return the response"""
    return response


@make_response.register(str)
def _(response: str):
    if response.startswith("<"):
        return make_response(
            Response(
                status=200,
                headers={"Content-Type": "text/html"},
                body=response,
            )
        )
    return make_response(
        Response(
            status=200,
            headers={"Content-Type": "text/plain"},
            body=response,
        )
    )


@make_response.register(dict)
def _(response: dict):
    return make_response(
        Response(
            status=200,
            headers={"Content-Type": "application/json"},
            body=dumps(response),
        )
    )


@make_response.register(GallonModel)
def _(response: GallonModel):
    return make_response(
        Response(
            status=200,
            headers={"Content-Type": "application/json"},
            body=dumps(response.dict()),
        )
    )


@make_response.register(list)
def _(response: list):
    _response = [dumps(r) for r in response]
    return make_response(
        Response(
            status=200,
            headers={"Content-Type": "application/json"},
            body=dumps(_response),
        )
    )


def setup_logger():
    """Setup the logger"""
    logger = logging.getLogger("Gallon Server")
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    )
    logger.addHandler(handler)
    return logger
