#OrderPanel( parent, on_submit, on_cancel, on_flatten,on_panic)
class OrderPanel:

    def get_order_request(
        self
    ) -> dict:
        """
        Build order request.
        """

    def set_symbol(
        self,
        symbol
    ):
        ...

    def set_defaults(
        self,
        offsets
    ):
        ...

    def enable(self):
        ...

    def disable(self):
        ...

    def set_status(
        self,
        text
    ):
        ...