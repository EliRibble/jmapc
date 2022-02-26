#!/usr/bin/env python3

# Example output:
#
# CoreEchoResponse(data={'hello': 'world'})

import os

from jmapc import Client
from jmapc.methods import CoreEcho


def main() -> None:
    # Create and configure client
    j = Client(
        host=os.environ["JMAP_HOST"],
        user=os.environ["JMAP_USER"],
        password=os.environ["JMAP_PASSWORD"],
    )

    # Prepare a request for the JMAP Core/echo method with some sample data
    method = CoreEcho(data=dict(hello="world"))

    # Call JMAP API with the prepared request
    result = j.call_method(method)

    # Print result
    print(result)


if __name__ == "__main__":
    main()
