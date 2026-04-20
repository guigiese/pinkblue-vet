from .bitlab import BitlabConnector
from .pathoweb import PathoWebConnector

CONNECTORS = {
    "bitlab":    BitlabConnector,
    "pathoweb":  PathoWebConnector,
}
