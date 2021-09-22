from durin import permissions

from .settings import TEST_CLIENT_NAME


class CustomAllowSpecificClients(permissions.AllowSpecificClients):

    allowed_clients_name = (TEST_CLIENT_NAME,)


class CustomDisallowSpecificClients(permissions.DisallowSpecificClients):

    disallowed_clients_name = (TEST_CLIENT_NAME,)
