from .bitlab import BitlabConnector
from .nexio import NexioConnector

CONNECTORS = {
    "bitlab": BitlabConnector,
    "nexio":  NexioConnector,
}
